"""personal cabinet auth and profile tables

Revision ID: 20260529_0005
Revises: 20260526_0004
Create Date: 2026-05-29
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260529_0005"
down_revision = "20260526_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "lk_organizations",
        sa.Column("organization_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("slug", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("organization_id"),
        sa.UniqueConstraint("slug"),
    )

    op.create_table(
        "lk_users",
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=False),
        sa.Column("permission_profile", sa.String(length=32), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["lk_organizations.organization_id"]),
        sa.PrimaryKeyConstraint("user_id"),
        sa.UniqueConstraint("email"),
    )

    op.create_table(
        "lk_user_permissions",
        sa.Column("permission_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("permission", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["lk_users.user_id"]),
        sa.PrimaryKeyConstraint("permission_id"),
        sa.UniqueConstraint("user_id", "permission", name="uq_lk_user_permissions_user_permission"),
    )
    op.create_index("ix_lk_user_permissions_user", "lk_user_permissions", ["user_id"])

    op.create_table(
        "lk_sessions",
        sa.Column("session_id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("user_agent", sa.String(length=255), nullable=True),
        sa.Column("ip_address", sa.String(length=64), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["lk_users.user_id"]),
        sa.PrimaryKeyConstraint("session_id"),
    )
    op.create_index("ix_lk_sessions_user", "lk_sessions", ["user_id"])
    op.create_index("ix_lk_sessions_expires", "lk_sessions", ["expires_at"])

    op.create_table(
        "lk_integrations",
        sa.Column("integration_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("external_account_id", sa.String(length=128), nullable=True),
        sa.Column("token_ref", sa.String(length=255), nullable=True),
        sa.Column("metadata_payload", sa.JSON(), nullable=False),
        sa.Column("updated_by_user_id", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["lk_organizations.organization_id"]),
        sa.ForeignKeyConstraint(["updated_by_user_id"], ["lk_users.user_id"]),
        sa.PrimaryKeyConstraint("integration_id"),
        sa.UniqueConstraint("organization_id", "provider", name="uq_lk_integrations_org_provider"),
    )

    op.create_table(
        "lk_audit_events",
        sa.Column("event_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("actor_user_id", sa.String(length=64), nullable=True),
        sa.Column("action", sa.String(length=128), nullable=False),
        sa.Column("object_type", sa.String(length=64), nullable=False),
        sa.Column("object_id", sa.String(length=128), nullable=False),
        sa.Column("details", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["lk_organizations.organization_id"]),
        sa.ForeignKeyConstraint(["actor_user_id"], ["lk_users.user_id"]),
        sa.PrimaryKeyConstraint("event_id"),
    )
    op.create_index("ix_lk_audit_events_org", "lk_audit_events", ["organization_id"])
    op.create_index("ix_lk_audit_events_created_at", "lk_audit_events", ["created_at"])

    op.create_table(
        "lk_user_preferences",
        sa.Column("preference_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("notification_settings", sa.JSON(), nullable=False),
        sa.Column("export_settings", sa.JSON(), nullable=False),
        sa.Column("timezone", sa.String(length=64), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["lk_users.user_id"]),
        sa.PrimaryKeyConstraint("preference_id"),
        sa.UniqueConstraint("user_id"),
    )


def downgrade() -> None:
    op.drop_table("lk_user_preferences")
    op.drop_index("ix_lk_audit_events_created_at", table_name="lk_audit_events")
    op.drop_index("ix_lk_audit_events_org", table_name="lk_audit_events")
    op.drop_table("lk_audit_events")
    op.drop_table("lk_integrations")
    op.drop_index("ix_lk_sessions_expires", table_name="lk_sessions")
    op.drop_index("ix_lk_sessions_user", table_name="lk_sessions")
    op.drop_table("lk_sessions")
    op.drop_index("ix_lk_user_permissions_user", table_name="lk_user_permissions")
    op.drop_table("lk_user_permissions")
    op.drop_table("lk_users")
    op.drop_table("lk_organizations")
