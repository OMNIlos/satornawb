"""add manual finance and bank statement tables

Revision ID: 20260817_0025
Revises: 20260810_0024
Create Date: 2026-08-17 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260817_0025"
down_revision = "20260810_0024"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "finance_counterparties",
        sa.Column("counterparty_id", sa.String(length=32), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("lk_organizations.organization_id"), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("inn", sa.String(length=12), nullable=True),
        sa.Column("kpp", sa.String(length=9), nullable=True),
        sa.Column("bank_account", sa.String(length=34), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("organization_id", "inn", name="uq_finance_counterparties_org_inn"),
        sa.UniqueConstraint("organization_id", "bank_account", name="uq_finance_counterparties_org_account"),
        sa.UniqueConstraint("organization_id", "name", "kind", name="uq_finance_counterparties_org_name_kind"),
    )
    op.create_index("ix_finance_counterparties_org_inn", "finance_counterparties", ["organization_id", "inn"])
    op.create_index("ix_finance_counterparties_org_kind", "finance_counterparties", ["organization_id", "kind"])

    op.create_table(
        "finance_categories",
        sa.Column("category_id", sa.String(length=32), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("lk_organizations.organization_id"), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("direction", sa.String(length=16), nullable=False),
        sa.Column("cash_flow_section", sa.String(length=16), nullable=False),
        sa.Column("pnl_treatment", sa.String(length=32), nullable=False, server_default="unreviewed"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("organization_id", "name", "direction", name="uq_finance_categories_org_name_direction"),
    )
    op.create_index("ix_finance_categories_org_active", "finance_categories", ["organization_id", "active"])

    op.create_table(
        "finance_allocation_rules",
        sa.Column("rule_id", sa.String(length=32), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("lk_organizations.organization_id"), nullable=False),
        sa.Column("category_id", sa.String(length=32), sa.ForeignKey("finance_categories.category_id"), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("direction", sa.String(length=16), nullable=False, server_default="both"),
        sa.Column("counterparty_inn", sa.String(length=12), nullable=True),
        sa.Column("purpose_contains", sa.String(length=255), nullable=True),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_finance_rules_org_priority", "finance_allocation_rules", ["organization_id", "active", "priority"])

    op.create_table(
        "finance_bank_imports",
        sa.Column("import_id", sa.String(length=32), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("lk_organizations.organization_id"), nullable=False),
        sa.Column("file_name", sa.String(length=255), nullable=False),
        sa.Column("file_sha256", sa.String(length=64), nullable=False),
        sa.Column("source_format", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("rows_total", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("rows_imported", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("rows_duplicate", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("rows_unclassified", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("diagnostics", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("created_by_user_id", sa.String(length=32), sa.ForeignKey("lk_users.user_id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("organization_id", "file_sha256", name="uq_finance_bank_imports_org_sha256"),
    )
    op.create_index("ix_finance_bank_imports_org_created", "finance_bank_imports", ["organization_id", "created_at"])

    op.create_table(
        "finance_bank_transactions",
        sa.Column("transaction_id", sa.String(length=32), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("lk_organizations.organization_id"), nullable=False),
        sa.Column("import_id", sa.String(length=32), sa.ForeignKey("finance_bank_imports.import_id"), nullable=False),
        sa.Column("fingerprint", sa.String(length=64), nullable=False),
        sa.Column("operation_date", sa.Date(), nullable=False),
        sa.Column("direction", sa.String(length=16), nullable=False),
        sa.Column("amount_kopecks", sa.BigInteger(), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False, server_default="RUB"),
        sa.Column("document_number", sa.String(length=128), nullable=True),
        sa.Column("counterparty_name", sa.String(length=255), nullable=True),
        sa.Column("counterparty_inn", sa.String(length=12), nullable=True),
        sa.Column("counterparty_kpp", sa.String(length=9), nullable=True),
        sa.Column("counterparty_account", sa.String(length=34), nullable=True),
        sa.Column("own_account", sa.String(length=34), nullable=True),
        sa.Column("purpose", sa.Text(), nullable=True),
        sa.Column("counterparty_id", sa.String(length=32), sa.ForeignKey("finance_counterparties.counterparty_id"), nullable=True),
        sa.Column("category_id", sa.String(length=32), sa.ForeignKey("finance_categories.category_id"), nullable=True),
        sa.Column("classification_state", sa.String(length=16), nullable=False, server_default="unclassified"),
        sa.Column("source_row", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("organization_id", "fingerprint", name="uq_finance_bank_transactions_org_fingerprint"),
    )
    op.create_index("ix_finance_transactions_org_date", "finance_bank_transactions", ["organization_id", "operation_date"])
    op.create_index("ix_finance_transactions_org_classification", "finance_bank_transactions", ["organization_id", "classification_state"])
    op.create_index("ix_finance_transactions_org_category", "finance_bank_transactions", ["organization_id", "category_id"])


def downgrade() -> None:
    op.drop_table("finance_bank_transactions")
    op.drop_table("finance_bank_imports")
    op.drop_table("finance_allocation_rules")
    op.drop_table("finance_categories")
    op.drop_table("finance_counterparties")
