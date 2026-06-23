"""fill-priority for accounts that back multiple savings goals (emergency fund / tax reserve)

Revision ID: 0034
Revises: 0033
Create Date: 2026-06-23
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0034"
down_revision: Union[str, None] = "0033"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "emergency_funds",
        sa.Column("account_priority", sa.Integer(), nullable=False, server_default="100"),
    )
    op.add_column(
        "tax_reserves",
        sa.Column("account_priority", sa.Integer(), nullable=False, server_default="100"),
    )


def downgrade() -> None:
    op.drop_column("tax_reserves", "account_priority")
    op.drop_column("emergency_funds", "account_priority")
