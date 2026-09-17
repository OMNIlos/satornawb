from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.contracts.envelopes import DataEnvelope, PaginatedEnvelope, UtcDateTime
from app.control_plane.auth import ActorContext, actor_from_request, has_permission
from app.infra.db import get_db_session
from app.platform.catalog.schemas import (
    CatalogSkuView,
    MarketplaceOfferView,
    ProductionMarketplaceLinkView,
    ProductionSkuView,
    WbProductView,
)
from app.platform.catalog.service import (
    CatalogService,
    CatalogSku,
    MarketplaceProduct,
    ProductionSku,
)
from app.platform.economics.costs import (
    CostConflictError,
    CostNotFoundError,
    CostValidationError,
    CostValue,
    CostsService,
)
from app.platform.economics.schemas import CostSetRequest, CostView, CurrentCostSetRequest
from app.platform.catalog.orm import MarketplaceOfferRow
from app.platform.identity.orm import IamMembershipRow
from app.platform.integrations.orm import MarketplaceAccountRow
from app.repricer_cache.orm import WbRepricerGoodsCacheRow
from app.repricer_sync import (
    _good_buyer_price_no_wallet_kopecks,
    _good_seller_price_kopecks,
)

router = APIRouter(tags=["catalog-v2"])


def get_catalog_actor(request: Request) -> ActorContext:
    return actor_from_request(request)


def _require(actor: ActorContext, permission: str) -> None:
    if not has_permission(actor, permission):
        raise HTTPException(
            status_code=403,
            detail={"code": "NO_ACCESS", "message": f"NO_ACCESS:{permission}"},
        )


def _require_cost_sku_scope(session: Session, actor: ActorContext, catalog_sku_id: int) -> None:
    from app.infra.db import set_tenant_context
    set_tenant_context(session, actor.organization_id)
    membership = session.scalar(select(IamMembershipRow).where(
        IamMembershipRow.organization_id == actor.organization_id,
        IamMembershipRow.user_id == actor.user_id, IamMembershipRow.is_active.is_(True)))
    if membership is None:
        raise HTTPException(status_code=403, detail={"code": "NO_ACCESS"})
    if membership.scope_mode != "all":
        accounts = set(session.scalars(select(MarketplaceOfferRow.marketplace_account_id).where(
            MarketplaceOfferRow.organization_id == actor.organization_id,
            MarketplaceOfferRow.catalog_sku_id == catalog_sku_id)).all())
        if not accounts or not accounts.issubset(set(membership.allowed_account_ids or [])):
            raise HTTPException(status_code=403, detail={"code": "NO_ACCESS"})


def _cost_view(cost: CostValue, *, visible: bool) -> CostView:
    if not visible:
        return CostView(valueState="restricted")
    return CostView(
        costVersionId=cost.cost_version_id,
        amountKopecks=cost.amount_kopecks,
        valueState=cost.value_state,
        effectiveFrom=cost.effective_from,
        source=cost.source,
        sourceReference=cost.source_reference,
        evidenceStatus=cost.evidence_status,
        supersedesCostVersionId=cost.supersedes_cost_version_id,
        createdAt=cost.created_at,
    )


def _sku_view(sku: CatalogSku, *, costs_visible: bool) -> CatalogSkuView:
    return CatalogSkuView(
        catalogSkuId=sku.catalog_sku_id,
        code=sku.code,
        printId=sku.print_id,
        productType=sku.product_type,
        color=sku.color,
        size=sku.size,
        managerMembershipId=sku.manager_membership_id,
        currentCost=_cost_view(sku.current_cost, visible=costs_visible),
        createdAt=sku.created_at,
        updatedAt=sku.updated_at,
    )


def _goods_by_nm_id(session: Session, organization_id: int) -> dict[str, dict]:
    pages = session.scalars(
        select(WbRepricerGoodsCacheRow)
        .where(WbRepricerGoodsCacheRow.organization_id == organization_id)
        .order_by(WbRepricerGoodsCacheRow.page_offset.asc())
    ).all()
    rows = [
        item for page in pages for item in page.goods_payload if isinstance(item, dict)
    ]
    return {
        str(raw_nm_id): row
        for row in rows
        if isinstance(row, dict)
        and (raw_nm_id := row.get("nmID") or row.get("nmId")) is not None
    }


