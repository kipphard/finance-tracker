"""trips: Fahrtenbuch (per-trip mileage log)

Revision ID: 0039
Revises: 0038
Create Date: 2026-06-25
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from backend.persistence.types import GUID

revision: str = "0039"
down_revision: Union[str, None] = "0038"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "trips",
        sa.Column("id", GUID, primary_key=True),
        sa.Column("user_id", GUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("from_place", sa.String(200), nullable=False, server_default=""),
        sa.Column("to_place", sa.String(200), nullable=False, server_default=""),
        sa.Column("km", sa.Numeric(10, 2), nullable=False),
        sa.Column("purpose", sa.String(300), nullable=False, server_default=""),
        sa.Column("client_id", GUID, sa.ForeignKey("clients.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_trips_user_id", "trips", ["user_id"])
    op.create_index("ix_trips_user_date", "trips", ["user_id", "date"])


def downgrade() -> None:
    op.drop_index("ix_trips_user_date", table_name="trips")
    op.drop_index("ix_trips_user_id", table_name="trips")
    op.drop_table("trips")
