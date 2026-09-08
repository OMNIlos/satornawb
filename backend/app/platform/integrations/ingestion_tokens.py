"""Account-owned Avito ingestion-token lifecycle boundary."""

from __future__ import annotations

import hashlib
import hmac
import re
import secrets
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Literal
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.cabinet.orm import LkAuditEventRow
from app.infra.db import get_session_factory, set_tenant_context
from app.platform.integrations.credential_store import MarketplaceAccountCredentialOwner
from app.platform.integrations.orm import (
    MarketplaceAccountIngestionTokenRow,
    MarketplaceAccountRow,
)

INGESTION_TOKEN_SCOPE = "avito.browser_snapshot.write"
_TOKEN_PREFIX = "sat1"
_MAX_ORGANIZATION_ID = (1 << 63) - 1
_SECRET_BYTES = 32
_SECRET_LENGTH = 43
_MIN_BEARER_LENGTH = len(_TOKEN_PREFIX) + 3 + 1 + 32 + _SECRET_LENGTH
_MAX_BEARER_LENGTH = len(_TOKEN_PREFIX) + 3 + 19 + 32 + _SECRET_LENGTH
_UUID_HEX = re.compile(r"[0-9a-f]{32}\Z", re.ASCII)
_URLSAFE_SECRET = re.compile(r"[A-Za-z0-9_-]{43}\Z", re.ASCII)
_REVOCATION_REASONS = frozenset(
    {
        "token_rotated",
        "account_disconnected",
        "security_incident",
        "operator_revoked",
        "expired",
    }
)
_SAFE_ERROR_CODES = frozenset(
    {
        "ingestion_token_account_unavailable",
        "ingestion_token_already_revealed",
        "ingestion_token_contract_invalid",
        "ingestion_token_invalid",
        "ingestion_token_reason_invalid",
        "ingestion_token_serialization_refused",
        "ingestion_token_unavailable",
    }
)


class IngestionTokenStoreError(ValueError):
    """Fail-closed token-store error with a non-disclosing public form."""

    def __init__(self, code: str) -> None:
        self.code = code if code in _SAFE_ERROR_CODES else "ingestion_token_unavailable"
        super().__init__(self.code)

    def __repr__(self) -> str:
        return f"IngestionTokenStoreError(code={self.code!r})"


@dataclass(frozen=True)
class IngestionTokenMetadata:
    token_id: UUID
    organization_id: int
    marketplace_account_id: int
    provider: str
    scope: str
    issued_at: datetime
    expires_at: datetime
    revoked_at: datetime | None
    revocation_reason_code: str | None
    last_used_at: datetime | None
    status: Literal["active", "expired", "revoked"]


@dataclass(frozen=True)
class VerifiedIngestionToken:
    token_id: UUID
    owner: MarketplaceAccountCredentialOwner
    scope: str
    expires_at: datetime


class IssuedIngestionToken:
    """A one-time bearer reveal paired with metadata safe for serialization."""

    __slots__ = ("_metadata", "_raw_bearer")

    def __init__(self, metadata: IngestionTokenMetadata, raw_bearer: str) -> None:
        self._metadata = metadata
        self._raw_bearer: str | None = raw_bearer

    @property
    def metadata(self) -> IngestionTokenMetadata:
        return self._metadata

    def reveal(self) -> str:
        raw_bearer = self._raw_bearer
        if raw_bearer is None:
            raise IngestionTokenStoreError("ingestion_token_already_revealed")
        self._raw_bearer = None
        return raw_bearer

    def __repr__(self) -> str:
        return "<IssuedIngestionToken redacted>"

    __str__ = __repr__

    def __reduce_ex__(self, _protocol: int):
        raise IngestionTokenStoreError("ingestion_token_serialization_refused")


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _positive_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def _validate_owner(owner: MarketplaceAccountCredentialOwner) -> None:
    if (
        not isinstance(owner, MarketplaceAccountCredentialOwner)
        or not _positive_int(owner.organization_id)
        or not _positive_int(owner.marketplace_account_id)
        or owner.organization_id > _MAX_ORGANIZATION_ID
        or owner.marketplace_account_id > _MAX_ORGANIZATION_ID
        or owner.provider != "avito"
    ):
        raise IngestionTokenStoreError("ingestion_token_contract_invalid")


