"""store raw WB advertising evidence

Revision ID: 20260903_0058
Revises: 20260903_0057
Create Date: 2026-09-03
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "20260903_0058"
down_revision = "20260903_0057"
branch_labels = None
depends_on = None

RUN_TABLE = "wb_advertising_sync_runs"
FACT_TABLE = "wb_advertising_facts"
CAMPAIGN_TABLE = "wb_advertising_campaign_snapshots"
DOCUMENT_TABLE = "wb_advertising_spend_documents"
RAW_TABLES = (CAMPAIGN_TABLE, DOCUMENT_TABLE)


def upgrade() -> None:
    for table in (RUN_TABLE, FACT_TABLE):
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")

    for column in (
        sa.Column("parent_sync_run_id", sa.String(length=36), nullable=True),
        sa.Column("raw_manifest", sa.JSON(), nullable=True),
        sa.Column("raw_manifest_checksum", sa.String(length=64), nullable=True),
        sa.Column("expected_request_count", sa.Integer(), nullable=True),
        sa.Column("completed_request_count", sa.Integer(), nullable=True),
        sa.Column("campaign_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "spend_document_count", sa.Integer(), nullable=False, server_default="0"
        ),
        sa.Column("document_total_spend_kopecks", sa.BigInteger(), nullable=True),
    ):
        op.add_column(RUN_TABLE, column)
    op.create_foreign_key(
        "fk_wb_advertising_sync_runs_parent",
        RUN_TABLE,
        RUN_TABLE,
        ["organization_id", "marketplace_account_id", "parent_sync_run_id"],
        ["organization_id", "marketplace_account_id", "sync_run_id"],
    )
    op.create_check_constraint(
        "ck_wb_advertising_sync_runs_parent_not_self",
        RUN_TABLE,
        "parent_sync_run_id IS NULL OR parent_sync_run_id <> sync_run_id",
    )
    op.create_check_constraint(
        "ck_wb_advertising_sync_runs_raw_counts",
        RUN_TABLE,
        "campaign_count >= 0 AND spend_document_count >= 0",
    )
    op.create_check_constraint(
        "ck_wb_advertising_sync_runs_raw_coverage",
        RUN_TABLE,
        "(raw_manifest IS NULL AND raw_manifest_checksum IS NULL "
        "AND expected_request_count IS NULL AND completed_request_count IS NULL) OR "
        "(raw_manifest IS NOT NULL AND raw_manifest_checksum IS NOT NULL "
        "AND expected_request_count IS NOT NULL AND completed_request_count IS NOT NULL "
        "AND expected_request_count >= 0 AND completed_request_count >= 0 "
        "AND completed_request_count <= expected_request_count)",
    )
    op.create_index(
        "ix_wb_advertising_sync_runs_parent",
        RUN_TABLE,
        ["organization_id", "marketplace_account_id", "parent_sync_run_id"],
    )

    for column in (
        sa.Column("grain", sa.String(length=16), nullable=True),
        sa.Column("date_from", sa.Date(), nullable=True),
        sa.Column("date_to", sa.Date(), nullable=True),
        sa.Column("fact_scope", sa.String(length=16), nullable=True),
        sa.Column("app_type", sa.Integer(), nullable=True),
        sa.Column("currency", sa.String(length=8), nullable=True),
        sa.Column("cancel_count", sa.BigInteger(), nullable=True),
    ):
        op.add_column(FACT_TABLE, column)
    op.execute(sa.text("""
            UPDATE wb_advertising_facts AS fact
            SET grain = CASE WHEN fact.business_date IS NULL THEN 'period' ELSE 'day' END,
                date_from = COALESCE(fact.business_date, run.date_from),
                date_to = COALESCE(fact.business_date, run.date_to),
                fact_scope = CASE
                    WHEN fact.nm_id IS NOT NULL THEN 'source_sku'
                    WHEN fact.campaign_id IS NOT NULL THEN 'campaign'
                    ELSE 'account'
                END
            FROM wb_advertising_sync_runs AS run
            WHERE run.organization_id = fact.organization_id
              AND run.marketplace_account_id = fact.marketplace_account_id
              AND run.sync_run_id = fact.sync_run_id
            """))
    for name, type_ in (
        ("grain", sa.String(length=16)),
        ("date_from", sa.Date()),
        ("date_to", sa.Date()),
        ("fact_scope", sa.String(length=16)),
    ):
        op.alter_column(
            FACT_TABLE,
            name,
            existing_type=type_,
            existing_nullable=True,
            nullable=False,
        )
    op.alter_column(
        FACT_TABLE,
        "spend_kopecks",
        existing_type=sa.BigInteger(),
        existing_nullable=False,
        nullable=True,
    )
    op.execute(sa.text("""
            DO $$
            BEGIN
                IF EXISTS (
                    SELECT 1
                    FROM wb_advertising_facts
                    GROUP BY organization_id, marketplace_account_id,
                             sync_run_id, source_identity
                    HAVING COUNT(*) > 1
                ) THEN
                    RAISE EXCEPTION
                        'cannot enforce raw advertising source identity uniqueness';
                END IF;
            END
            $$
            """))
    op.drop_constraint(
        "uq_wb_advertising_facts_observation", FACT_TABLE, type_="unique"
    )
    op.create_unique_constraint(
        "uq_wb_advertising_facts_source_identity",
        FACT_TABLE,
        ["organization_id", "marketplace_account_id", "sync_run_id", "source_identity"],
    )
    op.create_check_constraint(
        "ck_wb_advertising_facts_grain",
        FACT_TABLE,
        "grain IN ('day', 'period')",
    )
    op.create_check_constraint(
        "ck_wb_advertising_facts_period",
        FACT_TABLE,
        "date_from <= date_to AND (grain <> 'day' OR date_from = date_to)",
    )
    op.create_check_constraint(
        "ck_wb_advertising_facts_scope",
        FACT_TABLE,
        "fact_scope IN ('account', 'campaign', 'source_sku')",
    )
    op.create_check_constraint(
        "ck_wb_advertising_facts_scope_identity",
        FACT_TABLE,
        "(fact_scope = 'account' AND campaign_id IS NULL AND nm_id IS NULL) OR "
        "(fact_scope = 'campaign' AND campaign_id IS NOT NULL AND nm_id IS NULL) OR "
        "(fact_scope = 'source_sku' AND nm_id IS NOT NULL)",
    )
    op.drop_constraint("ck_wb_advertising_facts_metrics", FACT_TABLE, type_="check")
    op.create_check_constraint(
        "ck_wb_advertising_facts_metrics",
        FACT_TABLE,
        "(impressions IS NULL OR impressions >= 0) "
        "AND (clicks IS NULL OR clicks >= 0) "
        "AND (cart_adds IS NULL OR cart_adds >= 0) "
        "AND (order_count IS NULL OR order_count >= 0) "
        "AND (order_revenue_kopecks IS NULL OR order_revenue_kopecks >= 0) "
        "AND (cancel_count IS NULL OR cancel_count >= 0)",
    )
    op.create_index(
        "ix_wb_advertising_facts_campaign_period",
        FACT_TABLE,
        [
            "organization_id",
            "marketplace_account_id",
            "date_from",
            "date_to",
            "campaign_id",
            "fact_scope",
            "sync_run_id",
        ],
    )
    op.create_index(
        "ix_wb_advertising_facts_sku_period",
        FACT_TABLE,
        [
            "organization_id",
            "marketplace_account_id",
            "date_from",
            "date_to",
            "nm_id",
            "fact_scope",
            "sync_run_id",
        ],
    )

    op.create_table(
        CAMPAIGN_TABLE,
        sa.Column("campaign_snapshot_id", sa.String(length=64), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("marketplace_account_id", sa.Integer(), nullable=False),
        sa.Column("sync_run_id", sa.String(length=36), nullable=False),
        sa.Column("source_identity", sa.String(length=160), nullable=False),
        sa.Column("payload_checksum", sa.String(length=64), nullable=False),
        sa.Column("campaign_id", sa.BigInteger(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=True),
        sa.Column("campaign_type", sa.Integer(), nullable=True),
        sa.Column("status", sa.Integer(), nullable=True),
        sa.Column("payment_type", sa.String(length=32), nullable=True),
        sa.Column("bid_type", sa.String(length=32), nullable=True),
        sa.Column("member_nm_ids", sa.JSON(), nullable=False),
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
            name="fk_wb_advertising_campaign_snapshots_org_account_run",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("campaign_snapshot_id"),
        sa.UniqueConstraint(
            "organization_id",
            "marketplace_account_id",
            "sync_run_id",
            "source_identity",
            name="uq_wb_advertising_campaign_snapshots_source_identity",
        ),
        sa.CheckConstraint(
            "campaign_id > 0", name="ck_wb_advertising_campaign_snapshots_campaign"
        ),
    )
    op.create_index(
        "ix_wb_advertising_campaign_snapshots_campaign",
        CAMPAIGN_TABLE,
        ["organization_id", "marketplace_account_id", "campaign_id", "sync_run_id"],
    )

    op.create_table(
        DOCUMENT_TABLE,
        sa.Column("spend_document_id", sa.String(length=64), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("marketplace_account_id", sa.Integer(), nullable=False),
        sa.Column("sync_run_id", sa.String(length=36), nullable=False),
        sa.Column("source_identity", sa.String(length=160), nullable=False),
        sa.Column("payload_checksum", sa.String(length=64), nullable=False),
        sa.Column("upd_num", sa.String(length=128), nullable=False),
        sa.Column("upd_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("business_date", sa.Date(), nullable=False),
        sa.Column("campaign_id", sa.BigInteger(), nullable=False),
        sa.Column("campaign_name", sa.String(length=255), nullable=True),
        sa.Column("campaign_type", sa.Integer(), nullable=True),
        sa.Column("payment_type", sa.String(length=32), nullable=True),
        sa.Column("campaign_status", sa.Integer(), nullable=True),
        sa.Column("currency", sa.String(length=8), nullable=True),
        sa.Column("spend_kopecks", sa.BigInteger(), nullable=False),
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
            name="fk_wb_advertising_spend_documents_org_account_run",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("spend_document_id"),
        sa.UniqueConstraint(
            "organization_id",
            "marketplace_account_id",
            "sync_run_id",
            "source_identity",
            name="uq_wb_advertising_spend_documents_source_identity",
        ),
        sa.CheckConstraint(
            "upd_num <> ''", name="ck_wb_advertising_spend_documents_upd_num"
        ),
        sa.CheckConstraint(
            "campaign_id > 0", name="ck_wb_advertising_spend_documents_campaign"
        ),
    )
    op.create_index(
        "ix_wb_advertising_spend_documents_date_campaign",
        DOCUMENT_TABLE,
        [
            "organization_id",
            "marketplace_account_id",
            "business_date",
            "campaign_id",
            "sync_run_id",
        ],
    )
    op.create_index(
        "ix_wb_advertising_spend_documents_source",
        DOCUMENT_TABLE,
        [
            "organization_id",
            "marketplace_account_id",
            "upd_num",
            "campaign_id",
            "upd_time",
        ],
    )

    tenant = "organization_id = NULLIF(current_setting('app.organization_id', true), '')::integer"
    for table in RAW_TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY tenant_isolation_{table} ON {table} "
            f"USING ({tenant}) WITH CHECK ({tenant})"
        )
    for table in (RUN_TABLE, FACT_TABLE):
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")


def downgrade() -> None:
    for table in (RUN_TABLE, FACT_TABLE):
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")

    op.execute(sa.text("""
            DO $$
            BEGIN
                IF EXISTS (
                    SELECT 1
                    FROM wb_advertising_sync_runs
                    WHERE formula_version = 'wb-advertising-raw-v1'
                ) THEN
                    RAISE EXCEPTION
                        'cannot downgrade while raw advertising evidence exists';
                END IF;
            END
            $$
            """))
    for table in reversed(RAW_TABLES):
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation_{table} ON {table}")
        op.drop_table(table)

    op.drop_index("ix_wb_advertising_facts_sku_period", table_name=FACT_TABLE)
    op.drop_index("ix_wb_advertising_facts_campaign_period", table_name=FACT_TABLE)
    op.drop_constraint("ck_wb_advertising_facts_metrics", FACT_TABLE, type_="check")
    for name in (
        "ck_wb_advertising_facts_scope_identity",
        "ck_wb_advertising_facts_scope",
        "ck_wb_advertising_facts_period",
        "ck_wb_advertising_facts_grain",
    ):
        op.drop_constraint(name, FACT_TABLE, type_="check")
    op.drop_constraint(
        "uq_wb_advertising_facts_source_identity", FACT_TABLE, type_="unique"
    )
    op.create_unique_constraint(
        "uq_wb_advertising_facts_observation",
        FACT_TABLE,
        [
            "organization_id",
            "marketplace_account_id",
            "sync_run_id",
            "source_identity",
            "payload_checksum",
        ],
    )
    op.create_check_constraint(
        "ck_wb_advertising_facts_metrics",
        FACT_TABLE,
        "(impressions IS NULL OR impressions >= 0) "
        "AND (clicks IS NULL OR clicks >= 0) "
        "AND (cart_adds IS NULL OR cart_adds >= 0) "
        "AND (order_count IS NULL OR order_count >= 0) "
        "AND (order_revenue_kopecks IS NULL OR order_revenue_kopecks >= 0)",
    )
    op.alter_column(
        FACT_TABLE,
        "spend_kopecks",
        existing_type=sa.BigInteger(),
        existing_nullable=True,
        nullable=False,
    )
    for name in reversed(
        (
            "grain",
            "date_from",
            "date_to",
            "fact_scope",
            "app_type",
            "currency",
            "cancel_count",
        )
    ):
        op.drop_column(FACT_TABLE, name)

    op.drop_index("ix_wb_advertising_sync_runs_parent", table_name=RUN_TABLE)
    for name, type_ in (
        ("ck_wb_advertising_sync_runs_raw_coverage", "check"),
        ("ck_wb_advertising_sync_runs_raw_counts", "check"),
        ("ck_wb_advertising_sync_runs_parent_not_self", "check"),
        ("fk_wb_advertising_sync_runs_parent", "foreignkey"),
    ):
        op.drop_constraint(name, RUN_TABLE, type_=type_)
    for name in reversed(
        (
            "parent_sync_run_id",
            "raw_manifest",
            "raw_manifest_checksum",
            "expected_request_count",
            "completed_request_count",
            "campaign_count",
            "spend_document_count",
            "document_total_spend_kopecks",
        )
    ):
        op.drop_column(RUN_TABLE, name)
    for table in (RUN_TABLE, FACT_TABLE):
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
