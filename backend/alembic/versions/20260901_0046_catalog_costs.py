"""canonical catalog and costs

Revision ID: 20260901_0046
Revises: 20260831_0045
Create Date: 2026-09-01
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260901_0046"
down_revision = "20260831_0045"
branch_labels = None
depends_on = None

TENANT_TABLES = (
    "iam_memberships",
    "marketplace_accounts",
    "catalog_skus",
    "marketplace_products",
    "marketplace_offers",
    "catalog_cost_versions",
)


def _enable_rls(table: str) -> None:
    tenant = "organization_id = NULLIF(current_setting('app.organization_id', true), '')::integer"
    op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
    op.execute(f"CREATE POLICY tenant_isolation_{table} ON {table} USING ({tenant}) WITH CHECK ({tenant})")


def upgrade() -> None:
    op.create_table(
        "iam_memberships",
        sa.Column("membership_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("permissions", sa.JSON(), nullable=False),
        sa.Column("scope_mode", sa.String(length=16), nullable=False),
        sa.Column("allowed_account_ids", sa.JSON(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["lk_organizations.organization_id"]),
        sa.ForeignKeyConstraint(["user_id"], ["lk_users.user_id"]),
        sa.PrimaryKeyConstraint("membership_id"),
        sa.UniqueConstraint("organization_id", "membership_id", name="uq_iam_memberships_org_id"),
        sa.UniqueConstraint("organization_id", "user_id", name="uq_iam_memberships_org_user"),
    )
    op.create_table(
        "marketplace_accounts",
        sa.Column("marketplace_account_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("marketplace", sa.String(length=16), nullable=False),
        sa.Column("external_account_id", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("credential_ref", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["lk_organizations.organization_id"]),
        sa.PrimaryKeyConstraint("marketplace_account_id"),
        sa.UniqueConstraint("organization_id", "marketplace_account_id", name="uq_marketplace_accounts_org_id"),
        sa.UniqueConstraint(
            "organization_id",
            "marketplace",
            "external_account_id",
            name="uq_marketplace_accounts_org_marketplace_external",
        ),
    )
    op.create_table(
        "catalog_skus",
        sa.Column("catalog_sku_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(length=128), nullable=False),
        sa.Column("print_id", sa.String(length=128), nullable=True),
        sa.Column("product_type", sa.String(length=64), nullable=True),
        sa.Column("color", sa.String(length=64), nullable=True),
        sa.Column("size", sa.String(length=64), nullable=True),
        sa.Column("manager_membership_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(
            ["organization_id", "manager_membership_id"],
            ["iam_memberships.organization_id", "iam_memberships.membership_id"],
            name="fk_catalog_skus_org_manager_membership",
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["lk_organizations.organization_id"]),
        sa.PrimaryKeyConstraint("catalog_sku_id"),
        sa.UniqueConstraint("organization_id", "catalog_sku_id", name="uq_catalog_skus_org_id"),
        sa.UniqueConstraint("organization_id", "code", name="uq_catalog_skus_org_code"),
    )
    op.create_table(
        "marketplace_products",
        sa.Column("marketplace_product_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("marketplace_account_id", sa.Integer(), nullable=False),
        sa.Column("external_product_id", sa.String(length=128), nullable=False),
        sa.Column("seller_article", sa.String(length=128), nullable=True),
        sa.Column("brand", sa.String(length=255), nullable=True),
        sa.Column("title", sa.String(length=512), nullable=True),
        sa.Column("image_url", sa.String(length=2048), nullable=True),
        sa.Column("product_status", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(
            ["organization_id", "marketplace_account_id"],
            ["marketplace_accounts.organization_id", "marketplace_accounts.marketplace_account_id"],
            name="fk_marketplace_products_org_account",
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["lk_organizations.organization_id"]),
        sa.PrimaryKeyConstraint("marketplace_product_id"),
        sa.UniqueConstraint("organization_id", "marketplace_product_id", name="uq_marketplace_products_org_id"),
        sa.UniqueConstraint(
            "organization_id",
            "marketplace_account_id",
            "external_product_id",
            name="uq_marketplace_products_org_account_external",
        ),
    )
    op.create_table(
        "marketplace_offers",
        sa.Column("marketplace_offer_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("marketplace_account_id", sa.Integer(), nullable=False),
        sa.Column("marketplace_product_id", sa.Integer(), nullable=False),
        sa.Column("external_offer_key", sa.String(length=128), nullable=False),
        sa.Column("catalog_sku_id", sa.Integer(), nullable=True),
        sa.Column("offer_status", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(
            ["organization_id", "catalog_sku_id"],
            ["catalog_skus.organization_id", "catalog_skus.catalog_sku_id"],
            name="fk_marketplace_offers_org_sku",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "marketplace_account_id"],
            ["marketplace_accounts.organization_id", "marketplace_accounts.marketplace_account_id"],
            name="fk_marketplace_offers_org_account",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "marketplace_product_id"],
            ["marketplace_products.organization_id", "marketplace_products.marketplace_product_id"],
            name="fk_marketplace_offers_org_product",
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["lk_organizations.organization_id"]),
        sa.PrimaryKeyConstraint("marketplace_offer_id"),
        sa.UniqueConstraint(
            "organization_id",
            "marketplace_product_id",
            "external_offer_key",
            name="uq_marketplace_offers_org_product_external",
        ),
    )
    op.create_table(
        "catalog_cost_versions",
        sa.Column("cost_version_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("catalog_sku_id", sa.Integer(), nullable=False),
        sa.Column("amount_kopecks", sa.Integer(), nullable=True),
        sa.Column("value_state", sa.String(length=16), nullable=False),
        sa.Column("effective_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("source_reference", sa.String(length=255), nullable=False),
        sa.Column("evidence_status", sa.String(length=32), nullable=False),
        sa.Column("supersedes_cost_version_id", sa.Integer(), nullable=True),
        sa.Column("created_by_membership_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.CheckConstraint("source_reference <> ''", name="ck_catalog_cost_versions_source_reference"),
        sa.CheckConstraint(
            "(value_state = 'configured' AND amount_kopecks >= 0) OR "
            "(value_state = 'assumed' AND amount_kopecks > 0) OR "
            "(value_state = 'missing' AND amount_kopecks IS NULL)",
            name="ck_catalog_cost_versions_value",
        ),
        sa.CheckConstraint(
            "evidence_status IN ('dated', 'undated', 'period_end_fallback')",
            name="ck_catalog_cost_versions_evidence_status",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "catalog_sku_id"],
            ["catalog_skus.organization_id", "catalog_skus.catalog_sku_id"],
            name="fk_catalog_cost_versions_org_sku",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "created_by_membership_id"],
            ["iam_memberships.organization_id", "iam_memberships.membership_id"],
            name="fk_catalog_cost_versions_org_membership",
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["lk_organizations.organization_id"]),
        sa.ForeignKeyConstraint(
            ["organization_id", "supersedes_cost_version_id"],
            ["catalog_cost_versions.organization_id", "catalog_cost_versions.cost_version_id"],
            name="fk_catalog_cost_versions_org_supersedes",
        ),
        sa.PrimaryKeyConstraint("cost_version_id"),
        sa.UniqueConstraint("organization_id", "cost_version_id", name="uq_catalog_cost_versions_org_id"),
        sa.UniqueConstraint(
            "organization_id",
            "source",
            "source_reference",
            name="uq_catalog_cost_versions_org_source_reference",
        ),
    )
    op.create_index(
        "ix_catalog_cost_versions_resolve",
        "catalog_cost_versions",
        ["organization_id", "catalog_sku_id", "effective_from", "created_at"],
    )
    for table in TENANT_TABLES:
        _enable_rls(table)


def downgrade() -> None:
    op.drop_index("ix_catalog_cost_versions_resolve", table_name="catalog_cost_versions")
    for table in reversed(TENANT_TABLES):
        op.drop_table(table)
