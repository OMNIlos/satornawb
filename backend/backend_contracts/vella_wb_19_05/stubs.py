from __future__ import annotations

from datetime import date, datetime, timezone
from hashlib import sha1

from .models import (
    AbcFilteredSummary,
    AbcReportResponse,
    AdsAttributionPolicy,
    AdsPerformanceResponse,
    AdsPerformanceRow,
    AdsTotals,
    AiReviewApproval,
    AiReviewCacheMetrics,
    DatePeriod,
    DayAllocationSummary,
    ManualCost,
    PnlFieldMapping,
    PnlReportResponse,
    PnlRow,
    PnlTotals,
    PriceGuardResponse,
    PriceGuardTrigger,
    ReportGroupBy,
    RnpReportResponse,
    RnpRow,
    SourceEvidence,
    SppSnapshot,
    utc_now,
)


DEFAULT_FROM = date(2026, 5, 1)
DEFAULT_TO = date(2026, 5, 19)


def _period(date_from: date = DEFAULT_FROM, date_to: date = DEFAULT_TO) -> DatePeriod:
    return DatePeriod(dateFrom=date_from, dateTo=date_to)


def _mock_evidence(source_id: str, source_name: str, fields: list[str]) -> list[SourceEvidence]:
    return [
        SourceEvidence(
            sourceId=source_id,
            sourceType="mock",
            sourceName=source_name,
            lastSyncedAt=None,
            freshnessTtlMinutes=None,
            fieldsUsed=fields,
        )
    ]


def build_pnl_report_stub(
    date_from: date = DEFAULT_FROM,
    date_to: date = DEFAULT_TO,
    group_by: ReportGroupBy = "sku",
) -> PnlReportResponse:
    return PnlReportResponse(
        sourceStatus="blocked",
        confidence="blocked",
        blockerIds=["WB-12", "WB-13"],
        sourceEvidence=_mock_evidence("sprint-a-pnl-stub", "Sprint A P&L blocked stub", ["fieldMapping", "manualCosts", "dayAllocation"]),
        calculatedAt=utc_now(),
        period=_period(date_from, date_to),
        reportState="blocked",
        groupBy=group_by,
        totals=PnlTotals(
            revenueKopecks=4_280_000,
            netProfitKopecks=None,
            marginPct=None,
            sourceStatus="blocked",
            confidence="blocked",
        ),
        rows=[
            PnlRow(
                rowId="sku-FBBT_42",
                label="FBBT_42",
                brandId="brand-satorna",
                managerId="maria",
                skuId="FBBT_42",
                revenueKopecks=428_000,
                cogsKopecks=171_000,
                commissionKopecks=62_000,
                logisticsKopecks=31_000,
                storageKopecks=None,
                adSpendKopecks=None,
                taxKopecks=None,
                overheadKopecks=None,
                netProfitKopecks=None,
                marginPct=None,
                sourceStatus="blocked",
                confidence="blocked",
            )
        ],
        fieldMapping=[
            PnlFieldMapping(
                metricId="storage",
                metricLabel="Хранение",
                sourceId="manual-financial-rules",
                sourceField=None,
                formula="manual allocation required",
                fallback="block final P&L until WB-12 is closed",
                blockerIds=["WB-12"],
            ),
            PnlFieldMapping(
                metricId="tax",
                metricLabel="Налоги",
                sourceId="manual-financial-rules",
                sourceField=None,
                formula="tax/VAT rule required",
                fallback="block final P&L until WB-13 is closed",
                blockerIds=["WB-13"],
            ),
        ],
        manualCosts=[
            ManualCost(
                costId="storage-overhead",
                label="Хранение и overhead",
                amountKopecks=None,
                allocationBase="unknown",
                sourceStatus="blocked",
                blockerIds=["WB-12"],
            ),
            ManualCost(
                costId="tax",
                label="Налоги",
                amountKopecks=None,
                allocationBase="unknown",
                sourceStatus="blocked",
                blockerIds=["WB-13"],
            ),
        ],
        dayAllocation=DayAllocationSummary(
            allocationDateField=None,
            expenseDateField=None,
            rule="blocked until financial allocation calendar is confirmed",
            sourceStatus="blocked",
            blockerIds=["WB-12"],
        ),
    )


