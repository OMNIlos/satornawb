from __future__ import annotations

from fastapi import HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.control_plane.auth import ActorContext, actor_from_request, has_permission
from app.infra.db import set_tenant_context
from app.platform.identity.orm import IamMembershipRow
from app.platform.integrations.orm import MarketplaceAccountRow


def get_finance_actor(request: Request) -> ActorContext:
    return actor_from_request(request)


def require_finance_read(actor: ActorContext) -> None:
    if not has_permission(actor, "finance:read"):
        raise HTTPException(
            status_code=403,
            detail={"code": "NO_ACCESS", "message": "NO_ACCESS:finance:read"},
        )


def require_wb_account_scope(
    session: Session, actor: ActorContext, marketplace_account_id: int
) -> None:
    set_tenant_context(session, actor.organization_id)
    account = session.scalar(
        select(MarketplaceAccountRow.marketplace_account_id).where(
            MarketplaceAccountRow.organization_id == actor.organization_id,
            MarketplaceAccountRow.marketplace_account_id == marketplace_account_id,
            MarketplaceAccountRow.marketplace == "wb",
        )
    )
    if account is None:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "WB_ACCOUNT_NOT_FOUND",
                "message": "WB marketplace account not found",
            },
        )
    membership = session.scalar(
        select(IamMembershipRow).where(
            IamMembershipRow.organization_id == actor.organization_id,
            IamMembershipRow.user_id == actor.user_id,
            IamMembershipRow.is_active.is_(True),
        )
    )
    allowed = membership is not None and (
        membership.scope_mode == "all"
        or marketplace_account_id
        in {
            int(value)
            for value in membership.allowed_account_ids
            if str(value).isdigit()
        }
    )
    if not allowed:
        raise HTTPException(
            status_code=403,
            detail={
                "code": "ACCOUNT_SCOPE_DENIED",
                "message": "WB account is outside membership scope",
            },
        )
