"""planned purchase monthly_save (Planned purchases fund)

Revision ID: 0027
Revises: 0026
Create Date: 2026-06-21
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0027"
down_revision: Union[str, None] = "0026"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "planned_purchases",
        sa.Column("monthly_save", sa.Numeric(20, 4), nullable=False, server_default="0"),
    )
    # drop the server_default now that existing rows are backfilled (app supplies the value)
    op.alter_column("planned_purchases", "monthly_save", server_default=None)


def downgrade() -> None:
    op.drop_column("planned_purchases", "monthly_save")
