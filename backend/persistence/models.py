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
    Text,
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
    # Expected annual return/growth as a percent (e.g. 7.0). Feeds the net-worth forecast; 0 = flat.
    expected_return: Mapped[Decimal] = mapped_column(
        Numeric(6, 3), default=0, nullable=False
    )
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
    # Business-deductible share (0–100%) for this single expense; overrides the category's
    # mixed-use rate in the EÜR. Null = fall back to the freelance-tag / category-rate handling.
    deductible_pct: Mapped[Decimal | None] = mapped_column(Numeric(6, 3), nullable=True)
    # Off-balance bookkeeping record (e.g. past freelancing entries for taxes): kept for the
    # transaction list, reports and CSV exports, but excluded from account balances, net worth
    # and the forecast.
    excluded: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # Free-text tags (lowercased), orthogonal to the single category — e.g. ["software"].
    tags: Mapped[list] = mapped_column(JSONType, default=list, nullable=False)
    # First-class business/private split (replaces the old freelance tag): True = the transaction
    # counts as business income/expense in the EÜR. Private (False) is the default.
    is_business: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # Both legs of an account-to-account transfer are flagged so they drop out of the
    # income/expense, cashflow and category-breakdown reports (internal moves, not spending).
    is_transfer: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # Links transactions that belong to one recurring/backfilled series, so they can be
    # edited together. For materialized recurring it's the cashflow item id; for a backfill it's
    # a fresh id shared by the batch.
    series_id: Mapped[uuid.UUID | None] = mapped_column(GUID, nullable=True, index=True)


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


class PlannedPurchase(Base):
    """A wishlist item (name + price); the app projects when it becomes affordable."""

    __tablename__ = "planned_purchases"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = _user_fk()
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    price: Mapped[Decimal] = mapped_column(Money, nullable=False)
    # How much to set aside per month for this item (0 = not actively saving yet).
    monthly_save: Mapped[Decimal] = mapped_column(Money, nullable=False, default=Decimal(0))
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
    # Optional destination account for the "Apply this month" action (transfer the bucket's share
    # into it). Null = the bucket is informational only.
    account_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID, ForeignKey("accounts.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, nullable=False
    )


class EmergencyFund(Base):
    """Per-user emergency-fund goal: a target that is N× monthly fixed costs (or a custom
    amount), plus how much has been set aside so far. One row per user."""

    __tablename__ = "emergency_funds"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    target_months: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    target_amount: Mapped[Decimal | None] = mapped_column(Money, nullable=True)  # custom override
    current_amount: Mapped[Decimal] = mapped_column(Money, default=0, nullable=False)
    # Optional account holding the fund: when set, "saved so far" is its live balance and the
    # "Apply this month" action transfers the contribution into it.
    account_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID, ForeignKey("accounts.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, nullable=False
    )


class TaxReserve(Base):
    """Per-user "Steuerrücklage": how much income tax to keep aside for the freelance profit.
    The amount *owed* is computed live from the §32a EÜR estimate; what's *set aside* is either
    the balance of a designated reserve account (``reserve_account_id``) or a manually-entered
    notional amount (``current_amount``) when no account is linked. One row per user.

    A linked reserve account is treated as *earmarked* — excluded from the cash-runway liquid
    pool — so the money owed to the Finanzamt isn't counted as spendable."""

    __tablename__ = "tax_reserves"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    # Account whose balance counts as "set aside"; null = track notionally via current_amount.
    reserve_account_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID, ForeignKey("accounts.id", ondelete="SET NULL"), nullable=True
    )
    current_amount: Mapped[Decimal] = mapped_column(Money, default=0, nullable=False)
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


# ===== Freelance: time tracking + invoicing ==============================


