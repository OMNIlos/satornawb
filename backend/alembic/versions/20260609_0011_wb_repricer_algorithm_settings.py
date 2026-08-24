from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "20260609_0011"
down_revision = "20260605_0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "wb_repricer_algorithm_settings",
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("settings_payload", sa.JSON(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["lk_organizations.organization_id"]),
        sa.PrimaryKeyConstraint("organization_id"),
    )


def downgrade() -> None:
    op.drop_table("wb_repricer_algorithm_settings")
