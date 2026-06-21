"""business profile: notification digest preferences

Revision ID: 0025
Revises: 0024
Create Date: 2026-06-21
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0025"
down_revision: Union[str, None] = "0024"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("business_profiles",
                  sa.Column("digest_cadence", sa.String(8), nullable=False, server_default="off"))
    op.add_column("business_profiles",
                  sa.Column("digest_invoices", sa.Boolean(), nullable=False, server_default=sa.true()))
    op.add_column("business_profiles",
                  sa.Column("digest_time", sa.Boolean(), nullable=False, server_default=sa.true()))
    op.add_column("business_profiles",
                  sa.Column("digest_finance", sa.Boolean(), nullable=False, server_default=sa.true()))


def downgrade() -> None:
    op.drop_column("business_profiles", "digest_finance")
    op.drop_column("business_profiles", "digest_time")
    op.drop_column("business_profiles", "digest_invoices")
    op.drop_column("business_profiles", "digest_cadence")
