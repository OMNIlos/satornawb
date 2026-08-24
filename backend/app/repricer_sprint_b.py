from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Literal
from uuid import uuid4

from fastapi import HTTPException
from pydantic import BaseModel, Field

from app.contracts.envelopes import UtcDateTime
from app.discovery.repricer_sources import build_repricer_discovery_readiness
from app.repricer_settings import get_repricer_guard_limits, get_repricer_spp_accounting_settings
from app.wb22_apply import PriceApplyRequest, PriceApplyResponse, PriceApplyRowRequest, run_price_apply
from app.wb23_runtime import (
    MarginPreviewRequest,
    MarginPreviewResponse,
    PminPmaxValidationRequest,
    PminPmaxValidationResponse,
    PriceMetricValue,
    PriceMetricsSnapshot,
    build_margin_preview,
    build_pmin_pmax_validation,
    build_price_metrics_snapshot,
    build_price_metrics_snapshot_from_row,
)
from app.wb_api.client import WbApiClient


GuardSeverity = Literal["info", "warning", "blocker"]
DraftState = Literal["draft", "approved", "queued", "sent", "accepted", "failed", "blocked", "needs_attention", "local_applied"]
ApplyJobState = Literal["queued", "sent", "accepted", "failed", "blocked", "needs_attention", "local_applied"]
ApprovalState = Literal["required", "approved"]


FORMULA_VERSION_RECOMMENDATION = "sprint-b-repricer-v1"
FORMULA_VERSION_GUARDS = "sprint-b-guards-v1"
SOURCE_SNAPSHOT_VERSION = "wb23-runtime-v1"


def _buyer_price_for_accounting(seller_price_kopecks: int, spp_pct: float | None) -> int | None:
    if spp_pct is None:
        return None
    accounting = get_repricer_spp_accounting_settings()
    multiplier = 1 - float(spp_pct) / 100
    if accounting.mode == "spp_plus_wallet" and accounting.wb_wallet_pct is not None:
        multiplier *= 1 - float(accounting.wb_wallet_pct) / 100
    return int(round(seller_price_kopecks * multiplier))


class DraftEconomicsInput(BaseModel):
    cogsKopecks: int | None = Field(default=None, ge=0)
    commissionPct: float | None = Field(default=None, ge=0, le=100)
    logisticsKopecks: int | None = Field(default=None, ge=0)
    storageKopecks: int = Field(default=0, ge=0)
    taxKopecks: int = Field(default=0, ge=0)
    buyoutPct: float | None = Field(default=None, ge=0, le=100)
    stockUnits: int | None = Field(default=None, ge=0)
    promoActive: bool = False


class PriceRecommendationRequest(BaseModel):
    scenario: str = "complete"
    articleId: str = Field(min_length=1)
    nmId: int = Field(gt=0)
    candidateSellerPriceKopecks: int = Field(gt=0)
    minPriceKopecks: int | None = Field(default=None, gt=0)
    pMaxKopecks: int | None = Field(default=None, gt=0)
    economics: DraftEconomicsInput


class PriceDraftCreateRequest(BaseModel):
    scenario: str = "complete"
    articleId: str = Field(min_length=1)
    nmId: int = Field(gt=0)
    candidateSellerPriceKopecks: int = Field(gt=0)
    minPriceKopecks: int | None = Field(default=None, gt=0)
    pMaxKopecks: int | None = Field(default=None, gt=0)
    economics: DraftEconomicsInput
    reason: str | None = None


class ApproveDraftRequest(BaseModel):
    approvalRef: str = Field(min_length=1)
    reason: str | None = None


class ApplyDraftRequest(BaseModel):
    scenario: str = "complete"
    pollMaxAttempts: int = Field(default=6, ge=1, le=60)
    pollDelaySeconds: float = Field(default=0.0, ge=0.0, le=5.0)
    skipStatusPoll: bool = False


class RetryApplyJobRequest(BaseModel):
    scenario: str = "complete"
    pollMaxAttempts: int = Field(default=6, ge=1, le=60)
    pollDelaySeconds: float = Field(default=0.0, ge=0.0, le=5.0)


class GuardTrigger(BaseModel):
    code: str = Field(min_length=1)
    severity: GuardSeverity
    message: str = Field(min_length=1)
    observedValue: float | int | str | None = None
    threshold: float | int | str | None = None


