"""user-level wb token onboarding storage

Revision ID: 20260529_0007
Revises: 20260529_0006
Create Date: 2026-05-29
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260529_0007"
down_revision = "20260529_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "lk_user_wb_tokens",
        sa.Column("token_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("wb_token", sa.Text(), nullable=False),
        sa.Column("token_masked", sa.String(length=32), nullable=False),
        sa.Column("created_by_user_id", sa.String(length=64), nullable=True),
        sa.Column("updated_by_user_id", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["lk_organizations.organization_id"]),
        sa.ForeignKeyConstraint(["user_id"], ["lk_users.user_id"]),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["lk_users.user_id"]),
        sa.ForeignKeyConstraint(["updated_by_user_id"], ["lk_users.user_id"]),
        sa.PrimaryKeyConstraint("token_id"),
        sa.UniqueConstraint("user_id"),
    )
    op.create_index("ix_lk_user_wb_tokens_org_user", "lk_user_wb_tokens", ["organization_id", "user_id"])


def downgrade() -> None:
    op.drop_index("ix_lk_user_wb_tokens_org_user", table_name="lk_user_wb_tokens")
    op.drop_table("lk_user_wb_tokens")
