"""per-transaction business-deductible % override

Revision ID: 0030
Revises: 0029
Create Date: 2026-06-23
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0030"
down_revision: Union[str, None] = "0029"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "transactions",
        sa.Column("deductible_pct", sa.Numeric(6, 3), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("transactions", "deductible_pct")