class SourceMetricSnapshot(BaseModel):
    metricId: str = Field(min_length=1)
    sourceStatus: Literal["fresh", "partial", "stale", "blocked"]
    blockerIds: list[str]
    fieldSource: str = Field(min_length=1)
    value: int | float | None = None
    fetchedAt: UtcDateTime
    staleAfter: UtcDateTime
    confidence: Literal["high", "medium", "low", "blocked"]
    warnings: list[str] = Field(default_factory=list)


class SourceSnapshot(BaseModel):
    sourceStatus: Literal["fresh", "partial", "stale", "blocked"]
    blockerIds: list[str]
    capturedAt: UtcDateTime
    snapshotVersion: str = Field(min_length=1)
    metrics: list[SourceMetricSnapshot]


class NormalizedEconomics(BaseModel):
    articleId: str
    nmId: int
    currentSellerPriceKopecks: int | None = None
    currentBuyerPriceKopecks: int | None = None
    currentSppPct: float | None = None
    candidateSellerPriceKopecks: int
    candidateBuyerPriceKopecks: int | None = None
    cogsKopecks: int | None = None
    commissionPct: float | None = None
    logisticsKopecks: int | None = None
    storageKopecks: int = 0
    taxKopecks: int = 0
    buyoutPct: float | None = None
    stockUnits: int | None = None
    promoActive: bool = False
    minPriceKopecks: int | None = None
    pMinKopecks: int | None = None
    pMaxKopecks: int | None = None
    predictedMarginKopecks: int | None = None
    predictedMarginPct: float | None = None


class PriceGuardReport(BaseModel):
    canApply: bool
    blockers: list[str]
    triggers: list[GuardTrigger]


class PriceRecommendationResponse(BaseModel):
    articleId: str
    nmId: int
    formulaVersion: str
    guardFormulaVersion: str
    sourceSnapshot: SourceSnapshot
    normalized: NormalizedEconomics
    guardReport: PriceGuardReport


class PriceDraftView(BaseModel):
    draftId: str = Field(min_length=1)
    articleId: str = Field(min_length=1)
    nmId: int = Field(gt=0)
    state: DraftState
    approvalState: ApprovalState
    approvalRef: str | None = None
    approvalActorId: str | None = None
    createdByActorId: str = Field(min_length=1)
    createdByRole: str = Field(min_length=1)
    reason: str | None = None
    formulaVersion: str = Field(min_length=1)
    guardFormulaVersion: str = Field(min_length=1)
    sourceSnapshot: SourceSnapshot
    normalized: NormalizedEconomics
    guardReport: PriceGuardReport
    applyJobId: str | None = None
    createdAt: UtcDateTime
    updatedAt: UtcDateTime


class ApplyJobRowError(BaseModel):
    nmId: int | None = None
    sizeId: int | None = None
    wbStatus: int | None = None
    errorText: str


class ApplyJobView(BaseModel):
    jobId: str = Field(min_length=1)
    draftId: str = Field(min_length=1)
    articleId: str = Field(min_length=1)
    nmId: int = Field(gt=0)
    state: ApplyJobState
    sourceStatus: Literal["fresh", "partial", "blocked"]
    blockerIds: list[str]
    wbUploadId: int | None = None
    wbStatus: int | None = None
    rowErrors: list[ApplyJobRowError] = Field(default_factory=list)
    retryCount: int = Field(ge=0)
    maxRetryCount: int = Field(ge=0)
    nextRetryAt: UtcDateTime | None = None
    stopRequired: bool
    notes: list[str] = Field(default_factory=list)
    lastApplyResult: PriceApplyResponse
    formulaVersion: str = Field(min_length=1)
    guardFormulaVersion: str = Field(min_length=1)
    sourceSnapshot: SourceSnapshot
    createdAt: UtcDateTime
    updatedAt: UtcDateTime


class _PreparedDraft(BaseModel):
    sourceSnapshot: SourceSnapshot
    normalized: NormalizedEconomics
    guardReport: PriceGuardReport


class _PriceHistoryPoint(BaseModel):
    sellerPriceKopecks: int = Field(gt=0)
    appliedAt: UtcDateTime


