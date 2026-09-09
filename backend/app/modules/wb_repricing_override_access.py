"""SKU-override-specific access in a caller-owned PostgreSQL root transaction.

Not a repository, receipt reader, committed service or provider capability. The
eventual service calls this before domain lookup/locks, keeps the same physical
root through revision/head/audit work, and returns only after commit. Existing
publication guard owns final live-auth validation. No new permission policy.
"""

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.cabinet.permissions import (
    WB_SKU_OVERRIDE_READ_PERMISSIONS,
    WB_SKU_OVERRIDE_REPLACE_PERMISSIONS,
)
from app.infra.db import set_marketplace_account_context
from app.modules.wb_repricing_overrides import OverrideChange
from app.platform.integrations.publication_guard import (
    ExpectedAccountBinding,
    PublicationGuardError,
    UserSessionPrincipal,
    acquire_publication_guard,
)


class OverrideMappingUnresolvedError(ValueError):
    """A domain blocker, not an authentication or database failure."""

    def __init__(self):
        self.code = "override_mapping_unresolved"
        super().__init__(self.code)


def _acquire(
    session, organization_id, marketplace_account_id, principal, binding, permissions
):
    if (
        type(organization_id) is not int
        or not 0 < organization_id < 2**31
        or type(marketplace_account_id) is not int
        or not 0 < marketplace_account_id < 2**31
        or type(principal) is not UserSessionPrincipal
        or type(binding) is not ExpectedAccountBinding
        or principal.organization_id != organization_id
        or binding.marketplace_account_id != marketplace_account_id
        or binding.provider != "wb"
    ):
        raise PublicationGuardError("publication_context_invalid")
    guard = acquire_publication_guard(
        session,
        principal=principal,
        required_permissions=permissions,
        accounts=(binding,),
        authorities=(),
    )
    try:
        set_marketplace_account_context(
            session,
            organization_id=organization_id,
            marketplace_account_id=marketplace_account_id,
        )
    except SQLAlchemyError:
        raise PublicationGuardError("publication_persistence_failed") from None
    return guard


def acquire_override_read_guard(
    session, *, organization_id, marketplace_account_id, principal, binding
):
    """Authorize historical scoped reads; no requirement for a current offer mapping."""
    return _acquire(
        session,
        organization_id,
        marketplace_account_id,
        principal,
        binding,
        WB_SKU_OVERRIDE_READ_PERMISSIONS,
    )


def acquire_override_replace_guard(session, *, change, principal, binding):
    """Require BOTH permissions and freeze a current scoped mapping for new mutation.

    Not an exact-command replay entry point: the future service must authorize
    BOTH permissions before receipt lookup, then require mapping only for a new
    revision. A historical replay does not become a new mutation after remapping.
    This does not prove an immutable historical mapping version. Lock all matching
    current offers in PK order; SHARE conflicts with changing catalog_sku_id, unlike
    KEY SHARE. No guessed offer status grammar, article lookup or nmId-to-size map.
    """
    if (
        type(change) is not OverrideChange
        or type(principal) is not UserSessionPrincipal
    ):
        raise PublicationGuardError("publication_context_invalid")
    change.__post_init__()
    if change.actor_membership_id != principal.membership_id:
        raise PublicationGuardError("publication_context_invalid")
    guard = _acquire(
        session,
        change.organization_id,
        change.marketplace_account_id,
        principal,
        binding,
        WB_SKU_OVERRIDE_REPLACE_PERMISSIONS,
    )
    try:
        mapped = (
            session.execute(
                text(
                    "SELECT marketplace_offer_id FROM marketplace_offers "
                    "WHERE organization_id=:org AND marketplace_account_id=:account "
                    "AND catalog_sku_id=:sku ORDER BY marketplace_offer_id FOR SHARE"
                ),
                {
                    "org": change.organization_id,
                    "account": change.marketplace_account_id,
                    "sku": change.catalog_sku_id,
                },
            )
            .scalars()
            .all()
        )
    except SQLAlchemyError:
        raise PublicationGuardError("publication_persistence_failed") from None
    if not mapped:
        raise OverrideMappingUnresolvedError()
    guard.revalidate_before_write()
    return guard
