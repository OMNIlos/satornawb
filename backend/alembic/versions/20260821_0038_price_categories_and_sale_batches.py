"""price categories and atomic multi-line sales

Revision ID: 20260821_0038
Revises: 20260821_0037
"""

import sqlalchemy as sa

from alembic import op

revision = "20260821_0038"
down_revision = "20260821_0037"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "client_price_categories",
        sa.Column("category_id", sa.String(length=32), primary_key=True),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["lk_organizations.organization_id"]
        ),
        sa.UniqueConstraint(
            "organization_id", "category_id", name="uq_client_price_categories_org_id"
        ),
        sa.UniqueConstraint(
            "organization_id", "name", name="uq_client_price_categories_org_name"
        ),
    )
    op.create_index(
        "ix_client_price_categories_org_active",
        "client_price_categories",
        ["organization_id", "active", "name"],
    )
    op.create_table(
        "client_price_category_items",
        sa.Column("price_id", sa.String(length=32), primary_key=True),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("category_id", sa.String(length=32), nullable=False),
        sa.Column("item_id", sa.String(length=32), nullable=False),
        sa.Column("channel", sa.String(length=32), nullable=False),
        sa.Column("price_kopecks", sa.BigInteger(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "price_kopecks >= 0", name="ck_client_price_category_items_nonnegative"
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "category_id"],
            [
                "client_price_categories.organization_id",
                "client_price_categories.category_id",
            ],
            name="fk_client_price_category_items_org_category",
        ),
        sa.ForeignKeyConstraint(["item_id"], ["inventory_items.item_id"]),
        sa.UniqueConstraint(
            "organization_id",
            "category_id",
            "item_id",
            "channel",
            name="uq_client_price_category_items_scope",
        ),
    )
    op.create_index(
        "ix_client_price_category_items_category",
        "client_price_category_items",
        ["organization_id", "category_id", "channel"],
    )
    op.add_column(
        "client_accounts",
        sa.Column("price_category_id", sa.String(length=32), nullable=True),
    )
    op.create_foreign_key(
        "fk_client_accounts_org_price_category",
        "client_accounts",
        "client_price_categories",
        ["organization_id", "price_category_id"],
        ["organization_id", "category_id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_client_accounts_org_price_category", "client_accounts", type_="foreignkey"
    )
    op.drop_column("client_accounts", "price_category_id")
    op.drop_index(
        "ix_client_price_category_items_category",
        table_name="client_price_category_items",
    )
    op.drop_table("client_price_category_items")
    op.drop_index(
        "ix_client_price_categories_org_active", table_name="client_price_categories"
    )
    op.drop_table("client_price_categories")
