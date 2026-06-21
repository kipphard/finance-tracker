"""planned purchases (wishlist)

Revision ID: 0026
Revises: 0025
Create Date: 2026-06-21
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from backend.persistence.types import GUID

revision: str = "0026"
down_revision: Union[str, None] = "0025"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "planned_purchases",
        sa.Column("id", GUID, primary_key=True),
        sa.Column("user_id", GUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("price", sa.Numeric(20, 4), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_planned_purchases_user_id", "planned_purchases", ["user_id"])


def downgrade() -> None:
    op.drop_table("planned_purchases")
