"""per-account 'exclude from runway' toggle on the emergency fund + allocation buckets

Revision ID: 0035
Revises: 0034
Create Date: 2026-06-23

The emergency fund defaults to earmarked (excluded from runway, like the tax reserve); %-buckets
default to not earmarked (their balance stays in the spendable pool unless the user opts in).
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0035"
down_revision: Union[str, None] = "0034"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "emergency_funds",
        sa.Column("earmarked", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.add_column(
        "allocations",
        sa.Column("earmarked", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("allocations", "earmarked")
    op.drop_column("emergency_funds", "earmarked")
