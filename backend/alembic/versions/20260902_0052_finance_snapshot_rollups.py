"""materialize per-SKU finance snapshot rollups

Revision ID: 20260902_0052
Revises: 20260902_0051
Create Date: 2026-09-02
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "20260902_0052"
down_revision = "20260902_0051"
branch_labels = None
depends_on = None

TABLE = "wb_finance_sync_run_sku_rollups"


def upgrade() -> None:
    op.add_column(
        "wb_finance_sync_runs",
        sa.Column(
            "is_rollup_materialized",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.create_table(
        TABLE,
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("marketplace_account_id", sa.Integer(), nullable=False),
        sa.Column("sync_run_id", sa.String(length=36), nullable=False),
        sa.Column("nm_id", sa.BigInteger(), nullable=False),
        sa.Column("seller_article", sa.String(length=128), nullable=True),
        sa.Column("operation_count", sa.Integer(), nullable=False),
        sa.Column("revenue_kopecks", sa.BigInteger(), nullable=False),
        sa.Column("main_revenue_kopecks", sa.BigInteger(), nullable=False),
        sa.Column("redemptions_revenue_kopecks", sa.BigInteger(), nullable=False),
        sa.Column("late_correction_revenue_kopecks", sa.BigInteger(), nullable=False),
        sa.Column("unknown_revenue_kopecks", sa.BigInteger(), nullable=False),
        sa.Column("sales_units", sa.Integer(), nullable=False),
        sa.Column("returns_units", sa.Integer(), nullable=False),
        sa.Column("net_units", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["organization_id", "marketplace_account_id", "sync_run_id"],
            [
                "wb_finance_sync_runs.organization_id",
                "wb_finance_sync_runs.marketplace_account_id",
                "wb_finance_sync_runs.sync_run_id",
            ],
            name="fk_wb_finance_rollups_org_account_run",
            ondelete="CASCADE",
        ),
        sa.CheckConstraint("nm_id >= 0", name="ck_wb_finance_rollups_nm_id"),
        sa.PrimaryKeyConstraint(
            "organization_id",
            "marketplace_account_id",
            "sync_run_id",
            "nm_id",
        ),
    )
    tenant = "organization_id = NULLIF(current_setting('app.organization_id', true), '')::integer"
    op.execute(f"ALTER TABLE {TABLE} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {TABLE} FORCE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY tenant_isolation_{TABLE} ON {TABLE} "
        f"USING ({tenant}) WITH CHECK ({tenant})"
    )


def downgrade() -> None:
    op.execute(f"DROP POLICY IF EXISTS tenant_isolation_{TABLE} ON {TABLE}")
    op.drop_table(TABLE)
    op.drop_column("wb_finance_sync_runs", "is_rollup_materialized")
