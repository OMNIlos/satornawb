from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "20260716_0015"
down_revision = "20260713_0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "wb_repricer_source_cache",
        "source_key",
        existing_type=sa.String(length=64),
        type_=sa.String(length=255),
        existing_nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "wb_repricer_source_cache",
        "source_key",
        existing_type=sa.String(length=255),
        type_=sa.String(length=64),
        existing_nullable=False,
    )
