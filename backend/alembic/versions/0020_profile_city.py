"""business profile: city (default invoice place)

Revision ID: 0020
Revises: 0019
Create Date: 2026-06-21
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0020"
down_revision: Union[str, None] = "0019"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("business_profiles",
                  sa.Column("city", sa.String(120), nullable=False, server_default=""))


def downgrade() -> None:
    op.drop_column("business_profiles", "city")
