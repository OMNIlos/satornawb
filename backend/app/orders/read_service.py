"""Guarded persisted reads; authenticated principal comes from the calling adapter."""

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.orders.snapshot_repository import OrdersSnapshotRepository, SnapshotChunk
from app.platform.integrations.publication_guard import (
    ExpectedAccountBinding,
    PublicationGuardError,
    UserSessionPrincipal,
    acquire_publication_guard,
)


def read_orders_snapshot(
    session: Session,
    *,
    principal: UserSessionPrincipal,
    accounts: tuple[ExpectedAccountBinding, ...],
    snapshot_id: int,
    query_checksum: str,
    after_position: int = 0,
    limit: int = 100,
) -> SnapshotChunk:
    """Own one clean transaction and return only after final authorization succeeds.

    The caller supplies authenticated session/membership identity and exact account
    bindings, not permissions. No credentials are needed to read persisted facts.
    This is not an HTTP endpoint or a signed cursor parser.
    """
    if not isinstance(session, Session) or session.in_transaction():
        raise PublicationGuardError("publication_context_invalid")
    try:
        with session.begin():
            guard = acquire_publication_guard(
                session,
                principal=principal,
                required_permissions=frozenset({"cabinet:read"}),
                accounts=accounts,
                authorities=(),
            )
            result = OrdersSnapshotRepository(session, principal.organization_id).read(
                snapshot_id,
                tuple(sorted(account.marketplace_account_id for account in accounts)),
                query_checksum,
                after_position=after_position,
                limit=limit,
            )
            guard.revalidate_before_write()
        return result
    except SQLAlchemyError:
        raise PublicationGuardError("publication_persistence_failed") from None
