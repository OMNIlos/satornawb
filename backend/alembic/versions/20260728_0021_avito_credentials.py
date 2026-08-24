"""add avito user credentials

Revision ID: 20260728_0021
Revises: 20260717_0020
Create Date: 2026-07-28 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260728_0021"
down_revision = "20260717_0020"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "lk_user_avito_credentials",
        sa.Column("credentials_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("client_id", sa.Text(), nullable=False),
        sa.Column("client_secret", sa.Text(), nullable=False),
        sa.Column("client_id_masked", sa.String(length=64), nullable=False),
        sa.Column("client_secret_masked", sa.String(length=64), nullable=False),
        sa.Column("cached_access_token", sa.Text(), nullable=True),
        sa.Column("access_token_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by_user_id", sa.String(), nullable=True),
        sa.Column("updated_by_user_id", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["lk_users.user_id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["lk_organizations.organization_id"]),
        sa.ForeignKeyConstraint(["updated_by_user_id"], ["lk_users.user_id"]),
        sa.ForeignKeyConstraint(["user_id"], ["lk_users.user_id"]),
        sa.PrimaryKeyConstraint("credentials_id"),
        sa.UniqueConstraint("user_id"),
    )


def downgrade() -> None:
    op.drop_table("lk_user_avito_credentials")
