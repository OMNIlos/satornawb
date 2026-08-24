from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "20260716_0016"
down_revision = "20260716_0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "wb_report_rule_profiles",
        sa.Column("profile_id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("lk_organizations.organization_id"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("preset", sa.String(length=32), nullable=False),
        sa.Column("config_json", sa.JSON(), nullable=False),
        sa.Column("created_by_user_id", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.UniqueConstraint("organization_id", "version", name="uq_wb_report_rule_profile_org_version"),
    )
    op.create_index(
        "uq_wb_report_rule_profile_active_org",
        "wb_report_rule_profiles",
        ["organization_id"],
        unique=True,
        postgresql_where=sa.text("is_active"),
        sqlite_where=sa.text("is_active = 1"),
    )


def downgrade() -> None:
    op.drop_index("uq_wb_report_rule_profile_active_org", table_name="wb_report_rule_profiles")
    op.drop_table("wb_report_rule_profiles")