@dataclass
class _SprintBMemoryState:
    drafts: dict[str, PriceDraftView] = field(default_factory=dict)
    jobs: dict[str, ApplyJobView] = field(default_factory=dict)
    price_history: dict[str, list[_PriceHistoryPoint]] = field(default_factory=dict)


_MEMORY = _SprintBMemoryState()


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _metric_by_id(snapshot: PriceMetricsSnapshot, metric_id: str) -> PriceMetricValue | None:
    return next((metric for metric in snapshot.metrics if metric.metricId == metric_id), None)


def _metric_float(metric: PriceMetricValue | None) -> float | None:
    if metric is None:
        return None
    value = metric.value
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _to_source_snapshot(snapshot: PriceMetricsSnapshot) -> SourceSnapshot:
    captured_at = _now_utc()
    items: list[SourceMetricSnapshot] = []
    for metric in snapshot.metrics:
        items.append(
            SourceMetricSnapshot(
                metricId=metric.metricId,
                sourceStatus=metric.sourceStatus,
                blockerIds=metric.blockerIds,
                fieldSource=metric.fieldSource,
                value=metric.value,
                fetchedAt=metric.freshness.fetchedAt,
                staleAfter=metric.freshness.staleAfter,
                confidence=metric.freshness.confidence,
                warnings=metric.warnings,
            )
        )
    return SourceSnapshot(
        sourceStatus=snapshot.sourceStatus,
        blockerIds=snapshot.blockerIds,
        capturedAt=captured_at,
        snapshotVersion=SOURCE_SNAPSHOT_VERSION,
        metrics=items,
    )


def _predict_margin(candidate_buyer_price: int | None, economics: DraftEconomicsInput) -> tuple[int | None, float | None]:
    if candidate_buyer_price is None:
        return None, None
    if economics.cogsKopecks is None:
        return None, None
    if economics.commissionPct is None:
        return None, None
    if economics.logisticsKopecks is None:
        return None, None
    commission_kopecks = int(round(candidate_buyer_price * economics.commissionPct / 100))
    margin_kopecks = (
        candidate_buyer_price
        - commission_kopecks
        - economics.cogsKopecks
        - economics.logisticsKopecks
        - economics.storageKopecks
    )
    margin_pct = (margin_kopecks / candidate_buyer_price * 100) if candidate_buyer_price > 0 else None
    return margin_kopecks, margin_pct


def _daily_reference_price(article_id: str, fallback_price: int | None) -> int | None:
    points = _MEMORY.price_history.get(article_id, [])
    cutoff = _now_utc() - timedelta(hours=24)
    recent = [point for point in points if point.appliedAt >= cutoff]
    if recent:
        return recent[-1].sellerPriceKopecks
    return fallback_price


