"""manual cashflow items (recurring inflows/outflows)

Revision ID: 0003
Revises: 0002
Create Date: 2026-06-19
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from backend.persistence.models import Cadence, CashflowDirection
from backend.persistence.types import GUID

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "cashflow_items",
        sa.Column("id", GUID, primary_key=True),
        sa.Column(
            "direction",
            sa.Enum(CashflowDirection, name="cashflow_direction"),
            nullable=False,
        ),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("amount", sa.Numeric(20, 4), nullable=False),
        sa.Column(
            "cadence", sa.Enum(Cadence, name="cashflow_cadence"), nullable=False
        ),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column(
            "category_id", GUID, sa.ForeignKey("categories.id"), nullable=True
        ),
        sa.Column("next_due", sa.Date, nullable=True),
        sa.Column("active", sa.Boolean, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("cashflow_items")
    sa.Enum(name="cashflow_direction").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="cashflow_cadence").drop(op.get_bind(), checkfirst=True)
