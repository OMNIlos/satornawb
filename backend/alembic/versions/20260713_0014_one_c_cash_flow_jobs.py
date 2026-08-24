from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "20260713_0014"
down_revision = "20260712_0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "one_c_cash_flow_jobs",
        sa.Column("job_id", sa.String(length=32), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("job_type", sa.String(length=32), nullable=False),
        sa.Column("period_from", sa.Date(), nullable=False),
        sa.Column("period_to", sa.Date(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("requested_by", sa.String(length=128), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("rows_payload", sa.JSON(), nullable=False),
        sa.Column("balances_payload", sa.JSON(), nullable=False),
        sa.Column("raw_result", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("job_id"),
        sa.UniqueConstraint("organization_id", "period_from", "period_to", name="uq_one_c_cash_flow_job_period"),
    )
    op.create_index("ix_one_c_cash_flow_jobs_organization_id", "one_c_cash_flow_jobs", ["organization_id"])
    op.create_index("ix_one_c_cash_flow_jobs_status_created", "one_c_cash_flow_jobs", ["status", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_one_c_cash_flow_jobs_status_created", table_name="one_c_cash_flow_jobs")
    op.drop_index("ix_one_c_cash_flow_jobs_organization_id", table_name="one_c_cash_flow_jobs")
    op.drop_table("one_c_cash_flow_jobs")
