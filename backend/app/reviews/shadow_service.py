"""Dormant WB received-DTO composition, not an HTTP/worker authentication API.

Trusted manual caller reserves before provider I/O with the paired fetch binding.
Finish receives those same DTOs; neither operation fetches, decrypts or logs them.
Running reservations survive failed publication; no automated recovery is implied.
"""

from contextlib import contextmanager
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import Engine, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.control_plane.auth import ActorContext
from app.infra.db import set_tenant_context
from app.platform.identity.orm import IamMembershipRow
from app.platform.integrations.credential_store import (
    CredentialFetchBinding,
    MarketplaceAccountCredentialOwner,
)
from app.platform.integrations.publication_guard import (
    ExpectedAccountBinding,
    ExpectedCredential,
    PublicationGuardError,
    UserSessionPrincipal,
    acquire_publication_guard,
)
from app.reviews.canonical_contract import ReviewNormalizationError, normalize_wb_review
from app.reviews.canonical_repository import (
    ReviewFactsRepository,
    ReviewOwner,
    ReviewRunReference,
)
from app.reviews.canonical_wb_fetch import CanonicalWbFeedbackRow
from app.reviews.ingestion_contract import ReviewRepositoryError, snapshot_manifest
from app.security.marketplace_credentials import CredentialIdentity
from app.wb_api.feedbacks_runtime import WbFeedbackRow

_PERMISSION = frozenset({"reviews:write"})
_CODES = frozenset(
    {
        "REVIEW_SHADOW_INVALID",
        "REVIEW_SHADOW_DENIED",
        "REVIEW_SHADOW_AUTHORITY_CHANGED",
        "REVIEW_SHADOW_EXPIRED",
        "REVIEW_SHADOW_STORAGE_UNAVAILABLE",
        "REVIEW_SHADOW_CONFLICT",
    }
)


class ReviewShadowError(ValueError):
    def __init__(self, code="REVIEW_SHADOW_INVALID"):
        self.code = (
            code if type(code) is str and code in _CODES else "REVIEW_SHADOW_INVALID"
        )
        super().__init__(self.code)


@dataclass(frozen=True, slots=True, repr=False)
class ReviewShadowTicket:
    """Internal metadata, never an authenticated bearer/client payload."""

    principal: UserSessionPrincipal
    account: ExpectedAccountBinding
    authority: ExpectedCredential
    run: ReviewRunReference
    source_run_id: str
    request_checksum: str


@dataclass(frozen=True, slots=True)
class ReviewShadowReceipt:
    sync_run_id: UUID
    manifest_checksum: str
    observed_count: int


@contextmanager
def _safe_errors():
    try:
        yield
    except ReviewShadowError:
        raise
    except PublicationGuardError as error:
        code = {
            "publication_context_invalid": "REVIEW_SHADOW_INVALID",
            "publication_access_denied": "REVIEW_SHADOW_DENIED",
            "publication_binding_changed": "REVIEW_SHADOW_AUTHORITY_CHANGED",
            "publication_authority_invalid": "REVIEW_SHADOW_AUTHORITY_CHANGED",
            "publication_expired": "REVIEW_SHADOW_EXPIRED",
        }.get(error.code, "REVIEW_SHADOW_STORAGE_UNAVAILABLE")
        raise ReviewShadowError(code) from None
    except ReviewRepositoryError as error:
        code = (
            "REVIEW_SHADOW_CONFLICT"
            if error.code in {"REVIEW_REPLAY_CONFLICT", "REVIEW_VERSION_CONFLICT", "REVIEW_HISTORY_BINDING_CONFLICT"}
            else "REVIEW_SHADOW_STORAGE_UNAVAILABLE"
            if error.code == "REVIEW_STORAGE_UNAVAILABLE"
            else "REVIEW_SHADOW_INVALID"
        )
        raise ReviewShadowError(code) from None
    except SQLAlchemyError:
        # Includes failures at physical Session.commit/context exit.
        raise ReviewShadowError("REVIEW_SHADOW_STORAGE_UNAVAILABLE") from None
    except (ReviewNormalizationError, UnicodeError, ValueError, TypeError):
        raise ReviewShadowError() from None


def _engine(engine):
    if not isinstance(engine, Engine) or engine.dialect.name != "postgresql":
        raise ReviewShadowError()
    return engine


