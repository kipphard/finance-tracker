"""freelance: business profile, clients, time entries, invoices

Revision ID: 0016
Revises: 0015
Create Date: 2026-06-21
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from backend.persistence.types import GUID

revision: str = "0016"
down_revision: Union[str, None] = "0015"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

MONEY = sa.Numeric(20, 4)


def upgrade() -> None:
    op.create_table(
        "business_profiles",
        sa.Column("id", GUID, primary_key=True),
        sa.Column("user_id", GUID, sa.ForeignKey("users.id", ondelete="CASCADE"),
                  nullable=False, unique=True),
        sa.Column("name", sa.String(200), nullable=False, server_default=""),
        sa.Column("address", sa.Text(), nullable=False, server_default=""),
        sa.Column("iban", sa.String(64), nullable=False, server_default=""),
        sa.Column("bic", sa.String(32), nullable=False, server_default=""),
        sa.Column("tax_number", sa.String(64), nullable=False, server_default=""),
        sa.Column("vat_note", sa.Text(), nullable=False, server_default=""),
        sa.Column("intro_text", sa.Text(), nullable=False, server_default=""),
        sa.Column("default_hourly_rate", MONEY, nullable=False, server_default="0"),
        sa.Column("next_invoice_number", sa.Integer(), nullable=False, server_default="100001"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "clients",
        sa.Column("id", GUID, primary_key=True),
        sa.Column("user_id", GUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("address", sa.Text(), nullable=False, server_default=""),
        sa.Column("hourly_rate", MONEY, nullable=False, server_default="0"),
        sa.Column("budget_hours", sa.Numeric(8, 2), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("archived", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_clients_user_id", "clients", ["user_id"])

    op.create_table(
        "invoices",
        sa.Column("id", GUID, primary_key=True),
        sa.Column("user_id", GUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("client_id", GUID, sa.ForeignKey("clients.id", ondelete="CASCADE"), nullable=False),
        sa.Column("number", sa.String(40), nullable=False),
        sa.Column("issue_date", sa.Date(), nullable=False),
        sa.Column("place", sa.String(120), nullable=False, server_default=""),
        sa.Column("intro_text", sa.Text(), nullable=False, server_default=""),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("vat_rate", sa.Numeric(6, 3), nullable=False, server_default="0"),
        sa.Column("total", MONEY, nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_invoices_user_id", "invoices", ["user_id"])

    op.create_table(
        "invoice_items",
        sa.Column("id", GUID, primary_key=True),
        sa.Column("invoice_id", GUID, sa.ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("hours", sa.Numeric(8, 2), nullable=False, server_default="0"),
        sa.Column("rate", MONEY, nullable=False, server_default="0"),
        sa.Column("amount", MONEY, nullable=False, server_default="0"),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_index("ix_invoice_items_invoice_id", "invoice_items", ["invoice_id"])

    op.create_table(
        "time_entries",
        sa.Column("id", GUID, primary_key=True),
        sa.Column("user_id", GUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("client_id", GUID, sa.ForeignKey("clients.id", ondelete="CASCADE"), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("minutes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("invoice_id", GUID, sa.ForeignKey("invoices.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_time_entries_user_id", "time_entries", ["user_id"])
    op.create_index("ix_time_entries_client", "time_entries", ["client_id"])
    op.create_index("ix_time_entries_invoice_id", "time_entries", ["invoice_id"])


def downgrade() -> None:
    op.drop_table("time_entries")
    op.drop_table("invoice_items")
    op.drop_table("invoices")
    op.drop_table("clients")
    op.drop_table("business_profiles")
