"""store finance revenue basis outside source cache payload

Revision ID: 20260825_0025
Revises: 20260810_0024
Create Date: 2026-08-25 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260825_0025"
down_revision = "20260810_0024"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "wb_repricer_source_cache",
        sa.Column("revenue_basis", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "wb_repricer_source_cache",
        sa.Column("finance_schema_version", sa.String(length=32), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("wb_repricer_source_cache", "finance_schema_version")
    op.drop_column("wb_repricer_source_cache", "revenue_basis")