def build_ads_performance_stub(
    date_from: date = DEFAULT_FROM,
    date_to: date = DEFAULT_TO,
    group_by: ReportGroupBy = "campaign",
) -> AdsPerformanceResponse:
    attribution_level = "campaign_sku" if group_by == "sku" else "campaign_only"
    return AdsPerformanceResponse(
        sourceStatus="blocked",
        confidence="blocked",
        blockerIds=["WB-02"],
        sourceEvidence=_mock_evidence("sprint-a-ads-stub", "Sprint A Ads blocked stub", ["attributionPolicy", "rows"]),
        calculatedAt=utc_now(),
        period=_period(date_from, date_to),
        groupBy=group_by,
        totals=AdsTotals(
            adSpendKopecks=None,
            impressions=None,
            clicks=None,
            cartAdds=None,
            ordersCount=None,
            ordersKopecks=None,
            drrPct=None,
            romiPct=None,
            roiPct=None,
        ),
        rows=[
            AdsPerformanceRow(
                rowId=f"{group_by}-ads-source-blocked",
                campaignId="campaign-unconfirmed" if group_by != "sku" else None,
                skuId="FBBT_42" if group_by == "sku" else None,
                brandId="brand-satorna",
                managerId="maria",
                adSpendKopecks=None,
                impressions=None,
                clicks=None,
                cartAdds=None,
                ordersCount=None,
                ordersKopecks=None,
                drrPct=None,
                romiPct=None,
                roiPct=None,
                attributionLevel=attribution_level,
                confidence="blocked",
            )
        ],
        attributionPolicy=AdsAttributionPolicy(
            allowedSkuLevels=["exact_sku", "campaign_sku"],
            campaignOnlyCanAllocateToSkuPnl=False,
            notes=["campaign_only spend stays campaign-level and is not SKU P&L truth"],
        ),
    )


def build_rnp_report_stub(
    date_from: date = DEFAULT_FROM,
    date_to: date = DEFAULT_TO,
    group_by: ReportGroupBy = "sku",
) -> RnpReportResponse:
    return RnpReportResponse(
        sourceStatus="blocked",
        confidence="blocked",
        blockerIds=["WB-02", "WB-11"],
        sourceEvidence=_mock_evidence("sprint-a-rnp-stub", "Sprint A RNP blocked stub", ["drrPct", "adsSourceStatus"]),
        calculatedAt=utc_now(),
        period=_period(date_from, date_to),
        groupBy=group_by,
        rows=[
            RnpRow(
                rowId="sku-FBBT_42",
                label="FBBT_42",
                sku="FBBT_42",
                nmId=684820752,
                productName="FBBT_42",
                brandName="Satorna",
                categoryName="Футболки",
                skuId="FBBT_42",
                brandId="brand-satorna",
                managerId="maria",
                activeRule="manual_review",
                openCount=1200,
                openCountDeltaPct=4.2,
                cartCount=180,
                cartCountDeltaPct=-2.1,
                orderCount=48,
                orderCountDeltaPct=1.4,
                orderSumKopecks=6720000,
                orderSumDeltaPct=3.3,
                buyoutCount=31,
                buyoutSumKopecks=4340000,
                buyoutPct=64.6,
                ctrPct=4.25,
                atcrPct=15.0,
                cartToOrderPct=26.67,
                adImpressions=420,
                adClicks=51,
                adCtrPct=12.14,
                adCartAdds=17,
                adAtcrPct=33.33,
                adOrders=8,
                adSalesKopecks=1120000,
                adSpendKopecks=140000,
                adSpendDeltaPct=9.5,
                drrPct=2.08,
                roiPct=700.0,
                acooPct=12.5,
                tacooPct=2.08,
                marginPct=None,
                avgPosition=None,
                organicOpenCountEstimated=1149,
                organicCartCountEstimated=163,
                organicOrderCountEstimated=40,
                organicSalesKopecksEstimated=5600000,
                organicEstimate=True,
                reasons=["estimated_organic", "ads_source_blocked"],
                comments=[],
                auditEvents=[],
                sourceStatus="blocked",
                confidence="blocked",
            )
        ],
        adSpendKopecks=None,
        drrPct=None,
        formulaNotes=["DRR/ROI formulas and ads source are blocked until WB-02/WB-11 close"],
        adsSourceStatus="blocked",
    )


