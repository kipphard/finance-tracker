"""year inputs for the Erstattung/Nachzahlung estimate: withheld Lohnsteuer + prepayments

Revision ID: 0032
Revises: 0031
Create Date: 2026-06-23
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0032"
down_revision: Union[str, None] = "0031"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "tax_year_inputs",
        sa.Column("withheld_lohnsteuer", sa.Numeric(20, 4), nullable=False, server_default="0"),
    )
    op.add_column(
        "tax_year_inputs",
        sa.Column("income_tax_prepaid", sa.Numeric(20, 4), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("tax_year_inputs", "income_tax_prepaid")
    op.drop_column("tax_year_inputs", "withheld_lohnsteuer")
