"""SQLAlchemy models for the §5 data model.

The full schema sketch from the plan is materialized here (accounts, balances,
transactions, categories, rules, recurring, connections, net_worth_snapshots) even though
Phase 0 only exercises accounts / balances / net_worth_snapshots. Later phases fill in the
rest behind the same models.

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
    String,
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


class Account(Base):
    __tablename__ = "accounts"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    connector: Mapped[str] = mapped_column(String(50), nullable=False)
    type: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="EUR")
    institution: Mapped[str | None] = mapped_column(String(200), nullable=True)
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

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    kind: Mapped[CategoryKind] = mapped_column(
        Enum(CategoryKind, name="category_kind"), nullable=False
    )
    is_fixed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
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
    # Stable dedupe key for idempotent sync upserts (§4.2).
    hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)


class Rule(Base):
    __tablename__ = "rules"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    match_pattern: Mapped[str] = mapped_column(String(500), nullable=False)
    category_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("categories.id"), nullable=False
    )
    priority: Mapped[int] = mapped_column(Integer, default=100, nullable=False)


class Recurring(Base):
    __tablename__ = "recurring"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
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
    connector: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[ConnectionStatus] = mapped_column(
        Enum(ConnectionStatus, name="connection_status"),
        default=ConnectionStatus.pending,
        nullable=False,
    )
    consent_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # Encrypted at rest via Fernet (§8). No real token stored until Phase 1.
    access_token: Mapped[str | None] = mapped_column(EncryptedString, nullable=True)
    refresh_token: Mapped[str | None] = mapped_column(EncryptedString, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, nullable=False
    )


class NetWorthSnapshot(Base):
    __tablename__ = "net_worth_snapshots"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    ts: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, nullable=False
    )
    total: Mapped[Decimal] = mapped_column(Money, nullable=False)
    breakdown_json: Mapped[dict] = mapped_column(JSONType, nullable=False, default=dict)
