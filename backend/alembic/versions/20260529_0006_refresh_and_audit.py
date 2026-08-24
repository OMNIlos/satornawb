"""refresh sessions and extended audit fields

Revision ID: 20260529_0006
Revises: 20260529_0005
Create Date: 2026-05-29
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260529_0006"
down_revision = "20260529_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("lk_sessions", sa.Column("revoked_reason", sa.String(length=64), nullable=True))
    op.add_column("lk_sessions", sa.Column("refresh_token_hash", sa.String(length=128), nullable=True))
    op.add_column("lk_sessions", sa.Column("refresh_token_expires_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_lk_sessions_refresh_token_hash", "lk_sessions", ["refresh_token_hash"])

    op.add_column("lk_audit_events", sa.Column("before_state", sa.JSON(), nullable=True))
    op.add_column("lk_audit_events", sa.Column("after_state", sa.JSON(), nullable=True))
    op.add_column("lk_audit_events", sa.Column("reason", sa.Text(), nullable=True))
    op.add_column("lk_audit_events", sa.Column("ip_address", sa.String(length=64), nullable=True))
    op.add_column("lk_audit_events", sa.Column("user_agent", sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column("lk_audit_events", "user_agent")
    op.drop_column("lk_audit_events", "ip_address")
    op.drop_column("lk_audit_events", "reason")
    op.drop_column("lk_audit_events", "after_state")
    op.drop_column("lk_audit_events", "before_state")

    op.drop_index("ix_lk_sessions_refresh_token_hash", table_name="lk_sessions")
    op.drop_column("lk_sessions", "refresh_token_expires_at")
    op.drop_column("lk_sessions", "refresh_token_hash")
    op.drop_column("lk_sessions", "revoked_reason")
