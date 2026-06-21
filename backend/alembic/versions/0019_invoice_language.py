"""invoice language: invoices.language + business_profiles.default_language

Revision ID: 0019
Revises: 0018
Create Date: 2026-06-21
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0019"
down_revision: Union[str, None] = "0018"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("business_profiles",
                  sa.Column("default_language", sa.String(2), nullable=False, server_default="de"))
    op.add_column("invoices",
                  sa.Column("language", sa.String(2), nullable=False, server_default="de"))


def downgrade() -> None:
    op.drop_column("invoices", "language")
    op.drop_column("business_profiles", "default_language")
