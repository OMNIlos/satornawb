from __future__ import annotations

from fastapi import APIRouter, Query

from app.contracts.envelopes import DataEnvelope
from app.wb23_runtime import (
    ApplyStatusResponse,
    FreshnessPolicy,
    MarginPreviewRequest,
    MarginPreviewResponse,
    PminPmaxValidationRequest,
    PminPmaxValidationResponse,
    PriceMetricsSnapshot,
    wb23_freshness_policies,
    build_apply_status,
    build_margin_preview,
    build_pmin_pmax_validation,
    build_price_metrics_snapshot,
)
from app.wb_api.client import RateLimitedWbApiClient, build_wb_client, build_wb_statistics_client


router = APIRouter(tags=["wb-repricer-wb23"])


@router.get("/api/v1/wb-repricer/wb23/freshness-policies", response_model=DataEnvelope[list[FreshnessPolicy]])
def get_wb23_freshness_policies() -> DataEnvelope[list[FreshnessPolicy]]:
    return DataEnvelope(data=wb23_freshness_policies())


@router.get("/api/v1/wb-repricer/sku/{articleId}/price-metrics", response_model=DataEnvelope[PriceMetricsSnapshot])
def get_price_metrics_snapshot(
    articleId: str,
    scenario: str = Query(default="complete"),
    nmId: int | None = Query(default=None, gt=0),
) -> DataEnvelope[PriceMetricsSnapshot]:
    client = RateLimitedWbApiClient(inner=build_wb_client(scenario))
    orders_client = RateLimitedWbApiClient(inner=build_wb_statistics_client(scenario))
    return DataEnvelope(
        data=build_price_metrics_snapshot(client=client, article_id=articleId, nm_id=nmId, orders_client=orders_client)
    )


@router.post("/api/v1/wb-repricer/sku/{articleId}/margin-preview", response_model=DataEnvelope[MarginPreviewResponse])
def post_margin_preview(articleId: str, payload: MarginPreviewRequest) -> DataEnvelope[MarginPreviewResponse]:
    client = RateLimitedWbApiClient(inner=build_wb_client(payload.scenario))
    return DataEnvelope(data=build_margin_preview(client=client, article_id=articleId, payload=payload))


@router.post(
    "/api/v1/wb-repricer/sku/{articleId}/pmin-pmax/validate",
    response_model=DataEnvelope[PminPmaxValidationResponse],
)
def post_pmin_pmax_validation(
    articleId: str,
    payload: PminPmaxValidationRequest,
) -> DataEnvelope[PminPmaxValidationResponse]:
    client = RateLimitedWbApiClient(inner=build_wb_client(payload.scenario))
    return DataEnvelope(data=build_pmin_pmax_validation(client=client, article_id=articleId, payload=payload))


@router.get("/api/v1/wb-repricer/uploads/{uploadId}/apply-status", response_model=DataEnvelope[ApplyStatusResponse])
def get_apply_status(uploadId: int, scenario: str = Query(default="complete")) -> DataEnvelope[ApplyStatusResponse]:
    client = RateLimitedWbApiClient(inner=build_wb_client(scenario))
    return DataEnvelope(data=build_apply_status(client=client, upload_id=uploadId))
