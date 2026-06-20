"""link transactions in a recurring/backfilled series

Revision ID: 0015
Revises: 0014
Create Date: 2026-06-20
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from backend.persistence.types import GUID

revision: str = "0015"
down_revision: Union[str, None] = "0014"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("transactions", sa.Column("series_id", GUID, nullable=True))
    op.create_index("ix_transactions_series_id", "transactions", ["series_id"])


def downgrade() -> None:
    op.drop_index("ix_transactions_series_id", table_name="transactions")
    op.drop_column("transactions", "series_id")
