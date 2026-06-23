"""first-class business/private flag on transactions; retire freelance_tag

Revision ID: 0031
Revises: 0030
Create Date: 2026-06-23

Adds transactions.is_business and backfills it from the data that used to mark a
transaction as business: a tag matching the user's TaxProfile.freelance_tag (or
the literal "freelance" for users without a profile). Then drops freelance_tag,
since the flag is now the source of truth for the EÜR.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0031"
down_revision: Union[str, None] = "0030"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "transactions",
        sa.Column("is_business", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    # Backfill from the old tag mechanism (Postgres: cast JSON tags to jsonb, use the `?` element
    # test). Users with a tax profile use their configured tag; everyone else falls back to
    # "freelance" (the historical default).
    op.execute(
        """
        UPDATE transactions t
        SET is_business = true
        FROM tax_profiles tp
        WHERE tp.user_id = t.user_id
          AND t.tags::jsonb ? tp.freelance_tag
        """
    )
    op.execute(
        """
        UPDATE transactions t
        SET is_business = true
        WHERE NOT EXISTS (SELECT 1 FROM tax_profiles tp WHERE tp.user_id = t.user_id)
          AND t.tags::jsonb ? 'freelance'
        """
    )
    op.drop_column("tax_profiles", "freelance_tag")


def downgrade() -> None:
    op.add_column(
        "tax_profiles",
        sa.Column("freelance_tag", sa.String(50), nullable=False, server_default="freelance"),
    )
    op.drop_column("transactions", "is_business")
