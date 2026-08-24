from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "20260604_0008"
down_revision = "20260529_0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "wb_repricer_goods_cache",
        sa.Column("cache_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("page_offset", sa.Integer(), nullable=False),
        sa.Column("page_limit", sa.Integer(), nullable=False),
        sa.Column("goods_payload", sa.JSON(), nullable=False),
        sa.Column("wb_request_id", sa.String(length=128), nullable=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["lk_organizations.organization_id"]),
        sa.PrimaryKeyConstraint("cache_id"),
        sa.UniqueConstraint("organization_id", "page_offset", "page_limit", name="uq_wb_repricer_goods_cache_page"),
    )
    op.create_index("ix_wb_repricer_goods_cache_org", "wb_repricer_goods_cache", ["organization_id"])


def downgrade() -> None:
    op.drop_index("ix_wb_repricer_goods_cache_org", table_name="wb_repricer_goods_cache")
    op.drop_table("wb_repricer_goods_cache")