def _binding(actor, binding):
    if type(actor) is not ActorContext or not actor.session_id:
        raise ReviewShadowError("REVIEW_SHADOW_DENIED")
    if (
        type(binding) is not CredentialFetchBinding
        or type(binding.owner) is not MarketplaceAccountCredentialOwner
        or type(binding.credential_identity) is not CredentialIdentity
    ):
        raise ReviewShadowError()
    owner, identity = binding.owner, binding.credential_identity
    if (
        owner.provider != "wb"
        or identity.provider != "wb"
        or identity.credential_kind != "wb_api"
        or owner.organization_id != actor.organization_id
        or identity.organization_id != owner.organization_id
        or identity.marketplace_account_id != owner.marketplace_account_id
    ):
        raise ReviewShadowError("REVIEW_SHADOW_AUTHORITY_CHANGED")
    return (
        ExpectedAccountBinding(
            owner.marketplace_account_id,
            "wb",
            binding.external_account_id,
            binding.credential_ref,
        ),
        ExpectedCredential(
            identity.marketplace_account_id,
            identity.credential_id,
            identity.credential_kind,
            identity.generation,
            identity.payload_schema_version,
            identity.expires_at,
        ),
    )


def _repository(session, principal, account):
    return ReviewFactsRepository(
        session.connection(),
        ReviewOwner(
            principal.organization_id,
            account.marketplace_account_id,
            "wb",
            account.external_account_id,
            account.credential_ref,
        ),
        command_savepoints=False,
    )


def begin_review_shadow(engine, *, actor, binding, source_run_id, request_checksum):
    with _safe_errors():
        account, authority = _binding(actor, binding)
        with Session(_engine(engine)) as session, session.begin():
            set_tenant_context(session, actor.organization_id)
            member = session.execute(
                select(IamMembershipRow.membership_id).where(
                    IamMembershipRow.organization_id == actor.organization_id,
                    IamMembershipRow.user_id == actor.user_id,
                )
            ).scalar_one_or_none()
            if member is None:
                raise ReviewShadowError("REVIEW_SHADOW_DENIED")
            principal = UserSessionPrincipal(
                actor.organization_id, actor.user_id, member, actor.session_id
            )
            guard = acquire_publication_guard(
                session,
                principal=principal,
                required_permissions=_PERMISSION,
                accounts=(account,),
                authorities=(authority,),
            )
            now = guard.revalidate_before_write()
            run = _repository(session, principal, account).reserve_run(
                source_run_id=source_run_id,
                request_checksum=request_checksum,
                started_at=now,
            )
            ticket = ReviewShadowTicket(
                principal, account, authority, run, source_run_id, request_checksum
            )
        return ticket


def publish_received_review_rows(engine, *, ticket, rows, coverage):
    with _safe_errors():
        if (
            type(ticket) is not ReviewShadowTicket
            or type(ticket.run) is not ReviewRunReference
            or type(rows) is not tuple
            or not all(
                type(row) in (WbFeedbackRow, CanonicalWbFeedbackRow) for row in rows
            )
            or type(ticket.account) is not ExpectedAccountBinding
            or ticket.account.provider != "wb"
            or type(ticket.authority) is not ExpectedCredential
            or ticket.authority.kind != "wb_api"
        ):
            raise ReviewShadowError()
        with Session(_engine(engine)) as session, session.begin():
            guard = acquire_publication_guard(
                session,
                principal=ticket.principal,
                required_permissions=_PERMISSION,
                accounts=(ticket.account,),
                authorities=(ticket.authority,),
            )
            now = guard.revalidate_before_write()
            facts = tuple(
                normalize_wb_review(
                    row,
                    ticket.principal.organization_id,
                    ticket.account.marketplace_account_id,
                    ticket.source_run_id,
                    now,
                )
                for row in rows
            )
            snapshot_manifest(
                facts,
                coverage,
                "partial",
                {f.identity.external_review_id: 0 for f in facts},
            )
            repo = _repository(session, ticket.principal, ticket.account)
            run = repo.reserve_run(
                source_run_id=ticket.source_run_id,
                request_checksum=ticket.request_checksum,
                started_at=now,
            )
            if run != ticket.run:
                raise ReviewShadowError("REVIEW_SHADOW_CONFLICT")
            versions = {}
            for fact in facts:
                current = repo.get_fact(fact.identity.external_review_id)
                versions[fact.identity.external_review_id] = (
                    0 if current is None else current.version
                )
            now = guard.revalidate_before_write()
            manifest = repo.ingest(
                run.sync_run_id,
                facts=facts,
                coverage=coverage,
                completeness="partial",
                completed_at=now,
                expected_versions=versions,
            )
            receipt = ReviewShadowReceipt(run.sync_run_id, manifest, len(facts))
        return receipt