def _evaluate_guards(
    article_id: str,
    snapshot: PriceMetricsSnapshot,
    source_snapshot: SourceSnapshot,
    normalized: NormalizedEconomics,
    pmin_validation: PminPmaxValidationResponse,
    margin_preview: MarginPreviewResponse,
) -> PriceGuardReport:
    triggers: list[GuardTrigger] = []
    blockers: set[str] = set()
    guard_limits = get_repricer_guard_limits()

    discovery = build_repricer_discovery_readiness()
    if not discovery.canUnblockPriceGuard:
        for blocker in discovery.blockingIds:
            if blocker in {"WB-22", "WB-23"}:
                blockers.add(blocker)
                triggers.append(
                    GuardTrigger(
                        code="discovery_not_ready",
                        severity="blocker",
                        message="WB-22/WB-23 readiness is not confirmed for production apply",
                        observedValue=blocker,
                        threshold="confirmed",
                    )
                )

    if source_snapshot.sourceStatus in {"blocked", "stale"}:
        blockers.add("WB-23")
        triggers.append(
            GuardTrigger(
                code="source_stale_or_blocked",
                severity="blocker",
                message="Critical price sources are stale or blocked",
                observedValue=source_snapshot.sourceStatus,
                threshold="fresh|partial",
            )
        )

    if normalized.currentSppPct is None:
        blockers.add("WB-23")
        triggers.append(
            GuardTrigger(
                code="spp_missing",
                severity="blocker",
                message="SPP input is missing, candidate buyer plane cannot be validated",
            )
        )

    if normalized.cogsKopecks is None:
        blockers.add("WB-23")
        triggers.append(
            GuardTrigger(
                code="cogs_missing",
                severity="blocker",
                message="COGS is missing for SKU",
            )
        )

    if normalized.commissionPct is None:
        blockers.add("WB-23")
        triggers.append(
            GuardTrigger(
                code="commission_missing",
                severity="blocker",
                message="Commission input is missing for SKU",
            )
        )

    if normalized.logisticsKopecks is None:
        blockers.add("WB-23")
        triggers.append(
            GuardTrigger(
                code="logistics_missing",
                severity="blocker",
                message="Logistics input is missing for SKU",
            )
        )

    if normalized.buyoutPct is None:
        blockers.add("WB-23")
        triggers.append(
            GuardTrigger(
                code="buyout_missing",
                severity="blocker",
                message="Buyout input is missing for SKU",
            )
        )

    if normalized.stockUnits is None:
        blockers.add("WB-23")
        triggers.append(
            GuardTrigger(
                code="stock_missing",
                severity="blocker",
                message="Stock input is missing for SKU",
            )
        )
    elif normalized.stockUnits <= 0:
        blockers.add("WB-23")
        triggers.append(
            GuardTrigger(
                code="stock_oos",
                severity="blocker",
                message="Stock is empty, auto-apply is blocked",
                observedValue=normalized.stockUnits,
                threshold=1,
            )
        )

    if normalized.promoActive and normalized.minPriceKopecks is None:
        blockers.add("WB-23")
        triggers.append(
            GuardTrigger(
                code="promo_min_price_missing",
                severity="blocker",
                message="Promo flag is active but minPrice is not provided",
            )
        )

    if normalized.minPriceKopecks is not None and normalized.candidateSellerPriceKopecks < normalized.minPriceKopecks:
        blockers.add("WB-23")
        triggers.append(
            GuardTrigger(
                code="candidate_below_min_price",
                severity="blocker",
                message="Candidate seller price is lower than minPrice",
                observedValue=normalized.candidateSellerPriceKopecks,
                threshold=normalized.minPriceKopecks,
            )
        )

    if normalized.predictedMarginKopecks is not None and normalized.predictedMarginKopecks < 0:
        blockers.add("WB-23")
        triggers.append(
            GuardTrigger(
                code="negative_margin",
                severity="blocker",
                message="Predicted margin is negative",
                observedValue=normalized.predictedMarginKopecks,
                threshold=0,
            )
        )

    if guard_limits.pmin_guard_enabled and not pmin_validation.isValid:
        blockers.add("WB-23")
        triggers.append(
            GuardTrigger(
                code="pmin_pmax_block",
                severity="blocker",
                message="Candidate price failed P_min/P_max validation",
                observedValue=",".join(pmin_validation.reasons),
                threshold="isValid=true",
            )
        )

    current_price = normalized.currentSellerPriceKopecks
    if current_price is not None and current_price > 0:
        delta_update_pct = abs(normalized.candidateSellerPriceKopecks - current_price) / current_price * 100
        if delta_update_pct > guard_limits.per_update_step_pct:
            blockers.add("WB-23")
            triggers.append(
                GuardTrigger(
                    code="per_update_step_exceeded",
                    severity="blocker",
                    message=f"Per-update change exceeds {guard_limits.per_update_step_pct:.1f}%",
                    observedValue=round(delta_update_pct, 4),
                    threshold=guard_limits.per_update_step_pct,
                )
            )

    daily_ref = _daily_reference_price(article_id, current_price)
    if daily_ref is not None and daily_ref > 0:
        delta_day_pct = abs(normalized.candidateSellerPriceKopecks - daily_ref) / daily_ref * 100
        if delta_day_pct > guard_limits.per_day_step_pct:
            blockers.add("WB-23")
            triggers.append(
                GuardTrigger(
                    code="per_day_step_exceeded",
                    severity="blocker",
                    message=f"24-hour change exceeds {guard_limits.per_day_step_pct:.1f}%",
                    observedValue=round(delta_day_pct, 4),
                    threshold=guard_limits.per_day_step_pct,
                )
            )

    if margin_preview.sourceStatus in {"blocked"}:
        blockers.add("WB-23")
        triggers.append(
            GuardTrigger(
                code="margin_preview_blocked",
                severity="blocker",
                message="Margin preview source is blocked",
                observedValue=margin_preview.sourceStatus,
                threshold="fresh|partial",
            )
        )

    return PriceGuardReport(
        canApply=not blockers,
        blockers=sorted(blockers),
        triggers=triggers,
    )