def _wb_product_view(
    product: MarketplaceProduct,
    *,
    costs_visible: bool,
    goods_by_nm_id: dict[str, dict],
) -> WbProductView:
    snapshot = goods_by_nm_id.get(product.external_product_id)
    snapshot_status = None
    if snapshot is not None:
        raw_status = snapshot.get("productStatus") or snapshot.get("status")
        snapshot_status = str(raw_status).strip() if raw_status is not None else None
    return WbProductView(
        marketplaceProductId=product.marketplace_product_id,
        marketplaceAccountId=product.marketplace_account_id,
        externalProductId=product.external_product_id,
        sellerArticle=product.seller_article,
        brand=product.brand,
        title=product.title,
        imageUrl=product.image_url,
        productStatus=snapshot_status or product.product_status,
        priceBeforeSppKopecks=(
            _good_seller_price_kopecks(snapshot) if snapshot is not None else None
        ),
        priceAfterSppKopecks=(
            _good_buyer_price_no_wallet_kopecks(snapshot)
            if snapshot is not None
            else None
        ),
        priceSnapshotAvailable=snapshot is not None,
        offers=[
            MarketplaceOfferView(
                marketplaceOfferId=offer.marketplace_offer_id,
                externalOfferKey=offer.external_offer_key,
                offerStatus=offer.offer_status,
                catalogSku=(
                    _sku_view(offer.catalog_sku, costs_visible=costs_visible)
                    if offer.catalog_sku
                    else None
                ),
            )
            for offer in product.offers
        ],
        createdAt=product.created_at,
        updatedAt=product.updated_at,
    )


def _production_sku_view(
    row: ProductionSku, *, costs_visible: bool
) -> ProductionSkuView:
    sku = _sku_view(row.sku, costs_visible=costs_visible)
    return ProductionSkuView(
        **sku.model_dump(),
        marketplaceLinks=[
            ProductionMarketplaceLinkView(
                marketplace=link.marketplace,
                marketplaceAccountId=link.marketplace_account_id,
                marketplaceProductId=link.marketplace_product_id,
                externalProductId=link.external_product_id,
                externalOfferKey=link.external_offer_key,
                sellerArticle=link.seller_article,
                title=link.title,
                productStatus=link.product_status,
                offerStatus=link.offer_status,
            )
            for link in row.marketplace_links
        ],
    )


def _not_found(exc: CostNotFoundError) -> HTTPException:
    return HTTPException(
        status_code=404,
        detail={"code": "CATALOG_SKU_NOT_FOUND", "message": str(exc)},
    )


