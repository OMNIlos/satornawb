"""add sales records

Revision ID: 20260820_0034
Revises: 20260819_0033
"""

import sqlalchemy as sa

from alembic import op

revision = "20260820_0034"
down_revision = "20260819_0033"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "sales_records",
        sa.Column("sale_id", sa.String(length=32), primary_key=True),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("client_id", sa.String(length=32), nullable=False),
        sa.Column("channel", sa.String(length=16), nullable=False),
        sa.Column("sale_type", sa.String(length=16), nullable=False),
        sa.Column("description", sa.String(length=255), nullable=False),
        sa.Column("equipment_asset_id", sa.String(length=32), nullable=True),
        sa.Column("equipment_previous_status", sa.String(length=16), nullable=True),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("unit_price_kopecks", sa.BigInteger(), nullable=False),
        sa.Column("total_kopecks", sa.BigInteger(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("sold_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by_user_id", sa.String(length=32), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["lk_organizations.organization_id"]
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "client_id"],
            ["client_accounts.organization_id", "client_accounts.client_id"],
            name="fk_sales_records_org_client",
        ),
        sa.ForeignKeyConstraint(
            ["equipment_asset_id"], ["inventory_equipment_assets.asset_id"]
        ),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["lk_users.user_id"]),
        sa.CheckConstraint(
            "channel IN ('wb', 'avito', 'direct', 'other')",
            name="ck_sales_records_channel",
        ),
        sa.CheckConstraint(
            "sale_type IN ('order', 'equipment', 'service')",
            name="ck_sales_records_type",
        ),
        sa.CheckConstraint(
            "status IN ('posted', 'cancelled')", name="ck_sales_records_status"
        ),
        sa.CheckConstraint("quantity > 0", name="ck_sales_records_quantity"),
        sa.CheckConstraint(
            "unit_price_kopecks >= 0 AND total_kopecks >= 0",
            name="ck_sales_records_amount",
        ),
    )
    op.create_index(
        "ix_sales_records_org_date",
        "sales_records",
        ["organization_id", "sold_at", "sale_id"],
    )
    op.create_index(
        "ix_sales_records_org_client",
        "sales_records",
        ["organization_id", "client_id", "status"],
    )


def downgrade() -> None:
    op.drop_index("ix_sales_records_org_client", table_name="sales_records")
    op.drop_index("ix_sales_records_org_date", table_name="sales_records")
    op.drop_table("sales_records")