def _build_prepared_draft(
    client: WbApiClient,
    payload: PriceRecommendationRequest,
    *,
    sku_row: dict[str, Any] | None = None,
    orders_client: WbApiClient | None = None,
) -> _PreparedDraft:
    if sku_row is not None:
        price_snapshot = build_price_metrics_snapshot_from_row(payload.articleId, sku_row)
    else:
        price_snapshot = build_price_metrics_snapshot(
            client=client,
            article_id=payload.articleId,
            nm_id=int(payload.nmId) if payload.nmId is not None else None,
            orders_client=orders_client,
        )
    source_snapshot = _to_source_snapshot(price_snapshot)

    metric_before = _metric_by_id(price_snapshot, "current_price_before_spp")
    metric_after = _metric_by_id(price_snapshot, "current_price_after_spp")
    metric_spp = _metric_by_id(price_snapshot, "spp_pct")

    current_before = _metric_float(metric_before)
    current_after = _metric_float(metric_after)
    current_spp_pct = _metric_float(metric_spp)

    candidate_buyer_price = _buyer_price_for_accounting(payload.candidateSellerPriceKopecks, current_spp_pct)

    margin_cost = payload.economics.cogsKopecks if payload.economics.cogsKopecks and payload.economics.cogsKopecks > 0 else 1

    margin_preview_request = MarginPreviewRequest(
        scenario=payload.scenario,
        costPriceKopecks=margin_cost,
        wbCommissionPct=payload.economics.commissionPct or 0,
        logisticsKopecks=payload.economics.logisticsKopecks or 0,
        taxKopecks=payload.economics.taxKopecks,
        storageKopecks=payload.economics.storageKopecks,
    )
    margin_preview = build_margin_preview(
        client=client,
        article_id=payload.articleId,
        payload=margin_preview_request,
        price_snapshot=price_snapshot,
    )

    pmin_request = PminPmaxValidationRequest(
        scenario=payload.scenario,
        candidateBuyerPriceKopecks=candidate_buyer_price or payload.candidateSellerPriceKopecks,
        costPriceKopecks=payload.economics.cogsKopecks or 1,
        wbCommissionPct=payload.economics.commissionPct or 0,
        targetMarginPct=10,
        logisticsKopecks=payload.economics.logisticsKopecks or 0,
        taxKopecks=payload.economics.taxKopecks,
        fixedCostsKopecks=payload.economics.storageKopecks,
        pMaxKopecks=payload.pMaxKopecks,
    )
    pmin_validation = build_pmin_pmax_validation(
        client=client,
        article_id=payload.articleId,
        payload=pmin_request,
        price_snapshot=price_snapshot,
    )

    predicted_margin_kopecks, predicted_margin_pct = _predict_margin(candidate_buyer_price, payload.economics)

    normalized = NormalizedEconomics(
        articleId=payload.articleId,
        nmId=payload.nmId,
        currentSellerPriceKopecks=int(round(current_before)) if current_before is not None else None,
        currentBuyerPriceKopecks=int(round(current_after)) if current_after is not None else None,
        currentSppPct=round(current_spp_pct, 4) if current_spp_pct is not None else None,
        candidateSellerPriceKopecks=payload.candidateSellerPriceKopecks,
        candidateBuyerPriceKopecks=candidate_buyer_price,
        cogsKopecks=payload.economics.cogsKopecks,
        commissionPct=payload.economics.commissionPct,
        logisticsKopecks=payload.economics.logisticsKopecks,
        storageKopecks=payload.economics.storageKopecks,
        taxKopecks=payload.economics.taxKopecks,
        buyoutPct=payload.economics.buyoutPct,
        stockUnits=payload.economics.stockUnits,
        promoActive=payload.economics.promoActive,
        minPriceKopecks=payload.minPriceKopecks,
        pMinKopecks=pmin_validation.pMinKopecks,
        pMaxKopecks=payload.pMaxKopecks,
        predictedMarginKopecks=predicted_margin_kopecks,
        predictedMarginPct=round(predicted_margin_pct, 4) if predicted_margin_pct is not None else None,
    )

    guard_report = _evaluate_guards(
        article_id=payload.articleId,
        snapshot=price_snapshot,
        source_snapshot=source_snapshot,
        normalized=normalized,
        pmin_validation=pmin_validation,
        margin_preview=margin_preview,
    )

    return _PreparedDraft(
        sourceSnapshot=source_snapshot,
        normalized=normalized,
        guardReport=guard_report,
    )


