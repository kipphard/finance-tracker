"""tax profiles + per-year inputs (German freelance EÜR)

Revision ID: 0028
Revises: 0027
Create Date: 2026-06-22
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from backend.persistence.types import GUID, JSONType

revision: str = "0028"
down_revision: Union[str, None] = "0027"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "tax_profiles",
        sa.Column("id", GUID, primary_key=True),
        sa.Column("user_id", GUID, sa.ForeignKey("users.id", ondelete="CASCADE"),
                  nullable=False, unique=True),
        sa.Column("freelance_tag", sa.String(50), nullable=False, server_default="freelance"),
        sa.Column("business_type", sa.String(16), nullable=False, server_default="freiberufler"),
        sa.Column("mixed_use_rates", JSONType, nullable=False, server_default="{}"),
        sa.Column("km_rate", sa.Numeric(20, 4), nullable=False, server_default="0.30"),
        sa.Column("home_office_mode", sa.String(8), nullable=False, server_default="none"),
        sa.Column("room_use_pauschale", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("room_sqm", sa.Numeric(8, 2), nullable=True),
        sa.Column("home_total_sqm", sa.Numeric(8, 2), nullable=True),
        sa.Column("home_annual_cost", sa.Numeric(20, 4), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "tax_year_inputs",
        sa.Column("id", GUID, primary_key=True),
        sa.Column("user_id", GUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("other_taxable_income", sa.Numeric(20, 4), nullable=False, server_default="0"),
        sa.Column("home_office_days", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("business_km", sa.Numeric(20, 4), nullable=False, server_default="0"),
        sa.Column("notes", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("user_id", "year", name="uq_tax_year_inputs_user_year"),
    )
    op.create_index("ix_tax_year_inputs_user_id", "tax_year_inputs", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_tax_year_inputs_user_id", table_name="tax_year_inputs")
    op.drop_table("tax_year_inputs")
    op.drop_table("tax_profiles")
