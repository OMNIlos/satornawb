"""add tenant-scoped client billing foundation

Revision ID: 20260819_0032
Revises: 20260818_0031
Create Date: 2026-08-19 21:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "20260819_0032"
down_revision = "20260818_0031"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "client_accounts",
        sa.Column("client_id", sa.String(32), primary_key=True),
        sa.Column(
            "organization_id",
            sa.Integer(),
            sa.ForeignKey("lk_organizations.organization_id"),
            nullable=False,
        ),
        sa.Column("code", sa.String(32), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column(
            "return_warehouse_id",
            sa.String(32),
            sa.ForeignKey("inventory_warehouses.warehouse_id"),
            nullable=False,
        ),
        sa.Column("telegram_recipient_ref", sa.String(128), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "organization_id", "client_id", name="uq_client_accounts_org_id"
        ),
        sa.UniqueConstraint(
            "organization_id", "code", name="uq_client_accounts_org_code"
        ),
        sa.UniqueConstraint(
            "organization_id",
            "return_warehouse_id",
            name="uq_client_accounts_org_return_warehouse",
        ),
    )
    op.create_index(
        "ix_client_accounts_org_active",
        "client_accounts",
        ["organization_id", "active", "name"],
    )

    op.create_table(
        "client_sale_tariffs",
        sa.Column("tariff_id", sa.String(32), primary_key=True),
        sa.Column(
            "organization_id",
            sa.Integer(),
            sa.ForeignKey("lk_organizations.organization_id"),
            nullable=False,
        ),
        sa.Column("client_id", sa.String(32), nullable=False),
        sa.Column(
            "item_id",
            sa.String(32),
            sa.ForeignKey("inventory_items.item_id"),
            nullable=False,
        ),
        sa.Column("channel", sa.String(16), nullable=False),
        sa.Column("price_kopecks", sa.BigInteger(), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="RUB"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "price_kopecks >= 0", name="ck_client_sale_tariffs_price_nonnegative"
        ),
        sa.CheckConstraint(
            "channel IN ('wb', 'avito', 'other')",
            name="ck_client_sale_tariffs_channel",
        ),
        sa.CheckConstraint("currency = 'RUB'", name="ck_client_sale_tariffs_currency"),
        sa.ForeignKeyConstraint(
            ["organization_id", "client_id"],
            ["client_accounts.organization_id", "client_accounts.client_id"],
            name="fk_client_sale_tariffs_org_client",
        ),
        sa.UniqueConstraint(
            "organization_id",
            "client_id",
            "item_id",
            "channel",
            name="uq_client_sale_tariffs_scope",
        ),
    )
    op.create_index(
        "ix_client_sale_tariffs_org_client",
        "client_sale_tariffs",
        ["organization_id", "client_id", "active"],
    )

    op.create_table(
        "client_billing_runs",
        sa.Column("billing_id", sa.String(32), primary_key=True),
        sa.Column(
            "organization_id",
            sa.Integer(),
            sa.ForeignKey("lk_organizations.organization_id"),
            nullable=False,
        ),
        sa.Column("client_id", sa.String(32), nullable=False),
        sa.Column("external_reference", sa.String(128), nullable=False),
        sa.Column("payload_sha256", sa.String(64), nullable=False),
        sa.Column("channel", sa.String(16), nullable=False),
        sa.Column(
            "make_new_units", sa.BigInteger(), nullable=False, server_default="0"
        ),
        sa.Column(
            "return_ready_units", sa.BigInteger(), nullable=False, server_default="0"
        ),
        sa.Column(
            "total_amount_kopecks", sa.BigInteger(), nullable=False, server_default="0"
        ),
        sa.Column("status", sa.String(16), nullable=False, server_default="posted"),
        sa.Column(
            "created_by_user_id",
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
        sa.CheckConstraint(
            "make_new_units >= 0", name="ck_client_billing_runs_make_new_nonnegative"
        ),
        sa.CheckConstraint(
            "return_ready_units >= 0",
            name="ck_client_billing_runs_return_ready_nonnegative",
        ),
        sa.CheckConstraint(
            "total_amount_kopecks >= 0", name="ck_client_billing_runs_total_nonnegative"
        ),
        sa.CheckConstraint(
            "channel IN ('wb', 'avito', 'other')", name="ck_client_billing_runs_channel"
        ),
        sa.CheckConstraint("status = 'posted'", name="ck_client_billing_runs_status"),
        sa.ForeignKeyConstraint(
            ["organization_id", "client_id"],
            ["client_accounts.organization_id", "client_accounts.client_id"],
            name="fk_client_billing_runs_org_client",
        ),
        sa.UniqueConstraint(
            "organization_id",
            "external_reference",
            name="uq_client_billing_runs_org_reference",
        ),
        sa.UniqueConstraint(
            "organization_id", "billing_id", name="uq_client_billing_runs_org_id"
        ),
    )
    op.create_index(
        "ix_client_billing_runs_org_client",
        "client_billing_runs",
        ["organization_id", "client_id", "created_at"],
    )

    op.create_table(
        "client_billing_lines",
        sa.Column("line_id", sa.String(32), primary_key=True),
        sa.Column(
            "organization_id",
            sa.Integer(),
            sa.ForeignKey("lk_organizations.organization_id"),
            nullable=False,
        ),
        sa.Column("billing_id", sa.String(32), nullable=False),
        sa.Column("line_reference", sa.String(128), nullable=False),
        sa.Column(
            "item_id",
            sa.String(32),
            sa.ForeignKey("inventory_items.item_id"),
            nullable=False,
        ),
        sa.Column("execution_type", sa.String(16), nullable=False),
        sa.Column("quantity", sa.BigInteger(), nullable=False),
        sa.Column("unit_price_kopecks", sa.BigInteger(), nullable=False),
        sa.Column("amount_kopecks", sa.BigInteger(), nullable=False),
        sa.CheckConstraint(
            "quantity > 0", name="ck_client_billing_lines_quantity_positive"
        ),
        sa.CheckConstraint(
            "unit_price_kopecks >= 0", name="ck_client_billing_lines_price_nonnegative"
        ),
        sa.CheckConstraint(
            "amount_kopecks >= 0", name="ck_client_billing_lines_amount_nonnegative"
        ),
        sa.CheckConstraint(
            "execution_type IN ('MAKE_NEW', 'RETURN_READY')",
            name="ck_client_billing_lines_execution_type",
        ),
        sa.CheckConstraint(
            "execution_type <> 'RETURN_READY' OR (unit_price_kopecks = 0 AND amount_kopecks = 0)",
            name="ck_client_billing_lines_return_free",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "billing_id"],
            ["client_billing_runs.organization_id", "client_billing_runs.billing_id"],
            name="fk_client_billing_lines_org_billing",
        ),
        sa.UniqueConstraint(
            "billing_id", "line_reference", name="uq_client_billing_lines_reference"
        ),
    )
    op.create_index(
        "ix_client_billing_lines_billing",
        "client_billing_lines",
        ["billing_id", "line_reference"],
    )

    op.create_table(
        "client_debt_ledger_entries",
        sa.Column("entry_id", sa.String(32), primary_key=True),
        sa.Column(
            "organization_id",
            sa.Integer(),
            sa.ForeignKey("lk_organizations.organization_id"),
            nullable=False,
        ),
        sa.Column("client_id", sa.String(32), nullable=False),
        sa.Column("entry_type", sa.String(16), nullable=False),
        sa.Column("delta_kopecks", sa.BigInteger(), nullable=False),
        sa.Column("source_type", sa.String(16), nullable=False),
        sa.Column("source_id", sa.String(32), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "delta_kopecks <> 0", name="ck_client_debt_ledger_delta_nonzero"
        ),
        sa.CheckConstraint(
            "(entry_type = 'charge' AND source_type = 'billing' AND delta_kopecks > 0) "
            "OR (entry_type = 'payment' AND source_type = 'payment' AND delta_kopecks < 0)",
            name="ck_client_debt_ledger_semantics",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "client_id"],
            ["client_accounts.organization_id", "client_accounts.client_id"],
            name="fk_client_debt_ledger_org_client",
        ),
        sa.UniqueConstraint(
            "organization_id",
            "source_type",
            "source_id",
            name="uq_client_debt_ledger_source",
        ),
    )
    op.create_index(
        "ix_client_debt_ledger_org_client",
        "client_debt_ledger_entries",
        ["organization_id", "client_id", "created_at"],
    )

    op.create_table(
        "client_payments",
        sa.Column("payment_id", sa.String(32), primary_key=True),
        sa.Column(
            "organization_id",
            sa.Integer(),
            sa.ForeignKey("lk_organizations.organization_id"),
            nullable=False,
        ),
        sa.Column("client_id", sa.String(32), nullable=False),
        sa.Column("idempotency_key", sa.String(128), nullable=False),
        sa.Column("receipt_sha256", sa.String(64), nullable=False),
        sa.Column("payload_sha256", sa.String(64), nullable=False),
        sa.Column("amount_kopecks", sa.BigInteger(), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="RUB"),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("payment_reference", sa.String(128), nullable=True),
        sa.Column(
            "created_by_user_id",
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
        sa.CheckConstraint(
            "amount_kopecks > 0", name="ck_client_payments_amount_positive"
        ),
        sa.CheckConstraint("currency = 'RUB'", name="ck_client_payments_currency"),
        sa.ForeignKeyConstraint(
            ["organization_id", "client_id"],
            ["client_accounts.organization_id", "client_accounts.client_id"],
            name="fk_client_payments_org_client",
        ),
        sa.UniqueConstraint(
            "organization_id",
            "idempotency_key",
            name="uq_client_payments_org_idempotency",
        ),
        sa.UniqueConstraint(
            "organization_id", "receipt_sha256", name="uq_client_payments_org_receipt"
        ),
    )
    op.create_index(
        "ix_client_payments_org_client",
        "client_payments",
        ["organization_id", "client_id", "paid_at"],
    )

    op.create_table(
        "client_telegram_outbox",
        sa.Column("outbox_id", sa.String(32), primary_key=True),
        sa.Column(
            "organization_id",
            sa.Integer(),
            sa.ForeignKey("lk_organizations.organization_id"),
            nullable=False,
        ),
        sa.Column("client_id", sa.String(32), nullable=False),
        sa.Column("event_type", sa.String(32), nullable=False),
        sa.Column("dedupe_key", sa.String(128), nullable=False),
        sa.Column("recipient_ref", sa.String(128), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "event_type IN ('billing.posted', 'payment.registered')",
            name="ck_client_telegram_outbox_event_type",
        ),
        sa.CheckConstraint(
            "status = 'pending'", name="ck_client_telegram_outbox_status"
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "client_id"],
            ["client_accounts.organization_id", "client_accounts.client_id"],
            name="fk_client_telegram_outbox_org_client",
        ),
        sa.UniqueConstraint(
            "organization_id", "dedupe_key", name="uq_client_telegram_outbox_org_dedupe"
        ),
    )
    op.create_index(
        "ix_client_telegram_outbox_org_status",
        "client_telegram_outbox",
        ["organization_id", "status", "created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_client_telegram_outbox_org_status", table_name="client_telegram_outbox"
    )
    op.drop_table("client_telegram_outbox")
    op.drop_index("ix_client_payments_org_client", table_name="client_payments")
    op.drop_table("client_payments")
    op.drop_index(
        "ix_client_debt_ledger_org_client", table_name="client_debt_ledger_entries"
    )
    op.drop_table("client_debt_ledger_entries")
    op.drop_index("ix_client_billing_lines_billing", table_name="client_billing_lines")
    op.drop_table("client_billing_lines")
    op.drop_index("ix_client_billing_runs_org_client", table_name="client_billing_runs")
    op.drop_table("client_billing_runs")
    op.drop_index("ix_client_sale_tariffs_org_client", table_name="client_sale_tariffs")
    op.drop_table("client_sale_tariffs")
    op.drop_index("ix_client_accounts_org_active", table_name="client_accounts")
    op.drop_table("client_accounts")