def _validate_expiry(expires_at: datetime, now: datetime) -> datetime:
    if (
        not isinstance(expires_at, datetime)
        or expires_at.tzinfo is None
        or expires_at.utcoffset() is None
    ):
        raise IngestionTokenStoreError("ingestion_token_contract_invalid")
    try:
        normalized = expires_at.astimezone(timezone.utc)
    except (OverflowError, ValueError):
        raise IngestionTokenStoreError("ingestion_token_contract_invalid") from None
    if normalized <= now:
        raise IngestionTokenStoreError("ingestion_token_contract_invalid")
    return normalized


def _parse_bearer(raw_bearer: str) -> tuple[int, UUID, str]:
    if (
        not isinstance(raw_bearer, str)
        or len(raw_bearer) < _MIN_BEARER_LENGTH
        or len(raw_bearer) > _MAX_BEARER_LENGTH
    ):
        raise IngestionTokenStoreError("ingestion_token_invalid")
    parts = raw_bearer.split(".")
    if len(parts) != 4:
        raise IngestionTokenStoreError("ingestion_token_invalid")
    prefix, organization_text, token_text, secret = parts
    if (
        prefix != _TOKEN_PREFIX
        or not organization_text.isascii()
        or not organization_text.isdecimal()
        or organization_text.startswith("0")
        or len(organization_text) > 19
        or _UUID_HEX.fullmatch(token_text) is None
        or _URLSAFE_SECRET.fullmatch(secret) is None
    ):
        raise IngestionTokenStoreError("ingestion_token_invalid")
    organization_id = int(organization_text)
    if organization_id < 1 or organization_id > _MAX_ORGANIZATION_ID:
        raise IngestionTokenStoreError("ingestion_token_invalid")
    return organization_id, UUID(hex=token_text), secret


def _new_session() -> Session:
    try:
        return get_session_factory()()
    except SQLAlchemyError:
        raise IngestionTokenStoreError("ingestion_token_unavailable") from None


def _rollback_safely(session: Session) -> None:
    try:
        session.rollback()
    except SQLAlchemyError:
        pass


def _close_safely(session: Session) -> None:
    try:
        session.close()
    except SQLAlchemyError:
        pass


def _account(
    session: Session,
    owner: MarketplaceAccountCredentialOwner,
    *,
    lock: bool,
) -> MarketplaceAccountRow | None:
    query = select(MarketplaceAccountRow).where(
        MarketplaceAccountRow.organization_id == owner.organization_id,
        MarketplaceAccountRow.marketplace_account_id == owner.marketplace_account_id,
        MarketplaceAccountRow.marketplace == owner.provider,
    )
    if lock:
        query = query.with_for_update().execution_options(populate_existing=True)
    return session.scalar(query)


def _require_connected_account(
    session: Session,
    owner: MarketplaceAccountCredentialOwner,
    *,
    lock: bool,
    verifier: bool = False,
) -> MarketplaceAccountRow:
    account = _account(session, owner, lock=lock)
    if account is None or account.status != "connected":
        code = (
            "ingestion_token_invalid"
            if verifier
            else "ingestion_token_account_unavailable"
        )
        raise IngestionTokenStoreError(code)
    return account


def _owner_rows(
    session: Session,
    owner: MarketplaceAccountCredentialOwner,
    *,
    active_only: bool,
    lock: bool,
) -> list[MarketplaceAccountIngestionTokenRow]:
    query = select(MarketplaceAccountIngestionTokenRow).where(
        MarketplaceAccountIngestionTokenRow.organization_id == owner.organization_id,
        MarketplaceAccountIngestionTokenRow.marketplace_account_id
        == owner.marketplace_account_id,
        MarketplaceAccountIngestionTokenRow.provider == "avito",
        MarketplaceAccountIngestionTokenRow.scope == INGESTION_TOKEN_SCOPE,
    )
    if active_only:
        query = query.where(MarketplaceAccountIngestionTokenRow.revoked_at.is_(None))
    query = query.order_by(
        MarketplaceAccountIngestionTokenRow.issued_at,
        MarketplaceAccountIngestionTokenRow.token_id,
    )
    if lock:
        query = query.with_for_update()
    return list(session.scalars(query).all())


def _token_row(
    session: Session,
    *,
    organization_id: int,
    token_id: UUID,
    lock: bool,
) -> MarketplaceAccountIngestionTokenRow | None:
    query = select(MarketplaceAccountIngestionTokenRow).where(
        MarketplaceAccountIngestionTokenRow.organization_id == organization_id,
        MarketplaceAccountIngestionTokenRow.token_id == token_id,
        MarketplaceAccountIngestionTokenRow.provider == "avito",
        MarketplaceAccountIngestionTokenRow.scope == INGESTION_TOKEN_SCOPE,
    )
    if lock:
        query = query.with_for_update().execution_options(populate_existing=True)
    return session.scalar(query)