def build_price_recommendation(
    client: WbApiClient,
    payload: PriceRecommendationRequest,
    *,
    sku_row: dict[str, Any] | None = None,
    orders_client: WbApiClient | None = None,
) -> PriceRecommendationResponse:
    prepared = _build_prepared_draft(client=client, payload=payload, sku_row=sku_row, orders_client=orders_client)
    return PriceRecommendationResponse(
        articleId=payload.articleId,
        nmId=payload.nmId,
        formulaVersion=FORMULA_VERSION_RECOMMENDATION,
        guardFormulaVersion=FORMULA_VERSION_GUARDS,
        sourceSnapshot=prepared.sourceSnapshot,
        normalized=prepared.normalized,
        guardReport=prepared.guardReport,
    )


def create_price_draft(
    actor_id: str,
    actor_role: str,
    client: WbApiClient,
    payload: PriceDraftCreateRequest,
    *,
    sku_row: dict[str, Any] | None = None,
    orders_client: WbApiClient | None = None,
) -> PriceDraftView:
    prepared = _build_prepared_draft(
        client=client,
        payload=PriceRecommendationRequest(
            scenario=payload.scenario,
            articleId=payload.articleId,
            nmId=payload.nmId,
            candidateSellerPriceKopecks=payload.candidateSellerPriceKopecks,
            minPriceKopecks=payload.minPriceKopecks,
            pMaxKopecks=payload.pMaxKopecks,
            economics=payload.economics,
        ),
        sku_row=sku_row,
        orders_client=orders_client,
    )
    now = _now_utc()
    draft_id = f"drf_{uuid4().hex}"
    state: DraftState = "draft" if prepared.guardReport.canApply else "blocked"
    draft = PriceDraftView(
        draftId=draft_id,
        articleId=payload.articleId,
        nmId=payload.nmId,
        state=state,
        approvalState="required",
        approvalRef=None,
        approvalActorId=None,
        createdByActorId=actor_id,
        createdByRole=actor_role,
        reason=payload.reason,
        formulaVersion=FORMULA_VERSION_RECOMMENDATION,
        guardFormulaVersion=FORMULA_VERSION_GUARDS,
        sourceSnapshot=prepared.sourceSnapshot,
        normalized=prepared.normalized,
        guardReport=prepared.guardReport,
        applyJobId=None,
        createdAt=now,
        updatedAt=now,
    )
    _MEMORY.drafts[draft_id] = draft
    return draft


def get_draft_or_404(draft_id: str) -> PriceDraftView:
    draft = _MEMORY.drafts.get(draft_id)
    if draft is None:
        raise HTTPException(status_code=404, detail="PRICE_DRAFT_NOT_FOUND")
    return draft


def approve_draft(draft_id: str, actor_id: str, request: ApproveDraftRequest) -> PriceDraftView:
    current = get_draft_or_404(draft_id)
    if current.state == "blocked":
        raise HTTPException(status_code=409, detail="PRICE_DRAFT_BLOCKED_BY_GUARDS")
    updated = current.model_copy(
        update={
            "state": "approved",
            "approvalState": "approved",
            "approvalRef": request.approvalRef,
            "approvalActorId": actor_id,
            "updatedAt": _now_utc(),
        }
    )
    _MEMORY.drafts[draft_id] = updated
    return updated


def _map_apply_state(result: PriceApplyResponse) -> tuple[ApplyJobState, bool]:
    if result.applyState == "local_applied":
        return "local_applied", False
    if result.applyState == "accepted":
        return "accepted", False
    if result.applyState == "queued":
        return "queued", False
    if result.applyState == "blocked":
        return "blocked", True
    if result.statusLabel == "processing":
        return "sent", False
    if result.statusLabel in {"all_failed", "canceled"}:
        return "failed", True
    if result.statusLabel in {"partial_errors", "unknown"}:
        return "needs_attention", True
    if result.applyState == "requires_attention":
        return "needs_attention", True
    return "needs_attention", True


