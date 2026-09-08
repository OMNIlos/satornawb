from __future__ import annotations

from pydantic import BaseModel, Field

from app.contracts.envelopes import UtcDateTime
from app.platform.economics.schemas import CostView


class CatalogSkuView(BaseModel):
    catalogSkuId: int = Field(ge=1)
    code: str = Field(min_length=1)
    printId: str | None = None
    productType: str | None = None
    color: str | None = None
    size: str | None = None
    managerMembershipId: int | None = Field(default=None, ge=1)
    currentCost: CostView
    createdAt: UtcDateTime
    updatedAt: UtcDateTime


class MarketplaceOfferView(BaseModel):
    marketplaceOfferId: int = Field(ge=1)
    externalOfferKey: str = Field(min_length=1)
    offerStatus: str | None = None
    catalogSku: CatalogSkuView | None = None


class WbProductView(BaseModel):
    marketplaceProductId: int = Field(ge=1)
    marketplaceAccountId: int = Field(ge=1)
    externalProductId: str = Field(min_length=1)
    sellerArticle: str | None = None
    brand: str | None = None
    title: str | None = None
    imageUrl: str | None = None
    productStatus: str | None = None
    priceBeforeSppKopecks: int | None = Field(default=None, ge=0)
    priceAfterSppKopecks: int | None = Field(default=None, ge=0)
    priceSnapshotAvailable: bool
    offers: list[MarketplaceOfferView]
    createdAt: UtcDateTime
    updatedAt: UtcDateTime


class ProductionMarketplaceLinkView(BaseModel):
    marketplace: str = Field(min_length=1)
    marketplaceAccountId: int = Field(ge=1)
    marketplaceProductId: int = Field(ge=1)
    externalProductId: str = Field(min_length=1)
    externalOfferKey: str = Field(min_length=1)
    sellerArticle: str | None = None
    title: str | None = None
    productStatus: str | None = None
    offerStatus: str | None = None


class ProductionSkuView(CatalogSkuView):
    marketplaceLinks: list[ProductionMarketplaceLinkView]
