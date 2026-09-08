"""assign users to sales channels

Revision ID: 20260902_0051
Revises: 20260902_0050
"""

import sqlalchemy as sa

from alembic import op

revision = "20260902_0051"
down_revision = "20260902_0050"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "sales_user_channels",
        sa.Column("assignment_id", sa.String(length=32), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("channel", sa.String(length=32), nullable=False),
        sa.Column("created_by_user_id", sa.String(length=64), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["lk_organizations.organization_id"]
        ),
        sa.ForeignKeyConstraint(["user_id"], ["lk_users.user_id"]),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["lk_users.user_id"]),
        sa.ForeignKeyConstraint(
            ["organization_id", "channel"],
            ["sales_channels.organization_id", "sales_channels.code"],
            name="fk_sales_user_channels_org_channel",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("assignment_id"),
        sa.UniqueConstraint(
            "organization_id",
            "user_id",
            "channel",
            name="uq_sales_user_channels_org_user_channel",
        ),
    )
    op.create_index(
        "ix_sales_user_channels_org_user",
        "sales_user_channels",
        ["organization_id", "user_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_sales_user_channels_org_user", table_name="sales_user_channels")
    op.drop_table("sales_user_channels")
