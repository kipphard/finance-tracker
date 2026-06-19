"""multi-user: users table + per-user scoping (Phase 6)

Adds a users table and a NOT NULL user_id FK to every user-owned table, and swaps the
previously-global uniqueness (category name, transaction hash, account external id) to be
per-user. Assumes the data tables are empty (true for this deployment).

Revision ID: 0005
Revises: 0004
Create Date: 2026-06-19
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from backend.persistence.types import GUID

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_SCOPED_TABLES = [
    "accounts",
    "transactions",
    "categories",
    "rules",
    "recurring",
    "connections",
    "net_worth_snapshots",
    "budgets",
    "cashflow_items",
]


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", GUID, primary_key=True),
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    for table in _SCOPED_TABLES:
        op.add_column(table, sa.Column("user_id", GUID, nullable=False))
        op.create_foreign_key(
            f"fk_{table}_user_id", table, "users", ["user_id"], ["id"], ondelete="CASCADE"
        )
        op.create_index(f"ix_{table}_user_id", table, ["user_id"])

    # Swap global uniqueness -> per-user.
    op.execute("ALTER TABLE categories DROP CONSTRAINT IF EXISTS categories_name_key")
    op.create_unique_constraint("uq_categories_user_name", "categories", ["user_id", "name"])

    op.execute("ALTER TABLE transactions DROP CONSTRAINT IF EXISTS transactions_hash_key")
    op.create_unique_constraint("uq_transactions_user_hash", "transactions", ["user_id", "hash"])

    op.execute("ALTER TABLE accounts DROP CONSTRAINT IF EXISTS uq_accounts_external_id")
    op.create_unique_constraint(
        "uq_accounts_user_external", "accounts", ["user_id", "external_id"]
    )


def downgrade() -> None:
    op.drop_constraint("uq_accounts_user_external", "accounts", type_="unique")
    op.create_unique_constraint("uq_accounts_external_id", "accounts", ["external_id"])
    op.drop_constraint("uq_transactions_user_hash", "transactions", type_="unique")
    op.drop_constraint("uq_categories_user_name", "categories", type_="unique")

    for table in _SCOPED_TABLES:
        op.drop_index(f"ix_{table}_user_id", table_name=table)
        op.drop_constraint(f"fk_{table}_user_id", table, type_="foreignkey")
        op.drop_column(table, "user_id")

    op.drop_table("users")
