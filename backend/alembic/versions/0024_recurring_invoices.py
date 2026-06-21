"""recurring (retainer) invoices

Revision ID: 0024
Revises: 0023
Create Date: 2026-06-21
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from backend.persistence.types import GUID

revision: str = "0024"
down_revision: Union[str, None] = "0023"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

MONEY = sa.Numeric(20, 4)


def upgrade() -> None:
    op.create_table(
        "recurring_invoices",
        sa.Column("id", GUID, primary_key=True),
        sa.Column("user_id", GUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("client_id", GUID, sa.ForeignKey("clients.id", ondelete="CASCADE"), nullable=False),
        sa.Column("project_id", GUID, sa.ForeignKey("projects.id", ondelete="SET NULL"), nullable=True),
        sa.Column("cadence", sa.String(16), nullable=False, server_default="monthly"),
        sa.Column("mode", sa.String(8), nullable=False, server_default="flat"),
        sa.Column("amount", MONEY, nullable=False, server_default="0"),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("language", sa.String(2), nullable=False, server_default="de"),
        sa.Column("next_run", sa.Date(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_recurring_invoices_user_id", "recurring_invoices", ["user_id"])


def downgrade() -> None:
    op.drop_table("recurring_invoices")
