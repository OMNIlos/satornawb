"""Add required configurable AI prompt for WB reviews."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260717_0019"
down_revision = "20260717_0018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("rv_review_sync_settings", sa.Column("ai_prompt", sa.Text(), nullable=False, server_default=""))


def downgrade() -> None:
    op.drop_column("rv_review_sync_settings", "ai_prompt")
