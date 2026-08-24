from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal
from uuid import uuid4

from fastapi import HTTPException
from pydantic import BaseModel, Field

from app.contracts.envelopes import UtcDateTime
from app.repricer_sprint_b import (
    DraftEconomicsInput,
    PriceRecommendationRequest,
    PriceRecommendationResponse,
    SourceSnapshot,
    build_price_recommendation,
)
from app.wb_api.client import WbApiClient


StrategyId = Literal[
    "baskets_orders_4599",
    "revenue_dynamics_4600",
    "night_price_mode",
    "spp_turnover_4445",
]
StrategyStatus = Literal["draft", "enabled", "disabled", "discovery_required"]
AssignmentScope = Literal["strategy", "sku", "group"]
RevenueMode = Literal["percent_only", "percent_rub_floor"]


WB14_STRATEGY_SCOPE_CONFIRMED = True
SKU_SCOPE_ONLY_BLOCKER = "SCOPE_SKU_ONLY_V1"
WB25_BLOCKER = "WB-25"


STRATEGY_FORMULA_VERSIONS: dict[StrategyId, str] = {
    "baskets_orders_4599": "frm-strategy-4599-v1",
    "revenue_dynamics_4600": "frm-strategy-4600-v1",
    "night_price_mode": "frm-night-price-mode-v1",
    "spp_turnover_4445": "frm-4445-discovery-required-v1",
}

STRATEGY_SOURCE_DEPENDENCIES: dict[StrategyId, list[str]] = {
    "baskets_orders_4599": [
        "current_price_before_spp",
        "current_price_after_spp",
        "spp_pct",
        "baskets_orders_signal",
        "pmin_pmax_validation",
    ],
    "revenue_dynamics_4600": [
        "current_price_before_spp",
        "current_price_after_spp",
        "spp_pct",
        "revenue_dynamics_signal",
        "pmin_pmax_validation",
    ],
    "night_price_mode": [
        "current_price_before_spp",
        "current_price_after_spp",
        "spp_pct",
        "night_schedule",
        "pmin_pmax_validation",
    ],
    "spp_turnover_4445": ["spp_pct", "turnover_signal"],
}


class StrategyVersionCreateRequest(BaseModel):
    desiredStatus: Literal["draft", "enabled", "disabled"] = "draft"
    reason: str | None = None
    approvalRef: str | None = None

    capPct: float | None = Field(default=None, ge=0.1, le=20)

    revenueMode: RevenueMode | None = None
    revenueMaxStepPct: float | None = Field(default=None, ge=0.1, le=20)
    revenueRubFloorKopecks: int | None = Field(default=None, ge=0)

    nightEnabled: bool | None = None
    nightWindowStartHour: int | None = Field(default=None, ge=0, le=23)
    nightWindowEndHour: int | None = Field(default=None, ge=0, le=23)
    nightTimezone: str | None = None


class StrategyVersionView(BaseModel):
    strategyId: StrategyId
    version: int = Field(ge=1)
    status: StrategyStatus
    formulaVersion: str = Field(min_length=1)
    sourceDependencies: list[str]
    config: dict[str, Any]
    blockedReasons: list[str]
    createdByActorId: str = Field(min_length=1)
    createdByRole: str = Field(min_length=1)
    reason: str | None = None
    approvalRef: str | None = None
    createdAt: UtcDateTime


class StrategyCatalogItem(BaseModel):
    strategyId: StrategyId
    status: StrategyStatus
    currentVersion: int = Field(ge=1)
    formulaVersion: str = Field(min_length=1)
    sourceDependencies: list[str]
    blockedReasons: list[str]
    scopeAssignmentEnabled: bool


class StrategyDryRunItem(BaseModel):
    articleId: str = Field(min_length=1)
    nmId: int = Field(gt=0)
    candidateSellerPriceKopecks: int = Field(gt=0)
    economics: DraftEconomicsInput

    basketsTrend: Literal["up", "down"] | None = None
    ordersTrend: Literal["up", "down"] | None = None

    revenueTrendPct: float | None = None

    nightTargetDeltaPct: float | None = Field(default=None, ge=-20, le=20)


class StrategyDryRunRequest(BaseModel):
    scenario: str = "complete"
    items: list[StrategyDryRunItem] = Field(min_length=1)
    revenueModeOverride: RevenueMode | None = None
    revenueRubFloorKopecksOverride: int | None = Field(default=None, ge=0)


