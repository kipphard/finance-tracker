"""Manual account + balance entry endpoints."""
from __future__ import annotations

import uuid
from datetime import datetime, time, timezone
from decimal import Decimal

from fastapi import APIRouter, HTTPException, Response

from backend.api.deps import CurrentUser, SessionDep
from backend.connectors.manual import ManualConnector
from backend.persistence import repository
from backend.persistence.models import CategoryKind
from backend.schemas import (
    AccountCreate,
    AccountOut,
    AccountUpdate,
    BalanceCreate,
    BalanceOut,
    ReconcileIn,
    ReconcileOut,
    ReconciliationOut,
    ReconcilePreviewOut,
)

router = APIRouter(prefix="/accounts", tags=["accounts"])

# Smallest delta worth booking an adjusting entry for (rounding noise below this is a no-op).
_RECONCILE_EPSILON = Decimal("0.005")
_ADJUST_CATEGORY = "Balance adjustment"


def _account_out(session, account) -> AccountOut:
    out = AccountOut.model_validate(account)
    out.latest_balance = repository.account_balance(session, account)
    return out


@router.post("", response_model=AccountOut, status_code=201)
def create_account(
    payload: AccountCreate, session: SessionDep, user: CurrentUser
) -> AccountOut:
    connector = ManualConnector(session, user.id)
    account = connector.add_account(
        type=payload.type,
        name=payload.name,
        currency=payload.currency,
        institution=payload.institution,
        expected_return=payload.expected_return,
    )
    session.commit()
    return _account_out(session, account)


@router.get("", response_model=list[AccountOut])
def list_accounts(session: SessionDep, user: CurrentUser) -> list[AccountOut]:
    return [_account_out(session, a) for a in repository.list_accounts(session, user.id)]


@router.get("/{account_id}", response_model=AccountOut)
def get_account(account_id: uuid.UUID, session: SessionDep, user: CurrentUser) -> AccountOut:
    account = repository.get_account(session, account_id, user.id)
    if account is None:
        raise HTTPException(status_code=404, detail="account not found")
    return _account_out(session, account)


@router.patch("/{account_id}", response_model=AccountOut)
def update_account(
    account_id: uuid.UUID, payload: AccountUpdate, session: SessionDep, user: CurrentUser
) -> AccountOut:
    account = repository.get_account(session, account_id, user.id)
    if account is None:
        raise HTTPException(status_code=404, detail="account not found")
    repository.update_account(session, account, **payload.model_dump(exclude_unset=True))
    session.commit()
    return _account_out(session, account)


@router.delete("/{account_id}", status_code=204)
def delete_account(account_id: uuid.UUID, session: SessionDep, user: CurrentUser) -> Response:
    """Delete an account and all its transactions/attachments/balances."""
    if not repository.delete_account(session, account_id, user.id):
        raise HTTPException(status_code=404, detail="account not found")
    session.commit()
    return Response(status_code=204)


@router.post("/{account_id}/balances", response_model=BalanceOut, status_code=201)
def add_balance(
    account_id: uuid.UUID, payload: BalanceCreate, session: SessionDep, user: CurrentUser
) -> BalanceOut:
    if repository.get_account(session, account_id, user.id) is None:
        raise HTTPException(status_code=404, detail="account not found")
    connector = ManualConnector(session, user.id)
    balance = connector.add_balance(
        account_id=account_id, amount=payload.amount, ts=payload.ts
    )
    session.commit()
    return BalanceOut.model_validate(balance)


@router.get("/{account_id}/balances", response_model=list[BalanceOut])
def list_balances(
    account_id: uuid.UUID, session: SessionDep, user: CurrentUser
) -> list[BalanceOut]:
    if repository.get_account(session, account_id, user.id) is None:
        raise HTTPException(status_code=404, detail="account not found")
    return [
        BalanceOut.model_validate(b)
        for b in repository.list_balances(session, account_id)
    ]


# --- reconciliation -------------------------------------------------------


