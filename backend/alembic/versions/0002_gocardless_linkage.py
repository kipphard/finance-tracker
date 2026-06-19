"""gocardless linkage columns (Phase 1)

Adds the GoCardless requisition fields to `connections` and the provider linkage
(`connection_id`, `external_id`) to `accounts`.

Revision ID: 0002
Revises: 0001
Create Date: 2026-06-19
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from backend.persistence.types import GUID

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("connections", sa.Column("institution_id", sa.String(255), nullable=True))
    op.add_column("connections", sa.Column("requisition_id", sa.String(255), nullable=True))
    op.add_column("connections", sa.Column("reference", sa.String(255), nullable=True))
    op.create_unique_constraint(
        "uq_connections_requisition_id", "connections", ["requisition_id"]
    )

    op.add_column("accounts", sa.Column("connection_id", GUID, nullable=True))
    op.add_column("accounts", sa.Column("external_id", sa.String(255), nullable=True))
    op.create_unique_constraint("uq_accounts_external_id", "accounts", ["external_id"])
    op.create_foreign_key(
        "fk_accounts_connection_id",
        "accounts",
        "connections",
        ["connection_id"],
        ["id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    op.drop_constraint("fk_accounts_connection_id", "accounts", type_="foreignkey")
    op.drop_constraint("uq_accounts_external_id", "accounts", type_="unique")
    op.drop_column("accounts", "external_id")
    op.drop_column("accounts", "connection_id")
    op.drop_constraint("uq_connections_requisition_id", "connections", type_="unique")
    op.drop_column("connections", "reference")
    op.drop_column("connections", "requisition_id")
    op.drop_column("connections", "institution_id")