class StrategyDryRunSkuResult(BaseModel):
    articleId: str = Field(min_length=1)
    nmId: int = Field(gt=0)
    currentSellerPriceKopecks: int | None = None
    candidateSellerPriceKopecks: int = Field(gt=0)
    recommendedSellerPriceKopecks: int | None = None
    deltaPct: float | None = None
    deltaKopecks: int | None = None
    explanation: str = Field(min_length=1)
    blockedReasons: list[str]
    guardBlockers: list[str]
    guardDetails: list[dict[str, Any]] = Field(default_factory=list)
    canCreateProductionDraft: bool
    autoCommitAllowed: bool
    formulaVersion: str = Field(min_length=1)
    sourceDependencies: list[str]
    sourceSnapshot: SourceSnapshot


class StrategyDryRunReport(BaseModel):
    runId: str = Field(min_length=1)
    strategyId: StrategyId
    strategyVersion: int = Field(ge=1)
    strategyStatus: StrategyStatus
    formulaVersion: str = Field(min_length=1)
    sourceDependencies: list[str]
    blockedReasons: list[str]
    items: list[StrategyDryRunSkuResult]
    generatedAt: UtcDateTime


class StrategyDryRunRecord(BaseModel):
    runId: str = Field(min_length=1)
    strategyId: StrategyId
    strategyVersion: int = Field(ge=1)
    createdAt: UtcDateTime
    blockedReasons: list[str]
    resultSummary: dict[str, Any]


class StrategyAssignmentRequest(BaseModel):
    strategyId: StrategyId
    scope: AssignmentScope
    targetId: str = Field(min_length=1)


class StrategyAssignmentView(BaseModel):
    assignmentId: str = Field(min_length=1)
    strategyId: StrategyId
    scope: AssignmentScope
    targetId: str = Field(min_length=1)
    status: Literal["active", "blocked"]
    blockerIds: list[str]
    createdAt: UtcDateTime


class NightScheduleRequest(BaseModel):
    enabled: bool
    windowStartHour: int = Field(ge=0, le=23)
    windowEndHour: int = Field(ge=0, le=23)
    timezoneName: str = Field(min_length=1)
    approvalRef: str | None = None
    reason: str | None = None


class NightScheduleView(BaseModel):
    enabled: bool
    windowStartHour: int = Field(ge=0, le=23)
    windowEndHour: int = Field(ge=0, le=23)
    timezoneName: str = Field(min_length=1)
    approvalRef: str | None = None
    updatedAt: UtcDateTime


@dataclass
class _SprintCState:
    versions: dict[StrategyId, list[StrategyVersionView]] = field(default_factory=dict)
    dry_runs: dict[StrategyId, list[StrategyDryRunRecord]] = field(default_factory=dict)
    assignments: list[StrategyAssignmentView] = field(default_factory=list)


_MEMORY = _SprintCState()


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _strategy_ids() -> tuple[StrategyId, ...]:
    return (
        "baskets_orders_4599",
        "revenue_dynamics_4600",
        "night_price_mode",
        "spp_turnover_4445",
    )


def _ensure_defaults() -> None:
    if _MEMORY.versions:
        return

    now = _now_utc()
    _MEMORY.versions = {
        "baskets_orders_4599": [
            StrategyVersionView(
                strategyId="baskets_orders_4599",
                version=1,
                status="draft",
                formulaVersion=STRATEGY_FORMULA_VERSIONS["baskets_orders_4599"],
                sourceDependencies=STRATEGY_SOURCE_DEPENDENCIES["baskets_orders_4599"],
                config={"capPct": 3.0},
                blockedReasons=[],
                createdByActorId="system",
                createdByRole="admin",
                reason="initial seed",
                approvalRef=None,
                createdAt=now,
            )
        ],
        "revenue_dynamics_4600": [
            StrategyVersionView(
                strategyId="revenue_dynamics_4600",
                version=1,
                status="draft",
                formulaVersion=STRATEGY_FORMULA_VERSIONS["revenue_dynamics_4600"],
                sourceDependencies=STRATEGY_SOURCE_DEPENDENCIES["revenue_dynamics_4600"],
                config={"mode": None, "maxStepPct": 3.0, "rubFloorKopecks": None},
                blockedReasons=["revenue_mode_not_selected"],
                createdByActorId="system",
                createdByRole="admin",
                reason="initial seed",
                approvalRef=None,
                createdAt=now,
            )
        ],
        "night_price_mode": [
            StrategyVersionView(
                strategyId="night_price_mode",
                version=1,
                status="disabled",
                formulaVersion=STRATEGY_FORMULA_VERSIONS["night_price_mode"],
                sourceDependencies=STRATEGY_SOURCE_DEPENDENCIES["night_price_mode"],
                config={"enabled": False, "windowStartHour": 1, "windowEndHour": 5, "timezone": "Europe/Moscow"},
                blockedReasons=[],
                createdByActorId="system",
                createdByRole="admin",
                reason="initial seed",
                approvalRef=None,
                createdAt=now,
            )
        ],
        "spp_turnover_4445": [
            StrategyVersionView(
                strategyId="spp_turnover_4445",
                version=1,
                status="discovery_required",
                formulaVersion=STRATEGY_FORMULA_VERSIONS["spp_turnover_4445"],
                sourceDependencies=STRATEGY_SOURCE_DEPENDENCIES["spp_turnover_4445"],
                config={"state": "discovery_required"},
                blockedReasons=[f"{WB25_BLOCKER}: rules are not confirmed by client"],
                createdByActorId="system",
                createdByRole="admin",
                reason="initial seed",
                approvalRef=None,
                createdAt=now,
            )
        ],
    }
    _MEMORY.dry_runs = {strategy_id: [] for strategy_id in _strategy_ids()}


