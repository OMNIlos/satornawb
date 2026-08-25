"""add inventory catalogs, item attributes, aliases and reversible movements

Revision ID: 20260817_0028
Revises: 20260817_0027
Create Date: 2026-08-17 18:30:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260817_0028"
down_revision = "20260817_0027"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("inventory_items", sa.Column("product_type", sa.String(128), nullable=True))
    op.add_column("inventory_items", sa.Column("color", sa.String(128), nullable=True))
    op.add_column("inventory_items", sa.Column("size", sa.String(32), nullable=True))
    op.add_column("inventory_items", sa.Column("reference_price_kopecks", sa.BigInteger(), nullable=True))
    op.create_table(
        "inventory_attribute_values",
        sa.Column("value_id", sa.String(32), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("lk_organizations.organization_id"), nullable=False),
        sa.Column("attribute_type", sa.String(32), nullable=False),
        sa.Column("value", sa.String(128), nullable=False),
        sa.Column("normalized_value", sa.String(128), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("organization_id", "attribute_type", "normalized_value", name="uq_inventory_attribute_org_type_value"),
    )
    op.create_index("ix_inventory_attribute_org_type", "inventory_attribute_values", ["organization_id", "attribute_type", "active", "sort_order"])
    op.create_table(
        "inventory_item_aliases",
        sa.Column("alias_id", sa.String(32), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("lk_organizations.organization_id"), nullable=False),
        sa.Column("item_id", sa.String(32), sa.ForeignKey("inventory_items.item_id"), nullable=False),
        sa.Column("alias", sa.String(255), nullable=False),
        sa.Column("normalized_alias", sa.String(255), nullable=False),
        sa.Column("source", sa.String(32), nullable=False, server_default="manual"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("organization_id", "normalized_alias", name="uq_inventory_alias_org_normalized"),
    )
    op.create_index("ix_inventory_alias_org_item", "inventory_item_aliases", ["organization_id", "item_id", "active"])
    op.add_column("inventory_movements", sa.Column("reverses_movement_id", sa.String(32), nullable=True))
    op.add_column("inventory_movements", sa.Column("note", sa.Text(), nullable=True))
    op.create_foreign_key("fk_inventory_movement_reverses", "inventory_movements", "inventory_movements", ["reverses_movement_id"], ["movement_id"])
    op.create_unique_constraint("uq_inventory_movement_reverses", "inventory_movements", ["reverses_movement_id"])


def downgrade() -> None:
    op.drop_constraint("uq_inventory_movement_reverses", "inventory_movements", type_="unique")
    op.drop_constraint("fk_inventory_movement_reverses", "inventory_movements", type_="foreignkey")
    op.drop_column("inventory_movements", "note")
    op.drop_column("inventory_movements", "reverses_movement_id")
    op.drop_table("inventory_item_aliases")
    op.drop_table("inventory_attribute_values")
    op.drop_column("inventory_items", "reference_price_kopecks")
    op.drop_column("inventory_items", "size")
    op.drop_column("inventory_items", "color")
    op.drop_column("inventory_items", "product_type")
