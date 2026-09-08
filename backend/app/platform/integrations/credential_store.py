from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.cabinet.orm import LkAuditEventRow
from app.config import get_settings, load_marketplace_credential_keyring
from app.infra.db import get_session_factory, set_tenant_context
from app.platform.integrations.orm import MarketplaceAccountCredentialRow, MarketplaceAccountRow
from app.security.marketplace_credentials import (
    CredentialCryptoError,
    CredentialIdentity,
    CredentialKeyring,
    DecryptedCredential,
    EncryptedCredential,
    decrypt_credential,
    encrypt_credential,
)


_REVOCATION_REASONS = frozenset(
    {
        "provider_rotated",
        "credential_replaced",
        "account_disconnected",
        "security_incident",
        "operator_revoked",
        "expired",
    }
)
_CREDENTIAL_KINDS_BY_PROVIDER = {
    "wb": frozenset({"wb_api"}),
    "avito": frozenset({"avito_oauth_client", "avito_oauth_access"}),
}
_SAFE_ERROR_CODES = frozenset(
    {
        "credential_account_not_found",
        "credential_account_identity_mismatch",
        "credential_concurrent_update",
        "credential_configuration_invalid",
        "credential_contract_invalid",
        "credential_expired",
        "credential_missing",
        "credential_persistence_failed",
        "credential_reason_invalid",
    }
)


class CredentialStoreError(ValueError):
    def __init__(self, code: str) -> None:
        self.code = code if code in _SAFE_ERROR_CODES else "credential_persistence_failed"
        super().__init__(self.code)

    def __repr__(self) -> str:
        return f"CredentialStoreError(code={self.code!r})"


@dataclass(frozen=True)
class MarketplaceAccountCredentialOwner:
    organization_id: int
    marketplace_account_id: int
    provider: str


@dataclass(frozen=True)
class CredentialMetadata:
    credential_id: UUID
    organization_id: int
    marketplace_account_id: int
    provider: str
    credential_kind: str
    generation: int
    expires_at: datetime | None
    revoked_at: datetime | None
    revocation_reason_code: str | None
    created_at: datetime
    updated_at: datetime


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None or value.utcoffset() is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _load_keyring() -> CredentialKeyring:
    try:
        return load_marketplace_credential_keyring(get_settings())
    except RuntimeError:
        raise CredentialStoreError("credential_configuration_invalid") from None


def _validate_owner(owner: MarketplaceAccountCredentialOwner) -> None:
    if (
        not isinstance(owner.organization_id, int)
        or isinstance(owner.organization_id, bool)
        or owner.organization_id < 1
        or not isinstance(owner.marketplace_account_id, int)
        or isinstance(owner.marketplace_account_id, bool)
        or owner.marketplace_account_id < 1
        or owner.provider not in {"wb", "avito"}
    ):
        raise CredentialStoreError("credential_contract_invalid")


def _validate_kind(
    owner: MarketplaceAccountCredentialOwner,
    kind: str,
) -> None:
    if kind not in _CREDENTIAL_KINDS_BY_PROVIDER.get(owner.provider, frozenset()):
        raise CredentialStoreError("credential_contract_invalid")


