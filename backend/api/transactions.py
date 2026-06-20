"""Transaction endpoints: manual entry, CSV import, listing, reclassify, batch categorize."""
from __future__ import annotations

import calendar
import hashlib
import uuid
from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, File, HTTPException, Query, Response, UploadFile

from backend.api.deps import CurrentUser, SessionDep
from backend.categorize.engine import categorize_transaction, recategorize_all
from backend.csv_import import parse_transactions_csv
from backend.persistence import repository
from backend.persistence.models import Cadence
from backend.schemas import (
    CategorizeResultOut,
    ImportResultOut,
    TransactionCreate,
    TransactionOut,
    TransactionSeriesCreate,
    TransactionSeriesResult,
    TransactionUpdate,
    TransferCreate,
    TransferOut,
)

router = APIRouter(tags=["transactions"])


def _content_hash(account_id, ts, amount, payee, description) -> str:
    raw = f"{account_id}|{ts.isoformat()}|{amount}|{payee or ''}|{description or ''}"
    return hashlib.sha256(raw.encode()).hexdigest()


@router.post(
    "/accounts/{account_id}/transactions", response_model=TransactionOut, status_code=201
)
def add_transaction(
    account_id: uuid.UUID, payload: TransactionCreate, session: SessionDep, user: CurrentUser
) -> TransactionOut:
    account = repository.get_account(session, account_id, user.id)
    if account is None:
        raise HTTPException(status_code=404, detail="account not found")
    txn, _ = repository.upsert_transaction(
        session,
        user_id=user.id,
        account_id=account_id,
        ts=payload.ts,
        amount=payload.amount,
        currency=payload.currency or account.currency,
        hash=uuid.uuid4().hex,
        raw_payee=payload.raw_payee,
        description=payload.description,
        counterparty=payload.counterparty,
        invoice_number=payload.invoice_number,
        vat_rate=payload.vat_rate,
        excluded=payload.excluded,
        tags=payload.tags,
    )
    categorize_transaction(session, user.id, txn)
    session.commit()
    return TransactionOut.model_validate(txn)


_SERIES_MAX = 240  # 20 years monthly — guards against a runaway range


def _add_months(d: date, n: int) -> date:
    idx = d.year * 12 + (d.month - 1) + n
    year, month = idx // 12, idx % 12 + 1
    return date(year, month, min(d.day, calendar.monthrange(year, month)[1]))


def _step(d: date, cadence: Cadence) -> date:
    if cadence == Cadence.weekly:
        return d + timedelta(days=7)
    if cadence == Cadence.biweekly:
        return d + timedelta(days=14)
    if cadence == Cadence.monthly:
        return _add_months(d, 1)
    if cadence == Cadence.quarterly:
        return _add_months(d, 3)
    if cadence == Cadence.yearly:
        return _add_months(d, 12)
    raise HTTPException(status_code=400, detail="cadence must repeat (not one-off)")


@router.post(
    "/accounts/{account_id}/transactions/series",
    response_model=TransactionSeriesResult,
    status_code=201,
)
def add_transaction_series(
    account_id: uuid.UUID,
    payload: TransactionSeriesCreate,
    session: SessionDep,
    user: CurrentUser,
) -> TransactionSeriesResult:
    """Backfill a recurring series: one transaction per period from start to end (inclusive).
    Useful for recording past freelancing months in one go (often as off-balance records)."""
    account = repository.get_account(session, account_id, user.id)
    if account is None:
        raise HTTPException(status_code=404, detail="account not found")
    if payload.end < payload.start:
        raise HTTPException(status_code=400, detail="end must be on or after start")

    series_id = uuid.uuid4()  # links the batch so it can be edited together later
    created = 0
    d = payload.start
    while d <= payload.end:
        if created >= _SERIES_MAX:
            raise HTTPException(status_code=400, detail=f"date range too large (max {_SERIES_MAX} entries)")
        ts = datetime(d.year, d.month, d.day, tzinfo=timezone.utc)
        txn, _ = repository.upsert_transaction(
            session,
            user_id=user.id,
            account_id=account_id,
            ts=ts,
            amount=payload.amount,
            currency=payload.currency or account.currency,
            hash=uuid.uuid4().hex,
            raw_payee=payload.raw_payee,
            description=payload.description,
            counterparty=payload.counterparty,
            invoice_number=payload.invoice_number,
            vat_rate=payload.vat_rate,
            excluded=payload.excluded,
            tags=payload.tags,
            series_id=series_id,
        )
        categorize_transaction(session, user.id, txn)
        created += 1
        d = _step(d, payload.cadence)
    session.commit()
    return TransactionSeriesResult(created=created)


@router.post("/transfers", response_model=TransferOut, status_code=201)
def create_transfer(
    payload: TransferCreate, session: SessionDep, user: CurrentUser
) -> TransferOut:
    """Move money between two of the user's accounts in one step: books a matching outflow on
    the source and inflow on the destination. Net worth is unchanged (the two legs cancel)."""
    if payload.from_account_id == payload.to_account_id:
        raise HTTPException(status_code=400, detail="cannot transfer to the same account")
    src = repository.get_account(session, payload.from_account_id, user.id)
    dst = repository.get_account(session, payload.to_account_id, user.id)
    if src is None or dst is None:
        raise HTTPException(status_code=404, detail="account not found")

    ts = payload.ts or datetime.now(timezone.utc)
    out_txn, _ = repository.upsert_transaction(
        session,
        user_id=user.id,
        account_id=src.id,
        ts=ts,
        amount=-payload.amount,
        currency=src.currency,
        hash=uuid.uuid4().hex,
        raw_payee=f"Transfer to {dst.name}",
        description=payload.note,
        tags=payload.tags,
        is_transfer=True,
    )
    in_txn, _ = repository.upsert_transaction(
        session,
        user_id=user.id,
        account_id=dst.id,
        ts=ts,
        amount=payload.amount,
        currency=dst.currency,
        hash=uuid.uuid4().hex,
        raw_payee=f"Transfer from {src.name}",
        description=payload.note,
        tags=payload.tags,
        is_transfer=True,
    )
    session.commit()
    return TransferOut(
        from_transaction_id=out_txn.id, to_transaction_id=in_txn.id, amount=payload.amount
    )