def _parse_strategy_id(value: str) -> StrategyId:
    if value not in _strategy_ids():
        raise HTTPException(status_code=404, detail="STRATEGY_NOT_FOUND")
    return value  # type: ignore[return-value]


def _latest(strategy_id: StrategyId) -> StrategyVersionView:
    _ensure_defaults()
    rows = _MEMORY.versions[strategy_id]
    return rows[-1]


def list_strategy_catalog() -> list[StrategyCatalogItem]:
    _ensure_defaults()
    result: list[StrategyCatalogItem] = []
    for strategy_id in _strategy_ids():
        current = _latest(strategy_id)
        result.append(
            StrategyCatalogItem(
                strategyId=strategy_id,
                status=current.status,
                currentVersion=current.version,
                formulaVersion=current.formulaVersion,
                sourceDependencies=current.sourceDependencies,
                blockedReasons=current.blockedReasons,
                scopeAssignmentEnabled=WB14_STRATEGY_SCOPE_CONFIRMED,
            )
        )
    return result


def list_strategy_versions(strategy_id_raw: str) -> list[StrategyVersionView]:
    strategy_id = _parse_strategy_id(strategy_id_raw)
    _ensure_defaults()
    return list(_MEMORY.versions[strategy_id])


def _build_config(strategy_id: StrategyId, request: StrategyVersionCreateRequest, previous: StrategyVersionView) -> tuple[dict[str, Any], list[str], StrategyStatus]:
    blocked_reasons: list[str] = []
    next_status: StrategyStatus = request.desiredStatus  # type: ignore[assignment]

    if strategy_id == "baskets_orders_4599":
        cap_pct = request.capPct if request.capPct is not None else float(previous.config.get("capPct", 3.0))
        config = {"capPct": cap_pct}
        return config, blocked_reasons, next_status

    if strategy_id == "revenue_dynamics_4600":
        mode = request.revenueMode if request.revenueMode is not None else previous.config.get("mode")
        max_step = request.revenueMaxStepPct if request.revenueMaxStepPct is not None else float(previous.config.get("maxStepPct", 3.0))
        rub_floor = request.revenueRubFloorKopecks if request.revenueRubFloorKopecks is not None else previous.config.get("rubFloorKopecks")
        if mode is None:
            blocked_reasons.append("revenue_mode_not_selected")
            if next_status == "enabled":
                next_status = "draft"
        config = {"mode": mode, "maxStepPct": max_step, "rubFloorKopecks": rub_floor}
        return config, blocked_reasons, next_status

    if strategy_id == "night_price_mode":
        enabled = request.nightEnabled if request.nightEnabled is not None else bool(previous.config.get("enabled", False))
        start_hour = request.nightWindowStartHour if request.nightWindowStartHour is not None else int(previous.config.get("windowStartHour", 1))
        end_hour = request.nightWindowEndHour if request.nightWindowEndHour is not None else int(previous.config.get("windowEndHour", 5))
        timezone_name = request.nightTimezone if request.nightTimezone is not None else str(previous.config.get("timezone", "Europe/Moscow"))
        if start_hour == end_hour:
            blocked_reasons.append("night_window_invalid")
            enabled = False
            next_status = "disabled"
        if enabled and not request.approvalRef:
            blocked_reasons.append("night_enable_requires_approval_ref")
            enabled = False
            next_status = "disabled"
        config = {
            "enabled": enabled,
            "windowStartHour": start_hour,
            "windowEndHour": end_hour,
            "timezone": timezone_name,
        }
        return config, blocked_reasons, next_status if enabled else "disabled"

    blocked_reasons.append(f"{WB25_BLOCKER}: strategy remains discovery_required")
    return {"state": "discovery_required"}, blocked_reasons, "discovery_required"


