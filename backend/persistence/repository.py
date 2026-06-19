"""Thin query helpers shared by connectors, the aggregator, and the API.

These add + flush (so server-side ids/defaults populate) but do not commit; the caller
controls the transaction boundary.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from backend.persistence.models import (
    Account,
    Balance,
    Cadence,
    CashflowDirection,
    CashflowItem,
    Connection,
    ConnectionStatus,
    NetWorthSnapshot,
    Transaction,
)


def create_account(
    session: Session,
    *,
    connector: str,
    type_: str,
    name: str,
    currency: str,
    institution: str | None = None,
    connection_id: uuid.UUID | None = None,
    external_id: str | None = None,
) -> Account:
    account = Account(
        connector=connector,
        type=type_,
        name=name,
        currency=currency,
        institution=institution,
        connection_id=connection_id,
        external_id=external_id,
    )
    session.add(account)
    session.flush()
    return account


def get_account_by_external_id(session: Session, external_id: str) -> Account | None:
    stmt = select(Account).where(Account.external_id == external_id)
    return session.execute(stmt).scalars().first()


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


# --- connections (provider linkages) -------------------------------------


def create_connection(
    session: Session,
    *,
    connector: str,
    status: ConnectionStatus = ConnectionStatus.pending,
    institution_id: str | None = None,
    requisition_id: str | None = None,
    reference: str | None = None,
    consent_expires_at: datetime | None = None,
) -> Connection:
    connection = Connection(
        connector=connector,
        status=status,
        institution_id=institution_id,
        requisition_id=requisition_id,
        reference=reference,
        consent_expires_at=consent_expires_at,
    )
    session.add(connection)
    session.flush()
    return connection


def get_connection(session: Session, connection_id: uuid.UUID) -> Connection | None:
    return session.get(Connection, connection_id)


def get_connection_by_requisition(
    session: Session, requisition_id: str
) -> Connection | None:
    stmt = select(Connection).where(Connection.requisition_id == requisition_id)
    return session.execute(stmt).scalars().first()


def get_connection_by_reference(session: Session, reference: str) -> Connection | None:
    stmt = select(Connection).where(Connection.reference == reference)
    return session.execute(stmt).scalars().first()


def list_connections(
    session: Session, connector: str | None = None
) -> list[Connection]:
    stmt = select(Connection).order_by(Connection.created_at)
    if connector is not None:
        stmt = stmt.where(Connection.connector == connector)
    return list(session.execute(stmt).scalars().all())


def list_accounts_for_connection(
    session: Session, connection_id: uuid.UUID
) -> list[Account]:
    stmt = select(Account).where(Account.connection_id == connection_id)
    return list(session.execute(stmt).scalars().all())


def upsert_transaction(
    session: Session,
    *,
    account_id: uuid.UUID,
    ts: datetime,
    amount: Decimal,
    currency: str,
    hash: str,
    raw_payee: str | None = None,
    description: str | None = None,
) -> tuple[Transaction, bool]:
    """Insert a transaction or return the existing one (deduped by stable hash). §4.2."""
    existing = session.execute(
        select(Transaction).where(Transaction.hash == hash)
    ).scalars().first()
    if existing is not None:
        return existing, False
    txn = Transaction(
        account_id=account_id,
        ts=ts,
        amount=amount,
        currency=currency,
        raw_payee=raw_payee,
        description=description,
        hash=hash,
    )
    session.add(txn)
    session.flush()
    return txn, True


# --- cashflow items -------------------------------------------------------


def create_cashflow_item(
    session: Session,
    *,
    direction: CashflowDirection,
    name: str,
    amount: Decimal,
    cadence: Cadence,
    currency: str,
    category_id: uuid.UUID | None = None,
    next_due=None,
) -> CashflowItem:
    item = CashflowItem(
        direction=direction,
        name=name,
        amount=amount,
        cadence=cadence,
        currency=currency,
        category_id=category_id,
        next_due=next_due,
    )
    session.add(item)
    session.flush()
    return item


def get_cashflow_item(session: Session, item_id: uuid.UUID) -> CashflowItem | None:
    return session.get(CashflowItem, item_id)


def list_cashflow_items(
    session: Session,
    *,
    direction: CashflowDirection | None = None,
    active_only: bool = False,
) -> list[CashflowItem]:
    stmt = select(CashflowItem).order_by(CashflowItem.created_at)
    if direction is not None:
        stmt = stmt.where(CashflowItem.direction == direction)
    if active_only:
        stmt = stmt.where(CashflowItem.active.is_(True))
    return list(session.execute(stmt).scalars().all())


def update_cashflow_item(
    session: Session, item: CashflowItem, **fields
) -> CashflowItem:
    for key, value in fields.items():
        if value is not None:
            setattr(item, key, value)
    session.flush()
    return item


def delete_cashflow_item(session: Session, item_id: uuid.UUID) -> bool:
    item = session.get(CashflowItem, item_id)
    if item is None:
        return False
    session.delete(item)
    session.flush()
    return True


def delete_connection(session: Session, connection_id: uuid.UUID) -> bool:
    """Purge a connection and all of its accounts/balances/transactions (§8)."""
    connection = session.get(Connection, connection_id)
    if connection is None:
        return False
    account_ids = [
        a.id for a in list_accounts_for_connection(session, connection_id)
    ]
    if account_ids:
        session.execute(delete(Balance).where(Balance.account_id.in_(account_ids)))
        session.execute(
            delete(Transaction).where(Transaction.account_id.in_(account_ids))
        )
        session.execute(delete(Account).where(Account.id.in_(account_ids)))
    session.delete(connection)
    session.flush()
    return True
