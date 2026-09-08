from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from app.infra.db import set_tenant_context
from app.platform.catalog.orm import (
    CatalogSkuRow,
    MarketplaceOfferRow,
    MarketplaceProductRow,
)
from app.platform.clock import utc_now
from app.platform.economics.costs import CostNotFoundError, CostValue, CostsService
from app.platform.integrations.orm import MarketplaceAccountRow


def _db_utc(value: datetime) -> datetime:
    return (
        value.replace(tzinfo=timezone.utc)
        if value.tzinfo is None
        else value.astimezone(timezone.utc)
    )


@dataclass(frozen=True)
class CatalogSku:
    catalog_sku_id: int
    code: str
    print_id: str | None
    product_type: str | None
    color: str | None
    size: str | None
    manager_membership_id: int | None
    current_cost: CostValue
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class MarketplaceOffer:
    marketplace_offer_id: int
    external_offer_key: str
    offer_status: str | None
    catalog_sku: CatalogSku | None


@dataclass(frozen=True)
class MarketplaceProduct:
    marketplace_product_id: int
    marketplace_account_id: int
    external_product_id: str
    seller_article: str | None
    brand: str | None
    title: str | None
    image_url: str | None
    product_status: str | None
    offers: tuple[MarketplaceOffer, ...]
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class MarketplaceLink:
    marketplace: str
    marketplace_account_id: int
    marketplace_product_id: int
    external_product_id: str
    external_offer_key: str
    seller_article: str | None
    title: str | None
    product_status: str | None
    offer_status: str | None


@dataclass(frozen=True)
class ProductionSku:
    sku: CatalogSku
    marketplace_links: tuple[MarketplaceLink, ...]


