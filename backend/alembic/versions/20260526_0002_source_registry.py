"""source registry tables

Revision ID: 20260526_0002
Revises: 20260526_0001
Create Date: 2026-05-26
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260526_0002"
down_revision = "20260526_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "source_registry_blockers",
        sa.Column("blocker_id", sa.String(length=32), nullable=False),
        sa.Column("lifecycle_status", sa.String(length=16), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("owner", sa.String(length=255), nullable=False),
        sa.Column("impact_area", sa.String(length=255), nullable=False),
        sa.Column("resolution_needed", sa.Text(), nullable=False),
        sa.Column("source_ref", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("blocker_id"),
    )
    op.create_table(
        "source_registry_formulas",
        sa.Column("formula_id", sa.String(length=64), nullable=False),
        sa.Column("formula_name", sa.String(length=255), nullable=False),
        sa.Column("inputs", sa.Text(), nullable=False),
        sa.Column("output_units", sa.String(length=255), nullable=False),
        sa.Column("rule", sa.Text(), nullable=False),
        sa.Column("rounding", sa.String(length=255), nullable=False),
        sa.Column("owner", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("used_by", sa.Text(), nullable=False),
        sa.Column("blocker_ids", sa.JSON(), nullable=False),
        sa.Column("source_ref", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("formula_id"),
    )
    op.create_table(
        "source_registry_entries",
        sa.Column("row_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("screen", sa.String(length=128), nullable=False),
        sa.Column("metric_action", sa.String(length=255), nullable=False),
        sa.Column("module", sa.String(length=64), nullable=False),
        sa.Column("source_name", sa.Text(), nullable=False),
        sa.Column("source_field", sa.Text(), nullable=False),
        sa.Column("formula_text", sa.Text(), nullable=False),
        sa.Column("formula_id", sa.String(length=64), nullable=False),
        sa.Column("refresh_policy", sa.String(length=255), nullable=False),
        sa.Column("fallback_policy", sa.Text(), nullable=False),
        sa.Column("freshness_confidence", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("blocker_ids", sa.JSON(), nullable=False),
        sa.Column("critical_for_apply", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("source_ref", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["formula_id"], ["source_registry_formulas.formula_id"]),
        sa.PrimaryKeyConstraint("row_id"),
    )
    op.create_index("ix_source_registry_entries_screen", "source_registry_entries", ["screen"])
    op.create_index("ix_source_registry_entries_module", "source_registry_entries", ["module"])
    op.create_index("ix_source_registry_entries_status", "source_registry_entries", ["status"])
    op.create_index("ix_source_registry_entries_formula_id", "source_registry_entries", ["formula_id"])


def downgrade() -> None:
    op.drop_index("ix_source_registry_entries_formula_id", table_name="source_registry_entries")
    op.drop_index("ix_source_registry_entries_status", table_name="source_registry_entries")
    op.drop_index("ix_source_registry_entries_module", table_name="source_registry_entries")
    op.drop_index("ix_source_registry_entries_screen", table_name="source_registry_entries")
    op.drop_table("source_registry_entries")
    op.drop_table("source_registry_formulas")
    op.drop_table("source_registry_blockers")