@router.post(
    "/accounts/{account_id}/transactions/import",
    response_model=ImportResultOut,
    status_code=201,
)
def import_transactions(
    account_id: uuid.UUID,
    session: SessionDep,
    user: CurrentUser,
    file: UploadFile = File(...),
) -> ImportResultOut:
    account = repository.get_account(session, account_id, user.id)
    if account is None:
        raise HTTPException(status_code=404, detail="account not found")
    content = file.file.read().decode("utf-8-sig")
    try:
        parsed = parse_transactions_csv(content)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    imported = duplicates = categorized = 0
    for row in parsed.rows:
        txn, created = repository.upsert_transaction(
            session,
            user_id=user.id,
            account_id=account_id,
            ts=row.ts,
            amount=row.amount,
            currency=account.currency,
            hash=_content_hash(account_id, row.ts, row.amount, row.raw_payee, row.description),
            raw_payee=row.raw_payee,
            description=row.description,
        )
        if not created:
            duplicates += 1
            continue
        imported += 1
        if categorize_transaction(session, user.id, txn):
            categorized += 1
    session.commit()
    return ImportResultOut(
        imported=imported,
        skipped_duplicates=duplicates,
        skipped_invalid=parsed.skipped,
        categorized=categorized,
    )


@router.get("/accounts/{account_id}/transactions", response_model=list[TransactionOut])
def list_account_transactions(
    account_id: uuid.UUID, session: SessionDep, user: CurrentUser
) -> list[TransactionOut]:
    if repository.get_account(session, account_id, user.id) is None:
        raise HTTPException(status_code=404, detail="account not found")
    return [
        TransactionOut.model_validate(t)
        for t in repository.list_transactions(session, user.id, account_id=account_id)
    ]


@router.get("/transactions", response_model=list[TransactionOut])
def list_transactions(
    session: SessionDep,
    user: CurrentUser,
    account_id: uuid.UUID | None = None,
    category_id: uuid.UUID | None = None,
    uncategorized: bool = False,
) -> list[TransactionOut]:
    return [
        TransactionOut.model_validate(t)
        for t in repository.list_transactions(
            session, user.id, account_id=account_id, category_id=category_id,
            uncategorized=uncategorized,
        )
    ]


@router.post("/transactions/categorize", response_model=CategorizeResultOut)
def categorize_existing(
    session: SessionDep, user: CurrentUser, only_uncategorized: bool = True
) -> CategorizeResultOut:
    count = recategorize_all(session, user.id, only_uncategorized=only_uncategorized)
    session.commit()
    return CategorizeResultOut(categorized=count)


@router.get("/transactions/{txn_id}", response_model=TransactionOut)
def get_transaction(txn_id: uuid.UUID, session: SessionDep, user: CurrentUser) -> TransactionOut:
    txn = repository.get_transaction(session, txn_id, user.id)
    if txn is None:
        raise HTTPException(status_code=404, detail="transaction not found")
    return TransactionOut.model_validate(txn)


@router.patch("/transactions/{txn_id}", response_model=TransactionOut)
def update_transaction(
    txn_id: uuid.UUID,
    payload: TransactionUpdate,
    session: SessionDep,
    user: CurrentUser,
    scope: str = Query("single"),
) -> TransactionOut:
    """Edit a transaction. With ?scope=series the same changes (except the date) are applied to
    every transaction sharing this one's series_id — i.e. the whole recurring/backfilled series."""
    txn = repository.get_transaction(session, txn_id, user.id)
    if txn is None:
        raise HTTPException(status_code=404, detail="transaction not found")

    data = payload.model_dump(exclude_unset=True)
    remember = data.pop("remember", False)
    if data.get("category_id") is not None:
        if repository.get_category(session, data["category_id"], user.id) is None:
            raise HTTPException(status_code=400, detail="unknown category")
    if data.get("account_id") is not None:
        if repository.get_account(session, data["account_id"], user.id) is None:
            raise HTTPException(status_code=400, detail="unknown account")
    if "tags" in data:
        data["tags"] = repository.normalize_tags(data["tags"])
    for key, value in data.items():
        setattr(txn, key, value)

    # Apply to the rest of the series (keep each occurrence's own date).
    if scope == "series" and txn.series_id is not None:
        shared = {k: v for k, v in data.items() if k != "ts"}
        if shared:
            for other in repository.list_transactions_in_series(session, user.id, txn.series_id):
                if other.id == txn.id:
                    continue
                for key, value in shared.items():
                    setattr(other, key, value)

    if remember and txn.category_id is not None and txn.raw_payee:
        if (
            repository.find_rule_by_pattern(session, user.id, txn.raw_payee, txn.category_id)
            is None
        ):
            repository.create_rule(
                session, user_id=user.id, match_pattern=txn.raw_payee,
                category_id=txn.category_id, priority=200,
            )
    session.commit()
    return TransactionOut.model_validate(txn)


@router.delete("/transactions/{txn_id}", status_code=204)
def delete_transaction(
    txn_id: uuid.UUID, session: SessionDep, user: CurrentUser
) -> Response:
    if not repository.delete_transaction(session, txn_id, user.id):
        raise HTTPException(status_code=404, detail="transaction not found")
    session.commit()
    return Response(status_code=204)
