"""freelance projects: projects table + project_id on time_entries and invoices

Revision ID: 0017
Revises: 0016
Create Date: 2026-06-21
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from backend.persistence.types import GUID

revision: str = "0017"
down_revision: Union[str, None] = "0016"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

MONEY = sa.Numeric(20, 4)


def upgrade() -> None:
    op.create_table(
        "projects",
        sa.Column("id", GUID, primary_key=True),
        sa.Column("user_id", GUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("client_id", GUID, sa.ForeignKey("clients.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("hourly_rate", MONEY, nullable=True),
        sa.Column("budget_hours", sa.Numeric(8, 2), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("archived", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_projects_user_id", "projects", ["user_id"])
    op.create_index("ix_projects_client", "projects", ["client_id"])

    op.add_column(
        "time_entries",
        sa.Column("project_id", GUID, sa.ForeignKey("projects.id", ondelete="SET NULL"), nullable=True),
    )
    op.create_index("ix_time_entries_project_id", "time_entries", ["project_id"])

    op.add_column(
        "invoices",
        sa.Column("project_id", GUID, sa.ForeignKey("projects.id", ondelete="SET NULL"), nullable=True),
    )
    op.create_index("ix_invoices_project_id", "invoices", ["project_id"])


def downgrade() -> None:
    op.drop_index("ix_invoices_project_id", "invoices")
    op.drop_column("invoices", "project_id")
    op.drop_index("ix_time_entries_project_id", "time_entries")
    op.drop_column("time_entries", "project_id")
    op.drop_index("ix_projects_client", "projects")
    op.drop_index("ix_projects_user_id", "projects")
    op.drop_table("projects")
