"""accounting fields on transactions + account link on cashflow items

Revision ID: 0007
Revises: 0006
Create Date: 2026-06-19
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from backend.persistence.types import GUID

revision: str = "0007"
down_revision: Union[str, None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("transactions", sa.Column("counterparty", sa.String(255), nullable=True))
    op.add_column("transactions", sa.Column("invoice_number", sa.String(100), nullable=True))
    op.add_column("transactions", sa.Column("vat_rate", sa.Numeric(6, 3), nullable=True))
    op.add_column("cashflow_items", sa.Column("account_id", GUID, nullable=True))
    op.create_foreign_key(
        "fk_cashflow_items_account_id",
        "cashflow_items",
        "accounts",
        ["account_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_cashflow_items_account_id", "cashflow_items", type_="foreignkey")
    op.drop_column("cashflow_items", "account_id")
    op.drop_column("transactions", "vat_rate")
    op.drop_column("transactions", "invoice_number")
    op.drop_column("transactions", "counterparty")