def _to_apply_request(draft: PriceDraftView, request: ApplyDraftRequest) -> PriceApplyRequest:
    row = PriceApplyRowRequest(
        nmId=draft.nmId,
        priceKopecks=draft.normalized.candidateSellerPriceKopecks,
        discountPct=0,
        minPriceKopecks=draft.normalized.minPriceKopecks,
    )
    return PriceApplyRequest(
        scenario=request.scenario,
        dryRun=False,
        pollMaxAttempts=request.pollMaxAttempts,
        pollDelaySeconds=request.pollDelaySeconds,
        skipStatusPoll=request.skipStatusPoll,
        rows=[row],
    )


def _create_job(draft: PriceDraftView, result: PriceApplyResponse, state: ApplyJobState, stop_required: bool) -> ApplyJobView:
    now = _now_utc()
    retry_count = 1 if state in {"failed", "needs_attention"} else 0
    next_retry_at = now + timedelta(minutes=5) if retry_count > 0 else None
    row_errors = [
        ApplyJobRowError(
            nmId=row.nmId,
            sizeId=row.sizeId,
            wbStatus=row.wbStatus,
            errorText=row.errorText,
        )
        for row in result.rowErrors
    ]
    return ApplyJobView(
        jobId=f"job_{uuid4().hex}",
        draftId=draft.draftId,
        articleId=draft.articleId,
        nmId=draft.nmId,
        state=state,
        sourceStatus=result.sourceStatus,
        blockerIds=result.blockerIds,
        wbUploadId=result.wbUploadId,
        wbStatus=result.wbStatus,
        rowErrors=row_errors,
        retryCount=retry_count,
        maxRetryCount=3,
        nextRetryAt=next_retry_at,
        stopRequired=stop_required,
        notes=result.notes,
        lastApplyResult=result,
        formulaVersion=draft.formulaVersion,
        guardFormulaVersion=draft.guardFormulaVersion,
        sourceSnapshot=draft.sourceSnapshot,
        createdAt=now,
        updatedAt=now,
    )


def _store_apply_result(draft: PriceDraftView, result: PriceApplyResponse) -> ApplyJobView:
    state, stop_required = _map_apply_state(result)
    job = _create_job(draft=draft, result=result, state=state, stop_required=stop_required)
    _MEMORY.jobs[job.jobId] = job

    new_draft_state: DraftState = {
        "accepted": "accepted",
        "local_applied": "local_applied",
        "failed": "failed",
        "blocked": "blocked",
        "needs_attention": "needs_attention",
        "sent": "sent",
        "queued": "queued",
    }.get(state, "needs_attention")
    _MEMORY.drafts[draft.draftId] = draft.model_copy(
        update={"state": new_draft_state, "applyJobId": job.jobId, "updatedAt": _now_utc()}
    )

    if state in {"accepted", "local_applied"}:
        history = _MEMORY.price_history.setdefault(draft.articleId, [])
        history.append(
            _PriceHistoryPoint(
                sellerPriceKopecks=draft.normalized.candidateSellerPriceKopecks,
                appliedAt=_now_utc(),
            )
        )
        _MEMORY.price_history[draft.articleId] = history[-50:]

    return job


