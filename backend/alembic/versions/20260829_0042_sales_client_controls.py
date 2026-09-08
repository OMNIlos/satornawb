"""make return warehouse optional and add client INN

Revision ID: 20260829_0042
Revises: 20260827_0041
"""

import sqlalchemy as sa

from alembic import op

revision = "20260829_0042"
down_revision = "20260827_0041"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("client_accounts", sa.Column("inn", sa.String(12), nullable=True))
    op.alter_column(
        "client_accounts",
        "return_warehouse_id",
        existing_type=sa.String(32),
        nullable=True,
    )
    op.create_index(
        "ix_client_accounts_org_inn",
        "client_accounts",
        ["organization_id", "inn"],
    )


def downgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
          IF EXISTS (SELECT 1 FROM client_accounts WHERE return_warehouse_id IS NULL) THEN
            RAISE EXCEPTION 'cannot downgrade while clients without return warehouses exist';
          END IF;
        END $$
        """
    )
    op.drop_index("ix_client_accounts_org_inn", table_name="client_accounts")
    op.alter_column(
        "client_accounts",
        "return_warehouse_id",
        existing_type=sa.String(32),
        nullable=False,
    )
    op.drop_column("client_accounts", "inn")