def _parse_access_expiry(kind: str, plaintext: Mapping[str, Any]) -> datetime | None:
    if kind != "avito_oauth_access":
        return None
    raw = plaintext.get("expiresAt") if isinstance(plaintext, Mapping) else None
    if not isinstance(raw, str):
        raise CredentialStoreError("credential_contract_invalid")
    try:
        parsed = datetime.strptime(raw, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError:
        raise CredentialStoreError("credential_contract_invalid") from None
    return parsed


def _account(
    session: Session,
    owner: MarketplaceAccountCredentialOwner,
    *,
    lock: bool,
    expected_external_account_id: str | None = None,
) -> MarketplaceAccountRow:
    query = select(MarketplaceAccountRow).where(
        MarketplaceAccountRow.organization_id == owner.organization_id,
        MarketplaceAccountRow.marketplace_account_id == owner.marketplace_account_id,
        MarketplaceAccountRow.marketplace == owner.provider,
    )
    if lock:
        query = query.with_for_update()
    account = session.scalar(query)
    if account is None:
        raise CredentialStoreError("credential_account_not_found")
    if (
        expected_external_account_id is not None
        and account.external_account_id != expected_external_account_id
    ):
        raise CredentialStoreError("credential_account_identity_mismatch")
    return account


def _active_row(
    session: Session,
    owner: MarketplaceAccountCredentialOwner,
    kind: str,
    *,
    lock: bool,
) -> MarketplaceAccountCredentialRow | None:
    query = (
        select(MarketplaceAccountCredentialRow)
        .where(
            MarketplaceAccountCredentialRow.organization_id == owner.organization_id,
            MarketplaceAccountCredentialRow.marketplace_account_id == owner.marketplace_account_id,
            MarketplaceAccountCredentialRow.provider == owner.provider,
            MarketplaceAccountCredentialRow.credential_kind == kind,
            MarketplaceAccountCredentialRow.revoked_at.is_(None),
        )
        .order_by(MarketplaceAccountCredentialRow.generation.desc())
    )
    if lock:
        query = query.with_for_update()
    return session.scalar(query)


def _latest_row(
    session: Session,
    owner: MarketplaceAccountCredentialOwner,
    kind: str,
) -> MarketplaceAccountCredentialRow | None:
    return session.scalar(
        select(MarketplaceAccountCredentialRow)
        .where(
            MarketplaceAccountCredentialRow.organization_id == owner.organization_id,
            MarketplaceAccountCredentialRow.marketplace_account_id
            == owner.marketplace_account_id,
            MarketplaceAccountCredentialRow.provider == owner.provider,
            MarketplaceAccountCredentialRow.credential_kind == kind,
        )
        .order_by(
            MarketplaceAccountCredentialRow.generation.desc(),
            MarketplaceAccountCredentialRow.created_at.desc(),
        )
    )


def _identity(row: MarketplaceAccountCredentialRow) -> CredentialIdentity:
    return CredentialIdentity(
        organization_id=int(row.organization_id),
        marketplace_account_id=int(row.marketplace_account_id),
        provider=row.provider,
        credential_kind=row.credential_kind,
        payload_schema_version=int(row.payload_schema_version),
        credential_id=row.credential_id,
        generation=int(row.generation),
        expires_at=_as_utc(row.expires_at),
    )


def _encrypted(row: MarketplaceAccountCredentialRow) -> EncryptedCredential:
    return EncryptedCredential(
        algorithm=row.algorithm,
        key_version=int(row.key_version),
        aad_version=int(row.aad_version),
        nonce=bytes(row.nonce),
        ciphertext=bytes(row.ciphertext),
    )


def _metadata(row: MarketplaceAccountCredentialRow) -> CredentialMetadata:
    return CredentialMetadata(
        credential_id=row.credential_id,
        organization_id=int(row.organization_id),
        marketplace_account_id=int(row.marketplace_account_id),
        provider=row.provider,
        credential_kind=row.credential_kind,
        generation=int(row.generation),
        expires_at=_as_utc(row.expires_at),
        revoked_at=_as_utc(row.revoked_at),
        revocation_reason_code=row.revocation_reason_code,
        created_at=_as_utc(row.created_at),
        updated_at=_as_utc(row.updated_at),
    )


def _audit(
    session: Session,
    row: MarketplaceAccountCredentialRow,
    *,
    operation: str,
    actor_user_id: str | None = None,
) -> None:
    session.add(
        LkAuditEventRow(
            organization_id=row.organization_id,
            actor_user_id=actor_user_id,
            action=f"integration.marketplace_credential.{operation}",
            object_type="marketplace_account_credential",
            object_id=str(row.credential_id),
            details={
                "credentialKind": row.credential_kind,
                "generation": int(row.generation),
                "marketplaceAccountId": int(row.marketplace_account_id),
                "operation": operation,
                "provider": row.provider,
                "resultCode": "ready",
            },
        )
    )


def _translate_persistence_error() -> CredentialStoreError:
    return CredentialStoreError("credential_persistence_failed")


def require_marketplace_credential_store_ready() -> None:
    """Fail closed before provider validation when the keyring is unavailable."""

    _load_keyring()


def put_marketplace_credential(
    account_identity: MarketplaceAccountCredentialOwner,
    kind: str,
    plaintext: Mapping[str, Any],
    *,
    actor_user_id: str | None = None,
    expected_external_account_id: str | None = None,
) -> CredentialMetadata:
    _validate_owner(account_identity)
    _validate_kind(account_identity, kind)
    if expected_external_account_id is not None and (
        not isinstance(expected_external_account_id, str)
        or not expected_external_account_id
    ):
        raise CredentialStoreError("credential_contract_invalid")
    expires_at = _parse_access_expiry(kind, plaintext)
    keyring = _load_keyring()
    now = _utc_now()
    with get_session_factory()() as session:
        try:
            set_tenant_context(session, account_identity.organization_id)
            _account(
                session,
                account_identity,
                lock=True,
                expected_external_account_id=expected_external_account_id,
            )
            current = _active_row(session, account_identity, kind, lock=True)
            latest = current or _latest_row(session, account_identity, kind)
            generation = int(latest.generation) + 1 if latest is not None else 1
            if current is not None:
                current.revoked_at = now
                current.revocation_reason_code = "credential_replaced"
                current.updated_at = now
                session.flush()
            identity = CredentialIdentity(
                organization_id=account_identity.organization_id,
                marketplace_account_id=account_identity.marketplace_account_id,
                provider=account_identity.provider,
                credential_kind=kind,
                payload_schema_version=1,
                credential_id=uuid4(),
                generation=generation,
                expires_at=expires_at,
            )
            encrypted = encrypt_credential(identity, plaintext, keyring)
            if decrypt_credential(identity, encrypted, keyring).reveal() != dict(plaintext):
                raise CredentialCryptoError("credential_auth_failed")
            row = MarketplaceAccountCredentialRow(
                credential_id=identity.credential_id,
                organization_id=identity.organization_id,
                marketplace_account_id=identity.marketplace_account_id,
                provider=identity.provider,
                credential_kind=identity.credential_kind,
                algorithm=encrypted.algorithm,
                key_version=encrypted.key_version,
                aad_version=encrypted.aad_version,
                payload_schema_version=identity.payload_schema_version,
                nonce=encrypted.nonce,
                ciphertext=encrypted.ciphertext,
                generation=identity.generation,
                expires_at=identity.expires_at,
                created_at=now,
                updated_at=now,
            )
            session.add(row)
            session.flush()
            _audit(
                session,
                row,
                operation="put",
                actor_user_id=actor_user_id,
            )
            session.commit()
            return _metadata(row)
        except (CredentialCryptoError, CredentialStoreError):
            session.rollback()
            raise
        except (IntegrityError, SQLAlchemyError):
            session.rollback()
            raise _translate_persistence_error() from None


def resolve_marketplace_credential(
    account_identity: MarketplaceAccountCredentialOwner,
    kind: str,
) -> DecryptedCredential:
    _validate_owner(account_identity)
    _validate_kind(account_identity, kind)
    keyring = _load_keyring()
    with get_session_factory()() as session:
        try:
            set_tenant_context(session, account_identity.organization_id)
            _account(session, account_identity, lock=False)
            row = _active_row(session, account_identity, kind, lock=False)
            if row is None:
                raise CredentialStoreError("credential_missing")
            expires_at = _as_utc(row.expires_at)
            if expires_at is not None and expires_at <= _utc_now():
                raise CredentialStoreError("credential_expired")
            return decrypt_credential(_identity(row), _encrypted(row), keyring)
        except (CredentialCryptoError, CredentialStoreError):
            raise
        except SQLAlchemyError:
            raise _translate_persistence_error() from None


def get_marketplace_credential_metadata(
    account_identity: MarketplaceAccountCredentialOwner,
    kind: str,
) -> CredentialMetadata | None:
    _validate_owner(account_identity)
    _validate_kind(account_identity, kind)
    with get_session_factory()() as session:
        try:
            set_tenant_context(session, account_identity.organization_id)
            _account(session, account_identity, lock=False)
            row = _latest_row(session, account_identity, kind)
            return _metadata(row) if row is not None else None
        except CredentialStoreError:
            raise
        except SQLAlchemyError:
            raise _translate_persistence_error() from None


def revoke_marketplace_credential(
    account_identity: MarketplaceAccountCredentialOwner,
    kind: str,
    reason_code: str,
    *,
    actor_user_id: str | None = None,
) -> CredentialMetadata:
    _validate_owner(account_identity)
    _validate_kind(account_identity, kind)
    if reason_code not in _REVOCATION_REASONS:
        raise CredentialStoreError("credential_reason_invalid")
    now = _utc_now()
    with get_session_factory()() as session:
        try:
            set_tenant_context(session, account_identity.organization_id)
            _account(session, account_identity, lock=True)
            row = _active_row(session, account_identity, kind, lock=True)
            if row is None:
                raise CredentialStoreError("credential_missing")
            row.revoked_at = now
            row.revocation_reason_code = reason_code
            row.updated_at = now
            session.flush()
            _audit(
                session,
                row,
                operation="revoke",
                actor_user_id=actor_user_id,
            )
            session.commit()
            return _metadata(row)
        except CredentialStoreError:
            session.rollback()
            raise
        except (IntegrityError, SQLAlchemyError):
            session.rollback()
            raise _translate_persistence_error() from None


def reencrypt_credential(
    credential_id: UUID,
    expected_generation: int,
    target_key_version: int,
) -> CredentialMetadata:
    if (
        not isinstance(credential_id, UUID)
        or not isinstance(expected_generation, int)
        or isinstance(expected_generation, bool)
        or expected_generation < 1
        or not isinstance(target_key_version, int)
        or isinstance(target_key_version, bool)
        or target_key_version < 1
    ):
        raise CredentialStoreError("credential_contract_invalid")
    keyring = _load_keyring()
    target_key = keyring.key_for(target_key_version)
    target_keyring = CredentialKeyring(
        current_key_version=target_key_version,
        keys={target_key_version: target_key},
    )
    now = _utc_now()
    with get_session_factory()() as session:
        try:
            row = session.scalar(
                select(MarketplaceAccountCredentialRow)
                .where(
                    MarketplaceAccountCredentialRow.credential_id == credential_id,
                    MarketplaceAccountCredentialRow.revoked_at.is_(None),
                )
                .with_for_update()
            )
            if row is None:
                raise CredentialStoreError("credential_missing")
            if int(row.generation) != expected_generation:
                raise CredentialStoreError("credential_concurrent_update")
            old_payload = decrypt_credential(_identity(row), _encrypted(row), keyring).reveal()
            new_identity = CredentialIdentity(
                organization_id=int(row.organization_id),
                marketplace_account_id=int(row.marketplace_account_id),
                provider=row.provider,
                credential_kind=row.credential_kind,
                payload_schema_version=int(row.payload_schema_version),
                credential_id=row.credential_id,
                generation=expected_generation + 1,
                expires_at=_as_utc(row.expires_at),
            )
            encrypted = encrypt_credential(new_identity, old_payload, target_keyring)
            verified = decrypt_credential(new_identity, encrypted, target_keyring).reveal()
            if verified != old_payload:
                raise CredentialCryptoError("credential_auth_failed")
            result = session.execute(
                update(MarketplaceAccountCredentialRow)
                .where(
                    MarketplaceAccountCredentialRow.credential_id == credential_id,
                    MarketplaceAccountCredentialRow.generation == expected_generation,
                    MarketplaceAccountCredentialRow.revoked_at.is_(None),
                )
                .values(
                    algorithm=encrypted.algorithm,
                    key_version=encrypted.key_version,
                    aad_version=encrypted.aad_version,
                    nonce=encrypted.nonce,
                    ciphertext=encrypted.ciphertext,
                    generation=new_identity.generation,
                    updated_at=now,
                )
                .execution_options(synchronize_session=False)
            )
            if int(result.rowcount or 0) != 1:
                raise CredentialStoreError("credential_concurrent_update")
            session.expire(row)
            session.refresh(row)
            _audit(session, row, operation="reencrypt")
            session.commit()
            return _metadata(row)
        except (CredentialCryptoError, CredentialStoreError):
            session.rollback()
            raise
        except (IntegrityError, SQLAlchemyError):
            session.rollback()
            raise _translate_persistence_error() from None
