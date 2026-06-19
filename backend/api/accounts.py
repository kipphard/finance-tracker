"""Manual account + balance entry endpoints."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException

from backend.api.deps import CurrentUser, SessionDep
from backend.connectors.manual import ManualConnector
from backend.persistence import repository
from backend.schemas import AccountCreate, AccountOut, BalanceCreate, BalanceOut

router = APIRouter(prefix="/accounts", tags=["accounts"])


def _account_out(session, account) -> AccountOut:
    out = AccountOut.model_validate(account)
    latest = repository.latest_balance(session, account.id)
    out.latest_balance = latest.amount if latest is not None else None
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
