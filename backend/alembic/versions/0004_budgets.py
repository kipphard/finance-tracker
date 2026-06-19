"""budgets (per-category monthly limits)

Revision ID: 0004
Revises: 0003
Create Date: 2026-06-19
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from backend.persistence.types import GUID

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "budgets",
        sa.Column("id", GUID, primary_key=True),
        sa.Column(
            "category_id",
            GUID,
            sa.ForeignKey("categories.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("monthly_limit", sa.Numeric(20, 4), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("budgets")
