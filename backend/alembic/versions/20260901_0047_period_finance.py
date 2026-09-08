"""canonical Moscow periods and immutable WB finance snapshots

Revision ID: 20260901_0047
Revises: 20260901_0046
Create Date: 2026-09-01
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "20260901_0047"
down_revision = "20260901_0046"
branch_labels = None
depends_on = None

TENANT_TABLES = (
    "wb_finance_sync_runs",
    "wb_finance_operations",
    "wb_finance_sync_run_operations",
)


def _enable_rls(table: str) -> None:
    tenant = "organization_id = NULLIF(current_setting('app.organization_id', true), '')::integer"
    op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY tenant_isolation_{table} ON {table} "
        f"USING ({tenant}) WITH CHECK ({tenant})"
    )


def upgrade() -> None:
    op.create_table(
        "wb_finance_sync_runs",
        sa.Column("sync_run_id", sa.String(length=36), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("marketplace_account_id", sa.Integer(), nullable=False),
        sa.Column("date_from", sa.Date(), nullable=False),
        sa.Column("date_to", sa.Date(), nullable=False),
        sa.Column("snapshot_checksum", sa.String(length=64), nullable=False),
        sa.Column("formula_version", sa.String(length=32), nullable=False),
        sa.Column("operation_count", sa.Integer(), nullable=False),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "date_from <= date_to", name="ck_wb_finance_sync_runs_period"
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "marketplace_account_id"],
            [
                "marketplace_accounts.organization_id",
                "marketplace_accounts.marketplace_account_id",
            ],
            name="fk_wb_finance_sync_runs_org_account",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["lk_organizations.organization_id"]
        ),
        sa.PrimaryKeyConstraint("sync_run_id"),
        sa.UniqueConstraint(
            "organization_id",
            "marketplace_account_id",
            "sync_run_id",
            name="uq_wb_finance_sync_runs_org_account_id",
        ),
        sa.UniqueConstraint(
            "organization_id",
            "marketplace_account_id",
            "date_from",
            "date_to",
            "snapshot_checksum",
            name="uq_wb_finance_sync_runs_snapshot",
        ),
    )
    op.create_index(
        "ix_wb_finance_sync_runs_covering",
        "wb_finance_sync_runs",
        [
            "organization_id",
            "marketplace_account_id",
            "date_from",
            "date_to",
            "last_observed_at",
        ],
    )
    op.create_table(
        "wb_finance_operations",
        sa.Column("operation_id", sa.String(length=64), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("marketplace_account_id", sa.Integer(), nullable=False),
        sa.Column("source_identity", sa.String(length=80), nullable=False),
        sa.Column("payload_checksum", sa.String(length=64), nullable=False),
        sa.Column("rrd_id", sa.BigInteger(), nullable=True),
        sa.Column("report_id", sa.BigInteger(), nullable=True),
        sa.Column("report_type", sa.String(length=16), nullable=False),
        sa.Column("operation_kind", sa.String(length=16), nullable=False),
        sa.Column("business_date", sa.Date(), nullable=True),
        sa.Column("correction_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_late_correction", sa.Boolean(), nullable=False),
        sa.Column("nm_id", sa.BigInteger(), nullable=True),
        sa.Column("seller_article", sa.String(length=128), nullable=True),
        sa.Column("sign", sa.Integer(), nullable=False),
        sa.Column("units", sa.Integer(), nullable=False),
        sa.Column("revenue_kopecks", sa.BigInteger(), nullable=False),
        sa.Column("commission_kopecks", sa.BigInteger(), nullable=False),
        sa.Column("logistics_kopecks", sa.BigInteger(), nullable=False),
        sa.Column("storage_kopecks", sa.BigInteger(), nullable=False),
        sa.Column("acceptance_kopecks", sa.BigInteger(), nullable=False),
        sa.Column("penalty_kopecks", sa.BigInteger(), nullable=False),
        sa.Column("deduction_kopecks", sa.BigInteger(), nullable=False),
        sa.Column("additional_payment_kopecks", sa.BigInteger(), nullable=False),
        sa.Column("acquiring_kopecks", sa.BigInteger(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "report_type IN ('main', 'redemptions', 'unknown')",
            name="ck_wb_finance_operations_report_type",
        ),
        sa.CheckConstraint(
            "operation_kind IN ('sale', 'return', 'correction', 'other')",
            name="ck_wb_finance_operations_kind",
        ),
        sa.CheckConstraint("sign IN (-1, 0, 1)", name="ck_wb_finance_operations_sign"),
        sa.ForeignKeyConstraint(
            ["organization_id", "marketplace_account_id"],
            [
                "marketplace_accounts.organization_id",
                "marketplace_accounts.marketplace_account_id",
            ],
            name="fk_wb_finance_operations_org_account",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["lk_organizations.organization_id"]
        ),
        sa.PrimaryKeyConstraint("operation_id"),
        sa.UniqueConstraint(
            "organization_id",
            "marketplace_account_id",
            "operation_id",
            name="uq_wb_finance_operations_org_account_id",
        ),
    )
    op.create_index(
        "ix_wb_finance_operations_product_date",
        "wb_finance_operations",
        ["organization_id", "marketplace_account_id", "nm_id", "business_date"],
    )
    op.create_index(
        "ix_wb_finance_operations_source_identity",
        "wb_finance_operations",
        ["organization_id", "marketplace_account_id", "source_identity"],
    )
    op.create_table(
        "wb_finance_sync_run_operations",
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("marketplace_account_id", sa.Integer(), nullable=False),
        sa.Column("sync_run_id", sa.String(length=36), nullable=False),
        sa.Column("operation_id", sa.String(length=64), nullable=False),
        sa.ForeignKeyConstraint(
            ["organization_id", "marketplace_account_id", "operation_id"],
            [
                "wb_finance_operations.organization_id",
                "wb_finance_operations.marketplace_account_id",
                "wb_finance_operations.operation_id",
            ],
            name="fk_wb_finance_membership_org_account_operation",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "marketplace_account_id", "sync_run_id"],
            [
                "wb_finance_sync_runs.organization_id",
                "wb_finance_sync_runs.marketplace_account_id",
                "wb_finance_sync_runs.sync_run_id",
            ],
            name="fk_wb_finance_membership_org_account_run",
        ),
        sa.PrimaryKeyConstraint(
            "organization_id",
            "marketplace_account_id",
            "sync_run_id",
            "operation_id",
        ),
    )
    op.create_index(
        "ix_wb_finance_membership_operation",
        "wb_finance_sync_run_operations",
        ["organization_id", "marketplace_account_id", "operation_id"],
    )
    for table in TENANT_TABLES:
        _enable_rls(table)


def downgrade() -> None:
    op.drop_index(
        "ix_wb_finance_membership_operation",
        table_name="wb_finance_sync_run_operations",
    )
    op.drop_table("wb_finance_sync_run_operations")
    op.drop_index(
        "ix_wb_finance_operations_source_identity",
        table_name="wb_finance_operations",
    )
    op.drop_index(
        "ix_wb_finance_operations_product_date",
        table_name="wb_finance_operations",
    )
    op.drop_table("wb_finance_operations")
    op.drop_index("ix_wb_finance_sync_runs_covering", table_name="wb_finance_sync_runs")
    op.drop_table("wb_finance_sync_runs")
