"""Manual account + balance entry endpoints."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, Response

from backend.api.deps import CurrentUser, SessionDep
from backend.connectors.manual import ManualConnector
from backend.persistence import repository
from backend.schemas import (
    AccountCreate,
    AccountOut,
    AccountUpdate,
    BalanceCreate,
    BalanceOut,
)

router = APIRouter(prefix="/accounts", tags=["accounts"])


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
