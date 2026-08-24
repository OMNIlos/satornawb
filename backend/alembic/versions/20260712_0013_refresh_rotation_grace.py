from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "20260712_0013"
down_revision = "20260701_0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("lk_sessions", sa.Column("previous_refresh_token_hash", sa.String(length=128), nullable=True))
    op.add_column("lk_sessions", sa.Column("previous_refresh_token_expires_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_lk_sessions_previous_refresh_hash", "lk_sessions", ["previous_refresh_token_hash"])


def downgrade() -> None:
    op.drop_index("ix_lk_sessions_previous_refresh_hash", table_name="lk_sessions")
    op.drop_column("lk_sessions", "previous_refresh_token_expires_at")
    op.drop_column("lk_sessions", "previous_refresh_token_hash")
