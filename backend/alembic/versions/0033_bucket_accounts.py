"""link accounts to allocation buckets + emergency fund (for the 'Apply this month' action)

Revision ID: 0033
Revises: 0032
Create Date: 2026-06-23
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from backend.persistence.types import GUID

revision: str = "0033"
down_revision: Union[str, None] = "0032"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "allocations",
        sa.Column("account_id", GUID, sa.ForeignKey("accounts.id", ondelete="SET NULL"), nullable=True),
    )
    op.add_column(
        "emergency_funds",
        sa.Column("account_id", GUID, sa.ForeignKey("accounts.id", ondelete="SET NULL"), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("emergency_funds", "account_id")
    op.drop_column("allocations", "account_id")
