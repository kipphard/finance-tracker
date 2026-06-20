"""expected annual return on accounts (for the net-worth forecast)

Revision ID: 0010
Revises: 0009
Create Date: 2026-06-20
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0010"
down_revision: Union[str, None] = "0009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "accounts",
        sa.Column("expected_return", sa.Numeric(6, 3), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("accounts", "expected_return")
