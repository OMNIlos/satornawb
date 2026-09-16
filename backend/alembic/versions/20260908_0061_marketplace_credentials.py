"""add account-owned encrypted marketplace credentials

Revision ID: 20260908_0061
Revises: 20260905_0060
Create Date: 2026-09-08
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op


revision = "20260908_0061"
down_revision = "20260905_0060"
branch_labels = None
depends_on = None

CREDENTIAL_TABLE = "marketplace_account_credentials"
INGESTION_TABLE = "marketplace_account_ingestion_tokens"
TABLES = (CREDENTIAL_TABLE, INGESTION_TABLE)
PARENT_PROVIDER_UNIQUE = "uq_marketplace_accounts_org_id_marketplace"


def _enable_rls(table: str) -> None:
    tenant = "organization_id = NULLIF(current_setting('app.organization_id', true), '')::integer"
    op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY tenant_isolation_{table} ON {table} "
        f"USING ({tenant}) WITH CHECK ({tenant})"
    )


def upgrade() -> None:
    op.create_unique_constraint(
        PARENT_PROVIDER_UNIQUE,
        "marketplace_accounts",
        ["organization_id", "marketplace_account_id", "marketplace"],
    )
    op.create_table(
        CREDENTIAL_TABLE,
        sa.Column("credential_id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.BigInteger(), nullable=False),
        sa.Column("marketplace_account_id", sa.BigInteger(), nullable=False),
        sa.Column("provider", sa.String(length=16), nullable=False),
        sa.Column("credential_kind", sa.String(length=32), nullable=False),
        sa.Column("algorithm", sa.String(length=32), nullable=False),
        sa.Column("key_version", sa.Integer(), nullable=False),
        sa.Column("aad_version", sa.SmallInteger(), nullable=False),
        sa.Column("payload_schema_version", sa.SmallInteger(), nullable=False),
        sa.Column("nonce", sa.LargeBinary(), nullable=False),
        sa.Column("ciphertext", sa.LargeBinary(), nullable=False),
        sa.Column("generation", sa.BigInteger(), server_default=sa.text("1"), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revocation_reason_code", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("credential_id"),
        sa.ForeignKeyConstraint(
            ["organization_id", "marketplace_account_id", "provider"],
            [
                "marketplace_accounts.organization_id",
                "marketplace_accounts.marketplace_account_id",
                "marketplace_accounts.marketplace",
            ],
            name="fk_marketplace_account_credentials_org_account_provider",
        ),
        sa.CheckConstraint("algorithm = 'AES-256-GCM'", name="ck_marketplace_account_credentials_algorithm"),
        sa.CheckConstraint("key_version > 0", name="ck_marketplace_account_credentials_key_version"),
        sa.CheckConstraint("aad_version = 1", name="ck_marketplace_account_credentials_aad_version"),
        sa.CheckConstraint(
            "(provider = 'wb' AND credential_kind = 'wb_api' AND payload_schema_version = 1) OR "
            "(provider = 'avito' AND credential_kind = 'avito_oauth_client' AND payload_schema_version = 1) OR "
            "(provider = 'avito' AND credential_kind = 'avito_oauth_access' AND payload_schema_version = 1)",
            name="ck_marketplace_account_credentials_schema",
        ),
        sa.CheckConstraint("octet_length(nonce) = 12", name="ck_marketplace_account_credentials_nonce"),
        sa.CheckConstraint(
            "octet_length(ciphertext) > 16 AND octet_length(ciphertext) <= 16400",
            name="ck_marketplace_account_credentials_ciphertext",
        ),
        sa.CheckConstraint("generation > 0", name="ck_marketplace_account_credentials_generation"),
        sa.CheckConstraint(
            "(credential_kind = 'avito_oauth_access' AND expires_at IS NOT NULL) OR "
            "(credential_kind <> 'avito_oauth_access' AND expires_at IS NULL)",
            name="ck_marketplace_account_credentials_expiry",
        ),
        sa.CheckConstraint(
            "(revoked_at IS NULL AND revocation_reason_code IS NULL) OR "
            "(revoked_at IS NOT NULL AND revocation_reason_code IN "
            "('provider_rotated', 'credential_replaced', 'account_disconnected', "
            "'security_incident', 'operator_revoked', 'expired'))",
            name="ck_marketplace_account_credentials_revocation",
        ),
    )
    op.create_index(
        "uq_marketplace_account_credentials_active_kind",
        CREDENTIAL_TABLE,
        ["organization_id", "marketplace_account_id", "credential_kind"],
        unique=True,
        postgresql_where=sa.text("revoked_at IS NULL"),
    )
    op.create_index(
        "ix_marketplace_account_credentials_account",
        CREDENTIAL_TABLE,
        ["organization_id", "marketplace_account_id", "provider", "credential_kind"],
    )
    op.create_index(
        "ix_marketplace_account_credentials_key_version",
        CREDENTIAL_TABLE,
        ["key_version"],
        postgresql_where=sa.text("revoked_at IS NULL"),
    )

    op.create_table(
        INGESTION_TABLE,
        sa.Column("token_id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.BigInteger(), nullable=False),
        sa.Column("marketplace_account_id", sa.BigInteger(), nullable=False),
        sa.Column("provider", sa.String(length=16), nullable=False),
        sa.Column("verifier", sa.LargeBinary(), nullable=False),
        sa.Column("scope", sa.String(length=64), nullable=False),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revocation_reason_code", sa.String(length=64), nullable=True),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("token_id"),
        sa.ForeignKeyConstraint(
            ["organization_id", "marketplace_account_id", "provider"],
            [
                "marketplace_accounts.organization_id",
                "marketplace_accounts.marketplace_account_id",
                "marketplace_accounts.marketplace",
            ],
            name="fk_marketplace_account_ingestion_tokens_org_account_provider",
        ),
        sa.CheckConstraint("provider = 'avito'", name="ck_marketplace_account_ingestion_tokens_provider"),
        sa.CheckConstraint(
            "scope = 'avito.browser_snapshot.write'",
            name="ck_marketplace_account_ingestion_tokens_scope",
        ),
        sa.CheckConstraint("octet_length(verifier) = 32", name="ck_marketplace_account_ingestion_tokens_verifier"),
        sa.CheckConstraint("expires_at > issued_at", name="ck_marketplace_account_ingestion_tokens_expiry"),
        sa.CheckConstraint(
            "(revoked_at IS NULL AND revocation_reason_code IS NULL) OR "
            "(revoked_at IS NOT NULL AND revocation_reason_code IN "
            "('token_rotated', 'account_disconnected', 'security_incident', "
            "'operator_revoked', 'expired'))",
            name="ck_marketplace_account_ingestion_tokens_revocation",
        ),
    )
    op.create_index(
        "ix_marketplace_account_ingestion_tokens_account",
        INGESTION_TABLE,
        ["organization_id", "marketplace_account_id", "provider", "expires_at"],
    )
    for table in TABLES:
        _enable_rls(table)


def downgrade() -> None:
    for table in reversed(TABLES):
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation_{table} ON {table}")
        op.drop_table(table)
    op.drop_constraint(PARENT_PROVIDER_UNIQUE, "marketplace_accounts", type_="unique")
