"""add warehouse stocktakes

Revision ID: 20260818_0031
Revises: 20260818_0030
Create Date: 2026-08-18 12:30:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "20260818_0031"
down_revision = "20260818_0030"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("inventory_lots", "receipt_line_id", existing_type=sa.String(32), nullable=True)
    op.create_table(
        "inventory_stocktakes",
        sa.Column("stocktake_id", sa.String(32), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("lk_organizations.organization_id"), nullable=False),
        sa.Column("warehouse_id", sa.String(32), sa.ForeignKey("inventory_warehouses.warehouse_id"), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="draft"),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_by_user_id", sa.String(64), sa.ForeignKey("lk_users.user_id"), nullable=True),
        sa.Column("posted_by_user_id", sa.String(64), sa.ForeignKey("lk_users.user_id"), nullable=True),
        sa.Column("posted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_inventory_stocktakes_org_status", "inventory_stocktakes", ["organization_id", "status", "created_at"])
    op.create_table(
        "inventory_stocktake_lines",
        sa.Column("line_id", sa.String(32), primary_key=True),
        sa.Column("stocktake_id", sa.String(32), sa.ForeignKey("inventory_stocktakes.stocktake_id"), nullable=False),
        sa.Column("item_id", sa.String(32), sa.ForeignKey("inventory_items.item_id"), nullable=False),
        sa.Column("system_quantity", sa.Numeric(18, 3), nullable=False),
        sa.Column("actual_quantity", sa.Numeric(18, 3), nullable=True),
        sa.Column("variance_quantity", sa.Numeric(18, 3), nullable=True),
        sa.Column("unit_cost_kopecks", sa.BigInteger(), nullable=False, server_default="0"),
        sa.UniqueConstraint("stocktake_id", "item_id", name="uq_inventory_stocktake_item"),
    )


def downgrade() -> None:
    op.drop_table("inventory_stocktake_lines")
    op.drop_index("ix_inventory_stocktakes_org_status", table_name="inventory_stocktakes")
    op.drop_table("inventory_stocktakes")
    op.alter_column("inventory_lots", "receipt_line_id", existing_type=sa.String(32), nullable=False)
