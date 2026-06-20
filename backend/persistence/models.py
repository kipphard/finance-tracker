"""SQLAlchemy models for the §5 data model + Phase 6 multi-user.

Every user-owned table carries a `user_id` FK so all queries can be scoped to the owner
(strict per-user isolation). `balances` is the exception — it is always reached through a
user-owned `account`. Uniqueness that used to be global (category name, transaction hash,
account external id) is now per-user.

Notes:
- UUID primary keys (Python-side uuid4 default).
- Money columns are exact Decimal (never float).
- Timestamps are timezone-aware and set in Python at flush for predictable values.
"""
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from enum import Enum as PyEnum

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.persistence.database import Base
from backend.persistence.encryption import EncryptedString
from backend.persistence.types import GUID, JSONType, Money


def _now() -> datetime:
    return datetime.now(timezone.utc)


class CategoryKind(str, PyEnum):
    income = "income"
    expense = "expense"


class ConnectionStatus(str, PyEnum):
    pending = "pending"
    active = "active"
    expired = "expired"
    error = "error"


class CashflowDirection(str, PyEnum):
    inflow = "inflow"
    outflow = "outflow"


class Cadence(str, PyEnum):
    one_off = "one_off"
    weekly = "weekly"
    biweekly = "biweekly"
    monthly = "monthly"
    quarterly = "quarterly"
    yearly = "yearly"


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, nullable=False
    )


def _user_fk() -> Mapped[uuid.UUID]:
    return mapped_column(
        GUID, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )


class Account(Base):
    __tablename__ = "accounts"
    __table_args__ = (UniqueConstraint("user_id", "external_id", name="uq_accounts_user_external"),)

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = _user_fk()
    connector: Mapped[str] = mapped_column(String(50), nullable=False)
    type: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="EUR")
    institution: Mapped[str | None] = mapped_column(String(200), nullable=True)
    connection_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID, ForeignKey("connections.id", ondelete="CASCADE"), nullable=True
    )
    external_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, nullable=False
    )

    balances: Mapped[list["Balance"]] = relationship(
        back_populates="account", cascade="all, delete-orphan"
    )


class Balance(Base):
    __tablename__ = "balances"
    __table_args__ = (Index("ix_balances_account_ts", "account_id", "ts"),)

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    account_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False
    )
    ts: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, nullable=False
    )
    amount: Mapped[Decimal] = mapped_column(Money, nullable=False)

    account: Mapped["Account"] = relationship(back_populates="balances")


class Category(Base):
    __tablename__ = "categories"
    __table_args__ = (UniqueConstraint("user_id", "name", name="uq_categories_user_name"),)

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = _user_fk()
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    kind: Mapped[CategoryKind] = mapped_column(
        Enum(CategoryKind, name="category_kind"), nullable=False
    )
    is_fixed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class Transaction(Base):
    __tablename__ = "transactions"
    __table_args__ = (UniqueConstraint("user_id", "hash", name="uq_transactions_user_hash"),)

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = _user_fk()
    account_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False
    )
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Money, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="EUR")
    raw_payee: Mapped[str | None] = mapped_column(String(500), nullable=True)
    description: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    category_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID, ForeignKey("categories.id"), nullable=True
    )
    is_recurring: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    hash: Mapped[str] = mapped_column(String(64), nullable=False)
    # Accounting/freelancer fields.
    counterparty: Mapped[str | None] = mapped_column(String(255), nullable=True)
    invoice_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    vat_rate: Mapped[Decimal | None] = mapped_column(Numeric(6, 3), nullable=True)


class Rule(Base):
    __tablename__ = "rules"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = _user_fk()
    match_pattern: Mapped[str] = mapped_column(String(500), nullable=False)
    category_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("categories.id"), nullable=False
    )
    priority: Mapped[int] = mapped_column(Integer, default=100, nullable=False)


class Recurring(Base):
    __tablename__ = "recurring"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = _user_fk()
    payee: Mapped[str] = mapped_column(String(500), nullable=False)
    amount_est: Mapped[Decimal] = mapped_column(Money, nullable=False)
    cadence: Mapped[str] = mapped_column(String(50), nullable=False)
    next_due: Mapped[date | None] = mapped_column(Date, nullable=True)
    account_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False
    )


class Connection(Base):
    __tablename__ = "connections"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = _user_fk()
    connector: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[ConnectionStatus] = mapped_column(
        Enum(ConnectionStatus, name="connection_status"),
        default=ConnectionStatus.pending,
        nullable=False,
    )
    consent_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    institution_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    requisition_id: Mapped[str | None] = mapped_column(
        String(255), nullable=True, unique=True
    )
    reference: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Encrypted at rest via Fernet (§8).
    access_token: Mapped[str | None] = mapped_column(EncryptedString, nullable=True)
    refresh_token: Mapped[str | None] = mapped_column(EncryptedString, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, nullable=False
    )


class NetWorthSnapshot(Base):
    __tablename__ = "net_worth_snapshots"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = _user_fk()
    ts: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, nullable=False
    )
    total: Mapped[Decimal] = mapped_column(Money, nullable=False)
    breakdown_json: Mapped[dict] = mapped_column(JSONType, nullable=False, default=dict)


class Budget(Base):
    """A monthly spending limit for a category (§6 budgets)."""

    __tablename__ = "budgets"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = _user_fk()
    category_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("categories.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    monthly_limit: Mapped[Decimal] = mapped_column(Money, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, nullable=False
    )


class Attachment(Base):
    """A file (PDF/image, e.g. an invoice) attached to a transaction. Bytes stored in the DB;
    `data` is deferred so listing metadata never loads the blob."""

    __tablename__ = "attachments"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = _user_fk()
    transaction_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("transactions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(100), nullable=False)
    size: Mapped[int] = mapped_column(Integer, nullable=False)
    data: Mapped[bytes] = mapped_column(LargeBinary, nullable=False, deferred=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, nullable=False
    )


class Debt(Base):
    """A one-off thing the user needs to pay off (e.g. a car repair), with optional due date."""

    __tablename__ = "debts"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = _user_fk()
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Money, nullable=False)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    paid: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, nullable=False
    )


class Allocation(Base):
    """A percentage bucket for distributing the monthly leftover (income − fixed costs),
    e.g. Savings 50%, Invest 20%, Buffer 30%."""

    __tablename__ = "allocations"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = _user_fk()
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    percent: Mapped[Decimal] = mapped_column(Numeric(7, 4), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, nullable=False
    )


class CashflowItem(Base):
    """A manually entered recurring (or one-off) inflow or outflow, e.g. salary or rent."""

    __tablename__ = "cashflow_items"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = _user_fk()
    direction: Mapped[CashflowDirection] = mapped_column(
        Enum(CashflowDirection, name="cashflow_direction"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Money, nullable=False)
    cadence: Mapped[Cadence] = mapped_column(
        Enum(Cadence, name="cashflow_cadence"),
        default=Cadence.monthly,
        nullable=False,
    )
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="EUR")
    category_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID, ForeignKey("categories.id"), nullable=True
    )
    # Optional target account so the item can be auto-posted as a transaction.
    account_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID, ForeignKey("accounts.id", ondelete="SET NULL"), nullable=True
    )
    next_due: Mapped[date | None] = mapped_column(Date, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, nullable=False
    )
