from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Request
from vella_wb_19_05.models import AbcReportResponse, AdsPerformanceResponse, PnlReportResponse, ReportGroupBy, RnpReportResponse

from app.cabinet.store import get_user_wb_token_secret
from app.control_plane.auth import actor_from_request, has_permission
from app.control_plane.store import assert_permission_or_audit, record_audit_event
from app.wb_reports_sprint_d import (
    DEFAULT_FROM,
    DEFAULT_TO,
    ExportCurrentViewResponse,
    PlanFactDimension,
    PlanFactResponse,
    PnlRequestedState,
    SkuRatingResponse,
    build_abc_report,
    build_ads_performance_report,
    build_export_response,
    build_plan_fact_report,
    build_pnl_report,
    build_rnp_report,
    build_sku_rating_report,
)


router = APIRouter(tags=["wb-reports-sprint-d"])


def _actor_wb_token(actor) -> str | None:
    token = get_user_wb_token_secret(actor.user_id)
    return token.strip() if token and token.strip() else None


@router.get("/api/v1/wb-reports/pnl", response_model=PnlReportResponse)
def get_pnl_report(
    request: Request,
    dateFrom: date = DEFAULT_FROM,
    dateTo: date = DEFAULT_TO,
    groupBy: ReportGroupBy = "sku",
    source: PnlRequestedState = "preliminary",
) -> PnlReportResponse:
    actor = actor_from_request(request)
    assert_permission_or_audit(
        actor=actor,
        permission="settings:read",
        action="reports.pnl.get",
        object_type="wb_report",
        object_id=f"pnl:{groupBy}",
        reason="actor cannot read P&L report",
    )
    finance_allowed = has_permission(actor, "finance:read")
    report = build_pnl_report(
        date_from=dateFrom,
        date_to=dateTo,
        group_by=groupBy,
        requested_state=source,
        finance_allowed=finance_allowed,
        organization_id=actor.organization_id,
        wb_token=None,
    )
    record_audit_event(
        actor=actor,
        action="reports.pnl.get",
        object_type="wb_report",
        object_id=f"pnl:{groupBy}",
        before_state=None,
        after_state={
            "reportState": report.reportState,
            "sourceStatus": report.sourceStatus,
            "blockedReasonIds": report.blockerIds,
            "financeAllowed": finance_allowed,
        },
        reason="read pnl report",
        approval_ref=None,
        evidence_refs=["SPRINT_D", "NRP_LITE", "WB-11_CLOSED_2026-05-29", "WB-24_CLOSED_2026-05-29"],
    )
    return report


@router.get("/api/v1/wb-reports/ads/performance", response_model=AdsPerformanceResponse)
def get_ads_performance(
    request: Request,
    dateFrom: date = DEFAULT_FROM,
    dateTo: date = DEFAULT_TO,
    groupBy: ReportGroupBy = "campaign",
) -> AdsPerformanceResponse:
    actor = actor_from_request(request)
    assert_permission_or_audit(
        actor=actor,
        permission="settings:read",
        action="reports.ads.get",
        object_type="wb_report",
        object_id=f"ads:{groupBy}",
        reason="actor cannot read ads performance report",
    )
    finance_allowed = has_permission(actor, "finance:read")
    report = build_ads_performance_report(
        date_from=dateFrom,
        date_to=dateTo,
        group_by=groupBy,
        finance_allowed=finance_allowed,
        organization_id=actor.organization_id,
        wb_token=None,
    )
    record_audit_event(
        actor=actor,
        action="reports.ads.get",
        object_type="wb_report",
        object_id=f"ads:{groupBy}",
        before_state=None,
        after_state={
            "sourceStatus": report.sourceStatus,
            "blockerIds": report.blockerIds,
            "financeAllowed": finance_allowed,
        },
        reason="read ads performance report",
        approval_ref=None,
        evidence_refs=["SPRINT_D", "WB-02_CLOSED_2026-06-01", "attribution_confidence"],
    )
    return report


@router.get("/api/v1/wb-reports/rnp", response_model=RnpReportResponse)
def get_rnp_report(
    request: Request,
    dateFrom: date = DEFAULT_FROM,
    dateTo: date = DEFAULT_TO,
    groupBy: ReportGroupBy = "sku",
) -> RnpReportResponse:
    actor = actor_from_request(request)
    assert_permission_or_audit(
        actor=actor,
        permission="settings:read",
        action="reports.rnp.get",
        object_type="wb_report",
        object_id=f"rnp:{groupBy}",
        reason="actor cannot read RNP report",
    )
    finance_allowed = has_permission(actor, "finance:read")
    report = build_rnp_report(
        date_from=dateFrom,
        date_to=dateTo,
        group_by=groupBy,
        finance_allowed=finance_allowed,
        organization_id=actor.organization_id,
        wb_token=None,
    )
    record_audit_event(
        actor=actor,
        action="reports.rnp.get",
        object_type="wb_report",
        object_id=f"rnp:{groupBy}",
        before_state=None,
        after_state={
            "sourceStatus": report.sourceStatus,
            "blockerIds": report.blockerIds,
            "financeAllowed": finance_allowed,
        },
        reason="read rnp report",
        approval_ref=None,
        evidence_refs=["SPRINT_D", "WB-02_CLOSED_2026-06-01", "WB-11_CLOSED_2026-05-29"],
    )
    return report


