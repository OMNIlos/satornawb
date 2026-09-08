"""add ordered sales document numbers and durable batch requests

Revision ID: 20260830_0044
Revises: 20260829_0043
"""

import sqlalchemy as sa
from alembic import op

revision = "20260830_0044"
down_revision = "20260829_0043"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "sales_document_sequences",
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("last_number", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["lk_organizations.organization_id"]
        ),
        sa.PrimaryKeyConstraint("organization_id"),
    )
    op.create_table(
        "sales_batch_requests",
        sa.Column("batch_request_id", sa.String(length=32), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("request_id", sa.String(length=64), nullable=False),
        sa.Column("payload_sha256", sa.String(length=64), nullable=False),
        sa.Column("external_reference", sa.String(length=128), nullable=False),
        sa.Column("sale_ids_json", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["lk_organizations.organization_id"]
        ),
        sa.PrimaryKeyConstraint("batch_request_id"),
        sa.UniqueConstraint(
            "organization_id",
            "request_id",
            name="uq_sales_batch_requests_org_request",
        ),
    )
    op.create_index(
        "ix_sales_batch_requests_org_created",
        "sales_batch_requests",
        ["organization_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_sales_batch_requests_org_created", table_name="sales_batch_requests"
    )
    op.drop_table("sales_batch_requests")
    op.drop_table("sales_document_sequences")
