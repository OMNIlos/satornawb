from __future__ import annotations

from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.control_plane.auth import ActorContext
from app.infra.db import get_db_session
from app.modules.wb_reports.abc_pnl import AbcPnlPage, WbAbcPnlService
from app.modules.wb_reports.schemas import (
    AbcPnlMetaView,
    AbcPnlPageView,
    AbcPnlRowView,
    AbcPnlSummaryView,
)
from app.platform.clock import utc_now
from app.platform.finance.access import (
    get_finance_actor,
    require_finance_read,
    require_wb_account_scope,
)
from app.platform.finance.schemas import FinancePeriodView, FinanceSnapshotView
from app.platform.finance.service import FinanceAccountNotFound
from app.platform.period import Period, PeriodValidationError

router = APIRouter(tags=["wb-reports-v2"])


def _view(
    page: AbcPnlPage,
    marketplace_account_id: int,
    resolved_now: datetime,
) -> AbcPnlPageView:
    period = page.period
    snapshot = page.snapshot
    return AbcPnlPageView(
        items=[
            AbcPnlRowView(
                nmId=row.nm_id,
                sellerArticle=row.seller_article,
                catalogSkuId=row.catalog_sku_id,
                operationCount=row.operation_count,
                revenueKopecks=row.revenue_kopecks,
                salesRevenueKopecks=row.sales_revenue_kopecks,
                returnsRevenueKopecks=row.returns_revenue_kopecks,
                mainRevenueKopecks=row.main_revenue_kopecks,
                redemptionsRevenueKopecks=row.redemptions_revenue_kopecks,
                lateCorrectionRevenueKopecks=row.late_correction_revenue_kopecks,
                unknownRevenueKopecks=row.unknown_revenue_kopecks,
                salesUnits=row.sales_units,
                returnsUnits=row.returns_units,
                netUnits=row.net_units,
                commissionKopecks=row.commission_kopecks,
                logisticsKopecks=row.logistics_kopecks,
                storageKopecks=row.storage_kopecks,
                acceptanceKopecks=row.acceptance_kopecks,
                penaltyKopecks=row.penalty_kopecks,
                deductionKopecks=row.deduction_kopecks,
                additionalPaymentKopecks=row.additional_payment_kopecks,
                financeOtherExpensesKopecks=row.finance_other_expenses_kopecks,
                compensationKopecks=row.compensation_kopecks,
                acquiringKopecks=row.acquiring_kopecks,
                financeExpensesKopecks=row.finance_expenses_kopecks,
                costValueState=row.cost_value_state,
                costEvidenceStatus=row.cost_evidence_status,
                cogsKopecks=row.cogs_kopecks,
                settlementProfitKopecks=row.settlement_profit_kopecks,
                economicsValueState=row.economics_value_state,
                economicsEvidenceStatus=row.economics_evidence_status,
                taxKopecks=row.tax_kopecks,
                otherExpensesKopecks=row.other_expenses_kopecks,
                profitBeforeAdsAndLoyaltyKopecks=(
                    row.profit_before_ads_and_loyalty_kopecks
                ),
                advertisingSpendKopecks=row.advertising_spend_kopecks,
                profitBeforeLoyaltyKopecks=row.profit_before_loyalty_kopecks,
                cashbackAmountKopecks=row.cashback_amount_kopecks,
                cashbackDiscountKopecks=row.cashback_discount_kopecks,
                cashbackCommissionChangeKopecks=(
                    row.cashback_commission_change_kopecks
                ),
                loyaltyNetCostKopecks=row.loyalty_net_cost_kopecks,
                profitAfterLoyaltyKopecks=row.profit_after_loyalty_kopecks,
                salesClass=row.sales_class,
                profitClass=row.profit_class,
                abcCode=row.abc_code,
                netProfitKopecks=row.net_profit_kopecks,
                blockerIds=list(row.blocker_ids),
            )
            for row in page.items
        ],
        total=page.total,
        limit=page.limit,
        offset=page.offset,
        summary=AbcPnlSummaryView(
            operationCount=page.summary.operation_count,
            skuCount=page.summary.sku_count,
            revenueKopecks=page.summary.revenue_kopecks,
            salesRevenueKopecks=page.summary.sales_revenue_kopecks,
            returnsRevenueKopecks=page.summary.returns_revenue_kopecks,
            salesUnits=page.summary.sales_units,
            returnsUnits=page.summary.returns_units,
            netUnits=page.summary.net_units,
            commissionKopecks=page.summary.commission_kopecks,
            logisticsKopecks=page.summary.logistics_kopecks,
            storageKopecks=page.summary.storage_kopecks,
            acceptanceKopecks=page.summary.acceptance_kopecks,
            penaltyKopecks=page.summary.penalty_kopecks,
            deductionKopecks=page.summary.deduction_kopecks,
            financeOtherExpensesKopecks=page.summary.finance_other_expenses_kopecks,
            compensationKopecks=page.summary.compensation_kopecks,
            acquiringKopecks=page.summary.acquiring_kopecks,
            financeExpensesKopecks=page.summary.finance_expenses_kopecks,
            cogsKopecks=page.summary.cogs_kopecks,
            settlementProfitKopecks=page.summary.settlement_profit_kopecks,
            taxKopecks=page.summary.tax_kopecks,
            otherExpensesKopecks=page.summary.other_expenses_kopecks,
            profitBeforeAdsAndLoyaltyKopecks=(
                page.summary.profit_before_ads_and_loyalty_kopecks
            ),
            advertisingSpendKopecks=page.summary.advertising_spend_kopecks,
            unattributedAdvertisingSpendKopecks=(
                page.summary.unattributed_advertising_spend_kopecks
            ),
            profitBeforeLoyaltyKopecks=(page.summary.profit_before_loyalty_kopecks),
            cashbackAmountKopecks=page.summary.cashback_amount_kopecks,
            cashbackDiscountKopecks=page.summary.cashback_discount_kopecks,
            cashbackCommissionChangeKopecks=(
                page.summary.cashback_commission_change_kopecks
            ),
            loyaltyNetCostKopecks=page.summary.loyalty_net_cost_kopecks,
            profitAfterLoyaltyKopecks=page.summary.profit_after_loyalty_kopecks,
            netProfitKopecks=page.summary.net_profit_kopecks,
        ),
        meta=AbcPnlMetaView(
            state=page.state,
            marketplaceAccountId=marketplace_account_id,
            period=FinancePeriodView(
                dateFrom=period.date_from,
                dateTo=period.date_to,
                startAt=period.start_at,
                endExclusiveAt=period.end_exclusive_at,
                days=period.days,
                temporalState=period.temporal_state(resolved_now),
            ),
            snapshot=(
                FinanceSnapshotView(
                    syncRunId=snapshot.sync_run_id,
                    snapshotChecksum=snapshot.snapshot_checksum,
                    formulaVersion=snapshot.formula_version,
                    operationCount=snapshot.operation_count,
                    capturedAt=snapshot.captured_at,
                    lastObservedAt=snapshot.last_observed_at,
                )
                if snapshot
                else None
            ),
            formulaVersion=page.formula_version,
            costLedgerRevision=page.cost_ledger_revision,
            economicsRevision=page.economics_revision,
            advertisingSource=(
                page.advertising_snapshot.source_kind
                if page.advertising_snapshot
                else None
            ),
            advertisingSnapshotChecksum=(
                page.advertising_snapshot.snapshot_checksum
                if page.advertising_snapshot
                else None
            ),
            advertisingEvidenceStatus=(
                page.advertising_snapshot.evidence_status
                if page.advertising_snapshot
                else None
            ),
            blockerIds=list(page.blocker_ids),
        ),
        timestamp=resolved_now,
    )


