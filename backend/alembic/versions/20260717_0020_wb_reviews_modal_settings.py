"""Persist WB reviews modal settings."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260717_0020"
down_revision = "20260717_0019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "rv_review_sync_settings",
        sa.Column("settings_payload", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
    )
    op.alter_column("rv_review_sync_settings", "settings_payload", server_default=None)


def downgrade() -> None:
    op.drop_column("rv_review_sync_settings", "settings_payload")
