"""add canonical WB advertising snapshots

Revision ID: 20260903_0057
Revises: 20260903_0056
Create Date: 2026-09-03
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "20260903_0057"
down_revision = "20260903_0056"
branch_labels = None
depends_on = None

RUN_TABLE = "wb_advertising_sync_runs"
FACT_TABLE = "wb_advertising_facts"
TABLES = (RUN_TABLE, FACT_TABLE)


def upgrade() -> None:
    op.create_table(
        RUN_TABLE,
        sa.Column("sync_run_id", sa.String(length=36), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("marketplace_account_id", sa.Integer(), nullable=False),
        sa.Column("source_kind", sa.String(length=32), nullable=False),
        sa.Column("date_from", sa.Date(), nullable=False),
        sa.Column("date_to", sa.Date(), nullable=False),
        sa.Column("source_reference", sa.String(length=255), nullable=False),
        sa.Column("snapshot_checksum", sa.String(length=64), nullable=False),
        sa.Column("formula_version", sa.String(length=32), nullable=False),
        sa.Column("source_total_spend_kopecks", sa.BigInteger(), nullable=False),
        sa.Column("fact_count", sa.Integer(), nullable=False),
        sa.Column("evidence_status", sa.String(length=32), nullable=False),
        sa.Column(
            "is_materialized",
            sa.Boolean(),
            server_default=sa.false(),
            nullable=False,
        ),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["lk_organizations.organization_id"]
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "marketplace_account_id"],
            [
                "marketplace_accounts.organization_id",
                "marketplace_accounts.marketplace_account_id",
            ],
            name="fk_wb_advertising_sync_runs_org_account",
        ),
        sa.PrimaryKeyConstraint("sync_run_id"),
        sa.UniqueConstraint(
            "organization_id",
            "marketplace_account_id",
            "sync_run_id",
            name="uq_wb_advertising_sync_runs_org_account_id",
        ),
        sa.UniqueConstraint(
            "organization_id",
            "marketplace_account_id",
            "source_kind",
            "date_from",
            "date_to",
            "snapshot_checksum",
            name="uq_wb_advertising_sync_runs_snapshot",
        ),
        sa.CheckConstraint(
            "source_kind IN ('finance_promotion', 'ads_fullstats')",
            name="ck_wb_advertising_sync_runs_source",
        ),
        sa.CheckConstraint(
            "evidence_status IN ('raw', 'aggregate_only', 'derived_legacy')",
            name="ck_wb_advertising_sync_runs_evidence",
        ),
        sa.CheckConstraint(
            "date_from <= date_to", name="ck_wb_advertising_sync_runs_period"
        ),
        sa.CheckConstraint(
            "fact_count >= 0", name="ck_wb_advertising_sync_runs_fact_count"
        ),
    )
    op.create_index(
        "ix_wb_advertising_sync_runs_exact",
        RUN_TABLE,
        [
            "organization_id",
            "marketplace_account_id",
            "date_from",
            "date_to",
            "source_kind",
            "is_materialized",
            "last_observed_at",
        ],
    )
    op.create_table(
        FACT_TABLE,
        sa.Column("advertising_fact_id", sa.String(length=64), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("marketplace_account_id", sa.Integer(), nullable=False),
        sa.Column("sync_run_id", sa.String(length=36), nullable=False),
        sa.Column("source_identity", sa.String(length=160), nullable=False),
        sa.Column("payload_checksum", sa.String(length=64), nullable=False),
        sa.Column("business_date", sa.Date(), nullable=True),
        sa.Column("campaign_id", sa.BigInteger(), nullable=True),
        sa.Column("nm_id", sa.BigInteger(), nullable=True),
        sa.Column("attribution_level", sa.String(length=24), nullable=False),
        sa.Column("spend_kopecks", sa.BigInteger(), nullable=False),
        sa.Column("impressions", sa.BigInteger(), nullable=True),
        sa.Column("clicks", sa.BigInteger(), nullable=True),
        sa.Column("cart_adds", sa.BigInteger(), nullable=True),
        sa.Column("order_count", sa.BigInteger(), nullable=True),
        sa.Column("order_revenue_kopecks", sa.BigInteger(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["lk_organizations.organization_id"]
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "marketplace_account_id", "sync_run_id"],
            [
                f"{RUN_TABLE}.organization_id",
                f"{RUN_TABLE}.marketplace_account_id",
                f"{RUN_TABLE}.sync_run_id",
            ],
            name="fk_wb_advertising_facts_org_account_run",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("advertising_fact_id"),
        sa.UniqueConstraint(
            "organization_id",
            "marketplace_account_id",
            "sync_run_id",
            "source_identity",
            "payload_checksum",
            name="uq_wb_advertising_facts_observation",
        ),
        sa.CheckConstraint(
            "attribution_level IN "
            "('exact_sku', 'campaign_sku', 'campaign_only', 'unknown')",
            name="ck_wb_advertising_facts_attribution",
        ),
        sa.CheckConstraint(
            "(impressions IS NULL OR impressions >= 0) "
            "AND (clicks IS NULL OR clicks >= 0) "
            "AND (cart_adds IS NULL OR cart_adds >= 0) "
            "AND (order_count IS NULL OR order_count >= 0) "
            "AND (order_revenue_kopecks IS NULL OR order_revenue_kopecks >= 0)",
            name="ck_wb_advertising_facts_metrics",
        ),
    )
    op.create_index(
        "ix_wb_advertising_facts_run",
        FACT_TABLE,
        ["organization_id", "marketplace_account_id", "sync_run_id"],
    )
    op.create_index(
        "ix_wb_advertising_facts_product_date",
        FACT_TABLE,
        ["organization_id", "marketplace_account_id", "nm_id", "business_date"],
    )

    tenant = "organization_id = NULLIF(current_setting('app.organization_id', true), '')::integer"
    for table in TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY tenant_isolation_{table} ON {table} "
            f"USING ({tenant}) WITH CHECK ({tenant})"
        )


def downgrade() -> None:
    for table in reversed(TABLES):
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation_{table} ON {table}")
        op.drop_table(table)
