from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    LargeBinary,
    SmallInteger,
    String,
    UniqueConstraint,
    Uuid,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.cabinet import orm as _cabinet_models  # noqa: F401
from app.infra.models import Base


class MarketplaceAccountRow(Base):
    __tablename__ = "marketplace_accounts"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "marketplace",
            "external_account_id",
            name="uq_marketplace_accounts_org_marketplace_external",
        ),
        UniqueConstraint("organization_id", "marketplace_account_id", name="uq_marketplace_accounts_org_id"),
        UniqueConstraint(
            "organization_id",
            "marketplace_account_id",
            "marketplace",
            name="uq_marketplace_accounts_org_id_marketplace",
        ),
    )

    marketplace_account_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("lk_organizations.organization_id"), nullable=False)
    marketplace: Mapped[str] = mapped_column(String(16), nullable=False)
    external_account_id: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="disconnected")
    credential_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class MarketplaceAccountCredentialRow(Base):
    __tablename__ = "marketplace_account_credentials"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "marketplace_account_id", "provider"],
            [
                "marketplace_accounts.organization_id",
                "marketplace_accounts.marketplace_account_id",
                "marketplace_accounts.marketplace",
            ],
            name="fk_marketplace_account_credentials_org_account_provider",
        ),
        CheckConstraint(
            "algorithm = 'AES-256-GCM'",
            name="ck_marketplace_account_credentials_algorithm",
        ),
        CheckConstraint(
            "key_version > 0",
            name="ck_marketplace_account_credentials_key_version",
        ),
        CheckConstraint(
            "aad_version = 1",
            name="ck_marketplace_account_credentials_aad_version",
        ),
        CheckConstraint(
            "(provider = 'wb' AND credential_kind = 'wb_api' AND payload_schema_version = 1) OR "
            "(provider = 'avito' AND credential_kind = 'avito_oauth_client' AND payload_schema_version = 1) OR "
            "(provider = 'avito' AND credential_kind = 'avito_oauth_access' AND payload_schema_version = 1)",
            name="ck_marketplace_account_credentials_schema",
        ),
        CheckConstraint(
            "octet_length(nonce) = 12",
            name="ck_marketplace_account_credentials_nonce",
        ),
        CheckConstraint(
            "octet_length(ciphertext) > 16 AND octet_length(ciphertext) <= 16400",
            name="ck_marketplace_account_credentials_ciphertext",
        ),
        CheckConstraint(
            "generation > 0",
            name="ck_marketplace_account_credentials_generation",
        ),
        CheckConstraint(
            "(credential_kind = 'avito_oauth_access' AND expires_at IS NOT NULL) OR "
            "(credential_kind <> 'avito_oauth_access' AND expires_at IS NULL)",
            name="ck_marketplace_account_credentials_expiry",
        ),
        CheckConstraint(
            "(revoked_at IS NULL AND revocation_reason_code IS NULL) OR "
            "(revoked_at IS NOT NULL AND revocation_reason_code IN "
            "('provider_rotated', 'credential_replaced', 'account_disconnected', "
            "'security_incident', 'operator_revoked', 'expired'))",
            name="ck_marketplace_account_credentials_revocation",
        ),
        Index(
            "uq_marketplace_account_credentials_active_kind",
            "organization_id",
            "marketplace_account_id",
            "credential_kind",
            unique=True,
            postgresql_where=text("revoked_at IS NULL"),
            sqlite_where=text("revoked_at IS NULL"),
        ),
        Index(
            "ix_marketplace_account_credentials_account",
            "organization_id",
            "marketplace_account_id",
            "provider",
            "credential_kind",
        ),
        Index(
            "ix_marketplace_account_credentials_key_version",
            "key_version",
            postgresql_where=text("revoked_at IS NULL"),
            sqlite_where=text("revoked_at IS NULL"),
        ),
    )

    credential_id: Mapped[UUID] = mapped_column(Uuid(), primary_key=True)
    organization_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    marketplace_account_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    provider: Mapped[str] = mapped_column(String(16), nullable=False)
    credential_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    algorithm: Mapped[str] = mapped_column(String(32), nullable=False, default="AES-256-GCM")
    key_version: Mapped[int] = mapped_column(Integer, nullable=False)
    aad_version: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=1)
    payload_schema_version: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=1)
    nonce: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    ciphertext: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    generation: Mapped[int] = mapped_column(BigInteger, nullable=False, default=1)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revocation_reason_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class MarketplaceAccountIngestionTokenRow(Base):
    __tablename__ = "marketplace_account_ingestion_tokens"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "marketplace_account_id", "provider"],
            [
                "marketplace_accounts.organization_id",
                "marketplace_accounts.marketplace_account_id",
                "marketplace_accounts.marketplace",
            ],
            name="fk_marketplace_account_ingestion_tokens_org_account_provider",
        ),
        CheckConstraint(
            "provider = 'avito'",
            name="ck_marketplace_account_ingestion_tokens_provider",
        ),
        CheckConstraint(
            "scope = 'avito.browser_snapshot.write'",
            name="ck_marketplace_account_ingestion_tokens_scope",
        ),
        CheckConstraint(
            "octet_length(verifier) = 32",
            name="ck_marketplace_account_ingestion_tokens_verifier",
        ),
        CheckConstraint(
            "expires_at > issued_at",
            name="ck_marketplace_account_ingestion_tokens_expiry",
        ),
        CheckConstraint(
            "(revoked_at IS NULL AND revocation_reason_code IS NULL) OR "
            "(revoked_at IS NOT NULL AND revocation_reason_code IN "
            "('token_rotated', 'account_disconnected', 'security_incident', "
            "'operator_revoked', 'expired'))",
            name="ck_marketplace_account_ingestion_tokens_revocation",
        ),
        Index(
            "ix_marketplace_account_ingestion_tokens_account",
            "organization_id",
            "marketplace_account_id",
            "provider",
            "expires_at",
        ),
    )

    token_id: Mapped[UUID] = mapped_column(Uuid(), primary_key=True)
    organization_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    marketplace_account_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    provider: Mapped[str] = mapped_column(String(16), nullable=False)
    verifier: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    scope: Mapped[str] = mapped_column(String(64), nullable=False)
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revocation_reason_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