def create_strategy_version(
    strategy_id_raw: str,
    actor_id: str,
    actor_role: str,
    request: StrategyVersionCreateRequest,
) -> StrategyVersionView:
    strategy_id = _parse_strategy_id(strategy_id_raw)
    _ensure_defaults()

    previous = _latest(strategy_id)
    next_version = previous.version + 1

    config, blocked_reasons, next_status = _build_config(strategy_id, request, previous)

    if strategy_id == "spp_turnover_4445":
        next_status = "discovery_required"

    created = StrategyVersionView(
        strategyId=strategy_id,
        version=next_version,
        status=next_status,
        formulaVersion=STRATEGY_FORMULA_VERSIONS[strategy_id],
        sourceDependencies=STRATEGY_SOURCE_DEPENDENCIES[strategy_id],
        config=config,
        blockedReasons=blocked_reasons,
        createdByActorId=actor_id,
        createdByRole=actor_role,
        reason=request.reason,
        approvalRef=request.approvalRef,
        createdAt=_now_utc(),
    )
    _MEMORY.versions[strategy_id].append(created)
    return created


def get_night_schedule() -> NightScheduleView:
    current = _latest("night_price_mode")
    cfg = current.config
    return NightScheduleView(
        enabled=bool(cfg.get("enabled", False)),
        windowStartHour=int(cfg.get("windowStartHour", 1)),
        windowEndHour=int(cfg.get("windowEndHour", 5)),
        timezoneName=str(cfg.get("timezone", "Europe/Moscow")),
        approvalRef=current.approvalRef,
        updatedAt=current.createdAt,
    )


def update_night_schedule(actor_id: str, actor_role: str, request: NightScheduleRequest) -> StrategyVersionView:
    if request.windowStartHour == request.windowEndHour:
        raise HTTPException(status_code=409, detail="NIGHT_WINDOW_INVALID")
    if request.enabled and not request.approvalRef:
        raise HTTPException(status_code=409, detail="NIGHT_ENABLE_REQUIRES_APPROVAL_REF")

    create_request = StrategyVersionCreateRequest(
        desiredStatus="enabled" if request.enabled else "disabled",
        reason=request.reason,
        approvalRef=request.approvalRef,
        nightEnabled=request.enabled,
        nightWindowStartHour=request.windowStartHour,
        nightWindowEndHour=request.windowEndHour,
        nightTimezone=request.timezoneName,
    )
    return create_strategy_version(
        strategy_id_raw="night_price_mode",
        actor_id=actor_id,
        actor_role=actor_role,
        request=create_request,
    )


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _base_price(recommendation: PriceRecommendationResponse, fallback: int) -> int:
    if fallback > 0:
        return fallback
    if recommendation.normalized.currentSellerPriceKopecks is not None:
        return recommendation.normalized.currentSellerPriceKopecks
    return fallback


def _guard_reason_codes(guard_report: Any) -> list[str]:
    reasons = list(getattr(guard_report, "blockers", []) or [])
    for trigger in getattr(guard_report, "triggers", []) or []:
        code = getattr(trigger, "code", None)
        if code:
            reasons.append(str(code))
        observed = getattr(trigger, "observedValue", None)
        if code == "pmin_pmax_block" and isinstance(observed, str):
            reasons.extend([item.strip() for item in observed.split(",") if item.strip()])
    return sorted(set(reasons))


def _guard_detail_payload(guard_report: Any) -> list[dict[str, Any]]:
    details: list[dict[str, Any]] = []
    for trigger in getattr(guard_report, "triggers", []) or []:
        code = getattr(trigger, "code", None)
        if not code:
            continue
        item: dict[str, Any] = {"code": str(code)}
        message = getattr(trigger, "message", None)
        observed = getattr(trigger, "observedValue", None)
        threshold = getattr(trigger, "threshold", None)
        if message is not None:
            item["message"] = message
        if observed is not None:
            item["observedValue"] = observed
        if threshold is not None:
            item["threshold"] = threshold
        details.append(item)
    return details


