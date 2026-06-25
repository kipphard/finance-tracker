"""reconciliations: per-account balance-reconcile history

Revision ID: 0038
Revises: 0037
Create Date: 2026-06-25
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from backend.persistence.types import GUID

revision: str = "0038"
down_revision: Union[str, None] = "0037"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "reconciliations",
        sa.Column("id", GUID, primary_key=True),
        sa.Column("user_id", GUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("account_id", GUID, sa.ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("as_of", sa.Date(), nullable=False),
        sa.Column("asserted_balance", sa.Numeric(20, 4), nullable=False),
        sa.Column("computed_balance", sa.Numeric(20, 4), nullable=False),
        sa.Column("delta", sa.Numeric(20, 4), nullable=False),
        sa.Column(
            "transaction_id", GUID,
            sa.ForeignKey("transactions.id", ondelete="SET NULL"), nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_reconciliations_user_id", "reconciliations", ["user_id"])
    op.create_index("ix_reconciliations_account_id", "reconciliations", ["account_id"])
    op.create_index(
        "ix_reconciliations_user_account", "reconciliations", ["user_id", "account_id", "as_of"]
    )


def downgrade() -> None:
    op.drop_index("ix_reconciliations_user_account", table_name="reconciliations")
    op.drop_index("ix_reconciliations_account_id", table_name="reconciliations")
    op.drop_index("ix_reconciliations_user_id", table_name="reconciliations")
    op.drop_table("reconciliations")
