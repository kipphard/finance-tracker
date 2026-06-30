"""one-off allocation buckets (separate windfall splitter, independent of the monthly buckets)

Revision ID: 0040
Revises: 0039
Create Date: 2026-06-30
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from backend.persistence.types import GUID

revision: str = "0040"
down_revision: Union[str, None] = "0039"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "oneoff_allocations",
        sa.Column("id", GUID, primary_key=True),
        sa.Column(
            "user_id",
            GUID,
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("percent", sa.Numeric(7, 4), nullable=False),
        sa.Column(
            "account_id",
            GUID,
            sa.ForeignKey("accounts.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_oneoff_allocations_user_id", "oneoff_allocations", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_oneoff_allocations_user_id", table_name="oneoff_allocations")
    op.drop_table("oneoff_allocations")