def _dry_run_4599(
    version: StrategyVersionView,
    item: StrategyDryRunItem,
    recommendation: PriceRecommendationResponse,
) -> StrategyDryRunSkuResult:
    if item.basketsTrend is None or item.ordersTrend is None:
        blocked_reasons = ["4599_requires_baskets_and_orders_trend"]
        blocked_reasons.extend(_guard_reason_codes(recommendation.guardReport))
        return StrategyDryRunSkuResult(
            articleId=item.articleId,
            nmId=item.nmId,
            currentSellerPriceKopecks=recommendation.normalized.currentSellerPriceKopecks,
            candidateSellerPriceKopecks=item.candidateSellerPriceKopecks,
            recommendedSellerPriceKopecks=None,
            deltaPct=None,
            deltaKopecks=None,
            explanation="Missing baskets/orders trend inputs for 4599",
            blockedReasons=blocked_reasons,
            guardBlockers=recommendation.guardReport.blockers,
            guardDetails=_guard_detail_payload(recommendation.guardReport),
            canCreateProductionDraft=False,
            autoCommitAllowed=False,
            formulaVersion=version.formulaVersion,
            sourceDependencies=version.sourceDependencies,
            sourceSnapshot=recommendation.sourceSnapshot,
        )

    matrix: dict[tuple[str, str], float] = {
        ("up", "up"): 3.0,
        ("down", "up"): 1.0,
        ("up", "down"): -1.0,
        ("down", "down"): -3.0,
    }
    raw_delta = matrix[(item.basketsTrend, item.ordersTrend)]
    cap_pct = float(version.config.get("capPct", 3.0))
    delta_pct = _clamp(raw_delta, -cap_pct, cap_pct)

    base_price = _base_price(recommendation, item.candidateSellerPriceKopecks)
    recommended = int(round(base_price * (1 + delta_pct / 100)))
    delta_kopecks = recommended - base_price

    blocked_reasons = _guard_reason_codes(recommendation.guardReport)
    if version.status != "enabled":
        blocked_reasons.append("strategy_not_enabled_for_production_draft")

    explanation = (
        f"4599 matrix: baskets={item.basketsTrend}, orders={item.ordersTrend}, rawDelta={raw_delta:+.1f}% "
        f"-> cappedDelta={delta_pct:+.1f}% (cap={cap_pct:.1f}%)."
    )

    return StrategyDryRunSkuResult(
        articleId=item.articleId,
        nmId=item.nmId,
        currentSellerPriceKopecks=base_price,
        candidateSellerPriceKopecks=item.candidateSellerPriceKopecks,
        recommendedSellerPriceKopecks=recommended,
        deltaPct=round(delta_pct, 4),
        deltaKopecks=delta_kopecks,
        explanation=explanation,
        blockedReasons=blocked_reasons,
        guardBlockers=recommendation.guardReport.blockers,
        guardDetails=_guard_detail_payload(recommendation.guardReport),
        canCreateProductionDraft=not blocked_reasons,
        autoCommitAllowed=False,
        formulaVersion=version.formulaVersion,
        sourceDependencies=version.sourceDependencies,
        sourceSnapshot=recommendation.sourceSnapshot,
    )