def build_abc_report_stub(
    date_from: date = DEFAULT_FROM,
    date_to: date = DEFAULT_TO,
    group_by: ReportGroupBy = "sku",
    filter_query: str = "",
) -> AbcReportResponse:
    filter_hash = sha1(f"{date_from}:{date_to}:{group_by}:{filter_query}".encode("utf-8")).hexdigest()[:12]
    sku_count = 10 if filter_query else 30
    locomotive_count = 4 if filter_query else 10
    return AbcReportResponse(
        sourceStatus="partial",
        confidence="low",
        blockerIds=["WB-02", "WB-19A"],
        sourceEvidence=_mock_evidence("sprint-a-abc-stub", "Sprint A ABC partial stub", ["filteredSummary", "filterHash"]),
        calculatedAt=utc_now(),
        period=_period(date_from, date_to),
        filteredSummary=AbcFilteredSummary(
            filterHash=filter_hash,
            skuCount=sku_count,
            locomotiveCount=locomotive_count,
            ordersCount=240 if not filter_query else 88,
            ordersKopecks=2_960_000 if not filter_query else 1_040_000,
            profitKopecks=710_000 if not filter_query else 264_000,
            marginPct=24.0 if not filter_query else 25.4,
            adSpendKopecks=None,
            sourceStatus="partial",
            confidence="low",
        ),
        rows=[],
    )


def build_price_guard_stub(article_id: str) -> PriceGuardResponse:
    return PriceGuardResponse(
        articleId=article_id,
        currentPriceKopecks=None,
        buyerPriceKopecks=None,
        sppSnapshot=SppSnapshot(
            sourceStatus="partial",
            sppPct=5,
            buyerPriceKopecks=117_427,
            capturedAt=None,
            blockerIds=[],
        ),
        recommendedSellerPriceKopecks=None,
        lastKnownGoodPriceKopecks=None,
        canApply=False,
        blockedReason="Real price apply is disabled by feature flag",
        freezeState="frozen",
        guardTriggers=[
            PriceGuardTrigger(
                type="source_stale",
                severity="blocker",
                observedValue="feature_flag_off",
                previousValue=None,
                threshold="VELLA_REAL_PRICE_APPLY_ENABLED=true",
                message="SPP/apply sources are mapped; enabling real mutation still requires explicit feature flag",
            )
        ],
        sourceEvidence=_mock_evidence("sprint-a-price-guard-stub", "Sprint A SPP guard blocked stub", ["sppSnapshot", "freezeState", "guardTriggers"]),
        blockerIds=[],
    )


def build_ai_review_approval_stub(review_id: str, rating: int) -> AiReviewApproval:
    low_rating = rating < 4
    return AiReviewApproval(
        reviewId=review_id,
        rating=rating,
        draftId=f"draft-{review_id}",
        approvalState="required" if low_rating else "not_required",
        approvalActorId=None,
        approvedAt=None,
        externalSendAllowed=not low_rating,
        sendState="draft_only" if low_rating else "ready_to_send",
        brandVoiceId="brand-satorna",
        promptTraceId=None,
        cacheMetrics=AiReviewCacheMetrics(cachedTokens=0, hitRatePct=0),
        auditEvidence=_mock_evidence("sprint-a-review-approval-stub", "Sprint A review approval stub", ["approvalState", "externalSendAllowed"]),
    )


def build_approved_review_stub(review_id: str, rating: int, actor_id: str) -> AiReviewApproval:
    return AiReviewApproval(
        reviewId=review_id,
        rating=rating,
        draftId=f"draft-{review_id}",
        approvalState="approved",
        approvalActorId=actor_id,
        approvedAt=datetime.now(timezone.utc),
        externalSendAllowed=True,
        sendState="ready_to_send",
        brandVoiceId="brand-satorna",
        promptTraceId=None,
        cacheMetrics=AiReviewCacheMetrics(cachedTokens=0, hitRatePct=0),
        auditEvidence=_mock_evidence("sprint-a-review-approval-stub", "Sprint A review approval stub", ["approvalState", "externalSendAllowed"]),
    )
