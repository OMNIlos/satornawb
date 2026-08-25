"""add inventory, equipment, UPD receipts and idempotent FIFO consumption

Revision ID: 20260817_0026
Revises: 20260817_0025
Create Date: 2026-08-17 12:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260817_0026"
down_revision = "20260817_0025"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "inventory_warehouses",
        sa.Column("warehouse_id", sa.String(32), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("lk_organizations.organization_id"), nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("organization_id", "name", name="uq_inventory_warehouses_org_name"),
    )
    op.create_table(
        "inventory_items",
        sa.Column("item_id", sa.String(32), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("lk_organizations.organization_id"), nullable=False),
        sa.Column("sku", sa.String(128), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("item_type", sa.String(32), nullable=False),
        sa.Column("unit", sa.String(16), nullable=False),
        sa.Column("barcode", sa.String(64), nullable=True),
        sa.Column("min_quantity", sa.Numeric(18, 3), nullable=False, server_default="0"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("organization_id", "sku", name="uq_inventory_items_org_sku"),
        sa.UniqueConstraint("organization_id", "barcode", name="uq_inventory_items_org_barcode"),
    )
    op.create_index("ix_inventory_items_org_type", "inventory_items", ["organization_id", "item_type", "active"])
    op.create_table(
        "inventory_supplier_item_mappings",
        sa.Column("mapping_id", sa.String(32), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("lk_organizations.organization_id"), nullable=False),
        sa.Column("supplier_counterparty_id", sa.String(32), sa.ForeignKey("finance_counterparties.counterparty_id"), nullable=False),
        sa.Column("supplier_item_code", sa.String(128), nullable=False),
        sa.Column("supplier_item_name", sa.String(255), nullable=True),
        sa.Column("item_id", sa.String(32), sa.ForeignKey("inventory_items.item_id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("organization_id", "supplier_counterparty_id", "supplier_item_code", name="uq_inventory_supplier_mapping_code"),
    )
    op.create_table(
        "inventory_receipts",
        sa.Column("receipt_id", sa.String(32), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("lk_organizations.organization_id"), nullable=False),
        sa.Column("warehouse_id", sa.String(32), sa.ForeignKey("inventory_warehouses.warehouse_id"), nullable=False),
        sa.Column("supplier_counterparty_id", sa.String(32), sa.ForeignKey("finance_counterparties.counterparty_id"), nullable=False),
        sa.Column("source_format", sa.String(16), nullable=False),
        sa.Column("file_name", sa.String(255), nullable=False),
        sa.Column("file_sha256", sa.String(64), nullable=False),
        sa.Column("document_number", sa.String(128), nullable=True),
        sa.Column("document_date", sa.Date(), nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="draft"),
        sa.Column("total_kopecks", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("diagnostics", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("created_by_user_id", sa.String(64), sa.ForeignKey("lk_users.user_id"), nullable=True),
        sa.Column("posted_by_user_id", sa.String(64), sa.ForeignKey("lk_users.user_id"), nullable=True),
        sa.Column("posted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("organization_id", "file_sha256", name="uq_inventory_receipts_org_file"),
    )
    op.create_index("ix_inventory_receipts_org_status", "inventory_receipts", ["organization_id", "status", "created_at"])
    op.create_table(
        "inventory_receipt_lines",
        sa.Column("line_id", sa.String(32), primary_key=True),
        sa.Column("receipt_id", sa.String(32), sa.ForeignKey("inventory_receipts.receipt_id"), nullable=False),
        sa.Column("line_number", sa.Integer(), nullable=False),
        sa.Column("supplier_item_code", sa.String(128), nullable=True),
        sa.Column("supplier_item_name", sa.String(255), nullable=False),
        sa.Column("barcode", sa.String(64), nullable=True),
        sa.Column("unit", sa.String(16), nullable=False),
        sa.Column("quantity", sa.Numeric(18, 3), nullable=False),
        sa.Column("unit_cost_kopecks", sa.BigInteger(), nullable=False),
        sa.Column("total_kopecks", sa.BigInteger(), nullable=False),
        sa.Column("vat_rate", sa.String(16), nullable=True),
        sa.Column("item_id", sa.String(32), sa.ForeignKey("inventory_items.item_id"), nullable=True),
        sa.Column("match_state", sa.String(16), nullable=False, server_default="unmatched"),
        sa.Column("source_row", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.UniqueConstraint("receipt_id", "line_number", name="uq_inventory_receipt_line_number"),
    )
    op.create_table(
        "inventory_lots",
        sa.Column("lot_id", sa.String(32), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("lk_organizations.organization_id"), nullable=False),
        sa.Column("warehouse_id", sa.String(32), sa.ForeignKey("inventory_warehouses.warehouse_id"), nullable=False),
        sa.Column("item_id", sa.String(32), sa.ForeignKey("inventory_items.item_id"), nullable=False),
        sa.Column("receipt_line_id", sa.String(32), sa.ForeignKey("inventory_receipt_lines.line_id"), nullable=False, unique=True),
        sa.Column("received_quantity", sa.Numeric(18, 3), nullable=False),
        sa.Column("remaining_quantity", sa.Numeric(18, 3), nullable=False),
        sa.Column("unit_cost_kopecks", sa.BigInteger(), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_inventory_lots_fifo", "inventory_lots", ["organization_id", "warehouse_id", "item_id", "received_at"])
    op.create_table(
        "inventory_consumptions",
        sa.Column("consumption_id", sa.String(32), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("lk_organizations.organization_id"), nullable=False),
        sa.Column("external_reference", sa.String(128), nullable=False),
        sa.Column("payload_sha256", sa.String(64), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("total_cost_kopecks", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("created_by_user_id", sa.String(64), sa.ForeignKey("lk_users.user_id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("organization_id", "external_reference", name="uq_inventory_consumptions_org_reference"),
    )
    op.create_table(
        "inventory_movements",
        sa.Column("movement_id", sa.String(32), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("lk_organizations.organization_id"), nullable=False),
        sa.Column("warehouse_id", sa.String(32), sa.ForeignKey("inventory_warehouses.warehouse_id"), nullable=False),
        sa.Column("item_id", sa.String(32), sa.ForeignKey("inventory_items.item_id"), nullable=False),
        sa.Column("lot_id", sa.String(32), sa.ForeignKey("inventory_lots.lot_id"), nullable=False),
        sa.Column("movement_type", sa.String(16), nullable=False),
        sa.Column("quantity", sa.Numeric(18, 3), nullable=False),
        sa.Column("unit_cost_kopecks", sa.BigInteger(), nullable=False),
        sa.Column("source_type", sa.String(32), nullable=False),
        sa.Column("source_id", sa.String(128), nullable=False),
        sa.Column("created_by_user_id", sa.String(64), sa.ForeignKey("lk_users.user_id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_inventory_movements_org_item", "inventory_movements", ["organization_id", "item_id", "created_at"])
    op.create_table(
        "inventory_equipment_assets",
        sa.Column("asset_id", sa.String(32), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("lk_organizations.organization_id"), nullable=False),
        sa.Column("item_id", sa.String(32), sa.ForeignKey("inventory_items.item_id"), nullable=False),
        sa.Column("warehouse_id", sa.String(32), sa.ForeignKey("inventory_warehouses.warehouse_id"), nullable=False),
        sa.Column("supplier_counterparty_id", sa.String(32), sa.ForeignKey("finance_counterparties.counterparty_id"), nullable=True),
        sa.Column("serial_number", sa.String(128), nullable=True),
        sa.Column("purchase_date", sa.Date(), nullable=True),
        sa.Column("purchase_cost_kopecks", sa.BigInteger(), nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="in_stock"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("organization_id", "serial_number", name="uq_inventory_equipment_org_serial"),
    )


def downgrade() -> None:
    op.drop_table("inventory_equipment_assets")
    op.drop_table("inventory_movements")
    op.drop_table("inventory_consumptions")
    op.drop_table("inventory_lots")
    op.drop_table("inventory_receipt_lines")
    op.drop_table("inventory_receipts")
    op.drop_table("inventory_supplier_item_mappings")
    op.drop_table("inventory_items")
    op.drop_table("inventory_warehouses")
