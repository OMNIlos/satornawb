from datetime import date

import pytest
from pydantic import ValidationError

from vella_wb_19_05.models import (
    AdsPerformanceResponse,
    AiReviewApproval,
    PnlReportResponse,
    PriceGuardResponse,
    RnpReportResponse,
)
from vella_wb_19_05.registry import BLOCKER_REGISTRY
from vella_wb_19_05.stubs import (
    build_abc_report_stub,
    build_ads_performance_stub,
    build_ai_review_approval_stub,
    build_pnl_report_stub,
    build_price_guard_stub,
    build_rnp_report_stub,
)


def dump(model):
    return model.model_dump(mode="python")


def test_source_registry_contains_19_05_blockers():
    assert {"WB-02", "WB-03", "WB-06", "WB-11", "WB-12", "WB-13", "WB-14A", "WB-19A", "WB-22", "WB-23"} <= set(BLOCKER_REGISTRY)


def test_pnl_financial_stub_is_not_final_while_blocked():
    report = build_pnl_report_stub()

    assert report.reportState == "blocked"
    assert report.sourceStatus == "blocked"
    assert {"WB-12", "WB-13"} <= set(report.blockerIds)

    payload = dump(report)
    payload["reportState"] = "final"

    with pytest.raises(ValidationError):
        PnlReportResponse.model_validate(payload)


def test_pnl_final_rejects_blocked_nested_financial_sources():
    report = build_pnl_report_stub()
    payload = dump(report)
    payload["reportState"] = "final"
    payload["sourceStatus"] = "fresh"
    payload["confidence"] = "high"
    payload["blockerIds"] = []

    with pytest.raises(ValidationError):
        PnlReportResponse.model_validate(payload)


def test_ads_campaign_only_is_allowed_only_outside_sku_context_and_not_high_confidence():
    campaign_report = build_ads_performance_stub(group_by="campaign")
    assert campaign_report.rows[0].attributionLevel == "campaign_only"
    assert campaign_report.rows[0].confidence == "blocked"

    sku_report = build_ads_performance_stub(group_by="sku")
    assert sku_report.rows[0].attributionLevel != "campaign_only"

    payload = dump(sku_report)
    payload["rows"][0]["attributionLevel"] = "campaign_only"

    with pytest.raises(ValidationError):
        AdsPerformanceResponse.model_validate(payload)


def test_ads_blocked_or_unknown_requires_wb02():
    report = build_ads_performance_stub()
    payload = dump(report)
    payload["blockerIds"] = ["WB-23"]

    with pytest.raises(ValidationError):
        AdsPerformanceResponse.model_validate(payload)


def test_rnp_missing_drr_and_blocked_ads_require_wb11_and_wb02():
    report = build_rnp_report_stub()
    assert {"WB-02", "WB-11"} <= set(report.blockerIds)

    missing_drr_payload = dump(report)
    missing_drr_payload["blockerIds"] = ["WB-02", "WB-23"]
    with pytest.raises(ValidationError):
        RnpReportResponse.model_validate(missing_drr_payload)

    blocked_ads_payload = dump(report)
    blocked_ads_payload["blockerIds"] = ["WB-11", "WB-23"]
    with pytest.raises(ValidationError):
        RnpReportResponse.model_validate(blocked_ads_payload)


def test_rnp_rows_expose_total_ads_and_estimated_organic_funnel():
    report = build_rnp_report_stub()
    row = report.rows[0].model_dump()

    assert row["nmId"] == 684820752
    assert row["sku"] == "FBBT_42"
    assert row["openCount"] == 1200
    assert row["cartCount"] == 180
    assert row["orderCount"] == 48
    assert row["orderSumKopecks"] == 6720000
    assert row["adImpressions"] == 420
    assert row["adClicks"] == 51
    assert row["adCartAdds"] == 17
    assert row["adOrders"] == 8
    assert row["adSalesKopecks"] == 1120000
    assert row["organicOpenCountEstimated"] == 1149
    assert row["organicOrderCountEstimated"] == 40
    assert row["organicSalesKopecksEstimated"] == 5600000
    assert row["organicEstimate"] is True
    assert row["acooPct"] == 12.5
    assert row["tacooPct"] == 2.08
    assert row["reasons"] == ["estimated_organic", "ads_source_blocked"]
    assert row["comments"] == []
    assert row["auditEvents"] == []


def test_abc_filtered_summary_changes_with_filter_context():
    all_rows = build_abc_report_stub(group_by="sku", filter_query="")
    locomotive_rows = build_abc_report_stub(group_by="sku", filter_query="status=locomotive")
    manager_rows = build_abc_report_stub(group_by="manager", filter_query="status=locomotive")

    assert all_rows.filteredSummary.filterHash != locomotive_rows.filteredSummary.filterHash
    assert locomotive_rows.filteredSummary.filterHash != manager_rows.filteredSummary.filterHash
    assert all_rows.filteredSummary.skuCount != locomotive_rows.filteredSummary.skuCount


def test_price_guard_default_blocks_apply_until_spp_sources_close():
    guard = build_price_guard_stub("FBBT_42")

    assert guard.canApply is False
    assert guard.freezeState == "frozen"
    assert guard.blockerIds == []

    payload = dump(guard)
    payload["canApply"] = True

    with pytest.raises(ValidationError):
        PriceGuardResponse.model_validate(payload)


def test_price_guard_rejects_apply_with_blocker_trigger_or_blocked_spp_snapshot():
    guard = build_price_guard_stub("FBBT_42")
    payload = dump(guard)
    payload["canApply"] = True
    payload["blockedReason"] = None
    payload["freezeState"] = "none"
    payload["blockerIds"] = []

    with pytest.raises(ValidationError):
        PriceGuardResponse.model_validate(payload)

    payload["guardTriggers"] = []
    with pytest.raises(ValidationError):
        PriceGuardResponse.model_validate(payload)


def test_low_rating_review_requires_approval_before_external_send():
    review = build_ai_review_approval_stub("wb-review-006", rating=2)
    assert review.approvalState == "required"
    assert review.externalSendAllowed is False

    payload = dump(review)
    payload["externalSendAllowed"] = True
    payload["sendState"] = "ready_to_send"

    with pytest.raises(ValidationError):
        AiReviewApproval.model_validate(payload)


def test_safe_rating_review_can_be_ready_without_approval():
    review = build_ai_review_approval_stub("wb-review-001", rating=5)

    assert review.approvalState == "not_required"
    assert review.externalSendAllowed is True
    assert review.sendState == "ready_to_send"
