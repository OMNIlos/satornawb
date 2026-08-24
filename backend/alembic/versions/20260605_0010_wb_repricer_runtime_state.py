from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "20260605_0010"
down_revision = "20260604_0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "wb_repricer_runtime_state",
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("state_payload", sa.JSON(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["lk_organizations.organization_id"]),
        sa.PrimaryKeyConstraint("organization_id"),
    )
    op.create_table(
        "wb_repricer_execution_runs",
        sa.Column("run_id", sa.String(length=64), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("trigger", sa.String(length=32), nullable=False),
        sa.Column("report_payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["lk_organizations.organization_id"]),
        sa.PrimaryKeyConstraint("run_id"),
    )
    op.create_index("ix_wb_repricer_execution_runs_org", "wb_repricer_execution_runs", ["organization_id"])
    op.create_table(
        "wb_repricer_changelog",
        sa.Column("row_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("entry_id", sa.String(length=128), nullable=False),
        sa.Column("article_id", sa.String(length=128), nullable=False),
        sa.Column("entry_payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["lk_organizations.organization_id"]),
        sa.PrimaryKeyConstraint("row_id"),
        sa.UniqueConstraint("organization_id", "entry_id", name="uq_wb_repricer_changelog_org_entry"),
    )
    op.create_index("ix_wb_repricer_changelog_org_article", "wb_repricer_changelog", ["organization_id", "article_id"])


def downgrade() -> None:
    op.drop_index("ix_wb_repricer_changelog_org_article", table_name="wb_repricer_changelog")
    op.drop_table("wb_repricer_changelog")
    op.drop_index("ix_wb_repricer_execution_runs_org", table_name="wb_repricer_execution_runs")
    op.drop_table("wb_repricer_execution_runs")
    op.drop_table("wb_repricer_runtime_state")