def _latest_owner_row(
    session: Session,
    owner: MarketplaceAccountCredentialOwner,
) -> MarketplaceAccountIngestionTokenRow | None:
    return session.scalar(
        select(MarketplaceAccountIngestionTokenRow)
        .where(
            MarketplaceAccountIngestionTokenRow.organization_id
            == owner.organization_id,
            MarketplaceAccountIngestionTokenRow.marketplace_account_id
            == owner.marketplace_account_id,
            MarketplaceAccountIngestionTokenRow.provider == "avito",
            MarketplaceAccountIngestionTokenRow.scope == INGESTION_TOKEN_SCOPE,
        )
        .order_by(
            MarketplaceAccountIngestionTokenRow.revoked_at.is_(None).desc(),
            MarketplaceAccountIngestionTokenRow.issued_at.desc(),
            MarketplaceAccountIngestionTokenRow.token_id.desc(),
        )
        .limit(1)
    )


def _metadata(
    row: MarketplaceAccountIngestionTokenRow, *, now: datetime
) -> IngestionTokenMetadata:
    issued_at = _as_utc(row.issued_at)
    expires_at = _as_utc(row.expires_at)
    revoked_at = _as_utc(row.revoked_at)
    last_used_at = _as_utc(row.last_used_at)
    if issued_at is None or expires_at is None:
        raise IngestionTokenStoreError("ingestion_token_unavailable")
    if revoked_at is not None:
        status: Literal["active", "expired", "revoked"] = "revoked"
    elif expires_at <= now:
        status = "expired"
    else:
        status = "active"
    return IngestionTokenMetadata(
        token_id=row.token_id,
        organization_id=int(row.organization_id),
        marketplace_account_id=int(row.marketplace_account_id),
        provider=row.provider,
        scope=row.scope,
        issued_at=issued_at,
        expires_at=expires_at,
        revoked_at=revoked_at,
        revocation_reason_code=row.revocation_reason_code,
        last_used_at=last_used_at,
        status=status,
    )


def _audit(
    session: Session,
    row: MarketplaceAccountIngestionTokenRow,
    *,
    operation: Literal["issue", "revoke"],
    result_code: str,
    actor_user_id: str | None,
) -> None:
    session.add(
        LkAuditEventRow(
            organization_id=int(row.organization_id),
            actor_user_id=actor_user_id,
            action=f"integration.marketplace_ingestion_token.{operation}",
            object_type="marketplace_account_ingestion_token",
            object_id=str(row.token_id),
            details={
                "marketplaceAccountId": int(row.marketplace_account_id),
                "operation": operation,
                "provider": "avito",
                "resultCode": result_code,
                "scope": INGESTION_TOKEN_SCOPE,
            },
        )
    )


def issue_ingestion_token(
    owner: MarketplaceAccountCredentialOwner,
    *,
    expires_at: datetime,
    actor_user_id: str | None = None,
) -> IssuedIngestionToken:
    _validate_owner(owner)
    now = _utc_now()
    normalized_expiry = _validate_expiry(expires_at, now)
    session = _new_session()
    try:
        set_tenant_context(session, owner.organization_id)
        _require_connected_account(session, owner, lock=True)
        current_rows = _owner_rows(session, owner, active_only=True, lock=True)
        for current in current_rows:
            current.revoked_at = now
            current.revocation_reason_code = "token_rotated"
        if current_rows:
            session.flush()

        secret = secrets.token_urlsafe(_SECRET_BYTES)
        if _URLSAFE_SECRET.fullmatch(secret) is None:
            raise IngestionTokenStoreError("ingestion_token_unavailable")
        token_id = uuid4()
        row = MarketplaceAccountIngestionTokenRow(
            token_id=token_id,
            organization_id=owner.organization_id,
            marketplace_account_id=owner.marketplace_account_id,
            provider="avito",
            verifier=hashlib.sha256(secret.encode("ascii")).digest(),
            scope=INGESTION_TOKEN_SCOPE,
            issued_at=now,
            expires_at=normalized_expiry,
        )
        session.add(row)
        session.flush()
        _audit(
            session,
            row,
            operation="issue",
            result_code="issued",
            actor_user_id=actor_user_id,
        )
        session.commit()
        metadata = _metadata(row, now=now)
        raw_bearer = f"{_TOKEN_PREFIX}.{owner.organization_id}.{token_id.hex}.{secret}"
        return IssuedIngestionToken(metadata, raw_bearer)
    except IngestionTokenStoreError:
        _rollback_safely(session)
        raise
    except (IntegrityError, SQLAlchemyError):
        _rollback_safely(session)
        raise IngestionTokenStoreError("ingestion_token_unavailable") from None
    finally:
        _close_safely(session)


