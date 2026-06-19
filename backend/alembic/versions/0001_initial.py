"""initial schema (§5 data model) — Phase 0

Explicit, frozen baseline: creates the Phase 0 tables only. Later phases add columns/tables
in their own revisions (0002 GoCardless linkage, 0003 cashflow). Do NOT use
metadata.create_all here — the metadata is not frozen and would drift as models evolve.

Revision ID: 0001
Revises:
Create Date: 2026-06-19
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from backend.persistence.models import CategoryKind, ConnectionStatus
from backend.persistence.types import GUID, JSONType, Money

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "accounts",
        sa.Column("id", GUID, primary_key=True),
        sa.Column("connector", sa.String(50), nullable=False),
        sa.Column("type", sa.String(50), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("institution", sa.String(200), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "categories",
        sa.Column("id", GUID, primary_key=True),
        sa.Column("name", sa.String(100), nullable=False, unique=True),
        sa.Column("kind", sa.Enum(CategoryKind, name="category_kind"), nullable=False),
        sa.Column("is_fixed", sa.Boolean, nullable=False),
    )
    op.create_table(
        "connections",
        sa.Column("id", GUID, primary_key=True),
        sa.Column("connector", sa.String(50), nullable=False),
        sa.Column(
            "status",
            sa.Enum(ConnectionStatus, name="connection_status"),
            nullable=False,
        ),
        sa.Column("consent_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("access_token", sa.Text, nullable=True),
        sa.Column("refresh_token", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "balances",
        sa.Column("id", GUID, primary_key=True),
        sa.Column(
            "account_id",
            GUID,
            sa.ForeignKey("accounts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("ts", sa.DateTime(timezone=True), nullable=False),
        sa.Column("amount", Money, nullable=False),
    )
    op.create_index("ix_balances_account_ts", "balances", ["account_id", "ts"])
    op.create_table(
        "transactions",
        sa.Column("id", GUID, primary_key=True),
        sa.Column(
            "account_id",
            GUID,
            sa.ForeignKey("accounts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("ts", sa.DateTime(timezone=True), nullable=False),
        sa.Column("amount", Money, nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("raw_payee", sa.String(500), nullable=True),
        sa.Column("description", sa.String(1000), nullable=True),
        sa.Column(
            "category_id", GUID, sa.ForeignKey("categories.id"), nullable=True
        ),
        sa.Column("is_recurring", sa.Boolean, nullable=False),
        sa.Column("hash", sa.String(64), nullable=False, unique=True),
    )
    op.create_table(
        "rules",
        sa.Column("id", GUID, primary_key=True),
        sa.Column("match_pattern", sa.String(500), nullable=False),
        sa.Column(
            "category_id", GUID, sa.ForeignKey("categories.id"), nullable=False
        ),
        sa.Column("priority", sa.Integer, nullable=False),
    )
    op.create_table(
        "recurring",
        sa.Column("id", GUID, primary_key=True),
        sa.Column("payee", sa.String(500), nullable=False),
        sa.Column("amount_est", Money, nullable=False),
        sa.Column("cadence", sa.String(50), nullable=False),
        sa.Column("next_due", sa.Date, nullable=True),
        sa.Column(
            "account_id",
            GUID,
            sa.ForeignKey("accounts.id", ondelete="CASCADE"),
            nullable=False,
        ),
    )
    op.create_table(
        "net_worth_snapshots",
        sa.Column("id", GUID, primary_key=True),
        sa.Column("ts", sa.DateTime(timezone=True), nullable=False),
        sa.Column("total", Money, nullable=False),
        sa.Column("breakdown_json", JSONType, nullable=False),
    )


def downgrade() -> None:
    op.drop_table("net_worth_snapshots")
    op.drop_table("recurring")
    op.drop_table("rules")
    op.drop_table("transactions")
    op.drop_index("ix_balances_account_ts", table_name="balances")
    op.drop_table("balances")
    op.drop_table("connections")
    op.drop_table("categories")
    op.drop_table("accounts")
    sa.Enum(name="connection_status").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="category_kind").drop(op.get_bind(), checkfirst=True)
