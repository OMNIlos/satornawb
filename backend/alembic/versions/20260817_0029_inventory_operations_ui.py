"""inventory categories, equipment quantity and manual intake support

Revision ID: 20260817_0029
Revises: 20260817_0028
Create Date: 2026-08-17 20:10:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "20260817_0029"
down_revision = "20260817_0028"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("inventory_items", sa.Column("category", sa.String(128), nullable=True))
    op.add_column("inventory_equipment_assets", sa.Column("quantity", sa.Integer(), nullable=False, server_default="1"))
    op.drop_constraint("uq_inventory_equipment_org_serial", "inventory_equipment_assets", type_="unique")
    op.drop_column("inventory_equipment_assets", "serial_number")


def downgrade() -> None:
    op.add_column("inventory_equipment_assets", sa.Column("serial_number", sa.String(128), nullable=True))
    op.create_unique_constraint("uq_inventory_equipment_org_serial", "inventory_equipment_assets", ["organization_id", "serial_number"])
    op.drop_column("inventory_equipment_assets", "quantity")
    op.drop_column("inventory_items", "category")
