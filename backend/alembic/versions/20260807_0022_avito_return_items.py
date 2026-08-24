"""add avito return items

Revision ID: 20260807_0022
Revises: 20260728_0021
Create Date: 2026-08-07 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260807_0022"
down_revision = "20260728_0021"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "avito_return_items",
        sa.Column("return_item_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("identity_key", sa.String(length=512), nullable=False),
        sa.Column("account_id", sa.String(length=128), nullable=True),
        sa.Column("account_name", sa.String(length=255), nullable=True),
        sa.Column("order_id", sa.String(length=128), nullable=False),
        sa.Column("marketplace_id", sa.String(length=128), nullable=True),
        sa.Column("item_id", sa.String(length=128), nullable=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("seller_article", sa.String(length=255), nullable=True),
        sa.Column("size", sa.String(length=64), nullable=True),
        sa.Column("color", sa.String(length=64), nullable=True),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=64), nullable=False),
        sa.Column("return_status", sa.String(length=128), nullable=True),
        sa.Column("source_updated_at", sa.String(length=64), nullable=True),
        sa.Column("last_payload", sa.JSON(), nullable=False),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["lk_organizations.organization_id"]),
        sa.PrimaryKeyConstraint("return_item_id"),
        sa.UniqueConstraint("organization_id", "identity_key", name="uq_avito_return_items_org_identity"),
    )
    op.create_index("ix_avito_return_items_organization_id", "avito_return_items", ["organization_id"])


def downgrade() -> None:
    op.drop_index("ix_avito_return_items_organization_id", table_name="avito_return_items")
    op.drop_table("avito_return_items")
