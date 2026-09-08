"""sales channels, blank sales, customer debt and payment method

Revision ID: 20260821_0037
Revises: 20260821_0036
"""

import sqlalchemy as sa

from alembic import op

revision = "20260821_0037"
down_revision = "20260821_0036"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "sales_channels",
        sa.Column("channel_id", sa.String(length=32), primary_key=True),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["organization_id"], ["lk_organizations.organization_id"]),
        sa.UniqueConstraint("organization_id", "code", name="uq_sales_channels_org_code"),
    )
    op.create_index("ix_sales_channels_org_active", "sales_channels", ["organization_id", "active", "name"])
    op.execute(sa.text("""
        INSERT INTO sales_channels (channel_id, organization_id, code, name, active)
        SELECT md5(org.organization_id::text || ':' || channel.code),
               org.organization_id, channel.code, channel.name, true
        FROM lk_organizations AS org
        CROSS JOIN (VALUES
            ('wb', 'Wildberries'),
            ('avito', 'Авито'),
            ('direct', 'Прямая продажа'),
            ('other', 'Другой')
        ) AS channel(code, name)
        ON CONFLICT (organization_id, code) DO NOTHING
    """))

    op.drop_constraint("ck_sales_records_channel", "sales_records", type_="check")
    op.alter_column("sales_records", "channel", type_=sa.String(length=32), existing_type=sa.String(length=16), existing_nullable=False)
    op.add_column("sales_records", sa.Column("inventory_item_id", sa.String(length=32), nullable=True))
    op.add_column("sales_records", sa.Column("warehouse_id", sa.String(length=32), nullable=True))
    op.add_column("sales_records", sa.Column("external_reference", sa.String(length=128), nullable=True))
    op.add_column("sales_records", sa.Column("source_file_name", sa.String(length=255), nullable=True))
    op.add_column("sales_records", sa.Column("inventory_unit_cost_kopecks", sa.BigInteger(), nullable=False, server_default="0"))
    op.create_foreign_key("fk_sales_records_inventory_item", "sales_records", "inventory_items", ["inventory_item_id"], ["item_id"])
    op.create_foreign_key("fk_sales_records_warehouse", "sales_records", "inventory_warehouses", ["warehouse_id"], ["warehouse_id"])
    op.create_index("ix_sales_records_org_reference", "sales_records", ["organization_id", "external_reference"])

    op.create_table(
        "sales_import_batches",
        sa.Column("batch_id", sa.String(length=32), primary_key=True),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("external_reference", sa.String(length=128), nullable=False),
        sa.Column("payload_sha256", sa.String(length=64), nullable=False),
        sa.Column("file_name", sa.String(length=255), nullable=False),
        sa.Column("file_sha256", sa.String(length=64), nullable=False),
        sa.Column("client_id", sa.String(length=32), nullable=False),
        sa.Column("channel", sa.String(length=32), nullable=False),
        sa.Column("warehouse_id", sa.String(length=32), nullable=False),
        sa.Column("rows_count", sa.Integer(), nullable=False),
        sa.Column("make_new_units", sa.Integer(), nullable=False),
        sa.Column("return_ready_units", sa.Integer(), nullable=False),
        sa.Column("total_kopecks", sa.BigInteger(), nullable=False),
        sa.Column("lines_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["organization_id"], ["lk_organizations.organization_id"]),
        sa.ForeignKeyConstraint(
            ["organization_id", "client_id"],
            ["client_accounts.organization_id", "client_accounts.client_id"],
            name="fk_sales_import_batches_org_client",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "channel"],
            ["sales_channels.organization_id", "sales_channels.code"],
            name="fk_sales_import_batches_org_channel",
        ),
        sa.ForeignKeyConstraint(["warehouse_id"], ["inventory_warehouses.warehouse_id"]),
        sa.UniqueConstraint("organization_id", "external_reference", name="uq_sales_import_batches_reference"),
    )
    op.create_index("ix_sales_import_batches_org_created", "sales_import_batches", ["organization_id", "created_at"])

    op.drop_constraint("ck_client_sale_tariffs_channel", "client_sale_tariffs", type_="check")
    op.alter_column("client_sale_tariffs", "channel", type_=sa.String(length=32), existing_type=sa.String(length=16), existing_nullable=False)
    op.drop_constraint("ck_client_debt_ledger_semantics", "client_debt_ledger_entries", type_="check")
    op.create_check_constraint(
        "ck_client_debt_ledger_semantics",
        "client_debt_ledger_entries",
        "(entry_type = 'charge' AND source_type IN ('billing', 'sale') AND delta_kopecks > 0) "
        "OR (entry_type = 'payment' AND source_type = 'payment' AND delta_kopecks < 0) "
        "OR (entry_type = 'adjustment' AND source_type = 'sale_cancel' AND delta_kopecks < 0)",
    )
    op.add_column("client_payments", sa.Column("payment_method", sa.String(length=8), nullable=False, server_default="bank"))
    op.create_check_constraint("ck_client_payments_method", "client_payments", "payment_method IN ('bank', 'cash')")


def downgrade() -> None:
    op.drop_constraint("ck_client_payments_method", "client_payments", type_="check")
    op.drop_column("client_payments", "payment_method")
    op.drop_constraint("ck_client_debt_ledger_semantics", "client_debt_ledger_entries", type_="check")
    op.create_check_constraint(
        "ck_client_debt_ledger_semantics", "client_debt_ledger_entries",
        "(entry_type = 'charge' AND source_type = 'billing' AND delta_kopecks > 0) OR "
        "(entry_type = 'payment' AND source_type = 'payment' AND delta_kopecks < 0)",
    )
    op.create_check_constraint("ck_client_sale_tariffs_channel", "client_sale_tariffs", "channel IN ('wb', 'avito', 'other')")
    op.alter_column("client_sale_tariffs", "channel", type_=sa.String(length=16), existing_type=sa.String(length=32), existing_nullable=False)
    op.drop_index("ix_sales_import_batches_org_created", table_name="sales_import_batches")
    op.drop_table("sales_import_batches")
    op.drop_index("ix_sales_records_org_reference", table_name="sales_records")
    op.drop_constraint("fk_sales_records_warehouse", "sales_records", type_="foreignkey")
    op.drop_constraint("fk_sales_records_inventory_item", "sales_records", type_="foreignkey")
    for column in ("inventory_unit_cost_kopecks", "source_file_name", "external_reference", "warehouse_id", "inventory_item_id"):
        op.drop_column("sales_records", column)
    op.create_check_constraint("ck_sales_records_channel", "sales_records", "channel IN ('wb', 'avito', 'direct', 'other')")
    op.alter_column("sales_records", "channel", type_=sa.String(length=16), existing_type=sa.String(length=32), existing_nullable=False)
    op.drop_index("ix_sales_channels_org_active", table_name="sales_channels")
    op.drop_table("sales_channels")
