from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "20260701_0012"
down_revision = "20260609_0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "wb_ads_report_cache",
        sa.Column("cache_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("date_from", sa.Date(), nullable=False),
        sa.Column("date_to", sa.Date(), nullable=False),
        sa.Column("group_by", sa.String(length=32), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["lk_organizations.organization_id"]),
        sa.PrimaryKeyConstraint("cache_id"),
        sa.UniqueConstraint("organization_id", "date_from", "date_to", "group_by", name="uq_wb_ads_report_cache_scope"),
    )
    op.create_index("ix_wb_ads_report_cache_org", "wb_ads_report_cache", ["organization_id"])

    op.create_table(
        "wb_ads_campaign_status_snapshots",
        sa.Column("snapshot_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("advert_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=64), nullable=True),
        sa.Column("advert_type", sa.String(length=64), nullable=True),
        sa.Column("payment_type", sa.String(length=32), nullable=True),
        sa.Column("change_time", sa.String(length=64), nullable=True),
        sa.Column("raw_payload", sa.JSON(), nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["lk_organizations.organization_id"]),
        sa.PrimaryKeyConstraint("snapshot_id"),
        sa.UniqueConstraint("organization_id", "advert_id", "fetched_at", name="uq_wb_ads_status_snapshot"),
    )
    op.create_index("ix_wb_ads_status_snapshots_org_advert", "wb_ads_campaign_status_snapshots", ["organization_id", "advert_id"])

    op.create_table(
        "wb_ads_campaign_budget_snapshots",
        sa.Column("snapshot_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("advert_id", sa.Integer(), nullable=False),
        sa.Column("cash_kopecks", sa.Integer(), nullable=True),
        sa.Column("netting_kopecks", sa.Integer(), nullable=True),
        sa.Column("total_kopecks", sa.Integer(), nullable=True),
        sa.Column("raw_payload", sa.JSON(), nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["lk_organizations.organization_id"]),
        sa.PrimaryKeyConstraint("snapshot_id"),
        sa.UniqueConstraint("organization_id", "advert_id", "fetched_at", name="uq_wb_ads_budget_snapshot"),
    )
    op.create_index("ix_wb_ads_budget_snapshots_org_advert", "wb_ads_campaign_budget_snapshots", ["organization_id", "advert_id"])

    op.create_table(
        "wb_ads_fullstats_daily_rows",
        sa.Column("row_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("report_date", sa.Date(), nullable=True),
        sa.Column("advert_id", sa.Integer(), nullable=True),
        sa.Column("app_type", sa.String(length=64), nullable=True),
        sa.Column("nm_id", sa.Integer(), nullable=True),
        sa.Column("attribution_level", sa.String(length=32), nullable=True),
        sa.Column("views", sa.Integer(), nullable=True),
        sa.Column("clicks", sa.Integer(), nullable=True),
        sa.Column("spend_kopecks", sa.Integer(), nullable=True),
        sa.Column("atbs", sa.Integer(), nullable=True),
        sa.Column("orders_count", sa.Integer(), nullable=True),
        sa.Column("orders_kopecks", sa.Integer(), nullable=True),
        sa.Column("raw_payload", sa.JSON(), nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["lk_organizations.organization_id"]),
        sa.PrimaryKeyConstraint("row_id"),
    )
    op.create_index("ix_wb_ads_fullstats_daily_org_date", "wb_ads_fullstats_daily_rows", ["organization_id", "report_date"])
    op.create_index("ix_wb_ads_fullstats_daily_org_advert", "wb_ads_fullstats_daily_rows", ["organization_id", "advert_id"])

    op.create_table(
        "wb_ads_spend_documents",
        sa.Column("row_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("upd_num", sa.String(length=128), nullable=True),
        sa.Column("upd_time", sa.String(length=64), nullable=True),
        sa.Column("advert_id", sa.Integer(), nullable=True),
        sa.Column("campaign_name", sa.String(length=255), nullable=True),
        sa.Column("campaign_type", sa.String(length=64), nullable=True),
        sa.Column("payment_type", sa.String(length=32), nullable=True),
        sa.Column("campaign_status", sa.String(length=64), nullable=True),
        sa.Column("spend_kopecks", sa.Integer(), nullable=True),
        sa.Column("raw_payload", sa.JSON(), nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["lk_organizations.organization_id"]),
        sa.PrimaryKeyConstraint("row_id"),
    )
    op.create_index("ix_wb_ads_spend_documents_org_advert", "wb_ads_spend_documents", ["organization_id", "advert_id"])


def downgrade() -> None:
    op.drop_index("ix_wb_ads_spend_documents_org_advert", table_name="wb_ads_spend_documents")
    op.drop_table("wb_ads_spend_documents")
    op.drop_index("ix_wb_ads_fullstats_daily_org_advert", table_name="wb_ads_fullstats_daily_rows")
    op.drop_index("ix_wb_ads_fullstats_daily_org_date", table_name="wb_ads_fullstats_daily_rows")
    op.drop_table("wb_ads_fullstats_daily_rows")
    op.drop_index("ix_wb_ads_budget_snapshots_org_advert", table_name="wb_ads_campaign_budget_snapshots")
    op.drop_table("wb_ads_campaign_budget_snapshots")
    op.drop_index("ix_wb_ads_status_snapshots_org_advert", table_name="wb_ads_campaign_status_snapshots")
    op.drop_table("wb_ads_campaign_status_snapshots")
    op.drop_index("ix_wb_ads_report_cache_org", table_name="wb_ads_report_cache")
    op.drop_table("wb_ads_report_cache")