@router.get("/api/v1/wb-reports/abc", response_model=AbcReportResponse)
def get_abc_report(
    request: Request,
    dateFrom: date = DEFAULT_FROM,
    dateTo: date = DEFAULT_TO,
    groupBy: ReportGroupBy = "sku",
    filters: str = "",
) -> AbcReportResponse:
    actor = actor_from_request(request)
    assert_permission_or_audit(
        actor=actor,
        permission="settings:read",
        action="reports.abc.get",
        object_type="wb_report",
        object_id=f"abc:{groupBy}",
        reason="actor cannot read abc report",
    )
    finance_allowed = has_permission(actor, "finance:read")
    report = build_abc_report(
        date_from=dateFrom,
        date_to=dateTo,
        group_by=groupBy,
        filters=filters,
        finance_allowed=finance_allowed,
        organization_id=actor.organization_id,
    )
    record_audit_event(
        actor=actor,
        action="reports.abc.get",
        object_type="wb_report",
        object_id=f"abc:{groupBy}",
        before_state=None,
        after_state={
            "sourceStatus": report.sourceStatus,
            "filterHash": report.filteredSummary.filterHash,
            "financeAllowed": finance_allowed,
        },
        reason="read abc report",
        approval_ref=None,
        evidence_refs=["SPRINT_D", "ABC_FILTERED_SUMMARY"],
    )
    return report


@router.get("/api/v1/wb-reports/plan-fact", response_model=PlanFactResponse)
def get_plan_fact_report(
    request: Request,
    dateFrom: date = DEFAULT_FROM,
    dateTo: date = DEFAULT_TO,
    dimension: PlanFactDimension = "manager",
) -> PlanFactResponse:
    actor = actor_from_request(request)
    assert_permission_or_audit(
        actor=actor,
        permission="settings:read",
        action="reports.plan_fact.get",
        object_type="wb_report",
        object_id=f"plan-fact:{dimension}",
        reason="actor cannot read plan-fact report",
    )
    finance_allowed = has_permission(actor, "finance:read")
    report = build_plan_fact_report(date_from=dateFrom, date_to=dateTo, dimension=dimension, finance_allowed=finance_allowed)
    record_audit_event(
        actor=actor,
        action="reports.plan_fact.get",
        object_type="wb_report",
        object_id=f"plan-fact:{dimension}",
        before_state=None,
        after_state={
            "sourceStatus": report.sourceStatus,
            "blockerIds": report.blockerIds,
            "financeAllowed": finance_allowed,
        },
        reason="read plan-fact report",
        approval_ref=None,
        evidence_refs=["SPRINT_D", "WB-14A", "WB-24_CLOSED_2026-05-29"],
    )
    return report


@router.get("/api/v1/wb-reports/sku-rating", response_model=SkuRatingResponse)
def get_sku_rating_report(
    request: Request,
    dateFrom: date = DEFAULT_FROM,
    dateTo: date = DEFAULT_TO,
) -> SkuRatingResponse:
    actor = actor_from_request(request)
    assert_permission_or_audit(
        actor=actor,
        permission="settings:read",
        action="reports.sku_rating.get",
        object_type="wb_report",
        object_id="sku-rating",
        reason="actor cannot read sku rating report",
    )
    finance_allowed = has_permission(actor, "finance:read")
    report = build_sku_rating_report(date_from=dateFrom, date_to=dateTo, finance_allowed=finance_allowed)
    record_audit_event(
        actor=actor,
        action="reports.sku_rating.get",
        object_type="wb_report",
        object_id="sku-rating",
        before_state=None,
        after_state={
            "sourceStatus": report.sourceStatus,
            "rowsCount": len(report.rows),
            "financeAllowed": finance_allowed,
        },
        reason="read sku rating report",
        approval_ref=None,
        evidence_refs=["SPRINT_D", "RATING_GROUPS", "EXPLAINABLE_SCORE"],
    )
    return report


@router.get("/api/v1/wb-export/current-view", response_model=ExportCurrentViewResponse)
def get_export_current_view(
    request: Request,
    dateFrom: date = DEFAULT_FROM,
    dateTo: date = DEFAULT_TO,
    filters: str = "",
) -> ExportCurrentViewResponse:
    actor = actor_from_request(request)
    assert_permission_or_audit(
        actor=actor,
        permission="settings:read",
        action="reports.export.get",
        object_type="wb_export",
        object_id="current-view",
        reason="actor cannot request export",
    )
    finance_allowed = has_permission(actor, "finance:read")
    result = build_export_response(
        finance_allowed=finance_allowed,
        filters=filters,
        period_from=dateFrom,
        period_to=dateTo,
    )
    record_audit_event(
        actor=actor,
        action="reports.export.get",
        object_type="wb_export",
        object_id="current-view",
        before_state=None,
        after_state=result.model_dump(mode="json"),
        reason="request export current view",
        approval_ref=None,
        evidence_refs=["SPRINT_D", "WB-24_CLOSED_2026-05-29", "visibility_policy_company_monthly_costs"],
    )
    return result
