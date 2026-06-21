"""business profile: postal_code (split sender address into street / PLZ / city)

Revision ID: 0021
Revises: 0020
Create Date: 2026-06-21
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0021"
down_revision: Union[str, None] = "0020"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("business_profiles",
                  sa.Column("postal_code", sa.String(16), nullable=False, server_default=""))


def downgrade() -> None:
    op.drop_column("business_profiles", "postal_code")
