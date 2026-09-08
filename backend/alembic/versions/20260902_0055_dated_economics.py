"""add dated organization and SKU economics policies

Revision ID: 20260902_0055
Revises: 20260902_0054
Create Date: 2026-09-02
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "20260902_0055"
down_revision = "20260902_0054"
branch_labels = None
depends_on = None

ORGANIZATION_TABLE = "organization_economics_versions"
OVERRIDE_TABLE = "catalog_economics_override_versions"
TABLES = (ORGANIZATION_TABLE, OVERRIDE_TABLE)


def _common_columns() -> tuple[sa.Column, ...]:
    return (
        sa.Column("tax_basis_points", sa.Integer(), nullable=True),
        sa.Column("other_expense_price_basis_points", sa.Integer(), nullable=True),
        sa.Column("other_expense_per_sale_kopecks", sa.BigInteger(), nullable=True),
        sa.Column("value_state", sa.String(length=16), nullable=False),
        sa.Column("effective_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("source_reference", sa.String(length=255), nullable=False),
        sa.Column("evidence_status", sa.String(length=32), nullable=False),
        sa.Column("created_by_membership_id", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
    )


def _value_constraint(name: str) -> sa.CheckConstraint:
    return sa.CheckConstraint(
        "(tax_basis_points IS NULL OR tax_basis_points BETWEEN 0 AND 10000) "
        "AND (other_expense_price_basis_points IS NULL OR "
        "other_expense_price_basis_points BETWEEN 0 AND 10000) "
        "AND (other_expense_per_sale_kopecks IS NULL OR "
        "other_expense_per_sale_kopecks >= 0)",
        name=name,
    )


def upgrade() -> None:
    op.create_table(
        ORGANIZATION_TABLE,
        sa.Column(
            "organization_economics_version_id",
            sa.Integer(),
            autoincrement=True,
            nullable=False,
        ),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        *_common_columns(),
        sa.Column(
            "supersedes_organization_economics_version_id",
            sa.Integer(),
            nullable=True,
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["lk_organizations.organization_id"],
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "created_by_membership_id"],
            ["iam_memberships.organization_id", "iam_memberships.membership_id"],
            name="fk_organization_economics_org_membership",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "supersedes_organization_economics_version_id"],
            [
                f"{ORGANIZATION_TABLE}.organization_id",
                f"{ORGANIZATION_TABLE}.organization_economics_version_id",
            ],
            name="fk_organization_economics_org_supersedes",
        ),
        _value_constraint("ck_organization_economics_values"),
        sa.CheckConstraint(
            "(value_state IN ('configured', 'assumed') "
            "AND tax_basis_points IS NOT NULL "
            "AND other_expense_price_basis_points IS NOT NULL "
            "AND other_expense_per_sale_kopecks IS NOT NULL) "
            "OR (value_state = 'missing' "
            "AND tax_basis_points IS NULL "
            "AND other_expense_price_basis_points IS NULL "
            "AND other_expense_per_sale_kopecks IS NULL)",
            name="ck_organization_economics_state",
        ),
        sa.CheckConstraint(
            "evidence_status IN ('dated', 'undated', 'period_end_fallback')",
            name="ck_organization_economics_evidence_status",
        ),
        sa.PrimaryKeyConstraint("organization_economics_version_id"),
        sa.UniqueConstraint(
            "organization_id",
            "organization_economics_version_id",
            name="uq_organization_economics_org_id",
        ),
        sa.UniqueConstraint(
            "organization_id",
            "source",
            "source_reference",
            name="uq_organization_economics_org_source_reference",
        ),
    )
    op.create_index(
        "ix_organization_economics_resolve",
        ORGANIZATION_TABLE,
        ["organization_id", "effective_from", "created_at"],
    )
    op.create_table(
        OVERRIDE_TABLE,
        sa.Column(
            "catalog_economics_override_version_id",
            sa.Integer(),
            autoincrement=True,
            nullable=False,
        ),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("catalog_sku_id", sa.Integer(), nullable=False),
        *_common_columns(),
        sa.Column(
            "supersedes_catalog_economics_override_version_id",
            sa.Integer(),
            nullable=True,
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["lk_organizations.organization_id"],
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "catalog_sku_id"],
            ["catalog_skus.organization_id", "catalog_skus.catalog_sku_id"],
            name="fk_catalog_economics_override_org_sku",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "created_by_membership_id"],
            ["iam_memberships.organization_id", "iam_memberships.membership_id"],
            name="fk_catalog_economics_override_org_membership",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "supersedes_catalog_economics_override_version_id"],
            [
                f"{OVERRIDE_TABLE}.organization_id",
                f"{OVERRIDE_TABLE}.catalog_economics_override_version_id",
            ],
            name="fk_catalog_economics_override_org_supersedes",
        ),
        _value_constraint("ck_catalog_economics_override_values"),
        sa.CheckConstraint(
            "value_state IN ('configured', 'assumed')",
            name="ck_catalog_economics_override_state",
        ),
        sa.CheckConstraint(
            "evidence_status IN ('dated', 'undated', 'period_end_fallback')",
            name="ck_catalog_economics_override_evidence_status",
        ),
        sa.PrimaryKeyConstraint("catalog_economics_override_version_id"),
        sa.UniqueConstraint(
            "organization_id",
            "catalog_economics_override_version_id",
            name="uq_catalog_economics_override_org_id",
        ),
        sa.UniqueConstraint(
            "organization_id",
            "source",
            "source_reference",
            name="uq_catalog_economics_override_org_source_reference",
        ),
    )
    op.create_index(
        "ix_catalog_economics_override_resolve",
        OVERRIDE_TABLE,
        ["organization_id", "catalog_sku_id", "effective_from", "created_at"],
    )
    tenant = "organization_id = NULLIF(current_setting('app.organization_id', true), '')::integer"
    for table in TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY tenant_isolation_{table} ON {table} "
            f"USING ({tenant}) WITH CHECK ({tenant})"
        )


def downgrade() -> None:
    for table in reversed(TABLES):
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation_{table} ON {table}")
        op.drop_table(table)
