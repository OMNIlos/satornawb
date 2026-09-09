"""Live IAM/session checks shared by account discovery, sync and reads."""
from sqlalchemy import Engine, func, select
from app.cabinet.orm import LkUserRow, LkSessionRow
from app.infra.db import set_tenant_context, set_marketplace_account_context
from app.platform.identity.orm import IamMembershipRow
from app.platform.integrations.orm import MarketplaceAccountRow
from app.platform.integrations.publication_guard import (
    UserSessionPrincipal, ExpectedAccountBinding, PublicationGuardError,
    _scope, acquire_publication_guard,
)
from app.wb_live.contracts import WbLiveError

def require_live_actor(session, actor, *, permission="integrations:write", account_id=None):
    """Root transaction required. Shared metadata locks survive until commit."""
    if (not isinstance(session.get_bind(), Engine) or session.get_bind().dialect.name != "postgresql"
            or not actor.session_id):
        raise WbLiveError("WB_ACCESS_DENIED")
    set_tenant_context(session, actor.organization_id)
    u = session.scalar(select(LkUserRow).where(LkUserRow.user_id == actor.user_id).with_for_update(read=True))
    m = session.scalar(select(IamMembershipRow).where(
        IamMembershipRow.organization_id == actor.organization_id,
        IamMembershipRow.user_id == actor.user_id).with_for_update(read=True))
    login = session.scalar(select(LkSessionRow).where(LkSessionRow.session_id == actor.session_id).with_for_update(read=True))
    now = session.scalar(select(func.clock_timestamp()))
    if (u is None or u.organization_id != actor.organization_id or not u.is_active or m is None or not m.is_active
            or login is None or login.user_id != actor.user_id or login.revoked_at is not None or login.expires_at <= now):
        raise WbLiveError("WB_ACCESS_DENIED")
    scopes = () if account_id is None else (type("AccountScope", (), {"marketplace_account_id": account_id})(),)
    try:
        _scope(m, scopes, frozenset({permission}))
    except PublicationGuardError:
        raise WbLiveError("WB_ACCESS_DENIED") from None
    return UserSessionPrincipal(actor.organization_id, actor.user_id, m.membership_id, actor.session_id), m

def acquire_read_context(session, actor, *, marketplace_account_id):
    """Returns a live publication guard; caller commits after bounded read."""
    principal, _ = require_live_actor(session, actor, permission="catalog:read", account_id=marketplace_account_id)
    a = session.scalar(select(MarketplaceAccountRow).where(
        MarketplaceAccountRow.organization_id == actor.organization_id,
        MarketplaceAccountRow.marketplace_account_id == marketplace_account_id,
        MarketplaceAccountRow.marketplace == "wb"))
    if a is None:
        raise WbLiveError("WB_ACCESS_DENIED")
    guard = acquire_publication_guard(session, principal=principal, required_permissions=frozenset({"catalog:read"}),
        accounts=(ExpectedAccountBinding(marketplace_account_id, "wb", a.external_account_id, a.credential_ref),), authorities=())
    set_marketplace_account_context(session, organization_id=actor.organization_id, marketplace_account_id=marketplace_account_id)
    return guard
