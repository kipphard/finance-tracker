"""Query helpers, all scoped to a user (Phase 6 isolation).

Every read/write is filtered by `user_id` so one user can never see or touch another's
data. `balances` is reached only through user-owned accounts (the caller scopes the account
first), so it has no direct user_id.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session

from backend.persistence.models import (
    Account,
    Attachment,
    Balance,
    Budget,
    Cadence,
    CashflowDirection,
    CashflowItem,
    Category,
    CategoryKind,
    Connection,
    ConnectionStatus,
    Debt,
    NetWorthSnapshot,
    Recurring,
    Rule,
    Transaction,
    User,
)


# --- users ----------------------------------------------------------------


def create_user(session: Session, *, email: str, password_hash: str) -> User:
    user = User(email=email, password_hash=password_hash)
    session.add(user)
    session.flush()
    return user


def get_user(session: Session, user_id: uuid.UUID) -> User | None:
    return session.get(User, user_id)


def get_user_by_email(session: Session, email: str) -> User | None:
    return session.execute(select(User).where(User.email == email)).scalars().first()


def delete_user(session: Session, user_id: uuid.UUID) -> bool:
    """GDPR: purge a user and all of their data."""
    user = session.get(User, user_id)
    if user is None:
        return False
    account_ids = [a.id for a in list_accounts(session, user_id)]
    if account_ids:
        session.execute(delete(Balance).where(Balance.account_id.in_(account_ids)))
    for model in (
        Attachment,
        Transaction,
        Recurring,
        Account,
        Rule,
        Budget,
        CashflowItem,
        Debt,
        Category,
        NetWorthSnapshot,
        Connection,
    ):
        session.execute(delete(model).where(model.user_id == user_id))
    session.delete(user)
    session.flush()
    return True


# --- accounts -------------------------------------------------------------


def create_account(
    session: Session,
    *,
    user_id: uuid.UUID,
    connector: str,
    type_: str,
    name: str,
    currency: str,
    institution: str | None = None,
    connection_id: uuid.UUID | None = None,
    external_id: str | None = None,
) -> Account:
    account = Account(
        user_id=user_id,
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


def get_account(
    session: Session, account_id: uuid.UUID, user_id: uuid.UUID
) -> Account | None:
    return session.execute(
        select(Account).where(Account.id == account_id, Account.user_id == user_id)
    ).scalars().first()


def get_account_by_external_id(
    session: Session, user_id: uuid.UUID, external_id: str
) -> Account | None:
    return session.execute(
        select(Account).where(
            Account.user_id == user_id, Account.external_id == external_id
        )
    ).scalars().first()


def list_accounts(
    session: Session, user_id: uuid.UUID, connector: str | None = None
) -> list[Account]:
    stmt = select(Account).where(Account.user_id == user_id).order_by(Account.created_at)
    if connector is not None:
        stmt = stmt.where(Account.connector == connector)
    return list(session.execute(stmt).scalars().all())


# --- balances (scoped via a user-owned account) ---------------------------


def add_balance(
    session: Session, *, account_id: uuid.UUID, amount: Decimal, ts: datetime | None = None
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


def account_balance(session: Session, account: Account) -> Decimal:
    """Bank-linked accounts use their latest synced balance; manual accounts are the sum of
    their transactions (transaction-first)."""
    if account.connection_id is not None:
        latest = latest_balance(session, account.id)
        return Decimal(latest.amount) if latest is not None else Decimal("0")
    total = session.execute(
        select(func.coalesce(func.sum(Transaction.amount), 0)).where(
            Transaction.account_id == account.id
        )
    ).scalar_one()
    return Decimal(str(total))


def update_account(session: Session, account: Account, **fields) -> Account:
    for key, value in fields.items():
        if value is not None:
            setattr(account, key, value)
    session.flush()
    return account


def delete_account(session: Session, account_id: uuid.UUID, user_id: uuid.UUID) -> bool:
    account = get_account(session, account_id, user_id)
    if account is None:
        return False
    txn_ids = [
        t.id for t in list_transactions(session, user_id, account_id=account_id)
    ]
    if txn_ids:
        session.execute(delete(Attachment).where(Attachment.transaction_id.in_(txn_ids)))
    session.execute(delete(Transaction).where(Transaction.account_id == account_id))
    session.execute(delete(Balance).where(Balance.account_id == account_id))
    session.execute(delete(Recurring).where(Recurring.account_id == account_id))
    session.execute(
        update(CashflowItem)
        .where(CashflowItem.account_id == account_id)
        .values(account_id=None)
    )
    session.delete(account)
    session.flush()
    return True


def latest_transaction_ts(session: Session, user_id: uuid.UUID) -> datetime | None:
    return session.execute(
        select(func.max(Transaction.ts)).where(Transaction.user_id == user_id)
    ).scalar_one_or_none()


# --- net worth snapshots --------------------------------------------------


def save_snapshot(
    session: Session, *, user_id: uuid.UUID, total: Decimal, breakdown: dict
) -> NetWorthSnapshot:
    snapshot = NetWorthSnapshot(user_id=user_id, total=total, breakdown_json=breakdown)
    session.add(snapshot)
    session.flush()
    return snapshot


def list_snapshots(session: Session, user_id: uuid.UUID) -> list[NetWorthSnapshot]:
    stmt = (
        select(NetWorthSnapshot)
        .where(NetWorthSnapshot.user_id == user_id)
        .order_by(NetWorthSnapshot.ts.desc())
    )
    return list(session.execute(stmt).scalars().all())


# --- connections (provider linkages) -------------------------------------


def create_connection(
    session: Session,
    *,
    user_id: uuid.UUID,
    connector: str,
    status: ConnectionStatus = ConnectionStatus.pending,
    institution_id: str | None = None,
    requisition_id: str | None = None,
    reference: str | None = None,
    consent_expires_at: datetime | None = None,
) -> Connection:
    connection = Connection(
        user_id=user_id,
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


def get_connection(
    session: Session, connection_id: uuid.UUID, user_id: uuid.UUID
) -> Connection | None:
    return session.execute(
        select(Connection).where(
            Connection.id == connection_id, Connection.user_id == user_id
        )
    ).scalars().first()


def get_connection_by_requisition(
    session: Session, user_id: uuid.UUID, requisition_id: str
) -> Connection | None:
    return session.execute(
        select(Connection).where(
            Connection.user_id == user_id, Connection.requisition_id == requisition_id
        )
    ).scalars().first()


def get_connection_by_reference(
    session: Session, user_id: uuid.UUID, reference: str
) -> Connection | None:
    return session.execute(
        select(Connection).where(
            Connection.user_id == user_id, Connection.reference == reference
        )
    ).scalars().first()


def list_connections(
    session: Session, user_id: uuid.UUID, connector: str | None = None
) -> list[Connection]:
    stmt = (
        select(Connection)
        .where(Connection.user_id == user_id)
        .order_by(Connection.created_at)
    )
    if connector is not None:
        stmt = stmt.where(Connection.connector == connector)
    return list(session.execute(stmt).scalars().all())


def list_accounts_for_connection(
    session: Session, connection_id: uuid.UUID
) -> list[Account]:
    stmt = select(Account).where(Account.connection_id == connection_id)
    return list(session.execute(stmt).scalars().all())


def delete_connection(
    session: Session, connection_id: uuid.UUID, user_id: uuid.UUID
) -> bool:
    """Purge a connection and all of its accounts/balances/transactions (§8)."""
    connection = get_connection(session, connection_id, user_id)
    if connection is None:
        return False
    account_ids = [a.id for a in list_accounts_for_connection(session, connection_id)]
    if account_ids:
        session.execute(delete(Balance).where(Balance.account_id.in_(account_ids)))
        session.execute(delete(Transaction).where(Transaction.account_id.in_(account_ids)))
        session.execute(delete(Account).where(Account.id.in_(account_ids)))
    session.delete(connection)
    session.flush()
    return True


# --- transactions ---------------------------------------------------------


def upsert_transaction(
    session: Session,
    *,
    user_id: uuid.UUID,
    account_id: uuid.UUID,
    ts: datetime,
    amount: Decimal,
    currency: str,
    hash: str,
    raw_payee: str | None = None,
    description: str | None = None,
    counterparty: str | None = None,
    invoice_number: str | None = None,
    vat_rate: Decimal | None = None,
) -> tuple[Transaction, bool]:
    """Insert or return the existing transaction (deduped by (user_id, hash)). §4.2."""
    existing = session.execute(
        select(Transaction).where(
            Transaction.user_id == user_id, Transaction.hash == hash
        )
    ).scalars().first()
    if existing is not None:
        return existing, False
    txn = Transaction(
        user_id=user_id,
        account_id=account_id,
        ts=ts,
        amount=amount,
        currency=currency,
        raw_payee=raw_payee,
        description=description,
        counterparty=counterparty,
        invoice_number=invoice_number,
        vat_rate=vat_rate,
        hash=hash,
    )
    session.add(txn)
    session.flush()
    return txn, True


def get_transaction(
    session: Session, txn_id: uuid.UUID, user_id: uuid.UUID
) -> Transaction | None:
    return session.execute(
        select(Transaction).where(
            Transaction.id == txn_id, Transaction.user_id == user_id
        )
    ).scalars().first()


def list_transactions(
    session: Session,
    user_id: uuid.UUID,
    *,
    account_id: uuid.UUID | None = None,
    category_id: uuid.UUID | None = None,
    uncategorized: bool = False,
) -> list[Transaction]:
    stmt = (
        select(Transaction)
        .where(Transaction.user_id == user_id)
        .order_by(Transaction.ts.desc())
    )
    if account_id is not None:
        stmt = stmt.where(Transaction.account_id == account_id)
    if category_id is not None:
        stmt = stmt.where(Transaction.category_id == category_id)
    if uncategorized:
        stmt = stmt.where(Transaction.category_id.is_(None))
    return list(session.execute(stmt).scalars().all())


def create_attachment(
    session: Session,
    *,
    user_id: uuid.UUID,
    transaction_id: uuid.UUID,
    filename: str,
    content_type: str,
    size: int,
    data: bytes,
) -> Attachment:
    attachment = Attachment(
        user_id=user_id,
        transaction_id=transaction_id,
        filename=filename,
        content_type=content_type,
        size=size,
        data=data,
    )
    session.add(attachment)
    session.flush()
    return attachment


def list_attachments(
    session: Session, transaction_id: uuid.UUID, user_id: uuid.UUID
) -> list[Attachment]:
    stmt = (
        select(Attachment)
        .where(Attachment.transaction_id == transaction_id, Attachment.user_id == user_id)
        .order_by(Attachment.created_at)
    )
    return list(session.execute(stmt).scalars().all())


def get_attachment(
    session: Session, attachment_id: uuid.UUID, user_id: uuid.UUID
) -> Attachment | None:
    return session.execute(
        select(Attachment).where(
            Attachment.id == attachment_id, Attachment.user_id == user_id
        )
    ).scalars().first()


def delete_attachment(
    session: Session, attachment_id: uuid.UUID, user_id: uuid.UUID
) -> bool:
    attachment = get_attachment(session, attachment_id, user_id)
    if attachment is None:
        return False
    session.delete(attachment)
    session.flush()
    return True


def delete_transaction(
    session: Session, txn_id: uuid.UUID, user_id: uuid.UUID
) -> bool:
    txn = get_transaction(session, txn_id, user_id)
    if txn is None:
        return False
    session.execute(delete(Attachment).where(Attachment.transaction_id == txn_id))
    session.delete(txn)
    session.flush()
    return True


def transactions_between(
    session: Session, user_id: uuid.UUID, start: datetime, end: datetime
) -> list[Transaction]:
    stmt = (
        select(Transaction)
        .where(
            Transaction.user_id == user_id,
            Transaction.ts >= start,
            Transaction.ts < end,
        )
        .order_by(Transaction.ts)
    )
    return list(session.execute(stmt).scalars().all())


# --- categories -----------------------------------------------------------


def create_category(
    session: Session,
    *,
    user_id: uuid.UUID,
    name: str,
    kind: CategoryKind,
    is_fixed: bool = False,
) -> Category:
    category = Category(user_id=user_id, name=name, kind=kind, is_fixed=is_fixed)
    session.add(category)
    session.flush()
    return category


def get_category(
    session: Session, category_id: uuid.UUID, user_id: uuid.UUID
) -> Category | None:
    return session.execute(
        select(Category).where(Category.id == category_id, Category.user_id == user_id)
    ).scalars().first()


def get_category_by_name(
    session: Session, user_id: uuid.UUID, name: str
) -> Category | None:
    return session.execute(
        select(Category).where(Category.user_id == user_id, Category.name == name)
    ).scalars().first()


def list_categories(session: Session, user_id: uuid.UUID) -> list[Category]:
    return list(
        session.execute(
            select(Category).where(Category.user_id == user_id).order_by(Category.name)
        ).scalars().all()
    )


def update_category(session: Session, category: Category, **fields) -> Category:
    for key, value in fields.items():
        if value is not None:
            setattr(category, key, value)
    session.flush()
    return category


def delete_category(
    session: Session, category_id: uuid.UUID, user_id: uuid.UUID
) -> bool:
    category = get_category(session, category_id, user_id)
    if category is None:
        return False
    session.execute(
        update(Transaction)
        .where(Transaction.category_id == category_id)
        .values(category_id=None)
    )
    session.execute(delete(Rule).where(Rule.category_id == category_id))
    session.execute(delete(Budget).where(Budget.category_id == category_id))
    session.delete(category)
    session.flush()
    return True


# --- rules ----------------------------------------------------------------


def create_rule(
    session: Session,
    *,
    user_id: uuid.UUID,
    match_pattern: str,
    category_id: uuid.UUID,
    priority: int = 100,
) -> Rule:
    rule = Rule(
        user_id=user_id,
        match_pattern=match_pattern,
        category_id=category_id,
        priority=priority,
    )
    session.add(rule)
    session.flush()
    return rule


def get_rule(session: Session, rule_id: uuid.UUID, user_id: uuid.UUID) -> Rule | None:
    return session.execute(
        select(Rule).where(Rule.id == rule_id, Rule.user_id == user_id)
    ).scalars().first()


def list_rules(session: Session, user_id: uuid.UUID) -> list[Rule]:
    stmt = (
        select(Rule)
        .where(Rule.user_id == user_id)
        .order_by(Rule.priority.desc(), Rule.match_pattern)
    )
    return list(session.execute(stmt).scalars().all())


def find_rule_by_pattern(
    session: Session, user_id: uuid.UUID, match_pattern: str, category_id: uuid.UUID
) -> Rule | None:
    return session.execute(
        select(Rule).where(
            Rule.user_id == user_id,
            Rule.match_pattern == match_pattern,
            Rule.category_id == category_id,
        )
    ).scalars().first()


def update_rule(session: Session, rule: Rule, **fields) -> Rule:
    for key, value in fields.items():
        if value is not None:
            setattr(rule, key, value)
    session.flush()
    return rule


def delete_rule(session: Session, rule_id: uuid.UUID, user_id: uuid.UUID) -> bool:
    rule = get_rule(session, rule_id, user_id)
    if rule is None:
        return False
    session.delete(rule)
    session.flush()
    return True


# --- recurring ------------------------------------------------------------


def create_recurring(
    session: Session,
    *,
    user_id: uuid.UUID,
    payee: str,
    amount_est: Decimal,
    cadence: str,
    next_due,
    account_id: uuid.UUID,
) -> Recurring:
    recurring = Recurring(
        user_id=user_id,
        payee=payee,
        amount_est=amount_est,
        cadence=cadence,
        next_due=next_due,
        account_id=account_id,
    )
    session.add(recurring)
    session.flush()
    return recurring


def list_recurring(session: Session, user_id: uuid.UUID) -> list[Recurring]:
    return list(
        session.execute(
            select(Recurring)
            .where(Recurring.user_id == user_id)
            .order_by(Recurring.next_due)
        ).scalars().all()
    )


def delete_all_recurring(session: Session, user_id: uuid.UUID) -> int:
    result = session.execute(delete(Recurring).where(Recurring.user_id == user_id))
    session.flush()
    return result.rowcount or 0


# --- reports --------------------------------------------------------------


def spending_by_category(session: Session, user_id: uuid.UUID) -> list[tuple]:
    stmt = (
        select(
            Transaction.category_id,
            func.coalesce(func.sum(Transaction.amount), 0),
            func.count(),
        )
        .where(Transaction.user_id == user_id)
        .group_by(Transaction.category_id)
    )
    return list(session.execute(stmt).all())


def category_spending_between(
    session: Session, user_id: uuid.UUID, start: datetime, end: datetime
) -> dict:
    stmt = (
        select(Transaction.category_id, func.coalesce(func.sum(Transaction.amount), 0))
        .where(
            Transaction.user_id == user_id,
            Transaction.ts >= start,
            Transaction.ts < end,
        )
        .group_by(Transaction.category_id)
    )
    return {row[0]: Decimal(str(row[1])) for row in session.execute(stmt).all()}


# --- cashflow items -------------------------------------------------------


def create_cashflow_item(
    session: Session,
    *,
    user_id: uuid.UUID,
    direction: CashflowDirection,
    name: str,
    amount: Decimal,
    cadence: Cadence,
    currency: str,
    category_id: uuid.UUID | None = None,
    account_id: uuid.UUID | None = None,
    next_due=None,
) -> CashflowItem:
    item = CashflowItem(
        user_id=user_id,
        direction=direction,
        name=name,
        amount=amount,
        cadence=cadence,
        currency=currency,
        category_id=category_id,
        account_id=account_id,
        next_due=next_due,
    )
    session.add(item)
    session.flush()
    return item


def get_cashflow_item(
    session: Session, item_id: uuid.UUID, user_id: uuid.UUID
) -> CashflowItem | None:
    return session.execute(
        select(CashflowItem).where(
            CashflowItem.id == item_id, CashflowItem.user_id == user_id
        )
    ).scalars().first()


def list_cashflow_items(
    session: Session,
    user_id: uuid.UUID,
    *,
    direction: CashflowDirection | None = None,
    active_only: bool = False,
) -> list[CashflowItem]:
    stmt = (
        select(CashflowItem)
        .where(CashflowItem.user_id == user_id)
        .order_by(CashflowItem.created_at)
    )
    if direction is not None:
        stmt = stmt.where(CashflowItem.direction == direction)
    if active_only:
        stmt = stmt.where(CashflowItem.active.is_(True))
    return list(session.execute(stmt).scalars().all())


def update_cashflow_item(session: Session, item: CashflowItem, **fields) -> CashflowItem:
    for key, value in fields.items():
        if value is not None:
            setattr(item, key, value)
    session.flush()
    return item


def delete_cashflow_item(
    session: Session, item_id: uuid.UUID, user_id: uuid.UUID
) -> bool:
    item = get_cashflow_item(session, item_id, user_id)
    if item is None:
        return False
    session.delete(item)
    session.flush()
    return True


# --- budgets --------------------------------------------------------------


def create_budget(
    session: Session, *, user_id: uuid.UUID, category_id: uuid.UUID, monthly_limit: Decimal
) -> Budget:
    budget = Budget(user_id=user_id, category_id=category_id, monthly_limit=monthly_limit)
    session.add(budget)
    session.flush()
    return budget


def get_budget(
    session: Session, budget_id: uuid.UUID, user_id: uuid.UUID
) -> Budget | None:
    return session.execute(
        select(Budget).where(Budget.id == budget_id, Budget.user_id == user_id)
    ).scalars().first()


def get_budget_by_category(
    session: Session, user_id: uuid.UUID, category_id: uuid.UUID
) -> Budget | None:
    return session.execute(
        select(Budget).where(
            Budget.user_id == user_id, Budget.category_id == category_id
        )
    ).scalars().first()


def list_budgets(session: Session, user_id: uuid.UUID) -> list[Budget]:
    return list(
        session.execute(
            select(Budget).where(Budget.user_id == user_id)
        ).scalars().all()
    )


def update_budget(session: Session, budget: Budget, **fields) -> Budget:
    for key, value in fields.items():
        if value is not None:
            setattr(budget, key, value)
    session.flush()
    return budget


def delete_budget(session: Session, budget_id: uuid.UUID, user_id: uuid.UUID) -> bool:
    budget = get_budget(session, budget_id, user_id)
    if budget is None:
        return False
    session.delete(budget)
    session.flush()
    return True


# --- debts (things to pay off) -------------------------------------------


def create_debt(
    session: Session, *, user_id: uuid.UUID, name: str, amount: Decimal, due_date=None
) -> Debt:
    debt = Debt(user_id=user_id, name=name, amount=amount, due_date=due_date)
    session.add(debt)
    session.flush()
    return debt


def get_debt(session: Session, debt_id: uuid.UUID, user_id: uuid.UUID) -> Debt | None:
    return session.execute(
        select(Debt).where(Debt.id == debt_id, Debt.user_id == user_id)
    ).scalars().first()


def list_debts(
    session: Session, user_id: uuid.UUID, *, unpaid_only: bool = False
) -> list[Debt]:
    stmt = (
        select(Debt)
        .where(Debt.user_id == user_id)
        .order_by(Debt.paid, Debt.due_date.is_(None), Debt.due_date, Debt.created_at)
    )
    if unpaid_only:
        stmt = stmt.where(Debt.paid.is_(False))
    return list(session.execute(stmt).scalars().all())


def update_debt(session: Session, debt: Debt, **fields) -> Debt:
    for key, value in fields.items():
        if value is not None:
            setattr(debt, key, value)
    session.flush()
    return debt


def delete_debt(session: Session, debt_id: uuid.UUID, user_id: uuid.UUID) -> bool:
    debt = get_debt(session, debt_id, user_id)
    if debt is None:
        return False
    session.delete(debt)
    session.flush()
    return True
