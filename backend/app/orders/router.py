"""Dormant persisted Orders API. Shared application registration belongs to T1."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.config import get_settings
from app.control_plane.auth import ActorContext, actor_from_request
from app.infra.db import get_db_session, set_tenant_context
from app.modules.orders import OrderContractValidationError
from app.orders.contracts import OrderReadPage
from app.orders.cursor import OrdersCursorCodec
from app.orders.http_contracts import OrdersReadPageResponse
from app.orders.read_service import read_orders_page
from app.platform.integrations.publication_guard import (
    ExpectedAccountBinding,
    PublicationGuardError,
    UserSessionPrincipal,
)

router = APIRouter(prefix="/api/v2/orders", tags=["orders"])


def _error(status, code):
    return HTTPException(status_code=status, detail={"code": code})


def get_orders_actor(request: Request) -> ActorContext:
    try:
        return actor_from_request(request)
    except HTTPException:
        raise _error(401, "orders_authentication_required") from None
    except SQLAlchemyError:
        raise _error(503, "orders_storage_unavailable") from None


def get_orders_cursor_codec() -> OrdersCursorCodec:
    try:
        return OrdersCursorCodec(get_settings().auth_secret.encode("utf-8"))
    except (ValueError, TypeError, AttributeError):
        raise _error(503, "orders_cursor_unavailable") from None


def discover_orders_bindings(session, actor, account_ids):
    """Metadata only, not authorization; the next transaction guards exact bindings."""
    if (
        session.in_transaction()
        or not isinstance(actor, ActorContext)
        or not actor.session_id
    ):
        raise PublicationGuardError("publication_context_invalid")
    with session.begin():
        set_tenant_context(session, actor.organization_id)
        membership = session.execute(
            text("""SELECT membership_id FROM iam_memberships
            WHERE organization_id=:org AND user_id=:user AND is_active"""),
            {"org": actor.organization_id, "user": actor.user_id},
        ).scalar_one_or_none()
        if membership is None:
            raise PublicationGuardError("publication_access_denied")
        principal = UserSessionPrincipal(
            actor.organization_id, actor.user_id, membership, actor.session_id
        )
        bindings = []
        for account_id in account_ids:
            row = session.execute(
                text("""SELECT marketplace,external_account_id,credential_ref
                FROM marketplace_accounts WHERE organization_id=:org AND marketplace_account_id=:account"""),
                {"org": actor.organization_id, "account": account_id},
            ).one_or_none()
            if row is None or row.marketplace not in ("wb", "avito"):
                raise PublicationGuardError("publication_access_denied")
            bindings.append(
                ExpectedAccountBinding(
                    account_id,
                    row.marketplace,
                    row.external_account_id,
                    row.credential_ref,
                )
            )
    return principal, tuple(bindings)


@router.get("", response_model=OrdersReadPageResponse)
def get_orders(
    account_id: Annotated[list[int], Query()],
    query_checksum: Annotated[str, Query()],
    actor: Annotated[ActorContext, Depends(get_orders_actor)],
    session: Annotated[Session, Depends(get_db_session)],
    codec: Annotated[OrdersCursorCodec, Depends(get_orders_cursor_codec)],
    snapshot_id: int | None = None,
    cursor: str | None = None,
    limit: int = Query(100, ge=1, le=200),
) -> OrderReadPage:
    # query_checksum selects a prepublished view; it does not implement filters.
    if (
        not account_id
        or len(set(account_id)) != len(account_id)
        or any(value <= 0 for value in account_id)
    ):
        raise _error(400, "orders_account_scope_invalid")
    try:
        principal, bindings = discover_orders_bindings(
            session, actor, tuple(sorted(account_id))
        )
        return read_orders_page(
            session,
            principal=principal,
            accounts=bindings,
            query_checksum=query_checksum,
            snapshot_id=snapshot_id,
            cursor=cursor,
            latest=snapshot_id is None and cursor is None,
            codec=codec,
            limit=limit,
        )
    except PublicationGuardError as exc:
        status = (
            503
            if exc.code
            in ("publication_persistence_failed", "publication_context_invalid")
            else 403
        )
        raise _error(
            status,
            "orders_storage_unavailable" if status == 503 else "orders_access_denied",
        ) from None
    except OrderContractValidationError as exc:
        # Never include token, external IDs or SQL details in the error envelope.
        status = (
            400
            if str(exc)
            in (
                "orders_cursor_invalid",
                "orders_snapshot_selection_invalid",
                "Invalid query checksum",
            )
            else 409
        )
        raise _error(
            status,
            "orders_request_invalid"
            if status == 400
            else "orders_snapshot_unavailable",
        ) from None
    except SQLAlchemyError:
        raise _error(503, "orders_storage_unavailable") from None
