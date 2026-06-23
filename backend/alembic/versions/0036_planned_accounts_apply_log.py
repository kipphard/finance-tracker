"""planned-purchase account link + earmark; allocation 'apply this month' log

Revision ID: 0036
Revises: 0035
Create Date: 2026-06-23
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from backend.persistence.types import GUID

revision: str = "0036"
down_revision: Union[str, None] = "0035"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "planned_purchases",
        sa.Column("account_id", GUID, sa.ForeignKey("accounts.id", ondelete="SET NULL"), nullable=True),
    )
    op.add_column(
        "planned_purchases",
        sa.Column("earmarked", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_table(
        "allocation_applies",
        sa.Column("id", GUID, primary_key=True),
        sa.Column("user_id", GUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("applied_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("total_moved", sa.Numeric(20, 4), nullable=False, server_default="0"),
    )
    op.create_index("ix_allocation_applies_user", "allocation_applies", ["user_id", "applied_at"])


def downgrade() -> None:
    op.drop_index("ix_allocation_applies_user", table_name="allocation_applies")
    op.drop_table("allocation_applies")
    op.drop_column("planned_purchases", "earmarked")
    op.drop_column("planned_purchases", "account_id")
