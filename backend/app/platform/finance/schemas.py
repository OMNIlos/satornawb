from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

from app.contracts.envelopes import UtcDateTime


class FinancePeriodView(BaseModel):
    dateFrom: date
    dateTo: date
    timezone: Literal["Europe/Moscow"] = "Europe/Moscow"
    startAt: UtcDateTime
    endExclusiveAt: UtcDateTime
    days: int = Field(ge=1, le=90)
    temporalState: Literal["complete", "partial", "future"]


class FinanceSnapshotView(BaseModel):
    syncRunId: str
    snapshotChecksum: str
    formulaVersion: str
    operationCount: int = Field(ge=0)
    capturedAt: UtcDateTime
    lastObservedAt: UtcDateTime


class FinanceSummaryView(BaseModel):
    operationCount: int = Field(ge=0)
    skuCount: int = Field(ge=0)
    totalRevenueKopecks: int
    mainRevenueKopecks: int
    redemptionsRevenueKopecks: int
    lateCorrectionRevenueKopecks: int
    unknownRevenueKopecks: int
    salesUnits: int = Field(ge=0)
    returnsUnits: int = Field(ge=0)
    netUnits: int


class FinanceSkuView(BaseModel):
    nmId: int = Field(gt=0)
    sellerArticle: str | None = None
    operationCount: int = Field(ge=0)
    revenueKopecks: int
    mainRevenueKopecks: int
    redemptionsRevenueKopecks: int
    lateCorrectionRevenueKopecks: int
    unknownRevenueKopecks: int
    salesUnits: int = Field(ge=0)
    returnsUnits: int = Field(ge=0)
    netUnits: int


class FinanceMetaView(BaseModel):
    state: Literal["ready", "partial", "future", "empty", "missing"]
    marketplaceAccountId: int = Field(gt=0)
    period: FinancePeriodView
    snapshot: FinanceSnapshotView | None = None


class FinancePageView(BaseModel):
    items: list[FinanceSkuView]
    total: int = Field(ge=0)
    limit: int = Field(ge=1, le=500)
    offset: int = Field(ge=0)
    summary: FinanceSummaryView
    meta: FinanceMetaView
    timestamp: UtcDateTime
