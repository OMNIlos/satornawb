"""add WB source cache metadata

Revision ID: 20260810_0024
Revises: 20260810_0023
Create Date: 2026-08-10 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260810_0024"
down_revision = "20260810_0023"
branch_labels = None
depends_on = None


def upgrade() -> None:
    columns = (
        sa.Column("range_date_from", sa.Date(), nullable=True),
        sa.Column("range_date_to", sa.Date(), nullable=True),
        sa.Column("daily_detail_status", sa.String(length=32), nullable=True),
        sa.Column("daily_detail_error", sa.Text(), nullable=True),
        sa.Column("daily_detail_deferred_at", sa.String(length=64), nullable=True),
        sa.Column("daily_detail_paused_at", sa.String(length=64), nullable=True),
        sa.Column("daily_detail_failed_at", sa.String(length=64), nullable=True),
        sa.Column("daily_detail_fetched_at", sa.String(length=64), nullable=True),
        sa.Column("daily_detail_partial_at", sa.String(length=64), nullable=True),
        sa.Column("daily_detail_preserved_at", sa.String(length=64), nullable=True),
        sa.Column("daily_detail_preserved_by", sa.String(length=128), nullable=True),
        sa.Column("daily_detail_requests_completed", sa.Integer(), nullable=True),
        sa.Column("daily_detail_requests_total", sa.Integer(), nullable=True),
        sa.Column("daily_aggregate_dates", sa.JSON(), nullable=True),
    )
    for column in columns:
        op.add_column("wb_repricer_source_cache", column)
    op.create_index(
        "ix_wb_repricer_source_cache_org_key_fetched",
        "wb_repricer_source_cache",
        ["organization_id", "source_key", "fetched_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_wb_repricer_source_cache_org_key_fetched", table_name="wb_repricer_source_cache")
    for column_name in (
        "daily_aggregate_dates",
        "daily_detail_requests_total",
        "daily_detail_requests_completed",
        "daily_detail_preserved_by",
        "daily_detail_preserved_at",
        "daily_detail_partial_at",
        "daily_detail_fetched_at",
        "daily_detail_failed_at",
        "daily_detail_paused_at",
        "daily_detail_deferred_at",
        "daily_detail_error",
        "daily_detail_status",
        "range_date_to",
        "range_date_from",
    ):
        op.drop_column("wb_repricer_source_cache", column_name)