@router.get("/api/v2/wb/reports/abc-pnl", response_model=AbcPnlPageView)
def get_wb_abc_pnl(
    actor: ActorContext = Depends(get_finance_actor),
    session: Session = Depends(get_db_session),
    marketplaceAccountId: int = Query(gt=0),
    periodDays: int = Query(default=7, ge=1, le=90),
    dateFrom: date | None = Query(default=None),
    dateTo: date | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> AbcPnlPageView:
    require_finance_read(actor)
    require_wb_account_scope(session, actor, marketplaceAccountId)
    resolved_now = utc_now()
    try:
        period = Period.resolve(
            period_days=periodDays,
            date_from=dateFrom,
            date_to=dateTo,
            now=resolved_now,
        )
    except PeriodValidationError as exc:
        raise HTTPException(
            status_code=422,
            detail={"code": "INVALID_PERIOD", "message": str(exc)},
        ) from exc
    try:
        page = WbAbcPnlService(
            session,
            actor.organization_id,
            now=lambda: resolved_now,
        ).get_page(
            marketplaceAccountId,
            period,
            limit=limit,
            offset=offset,
        )
    except FinanceAccountNotFound as exc:
        raise HTTPException(
            status_code=404,
            detail={"code": "WB_ACCOUNT_NOT_FOUND", "message": str(exc)},
        ) from exc
    return _view(page, marketplaceAccountId, resolved_now)