def _dry_run_4600(
    version: StrategyVersionView,
    item: StrategyDryRunItem,
    recommendation: PriceRecommendationResponse,
    mode_override: RevenueMode | None,
    floor_override: int | None,
) -> StrategyDryRunSkuResult:
    mode = mode_override or version.config.get("mode")
    max_step_pct = float(version.config.get("maxStepPct", 3.0))
    rub_floor = floor_override if floor_override is not None else version.config.get("rubFloorKopecks")

    blocked_reasons = _guard_reason_codes(recommendation.guardReport)
    if item.revenueTrendPct is None:
        blocked_reasons.append("4600_requires_revenue_trend_pct")
    if mode is None:
        blocked_reasons.append("revenue_mode_not_selected")

    base_price = _base_price(recommendation, item.candidateSellerPriceKopecks)
    if blocked_reasons:
        return StrategyDryRunSkuResult(
            articleId=item.articleId,
            nmId=item.nmId,
            currentSellerPriceKopecks=base_price,
            candidateSellerPriceKopecks=item.candidateSellerPriceKopecks,
            recommendedSellerPriceKopecks=None,
            deltaPct=None,
            deltaKopecks=None,
            explanation="Revenue dynamics 4600 is blocked: mode or trend input is missing",
            blockedReasons=blocked_reasons,
            guardBlockers=recommendation.guardReport.blockers,
            guardDetails=_guard_detail_payload(recommendation.guardReport),
            canCreateProductionDraft=False,
            autoCommitAllowed=False,
            formulaVersion=version.formulaVersion,
            sourceDependencies=version.sourceDependencies,
            sourceSnapshot=recommendation.sourceSnapshot,
        )

    assert item.revenueTrendPct is not None
    raw_delta_pct = _clamp(item.revenueTrendPct * 0.25, -max_step_pct, max_step_pct)
    recommended = int(round(base_price * (1 + raw_delta_pct / 100)))
    delta_kopecks = recommended - base_price
    applied_floor = False

    if mode == "percent_rub_floor" and rub_floor is not None and rub_floor > 0 and delta_kopecks != 0 and abs(delta_kopecks) < rub_floor:
        sign = 1 if delta_kopecks > 0 else -1
        delta_kopecks = sign * rub_floor
        recommended = base_price + delta_kopecks
        applied_floor = True

    delta_pct = (delta_kopecks / base_price * 100) if base_price > 0 else 0

    if version.status != "enabled":
        blocked_reasons.append("strategy_not_enabled_for_production_draft")

    explanation = (
        f"4600 mode={mode}, revenueTrendPct={item.revenueTrendPct:+.2f}% -> rawDelta={raw_delta_pct:+.2f}%"
    )
    if applied_floor and rub_floor is not None:
        explanation += f", rub floor applied ({rub_floor} kopecks)."
    else:
        explanation += "."

    return StrategyDryRunSkuResult(
        articleId=item.articleId,
        nmId=item.nmId,
        currentSellerPriceKopecks=base_price,
        candidateSellerPriceKopecks=item.candidateSellerPriceKopecks,
        recommendedSellerPriceKopecks=recommended,
        deltaPct=round(delta_pct, 4),
        deltaKopecks=delta_kopecks,
        explanation=explanation,
        blockedReasons=blocked_reasons,
        guardBlockers=recommendation.guardReport.blockers,
        guardDetails=_guard_detail_payload(recommendation.guardReport),
        canCreateProductionDraft=not blocked_reasons,
        autoCommitAllowed=False,
        formulaVersion=version.formulaVersion,
        sourceDependencies=version.sourceDependencies,
        sourceSnapshot=recommendation.sourceSnapshot,
    )


def _dry_run_night(
    version: StrategyVersionView,
    item: StrategyDryRunItem,
    recommendation: PriceRecommendationResponse,
) -> StrategyDryRunSkuResult:
    cfg = version.config
    enabled = bool(cfg.get("enabled", False))
    start_hour = int(cfg.get("windowStartHour", 1))
    end_hour = int(cfg.get("windowEndHour", 5))
    target_delta = item.nightTargetDeltaPct if item.nightTargetDeltaPct is not None else 1.0

    base_price = _base_price(recommendation, item.candidateSellerPriceKopecks)
    recommended = int(round(base_price * (1 + target_delta / 100)))
    delta_kopecks = recommended - base_price

    blocked_reasons = _guard_reason_codes(recommendation.guardReport)
    if not enabled:
        blocked_reasons.append("night_mode_disabled")
    blocked_reasons.append("night_mode_auto_commit_requires_separate_approval")

    explanation = (
        f"Night mode window {start_hour:02d}:00-{end_hour:02d}:00, targetDelta={target_delta:+.2f}%. "
        "Dry-run only: auto-commit is disabled by policy."
    )

    return StrategyDryRunSkuResult(
        articleId=item.articleId,
        nmId=item.nmId,
        currentSellerPriceKopecks=base_price,
        candidateSellerPriceKopecks=item.candidateSellerPriceKopecks,
        recommendedSellerPriceKopecks=recommended,
        deltaPct=round(target_delta, 4),
        deltaKopecks=delta_kopecks,
        explanation=explanation,
        blockedReasons=blocked_reasons,
        guardBlockers=recommendation.guardReport.blockers,
        guardDetails=_guard_detail_payload(recommendation.guardReport),
        canCreateProductionDraft=False,
        autoCommitAllowed=False,
        formulaVersion=version.formulaVersion,
        sourceDependencies=version.sourceDependencies,
        sourceSnapshot=recommendation.sourceSnapshot,
    )