def apply_approved_drafts(
    draft_ids: list[str],
    client: WbApiClient,
    real_apply_enabled: bool,
    local_apply_enabled: bool,
    request: ApplyDraftRequest,
) -> list[ApplyJobView]:
    drafts = [get_draft_or_404(draft_id) for draft_id in draft_ids]
    if not drafts:
        return []
    if any(draft.approvalState != "approved" or draft.approvalRef is None for draft in drafts):
        raise HTTPException(status_code=409, detail="PRICE_DRAFT_NOT_APPROVED")

    jobs_by_draft: dict[str, ApplyJobView] = {}
    ready: list[PriceDraftView] = []
    for draft in drafts:
        if draft.guardReport.canApply:
            ready.append(draft)
            continue
        result = PriceApplyResponse(
            sourceStatus="blocked",
            applyState="blocked",
            blockerIds=sorted(set(draft.guardReport.blockers + ["WB-23"])),
            wbUploadId=None,
            wbStatus=None,
            statusLabel="unknown",
            rowErrors=[],
            pollAttempts=0,
            observedAt=_now_utc(),
            notes=["Draft guard report contains blockers"],
        )
        jobs_by_draft[draft.draftId] = _store_apply_result(draft, result)

    if ready:
        apply_request = _to_apply_request(draft=ready[0], request=request).model_copy(
            update={"rows": [_to_apply_request(draft=draft, request=request).rows[0] for draft in ready]}
        )
        result = run_price_apply(
            client=client,
            payload=apply_request,
            real_apply_enabled=real_apply_enabled,
            local_apply_enabled=local_apply_enabled,
        )
        for draft in ready:
            draft_result = result.model_copy(
                update={
                    "rowErrors": [
                        row for row in result.rowErrors if row.nmId in {None, draft.nmId}
                    ]
                }
            )
            jobs_by_draft[draft.draftId] = _store_apply_result(draft, draft_result)

    return [jobs_by_draft[draft.draftId] for draft in drafts]


def apply_approved_draft(
    draft_id: str,
    client: WbApiClient,
    real_apply_enabled: bool,
    local_apply_enabled: bool,
    request: ApplyDraftRequest,
) -> ApplyJobView:
    return apply_approved_drafts(
        draft_ids=[draft_id],
        client=client,
        real_apply_enabled=real_apply_enabled,
        local_apply_enabled=local_apply_enabled,
        request=request,
    )[0]


def get_apply_job_or_404(job_id: str) -> ApplyJobView:
    job = _MEMORY.jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="PRICE_APPLY_JOB_NOT_FOUND")
    return job


def retry_apply_job(
    job_id: str,
    client: WbApiClient,
    real_apply_enabled: bool,
    local_apply_enabled: bool,
    request: RetryApplyJobRequest,
) -> ApplyJobView:
    job = get_apply_job_or_404(job_id)
    if job.state not in {"failed", "needs_attention"}:
        raise HTTPException(status_code=409, detail="PRICE_APPLY_JOB_RETRY_NOT_ALLOWED")
    if job.retryCount >= job.maxRetryCount:
        raise HTTPException(status_code=409, detail="PRICE_APPLY_JOB_RETRY_LIMIT_REACHED")

    draft = get_draft_or_404(job.draftId)
    result = run_price_apply(
        client=client,
        payload=PriceApplyRequest(
            scenario=request.scenario,
            dryRun=False,
            pollMaxAttempts=request.pollMaxAttempts,
            pollDelaySeconds=request.pollDelaySeconds,
            rows=[
                PriceApplyRowRequest(
                    nmId=draft.nmId,
                    priceKopecks=draft.normalized.candidateSellerPriceKopecks,
                    discountPct=0,
                    minPriceKopecks=draft.normalized.minPriceKopecks,
                )
            ],
        ),
        real_apply_enabled=real_apply_enabled,
        local_apply_enabled=local_apply_enabled,
    )

    state, stop_required = _map_apply_state(result)
    now = _now_utc()
    next_retry_at: datetime | None = None
    retry_count = job.retryCount + (1 if state in {"failed", "needs_attention"} else 0)
    if state in {"failed", "needs_attention"} and retry_count < job.maxRetryCount:
        next_retry_at = now + timedelta(minutes=5 * (2 ** (retry_count - 1)))

    updated = job.model_copy(
        update={
            "state": state,
            "sourceStatus": result.sourceStatus,
            "blockerIds": result.blockerIds,
            "wbUploadId": result.wbUploadId,
            "wbStatus": result.wbStatus,
            "rowErrors": [
                ApplyJobRowError(
                    nmId=row.nmId,
                    sizeId=row.sizeId,
                    wbStatus=row.wbStatus,
                    errorText=row.errorText,
                )
                for row in result.rowErrors
            ],
            "retryCount": retry_count,
            "nextRetryAt": next_retry_at,
            "stopRequired": stop_required,
            "notes": result.notes,
            "lastApplyResult": result,
            "updatedAt": now,
        }
    )
    _MEMORY.jobs[job_id] = updated
    return updated