def verify_ingestion_token(raw_bearer: str) -> VerifiedIngestionToken:
    organization_id, token_id, secret = _parse_bearer(raw_bearer)
    now = _utc_now()
    candidate_verifier = hashlib.sha256(secret.encode("ascii")).digest()
    session = _new_session()
    try:
        set_tenant_context(session, organization_id)
        candidate = _token_row(
            session,
            organization_id=organization_id,
            token_id=token_id,
            lock=False,
        )
        if candidate is None:
            raise IngestionTokenStoreError("ingestion_token_invalid")
        owner = MarketplaceAccountCredentialOwner(
            organization_id=organization_id,
            marketplace_account_id=int(candidate.marketplace_account_id),
            provider="avito",
        )

        # Global lock order is account row, then token row. The unlocked locator
        # read is repeated under the token lock before any successful use.
        _require_connected_account(session, owner, lock=True, verifier=True)
        row = _token_row(
            session,
            organization_id=organization_id,
            token_id=token_id,
            lock=True,
        )
        if (
            row is None
            or int(row.marketplace_account_id) != owner.marketplace_account_id
        ):
            raise IngestionTokenStoreError("ingestion_token_invalid")
        stored_verifier = bytes(row.verifier)
        secret_matches = hmac.compare_digest(stored_verifier, candidate_verifier)
        expires_at = _as_utc(row.expires_at)
        if (
            not secret_matches
            or len(stored_verifier) != hashlib.sha256().digest_size
            or row.revoked_at is not None
            or expires_at is None
            or expires_at <= now
        ):
            raise IngestionTokenStoreError("ingestion_token_invalid")
        row.last_used_at = now
        session.flush()
        session.commit()
        return VerifiedIngestionToken(
            token_id=row.token_id,
            owner=owner,
            scope=INGESTION_TOKEN_SCOPE,
            expires_at=expires_at,
        )
    except IngestionTokenStoreError:
        _rollback_safely(session)
        raise
    except (IntegrityError, SQLAlchemyError):
        _rollback_safely(session)
        raise IngestionTokenStoreError("ingestion_token_unavailable") from None
    finally:
        _close_safely(session)


def revoke_ingestion_tokens(
    owner: MarketplaceAccountCredentialOwner,
    reason_code: str,
    *,
    actor_user_id: str | None = None,
) -> tuple[IngestionTokenMetadata, ...]:
    _validate_owner(owner)
    if reason_code not in _REVOCATION_REASONS:
        raise IngestionTokenStoreError("ingestion_token_reason_invalid")
    now = _utc_now()
    session = _new_session()
    try:
        set_tenant_context(session, owner.organization_id)
        _require_connected_account(session, owner, lock=True)
        rows = _owner_rows(session, owner, active_only=True, lock=True)
        for row in rows:
            row.revoked_at = now
            row.revocation_reason_code = reason_code
            _audit(
                session,
                row,
                operation="revoke",
                result_code=reason_code,
                actor_user_id=actor_user_id,
            )
        if rows:
            session.flush()
        session.commit()
        return tuple(_metadata(row, now=now) for row in rows)
    except IngestionTokenStoreError:
        _rollback_safely(session)
        raise
    except (IntegrityError, SQLAlchemyError):
        _rollback_safely(session)
        raise IngestionTokenStoreError("ingestion_token_unavailable") from None
    finally:
        _close_safely(session)


def get_ingestion_token_status(
    owner: MarketplaceAccountCredentialOwner,
) -> IngestionTokenMetadata | None:
    _validate_owner(owner)
    now = _utc_now()
    session = _new_session()
    try:
        set_tenant_context(session, owner.organization_id)
        _require_connected_account(session, owner, lock=False)
        row = _latest_owner_row(session, owner)
        if row is None:
            return None
        return _metadata(row, now=now)
    except IngestionTokenStoreError:
        _rollback_safely(session)
        raise
    except SQLAlchemyError:
        _rollback_safely(session)
        raise IngestionTokenStoreError("ingestion_token_unavailable") from None
    finally:
        _close_safely(session)
