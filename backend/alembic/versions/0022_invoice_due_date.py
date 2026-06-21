"""invoice due date + business profile payment terms / payment info

Revision ID: 0022
Revises: 0021
Create Date: 2026-06-21
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0022"
down_revision: Union[str, None] = "0021"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("invoices", sa.Column("due_date", sa.Date(), nullable=True))
    op.add_column("business_profiles",
                  sa.Column("payment_terms_days", sa.Integer(), nullable=False, server_default="14"))
    op.add_column("business_profiles",
                  sa.Column("payment_info", sa.Text(), nullable=False, server_default=""))


def downgrade() -> None:
    op.drop_column("business_profiles", "payment_info")
    op.drop_column("business_profiles", "payment_terms_days")
    op.drop_column("invoices", "due_date")
