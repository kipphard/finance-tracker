"""Thin query helpers shared by connectors, the aggregator, and the API.

These add + flush (so server-side ids/defaults populate) but do not commit; the caller
controls the transaction boundary.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session

from backend.persistence.models import (
    Account,
    Balance,
    Cadence,
    CashflowDirection,
    CashflowItem,
    Category,
    CategoryKind,
    Connection,
    ConnectionStatus,
    NetWorthSnapshot,
    Recurring,
    Rule,
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


# --- categories (taxonomy) -----------------------------------------------


def create_category(
    session: Session, *, name: str, kind: CategoryKind, is_fixed: bool = False
) -> Category:
    category = Category(name=name, kind=kind, is_fixed=is_fixed)
    session.add(category)
    session.flush()
    return category


def get_category(session: Session, category_id: uuid.UUID) -> Category | None:
    return session.get(Category, category_id)


def get_category_by_name(session: Session, name: str) -> Category | None:
    return session.execute(
        select(Category).where(Category.name == name)
    ).scalars().first()


def list_categories(session: Session) -> list[Category]:
    return list(session.execute(select(Category).order_by(Category.name)).scalars().all())


def update_category(session: Session, category: Category, **fields) -> Category:
    for key, value in fields.items():
        if value is not None:
            setattr(category, key, value)
    session.flush()
    return category


def delete_category(session: Session, category_id: uuid.UUID) -> bool:
    """Delete a category, detaching transactions and removing its rules."""
    category = session.get(Category, category_id)
    if category is None:
        return False
    session.execute(
        update(Transaction)
        .where(Transaction.category_id == category_id)
        .values(category_id=None)
    )
    session.execute(delete(Rule).where(Rule.category_id == category_id))
    session.delete(category)
    session.flush()
    return True


# --- rules (categorization) ----------------------------------------------


def create_rule(
    session: Session,
    *,
    match_pattern: str,
    category_id: uuid.UUID,
    priority: int = 100,
) -> Rule:
    rule = Rule(match_pattern=match_pattern, category_id=category_id, priority=priority)
    session.add(rule)
    session.flush()
    return rule


def get_rule(session: Session, rule_id: uuid.UUID) -> Rule | None:
    return session.get(Rule, rule_id)


def list_rules(session: Session) -> list[Rule]:
    # Highest priority first; ties broken by pattern for determinism.
    stmt = select(Rule).order_by(Rule.priority.desc(), Rule.match_pattern)
    return list(session.execute(stmt).scalars().all())


def find_rule_by_pattern(
    session: Session, match_pattern: str, category_id: uuid.UUID
) -> Rule | None:
    stmt = select(Rule).where(
        Rule.match_pattern == match_pattern, Rule.category_id == category_id
    )
    return session.execute(stmt).scalars().first()


def update_rule(session: Session, rule: Rule, **fields) -> Rule:
    for key, value in fields.items():
        if value is not None:
            setattr(rule, key, value)
    session.flush()
    return rule


def delete_rule(session: Session, rule_id: uuid.UUID) -> bool:
    rule = session.get(Rule, rule_id)
    if rule is None:
        return False
    session.delete(rule)
    session.flush()
    return True


# --- transactions (read/update; writes go through upsert_transaction) ----


def get_transaction(session: Session, txn_id: uuid.UUID) -> Transaction | None:
    return session.get(Transaction, txn_id)


def list_transactions(
    session: Session,
    *,
    account_id: uuid.UUID | None = None,
    category_id: uuid.UUID | None = None,
    uncategorized: bool = False,
) -> list[Transaction]:
    stmt = select(Transaction).order_by(Transaction.ts.desc())
    if account_id is not None:
        stmt = stmt.where(Transaction.account_id == account_id)
    if category_id is not None:
        stmt = stmt.where(Transaction.category_id == category_id)
    if uncategorized:
        stmt = stmt.where(Transaction.category_id.is_(None))
    return list(session.execute(stmt).scalars().all())


# --- recurring (detected subscriptions) ----------------------------------


def create_recurring(
    session: Session,
    *,
    payee: str,
    amount_est: Decimal,
    cadence: str,
    next_due,
    account_id: uuid.UUID,
) -> Recurring:
    recurring = Recurring(
        payee=payee,
        amount_est=amount_est,
        cadence=cadence,
        next_due=next_due,
        account_id=account_id,
    )
    session.add(recurring)
    session.flush()
    return recurring


def list_recurring(session: Session) -> list[Recurring]:
    return list(
        session.execute(select(Recurring).order_by(Recurring.next_due)).scalars().all()
    )


def delete_all_recurring(session: Session) -> int:
    result = session.execute(delete(Recurring))
    session.flush()
    return result.rowcount or 0


# --- reports --------------------------------------------------------------


def spending_by_category(session: Session) -> list[tuple]:
    """Aggregate transaction amounts grouped by category_id -> (category_id, total, count)."""
    stmt = select(
        Transaction.category_id,
        func.coalesce(func.sum(Transaction.amount), 0),
        func.count(),
    ).group_by(Transaction.category_id)
    return list(session.execute(stmt).all())
