"""add durable manifest billing prepare/finalize saga

Revision ID: 20260819_0033
Revises: 20260819_0032
Create Date: 2026-08-19 23:30:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "20260819_0033"
down_revision = "20260819_0032"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "client_billing_batches",
        sa.Column("batch_id", sa.String(32), primary_key=True),
        sa.Column(
            "organization_id",
            sa.Integer(),
            sa.ForeignKey("lk_organizations.organization_id"),
            nullable=False,
        ),
        sa.Column("external_reference", sa.String(128), nullable=False),
        sa.Column("request_sha256", sa.String(64), nullable=False),
        sa.Column("quote_sha256", sa.String(64), nullable=False),
        sa.Column("channel", sa.String(16), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="prepared"),
        sa.Column("make_new_units", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("return_ready_units", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("total_units", sa.BigInteger(), nullable=False),
        sa.Column("total_amount_kopecks", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("finalization_key", sa.String(128), nullable=True),
        sa.Column("final_outcome_sha256", sa.String(64), nullable=True),
        sa.Column("result_sha256", sa.String(64), nullable=True),
        sa.Column("result_status", sa.String(16), nullable=True),
        sa.Column("chz_outcome", sa.String(32), nullable=True),
        sa.Column("chz_resolved_units", sa.BigInteger(), nullable=True),
        sa.Column("chz_not_required_reason", sa.String(255), nullable=True),
        sa.Column(
            "created_by_user_id",
            sa.String(64),
            sa.ForeignKey("lk_users.user_id"),
            nullable=True,
        ),
        sa.Column(
            "finalized_by_user_id",
            sa.String(64),
            sa.ForeignKey("lk_users.user_id"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("finalized_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "channel IN ('wb', 'avito', 'other')",
            name="ck_client_billing_batches_channel",
        ),
        sa.CheckConstraint(
            "status IN ('prepared', 'posted')",
            name="ck_client_billing_batches_status",
        ),
        sa.CheckConstraint(
            "make_new_units >= 0 AND return_ready_units >= 0 AND total_units > 0",
            name="ck_client_billing_batches_units",
        ),
        sa.CheckConstraint(
            "total_amount_kopecks >= 0",
            name="ck_client_billing_batches_amount",
        ),
        sa.CheckConstraint(
            "chz_outcome IS NULL OR chz_outcome IN ('ALL_RESOLVED', 'NOT_REQUIRED')",
            name="ck_client_billing_batches_chz_outcome",
        ),
        sa.UniqueConstraint(
            "organization_id",
            "external_reference",
            name="uq_client_billing_batches_org_reference",
        ),
        sa.UniqueConstraint(
            "organization_id", "batch_id", name="uq_client_billing_batches_org_id"
        ),
        sa.UniqueConstraint(
            "organization_id",
            "finalization_key",
            name="uq_client_billing_batches_org_finalization",
        ),
    )
    op.create_index(
        "ix_client_billing_batches_org_status",
        "client_billing_batches",
        ["organization_id", "status", "created_at"],
    )

    op.create_table(
        "client_billing_batch_groups",
        sa.Column("group_id", sa.String(32), primary_key=True),
        sa.Column(
            "organization_id",
            sa.Integer(),
            sa.ForeignKey("lk_organizations.organization_id"),
            nullable=False,
        ),
        sa.Column("batch_id", sa.String(32), nullable=False),
        sa.Column("client_id", sa.String(32), nullable=False),
        sa.Column("billing_id", sa.String(32), nullable=True),
        sa.Column("make_new_units", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("return_ready_units", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("total_amount_kopecks", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "make_new_units >= 0 AND return_ready_units >= 0",
            name="ck_client_billing_batch_groups_units",
        ),
        sa.CheckConstraint(
            "total_amount_kopecks >= 0",
            name="ck_client_billing_batch_groups_amount",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "batch_id"],
            ["client_billing_batches.organization_id", "client_billing_batches.batch_id"],
            name="fk_client_billing_batch_groups_org_batch",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "client_id"],
            ["client_accounts.organization_id", "client_accounts.client_id"],
            name="fk_client_billing_batch_groups_org_client",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "billing_id"],
            ["client_billing_runs.organization_id", "client_billing_runs.billing_id"],
            name="fk_client_billing_batch_groups_org_billing",
        ),
        sa.UniqueConstraint(
            "organization_id",
            "batch_id",
            "group_id",
            name="uq_client_billing_batch_groups_org_id",
        ),
        sa.UniqueConstraint(
            "batch_id", "client_id", name="uq_client_billing_batch_groups_client"
        ),
    )
    op.create_index(
        "ix_client_billing_batch_groups_batch",
        "client_billing_batch_groups",
        ["batch_id", "client_id"],
    )

    op.create_table(
        "client_billing_batch_lines",
        sa.Column("line_id", sa.String(32), primary_key=True),
        sa.Column(
            "organization_id",
            sa.Integer(),
            sa.ForeignKey("lk_organizations.organization_id"),
            nullable=False,
        ),
        sa.Column("batch_id", sa.String(32), nullable=False),
        sa.Column("group_id", sa.String(32), nullable=False),
        sa.Column("client_id", sa.String(32), nullable=False),
        sa.Column("stable_line_key", sa.String(64), nullable=False),
        sa.Column("source_references", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column(
            "item_id",
            sa.String(32),
            sa.ForeignKey("inventory_items.item_id"),
            nullable=False,
        ),
        sa.Column("item_sku_snapshot", sa.String(128), nullable=False),
        sa.Column("item_name_snapshot", sa.String(255), nullable=False),
        sa.Column("execution_type", sa.String(16), nullable=False),
        sa.Column("quantity", sa.BigInteger(), nullable=False),
        sa.Column("unit_price_kopecks", sa.BigInteger(), nullable=False),
        sa.Column("amount_kopecks", sa.BigInteger(), nullable=False),
        sa.CheckConstraint(
            "quantity > 0", name="ck_client_billing_batch_lines_quantity"
        ),
        sa.CheckConstraint(
            "unit_price_kopecks >= 0 AND amount_kopecks >= 0",
            name="ck_client_billing_batch_lines_amount",
        ),
        sa.CheckConstraint(
            "execution_type IN ('MAKE_NEW', 'RETURN_READY')",
            name="ck_client_billing_batch_lines_execution_type",
        ),
        sa.CheckConstraint(
            "execution_type <> 'RETURN_READY' OR (unit_price_kopecks = 0 AND amount_kopecks = 0)",
            name="ck_client_billing_batch_lines_return_free",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "batch_id"],
            ["client_billing_batches.organization_id", "client_billing_batches.batch_id"],
            name="fk_client_billing_batch_lines_org_batch",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "batch_id", "group_id"],
            [
                "client_billing_batch_groups.organization_id",
                "client_billing_batch_groups.batch_id",
                "client_billing_batch_groups.group_id",
            ],
            name="fk_client_billing_batch_lines_org_group",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "client_id"],
            ["client_accounts.organization_id", "client_accounts.client_id"],
            name="fk_client_billing_batch_lines_org_client",
        ),
        sa.UniqueConstraint(
            "batch_id",
            "stable_line_key",
            name="uq_client_billing_batch_lines_stable_key",
        ),
    )
    op.create_index(
        "ix_client_billing_batch_lines_group",
        "client_billing_batch_lines",
        ["batch_id", "group_id", "stable_line_key"],
    )

    op.add_column(
        "client_payments",
        sa.Column("allow_credit", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    # Nullable for pre-existing 0032 rows. Every new event gets a SHA-256 and
    # the application treats a legacy NULL as an unverifiable old event.
    op.add_column(
        "client_telegram_outbox",
        sa.Column("payload_sha256", sa.String(64), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("client_telegram_outbox", "payload_sha256")
    op.drop_column("client_payments", "allow_credit")
    op.drop_index(
        "ix_client_billing_batch_lines_group",
        table_name="client_billing_batch_lines",
    )
    op.drop_table("client_billing_batch_lines")
    op.drop_index(
        "ix_client_billing_batch_groups_batch",
        table_name="client_billing_batch_groups",
    )
    op.drop_table("client_billing_batch_groups")
    op.drop_index(
        "ix_client_billing_batches_org_status", table_name="client_billing_batches"
    )
    op.drop_table("client_billing_batches")
