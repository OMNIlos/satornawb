from __future__ import annotations

from datetime import date
from typing import List

from fastapi import APIRouter

from .models import (
    AbcReportResponse,
    AdsPerformanceResponse,
    AiReviewApproval,
    PnlReportResponse,
    PriceGuardResponse,
    ReportGroupBy,
    RnpReportResponse,
)
from .registry import BLOCKER_REGISTRY, BlockerRegistryEntry
from .stubs import (
    DEFAULT_FROM,
    DEFAULT_TO,
    build_abc_report_stub,
    build_ads_performance_stub,
    build_ai_review_approval_stub,
    build_pnl_report_stub,
    build_price_guard_stub,
    build_rnp_report_stub,
)

router = APIRouter()


@router.get("/api/v1/source-registry/blockers", response_model=List[BlockerRegistryEntry])
def list_blockers() -> List[BlockerRegistryEntry]:
    return list(BLOCKER_REGISTRY.values())


@router.get("/api/v1/wb-reports/pnl", response_model=PnlReportResponse)
def get_pnl_report(
    dateFrom: date = DEFAULT_FROM,
    dateTo: date = DEFAULT_TO,
    groupBy: ReportGroupBy = "sku",
):
    return build_pnl_report_stub(dateFrom, dateTo, groupBy)


@router.get("/api/v1/wb-reports/ads/performance", response_model=AdsPerformanceResponse)
def get_ads_performance(
    dateFrom: date = DEFAULT_FROM,
    dateTo: date = DEFAULT_TO,
    groupBy: ReportGroupBy = "campaign",
):
    return build_ads_performance_stub(dateFrom, dateTo, groupBy)


@router.get("/api/v1/wb-reports/rnp", response_model=RnpReportResponse)
def get_rnp_report(
    dateFrom: date = DEFAULT_FROM,
    dateTo: date = DEFAULT_TO,
    groupBy: ReportGroupBy = "sku",
):
    return build_rnp_report_stub(dateFrom, dateTo, groupBy)


@router.get("/api/v1/wb-reports/abc", response_model=AbcReportResponse)
def get_abc_report(
    dateFrom: date = DEFAULT_FROM,
    dateTo: date = DEFAULT_TO,
    groupBy: ReportGroupBy = "sku",
    filters: str = "",
):
    return build_abc_report_stub(dateFrom, dateTo, groupBy, filters)


@router.get("/api/v1/wb-repricer/sku/{articleId}/price-guard", response_model=PriceGuardResponse)
def get_price_guard(articleId: str):
    return build_price_guard_stub(articleId)


@router.get("/api/v1/wb-reviews/{reviewId}/approval", response_model=AiReviewApproval)
def get_review_approval(reviewId: str, rating: int):
    return build_ai_review_approval_stub(reviewId, rating)