def _require_manual_account(session, account_id: uuid.UUID, user_id: uuid.UUID):
    account = repository.get_account(session, account_id, user_id)
    if account is None:
        raise HTTPException(status_code=404, detail="account not found")
    if account.connection_id is not None:
        raise HTTPException(
            status_code=400, detail="only manual accounts can be reconciled"
        )
    return account


def _as_of_dt(as_of) -> datetime:
    """End of the asserted day, so same-day transactions count toward the computed balance."""
    return datetime.combine(as_of, time.max, tzinfo=timezone.utc)


@router.post("/{account_id}/reconcile/preview", response_model=ReconcilePreviewOut)
def reconcile_preview(
    account_id: uuid.UUID, payload: ReconcileIn, session: SessionDep, user: CurrentUser
) -> ReconcilePreviewOut:
    account = _require_manual_account(session, account_id, user.id)
    computed = repository.account_balance_as_of(session, account, _as_of_dt(payload.as_of))
    return ReconcilePreviewOut(
        account_id=account_id,
        as_of=payload.as_of,
        computed_balance=computed,
        asserted_balance=payload.asserted_balance,
        delta=payload.asserted_balance - computed,
        currency=account.currency,
    )


@router.post("/{account_id}/reconcile", response_model=ReconcileOut)
def reconcile(
    account_id: uuid.UUID, payload: ReconcileIn, session: SessionDep, user: CurrentUser
) -> ReconcileOut:
    account = _require_manual_account(session, account_id, user.id)
    as_of_dt = _as_of_dt(payload.as_of)
    computed = repository.account_balance_as_of(session, account, as_of_dt)
    delta = payload.asserted_balance - computed
    # Date the entry no later than now, so it's realized in the *current* balance immediately
    # (a ts at end-of-today would be in the future and wouldn't count until the day ends).
    txn_ts = min(as_of_dt, datetime.now(timezone.utc))

    if abs(delta) < _RECONCILE_EPSILON:
        return ReconcileOut(
            account_id=account_id, as_of=payload.as_of, computed_balance=computed,
            asserted_balance=payload.asserted_balance, delta=delta, currency=account.currency,
            adjusted=False, transaction_id=None,
        )

    category = repository.get_category_by_name(session, user.id, _ADJUST_CATEGORY)
    if category is None:
        category = repository.create_category(
            session, user_id=user.id, name=_ADJUST_CATEGORY, kind=CategoryKind.expense
        )
    # is_transfer keeps the entry out of income/expense + the EÜR, while account_balance (which
    # ignores is_transfer) still counts it — exactly what corrects the drift.
    txn, _created = repository.upsert_transaction(
        session,
        user_id=user.id,
        account_id=account_id,
        ts=txn_ts,
        amount=delta,
        currency=account.currency,
        hash=f"rec:{uuid.uuid4().hex}",  # must fit Transaction.hash (varchar 64)
        raw_payee="Balance reconciliation",
        description=f"Asserted {payload.asserted_balance} on {payload.as_of}",
        is_transfer=True,
    )
    txn.category_id = category.id  # upsert_transaction takes no category_id; set it post-create
    session.flush()
    repository.create_reconciliation(
        session, user_id=user.id, account_id=account_id, as_of=payload.as_of,
        asserted_balance=payload.asserted_balance, computed_balance=computed, delta=delta,
        transaction_id=txn.id,
    )
    session.commit()
    return ReconcileOut(
        account_id=account_id, as_of=payload.as_of, computed_balance=computed,
        asserted_balance=payload.asserted_balance, delta=delta, currency=account.currency,
        adjusted=True, transaction_id=txn.id,
    )


@router.get("/{account_id}/reconcile/history", response_model=list[ReconciliationOut])
def reconcile_history(
    account_id: uuid.UUID, session: SessionDep, user: CurrentUser
) -> list[ReconciliationOut]:
    if repository.get_account(session, account_id, user.id) is None:
        raise HTTPException(status_code=404, detail="account not found")
    return [
        ReconciliationOut.model_validate(r)
        for r in repository.list_reconciliations(session, user.id, account_id)
    ]
