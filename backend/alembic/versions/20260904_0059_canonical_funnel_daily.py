"""store canonical WB Sales Funnel daily evidence

Revision ID: 20260904_0059
Revises: 20260903_0058
Create Date: 2026-09-04
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "20260904_0059"
down_revision = "20260903_0058"
branch_labels = None
depends_on = None

RUN_TABLE = "wb_funnel_sync_runs"
FACT_TABLE = "wb_funnel_daily"
TABLES = (RUN_TABLE, FACT_TABLE)


def upgrade() -> None:
    op.create_table(
        RUN_TABLE,
        sa.Column("sync_run_id", sa.String(length=36), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("marketplace_account_id", sa.Integer(), nullable=False),
        sa.Column("parent_sync_run_id", sa.String(length=36), nullable=True),
        sa.Column("date_from", sa.Date(), nullable=False),
        sa.Column("date_to", sa.Date(), nullable=False),
        sa.Column("source_reference", sa.String(length=255), nullable=False),
        sa.Column("snapshot_checksum", sa.String(length=64), nullable=False),
        sa.Column("raw_manifest", sa.JSON(), nullable=False),
        sa.Column("raw_manifest_checksum", sa.String(length=64), nullable=False),
        sa.Column("expected_request_count", sa.Integer(), nullable=False),
        sa.Column("completed_request_count", sa.Integer(), nullable=False),
        sa.Column("normalizer_version", sa.String(length=32), nullable=False),
        sa.Column("fact_count", sa.Integer(), nullable=False),
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
            name="fk_wb_funnel_sync_runs_org_account",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "marketplace_account_id", "parent_sync_run_id"],
            [
                f"{RUN_TABLE}.organization_id",
                f"{RUN_TABLE}.marketplace_account_id",
                f"{RUN_TABLE}.sync_run_id",
            ],
            name="fk_wb_funnel_sync_runs_parent",
        ),
        sa.PrimaryKeyConstraint("sync_run_id"),
        sa.UniqueConstraint(
            "organization_id",
            "marketplace_account_id",
            "sync_run_id",
            name="uq_wb_funnel_sync_runs_org_account_id",
        ),
        sa.UniqueConstraint(
            "organization_id",
            "marketplace_account_id",
            "date_from",
            "date_to",
            "snapshot_checksum",
            name="uq_wb_funnel_sync_runs_snapshot",
        ),
        sa.CheckConstraint(
            "date_from <= date_to", name="ck_wb_funnel_sync_runs_period"
        ),
        sa.CheckConstraint(
            "expected_request_count > 0 "
            "AND completed_request_count = expected_request_count "
            "AND fact_count >= 0",
            name="ck_wb_funnel_sync_runs_counts",
        ),
        sa.CheckConstraint(
            "parent_sync_run_id IS NULL OR parent_sync_run_id <> sync_run_id",
            name="ck_wb_funnel_sync_runs_parent_not_self",
        ),
    )
    op.create_index(
        "ix_wb_funnel_sync_runs_exact",
        RUN_TABLE,
        [
            "organization_id",
            "marketplace_account_id",
            "date_from",
            "date_to",
            "last_observed_at",
        ],
    )
    op.create_index(
        "ix_wb_funnel_sync_runs_parent",
        RUN_TABLE,
        ["organization_id", "marketplace_account_id", "parent_sync_run_id"],
    )

    op.create_table(
        FACT_TABLE,
        sa.Column("funnel_daily_id", sa.String(length=64), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("marketplace_account_id", sa.Integer(), nullable=False),
        sa.Column("sync_run_id", sa.String(length=36), nullable=False),
        sa.Column("source_identity", sa.String(length=160), nullable=False),
        sa.Column("payload_checksum", sa.String(length=64), nullable=False),
        sa.Column("business_date", sa.Date(), nullable=False),
        sa.Column("nm_id", sa.BigInteger(), nullable=False),
        sa.Column("currency", sa.String(length=8), nullable=True),
        sa.Column("open_count", sa.BigInteger(), nullable=True),
        sa.Column("cart_count", sa.BigInteger(), nullable=True),
        sa.Column("order_count", sa.BigInteger(), nullable=True),
        sa.Column("order_amount_kopecks", sa.BigInteger(), nullable=True),
        sa.Column("buyout_count", sa.BigInteger(), nullable=True),
        sa.Column("buyout_amount_kopecks", sa.BigInteger(), nullable=True),
        sa.Column("add_to_wishlist_count", sa.BigInteger(), nullable=True),
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
            name="fk_wb_funnel_daily_org_account_run",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("funnel_daily_id"),
        sa.UniqueConstraint(
            "organization_id",
            "marketplace_account_id",
            "sync_run_id",
            "source_identity",
            name="uq_wb_funnel_daily_source_identity",
        ),
        sa.CheckConstraint("nm_id > 0", name="ck_wb_funnel_daily_nm_id"),
        sa.CheckConstraint(
            "(open_count IS NULL OR open_count >= 0) "
            "AND (cart_count IS NULL OR cart_count >= 0) "
            "AND (order_count IS NULL OR order_count >= 0) "
            "AND (order_amount_kopecks IS NULL OR order_amount_kopecks >= 0) "
            "AND (buyout_count IS NULL OR buyout_count >= 0) "
            "AND (buyout_amount_kopecks IS NULL OR buyout_amount_kopecks >= 0) "
            "AND (add_to_wishlist_count IS NULL OR add_to_wishlist_count >= 0)",
            name="ck_wb_funnel_daily_metrics",
        ),
        sa.CheckConstraint(
            "open_count IS NOT NULL OR cart_count IS NOT NULL "
            "OR order_count IS NOT NULL OR order_amount_kopecks IS NOT NULL "
            "OR buyout_count IS NOT NULL OR buyout_amount_kopecks IS NOT NULL "
            "OR add_to_wishlist_count IS NOT NULL",
            name="ck_wb_funnel_daily_has_metric",
        ),
    )
    op.create_index(
        "ix_wb_funnel_daily_product_date",
        FACT_TABLE,
        [
            "organization_id",
            "marketplace_account_id",
            "business_date",
            "nm_id",
            "sync_run_id",
        ],
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
    for table in TABLES:
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
    op.execute(sa.text("""
            DO $$
            BEGIN
                IF EXISTS (SELECT 1 FROM wb_funnel_sync_runs LIMIT 1) THEN
                    RAISE EXCEPTION
                        'cannot downgrade while canonical funnel evidence exists';
                END IF;
            END
            $$
            """))
    for table in reversed(TABLES):
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation_{table} ON {table}")
        op.drop_table(table)
