"""account and token health tables

Revision ID: 20260526_0004
Revises: 20260526_0003
Create Date: 2026-05-26
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260526_0004"
down_revision = "20260526_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "wb_accounts",
        sa.Column("account_id", sa.String(length=128), nullable=False),
        sa.Column("source_status", sa.String(length=16), nullable=False),
        sa.Column("auth_state", sa.String(length=32), nullable=False),
        sa.Column("blocker_ids", sa.JSON(), nullable=False),
        sa.Column("next_actions", sa.JSON(), nullable=False),
        sa.Column("last_checked_scenario", sa.String(length=32), nullable=False),
        sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("account_id"),
    )

    op.create_table(
        "wb_account_capabilities",
        sa.Column("capability_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("account_id", sa.String(length=128), nullable=False),
        sa.Column("capability", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("missing_scopes", sa.JSON(), nullable=False),
        sa.Column("blocker_ids", sa.JSON(), nullable=False),
        sa.Column("evidence_ref", sa.Text(), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["account_id"], ["wb_accounts.account_id"]),
        sa.PrimaryKeyConstraint("capability_id"),
    )
    op.create_index("ix_wb_account_capabilities_account", "wb_account_capabilities", ["account_id"])
    op.create_index("ix_wb_account_capabilities_capability", "wb_account_capabilities", ["capability"])

    op.create_table(
        "wb_account_missing_scopes",
        sa.Column("scope_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("account_id", sa.String(length=128), nullable=False),
        sa.Column("capability", sa.String(length=64), nullable=False),
        sa.Column("scope", sa.String(length=128), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["account_id"], ["wb_accounts.account_id"]),
        sa.PrimaryKeyConstraint("scope_id"),
    )
    op.create_index("ix_wb_account_missing_scopes_account", "wb_account_missing_scopes", ["account_id"])
    op.create_index("ix_wb_account_missing_scopes_scope", "wb_account_missing_scopes", ["scope"])

    op.create_table(
        "wb_token_health_checks",
        sa.Column("check_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("account_id", sa.String(length=128), nullable=False),
        sa.Column("scenario", sa.String(length=32), nullable=False),
        sa.Column("source_status", sa.String(length=16), nullable=False),
        sa.Column("auth_state", sa.String(length=32), nullable=False),
        sa.Column("blocker_ids", sa.JSON(), nullable=False),
        sa.Column("next_actions", sa.JSON(), nullable=False),
        sa.Column("capability_snapshot", sa.JSON(), nullable=False),
        sa.Column("checked_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["account_id"], ["wb_accounts.account_id"]),
        sa.PrimaryKeyConstraint("check_id"),
    )
    op.create_index("ix_wb_token_health_checks_account", "wb_token_health_checks", ["account_id"])
    op.create_index("ix_wb_token_health_checks_checked_at", "wb_token_health_checks", ["checked_at"])


def downgrade() -> None:
    op.drop_index("ix_wb_token_health_checks_checked_at", table_name="wb_token_health_checks")
    op.drop_index("ix_wb_token_health_checks_account", table_name="wb_token_health_checks")
    op.drop_table("wb_token_health_checks")

    op.drop_index("ix_wb_account_missing_scopes_scope", table_name="wb_account_missing_scopes")
    op.drop_index("ix_wb_account_missing_scopes_account", table_name="wb_account_missing_scopes")
    op.drop_table("wb_account_missing_scopes")

    op.drop_index("ix_wb_account_capabilities_capability", table_name="wb_account_capabilities")
    op.drop_index("ix_wb_account_capabilities_account", table_name="wb_account_capabilities")
    op.drop_table("wb_account_capabilities")

    op.drop_table("wb_accounts")