def _dry_run_4445(
    version: StrategyVersionView,
    item: StrategyDryRunItem,
    recommendation: PriceRecommendationResponse,
) -> StrategyDryRunSkuResult:
    blocked_reasons = [f"{WB25_BLOCKER}: strategy is discovery_required"]
    blocked_reasons.extend(_guard_reason_codes(recommendation.guardReport))
    explanation = "4445 remains disabled/discovery_required until client confirms SPP + turnover rules"

    return StrategyDryRunSkuResult(
        articleId=item.articleId,
        nmId=item.nmId,
        currentSellerPriceKopecks=recommendation.normalized.currentSellerPriceKopecks,
        candidateSellerPriceKopecks=item.candidateSellerPriceKopecks,
        recommendedSellerPriceKopecks=None,
        deltaPct=None,
        deltaKopecks=None,
        explanation=explanation,
        blockedReasons=blocked_reasons,
        guardBlockers=recommendation.guardReport.blockers,
        guardDetails=_guard_detail_payload(recommendation.guardReport),
        canCreateProductionDraft=False,
        autoCommitAllowed=False,
        formulaVersion=version.formulaVersion,
        sourceDependencies=version.sourceDependencies,
        sourceSnapshot=recommendation.sourceSnapshot,
    )


def _version_with_overrides(strategy_id: StrategyId, config_override: dict[str, Any] | None) -> StrategyVersionView:
    version = _latest(strategy_id)
    if not config_override:
        return version
    merged = {**version.config, **config_override}
    return version.model_copy(update={"config": merged, "status": "enabled"})


def _finalize_with_recommended_guards(
    *,
    client: WbApiClient,
    scenario: str,
    item: StrategyDryRunItem,
    result: StrategyDryRunSkuResult,
    min_price_kopecks: int | None,
    p_max_kopecks: int | None,
    execution_mode: bool,
    sku_row: dict[str, Any] | None = None,
) -> StrategyDryRunSkuResult:
    if result.recommendedSellerPriceKopecks is None:
        return result

    recommended = build_price_recommendation(
        client=client,
        payload=PriceRecommendationRequest(
            scenario=scenario,
            articleId=item.articleId,
            nmId=item.nmId,
            candidateSellerPriceKopecks=result.recommendedSellerPriceKopecks,
            minPriceKopecks=min_price_kopecks,
            pMaxKopecks=p_max_kopecks,
            economics=item.economics,
        ),
        sku_row=sku_row,
    )
    blocked_reasons = [reason for reason in result.blockedReasons if reason != "strategy_not_enabled_for_production_draft"]
    blocked_reasons.extend(_guard_reason_codes(recommended.guardReport))
    blocked_reasons = sorted(set(blocked_reasons))
    if execution_mode:
        blocked_reasons = [reason for reason in blocked_reasons if reason != "strategy_not_enabled_for_production_draft"]

    return result.model_copy(
        update={
            "blockedReasons": blocked_reasons,
            "guardBlockers": recommended.guardReport.blockers,
            "guardDetails": _guard_detail_payload(recommended.guardReport),
            "canCreateProductionDraft": recommended.guardReport.canApply and not blocked_reasons,
            "sourceSnapshot": recommended.sourceSnapshot,
        }
    )


def run_strategy_item_with_guards(
    *,
    strategy_id: StrategyId,
    client: WbApiClient,
    scenario: str,
    item: StrategyDryRunItem,
    config_override: dict[str, Any] | None = None,
    min_price_kopecks: int | None = None,
    p_max_kopecks: int | None = None,
    execution_mode: bool = False,
    revenue_mode_override: RevenueMode | None = None,
    revenue_rub_floor_override: int | None = None,
    sku_row: dict[str, Any] | None = None,
) -> StrategyDryRunSkuResult:
    version = _version_with_overrides(strategy_id, config_override)
    recommendation = build_price_recommendation(
        client=client,
        payload=PriceRecommendationRequest(
            scenario=scenario,
            articleId=item.articleId,
            nmId=item.nmId,
            candidateSellerPriceKopecks=item.candidateSellerPriceKopecks,
            minPriceKopecks=min_price_kopecks,
            pMaxKopecks=p_max_kopecks,
            economics=item.economics,
        ),
        sku_row=sku_row,
    )

    if strategy_id == "baskets_orders_4599":
        result = _dry_run_4599(version=version, item=item, recommendation=recommendation)
    elif strategy_id == "revenue_dynamics_4600":
        result = _dry_run_4600(
            version=version,
            item=item,
            recommendation=recommendation,
            mode_override=revenue_mode_override,
            floor_override=revenue_rub_floor_override,
        )
    elif strategy_id == "night_price_mode":
        result = _dry_run_night(version=version, item=item, recommendation=recommendation)
    else:
        result = _dry_run_4445(version=version, item=item, recommendation=recommendation)

    if execution_mode and strategy_id == "night_price_mode":
        result = result.model_copy(
            update={
                "blockedReasons": [
                    reason
                    for reason in result.blockedReasons
                    if reason not in {"night_mode_disabled", "night_mode_auto_commit_requires_separate_approval"}
                ],
            }
        )

    return _finalize_with_recommended_guards(
        client=client,
        scenario=scenario,
        item=item,
        result=result,
        min_price_kopecks=min_price_kopecks,
        p_max_kopecks=p_max_kopecks,
        execution_mode=execution_mode,
        sku_row=sku_row,
    )