@router.get("/api/v2/catalog/skus", response_model=PaginatedEnvelope[CatalogSkuView])
def get_catalog_skus(
    actor: ActorContext = Depends(get_catalog_actor),
    session: Session = Depends(get_db_session),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    asOf: UtcDateTime | None = Query(default=None),
) -> PaginatedEnvelope[CatalogSkuView]:
    _require(actor, "catalog:read")
    costs_visible = has_permission(actor, "costs:read")
    rows, total = CatalogService(session, actor.organization_id).list_skus(
        limit=limit,
        offset=offset,
        as_of=asOf,
        include_costs=costs_visible,
    )
    return PaginatedEnvelope(
        items=[_sku_view(row, costs_visible=costs_visible) for row in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/api/v2/catalog/skus/{catalogSkuId}", response_model=DataEnvelope[CatalogSkuView]
)
def get_catalog_sku(
    catalogSkuId: int,
    actor: ActorContext = Depends(get_catalog_actor),
    session: Session = Depends(get_db_session),
    asOf: UtcDateTime | None = Query(default=None),
) -> DataEnvelope[CatalogSkuView]:
    _require(actor, "catalog:read")
    costs_visible = has_permission(actor, "costs:read")
    try:
        row = CatalogService(session, actor.organization_id).get_sku(
            catalogSkuId,
            as_of=asOf,
            include_cost=costs_visible,
        )
    except CostNotFoundError as exc:
        raise _not_found(exc) from exc
    return DataEnvelope(data=_sku_view(row, costs_visible=costs_visible))


@router.get(
    "/api/v2/catalog/skus/{catalogSkuId}/cost-history",
    response_model=DataEnvelope[list[CostView]],
)
def get_catalog_sku_cost_history(
    catalogSkuId: int,
    actor: ActorContext = Depends(get_catalog_actor),
    session: Session = Depends(get_db_session),
) -> DataEnvelope[list[CostView]]:
    _require(actor, "catalog:read")
    _require(actor, "costs:read")
    try:
        rows = CostsService(session, actor.organization_id).list_cost_history(
            catalogSkuId
        )
    except CostNotFoundError as exc:
        raise _not_found(exc) from exc
    return DataEnvelope(data=[_cost_view(row, visible=True) for row in rows])


@router.post(
    "/api/v2/catalog/skus/{catalogSkuId}/cost", response_model=DataEnvelope[CostView]
)
def post_catalog_sku_cost(
    catalogSkuId: int,
    payload: CostSetRequest,
    actor: ActorContext = Depends(get_catalog_actor),
    session: Session = Depends(get_db_session),
) -> DataEnvelope[CostView]:
    _require(actor, "catalog:read")
    _require(actor, "costs:write")
    _require_cost_sku_scope(session, actor, catalogSkuId)
    try:
        row = CostsService(session, actor.organization_id).set_cost(
            catalog_sku_id=catalogSkuId,
            amount_kopecks=payload.amountKopecks,
            value_state=payload.valueState,
            effective_from=payload.effectiveFrom,
            source="manual",
            source_reference=payload.sourceReference,
            evidence_status=payload.evidenceStatus,
            supersedes_cost_version_id=payload.supersedesCostVersionId,
            created_by_user_id=actor.user_id,
        )
    except CostNotFoundError as exc:
        raise _not_found(exc) from exc
    except CostConflictError as exc:
        raise HTTPException(
            status_code=409,
            detail={"code": "COST_COMMAND_CONFLICT", "message": str(exc)},
        ) from exc
    except CostValidationError as exc:
        raise HTTPException(
            status_code=422, detail={"code": "INVALID_COST", "message": str(exc)}
        ) from exc
    return DataEnvelope(data=_cost_view(row, visible=True))


@router.post("/api/v2/catalog/skus/{catalogSkuId}/current-cost", response_model=DataEnvelope[CostView])
def post_catalog_sku_current_cost(
    catalogSkuId: int,
    payload: CurrentCostSetRequest,
    actor: ActorContext = Depends(get_catalog_actor),
    session: Session = Depends(get_db_session),
) -> DataEnvelope[CostView]:
    _require(actor, "catalog:read")
    _require(actor, "costs:read")
    _require(actor, "costs:write")
    # A shared CatalogSku changes every linked offer.
    _require_cost_sku_scope(session, actor, catalogSkuId)
    try:
        row = CostsService(session, actor.organization_id).set_current_cost(
            catalog_sku_id=catalogSkuId, amount_kopecks=payload.amountKopecks,
            expected_cost_version_id=payload.expectedCostVersionId,
            source_reference=payload.sourceReference, created_by_user_id=actor.user_id,
        )
    except CostNotFoundError as exc:
        raise _not_found(exc) from exc
    except CostConflictError as exc:
        session.rollback()
        raise HTTPException(status_code=409, detail={"code": "COST_VERSION_CONFLICT", "message": str(exc)}) from exc
    except CostValidationError as exc:
        session.rollback()
        raise HTTPException(status_code=422, detail={"code": "INVALID_COST", "message": str(exc)}) from exc
    return DataEnvelope(data=_cost_view(row, visible=True))


@router.get("/api/v2/wb/products/{nmId}/current-cost")
def get_wb_product_current_cost(
    nmId: int, actor: ActorContext = Depends(get_catalog_actor),
    session: Session = Depends(get_db_session),
):
    _require(actor, "catalog:read")
    _require(actor, "costs:read")
    from app.infra.db import set_tenant_context
    set_tenant_context(session, actor.organization_id)
    accounts = session.scalars(select(MarketplaceAccountRow.marketplace_account_id).where(
        MarketplaceAccountRow.organization_id == actor.organization_id,
        MarketplaceAccountRow.marketplace == "wb", MarketplaceAccountRow.status == "connected")).all()
    # Legacy table has no explicit account identity. Never guess among accounts.
    if len(accounts) != 1:
        raise HTTPException(status_code=409, detail={"code": "COST_ACCOUNT_AMBIGUOUS", "message": "Требуется однозначный WB-аккаунт"})
    membership = session.scalar(select(IamMembershipRow).where(
        IamMembershipRow.organization_id == actor.organization_id,
        IamMembershipRow.user_id == actor.user_id, IamMembershipRow.is_active.is_(True)))
    if membership is None or (membership.scope_mode != "all" and accounts[0] not in (membership.allowed_account_ids or [])):
        raise HTTPException(status_code=403, detail={"code": "NO_ACCESS"})
    mapping, ambiguous = CatalogService(session, actor.organization_id).resolve_wb_product_skus(accounts[0], [nmId])
    if nmId in ambiguous or nmId not in mapping:
        raise HTTPException(status_code=409, detail={"code": "COST_MAPPING_AMBIGUOUS", "message": "Нет однозначного соответствия CatalogSku; проверьте варианты товара"})
    sku_id = mapping[nmId]
    linked = session.scalars(select(MarketplaceOfferRow.marketplace_product_id).where(
        MarketplaceOfferRow.organization_id == actor.organization_id,
        MarketplaceOfferRow.catalog_sku_id == sku_id)).all()
    cost = CostsService(session, actor.organization_id).get_current_cost(sku_id)
    return DataEnvelope(data={"catalogSkuId": sku_id, "linkedProductCount": len(set(linked)),
        "canWrite": has_permission(actor, "costs:write"), "currentCost": _cost_view(cost, visible=True)})


@router.get("/api/v2/wb/products", response_model=PaginatedEnvelope[WbProductView])
def get_wb_products(
    actor: ActorContext = Depends(get_catalog_actor),
    session: Session = Depends(get_db_session),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    asOf: UtcDateTime | None = Query(default=None),
) -> PaginatedEnvelope[WbProductView]:
    _require(actor, "catalog:read")
    costs_visible = has_permission(actor, "costs:read")
    rows, total = CatalogService(session, actor.organization_id).list_wb_products(
        limit=limit,
        offset=offset,
        as_of=asOf,
        include_costs=costs_visible,
    )
    goods = _goods_by_nm_id(session, actor.organization_id)
    return PaginatedEnvelope(
        items=[
            _wb_product_view(row, costs_visible=costs_visible, goods_by_nm_id=goods)
            for row in rows
        ],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/api/v2/production/skus", response_model=PaginatedEnvelope[ProductionSkuView]
)
def get_production_skus(
    actor: ActorContext = Depends(get_catalog_actor),
    session: Session = Depends(get_db_session),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    asOf: UtcDateTime | None = Query(default=None),
) -> PaginatedEnvelope[ProductionSkuView]:
    _require(actor, "catalog:read")
    costs_visible = has_permission(actor, "costs:read")
    rows, total = CatalogService(session, actor.organization_id).list_production_skus(
        limit=limit,
        offset=offset,
        as_of=asOf,
        include_costs=costs_visible,
    )
    return PaginatedEnvelope(
        items=[_production_sku_view(row, costs_visible=costs_visible) for row in rows],
        total=total,
        limit=limit,
        offset=offset,
    )