class BusinessProfile(Base):
    """The freelancer's own details used on invoices (sender, bank, tax). One row per user."""

    __tablename__ = "business_profiles"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    name: Mapped[str] = mapped_column(String(200), default="", nullable=False)
    company_name: Mapped[str] = mapped_column(String(200), default="", nullable=False)
    phone: Mapped[str] = mapped_column(String(64), default="", nullable=False)
    email: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    address: Mapped[str] = mapped_column(Text, default="", nullable=False)  # street + number
    postal_code: Mapped[str] = mapped_column(String(16), default="", nullable=False)  # Postleitzahl
    city: Mapped[str] = mapped_column(String(120), default="", nullable=False)  # also invoice "place"
    iban: Mapped[str] = mapped_column(String(64), default="", nullable=False)
    bic: Mapped[str] = mapped_column(String(32), default="", nullable=False)
    tax_number: Mapped[str] = mapped_column(String(64), default="", nullable=False)
    # Kleinunternehmer per §19 UStG → no VAT on invoices. When False, invoices apply vat_rate.
    is_kleinunternehmer: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    vat_note: Mapped[str] = mapped_column(Text, default="", nullable=False)
    intro_text: Mapped[str] = mapped_column(Text, default="", nullable=False)
    payment_terms_days: Mapped[int] = mapped_column(Integer, default=14, nullable=False)
    payment_info: Mapped[str] = mapped_column(Text, default="", nullable=False)  # extra pay instructions/link
    default_language: Mapped[str] = mapped_column(String(2), default="de", nullable=False)
    # notification digest preferences
    digest_cadence: Mapped[str] = mapped_column(String(8), default="off", nullable=False)  # off|weekly|monthly
    digest_invoices: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    digest_time: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    digest_finance: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    default_hourly_rate: Mapped[Decimal] = mapped_column(Money, default=0, nullable=False)
    next_invoice_number: Mapped[int] = mapped_column(Integer, default=100001, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, nullable=False
    )


class Client(Base):
    """A freelance customer that time entries and invoices belong to."""

    __tablename__ = "clients"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = _user_fk()
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    address: Mapped[str] = mapped_column(Text, default="", nullable=False)  # invoice recipient block
    hourly_rate: Mapped[Decimal] = mapped_column(Money, default=0, nullable=False)
    budget_hours: Mapped[Decimal | None] = mapped_column(Numeric(8, 2), nullable=True)  # Kontingent
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    archived: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, nullable=False
    )


class Project(Base):
    """A project under a client. Time entries and invoices can optionally belong to one.
    hourly_rate / budget_hours are optional overrides — NULL inherits the client's."""

    __tablename__ = "projects"
    __table_args__ = (Index("ix_projects_client", "client_id"),)

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = _user_fk()
    client_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("clients.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    hourly_rate: Mapped[Decimal | None] = mapped_column(Money, nullable=True)  # override; NULL = inherit client
    budget_hours: Mapped[Decimal | None] = mapped_column(Numeric(8, 2), nullable=True)  # Kontingent
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    archived: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, nullable=False
    )


class TimeEntry(Base):
    """A block of billable work for a client. A running timer has ended_at = NULL."""

    __tablename__ = "time_entries"
    __table_args__ = (Index("ix_time_entries_client", "client_id"),)

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = _user_fk()
    client_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("clients.id", ondelete="CASCADE"), nullable=False
    )
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID, ForeignKey("projects.id", ondelete="SET NULL"), nullable=True, index=True
    )
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    minutes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)  # billable duration
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    invoice_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID, ForeignKey("invoices.id", ondelete="SET NULL"), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, nullable=False
    )


class Invoice(Base):
    """A generated invoice for a client, built from its (unbilled) time entries."""

    __tablename__ = "invoices"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = _user_fk()
    client_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("clients.id", ondelete="CASCADE"), nullable=False
    )
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID, ForeignKey("projects.id", ondelete="SET NULL"), nullable=True, index=True
    )
    number: Mapped[str] = mapped_column(String(40), nullable=False)
    issue_date: Mapped[date] = mapped_column(Date, default=lambda: _now().date(), nullable=False)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    place: Mapped[str] = mapped_column(String(120), default="", nullable=False)
    language: Mapped[str] = mapped_column(String(2), default="de", nullable=False)
    intro_text: Mapped[str] = mapped_column(Text, default="", nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="draft", nullable=False)
    vat_rate: Mapped[Decimal] = mapped_column(Numeric(6, 3), default=0, nullable=False)
    total: Mapped[Decimal] = mapped_column(Money, default=0, nullable=False)
    reminder_level: Mapped[int] = mapped_column(Integer, default=0, nullable=False)  # Mahnstufe
    last_reminder_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, nullable=False
    )

    items: Mapped[list["InvoiceItem"]] = relationship(
        back_populates="invoice", cascade="all, delete-orphan", order_by="InvoiceItem.position"
    )


