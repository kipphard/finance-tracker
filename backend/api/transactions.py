"""Transaction endpoints: manual entry, CSV import, listing, reclassify, batch categorize."""
from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, File, HTTPException, Response, UploadFile

from backend.api.deps import CurrentUser, SessionDep
from backend.categorize.engine import categorize_transaction, recategorize_all
from backend.csv_import import parse_transactions_csv
from backend.persistence import repository
from backend.schemas import (
    CategorizeResultOut,
    ImportResultOut,
    TransactionCreate,
    TransactionOut,
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
    )
    categorize_transaction(session, user.id, txn)
    session.commit()
    return TransactionOut.model_validate(txn)


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
    txn_id: uuid.UUID, payload: TransactionUpdate, session: SessionDep, user: CurrentUser
) -> TransactionOut:
    """Edit any field of a transaction (also used by inline recategorize, which only sends
    category_id). Only the fields present in the request are changed."""
    txn = repository.get_transaction(session, txn_id, user.id)
    if txn is None:
        raise HTTPException(status_code=404, detail="transaction not found")

    data = payload.model_dump(exclude_unset=True)
    remember = data.pop("remember", False)
    if data.get("category_id") is not None:
        if repository.get_category(session, data["category_id"], user.id) is None:
            raise HTTPException(status_code=400, detail="unknown category")
    for key, value in data.items():
        setattr(txn, key, value)

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