class CatalogService:
    def __init__(
        self,
        session: Session,
        organization_id: int,
        *,
        now: Callable[[], datetime] = utc_now,
    ):
        self.session = session
        self.organization_id = organization_id
        self.now = now

    def _prepare(self) -> None:
        set_tenant_context(self.session, self.organization_id)

    @staticmethod
    def _view(row: CatalogSkuRow, cost: CostValue) -> CatalogSku:
        return CatalogSku(
            catalog_sku_id=row.catalog_sku_id,
            code=row.code,
            print_id=row.print_id,
            product_type=row.product_type,
            color=row.color,
            size=row.size,
            manager_membership_id=row.manager_membership_id,
            current_cost=cost,
            created_at=_db_utc(row.created_at),
            updated_at=_db_utc(row.updated_at),
        )

    def list_skus(
        self,
        *,
        limit: int,
        offset: int,
        as_of: datetime | None = None,
        include_costs: bool = True,
    ) -> tuple[list[CatalogSku], int]:
        self._prepare()
        total = int(
            self.session.scalar(
                select(func.count())
                .select_from(CatalogSkuRow)
                .where(CatalogSkuRow.organization_id == self.organization_id)
            )
            or 0
        )
        rows = self.session.scalars(
            select(CatalogSkuRow)
            .where(CatalogSkuRow.organization_id == self.organization_id)
            .order_by(CatalogSkuRow.code.asc(), CatalogSkuRow.catalog_sku_id.asc())
            .limit(limit)
            .offset(offset)
        ).all()
        costs = (
            CostsService(self.session, self.organization_id, now=self.now).get_costs_at(
                [row.catalog_sku_id for row in rows],
                as_of or self.now(),
            )
            if include_costs
            else {
                row.catalog_sku_id: CostValue(None, row.catalog_sku_id, None, "missing")
                for row in rows
            }
        )
        return [self._view(row, costs[row.catalog_sku_id]) for row in rows], total

    def get_sku(
        self,
        catalog_sku_id: int,
        *,
        as_of: datetime | None = None,
        include_cost: bool = True,
    ) -> CatalogSku:
        self._prepare()
        row = self.session.scalar(
            select(CatalogSkuRow).where(
                CatalogSkuRow.organization_id == self.organization_id,
                CatalogSkuRow.catalog_sku_id == catalog_sku_id,
            )
        )
        if row is None:
            raise CostNotFoundError("catalog SKU not found")
        cost = (
            CostsService(self.session, self.organization_id, now=self.now).get_costs_at(
                [catalog_sku_id],
                as_of or self.now(),
            )[catalog_sku_id]
            if include_cost
            else CostValue(None, catalog_sku_id, None, "missing")
        )
        return self._view(row, cost)

    def resolve_wb_product_skus(
        self,
        marketplace_account_id: int,
        nm_ids: list[int],
    ) -> tuple[dict[int, int], set[int]]:
        requested = sorted({value for value in nm_ids if value > 0})
        if not requested:
            return {}, set()
        self._prepare()
        rows = self.session.execute(
            select(
                MarketplaceProductRow.external_product_id,
                MarketplaceOfferRow.catalog_sku_id,
            )
            .outerjoin(
                MarketplaceOfferRow,
                and_(
                    MarketplaceOfferRow.organization_id
                    == MarketplaceProductRow.organization_id,
                    MarketplaceOfferRow.marketplace_product_id
                    == MarketplaceProductRow.marketplace_product_id,
                ),
            )
            .where(
                MarketplaceProductRow.organization_id == self.organization_id,
                MarketplaceProductRow.marketplace_account_id
                == marketplace_account_id,
                MarketplaceProductRow.external_product_id.in_(
                    [str(value) for value in requested]
                ),
            )
        ).all()
        sku_ids_by_nm: dict[int, set[int]] = {}
        for external_product_id, catalog_sku_id in rows:
            nm_id = int(external_product_id)
            sku_ids_by_nm.setdefault(nm_id, set())
            if catalog_sku_id is not None:
                sku_ids_by_nm[nm_id].add(int(catalog_sku_id))
        return (
            {
                nm_id: next(iter(sku_ids))
                for nm_id, sku_ids in sku_ids_by_nm.items()
                if len(sku_ids) == 1
            },
            {
                nm_id
                for nm_id, sku_ids in sku_ids_by_nm.items()
                if len(sku_ids) > 1
            },
        )

    def list_wb_products(
        self,
        *,
        limit: int,
        offset: int,
        as_of: datetime | None = None,
        include_costs: bool = True,
    ) -> tuple[list[MarketplaceProduct], int]:
        self._prepare()
        scope = (
            MarketplaceProductRow.organization_id == self.organization_id,
            MarketplaceAccountRow.marketplace == "wb",
        )
        total = int(
            self.session.scalar(
                select(func.count())
                .select_from(MarketplaceProductRow)
                .join(
                    MarketplaceAccountRow,
                    and_(
                        MarketplaceAccountRow.organization_id
                        == MarketplaceProductRow.organization_id,
                        MarketplaceAccountRow.marketplace_account_id
                        == MarketplaceProductRow.marketplace_account_id,
                    ),
                )
                .where(*scope)
            )
            or 0
        )
        products = self.session.scalars(
            select(MarketplaceProductRow)
            .join(
                MarketplaceAccountRow,
                and_(
                    MarketplaceAccountRow.organization_id
                    == MarketplaceProductRow.organization_id,
                    MarketplaceAccountRow.marketplace_account_id
                    == MarketplaceProductRow.marketplace_account_id,
                ),
            )
            .where(*scope)
            .order_by(
                MarketplaceProductRow.external_product_id.asc(),
                MarketplaceProductRow.marketplace_product_id.asc(),
            )
            .limit(limit)
            .offset(offset)
        ).all()
        product_ids = [row.marketplace_product_id for row in products]
        offer_rows = (
            self.session.execute(
                select(MarketplaceOfferRow, CatalogSkuRow)
                .outerjoin(
                    CatalogSkuRow,
                    and_(
                        CatalogSkuRow.organization_id
                        == MarketplaceOfferRow.organization_id,
                        CatalogSkuRow.catalog_sku_id
                        == MarketplaceOfferRow.catalog_sku_id,
                    ),
                )
                .where(
                    MarketplaceOfferRow.organization_id == self.organization_id,
                    MarketplaceOfferRow.marketplace_product_id.in_(product_ids),
                )
                .order_by(
                    MarketplaceOfferRow.external_offer_key.asc(),
                    MarketplaceOfferRow.marketplace_offer_id.asc(),
                )
            ).all()
            if product_ids
            else []
        )
        sku_ids = [sku.catalog_sku_id for _offer, sku in offer_rows if sku is not None]
        costs = (
            CostsService(self.session, self.organization_id, now=self.now).get_costs_at(
                sku_ids, as_of or self.now()
            )
            if include_costs
            else {
                sku_id: CostValue(None, sku_id, None, "missing") for sku_id in sku_ids
            }
        )
        offers_by_product: dict[int, list[MarketplaceOffer]] = {}
        for offer, sku in offer_rows:
            offers_by_product.setdefault(offer.marketplace_product_id, []).append(
                MarketplaceOffer(
                    marketplace_offer_id=offer.marketplace_offer_id,
                    external_offer_key=offer.external_offer_key,
                    offer_status=offer.offer_status,
                    catalog_sku=(
                        self._view(sku, costs[sku.catalog_sku_id])
                        if sku is not None
                        else None
                    ),
                )
            )
        return [
            MarketplaceProduct(
                marketplace_product_id=row.marketplace_product_id,
                marketplace_account_id=row.marketplace_account_id,
                external_product_id=row.external_product_id,
                seller_article=row.seller_article,
                brand=row.brand,
                title=row.title,
                image_url=row.image_url,
                product_status=row.product_status,
                offers=tuple(offers_by_product.get(row.marketplace_product_id, [])),
                created_at=_db_utc(row.created_at),
                updated_at=_db_utc(row.updated_at),
            )
            for row in products
        ], total

    def list_production_skus(
        self,
        *,
        limit: int,
        offset: int,
        as_of: datetime | None = None,
        include_costs: bool = True,
    ) -> tuple[list[ProductionSku], int]:
        skus, total = self.list_skus(
            limit=limit,
            offset=offset,
            as_of=as_of,
            include_costs=include_costs,
        )
        sku_ids = [sku.catalog_sku_id for sku in skus]
        link_rows = (
            self.session.execute(
                select(
                    MarketplaceOfferRow, MarketplaceProductRow, MarketplaceAccountRow
                )
                .join(
                    MarketplaceProductRow,
                    and_(
                        MarketplaceProductRow.organization_id
                        == MarketplaceOfferRow.organization_id,
                        MarketplaceProductRow.marketplace_product_id
                        == MarketplaceOfferRow.marketplace_product_id,
                    ),
                )
                .join(
                    MarketplaceAccountRow,
                    and_(
                        MarketplaceAccountRow.organization_id
                        == MarketplaceOfferRow.organization_id,
                        MarketplaceAccountRow.marketplace_account_id
                        == MarketplaceOfferRow.marketplace_account_id,
                    ),
                )
                .where(
                    MarketplaceOfferRow.organization_id == self.organization_id,
                    MarketplaceOfferRow.catalog_sku_id.in_(sku_ids),
                )
                .order_by(
                    MarketplaceAccountRow.marketplace.asc(),
                    MarketplaceProductRow.external_product_id.asc(),
                    MarketplaceOfferRow.external_offer_key.asc(),
                )
            ).all()
            if sku_ids
            else []
        )
        links_by_sku: dict[int, list[MarketplaceLink]] = {}
        for offer, product, account in link_rows:
            if offer.catalog_sku_id is None:
                continue
            links_by_sku.setdefault(offer.catalog_sku_id, []).append(
                MarketplaceLink(
                    marketplace=account.marketplace,
                    marketplace_account_id=account.marketplace_account_id,
                    marketplace_product_id=product.marketplace_product_id,
                    external_product_id=product.external_product_id,
                    external_offer_key=offer.external_offer_key,
                    seller_article=product.seller_article,
                    title=product.title,
                    product_status=product.product_status,
                    offer_status=offer.offer_status,
                )
            )
        return [
            ProductionSku(
                sku=sku,
                marketplace_links=tuple(links_by_sku.get(sku.catalog_sku_id, [])),
            )
            for sku in skus
        ], total
