"""add reversible sales document archive

Revision ID: 20260829_0043
Revises: 20260829_0042
"""

import sqlalchemy as sa

from alembic import op

revision = "20260829_0043"
down_revision = "20260829_0042"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "sales_records",
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_sales_records_org_archive",
        "sales_records",
        ["organization_id", "archived_at", "sold_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_sales_records_org_archive", table_name="sales_records")
    op.drop_column("sales_records", "archived_at")
