"""product type prices for client price categories

Revision ID: 20260822_0039
Revises: 20260821_0038
"""

import sqlalchemy as sa

from alembic import op

revision = "20260822_0039"
down_revision = "20260821_0038"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "client_price_category_products",
        sa.Column("price_id", sa.String(length=32), primary_key=True),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("category_id", sa.String(length=32), nullable=False),
        sa.Column("product_type", sa.String(length=128), nullable=False),
        sa.Column("channel", sa.String(length=32), nullable=False),
        sa.Column("price_kopecks", sa.BigInteger(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("price_kopecks >= 0", name="ck_client_price_category_products_nonnegative"),
        sa.ForeignKeyConstraint(
            ["organization_id", "category_id"],
            ["client_price_categories.organization_id", "client_price_categories.category_id"],
            name="fk_client_price_category_products_org_category",
        ),
        sa.UniqueConstraint(
            "organization_id", "category_id", "product_type", "channel",
            name="uq_client_price_category_products_scope",
        ),
    )
    op.create_index(
        "ix_client_price_category_products_category",
        "client_price_category_products",
        ["organization_id", "category_id", "channel"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_client_price_category_products_category",
        table_name="client_price_category_products",
    )
    op.drop_table("client_price_category_products")
