"""store changed finance snapshots as immutable deltas

Revision ID: 20260902_0049
Revises: 20260902_0048
Create Date: 2026-09-02
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "20260902_0049"
down_revision = "20260902_0048"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "wb_finance_sync_runs",
        sa.Column("parent_sync_run_id", sa.String(length=36), nullable=True),
    )
    op.add_column(
        "wb_finance_sync_runs",
        sa.Column(
            "is_materialized",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
    )
    op.add_column(
        "wb_finance_sync_run_operations",
        sa.Column(
            "is_present",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
    )
    op.create_foreign_key(
        "fk_wb_finance_sync_runs_parent",
        "wb_finance_sync_runs",
        "wb_finance_sync_runs",
        ["organization_id", "marketplace_account_id", "parent_sync_run_id"],
        ["organization_id", "marketplace_account_id", "sync_run_id"],
    )
    op.create_check_constraint(
        "ck_wb_finance_sync_runs_parent_not_self",
        "wb_finance_sync_runs",
        "parent_sync_run_id IS NULL OR parent_sync_run_id <> sync_run_id",
    )
    op.create_index(
        "ix_wb_finance_sync_runs_parent",
        "wb_finance_sync_runs",
        ["organization_id", "marketplace_account_id", "parent_sync_run_id"],
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            """
            DO $$
            BEGIN
                IF EXISTS (
                    SELECT 1
                    FROM wb_finance_sync_runs
                    WHERE parent_sync_run_id IS NOT NULL OR NOT is_materialized
                ) OR EXISTS (
                    SELECT 1
                    FROM wb_finance_sync_run_operations
                    WHERE NOT is_present
                ) THEN
                    RAISE EXCEPTION
                        'cannot downgrade finance deltas before removing delta/incomplete snapshots';
                END IF;
            END
            $$
            """
        )
    )
    op.drop_index(
        "ix_wb_finance_sync_runs_parent",
        table_name="wb_finance_sync_runs",
    )
    op.drop_constraint(
        "ck_wb_finance_sync_runs_parent_not_self",
        "wb_finance_sync_runs",
        type_="check",
    )
    op.drop_constraint(
        "fk_wb_finance_sync_runs_parent",
        "wb_finance_sync_runs",
        type_="foreignkey",
    )
    op.drop_column("wb_finance_sync_run_operations", "is_present")
    op.drop_column("wb_finance_sync_runs", "is_materialized")
    op.drop_column("wb_finance_sync_runs", "parent_sync_run_id")
