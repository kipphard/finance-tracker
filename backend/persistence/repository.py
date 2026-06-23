"""Query helpers, all scoped to a user (Phase 6 isolation).

Every read/write is filtered by `user_id` so one user can never see or touch another's
data. `balances` is reached only through user-owned accounts (the caller scopes the account
first), so it has no direct user_id.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import case, delete, func, select, update
from sqlalchemy.orm import Session

from backend.persistence.models import (
    Account,
    Allocation,
    Attachment,
    Balance,
    Budget,
    BusinessProfile,
    Cadence,
    CashflowDirection,
    CashflowItem,
    Category,
    CategoryKind,
    Client,
    Connection,
    ConnectionStatus,
    Debt,
    EmergencyFund,
    Invoice,
    InvoiceItem,
    NetWorthSnapshot,
    PlannedPurchase,
    Project,
    Recurring,
    RecurringInvoice,
    Rule,
    TaxProfile,
    TaxReserve,
    TaxYearInput,
    TimeEntry,
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
    expected_return: Decimal = Decimal(0),
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
        expected_return=expected_return,
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
    their transactions up to *now* (transaction-first). Future-dated transactions are planned,
    not yet realized, so they don't count toward the current balance until their date arrives."""
    if account.connection_id is not None:
        latest = latest_balance(session, account.id)
        return Decimal(latest.amount) if latest is not None else Decimal("0")
    total = session.execute(
        select(func.coalesce(func.sum(Transaction.amount), 0)).where(
            Transaction.account_id == account.id,
            Transaction.ts <= datetime.now(timezone.utc),
            Transaction.excluded.is_(False),
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


def normalize_tags(tags: list[str] | None) -> list[str]:
    """Trim, lowercase, drop blanks, de-duplicate (order-preserving)."""
    out: list[str] = []
    for t in tags or []:
        v = t.strip().lower()
        if v and v not in out:
            out.append(v)
    return out


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
    deductible_pct: Decimal | None = None,
    excluded: bool = False,
    tags: list[str] | None = None,
    is_transfer: bool = False,
    series_id: uuid.UUID | None = None,
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
        deductible_pct=deductible_pct,
        excluded=excluded,
        tags=normalize_tags(tags),
        is_transfer=is_transfer,
        series_id=series_id,
        hash=hash,
    )
    session.add(txn)
    session.flush()
    return txn, True


def list_transactions_in_series(
    session: Session, user_id: uuid.UUID, series_id: uuid.UUID
) -> list[Transaction]:
    return list(
        session.execute(
            select(Transaction).where(
                Transaction.user_id == user_id, Transaction.series_id == series_id
            )
        ).scalars().all()
    )


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
            Transaction.is_transfer.is_(False),  # internal moves aren't income/expense
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
        .where(Transaction.user_id == user_id, Transaction.is_transfer.is_(False))
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


# --- planned purchases (wishlist) ----------------------------------------


def create_planned_purchase(session: Session, *, user_id: uuid.UUID, **fields) -> PlannedPurchase:
    item = PlannedPurchase(user_id=user_id, **fields)
    session.add(item)
    session.flush()
    return item


def get_planned_purchase(session: Session, item_id: uuid.UUID, user_id: uuid.UUID) -> PlannedPurchase | None:
    return session.execute(
        select(PlannedPurchase).where(PlannedPurchase.id == item_id, PlannedPurchase.user_id == user_id)
    ).scalars().first()


def list_planned_purchases(session: Session, user_id: uuid.UUID) -> list[PlannedPurchase]:
    return list(session.execute(
        select(PlannedPurchase).where(PlannedPurchase.user_id == user_id)
        .order_by(PlannedPurchase.price)
    ).scalars().all())


def update_planned_purchase(session: Session, item: PlannedPurchase, **fields) -> PlannedPurchase:
    for key, value in fields.items():
        setattr(item, key, value)
    session.flush()
    return item


def delete_planned_purchase(session: Session, item_id: uuid.UUID, user_id: uuid.UUID) -> bool:
    item = get_planned_purchase(session, item_id, user_id)
    if item is None:
        return False
    session.delete(item)
    session.flush()
    return True


# --- allocations (distribute the monthly leftover) -----------------------


def create_allocation(
    session: Session, *, user_id: uuid.UUID, name: str, percent: Decimal
) -> Allocation:
    allocation = Allocation(user_id=user_id, name=name, percent=percent)
    session.add(allocation)
    session.flush()
    return allocation


def get_allocation(
    session: Session, allocation_id: uuid.UUID, user_id: uuid.UUID
) -> Allocation | None:
    return session.execute(
        select(Allocation).where(
            Allocation.id == allocation_id, Allocation.user_id == user_id
        )
    ).scalars().first()


def list_allocations(session: Session, user_id: uuid.UUID) -> list[Allocation]:
    return list(
        session.execute(
            select(Allocation)
            .where(Allocation.user_id == user_id)
            .order_by(Allocation.created_at)
        ).scalars().all()
    )


def update_allocation(session: Session, allocation: Allocation, **fields) -> Allocation:
    for key, value in fields.items():
        if value is not None:
            setattr(allocation, key, value)
    session.flush()
    return allocation


def delete_allocation(
    session: Session, allocation_id: uuid.UUID, user_id: uuid.UUID
) -> bool:
    allocation = get_allocation(session, allocation_id, user_id)
    if allocation is None:
        return False
    session.delete(allocation)
    session.flush()
    return True


# --- emergency fund -------------------------------------------------------


def get_emergency_fund(session: Session, user_id: uuid.UUID) -> EmergencyFund:
    """Return the user's emergency-fund row, creating a default (3× fixed costs) on first use."""
    fund = session.execute(
        select(EmergencyFund).where(EmergencyFund.user_id == user_id)
    ).scalars().first()
    if fund is None:
        fund = EmergencyFund(user_id=user_id)
        session.add(fund)
        session.flush()
    return fund


def update_emergency_fund(session: Session, fund: EmergencyFund, **fields) -> EmergencyFund:
    # Unlike other updaters this sets fields even when None, so a custom target can be cleared
    # (target_amount = None) to fall back to the N× multiplier.
    for key, value in fields.items():
        setattr(fund, key, value)
    session.flush()
    return fund


# --- tax reserve (Steuerrücklage) ----------------------------------------


def get_tax_reserve(session: Session, user_id: uuid.UUID) -> TaxReserve:
    """Return the user's tax-reserve row, creating an empty default on first use."""
    reserve = session.execute(
        select(TaxReserve).where(TaxReserve.user_id == user_id)
    ).scalars().first()
    if reserve is None:
        reserve = TaxReserve(user_id=user_id)
        session.add(reserve)
        session.flush()
    return reserve


def update_tax_reserve(session: Session, reserve: TaxReserve, **fields) -> TaxReserve:
    # Sets fields even when None so the reserve account can be unlinked (reserve_account_id=None)
    # to fall back to the notional current_amount.
    for key, value in fields.items():
        setattr(reserve, key, value)
    session.flush()
    return reserve


def earmarked_account_ids(session: Session, user_id: uuid.UUID) -> set[uuid.UUID]:
    """Account ids that are spoken-for by a savings goal (currently the tax reserve) and so
    should be excluded from the spendable / cash-runway liquid pool."""
    ids = session.execute(
        select(TaxReserve.reserve_account_id).where(
            TaxReserve.user_id == user_id, TaxReserve.reserve_account_id.is_not(None)
        )
    ).scalars().all()
    return {i for i in ids if i is not None}


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


# ===== Freelance: business profile, clients, time, invoices =============


def get_business_profile(session: Session, user_id: uuid.UUID) -> BusinessProfile:
    """Return the user's business profile, creating an empty default on first use.

    intro_text / vat_note are left blank — the PDF supplies a language-appropriate default
    (German §19 note for de, English for en); the user can override them in Settings.
    """
    profile = session.execute(
        select(BusinessProfile).where(BusinessProfile.user_id == user_id)
    ).scalars().first()
    if profile is None:
        profile = BusinessProfile(user_id=user_id, next_invoice_number=100001)
        session.add(profile)
        session.flush()
    return profile


def update_business_profile(session: Session, profile: BusinessProfile, **fields) -> BusinessProfile:
    for key, value in fields.items():
        if value is not None:
            setattr(profile, key, value)
    session.flush()
    return profile


# --- clients --------------------------------------------------------------


def create_client(session: Session, *, user_id: uuid.UUID, **fields) -> Client:
    client = Client(user_id=user_id, **fields)
    session.add(client)
    session.flush()
    return client


def get_client(session: Session, client_id: uuid.UUID, user_id: uuid.UUID) -> Client | None:
    return session.execute(
        select(Client).where(Client.id == client_id, Client.user_id == user_id)
    ).scalars().first()


def list_clients(session: Session, user_id: uuid.UUID) -> list[Client]:
    return list(
        session.execute(
            select(Client).where(Client.user_id == user_id).order_by(Client.name)
        ).scalars().all()
    )


def update_client(session: Session, client: Client, **fields) -> Client:
    for key, value in fields.items():
        setattr(client, key, value)
    session.flush()
    return client


def delete_client(session: Session, client_id: uuid.UUID, user_id: uuid.UUID) -> bool:
    client = get_client(session, client_id, user_id)
    if client is None:
        return False
    session.execute(delete(TimeEntry).where(TimeEntry.client_id == client_id))
    inv_ids = [i.id for i in list_invoices(session, user_id, client_id=client_id)]
    if inv_ids:
        session.execute(delete(InvoiceItem).where(InvoiceItem.invoice_id.in_(inv_ids)))
        session.execute(delete(Invoice).where(Invoice.id.in_(inv_ids)))
    session.execute(delete(Project).where(Project.client_id == client_id))
    session.delete(client)
    session.flush()
    return True


def client_minutes(session: Session, user_id: uuid.UUID, client_id: uuid.UUID) -> tuple[int, int]:
    """Return (total billable minutes, unbilled minutes) for a client."""
    total, unbilled = session.execute(
        select(
            func.coalesce(func.sum(TimeEntry.minutes), 0),
            func.coalesce(
                func.sum(case((TimeEntry.invoice_id.is_(None), TimeEntry.minutes), else_=0)), 0
            ),
        ).where(TimeEntry.user_id == user_id, TimeEntry.client_id == client_id)
    ).one()
    return int(total), int(unbilled)


# --- projects -------------------------------------------------------------


def create_project(session: Session, *, user_id: uuid.UUID, **fields) -> Project:
    project = Project(user_id=user_id, **fields)
    session.add(project)
    session.flush()
    return project


def get_project(session: Session, project_id: uuid.UUID, user_id: uuid.UUID) -> Project | None:
    return session.execute(
        select(Project).where(Project.id == project_id, Project.user_id == user_id)
    ).scalars().first()


def list_projects(
    session: Session, user_id: uuid.UUID, *, client_id: uuid.UUID | None = None
) -> list[Project]:
    stmt = select(Project).where(Project.user_id == user_id)
    if client_id is not None:
        stmt = stmt.where(Project.client_id == client_id)
    return list(session.execute(stmt.order_by(Project.name)).scalars().all())


def update_project(session: Session, project: Project, **fields) -> Project:
    for key, value in fields.items():
        setattr(project, key, value)
    session.flush()
    return project


def delete_project(session: Session, project_id: uuid.UUID, user_id: uuid.UUID) -> bool:
    project = get_project(session, project_id, user_id)
    if project is None:
        return False
    # detach the project from its time entries + invoices (they survive, just un-projected)
    session.execute(
        update(TimeEntry).where(TimeEntry.project_id == project_id).values(project_id=None)
    )
    session.execute(
        update(Invoice).where(Invoice.project_id == project_id).values(project_id=None)
    )
    session.delete(project)
    session.flush()
    return True


def project_minutes(session: Session, user_id: uuid.UUID, project_id: uuid.UUID) -> tuple[int, int]:
    """Return (total billable minutes, unbilled minutes) for a project."""
    total, unbilled = session.execute(
        select(
            func.coalesce(func.sum(TimeEntry.minutes), 0),
            func.coalesce(
                func.sum(case((TimeEntry.invoice_id.is_(None), TimeEntry.minutes), else_=0)), 0
            ),
        ).where(TimeEntry.user_id == user_id, TimeEntry.project_id == project_id)
    ).one()
    return int(total), int(unbilled)


# --- time entries ---------------------------------------------------------


def create_time_entry(session: Session, *, user_id: uuid.UUID, **fields) -> TimeEntry:
    entry = TimeEntry(user_id=user_id, **fields)
    session.add(entry)
    session.flush()
    return entry


def get_time_entry(session: Session, entry_id: uuid.UUID, user_id: uuid.UUID) -> TimeEntry | None:
    return session.execute(
        select(TimeEntry).where(TimeEntry.id == entry_id, TimeEntry.user_id == user_id)
    ).scalars().first()


def get_running_entry(session: Session, user_id: uuid.UUID) -> TimeEntry | None:
    return session.execute(
        select(TimeEntry).where(TimeEntry.user_id == user_id, TimeEntry.ended_at.is_(None))
        .order_by(TimeEntry.started_at.desc())
    ).scalars().first()


def list_time_entries(
    session: Session,
    user_id: uuid.UUID,
    *,
    client_id: uuid.UUID | None = None,
    project_id: uuid.UUID | None = None,
    unbilled: bool = False,
    start: datetime | None = None,
    end: datetime | None = None,
) -> list[TimeEntry]:
    stmt = select(TimeEntry).where(TimeEntry.user_id == user_id)
    if client_id is not None:
        stmt = stmt.where(TimeEntry.client_id == client_id)
    if project_id is not None:
        stmt = stmt.where(TimeEntry.project_id == project_id)
    if unbilled:
        stmt = stmt.where(TimeEntry.invoice_id.is_(None))
    if start is not None:
        stmt = stmt.where(TimeEntry.started_at >= start)
    if end is not None:
        stmt = stmt.where(TimeEntry.started_at < end)
    return list(session.execute(stmt.order_by(TimeEntry.started_at.desc())).scalars().all())


def update_time_entry(session: Session, entry: TimeEntry, **fields) -> TimeEntry:
    for key, value in fields.items():
        setattr(entry, key, value)
    session.flush()
    return entry


def delete_time_entry(session: Session, entry_id: uuid.UUID, user_id: uuid.UUID) -> bool:
    entry = get_time_entry(session, entry_id, user_id)
    if entry is None:
        return False
    session.delete(entry)
    session.flush()
    return True


# --- invoices -------------------------------------------------------------


def create_invoice(session: Session, *, user_id: uuid.UUID, **fields) -> Invoice:
    invoice = Invoice(user_id=user_id, **fields)
    session.add(invoice)
    session.flush()
    return invoice


def get_invoice(session: Session, invoice_id: uuid.UUID, user_id: uuid.UUID) -> Invoice | None:
    return session.execute(
        select(Invoice).where(Invoice.id == invoice_id, Invoice.user_id == user_id)
    ).scalars().first()


def list_invoices(
    session: Session, user_id: uuid.UUID, *, client_id: uuid.UUID | None = None
) -> list[Invoice]:
    stmt = select(Invoice).where(Invoice.user_id == user_id)
    if client_id is not None:
        stmt = stmt.where(Invoice.client_id == client_id)
    return list(session.execute(stmt.order_by(Invoice.created_at.desc())).scalars().all())


def update_invoice(session: Session, invoice: Invoice, **fields) -> Invoice:
    for key, value in fields.items():
        if value is not None:
            setattr(invoice, key, value)
    session.flush()
    return invoice


def delete_invoice(session: Session, invoice_id: uuid.UUID, user_id: uuid.UUID) -> bool:
    invoice = get_invoice(session, invoice_id, user_id)
    if invoice is None:
        return False
    # release its time entries back to unbilled, then delete (items cascade)
    for entry in list_time_entries(session, user_id):
        if entry.invoice_id == invoice.id:
            entry.invoice_id = None
    session.delete(invoice)
    session.flush()
    return True


# --- recurring (retainer) invoices ----------------------------------------


def create_recurring_invoice(session: Session, *, user_id: uuid.UUID, **fields) -> RecurringInvoice:
    rec = RecurringInvoice(user_id=user_id, **fields)
    session.add(rec)
    session.flush()
    return rec


def get_recurring_invoice(session: Session, rec_id: uuid.UUID, user_id: uuid.UUID) -> RecurringInvoice | None:
    return session.execute(
        select(RecurringInvoice).where(RecurringInvoice.id == rec_id, RecurringInvoice.user_id == user_id)
    ).scalars().first()


def list_recurring_invoices(
    session: Session, user_id: uuid.UUID, *, active_only: bool = False
) -> list[RecurringInvoice]:
    stmt = select(RecurringInvoice).where(RecurringInvoice.user_id == user_id)
    if active_only:
        stmt = stmt.where(RecurringInvoice.active.is_(True))
    return list(session.execute(stmt.order_by(RecurringInvoice.next_run)).scalars().all())


def update_recurring_invoice(session: Session, rec: RecurringInvoice, **fields) -> RecurringInvoice:
    for key, value in fields.items():
        setattr(rec, key, value)
    session.flush()
    return rec


def delete_recurring_invoice(session: Session, rec_id: uuid.UUID, user_id: uuid.UUID) -> bool:
    rec = get_recurring_invoice(session, rec_id, user_id)
    if rec is None:
        return False
    session.delete(rec)
    session.flush()
    return True


def invoice_paid_amount(session: Session, user_id: uuid.UUID, number: str) -> Decimal:
    """Signed sum of all transactions tagged with this invoice number (payments add,
    refunds subtract). Empty/blank invoice number → 0."""
    if not (number or "").strip():
        return Decimal(0)
    total = session.execute(
        select(func.coalesce(func.sum(Transaction.amount), 0)).where(
            Transaction.user_id == user_id, Transaction.invoice_number == number
        )
    ).scalar()
    return Decimal(total or 0)


def list_invoice_transactions(session: Session, user_id: uuid.UUID, number: str) -> list[Transaction]:
    """Transactions tagged with this invoice number (the payments against it), oldest first."""
    if not (number or "").strip():
        return []
    return list(
        session.execute(
            select(Transaction)
            .where(Transaction.user_id == user_id, Transaction.invoice_number == number)
            .order_by(Transaction.ts)
        ).scalars().all()
    )


def reconcile_invoice_payments(session: Session, user_id: uuid.UUID) -> int:
    """Auto-mark invoices 'paid' when matching transactions cover the full total. Never
    downgrades a paid invoice and never marks a partial/refunded one. Returns # changed."""
    changed = 0
    for inv in list_invoices(session, user_id):
        if inv.status == "paid" or inv.total <= 0:
            continue
        if invoice_paid_amount(session, user_id, inv.number) >= inv.total:
            inv.status = "paid"
            changed += 1
    if changed:
        session.flush()
    return changed


# ===== Taxes: EÜR ==========================================================


def transactions_by_tag(
    session: Session,
    user_id: uuid.UUID,
    tag: str,
    start: datetime | None = None,
    end: datetime | None = None,
    include_excluded: bool = True,
) -> list[Transaction]:
    """All transactions carrying `tag` (case-insensitive), optionally within [start, end).

    Internal transfers are always dropped. `excluded` (off-balance) records are kept by
    default — they're the bookkeeping rows that still count for taxes. Tag membership is
    filtered in Python so it works the same on JSONB (Postgres) and JSON (SQLite)."""
    stmt = select(Transaction).where(
        Transaction.user_id == user_id,
        Transaction.is_transfer.is_(False),
    )
    if start is not None:
        stmt = stmt.where(Transaction.ts >= start)
    if end is not None:
        stmt = stmt.where(Transaction.ts < end)
    stmt = stmt.order_by(Transaction.ts)
    want = (tag or "").strip().lower()
    out: list[Transaction] = []
    for txn in session.execute(stmt).scalars().all():
        if not include_excluded and txn.excluded:
            continue
        if want in [str(t).lower() for t in (txn.tags or [])]:
            out.append(txn)
    return out


def get_tax_profile(session: Session, user_id: uuid.UUID) -> TaxProfile:
    """Return the user's tax profile, creating a default row on first use."""
    profile = session.execute(
        select(TaxProfile).where(TaxProfile.user_id == user_id)
    ).scalars().first()
    if profile is None:
        profile = TaxProfile(user_id=user_id)
        session.add(profile)
        session.flush()
    return profile


def update_tax_profile(session: Session, profile: TaxProfile, **fields) -> TaxProfile:
    for key, value in fields.items():
        if value is not None:
            setattr(profile, key, value)
    session.flush()
    return profile


def get_tax_year_input(session: Session, user_id: uuid.UUID, year: int) -> TaxYearInput:
    """Return the per-year tax inputs for `year`, creating a default row on first use."""
    row = session.execute(
        select(TaxYearInput).where(
            TaxYearInput.user_id == user_id, TaxYearInput.year == year
        )
    ).scalars().first()
    if row is None:
        row = TaxYearInput(user_id=user_id, year=year)
        session.add(row)
        session.flush()
    return row


def update_tax_year_input(session: Session, row: TaxYearInput, **fields) -> TaxYearInput:
    for key, value in fields.items():
        if value is not None:
            setattr(row, key, value)
    session.flush()
    return row
