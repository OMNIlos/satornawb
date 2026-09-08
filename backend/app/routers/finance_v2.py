from __future__ import annotations

from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.control_plane.auth import ActorContext
from app.infra.db import get_db_session
from app.platform.clock import utc_now
from app.platform.finance.access import (
    get_finance_actor,
    require_finance_read,
    require_wb_account_scope,
)
from app.platform.finance.schemas import (
    FinanceMetaView,
    FinancePageView,
    FinancePeriodView,
    FinanceSkuView,
    FinanceSnapshotView,
    FinanceSummaryView,
)
from app.platform.finance.service import (
    FinanceAccountNotFound,
    FinancePage,
    FinanceService,
)
from app.platform.period import Period, PeriodValidationError

router = APIRouter(tags=["finance-v2"])

def _view(
    page: FinancePage, marketplace_account_id: int, resolved_now: datetime
) -> FinancePageView:
    period = page.period
    snapshot = page.snapshot
    return FinancePageView(
        items=[
            FinanceSkuView(
                nmId=row.nm_id,
                sellerArticle=row.seller_article,
                operationCount=row.operation_count,
                revenueKopecks=row.revenue_kopecks,
                mainRevenueKopecks=row.main_revenue_kopecks,
                redemptionsRevenueKopecks=row.redemptions_revenue_kopecks,
                lateCorrectionRevenueKopecks=row.late_correction_revenue_kopecks,
                unknownRevenueKopecks=row.unknown_revenue_kopecks,
                salesUnits=row.sales_units,
                returnsUnits=row.returns_units,
                netUnits=row.net_units,
            )
            for row in page.items
        ],
        total=page.total,
        limit=page.limit,
        offset=page.offset,
        summary=FinanceSummaryView(
            operationCount=page.summary.operation_count,
            skuCount=page.summary.sku_count,
            totalRevenueKopecks=page.summary.total_revenue_kopecks,
            mainRevenueKopecks=page.summary.main_revenue_kopecks,
            redemptionsRevenueKopecks=page.summary.redemptions_revenue_kopecks,
            lateCorrectionRevenueKopecks=page.summary.late_correction_revenue_kopecks,
            unknownRevenueKopecks=page.summary.unknown_revenue_kopecks,
            salesUnits=page.summary.sales_units,
            returnsUnits=page.summary.returns_units,
            netUnits=page.summary.net_units,
        ),
        meta=FinanceMetaView(
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
        ),
        timestamp=resolved_now,
    )


@router.get("/api/v2/wb/finance", response_model=FinancePageView)
def get_wb_finance(
    actor: ActorContext = Depends(get_finance_actor),
    session: Session = Depends(get_db_session),
    marketplaceAccountId: int = Query(gt=0),
    periodDays: int = Query(default=7, ge=1, le=90),
    dateFrom: date | None = Query(default=None),
    dateTo: date | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> FinancePageView:
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
        page = FinanceService(
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
