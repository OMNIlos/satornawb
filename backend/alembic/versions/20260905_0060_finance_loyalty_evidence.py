"""store canonical WB loyalty money evidence

Revision ID: 20260905_0060
Revises: 20260904_0059
Create Date: 2026-09-05
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "20260905_0060"
down_revision = "20260904_0059"
branch_labels = None
depends_on = None

TABLES = (
    "wb_finance_operations",
    "wb_finance_sync_run_sku_pnl_rollups",
    "wb_finance_sync_run_sku_daily_pnl_rollups",
)
COLUMNS = (
    "cashback_amount_kopecks",
    "cashback_discount_kopecks",
    "cashback_commission_change_kopecks",
)


def upgrade() -> None:
    for table in TABLES:
        for column in COLUMNS:
            op.add_column(table, sa.Column(column, sa.BigInteger(), nullable=True))


def downgrade() -> None:
    for table in TABLES:
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
    evidence = " OR ".join(
        f"EXISTS (SELECT 1 FROM {table} "
        f"WHERE {' OR '.join(f'{column} IS NOT NULL' for column in COLUMNS)} LIMIT 1)"
        for table in TABLES
    )
    op.execute(
        sa.text(f"""
            DO $$
            BEGIN
                IF {evidence} THEN
                    RAISE EXCEPTION
                        'cannot downgrade while canonical loyalty evidence exists';
                END IF;
            END
            $$
            """)
    )
    for table in TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
    for table in reversed(TABLES):
        for column in reversed(COLUMNS):
            op.drop_column(table, column)
