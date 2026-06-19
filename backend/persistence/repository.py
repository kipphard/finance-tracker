"""Thin query helpers shared by connectors, the aggregator, and the API.

These add + flush (so server-side ids/defaults populate) but do not commit; the caller
controls the transaction boundary.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.persistence.models import Account, Balance, NetWorthSnapshot


def create_account(
    session: Session,
    *,
    connector: str,
    type_: str,
    name: str,
    currency: str,
    institution: str | None = None,
) -> Account:
    account = Account(
        connector=connector,
        type=type_,
        name=name,
        currency=currency,
        institution=institution,
    )
    session.add(account)
    session.flush()
    return account


def get_account(session: Session, account_id: uuid.UUID) -> Account | None:
    return session.get(Account, account_id)


def list_accounts(session: Session, connector: str | None = None) -> list[Account]:
    stmt = select(Account).order_by(Account.created_at)
    if connector is not None:
        stmt = stmt.where(Account.connector == connector)
    return list(session.execute(stmt).scalars().all())


def add_balance(
    session: Session,
    *,
    account_id: uuid.UUID,
    amount: Decimal,
    ts: datetime | None = None,
) -> Balance:
    balance = Balance(account_id=account_id, amount=amount)
    if ts is not None:
        balance.ts = ts
    session.add(balance)
    session.flush()
    return balance


def list_balances(session: Session, account_id: uuid.UUID) -> list[Balance]:
    stmt = (
        select(Balance)
        .where(Balance.account_id == account_id)
        .order_by(Balance.ts.desc(), Balance.id.desc())
    )
    return list(session.execute(stmt).scalars().all())


def latest_balance(session: Session, account_id: uuid.UUID) -> Balance | None:
    stmt = (
        select(Balance)
        .where(Balance.account_id == account_id)
        .order_by(Balance.ts.desc(), Balance.id.desc())
        .limit(1)
    )
    return session.execute(stmt).scalars().first()


def save_snapshot(
    session: Session, *, total: Decimal, breakdown: dict
) -> NetWorthSnapshot:
    snapshot = NetWorthSnapshot(total=total, breakdown_json=breakdown)
    session.add(snapshot)
    session.flush()
    return snapshot


def list_snapshots(session: Session) -> list[NetWorthSnapshot]:
    stmt = select(NetWorthSnapshot).order_by(NetWorthSnapshot.ts.desc())
    return list(session.execute(stmt).scalars().all())
