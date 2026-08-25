"""add inventory recipes for production material consumption

Revision ID: 20260817_0027
Revises: 20260817_0026
Create Date: 2026-08-17 16:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260817_0027"
down_revision = "20260817_0026"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "inventory_recipes",
        sa.Column("recipe_id", sa.String(32), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("lk_organizations.organization_id"), nullable=False),
        sa.Column("product_barcode", sa.String(64), nullable=True),
        sa.Column("seller_sku", sa.String(128), nullable=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("organization_id", "product_barcode", name="uq_inventory_recipes_org_barcode"),
        sa.UniqueConstraint("organization_id", "seller_sku", name="uq_inventory_recipes_org_sku"),
    )
    op.create_index("ix_inventory_recipes_org_active", "inventory_recipes", ["organization_id", "active"])
    op.create_table(
        "inventory_recipe_components",
        sa.Column("component_id", sa.String(32), primary_key=True),
        sa.Column("recipe_id", sa.String(32), sa.ForeignKey("inventory_recipes.recipe_id", ondelete="CASCADE"), nullable=False),
        sa.Column("warehouse_id", sa.String(32), sa.ForeignKey("inventory_warehouses.warehouse_id"), nullable=False),
        sa.Column("item_id", sa.String(32), sa.ForeignKey("inventory_items.item_id"), nullable=False),
        sa.Column("quantity_per_unit", sa.Numeric(18, 3), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("recipe_id", "warehouse_id", "item_id", name="uq_inventory_recipe_component"),
    )


def downgrade() -> None:
    op.drop_table("inventory_recipe_components")
    op.drop_table("inventory_recipes")
