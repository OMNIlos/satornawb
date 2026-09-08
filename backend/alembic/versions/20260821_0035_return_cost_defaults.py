"""add per-client return cost defaults

Revision ID: 20260821_0035
Revises: 20260820_0034
"""

import sqlalchemy as sa

from alembic import op

revision = "20260821_0035"
down_revision = "20260820_0034"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "client_accounts",
        sa.Column(
            "return_cost_tshirt_kopecks",
            sa.BigInteger(),
            nullable=False,
            server_default="25000",
        ),
    )
    op.add_column(
        "client_accounts",
        sa.Column(
            "return_cost_longsleeve_kopecks",
            sa.BigInteger(),
            nullable=False,
            server_default="35000",
        ),
    )
    op.add_column(
        "client_accounts",
        sa.Column(
            "return_cost_hoodie_kopecks",
            sa.BigInteger(),
            nullable=False,
            server_default="90000",
        ),
    )
    op.create_check_constraint(
        "ck_client_accounts_return_costs_nonnegative",
        "client_accounts",
        "return_cost_tshirt_kopecks >= 0 AND "
        "return_cost_longsleeve_kopecks >= 0 AND "
        "return_cost_hoodie_kopecks >= 0",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_client_accounts_return_costs_nonnegative",
        "client_accounts",
        type_="check",
    )
    op.drop_column("client_accounts", "return_cost_hoodie_kopecks")
    op.drop_column("client_accounts", "return_cost_longsleeve_kopecks")
    op.drop_column("client_accounts", "return_cost_tshirt_kopecks")
