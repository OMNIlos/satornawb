"""control plane a4 tables

Revision ID: 20260526_0003
Revises: 20260526_0002
Create Date: 2026-05-26
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260526_0003"
down_revision = "20260526_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "cp_settings_versions",
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("settings_payload", sa.JSON(), nullable=False),
        sa.Column("created_by_id", sa.String(length=128), nullable=False),
        sa.Column("created_by_role", sa.String(length=32), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("approval_ref", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("version"),
    )

    op.create_table(
        "cp_audit_events",
        sa.Column("event_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("actor_id", sa.String(length=128), nullable=False),
        sa.Column("actor_role", sa.String(length=32), nullable=False),
        sa.Column("action", sa.String(length=128), nullable=False),
        sa.Column("object_type", sa.String(length=64), nullable=False),
        sa.Column("object_id", sa.String(length=128), nullable=False),
        sa.Column("before_state", sa.JSON(), nullable=True),
        sa.Column("after_state", sa.JSON(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("approval_ref", sa.String(length=255), nullable=True),
        sa.Column("evidence_refs", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("event_id"),
    )
    op.create_index("ix_cp_audit_events_action", "cp_audit_events", ["action"])
    op.create_index("ix_cp_audit_events_object", "cp_audit_events", ["object_type", "object_id"])

    op.create_table(
        "cp_sync_jobs",
        sa.Column("job_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("job_type", sa.String(length=64), nullable=False),
        sa.Column("source", sa.String(length=128), nullable=False),
        sa.Column("period", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("last_success_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error_code", sa.String(length=64), nullable=True),
        sa.Column("last_error_message", sa.Text(), nullable=True),
        sa.Column("retry_count", sa.Integer(), nullable=False),
        sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("stale_after", sa.DateTime(timezone=True), nullable=True),
        sa.Column("linked_registry_row_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("job_id"),
    )
    op.create_index("ix_cp_sync_jobs_status", "cp_sync_jobs", ["status"])
    op.create_index("ix_cp_sync_jobs_next_run_at", "cp_sync_jobs", ["next_run_at"])


def downgrade() -> None:
    op.drop_index("ix_cp_sync_jobs_next_run_at", table_name="cp_sync_jobs")
    op.drop_index("ix_cp_sync_jobs_status", table_name="cp_sync_jobs")
    op.drop_table("cp_sync_jobs")
    op.drop_index("ix_cp_audit_events_object", table_name="cp_audit_events")
    op.drop_index("ix_cp_audit_events_action", table_name="cp_audit_events")
    op.drop_table("cp_audit_events")
    op.drop_table("cp_settings_versions")

