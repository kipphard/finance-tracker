"""invoice payment reminders: reminder_level (Mahnstufe) + last_reminder_at

Revision ID: 0023
Revises: 0022
Create Date: 2026-06-21
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0023"
down_revision: Union[str, None] = "0022"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("invoices",
                  sa.Column("reminder_level", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("invoices",
                  sa.Column("last_reminder_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("invoices", "last_reminder_at")
    op.drop_column("invoices", "reminder_level")