def run_strategy_dry_run(strategy_id_raw: str, client: WbApiClient, request: StrategyDryRunRequest) -> StrategyDryRunReport:
    strategy_id = _parse_strategy_id(strategy_id_raw)
    version = _latest(strategy_id)

    results: list[StrategyDryRunSkuResult] = []
    for item in request.items:
        recommendation = build_price_recommendation(
            client=client,
            payload=PriceRecommendationRequest(
                scenario=request.scenario,
                articleId=item.articleId,
                nmId=item.nmId,
                candidateSellerPriceKopecks=item.candidateSellerPriceKopecks,
                minPriceKopecks=None,
                pMaxKopecks=None,
                economics=item.economics,
            ),
        )

        if strategy_id == "baskets_orders_4599":
            result = _dry_run_4599(version=version, item=item, recommendation=recommendation)
        elif strategy_id == "revenue_dynamics_4600":
            result = _dry_run_4600(
                version=version,
                item=item,
                recommendation=recommendation,
                mode_override=request.revenueModeOverride,
                floor_override=request.revenueRubFloorKopecksOverride,
            )
        elif strategy_id == "night_price_mode":
            result = _dry_run_night(version=version, item=item, recommendation=recommendation)
        else:
            result = _dry_run_4445(version=version, item=item, recommendation=recommendation)

        results.append(result)

    report_blockers = sorted({reason for result in results for reason in result.blockedReasons})
    report = StrategyDryRunReport(
        runId=f"dry_{uuid4().hex}",
        strategyId=strategy_id,
        strategyVersion=version.version,
        strategyStatus=version.status,
        formulaVersion=version.formulaVersion,
        sourceDependencies=version.sourceDependencies,
        blockedReasons=report_blockers,
        items=results,
        generatedAt=_now_utc(),
    )

    _MEMORY.dry_runs[strategy_id].append(
        StrategyDryRunRecord(
            runId=report.runId,
            strategyId=strategy_id,
            strategyVersion=version.version,
            createdAt=report.generatedAt,
            blockedReasons=report.blockedReasons,
            resultSummary={
                "skuCount": len(report.items),
                "canCreateProductionDraftCount": sum(1 for row in report.items if row.canCreateProductionDraft),
                "blockedCount": sum(1 for row in report.items if row.blockedReasons),
            },
        )
    )

    return report


def list_strategy_dry_runs(strategy_id_raw: str) -> list[StrategyDryRunRecord]:
    strategy_id = _parse_strategy_id(strategy_id_raw)
    _ensure_defaults()
    return list(reversed(_MEMORY.dry_runs[strategy_id]))


def create_strategy_assignment(request: StrategyAssignmentRequest) -> StrategyAssignmentView:
    _ensure_defaults()
    if not WB14_STRATEGY_SCOPE_CONFIRMED:
        blocked = StrategyAssignmentView(
            assignmentId=f"asgn_{uuid4().hex}",
            strategyId=request.strategyId,
            scope=request.scope,
            targetId=request.targetId,
            status="blocked",
            blockerIds=["WB-14"],
            createdAt=_now_utc(),
        )
        return blocked

    if request.scope != "sku":
        return StrategyAssignmentView(
            assignmentId=f"asgn_{uuid4().hex}",
            strategyId=request.strategyId,
            scope=request.scope,
            targetId=request.targetId,
            status="blocked",
            blockerIds=[SKU_SCOPE_ONLY_BLOCKER],
            createdAt=_now_utc(),
        )

    active = StrategyAssignmentView(
        assignmentId=f"asgn_{uuid4().hex}",
        strategyId=request.strategyId,
        scope=request.scope,
        targetId=request.targetId,
        status="active",
        blockerIds=[],
        createdAt=_now_utc(),
    )
    _MEMORY.assignments.append(active)
    return active


def list_strategy_assignments() -> list[StrategyAssignmentView]:
    _ensure_defaults()
    return list(_MEMORY.assignments)