class InvoiceItem(Base):
    """A line on an invoice: a service description with hours, rate and amount."""

    __tablename__ = "invoice_items"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    invoice_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False, index=True
    )
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    hours: Mapped[Decimal] = mapped_column(Numeric(8, 2), default=0, nullable=False)
    rate: Mapped[Decimal] = mapped_column(Money, default=0, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Money, default=0, nullable=False)
    position: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    invoice: Mapped["Invoice"] = relationship(back_populates="items")


class RecurringInvoice(Base):
    """A retainer template that auto-drafts an invoice each period (flat fee or tracked time)."""

    __tablename__ = "recurring_invoices"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = _user_fk()
    client_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("clients.id", ondelete="CASCADE"), nullable=False
    )
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID, ForeignKey("projects.id", ondelete="SET NULL"), nullable=True
    )
    cadence: Mapped[str] = mapped_column(String(16), default="monthly", nullable=False)
    mode: Mapped[str] = mapped_column(String(8), default="flat", nullable=False)  # flat | time
    amount: Mapped[Decimal] = mapped_column(Money, default=0, nullable=False)     # flat fee (net)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)     # flat line text
    language: Mapped[str] = mapped_column(String(2), default="de", nullable=False)
    next_run: Mapped[date] = mapped_column(Date, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, nullable=False
    )


# ===== Taxes: German freelance EÜR (Einnahmenüberschussrechnung) ==========


class TaxProfile(Base):
    """Stable per-user tax settings for the EÜR. One row per user.

    Year-specific numbers (other income, days worked from home, business km) live on
    TaxYearInput instead — this row holds the setup that rarely changes."""

    __tablename__ = "tax_profiles"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    # freiberufler (Anlage S) | gewerbe (Anlage G) — drives the ELSTER prompt.
    business_type: Mapped[str] = mapped_column(String(16), default="freiberufler", nullable=False)
    # Mixed-use expense categories → business-use percent, e.g. {"<category_id>": 50}.
    mixed_use_rates: Mapped[dict] = mapped_column(JSONType, default=dict, nullable=False)
    # Kilometre rate for business travel (Reisekosten), default €0.30/km.
    km_rate: Mapped[Decimal] = mapped_column(Money, default=Decimal("0.30"), nullable=False)
    # none | flat (Homeoffice-Pauschale) | room (häusliches Arbeitszimmer)
    home_office_mode: Mapped[str] = mapped_column(String(8), default="none", nullable=False)
    # For room mode: use the €1.260 Jahrespauschale instead of actual area-based cost.
    room_use_pauschale: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    room_sqm: Mapped[Decimal | None] = mapped_column(Numeric(8, 2), nullable=True)
    home_total_sqm: Mapped[Decimal | None] = mapped_column(Numeric(8, 2), nullable=True)
    home_annual_cost: Mapped[Decimal] = mapped_column(Money, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, nullable=False
    )


class TaxYearInput(Base):
    """Year-specific tax inputs the user enters for a given calendar/tax year. One per (user, year)."""

    __tablename__ = "tax_year_inputs"
    __table_args__ = (UniqueConstraint("user_id", "year", name="uq_tax_year_inputs_user_year"),)

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = _user_fk()
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    # Other taxable income (e.g. salary / Bruttoarbeitslohn) the §32a tax estimate stacks on top of.
    other_taxable_income: Mapped[Decimal] = mapped_column(Money, default=0, nullable=False)
    # Income tax already paid toward this year, for the Erstattung/Nachzahlung estimate: the wage
    # tax the employer withheld (Lohnsteuerbescheinigung) + any Einkommensteuer-Vorauszahlungen.
    withheld_lohnsteuer: Mapped[Decimal] = mapped_column(Money, default=0, nullable=False)
    income_tax_prepaid: Mapped[Decimal] = mapped_column(Money, default=0, nullable=False)
    # Days worked from home that year (for the Homeoffice-Pauschale, €6/day, capped €1.260).
    home_office_days: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # Kilometres driven for the business that year (× km_rate → Reisekosten).
    business_km: Mapped[Decimal] = mapped_column(Money, default=0, nullable=False)
    notes: Mapped[str] = mapped_column(Text, default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, nullable=False
    )
