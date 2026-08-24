from __future__ import annotations

import re
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from typing import Any, Literal

from fastapi import APIRouter, Body, HTTPException, Query, Request

from app.cabinet.store import get_user_wb_token_secret
from app.cabinet.store import list_team_users
from app.config import get_settings
from app.control_plane.auth import actor_from_request, has_permission
from app.control_plane.store import assert_permission_or_audit, record_audit_event
from app.routers.one_c_cash_flow import get_cash_flow_for_period
from app.reports_exports import ReportExportId, get_report_export_or_none, materialize_report_export, request_report_export
from app.reports_history import ensure_daily_stock_history
from app.report_rules.presets import PRESET_CONFIGS
from app.report_rules.schemas import RulesDraftRequest, RulesSaveRequest
from app.report_rules.service import (
    PreviewTokenError,
    ReportRulesValidationError,
    create_preview,
    evaluate_metrics,
    issue_preview_token,
    normalize_config,
    verify_preview_token,
)
from app.report_rules.store import ProfileVersionConflict, activate_profile, list_profile_history, load_active_profile
from app.repricer_cache.store import get_covering_source_cache, get_source_cache, list_cached_goods, list_source_cache_by_prefix, list_source_cache_ranges_by_prefix, save_source_cache
from app.repricer_bff import _extract_wb_media_url
from app.wb_ads_cache.store import get_ads_report_cache, save_ads_history_snapshots, save_ads_report_cache
from app.wb_api.ads_runtime import AdsAttributionRow, AdsAttributionSnapshot
from app.wb_api.client import (
    RateLimitedWbApiClient,
    WbApiRequest,
    build_wb_analytics_client,
    build_wb_common_client,
    build_wb_marketplace_client,
    build_wb_supplies_client,
)
from app.wb_api.reports_sources_runtime import (
    WbFinanceReconciliation,
    WbReportsSourcesSnapshot,
    WbStockRow,
)
from app.wb_reports_sprint_d import (
    DEFAULT_FROM,
    DEFAULT_TO,
    _cache_aggregates,
    _period_cache,
    build_abc_report,
    build_pnl_report,
    build_plan_fact_report,
    build_rnp_report,
)


router = APIRouter(tags=["wb-reports-bff"])

DIGEST_REPORT_PAYLOAD_VERSION = "v11"

ReportId = Literal["digest", "abc", "rnp", "pnl", "expenses", "ads", "stock", "week-over-week"]
ReportGroupBy = Literal["sku", "manager", "brand", "category", "status", "warehouse", "campaign"]


def _actor_wb_token(actor: Any) -> str | None:
    token = get_user_wb_token_secret(actor.user_id)
    return token.strip() if token and token.strip() else None


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _report_rules_preview_rows(organization_id: int) -> tuple[list[dict[str, Any]], list[str]]:
    rows: list[dict[str, Any]] = []
    reports: set[str] = set()
    for cached in list_source_cache_by_prefix(organization_id, "reports_payload_", limit=50, slim=False):
        report = cached.get("report") if isinstance(cached.get("report"), dict) else {}
        report_rows = report.get("rows") if isinstance(report.get("rows"), list) else []
        report_id = str((report.get("meta") or {}).get("id") or cached.get("sourceKey") or "report")
        for raw in report_rows:
            if not isinstance(raw, dict):
                continue
            row = dict(raw)
            row["reportId"] = report_id
            if isinstance(row.get("marginPct"), dict):
                row["marginPct"] = row["marginPct"].get("percent")
            if isinstance(row.get("orders"), dict) and row.get("baskets"):
                baskets = row.get("baskets")
                baskets_value = baskets.get("units") if isinstance(baskets, dict) else baskets
                orders_value = row["orders"].get("units")
                if baskets_value and orders_value is not None:
                    row["cartToOrderPct"] = float(orders_value) / float(baskets_value) * 100
            rows.append(row)
            reports.add(report_id)
    return rows, sorted(reports)


def _rules_profile_payload(profile: Any) -> dict[str, Any]:
    return profile.model_dump(mode="json")


def _range_from_preset(preset: str, from_raw: str | None, to_raw: str | None) -> tuple[date, date, dict[str, str]]:
    today = date.today()
    if preset == "custom" and from_raw and to_raw:
        date_from = date.fromisoformat(from_raw)
        date_to = date.fromisoformat(to_raw)
    elif preset == "1d":
        date_from = today
        date_to = today
    elif preset == "14d":
        date_from = today - timedelta(days=13)
        date_to = today
    elif preset == "30d":
        date_from = today - timedelta(days=29)
        date_to = today
    else:
        preset = "7d"
        date_from = today - timedelta(days=6)
        date_to = today
    return date_from, date_to, {"preset": preset, "from": date_from.isoformat(), "to": date_to.isoformat()}


def _freshness_state(source_status: str) -> Literal["fresh", "partial", "pending_financial", "stale"]:
    if source_status == "fresh":
        return "fresh"
    if source_status in {"blocked", "unknown", "stale"}:
        return "stale"
    return "partial"


def _int_value(value: Any) -> int:
    if isinstance(value, bool) or value is None:
        return 0
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(round(value))
    if isinstance(value, str):
        try:
            return int(round(float(value.replace(",", ".").strip())))
        except ValueError:
            return 0
    return 0


def _parse_cache_date(value: Any) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def _rnp_daily_baskets_ready(
    organization_id: int,
    *,
    date_from: date,
    date_to: date,
) -> bool:
    return _report_daily_source_ready(organization_id, "baskets", date_from=date_from, date_to=date_to)


REPORT_DAILY_SOURCE_PREFIXES: dict[str, str] = {
    "period-stats": "period_stats_",
    "finance": "finance_",
    "ads": "ads_",
    "baskets": "baskets_",
}


REPORT_DAILY_SOURCES_BY_ID: dict[str, tuple[str, ...]] = {
    "digest": ("period-stats", "finance", "ads", "baskets"),
    "abc": ("period-stats", "finance", "ads", "baskets"),
    "rnp": ("baskets", "ads"),
    "ads": ("ads",),
    "stock": ("period-stats", "finance"),
    "pnl": ("finance", "ads"),
}


def _report_daily_source_ready(
    organization_id: int,
    source: str,
    *,
    date_from: date,
    date_to: date,
) -> bool:
    prefix = REPORT_DAILY_SOURCE_PREFIXES.get(source)
    if not prefix:
        return False
    required_days = (date_to - date_from).days + 1
    for cache in list_source_cache_ranges_by_prefix(organization_id, prefix, limit=100):
        if not isinstance(cache, dict):
            continue
        cache_from = _parse_cache_date(cache.get("dateFrom"))
        cache_to = _parse_cache_date(cache.get("dateTo"))
        if not cache_from or not cache_to or cache_from > date_from or cache_to < date_to:
            continue
        if _int_value(cache.get("dailyAggregatesDays")) >= required_days:
            return True
    return False


def _report_daily_sources_ready(
    organization_id: int,
    sources: tuple[str, ...],
    *,
    date_from: date,
    date_to: date,
) -> tuple[bool, list[str]]:
    missing = [
        source
        for source in sources
        if not _report_daily_source_ready(organization_id, source, date_from=date_from, date_to=date_to)
    ]
    return not missing, missing


def _report_waiting_daily_detail_job(
    report_id: str,
    date_from: date,
    date_to: date,
    group_by: str,
    missing_sources: list[str],
    existing: dict[str, Any] | None = None,
) -> dict[str, Any]:
    label = "Ждем дневную детализацию WB"
    if missing_sources:
        label = f"{label}: {', '.join(missing_sources)}"
    return {
        **(existing or {}),
        "state": "waiting_daily_detail",
        "reportId": report_id,
        "dateFrom": date_from.isoformat(),
        "dateTo": date_to.isoformat(),
        "groupBy": group_by,
        "stage": "waiting_daily_detail",
        "label": label,
        "missingSources": missing_sources,
        "percent": 20,
        "updatedAt": _utc_now_iso(),
    }


def _rnp_waiting_baskets_detail_job(
    report_id: str,
    date_from: date,
    date_to: date,
    group_by: str,
    existing: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        **(existing or {}),
        "state": "waiting_baskets_detail",
        "reportId": report_id,
        "dateFrom": date_from.isoformat(),
        "dateTo": date_to.isoformat(),
        "groupBy": group_by,
        "stage": "waiting_baskets_detail",
        "label": "Ждем дневную детализацию корзин WB для RNP",
        "percent": 20,
        "updatedAt": _utc_now_iso(),
    }


def _float_value(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.replace(",", ".").strip())
        except ValueError:
            return None
    return None


def _meta(report_id: ReportId, title: str, description: str, source_type: Literal["operational", "financial"] = "operational", source_status: str = "partial") -> dict[str, Any]:
    freshness = _freshness_state(source_status)
    if report_id in {"pnl", "expenses"} and source_type == "financial" and freshness != "fresh":
        freshness = "pending_financial"
    return {
        "id": report_id,
        "title": title,
        "description": description,
        "sourceType": source_type,
        "freshnessState": freshness,
        "lastUpdatedAt": _utc_now_iso(),
    }


def _kpi(id_: str, label: str, value: str, hint: str | None = None) -> dict[str, Any]:
    payload = {"id": id_, "label": label, "value": value}
    if hint is not None:
        payload["hint"] = hint
    return payload


def _cached_row_units(row: dict[str, Any], default: int = 1) -> int:
    return max(0, _int_value(row.get("_cachedUnits") or row.get("quantity") or default))


def _orders_sales_by_nm(snapshot: Any) -> dict[int, dict[str, int]]:
    result: dict[int, dict[str, int]] = defaultdict(lambda: {"orders_qty": 0, "orders_revenue": 0, "sales_qty": 0, "sales_revenue": 0, "seller_revenue": 0, "returns_qty": 0})
    for row in snapshot.orders:
        nm_id = int(row.get("nmId") or 0)
        if nm_id <= 0:
            continue
        units = _cached_row_units(row)
        result[nm_id]["orders_qty"] += units
        result[nm_id]["orders_revenue"] += int(round(float(row.get("finishedPrice") or 0) * 100)) * units
    for row in snapshot.sales:
        nm_id = int(row.get("nmId") or 0)
        if nm_id <= 0:
            continue
        units = _cached_row_units(row)
        is_return = bool(row.get("isReturn"))
        result[nm_id]["sales_qty"] += units
        result[nm_id]["sales_revenue"] += int(round(float(row.get("finishedPrice") or 0) * 100)) * units
        result[nm_id]["seller_revenue"] += int(round(float(row.get("forPay") or 0) * 100)) * units
        if is_return:
            result[nm_id]["returns_qty"] += units
    return result


def _average_rubles(total_kopecks: int, units: int) -> float:
    return round(total_kopecks / max(units, 1) / 100, 2)


def _int_map_from_aggregates(aggregates: dict[str, dict[str, Any]], *keys: str) -> dict[int, int]:
    result: dict[int, int] = {}
    for raw_nm_id, row in aggregates.items():
        if not isinstance(row, dict):
            continue
        nm_id = _int_value(row.get("nmId") or raw_nm_id)
        if nm_id <= 0:
            continue
        value = 0
        for key in keys:
            value = _int_value(row.get(key))
            if value:
                break
        if value:
            result[nm_id] = value
    return result


def _cached_stock_rows(stock_cache: dict[str, Any]) -> list[WbStockRow]:
    aggregates = _cache_aggregates(stock_cache)
    rows: list[WbStockRow] = []
    for raw_nm_id, aggregate in aggregates.items():
        if not isinstance(aggregate, dict):
            continue
        nm_id = _int_value(aggregate.get("nmId") or raw_nm_id)
        if nm_id <= 0:
            continue
        quantity = _int_value(aggregate.get("wbStockUnits") or aggregate.get("quantity") or aggregate.get("stockUnits"))
        in_way_to_client = _int_value(aggregate.get("inWayToClient") or aggregate.get("inWayToClientUnits"))
        in_way_from_client = _int_value(aggregate.get("inWayFromClient") or aggregate.get("inWayFromClientUnits"))
        available_units = _int_value(aggregate.get("availableUnits"))
        if available_units == 0 and "availableUnits" not in aggregate:
            available_units = quantity + in_way_from_client
        total_stock_units = _int_value(aggregate.get("stockCount") or aggregate.get("totalStockUnits"))

        rows.append(
            WbStockRow(
                nm_id=nm_id,
                chrt_id=_int_value(aggregate.get("chrtId")) or None,
                warehouse_id=_int_value(aggregate.get("warehouseId")) or None,
                warehouse_name=aggregate.get("warehouseName") or aggregate.get("warehouse") or "WB",
                region_name=aggregate.get("regionName") or aggregate.get("clusterName"),
                quantity=quantity,
                in_way_to_client=in_way_to_client,
                in_way_from_client=in_way_from_client,
                available_units=available_units,
                was_out_of_stock=available_units <= 0,
                stock_type="wb",
                total_stock_units=total_stock_units or None,
            )
        )
    return rows


def _cached_activity_rows(
    aggregates: dict[str, dict[str, Any]],
    *,
    date_to: date,
    units_key: str,
    kopecks_key: str,
    seller_payout_by_nm_kopecks: dict[int, int] | None = None,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for raw_nm_id, aggregate in aggregates.items():
        if not isinstance(aggregate, dict):
            continue
        nm_id = _int_value(aggregate.get("nmId") or raw_nm_id)
        units = _int_value(aggregate.get(units_key))
        if nm_id <= 0 or units <= 0:
            continue
        total_kopecks = _int_value(aggregate.get(kopecks_key))
        row = {
            "nmId": nm_id,
            "warehouseName": aggregate.get("warehouseName") or "WB",
            "regionName": aggregate.get("regionName"),
            "lastChangeDate": f"{date_to.isoformat()}T00:00:00",
            "finishedPrice": _average_rubles(total_kopecks, units),
            "_cachedUnits": units,
        }
        if seller_payout_by_nm_kopecks is not None:
            row["forPay"] = _average_rubles(seller_payout_by_nm_kopecks.get(nm_id, 0), units)
        rows.append(row)
    return rows


def build_cached_wb_reports_sources_snapshot(
    *,
    organization_id: int,
    date_from: date,
    date_to: date,
) -> WbReportsSourcesSnapshot:
    stock_cache = get_source_cache(organization_id, "stocks", slim=False) or {}
    period_stats = _cache_aggregates(_period_cache(organization_id, "period_stats", date_from, date_to))
    finance = _cache_aggregates(_period_cache(organization_id, "finance", date_from, date_to))

    seller_payout_by_nm_kopecks = _int_map_from_aggregates(finance, "sellerPayoutKopecks", "payableKopecks", "forPayKopecks")
    revenue_by_nm_kopecks = _int_map_from_aggregates(period_stats, "revenueKopecks", "salesKopecks", "ordersKopecks")
    if not revenue_by_nm_kopecks:
        revenue_by_nm_kopecks = _int_map_from_aggregates(finance, "sellerRevenueKopecks", "revenueGrossKopecks", "retailAmountKopecks")

    orders = _cached_activity_rows(period_stats, date_to=date_to, units_key="ordersUnits", kopecks_key="ordersKopecks")
    sales = _cached_activity_rows(
        period_stats,
        date_to=date_to,
        units_key="salesUnits",
        kopecks_key="revenueKopecks",
        seller_payout_by_nm_kopecks=seller_payout_by_nm_kopecks,
    )
    stocks = _cached_stock_rows(stock_cache)

    blockers: list[str] = []
    if not stocks:
        blockers.append("WB_CACHE_STOCKS_EMPTY")
    if not period_stats:
        blockers.append("WB_CACHE_PERIOD_STATS_EMPTY")
    if not finance:
        blockers.append("WB_CACHE_FINANCE_EMPTY")
    has_any_data = bool(stocks or period_stats or finance)

    return WbReportsSourcesSnapshot(
        source_status="cached" if has_any_data else "blocked",
        confidence="high" if has_any_data and not blockers else ("medium" if has_any_data else "blocked"),
        blocker_ids=blockers,
        source_evidence=[],
        orders=orders,
        sales=sales,
        stocks=stocks,
        financial_rows=[],
        finance_reconciliation=WbFinanceReconciliation(
            report_id=None,
            retail_amount_kopecks=sum(revenue_by_nm_kopecks.values()),
            for_pay_kopecks=sum(seller_payout_by_nm_kopecks.values()),
            delivery_service_kopecks=sum(_int_map_from_aggregates(finance, "logisticsKopecks").values()),
            paid_storage_kopecks=sum(_int_map_from_aggregates(finance, "storageKopecks").values()),
            paid_acceptance_kopecks=sum(_int_map_from_aggregates(finance, "acceptanceKopecks").values()),
            penalty_kopecks=sum(_int_map_from_aggregates(finance, "penaltyKopecks").values()),
        )
        if finance
        else None,
        revenue_by_nm_kopecks=revenue_by_nm_kopecks,
        seller_payout_by_nm_kopecks=seller_payout_by_nm_kopecks,
        commission_cost_by_nm_kopecks=_int_map_from_aggregates(finance, "commissionKopecks", "commissionFormulaKopecks"),
        logistics_cost_by_nm_kopecks=_int_map_from_aggregates(finance, "logisticsKopecks"),
        penalties_cost_by_nm_kopecks=_int_map_from_aggregates(finance, "penaltyKopecks"),
        acceptance_cost_by_nm_kopecks=_int_map_from_aggregates(finance, "acceptanceKopecks"),
        storage_cost_by_nm_kopecks=_int_map_from_aggregates(finance, "storageKopecks"),
    )


def build_cached_ads_attribution_snapshot(
    *,
    organization_id: int,
    date_from: date,
    date_to: date,
    group_by: str = "sku",
) -> AdsAttributionSnapshot:
    ads_cache = _period_cache(organization_id, "ads", date_from, date_to)
    aggregates = _cache_aggregates(ads_cache)
    daily_aggregates = ads_cache.get("dailyAggregates") if isinstance(ads_cache.get("dailyAggregates"), dict) else {}
    rows: list[AdsAttributionRow] = []
    daily_rows: list[dict[str, Any]] = []
    totals: dict[str, int] = {
        "ad_spend_kopecks": 0,
        "impressions": 0,
        "clicks": 0,
        "cart_adds": 0,
        "orders_count": 0,
        "orders_kopecks": 0,
    }

    for raw_key, aggregate in aggregates.items():
        if not isinstance(aggregate, dict):
            continue
        nm_id = _int_value(aggregate.get("nmId") or aggregate.get("nmID") or raw_key)
        campaign_id_raw = aggregate.get("campaignId") or aggregate.get("advertId") or aggregate.get("advert_id")
        campaign_id = str(campaign_id_raw) if campaign_id_raw not in (None, "") else None
        ad_spend = _int_value(aggregate.get("adSpendKopecks") or aggregate.get("spendKopecks") or aggregate.get("sumKopecks"))
        impressions = _int_value(aggregate.get("impressions") or aggregate.get("adImpressions") or aggregate.get("views"))
        clicks = _int_value(aggregate.get("clicks") or aggregate.get("adClicks"))
        cart_adds = _int_value(aggregate.get("cartAdds") or aggregate.get("adCartAdds") or aggregate.get("cartCount") or aggregate.get("baskets"))
        orders_count = _int_value(aggregate.get("ordersCount") or aggregate.get("adOrders") or aggregate.get("orderCount") or aggregate.get("orders"))
        orders_kopecks = _int_value(aggregate.get("ordersKopecks") or aggregate.get("adRevenueKopecks") or aggregate.get("orderSumKopecks") or aggregate.get("salesKopecks"))

        if not any((nm_id > 0, campaign_id, ad_spend, impressions, clicks, cart_adds, orders_count, orders_kopecks)):
            continue

        totals["ad_spend_kopecks"] += ad_spend
        totals["impressions"] += impressions
        totals["clicks"] += clicks
        totals["cart_adds"] += cart_adds
        totals["orders_count"] += orders_count
        totals["orders_kopecks"] += orders_kopecks

        sku_id = str(nm_id) if nm_id > 0 else None
        attribution_level = "campaign_sku" if sku_id and campaign_id else ("exact_sku" if sku_id else "campaign_only")
        rows.append(
            AdsAttributionRow(
                campaign_id=campaign_id,
                sku_id=sku_id,
                attribution_level=attribution_level,
                confidence="high" if ad_spend or orders_count else "medium",
                ad_spend_kopecks=ad_spend,
                impressions=impressions,
                clicks=clicks,
                cart_adds=cart_adds,
                orders_count=orders_count,
                orders_kopecks=orders_kopecks,
                campaign_name=str(aggregate.get("campaignName") or aggregate.get("advertName") or "") or (f"WB карточка {nm_id}" if nm_id > 0 and campaign_id is None else None),
                campaign_type=aggregate.get("campaignType") or aggregate.get("advertType"),
                campaign_status=aggregate.get("campaignStatus") or aggregate.get("status"),
                payment_type=aggregate.get("paymentType"),
            )
        )

    if isinstance(daily_aggregates, dict):
        for raw_day, raw_rows in sorted(daily_aggregates.items()):
            if not isinstance(raw_rows, dict):
                continue
            for raw_key, aggregate in raw_rows.items():
                if not isinstance(aggregate, dict):
                    continue
                nm_id = _int_value(aggregate.get("nmId") or aggregate.get("nmID") or raw_key)
                campaign_id_raw = aggregate.get("campaignId") or aggregate.get("advertId") or aggregate.get("advert_id")
                daily_rows.append(
                    {
                        "date": str(raw_day),
                        "campaignId": str(campaign_id_raw) if campaign_id_raw not in (None, "") else None,
                        "skuId": str(nm_id) if nm_id > 0 else None,
                        "attributionLevel": "campaign_sku" if campaign_id_raw and nm_id > 0 else "exact_sku" if nm_id > 0 else "campaign_only",
                        "adSpendKopecks": _int_value(aggregate.get("adSpendKopecks") or aggregate.get("spendKopecks") or aggregate.get("sumKopecks")),
                        "impressions": _int_value(aggregate.get("impressions") or aggregate.get("adImpressions") or aggregate.get("views")),
                        "clicks": _int_value(aggregate.get("clicks") or aggregate.get("adClicks")),
                        "cartAdds": _int_value(aggregate.get("cartAdds") or aggregate.get("adCartAdds") or aggregate.get("cartCount") or aggregate.get("baskets")),
                        "ordersCount": _int_value(aggregate.get("ordersCount") or aggregate.get("adOrders") or aggregate.get("orderCount") or aggregate.get("orders")),
                        "ordersKopecks": _int_value(aggregate.get("ordersKopecks") or aggregate.get("adRevenueKopecks") or aggregate.get("orderSumKopecks") or aggregate.get("salesKopecks")),
                    }
                )

    has_any_data = bool(rows or any(totals.values()))
    return AdsAttributionSnapshot(
        source_status="cached" if has_any_data else "blocked",
        confidence="high" if has_any_data else "blocked",
        blocker_ids=[] if has_any_data else ["WB_ADS_CACHE_EMPTY"],
        source_evidence=[],
        totals=totals,
        rows=rows,
        daily_rows=daily_rows,
        diagnostics={
            "summary": {
                "source": "repricer_ads_cache",
                "rows": len(rows),
                "blockedAt": None if has_any_data else "wb-ads-cache",
                "blockedSources": [] if has_any_data else ["wb-ads-cache"],
            }
        },
    )


def _previous_period(date_from: date, date_to: date) -> tuple[date, date]:
    period_days = (date_to - date_from).days + 1
    previous_to = date_from - timedelta(days=1)
    return previous_to - timedelta(days=period_days - 1), previous_to


def _delta_pct(current: int | float | None, previous: int | float | None) -> float | None:
    if current is None or previous in (None, 0):
        return None
    return round((current - previous) / abs(previous) * 100, 2)


def _ads_by_nm(ads_snapshot: Any | None) -> dict[int, dict[str, int]]:
    result: dict[int, dict[str, int]] = defaultdict(lambda: {"baskets": 0, "ad_spend": 0})
    for row in getattr(ads_snapshot, "rows", []) or []:
        raw_nm_id = getattr(row, "sku_id", None)
        try:
            nm_id = int(raw_nm_id)
        except (TypeError, ValueError):
            continue
        if nm_id <= 0:
            continue
        result[nm_id]["baskets"] += int(getattr(row, "cart_adds", 0) or 0)
        result[nm_id]["ad_spend"] += int(getattr(row, "ad_spend_kopecks", 0) or 0)
    return result


def _profit_by_nm(snapshot: Any, ads_by_nm: dict[int, dict[str, int]]) -> dict[int, dict[str, int | float | None]]:
    result: dict[int, dict[str, int | float | None]] = {}
    for nm_id, revenue in getattr(snapshot, "revenue_by_nm_kopecks", {}).items():
        seller_payout = int(getattr(snapshot, "seller_payout_by_nm_kopecks", {}).get(nm_id, 0) or 0)
        costs = sum(
            int(getattr(snapshot, field, {}).get(nm_id, 0) or 0)
            for field in (
                "commission_cost_by_nm_kopecks",
                "logistics_cost_by_nm_kopecks",
                "penalties_cost_by_nm_kopecks",
                "acceptance_cost_by_nm_kopecks",
                "storage_cost_by_nm_kopecks",
            )
        )
        ad_spend = int(ads_by_nm.get(nm_id, {}).get("ad_spend", 0) or 0)
        profit = seller_payout - costs - ad_spend
        result[nm_id] = {"profit": profit, "margin": round(profit / revenue * 100, 2) if revenue else None}
    return result


def _catalog_meta_by_nm(organization_id: int | None) -> dict[int, dict[str, Any]]:
    if organization_id is None:
        return {}
    result: dict[int, dict[str, Any]] = {}
    for good in list_cached_goods(organization_id):
        nm_id = _int_value(good.get("nmID") or good.get("nmId"))
        if nm_id <= 0:
            continue
        result[nm_id] = {
            "sku": str(good.get("vendorCode") or f"NM_{nm_id}").strip() or f"NM_{nm_id}",
            "productName": good.get("title") or good.get("name"),
            "brand": good.get("brand"),
            "category": good.get("subjectName") or good.get("subject"),
            "photoUrl": _extract_wb_media_url(good, nm_id),
        }
    content_cards = get_source_cache(organization_id, "content_cards", slim=True) or {}
    cards = content_cards.get("cards") if isinstance(content_cards.get("cards"), list) else []
    for card in cards:
        if not isinstance(card, dict):
            continue
        nm_id = _int_value(card.get("nmID") or card.get("nmId"))
        if nm_id <= 0:
            continue
        meta = result.setdefault(nm_id, {"sku": f"NM_{nm_id}", "productName": None, "brand": None, "category": None, "photoUrl": None})
        if card.get("vendorCode"):
            meta["sku"] = str(card.get("vendorCode"))
        if card.get("title"):
            meta["productName"] = card.get("title")
        if card.get("brand"):
            meta["brand"] = card.get("brand")
        if card.get("subjectName") or card.get("object"):
            meta["category"] = card.get("subjectName") or card.get("object")
        meta["photoUrl"] = _extract_wb_media_url(card, nm_id) or meta.get("photoUrl")
    return result


def _dict_or_attr(node: Any, key: str, default: Any = None) -> Any:
    if isinstance(node, dict):
        return node.get(key, default)
    return getattr(node, key, default)


def _date_from_source_row(row: dict[str, Any]) -> date | None:
    raw = row.get("lastChangeDate") or row.get("date") or row.get("saleDt") or row.get("orderDt")
    if not raw:
        return None
    try:
        return datetime.fromisoformat(str(raw).replace("Z", "+00:00")).date()
    except ValueError:
        try:
            return date.fromisoformat(str(raw)[:10])
        except ValueError:
            return None


def _digest_period_bounds(date_range: dict[str, str]) -> tuple[date, date]:
    return date.fromisoformat(date_range["from"]), date.fromisoformat(date_range["to"])


def _empty_daily_bucket(day: date) -> dict[str, Any]:
    return {
        "label": day.strftime("%d.%m"),
        "date": day.isoformat(),
        "ordersUnits": 0,
        "ordersKopecks": 0,
        "salesUnits": 0,
        "salesKopecks": 0,
        "returnsUnits": 0,
        "buyoutPct": None,
    }


def _funnel_rows_totals(rows: list[dict[str, Any]]) -> dict[str, int | float | None]:
    order_count = sum(_int_value(row.get("orderCount")) for row in rows)
    order_sum = sum(_int_value(row.get("orderSumKopecks")) for row in rows)
    buyout_count = sum(_int_value(row.get("buyoutCount")) for row in rows)
    buyout_sum = sum(_int_value(row.get("buyoutSumKopecks")) for row in rows)
    cancel_count = sum(_int_value(row.get("cancelCount")) for row in rows)
    open_count = sum(_int_value(row.get("openCount")) for row in rows)
    cart_count = sum(_int_value(row.get("cartCount")) for row in rows)
    return {
        "openCount": open_count,
        "cartCount": cart_count,
        "orderCount": order_count,
        "orderSumKopecks": order_sum,
        "buyoutCount": buyout_count,
        "buyoutSumKopecks": buyout_sum,
        "cancelCount": cancel_count,
        "buyoutPct": round(buyout_count / order_count * 100, 1) if order_count > 0 else None,
    }


def _cached_funnel_rows_from_baskets_cache(cache: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for raw_nm_id, aggregate in _cache_aggregates(cache).items():
        if not isinstance(aggregate, dict):
            continue
        nm_id = _int_value(aggregate.get("nmId") or aggregate.get("nmID") or raw_nm_id)
        if nm_id <= 0:
            continue
        rows.append(
            {
                "nmId": nm_id,
                "openCount": _int_value(
                    aggregate.get("openCount")
                    or aggregate.get("openCard")
                    or aggregate.get("openCardCount")
                    or aggregate.get("views")
                    or aggregate.get("viewCount")
                ),
                "cartCount": _int_value(
                    aggregate.get("cartCount")
                    or aggregate.get("cartAdds")
                    or aggregate.get("addToCart")
                    or aggregate.get("addToCartCount")
                    or aggregate.get("basketCount")
                    or aggregate.get("baskets")
                ),
                "orderCount": _int_value(aggregate.get("orderCount") or aggregate.get("ordersCount") or aggregate.get("orders")),
                "orderSumKopecks": _int_value(aggregate.get("orderSumKopecks") or aggregate.get("ordersKopecks")),
                "buyoutCount": _int_value(aggregate.get("buyoutCount") or aggregate.get("salesUnits")),
                "buyoutSumKopecks": _int_value(aggregate.get("buyoutSumKopecks") or aggregate.get("salesKopecks") or aggregate.get("revenueKopecks")),
                "cancelCount": _int_value(aggregate.get("cancelCount") or aggregate.get("returnsUnits")),
            }
        )
    return rows


def _cached_funnel_daily_rows(cache: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    raw_daily = cache.get("dailyAggregates") or cache.get("dailyRows") or cache.get("daily")
    if not isinstance(raw_daily, dict):
        return {}
    result: dict[str, list[dict[str, Any]]] = {}
    for raw_day, raw_rows in raw_daily.items():
        if isinstance(raw_rows, dict):
            rows = _cached_funnel_rows_from_baskets_cache({"aggregates": raw_rows})
        elif isinstance(raw_rows, list):
            rows = [dict(row) for row in raw_rows if isinstance(row, dict)]
        else:
            rows = []
        if rows:
            result[str(raw_day)] = rows
    return result


def _merged_daily_aggregates(
    organization_id: int,
    prefix: str,
    date_from: date,
    date_to: date,
) -> dict[str, Any]:
    """Merge raw dailyAggregates for a window across the caches that hold them.

    Same reason as the funnel variant: the days are spread over several cache
    windows, and the covering-cache query is far too expensive to reach for.
    """
    wanted = {
        (date_from + timedelta(days=offset)).isoformat()
        for offset in range((date_to - date_from).days + 1)
    }
    candidates: list[tuple[int, str]] = []
    for meta in list_source_cache_ranges_by_prefix(organization_id, prefix, limit=100):
        if not isinstance(meta, dict):
            continue
        source_key = str(meta.get("sourceKey") or "")
        if not source_key or "detail_status" in source_key or source_key.endswith("detail_active"):
            continue
        meta_from = _safe_cache_date(meta.get("dateFrom"))
        meta_to = _safe_cache_date(meta.get("dateTo"))
        if meta_from and meta_to:
            if meta_to < date_from or meta_from > date_to:
                continue
            overlap = (min(meta_to, date_to) - max(meta_from, date_from)).days + 1
        else:
            overlap = 0
        candidates.append((overlap, source_key))

    merged: dict[str, Any] = {}
    for _overlap, source_key in sorted(candidates, key=lambda item: item[0], reverse=True):
        if not wanted - merged.keys():
            break
        cache = get_source_cache(organization_id, source_key, slim=False) or {}
        raw_daily = cache.get("dailyAggregates")
        if not isinstance(raw_daily, dict):
            continue
        for raw_day, rows in raw_daily.items():
            day = str(raw_day)
            if day in wanted and day not in merged and rows:
                merged[day] = rows
    return merged


def _merged_funnel_daily_rows(
    organization_id: int,
    date_from: date,
    date_to: date,
) -> dict[str, list[dict[str, Any]]]:
    """Stitch basket daily detail for a window out of every cache that holds it.

    Daily detail is filled in chunks, so a 14-day chart routinely needs days
    spread over several cache windows.  Reading only the newest covering cache
    left the older half of the chart at zero orders while those days sat in a
    neighbouring cache.

    Each cache carries thousands of SKU rows, so we only open the ones whose
    range actually overlaps the window, widest overlap first, and stop as soon
    as every day is accounted for.
    """
    wanted = {
        (date_from + timedelta(days=offset)).isoformat()
        for offset in range((date_to - date_from).days + 1)
    }
    candidates: list[tuple[int, str]] = []
    for meta in list_source_cache_ranges_by_prefix(organization_id, "baskets_", limit=100):
        if not isinstance(meta, dict):
            continue
        source_key = str(meta.get("sourceKey") or "")
        if not source_key or "detail_status" in source_key or source_key.endswith("detail_active"):
            continue
        meta_from = _safe_cache_date(meta.get("dateFrom"))
        meta_to = _safe_cache_date(meta.get("dateTo"))
        if meta_from and meta_to:
            if meta_to < date_from or meta_from > date_to:
                continue
            overlap = (min(meta_to, date_to) - max(meta_from, date_from)).days + 1
        else:
            overlap = 0
        candidates.append((overlap, source_key))

    merged: dict[str, list[dict[str, Any]]] = {}
    for _overlap, source_key in sorted(candidates, key=lambda item: item[0], reverse=True):
        if not wanted - merged.keys():
            break
        cache = get_source_cache(organization_id, source_key, slim=False) or {}
        raw_daily = cache.get("dailyAggregates") or cache.get("dailyRows") or cache.get("daily")
        if not isinstance(raw_daily, dict):
            continue
        for raw_day, raw_rows in raw_daily.items():
            day = str(raw_day)
            if day not in wanted or day in merged:
                continue
            if isinstance(raw_rows, dict):
                rows = _cached_funnel_rows_from_baskets_cache({"aggregates": raw_rows})
            elif isinstance(raw_rows, list):
                rows = [dict(row) for row in raw_rows if isinstance(row, dict)]
            else:
                rows = []
            if rows:
                merged[day] = rows
    return merged


def _safe_cache_date(value: Any) -> date | None:
    try:
        return date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return None


def _build_digest_funnel_snapshot(
    *,
    organization_id: int,
    date_from: date,
    date_to: date,
    wb_token: str | None,
    progress_callback: Any | None = None,
) -> dict[str, Any]:
    cache = _period_cache(organization_id, "baskets", date_from, date_to)
    graph_from = max(date_from, date_to - timedelta(days=13))
    rows = _cached_funnel_rows_from_baskets_cache(cache)
    # Merging the days we need out of the overlapping caches costs about a
    # second; the covering-cache query costs half a minute because it parses
    # every multi-megabyte payload in the table.  Only fall back to it when the
    # merge came up empty.
    daily = _merged_funnel_daily_rows(organization_id, graph_from, date_to)
    if not daily:
        graph_cache = get_covering_source_cache(
            organization_id,
            "baskets_",
            date_from=graph_from,
            date_to=date_to,
            slim=False,
        ) or cache
        daily = _cached_funnel_daily_rows(graph_cache)
    finance_daily = _merged_daily_aggregates(organization_id, "finance_", graph_from, date_to)
    if not finance_daily:
        finance_cache = get_covering_source_cache(
            organization_id,
            "finance_",
            date_from=graph_from,
            date_to=date_to,
            slim=False,
        ) or _period_cache(organization_id, "finance", date_from, date_to)
        raw_finance = finance_cache.get("dailyAggregates")
        finance_daily = raw_finance if isinstance(raw_finance, dict) else {}
    errors = [] if rows else ["WB_FUNNEL_CACHE_EMPTY"]
    status = "hit" if cache else "missing"
    return {
        "rows": rows,
        "dailyRows": daily,
        "financeDailyRows": finance_daily,
        "totals": _funnel_rows_totals(rows),
        "status": "fresh" if rows else ("blocked" if errors else "empty"),
        "cacheStatus": status,
        "errors": errors,
    }


def _build_weekly_balance(date_range: dict[str, str], source_snapshot: Any) -> dict[str, Any]:
    date_from, date_to = _digest_period_bounds(date_range)
    days = [date_from + timedelta(days=offset) for offset in range((date_to - date_from).days + 1)]
    if len(days) > 14:
        days = days[-14:]
    buckets = {day: _empty_daily_bucket(day) for day in days}

    for row in source_snapshot.orders:
        row_date = _date_from_source_row(row)
        if row_date not in buckets:
            continue
        units = _cached_row_units(row)
        buckets[row_date]["ordersUnits"] += units
        buckets[row_date]["ordersKopecks"] += int(round(float(row.get("finishedPrice") or 0) * 100)) * units

    for row in source_snapshot.sales:
        row_date = _date_from_source_row(row)
        if row_date not in buckets:
            continue
        units = _cached_row_units(row)
        if bool(row.get("isReturn")):
            buckets[row_date]["returnsUnits"] += units
            continue
        buckets[row_date]["salesUnits"] += units
        buckets[row_date]["salesKopecks"] += int(round(float(row.get("finishedPrice") or 0) * 100)) * units

    points = []
    for bucket in buckets.values():
        orders_units = int(bucket["ordersUnits"])
        sales_units = int(bucket["salesUnits"])
        bucket["buyoutPct"] = round(sales_units / orders_units * 100, 1) if orders_units > 0 else None
        points.append(bucket)

    return {
        "title": "Баланс за неделю",
        "valueLabel": "Заказы",
        "compareLabel": "Продажи",
        "points": points,
    }


def _build_funnel_weekly_balance(date_range: dict[str, str], funnel_snapshot: dict[str, Any]) -> dict[str, Any] | None:
    daily_rows = funnel_snapshot.get("dailyRows") if isinstance(funnel_snapshot.get("dailyRows"), dict) else {}
    if not daily_rows:
        return None
    finance_daily_rows = funnel_snapshot.get("financeDailyRows") if isinstance(funnel_snapshot.get("financeDailyRows"), dict) else {}
    date_from, date_to = _digest_period_bounds(date_range)
    graph_from = max(date_from, date_to - timedelta(days=13))
    days = [graph_from + timedelta(days=offset) for offset in range((date_to - graph_from).days + 1)]
    points = []
    for day in days:
        rows = daily_rows.get(day.isoformat())
        totals = _funnel_rows_totals([row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else [])
        finance_rows = finance_daily_rows.get(day.isoformat())
        finance_rows = finance_rows.values() if isinstance(finance_rows, dict) else []
        finance_rows = [row for row in finance_rows if isinstance(row, dict)]
        gross_sales_units = sum(_int_value(row.get("salesUnits")) for row in finance_rows)
        returns_units = sum(_int_value(row.get("returnsUnits")) for row in finance_rows)
        sales_units = max(0, gross_sales_units - returns_units)
        sales_kopecks = sum(_int_value(row.get("buyerRevenueKopecks")) for row in finance_rows)
        if not finance_daily_rows:
            sales_units = _int_value(totals["buyoutCount"])
            returns_units = _int_value(totals["cancelCount"])
            sales_kopecks = _int_value(totals["buyoutSumKopecks"])
        bucket = _empty_daily_bucket(day)
        bucket.update(
            {
                "ordersUnits": totals["orderCount"],
                "ordersKopecks": totals["orderSumKopecks"],
                "salesUnits": sales_units,
                "salesKopecks": sales_kopecks,
                "returnsUnits": returns_units,
                "buyoutPct": round(sales_units / _int_value(totals["orderCount"]) * 100, 1) if _int_value(totals["orderCount"]) > 0 else None,
                "openCount": totals["openCount"],
                "cartCount": totals["cartCount"],
                "source": "wb_sales_funnel",
            }
        )
        points.append(bucket)
    return {
        "title": "Воронка продаж по дням",
        "valueLabel": "Заказали",
        "compareLabel": "Выкупили",
        "points": points,
        "source": "wb_sales_funnel",
    }


def _period_card(id_: str, label: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    orders_units = sum(_int_value(row.get("ordersUnits")) for row in rows)
    orders_kopecks = sum(_int_value(row.get("ordersKopecks")) for row in rows)
    sales_units = sum(_int_value(row.get("salesUnits")) for row in rows)
    sales_kopecks = sum(_int_value(row.get("salesKopecks")) for row in rows)
    returns_units = sum(_int_value(row.get("returnsUnits")) for row in rows)
    buyout_pct = round(sales_units / orders_units * 100, 1) if orders_units > 0 else None
    return {
        "id": id_,
        "label": label,
        "ordersUnits": orders_units,
        "ordersKopecks": orders_kopecks,
        "salesUnits": sales_units,
        "returnsUnits": returns_units,
        "buyoutPct": buyout_pct,
        "revenueKopecks": sales_kopecks,
    }


def _build_period_cards(date_range: dict[str, str], weekly_balance: dict[str, Any]) -> list[dict[str, Any]]:
    _date_from, date_to = _digest_period_bounds(date_range)
    points = list(weekly_balance["points"])
    today_rows = [row for row in points if row["date"] == date_to.isoformat()]
    yesterday_rows = [row for row in points if row["date"] == (date_to - timedelta(days=1)).isoformat()]
    return [
        _period_card("selected", "Выбранный период", points),
        _period_card("today", "Сегодня", today_rows),
        _period_card("yesterday", "Вчера", yesterday_rows),
    ]


def _preliminary_margin_kopecks(source_snapshot: Any) -> int:
    seller_payout = sum(int(value or 0) for value in getattr(source_snapshot, "seller_payout_by_nm_kopecks", {}).values())
    costs = 0
    for attr in (
        "commission_cost_by_nm_kopecks",
        "logistics_cost_by_nm_kopecks",
        "penalties_cost_by_nm_kopecks",
        "acceptance_cost_by_nm_kopecks",
        "storage_cost_by_nm_kopecks",
    ):
        costs += sum(abs(int(value or 0)) for value in getattr(source_snapshot, attr, {}).values())
    return seller_payout - costs


def _digest_oos_affected_item(stock_row: dict[str, Any]) -> dict[str, Any]:
    available_units = _as_int(stock_row.get("availableUnits"))
    return {
        "sku": str(stock_row.get("sku") or f"NM_{stock_row.get('nmId') or ''}"),
        "nmId": _as_int(stock_row.get("nmId")),
        "warehouseName": str(stock_row.get("warehouseName") or "unknown"),
        "availableUnits": available_units,
        "wbStockUnits": _as_int(stock_row.get("wbStockUnits")),
        "fromClientUnits": _as_int(stock_row.get("fromClientUnits")),
        "toClientUnits": _as_int(stock_row.get("toClientUnits")),
        "reason": f"Доступный остаток {available_units or 0} шт",
    }


def _build_digest_problem_rows(stock_rows: list[dict[str, Any]], ads_snapshot: Any) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    # Stocks arrive per warehouse, while the digest and its link promise a SKU count.
    # Keep one row per NM ID so a SKU stored in two empty warehouses is not counted twice.
    oos_by_nm: dict[str, dict[str, Any]] = {}
    for stock_row in stock_rows:
        if stock_row["availableUnits"] <= 0:
            oos_by_nm.setdefault(str(stock_row.get("nmId") or stock_row["sku"]), stock_row)
    oos_rows = list(oos_by_nm.values())
    if oos_rows:
        sample_skus = [str(row["sku"]) for row in oos_rows[:5]]
        affected_items = [_digest_oos_affected_item(row) for row in oos_rows]
        rows.append(
            {
                "id": "oos-risk",
                "kind": "oos_risk",
                "title": f"{len(oos_rows)} SKU с риском OOS",
                "details": f"Товары, у которых нулевой доступный остаток: {', '.join(sample_skus)}"
                + ("..." if len(oos_rows) > len(sample_skus) else ""),
                "metric": "Остатки",
                "reason": "oos_risk",
                "recommendation": "Проверить поставку и остатки WB",
                "skuCount": len(oos_rows),
                "affectedItems": affected_items,
            }
        )
    weak_ads_rows: list[Any] = []
    for row in getattr(ads_snapshot, "rows", []):
        attribution_level = _dict_or_attr(row, "attributionLevel")
        if attribution_level in {"campaign_only", "unknown"}:
            weak_ads_rows.append(row)
    if weak_ads_rows:
        sample_campaigns = [str(_dict_or_attr(row, "campaignName", _dict_or_attr(row, "campaignId", "РК"))) for row in weak_ads_rows[:3]]
        rows.append(
            {
                "id": "weak-ads-attribution",
                "kind": "weak_ads_attribution",
                "title": f"{len(weak_ads_rows)} кампании требуют review",
                "details": f"Ads attribution частичная: {', '.join(sample_campaigns)}. Stop/action только после approval.",
                "metric": "Реклама",
                "reason": "weak_ads_attribution",
                "recommendation": "Review перед stop/action",
                "campaignCount": len(weak_ads_rows),
            }
        )
    return rows


def _as_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        try:
            return int(float(value.strip().replace(",", ".")))
        except ValueError:
            return None
    return None


def _as_float(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.strip().replace(",", "."))
        except ValueError:
            return None
    return None


def _extract_payload_items(node: Any) -> list[dict[str, Any]]:
    if isinstance(node, list):
        return [item for item in node if isinstance(item, dict)]
    if isinstance(node, dict):
        for key in ("items", "data", "rows", "report", "warehouseList", "stocks"):
            candidate = node.get(key)
            if isinstance(candidate, list):
                return [item for item in candidate if isinstance(item, dict)]
            if isinstance(candidate, dict):
                nested = _extract_payload_items(candidate)
                if nested:
                    return nested
        response = node.get("response")
        if isinstance(response, dict):
            nested = _extract_payload_items(response)
            if nested:
                return nested
        return [node]
    return []


def _normalize_key(value: Any) -> str:
    return str(value or "").strip().casefold()


def _stock_rows_as_dicts(rows: list[WbStockRow]) -> list[dict[str, Any]]:
    return [
        {
            "nmId": row.nm_id,
            "chrtId": row.chrt_id,
            "warehouseId": row.warehouse_id,
            "warehouseName": row.warehouse_name,
            "regionName": row.region_name,
            "quantity": row.quantity,
            "inWayToClient": row.in_way_to_client,
            "inWayFromClient": row.in_way_from_client,
            "availableUnits": row.available_units,
            "wasOutOfStock": row.was_out_of_stock,
            "stockType": row.stock_type,
            "totalStockUnits": row.total_stock_units,
        }
        for row in rows
    ]


def _financial_rows_as_dicts(rows: list[Any]) -> list[dict[str, Any]]:
    return [
        {
            "rrdId": row.rrd_id,
            "nmId": row.nm_id,
            "srid": row.srid,
            "retailAmountKopecks": row.retail_amount_kopecks,
            "sellerPayoutKopecks": row.seller_payout_kopecks,
            "commissionPercent": row.commission_percent,
            "commissionKopecks": row.commission_kopecks,
            "logisticsKopecks": row.logistics_kopecks,
        }
        for row in rows
    ]


def _cache_source_payload(
    *,
    organization_id: int,
    source_key: str,
    status: str,
    payload: dict[str, Any],
    error: str | None = None,
) -> dict[str, Any]:
    rows = _extract_payload_items(payload.get("data", payload))
    stored = {
        "sourceKey": source_key,
        "status": status,
        "rowsCount": len(rows),
        **payload,
    }
    if error:
        stored["error"] = error
    if status in {"fresh", "partial"}:
        return save_source_cache(organization_id, source_key, stored)
    cached = get_source_cache(organization_id, source_key)
    if cached:
        cached_payload = dict(cached)
        cached_payload["status"] = "cached"
        cached_payload.setdefault("sourceKey", source_key)
        cached_payload.setdefault("rowsCount", len(_extract_payload_items(cached_payload.get("data", cached_payload))))
        if error:
            cached_payload["error"] = error
        return cached_payload
    return stored


def _request_source_with_cache(
    *,
    organization_id: int,
    source_key: str,
    client: RateLimitedWbApiClient,
    request: WbApiRequest,
) -> dict[str, Any]:
    try:
        envelope = client.request(request)
    except Exception as exc:  # pragma: no cover - real network/client guard
        return _cache_source_payload(
            organization_id=organization_id,
            source_key=source_key,
            status="error",
            payload={"data": None, "request": request.model_dump(mode="json")},
            error=str(exc),
        )
    status = "fresh" if envelope.ok else "error"
    return _cache_source_payload(
        organization_id=organization_id,
        source_key=source_key,
        status=status,
        payload={
            "data": envelope.data,
            "statusCode": envelope.statusCode,
            "request": envelope.request.model_dump(mode="json"),
            "wbRequestId": envelope.wbRequestId,
        },
        error=envelope.error.message if envelope.error else None,
    )


STOCK_AVAILABILITY_FILTERS = ["deficient", "actual", "balanced", "nonActual", "nonLiquid", "invalidData"]


def _stock_products_request_body(date_range: dict[str, str], *, stock_type: str = "") -> dict[str, Any]:
    return {
        "nmIDs": [],
        "currentPeriod": {"start": date_range["from"], "end": date_range["to"]},
        "stockType": stock_type,
        "skipDeletedNm": True,
        "orderBy": {"field": "avgOrders", "mode": "desc"},
        "availabilityFilters": STOCK_AVAILABILITY_FILTERS,
        "limit": 1000,
        "offset": 0,
    }


def _build_stock_source_bundle(
    *,
    organization_id: int,
    snapshot: Any,
    date_range: dict[str, str],
    wb_token: str | None,
) -> dict[str, dict[str, Any]]:
    sources: dict[str, dict[str, Any]] = {
        "wb_stock_current": _cache_source_payload(
            organization_id=organization_id,
            source_key="wb_stock_current",
            status="fresh" if snapshot.stocks else snapshot.source_status,
            payload={"data": _stock_rows_as_dicts(snapshot.stocks), "grain": "nmId x chrtId x warehouseId"},
        ),
        "wb_stock_remains_async": _cache_source_payload(
            organization_id=organization_id,
            source_key="wb_stock_remains_async",
            status="fresh" if snapshot.stocks else snapshot.source_status,
            payload={"data": _stock_rows_as_dicts(snapshot.stocks), "grain": "nmId x barcode x warehouseName"},
        ),
        "raw_orders": _cache_source_payload(
            organization_id=organization_id,
            source_key="raw_orders",
            status="fresh" if snapshot.orders else snapshot.source_status,
            payload={"data": snapshot.orders, "grain": "srid x nmId x warehouseName"},
        ),
        "raw_sales": _cache_source_payload(
            organization_id=organization_id,
            source_key="raw_sales",
            status="fresh" if snapshot.sales else snapshot.source_status,
            payload={"data": snapshot.sales, "grain": "sale/return x nmId x warehouseName"},
        ),
        "finance_logistics_fact": _cache_source_payload(
            organization_id=organization_id,
            source_key="finance_logistics_fact",
            status="fresh" if snapshot.financial_rows else snapshot.source_status,
            payload={"financialRows": _financial_rows_as_dicts(snapshot.financial_rows), "grain": "rrdId / srid / nmId"},
        ),
    }

    if get_settings().wb_api_mode == "real" and not wb_token:
        for key in (
            "seller_stock_current",
            "buyer_region_sales",
            "stock_product_metrics",
            "stock_size_office_metrics",
            "wb_offices_dim",
            "fbw_warehouses_dim",
            "box_tariffs",
            "pallet_tariffs",
        ):
            sources[key] = _cache_source_payload(
                organization_id=organization_id,
                source_key=key,
                status="blocked",
                payload={"data": None},
                error="WB_TOKEN_REQUIRED",
            )
    else:
        analytics_client = RateLimitedWbApiClient(inner=build_wb_analytics_client(token_override=wb_token))
        marketplace_client = RateLimitedWbApiClient(inner=build_wb_marketplace_client(token_override=wb_token))
        supplies_client = RateLimitedWbApiClient(inner=build_wb_supplies_client(token_override=wb_token))
        common_client = RateLimitedWbApiClient(inner=build_wb_common_client(token_override=wb_token))
        sources["buyer_region_sales"] = _request_source_with_cache(
            organization_id=organization_id,
            source_key="buyer_region_sales",
            client=analytics_client,
            request=WbApiRequest(method="GET", path="/api/v1/analytics/region-sale", query={"dateFrom": date_range["from"], "dateTo": date_range["to"]}),
        )
        sources["stock_product_metrics"] = _request_source_with_cache(
            organization_id=organization_id,
            source_key="stock_product_metrics",
            client=analytics_client,
            request=WbApiRequest(
                method="POST",
                path="/api/v2/stocks-report/products/products",
                jsonBody=_stock_products_request_body(date_range, stock_type=""),
            ),
        )
        sources["stock_size_office_metrics"] = _cache_source_payload(
            organization_id=organization_id,
            source_key="stock_size_office_metrics",
            status="missing",
            payload={
                "data": None,
                "reason": "WB /api/v2/stocks-report/products/sizes requires a concrete nmID; product drilldown is not requested for the summary table",
            },
        )
        sources["wb_offices_dim"] = _request_source_with_cache(
            organization_id=organization_id,
            source_key="wb_offices_dim",
            client=marketplace_client,
            request=WbApiRequest(method="GET", path="/api/v3/offices"),
        )
        sources["fbw_warehouses_dim"] = _request_source_with_cache(
            organization_id=organization_id,
            source_key="fbw_warehouses_dim",
            client=supplies_client,
            request=WbApiRequest(method="GET", path="/api/v1/warehouses"),
        )
        sources["box_tariffs"] = _request_source_with_cache(
            organization_id=organization_id,
            source_key="box_tariffs",
            client=common_client,
            request=WbApiRequest(method="GET", path="/api/v1/tariffs/box", query={"date": date_range["to"]}),
        )
        sources["pallet_tariffs"] = _request_source_with_cache(
            organization_id=organization_id,
            source_key="pallet_tariffs",
            client=common_client,
            request=WbApiRequest(method="GET", path="/api/v1/tariffs/pallet", query={"date": date_range["to"]}),
        )

        configured_ids = set(get_settings().wb_seller_stock_warehouse_ids)
        stock_ids = {row.warehouse_id for row in snapshot.stocks if row.warehouse_id}
        warehouse_ids = sorted(configured_ids | stock_ids)[:10]
        seller_stock_rows: list[dict[str, Any]] = []
        seller_stock_errors: list[str] = []
        for warehouse_id in warehouse_ids:
            result = _request_source_with_cache(
                organization_id=organization_id,
                source_key=f"seller_stock_current_{warehouse_id}",
                client=marketplace_client,
                request=WbApiRequest(method="POST", path=f"/api/v3/stocks/{warehouse_id}", jsonBody={"skus": []}),
            )
            if result.get("status") in {"fresh", "cached"}:
                seller_stock_rows.extend(_extract_payload_items(result.get("data")))
            if result.get("error"):
                seller_stock_errors.append(str(result["error"]))
        sources["seller_stock_current"] = _cache_source_payload(
            organization_id=organization_id,
            source_key="seller_stock_current",
            status="fresh" if seller_stock_rows else "partial",
            payload={"data": seller_stock_rows, "warehouseIds": warehouse_ids, "grain": "warehouseId x chrtId"},
            error="; ".join(seller_stock_errors[:3]) if seller_stock_errors else None,
        )

    for manual_key in ("local_orders_exact", "ktr_table", "stock_decision_rules"):
        cached = get_source_cache(organization_id, manual_key)
        sources[manual_key] = cached if cached else {"sourceKey": manual_key, "status": "missing", "rowsCount": 0, "data": None}
    sources["krp_table"] = _cache_source_payload(
        organization_id=organization_id,
        source_key="krp_table",
        status="fresh",
        payload={
            "data": [
                {"fromPct": 0, "toPct": 29.99, "krp": 1.0},
                {"fromPct": 30, "toPct": 59.99, "krp": 0.8},
                {"fromPct": 60, "toPct": 100, "krp": 0.6},
            ],
            "source": "backend_public_doc_seed",
        },
    )
    return sources


def _source_coverage(sources: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "entity": key,
            "status": value.get("status", "unknown"),
            "rowsCount": value.get("rowsCount", len(_extract_payload_items(value.get("data", value)))),
            "fetchedAt": value.get("fetchedAt"),
            "error": value.get("error"),
        }
        for key, value in sorted(sources.items())
    ]


def _orders_index(orders: list[dict[str, Any]], days: int) -> tuple[dict[tuple[int, str], int], dict[int, int], dict[tuple[int, str], int]]:
    by_nm_warehouse: dict[tuple[int, str], int] = defaultdict(int)
    by_nm: dict[int, int] = defaultdict(int)
    local_by_nm_cluster: dict[tuple[int, str], int] = defaultdict(int)
    seen: set[str] = set()
    for row in orders:
        nm_id = _as_int(row.get("nmId"))
        if not nm_id:
            continue
        if bool(row.get("isCancel")):
            continue
        srid = str(row.get("srid") or row.get("gNumber") or "")
        dedupe = srid or f"{nm_id}:{row.get('lastChangeDate')}:{row.get('warehouseName')}"
        units = _cached_row_units(row)
        if row.get("_cachedUnits") is None and dedupe in seen:
            continue
        seen.add(dedupe)
        warehouse = _normalize_key(row.get("warehouseName"))
        buyer_region = _normalize_key(row.get("regionName") or row.get("oblastOkrugName") or row.get("oblast"))
        by_nm[nm_id] += units
        by_nm_warehouse[(nm_id, warehouse)] += units
        if buyer_region:
            local_by_nm_cluster[(nm_id, buyer_region)] += units
    return dict(by_nm_warehouse), dict(by_nm), dict(local_by_nm_cluster)


def _sales_units_by_nm(sales: list[dict[str, Any]]) -> dict[int, int]:
    result: dict[int, int] = defaultdict(int)
    for row in sales:
        nm_id = _as_int(row.get("nmId"))
        if not nm_id:
            continue
        units = _cached_row_units(row)
        result[nm_id] += -units if bool(row.get("isReturn")) else units
    return dict(result)


def _metric_order_rate_by_nm(sources: dict[str, dict[str, Any]]) -> dict[int, float]:
    result: dict[int, float] = {}
    for row in _extract_payload_items(sources.get("stock_product_metrics", {}).get("data")):
        nm_id = _as_int(row.get("nmID") or row.get("nmId"))
        rate = _as_float(
            _stock_metric_value(row, "avgOrders")
            or _stock_metric_value(row, "avgOrdersPerDay")
            or _stock_metric_value(row, "ordersPerDay")
        )
        if nm_id and rate is not None:
            result[nm_id] = rate
    return result


def _stock_product_metrics_by_nm(sources: dict[str, dict[str, Any]]) -> dict[int, dict[str, Any]]:
    result: dict[int, dict[str, Any]] = {}
    for row in _extract_payload_items(sources.get("stock_product_metrics", {}).get("data")):
        nm_id = _as_int(row.get("nmID") or row.get("nmId"))
        if not nm_id:
            continue
        result[nm_id] = row
    return result


def _stock_metric_value(row: dict[str, Any], key: str) -> Any:
    metrics = row.get("metrics")
    if isinstance(metrics, dict) and key in metrics:
        return metrics.get(key)
    return row.get(key)


def _buyer_region_orders_by_nm_region(sources: dict[str, dict[str, Any]]) -> dict[tuple[int, str], int]:
    result: dict[tuple[int, str], int] = defaultdict(int)
    for row in _extract_payload_items(sources.get("buyer_region_sales", {}).get("data")):
        nm_id = _as_int(row.get("nmID") or row.get("nmId"))
        region = _normalize_key(row.get("regionName") or row.get("buyerRegion") or row.get("region"))
        count = _as_int(row.get("ordersCount") or row.get("orders") or row.get("quantity")) or 0
        if nm_id and region:
            result[(nm_id, region)] += count
    return dict(result)


def _manual_ktr_value(sources: dict[str, dict[str, Any]], localization_pct: float | None) -> float | None:
    if localization_pct is None:
        return None
    rows = _extract_payload_items(sources.get("ktr_table", {}).get("data"))
    for row in rows:
        lower = _as_float(row.get("fromPct") or row.get("from") or row.get("min"))
        upper = _as_float(row.get("toPct") or row.get("to") or row.get("max"))
        value = _as_float(row.get("ktr") or row.get("ktrIndex") or row.get("value"))
        if lower is None or upper is None or value is None:
            continue
        if lower <= localization_pct <= upper:
            return value
    return None


def _is_source_missing(sources: dict[str, dict[str, Any]], source_key: str) -> bool:
    return sources.get(source_key, {}).get("status") == "missing"


def _stock_manual_status(
    sources: dict[str, dict[str, Any]],
    *,
    has_derived_local_orders: bool,
) -> tuple[bool, list[str]]:
    ktr_missing = _is_source_missing(sources, "ktr_table")
    local_orders_exact_missing = _is_source_missing(sources, "local_orders_exact")
    warnings: list[str] = []
    if local_orders_exact_missing and not has_derived_local_orders:
        warnings.append("нет exact localOrders из seller portal")
    if ktr_missing:
        warnings.append("нет KTR table из seller portal")
    return (ktr_missing or (local_orders_exact_missing and not has_derived_local_orders)), warnings


def _stock_row_to_payload(
    row: WbStockRow,
    *,
    orders_by_nm_warehouse: dict[tuple[int, str], int],
    orders_by_nm: dict[int, int],
    local_orders_by_nm_cluster: dict[tuple[int, str], int],
    buyer_region_orders: dict[tuple[int, str], int],
    metric_rates: dict[int, float],
    sales_units: dict[int, int],
    logistics_cost_by_nm_kopecks: dict[int, int],
    days: int,
    sources: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    warehouse_key = _normalize_key(row.warehouse_name)
    cluster_key = _normalize_key(row.region_name or row.warehouse_name)
    exact_order_count = orders_by_nm_warehouse.get((row.nm_id, warehouse_key), 0)
    nm_order_count = orders_by_nm.get(row.nm_id, 0)
    metric_rate = metric_rates.get(row.nm_id)
    orders_per_day = metric_rate if metric_rate is not None else (exact_order_count / max(days, 1))
    local_orders = local_orders_by_nm_cluster.get((row.nm_id, cluster_key), 0)
    if local_orders == 0:
        local_orders = buyer_region_orders.get((row.nm_id, cluster_key), 0)
    localization_pct = round(min(local_orders / nm_order_count * 100, 100), 1) if nm_order_count > 0 else None
    ktr_index = _manual_ktr_value(sources, localization_pct)
    days_to_oos = round(row.available_units / orders_per_day, 1) if orders_per_day > 0 else None
    sold_units = max(sales_units.get(row.nm_id, 0), 0)
    logistics_total = logistics_cost_by_nm_kopecks.get(row.nm_id, 0)
    logistics_per_unit = round(logistics_total / sold_units) if sold_units > 0 and logistics_total > 0 else None

    if row.available_units <= 0 or (days_to_oos is not None and days_to_oos < 7):
        decision = "дозагрузить"
    elif days_to_oos is not None and days_to_oos > 60:
        decision = "снизить поставку"
    else:
        decision = "норма"
    manual_missing, manual_warnings = _stock_manual_status(
        sources,
        has_derived_local_orders=nm_order_count > 0,
    )
    decision_rules_missing = sources.get("stock_decision_rules", {}).get("status") == "missing"
    decision_status = "source_partial" if manual_missing or decision_rules_missing else "confirmed"
    comment_parts = []
    comment_parts.extend(manual_warnings)
    if logistics_per_unit is None:
        comment_parts.append("логистика/шт не подтверждена по продажам")
    return {
        "sku": f"NM_{row.nm_id}",
        "nmId": row.nm_id,
        "warehouseName": row.warehouse_name or "unknown",
        "clusterName": row.region_name or "unknown",
        "wbStockUnits": row.quantity,
        "fromClientUnits": row.in_way_from_client,
        "toClientUnits": row.in_way_to_client,
        "availableUnits": row.available_units,
        "ordersPerDay": round(orders_per_day, 2),
        "ordersCount": exact_order_count,
        "allOrdersCount": nm_order_count,
        "localOrdersCount": local_orders,
        "daysToOos": days_to_oos,
        "ktrIndex": ktr_index,
        "localizationPct": localization_pct,
        "logisticsPerUnitKopecks": logistics_per_unit,
        "decision": decision,
        "decisionStatus": decision_status,
        "comment": "; ".join(comment_parts) if comment_parts else "источники подтверждены",
    }


def _stock_row_to_digest_payload(row: WbStockRow) -> dict[str, Any]:
    return {
        "sku": f"NM_{row.nm_id}",
        "nmId": row.nm_id,
        "warehouseName": row.warehouse_name or "unknown",
        "clusterName": row.region_name or "unknown",
        "wbStockUnits": row.quantity,
        "fromClientUnits": row.in_way_from_client,
        "toClientUnits": row.in_way_to_client,
        "availableUnits": row.available_units,
    }


def _stock_product_rows_from_snapshot(
    *,
    stock_rows: list[WbStockRow],
    orders_by_nm: dict[int, int],
    metric_rates: dict[int, float],
    product_metrics: dict[int, dict[str, Any]],
    sales_units: dict[int, int],
    logistics_cost_by_nm_kopecks: dict[int, int],
    days: int,
    sources: dict[str, dict[str, Any]],
    catalog_meta: dict[int, dict[str, Any]],
    history: dict[int, list[Any]],
) -> list[dict[str, Any]]:
    grouped: dict[int, dict[str, Any]] = {}
    for row in stock_rows:
        bucket = grouped.setdefault(
            row.nm_id,
            {
                "quantity": 0,
                "totalStockUnits": None,
                "inWayToClient": 0,
                "inWayFromClient": 0,
                "availableUnits": 0,
                "warehouses": [],
                "regions": set(),
            },
        )
        stock_type = str(getattr(row, "stock_type", "wb") or "wb")
        bucket["quantity"] += row.quantity
        bucket["inWayToClient"] += row.in_way_to_client
        bucket["inWayFromClient"] += row.in_way_from_client
        row_total_stock = _as_int(getattr(row, "total_stock_units", None))
        if row_total_stock is not None:
            bucket["totalStockUnits"] = max(int(bucket["totalStockUnits"] or 0), row_total_stock)
        bucket["availableUnits"] += row.available_units
        if row.region_name:
            bucket["regions"].add(row.region_name)
        bucket["warehouses"].append(
            {
                "warehouseId": row.warehouse_id,
                "warehouseName": row.warehouse_name or "unknown",
                "clusterName": row.region_name or "unknown",
                "stockType": stock_type,
                "wbStockUnits": row.quantity,
                "marketplaceStockUnits": 0,
                "fromClientUnits": row.in_way_from_client,
                "toClientUnits": row.in_way_to_client,
                "availableUnits": row.available_units,
            }
        )

    rows: list[dict[str, Any]] = []
    decision_rules_missing = sources.get("stock_decision_rules", {}).get("status") == "missing"
    for nm_id, bucket in grouped.items():
        metric = product_metrics.get(nm_id, {})
        meta = catalog_meta.get(nm_id, {})
        orders_count = _as_int(_stock_metric_value(metric, "ordersCount") or _stock_metric_value(metric, "orders")) or orders_by_nm.get(nm_id, 0)
        orders_per_day = metric_rates.get(nm_id)
        if orders_per_day is None:
            orders_per_day = orders_count / max(days, 1)
        wb_stock_units = int(bucket["quantity"])
        total_stock_units = _as_int(_stock_metric_value(metric, "stockCount"))
        if total_stock_units is None:
            total_stock_units = _as_int(bucket.get("totalStockUnits"))
        if total_stock_units is None:
            total_stock_units = wb_stock_units
        total_stock_units = max(total_stock_units, wb_stock_units)
        marketplace_stock_units = max(total_stock_units - wb_stock_units, 0)
        available_units = int(bucket["availableUnits"])
        days_to_oos = round(available_units / orders_per_day, 1) if orders_per_day > 0 else None
        sold_units = max(sales_units.get(nm_id, 0), 0)
        logistics_total = logistics_cost_by_nm_kopecks.get(nm_id, 0)
        logistics_per_unit = round(logistics_total / sold_units) if sold_units > 0 and logistics_total > 0 else None
        if available_units <= 0 or (days_to_oos is not None and days_to_oos < 7):
            decision = "дозагрузить"
        elif days_to_oos is not None and days_to_oos > 60:
            decision = "снизить поставку"
        else:
            decision = "норма"
        has_derived_local_orders = orders_count > 0
        manual_missing, manual_warnings = _stock_manual_status(
            sources,
            has_derived_local_orders=has_derived_local_orders,
        )
        comment_parts = []
        comment_parts.extend(manual_warnings)
        if logistics_per_unit is None:
            comment_parts.append("логистика/шт не подтверждена по продажам")
        stock_history = history.get(nm_id, [])
        history_days = {item.snapshotDate for item in stock_history if getattr(item, "snapshotDate", None) is not None}
        warehouses = sorted(bucket["warehouses"], key=lambda item: (-(item["availableUnits"] or 0), str(item["warehouseName"])))
        top_warehouse = warehouses[0] if warehouses else {}
        regions = sorted(str(region) for region in bucket["regions"] if region)
        rows.append(
            {
                "sku": str(meta.get("sku") or f"NM_{nm_id}"),
                "nmId": nm_id,
                "productName": meta.get("productName") or f"WB {nm_id}",
                "photoUrl": meta.get("photoUrl") or _extract_wb_media_url(meta, nm_id),
                "brand": meta.get("brand"),
                "category": meta.get("category"),
                "warehouseName": f"{len(warehouses)} складов" if len(warehouses) != 1 else top_warehouse.get("warehouseName"),
                "clusterName": ", ".join(regions[:2]) if regions else "unknown",
                "wbStockUnits": wb_stock_units,
                "marketplaceStockUnits": marketplace_stock_units,
                "totalStockUnits": total_stock_units,
                "fromClientUnits": int(bucket["inWayFromClient"]),
                "toClientUnits": int(bucket["inWayToClient"]),
                "availableUnits": available_units,
                "ordersPerDay": round(float(orders_per_day), 2),
                "ordersCount": orders_count,
                "allOrdersCount": orders_count,
                "localOrdersCount": 0,
                "daysToOos": days_to_oos,
                "ktrIndex": None,
                "localizationPct": None,
                "logisticsPerUnitKopecks": logistics_per_unit,
                "decision": decision,
                "decisionStatus": "source_partial" if manual_missing or decision_rules_missing else "confirmed",
                "comment": "; ".join(comment_parts) if comment_parts else "источники подтверждены",
                "historyCoverageDays": min(7, len(history_days) or len(stock_history)),
                "historySource": "captured" if stock_history and all(item.source == "captured" for item in stock_history) else "backfilled",
                "warehouseCount": len(warehouses),
                "warehouses": warehouses,
            }
        )
    return sorted(rows, key=lambda row: (-_int_value(row.get("availableUnits")), str(row.get("sku") or "")))


def _build_stock_report_payload(date_range: dict[str, str], snapshot: Any, *, organization_id: int, wb_token: str | None) -> dict[str, Any]:
    snapshot_date = date.fromisoformat(date_range["to"])
    history = ensure_daily_stock_history(snapshot_date, snapshot.stocks)
    date_from = date.fromisoformat(date_range["from"])
    days = max((snapshot_date - date_from).days + 1, 1)
    sources = _build_stock_source_bundle(
        organization_id=organization_id,
        snapshot=snapshot,
        date_range=date_range,
        wb_token=wb_token,
    )
    _orders_by_nm_warehouse, orders_by_nm, _local_orders_by_nm_cluster = _orders_index(snapshot.orders, days)
    metric_rates = _metric_order_rate_by_nm(sources)
    product_metrics = _stock_product_metrics_by_nm(sources)
    sales_units = _sales_units_by_nm(snapshot.sales)
    rows = _stock_product_rows_from_snapshot(
        stock_rows=list(snapshot.stocks),
        orders_by_nm=orders_by_nm,
        metric_rates=metric_rates,
        product_metrics=product_metrics,
        sales_units=sales_units,
        logistics_cost_by_nm_kopecks=snapshot.logistics_cost_by_nm_kopecks,
        days=days,
        sources=sources,
        catalog_meta=_catalog_meta_by_nm(organization_id),
        history=history,
    )
    total_available = sum(row["availableUnits"] for row in rows)
    total_wb_stock = sum(row["wbStockUnits"] for row in rows)
    total_marketplace_stock = sum(row.get("marketplaceStockUnits", 0) for row in rows)
    total_stock = sum(row.get("totalStockUnits", row["wbStockUnits"]) for row in rows)
    total_from_client = sum(row["fromClientUnits"] for row in rows)
    total_to_client = sum(row["toClientUnits"] for row in rows)
    oos_risk = sum(1 for row in rows if row["daysToOos"] is not None and row["daysToOos"] < 7 or row["availableUnits"] <= 0)
    partial_sources = [item for item in _source_coverage(sources) if item["status"] not in {"fresh", "cached"}]
    local_orders_total = sum(orders_by_nm.values())
    has_derived_local_orders = local_orders_total > 0 or any(_int_value(row.get("ordersCount")) > 0 for row in rows)
    local_orders_card = {
        "title": "Local orders",
        "value": "derived" if has_derived_local_orders else ("нет exact" if _is_source_missing(sources, "local_orders_exact") else "loaded"),
        "meta": "WB orders/region-sale за выбранный период" if has_derived_local_orders else "seller portal geography orders",
        "className": "" if has_derived_local_orders or not _is_source_missing(sources, "local_orders_exact") else "warn",
        "chip": "Все",
    }
    return {
        "meta": _meta("stock", "Остатки WB", "Текущие остатки, inWay и доступность по складам WB.", "operational", snapshot.source_status),
        "cacheVersion": STOCK_REPORT_PAYLOAD_VERSION,
        "headline": "Доступный остаток считается как quantity + inWayFromClient; спрос, логистика и источники покрываются live WB API + backend cache.",
        "filters": {"dateRange": date_range, "groupBy": "sku"},
        "kpis": [
            _kpi("stock_rows", "Товаров", str(len(rows))),
            _kpi("available_units", "Доступно, шт", str(total_available)),
            _kpi("total_stock_units", "Итого остатков, шт", str(total_stock)),
            _kpi("wb_stock_units", "Остаток WB, шт", str(total_wb_stock)),
            _kpi("marketplace_stock_units", "Маркетплейс, шт", str(total_marketplace_stock)),
            _kpi("from_client_units", "От клиента, шт", str(total_from_client)),
            _kpi("to_client_units", "К клиенту, шт", str(total_to_client)),
            _kpi("oos_risk", "Риск OOS", str(oos_risk)),
            _kpi("history_days", "История, дней", "7"),
        ],
        "chart": {
            "title": "Доступность по складам",
            "valueLabel": "Доступно, шт",
            "points": [{"label": row["warehouseName"], "value": row["availableUnits"]} for row in rows[:20]],
        },
        "columns": [
            {"key": "sku", "label": "Артикул"},
            {"key": "nmId", "label": "WB"},
            {"key": "productName", "label": "Товар"},
            {"key": "brand", "label": "Бренд"},
            {"key": "category", "label": "Категория"},
            {"key": "warehouseName", "label": "Склад WB"},
            {"key": "clusterName", "label": "Кластер"},
            {"key": "totalStockUnits", "label": "Итого остатков"},
            {"key": "wbStockUnits", "label": "Остаток WB"},
            {"key": "fromClientUnits", "label": "От клиента"},
            {"key": "toClientUnits", "label": "К клиенту"},
            {"key": "availableUnits", "label": "Доступно"},
            {"key": "ordersPerDay", "label": "Заказы/день"},
            {"key": "daysToOos", "label": "Дней до OOS"},
            {"key": "ktrIndex", "label": "КТР"},
            {"key": "localizationPct", "label": "Локализация"},
            {"key": "logisticsPerUnitKopecks", "label": "Логистика/шт"},
            {"key": "decision", "label": "Решение"},
            {"key": "decisionStatus", "label": "Статус"},
            {"key": "comment", "label": "Комментарий"},
            {"key": "historySource", "label": "Источник истории"},
        ],
        "rows": rows,
        "sourceCoverage": _source_coverage(sources),
        "managementCards": [
            {"title": "OOS risk", "value": f"{oos_risk} SKU", "meta": "меньше 7 дней покрытия или нулевой доступный остаток", "className": "danger" if oos_risk else "", "chip": "OOS риск"},
            {"title": "Partial sources", "value": str(len(partial_sources)), "meta": "источники без fresh/cache покрытия", "className": "warn" if partial_sources else "", "chip": "Все"},
            {"title": "КТР", "value": "нет данных" if sources.get("ktr_table", {}).get("status") == "missing" else "loaded", "meta": "seller portal table для локализации", "className": "warn" if sources.get("ktr_table", {}).get("status") == "missing" else "", "chip": "КТР высокий"},
            local_orders_card,
        ],
    }


def _build_week_over_week_payload(
    date_range: dict[str, str],
    snapshot: Any,
    previous_snapshot: Any | None = None,
    ads_snapshot: Any | None = None,
    previous_ads_snapshot: Any | None = None,
    organization_id: int | None = None,
) -> dict[str, Any]:
    base = _orders_sales_by_nm(snapshot)
    previous = _orders_sales_by_nm(previous_snapshot) if previous_snapshot is not None else {}
    ads_by_nm = _ads_by_nm(ads_snapshot)
    previous_ads_by_nm = _ads_by_nm(previous_ads_snapshot)
    profit_by_nm = _profit_by_nm(snapshot, ads_by_nm)
    previous_profit_by_nm = _profit_by_nm(previous_snapshot, previous_ads_by_nm) if previous_snapshot is not None else {}
    catalog_meta = _catalog_meta_by_nm(organization_id)
    rows: list[dict[str, Any]] = []
    snapshot_date = date.fromisoformat(date_range["to"])
    history = ensure_daily_stock_history(snapshot_date, snapshot.stocks)
    for nm_id, agg in base.items():
        previous_agg = previous.get(nm_id, {})
        ads_agg = ads_by_nm.get(nm_id, {})
        previous_ads_agg = previous_ads_by_nm.get(nm_id, {})
        profit_agg = profit_by_nm.get(nm_id, {})
        previous_profit_agg = previous_profit_by_nm.get(nm_id, {})
        current_price = round(agg["orders_revenue"] / agg["orders_qty"]) if agg["orders_qty"] else None
        previous_price = round(previous_agg.get("orders_revenue", 0) / previous_agg.get("orders_qty", 0)) if previous_agg.get("orders_qty") else None
        stock_history = history.get(nm_id, [])
        availability_7d = [not item.wasOutOfStock for item in stock_history] if stock_history else [True] * 7
        was_oos = any(not value for value in availability_7d)
        history_source = "captured" if stock_history and all(item.source == "captured" for item in stock_history) else "backfilled"
        meta = catalog_meta.get(nm_id, {})
        sku = str(meta.get("sku") or f"NM_{nm_id}")
        rows.append(
            {
                "sku": sku,
                "nmId": nm_id,
                "productName": meta.get("productName"),
                "photoUrl": meta.get("photoUrl") or _extract_wb_media_url(meta, nm_id),
                "brand": meta.get("brand"),
                "category": meta.get("category"),
                "productStatus": "средний",
                "abcCode": "BB",
                "orders": {"units": agg["orders_qty"], "kopecks": agg["orders_revenue"], "deltaPct": _delta_pct(agg["orders_qty"], previous_agg.get("orders_qty"))},
                "sales": {"units": agg["sales_qty"], "kopecks": agg["sales_revenue"], "deltaPct": _delta_pct(agg["sales_qty"], previous_agg.get("sales_qty"))},
                "baskets": {"units": ads_agg.get("baskets"), "kopecks": None, "deltaPct": _delta_pct(ads_agg.get("baskets"), previous_ads_agg.get("baskets"))},
                "marginPct": {"percent": profit_agg.get("margin"), "deltaPct": _delta_pct(profit_agg.get("margin"), previous_profit_agg.get("margin"))},
                "profit": {"kopecks": profit_agg.get("profit"), "deltaPct": _delta_pct(profit_agg.get("profit"), previous_profit_agg.get("profit"))},
                "price": {"kopecks": current_price, "deltaPct": _delta_pct(current_price, previous_price)},
                "wasOutOfStock": was_oos,
                "stockAvailability7d": availability_7d,
                "stockOutDays": sum(1 for available in availability_7d if not available),
                "stockSnapshotCoveragePct": round(len(stock_history) / 7 * 100),
                "historySource": history_source,
                "conclusion": "История остатков еще накапливается: недостающие дни будут заполнены по мере новых снимков WB." if history_source == "backfilled" else "Остатки сравниваются по сохраненным ежедневным снимкам WB.",
            }
        )
    return {
        "meta": _meta("week-over-week", "Неделя к неделе", "Сравнение заказов, продаж и OOS-контекста.", "operational", snapshot.source_status),
        "cacheVersion": WEEK_OVER_WEEK_REPORT_PAYLOAD_VERSION,
        "headline": "Сравниваем текущую неделю с прошлой по продажам, заказам, марже и рискам по остаткам.",
        "filters": {"dateRange": date_range, "groupBy": "sku"},
        "kpis": [
            _kpi("sku_rows", "SKU в отчете", str(len(rows))),
            _kpi("oos_count", "SKU с OOS", str(sum(1 for row in rows if row["wasOutOfStock"]))),
            _kpi("history_days", "История, дней", "7"),
        ],
        "chart": {
            "title": "WoW: цены, маржа, прибыль, продажи, заказы, корзины",
            "valueLabel": "Текущее значение",
            "compareLabel": "Динамика, %",
            "series": ["price", "marginPct", "profit", "sales", "orders", "baskets"],
            "points": [
                {
                    "label": row["sku"],
                    "value": row["orders"]["units"],
                    "compareValue": row["orders"]["deltaPct"],
                    "sales": row["sales"],
                    "baskets": row["baskets"],
                    "marginPct": row["marginPct"],
                    "profit": row["profit"],
                    "price": row["price"],
                }
                for row in rows[:20]
            ],
        },
        "columns": [
            {"key": "sku", "label": "Артикул"},
            {"key": "abcCode", "label": "ABC"},
            {"key": "productStatus", "label": "Статус"},
            {"key": "price", "label": "Цена"},
            {"key": "orders", "label": "Заказы"},
            {"key": "sales", "label": "Продажи"},
            {"key": "wasOutOfStock", "label": "Был ОС"},
            {"key": "stockAvailability7d", "label": "Наличие 7 дней"},
            {"key": "historySource", "label": "Источник истории"},
            {"key": "conclusion", "label": "Вывод"},
        ],
        "rows": rows,
    }


def _composite_units(row: dict[str, Any], composite_key: str, fallback_key: str) -> int:
    composite = row.get(composite_key) if isinstance(row.get(composite_key), dict) else {}
    return _int_value(composite.get("units") or row.get(fallback_key))


def _composite_kopecks(row: dict[str, Any], composite_key: str, fallback_key: str) -> int:
    composite = row.get(composite_key) if isinstance(row.get(composite_key), dict) else {}
    return _int_value(composite.get("kopecks") or row.get(fallback_key))


def _abc_rows_have_period_activity(rows: list[dict[str, Any]]) -> bool:
    for row in rows:
        if not isinstance(row, dict):
            continue
        if _composite_units(row, "ordersComposite", "ordersUnits") > 0:
            return True
        if _composite_kopecks(row, "ordersComposite", "ordersKopecks") > 0:
            return True
        if _composite_units(row, "salesComposite", "salesUnits") > 0:
            return True
        if _composite_kopecks(row, "salesComposite", "salesKopecks") > 0:
            return True
        if _int_value(row.get("netTotalKopecks") or row.get("profitKopecks")) != 0:
            return True
        if _int_value(row.get("baskets")) > 0:
            return True
    return False


def _abc_rows_have_financial_activity(rows: list[dict[str, Any]]) -> bool:
    for row in rows:
        if not isinstance(row, dict):
            continue
        if _composite_units(row, "ordersComposite", "ordersUnits") > 0:
            return True
        if _composite_kopecks(row, "ordersComposite", "ordersKopecks") > 0:
            return True
        if _composite_units(row, "salesComposite", "salesUnits") > 0:
            return True
        if _composite_kopecks(row, "salesComposite", "salesKopecks") > 0:
            return True
        if _int_value(row.get("netTotalKopecks") or row.get("profitKopecks")) != 0:
            return True
        if _int_value(row.get("adSpendKopecks")) > 0:
            return True
    return False


def _repricer_rows_to_abc_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        mapped
        for mapped in (_repricer_row_to_abc_row(row) for row in rows if isinstance(row, dict))
        if mapped.get("sku")
    ]


def _week_report_has_period_activity(report: dict[str, Any]) -> bool:
    rows = report.get("rows") if isinstance(report.get("rows"), list) else []
    for row in rows:
        if not isinstance(row, dict):
            continue
        orders = row.get("orders") if isinstance(row.get("orders"), dict) else {}
        sales = row.get("sales") if isinstance(row.get("sales"), dict) else {}
        baskets = row.get("baskets") if isinstance(row.get("baskets"), dict) else {}
        profit = row.get("profit") if isinstance(row.get("profit"), dict) else {}
        if _int_value(orders.get("units") or orders.get("kopecks")) > 0:
            return True
        if _int_value(sales.get("units") or sales.get("kopecks")) > 0:
            return True
        if _int_value(baskets.get("units") or baskets.get("kopecks")) > 0:
            return True
        if _int_value(profit.get("kopecks")) != 0:
            return True
    return False


def _week_row_key(row: dict[str, Any]) -> str:
    return str(row.get("nmId") or row.get("sku") or row.get("label") or "").strip()


def _week_rows_from_abc_rows(rows: list[dict[str, Any]], previous_rows: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    previous_by_key = {_week_row_key(row): row for row in previous_rows or [] if _week_row_key(row)}
    result: list[dict[str, Any]] = []
    for row in rows:
        key = _week_row_key(row)
        previous = previous_by_key.get(key, {})
        orders_units = _composite_units(row, "ordersComposite", "ordersUnits")
        orders_kopecks = _composite_kopecks(row, "ordersComposite", "ordersKopecks")
        sales_units = _composite_units(row, "salesComposite", "salesUnits")
        sales_kopecks = _composite_kopecks(row, "salesComposite", "salesKopecks")
        previous_orders_units = _composite_units(previous, "ordersComposite", "ordersUnits") if previous else None
        previous_sales_units = _composite_units(previous, "salesComposite", "salesUnits") if previous else None
        baskets = _int_value(row.get("baskets"))
        previous_baskets = _int_value(previous.get("baskets")) if previous else None
        margin = _float_value(row.get("marginPct"))
        previous_margin = _float_value(previous.get("marginPct")) if previous else None
        profit = _int_value(row.get("netTotalKopecks") or row.get("profitKopecks"))
        previous_profit = _int_value(previous.get("netTotalKopecks") or previous.get("profitKopecks")) if previous else None
        price = _int_value(row.get("priceWithSppKopecks") or row.get("priceKopecks"))
        previous_price = _int_value(previous.get("priceWithSppKopecks") or previous.get("priceKopecks")) if previous else None
        stock_units = _int_value(row.get("wbStockUnits"))
        availability = ([False] * 7) if stock_units <= 0 else ([True] * 7)
        result.append(
            {
                "sku": str(row.get("sku") or row.get("label") or f"NM_{row.get('nmId') or 'unknown'}"),
                "nmId": row.get("nmId"),
                "productName": row.get("productName") or row.get("name"),
                "brand": row.get("brand"),
                "category": row.get("category"),
                "productStatus": row.get("productStatus") or "средний",
                "abcCode": row.get("abcCode") or "CC",
                "orders": {"units": orders_units, "kopecks": orders_kopecks, "deltaPct": _delta_pct(orders_units, previous_orders_units)},
                "sales": {"units": sales_units, "kopecks": sales_kopecks, "deltaPct": _delta_pct(sales_units, previous_sales_units)},
                "baskets": {"units": baskets, "kopecks": None, "deltaPct": _delta_pct(baskets, previous_baskets)},
                "marginPct": {"percent": margin, "deltaPct": _delta_pct(margin, previous_margin)},
                "profit": {"kopecks": profit, "deltaPct": _delta_pct(profit, previous_profit)},
                "price": {"kopecks": price, "deltaPct": _delta_pct(price, previous_price)},
                "wasOutOfStock": stock_units <= 0,
                "stockAvailability7d": availability,
                "stockOutDays": sum(1 for available in availability if not available),
                "stockSnapshotCoveragePct": 0,
                "historySource": row.get("historySource") or "abc_cache",
                "conclusion": row.get("conclusion") or "WoW row is normalized from period metrics for the selected current and previous ranges.",
            }
        )
    return result


def _week_over_week_shell(date_range: dict[str, str], rows: list[dict[str, Any]], *, source_status: str = "partial") -> dict[str, Any]:
    return {
        "meta": _meta("week-over-week", "Неделя к неделе", "Сравнение заказов, продаж и OOS-контекста.", "operational", source_status),
        "cacheVersion": WEEK_OVER_WEEK_REPORT_PAYLOAD_VERSION,
        "headline": "Сравниваем текущую неделю с прошлой по продажам, заказам, марже и рискам по остаткам.",
        "filters": {"dateRange": date_range, "groupBy": "sku"},
        "kpis": [
            _kpi("sku_rows", "SKU в отчете", str(len(rows))),
            _kpi("oos_count", "SKU с OOS", str(sum(1 for row in rows if row.get("wasOutOfStock")))),
            _kpi("history_days", "История, дней", "7"),
        ],
        "chart": {
            "title": "WoW: цены, маржа, прибыль, продажи, заказы, корзины",
            "valueLabel": "Текущее значение",
            "compareLabel": "Динамика, %",
            "series": ["price", "marginPct", "profit", "sales", "orders", "baskets"],
            "points": [
                {
                    "label": row["sku"],
                    "value": row["orders"]["units"],
                    "compareValue": row["orders"]["deltaPct"],
                    "sales": row["sales"],
                    "baskets": row["baskets"],
                    "marginPct": row["marginPct"],
                    "profit": row["profit"],
                    "price": row["price"],
                }
                for row in rows[:20]
            ],
        },
        "columns": [
            {"key": "sku", "label": "Артикул"},
            {"key": "abcCode", "label": "ABC"},
            {"key": "productStatus", "label": "Статус"},
            {"key": "price", "label": "Цена"},
            {"key": "orders", "label": "Заказы"},
            {"key": "sales", "label": "Продажи"},
            {"key": "wasOutOfStock", "label": "Был ОС"},
            {"key": "stockAvailability7d", "label": "Наличие 7 дней"},
            {"key": "historySource", "label": "Источник истории"},
            {"key": "conclusion", "label": "Вывод"},
        ],
        "rows": rows,
    }


def _abc_payload_rows(payload: Any) -> list[dict[str, Any]]:
    return [row for row in getattr(payload, "rows", []) or [] if isinstance(row, dict)]


def _week_period_stats_aggregates(organization_id: int, date_from: date, date_to: date) -> dict[str, dict[str, Any]]:
    try:
        return _cache_aggregates(_period_cache(organization_id, "period_stats", date_from, date_to))
    except Exception:
        return {}


def _week_rows_with_period_stats(rows: list[dict[str, Any]], period_stats: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    if not rows or not period_stats:
        return rows
    enriched_rows: list[dict[str, Any]] = []
    for row in rows:
        nm_key = str(row.get("nmId") or "").strip()
        stats = period_stats.get(nm_key) if nm_key else None
        if not isinstance(stats, dict):
            enriched_rows.append(row)
            continue

        enriched = dict(row)
        changed = False
        period_orders = _int_value(stats.get("ordersUnits"))
        period_sales = _int_value(stats.get("salesUnits"))
        period_revenue = _int_value(stats.get("revenueKopecks"))

        orders_units = _composite_units(enriched, "ordersComposite", "ordersUnits")
        orders_kopecks = _composite_kopecks(enriched, "ordersComposite", "ordersKopecks")
        if period_orders > 0 and orders_units <= 0:
            orders = dict(enriched.get("ordersComposite") or {})
            orders["units"] = period_orders
            orders["kopecks"] = orders_kopecks or period_revenue
            enriched["ordersUnits"] = period_orders
            enriched["ordersKopecks"] = orders["kopecks"]
            enriched["ordersComposite"] = orders
            changed = True

        sales_units = _composite_units(enriched, "salesComposite", "salesUnits")
        sales_kopecks = _composite_kopecks(enriched, "salesComposite", "salesKopecks")
        if period_sales > 0 and sales_units <= 0:
            sales = dict(enriched.get("salesComposite") or {})
            sales["units"] = period_sales
            sales["kopecks"] = sales_kopecks or period_revenue
            enriched["salesUnits"] = period_sales
            enriched["salesKopecks"] = sales["kopecks"]
            enriched["salesComposite"] = sales
            sales_kopecks = _int_value(sales["kopecks"])
            changed = True
        elif period_revenue > 0 and sales_kopecks <= 0:
            sales = dict(enriched.get("salesComposite") or {})
            sales["units"] = sales_units
            sales["kopecks"] = period_revenue
            enriched["salesKopecks"] = period_revenue
            enriched["salesComposite"] = sales
            sales_kopecks = period_revenue
            changed = True

        profit = _int_value(enriched.get("netTotalKopecks") or enriched.get("profitKopecks"))
        margin = _float_value(enriched.get("marginPct"))
        if profit == 0 and margin is not None and margin != 0 and sales_kopecks > 0:
            enriched["netTotalKopecks"] = int(round(sales_kopecks * margin / 100))
            enriched["profitSource"] = "margin_estimate"
            changed = True

        if changed:
            enriched["historySource"] = "repricer_period_stats"
            enriched["conclusion"] = "WoW row uses repricer identity plus cached period stats for orders, sales, and margin-derived profit."
        enriched_rows.append(enriched)
    return enriched_rows


def _week_funnel_metrics_by_nm(
    *,
    organization_id: int,
    date_from: date,
    date_to: date,
    wb_token: str | None,
    progress_callback: Any | None = None,
) -> dict[str, dict[str, int | float | None]]:
    rows = _cached_funnel_rows_from_baskets_cache(_period_cache(organization_id, "baskets", date_from, date_to))
    metrics: dict[str, dict[str, int | float | None]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        nm_id = row.get("nmId")
        if nm_id is None:
            continue
        key = str(nm_id)
        bucket = metrics.setdefault(
            key,
            {
                "cartCount": 0,
                "orderCount": 0,
                "orderSumKopecks": 0,
                "buyoutCount": 0,
                "buyoutSumKopecks": 0,
                "cancelCount": 0,
                "buyoutPct": None,
            },
        )
        for field in ("cartCount", "orderCount", "orderSumKopecks", "buyoutCount", "buyoutSumKopecks", "cancelCount"):
            bucket[field] = _int_value(bucket.get(field)) + _int_value(row.get(field))
    for bucket in metrics.values():
        order_count = _int_value(bucket.get("orderCount"))
        buyout_count = _int_value(bucket.get("buyoutCount"))
        bucket["buyoutPct"] = round(buyout_count / order_count * 100, 2) if order_count > 0 else None
    return metrics


def _week_rows_with_funnel_metrics(rows: list[dict[str, Any]], funnel_metrics: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    if not rows or not funnel_metrics:
        return rows
    enriched_rows: list[dict[str, Any]] = []
    for row in rows:
        nm_key = str(row.get("nmId") or "").strip()
        metrics = funnel_metrics.get(nm_key) if nm_key else None
        if not isinstance(metrics, dict):
            enriched_rows.append(row)
            continue
        enriched = dict(row)
        cart_count = _int_value(metrics.get("cartCount"))
        order_count = _int_value(metrics.get("orderCount"))
        order_sum = _int_value(metrics.get("orderSumKopecks"))
        buyout_count = _int_value(metrics.get("buyoutCount"))
        buyout_sum = _int_value(metrics.get("buyoutSumKopecks"))
        if cart_count > 0:
            enriched["baskets"] = cart_count
            enriched["cartCount"] = cart_count
        if order_count > 0 or order_sum > 0:
            enriched["ordersUnits"] = order_count
            enriched["ordersKopecks"] = order_sum
            enriched["ordersComposite"] = {"units": order_count, "kopecks": order_sum}
        if buyout_count > 0 or buyout_sum > 0:
            enriched["salesUnits"] = buyout_count
            enriched["salesKopecks"] = buyout_sum
            enriched["salesComposite"] = {"units": buyout_count, "kopecks": buyout_sum}
        if metrics.get("buyoutPct") is not None:
            enriched["buyoutPct"] = metrics.get("buyoutPct")
        enriched["historySource"] = "wb_sales_funnel"
        enriched["conclusion"] = "Заказы, выкупы и корзины взяты из WB Sales Funnel за текущий и предыдущий периоды."
        enriched_rows.append(enriched)
    return enriched_rows


def _build_week_over_week_abc_report(
    *,
    request: Request,
    actor: Any,
    date_from: date,
    date_to: date,
    date_range: dict[str, str],
    group_by: ReportGroupBy,
    finance_allowed: bool,
) -> dict[str, Any]:
    previous_from, previous_to = _previous_period(date_from, date_to)
    diagnostics: dict[str, Any] = {
        "mode": "abc_direct",
        "reportId": "week-over-week",
        "requestedRange": date_range,
        "previousRange": {"from": previous_from.isoformat(), "to": previous_to.isoformat()},
        "requests": [],
    }

    def add_step(stage: str, endpoint: str, start: date, end: date, rows: int, source_status: str | None = None) -> None:
        step: dict[str, Any] = {
            "stage": stage,
            "endpoint": endpoint,
            "dateFrom": start.isoformat(),
            "dateTo": end.isoformat(),
            "status": "ok",
            "rows": rows,
        }
        if source_status:
            step["sourceStatus"] = source_status
        diagnostics["requests"].append(step)

    current_payload = build_abc_report(
        date_from=date_from,
        date_to=date_to,
        group_by=group_by,
        filters="",
        finance_allowed=finance_allowed,
        organization_id=actor.organization_id,
    )
    previous_payload = build_abc_report(
        date_from=previous_from,
        date_to=previous_to,
        group_by=group_by,
        filters="",
        finance_allowed=finance_allowed,
        organization_id=actor.organization_id,
    )
    current_rows = _abc_payload_rows(current_payload)
    previous_rows = _abc_payload_rows(previous_payload)
    add_step("current_abc", "build_abc_report", date_from, date_to, len(current_rows), getattr(current_payload, "sourceStatus", None))
    add_step("previous_abc", "build_abc_report", previous_from, previous_to, len(previous_rows), getattr(previous_payload, "sourceStatus", None))

    used_repricer_fallback = False
    if not current_rows or not previous_rows:
        wb_token = _actor_wb_token(actor)
        if not current_rows:
            repricer_rows = _repricer_rows_for_abc_report(
                request=request,
                actor=actor,
                wb_token=wb_token,
                date_from=date_from,
                date_to=date_to,
            )
            current_rows = _repricer_rows_to_abc_rows(repricer_rows)
            used_repricer_fallback = bool(current_rows)
            add_step("current_repricer", "_repricer_rows_for_abc_report", date_from, date_to, len(current_rows), "fresh" if current_rows else "empty")
        if not previous_rows:
            repricer_rows = _repricer_rows_for_abc_report(
                request=request,
                actor=actor,
                wb_token=wb_token,
                date_from=previous_from,
                date_to=previous_to,
            )
            previous_rows = _repricer_rows_to_abc_rows(repricer_rows)
            used_repricer_fallback = used_repricer_fallback or bool(previous_rows)
            add_step("previous_repricer", "_repricer_rows_for_abc_report", previous_from, previous_to, len(previous_rows), "fresh" if previous_rows else "empty")

    current_period_stats = _week_period_stats_aggregates(actor.organization_id, date_from, date_to)
    previous_period_stats = _week_period_stats_aggregates(actor.organization_id, previous_from, previous_to)
    current_rows = _week_rows_with_period_stats(current_rows, current_period_stats)
    previous_rows = _week_rows_with_period_stats(previous_rows, previous_period_stats)
    add_step("current_period_stats", "period_stats_cache", date_from, date_to, len(current_period_stats), "cached" if current_period_stats else "empty")
    add_step("previous_period_stats", "period_stats_cache", previous_from, previous_to, len(previous_period_stats), "cached" if previous_period_stats else "empty")

    source_status = "fresh" if used_repricer_fallback and current_rows else str(getattr(current_payload, "sourceStatus", None) or "partial")
    rows = _week_rows_from_abc_rows(current_rows, previous_rows)
    payload = _week_over_week_shell(date_range, rows, source_status=source_status)
    payload["headline"] = "WoW-отчёт построен прямым запросом из того же источника, что ABC, без ожидания фоновой сборки."
    payload["cache"] = {
        "status": "live-abc-fallback" if used_repricer_fallback else "live-abc",
        "requestedRange": date_range,
        "previousRange": {"from": previous_from.isoformat(), "to": previous_to.isoformat()},
    }
    payload["diagnostics"] = diagnostics
    payload["sourceStatus"] = source_status
    payload["confidence"] = "medium" if used_repricer_fallback else getattr(current_payload, "confidence", None)
    payload["reportJob"] = {
        "state": "completed",
        "reportId": "week-over-week",
        "dateFrom": date_from.isoformat(),
        "dateTo": date_to.isoformat(),
        "groupBy": group_by,
        "stage": "abc_direct",
        "label": "WoW построен прямым GET по ABC-источнику",
        "percent": 100,
        "finishedAt": _utc_now_iso(),
    }
    return payload


def _build_week_over_week_fallback_report(
    *,
    request: Request,
    actor: Any,
    date_from: date,
    date_to: date,
    date_range: dict[str, str],
    finance_allowed: bool,
    wb_token: str | None,
) -> dict[str, Any]:
    previous_from, previous_to = _previous_period(date_from, date_to)
    diagnostics: dict[str, Any] = {
        "mode": "live",
        "reportId": "week-over-week",
        "requestedRange": date_range,
        "requests": [],
    }

    def add_step(stage: str, endpoint: str, start: date, end: date) -> dict[str, Any]:
        step = {
            "stage": stage,
            "endpoint": endpoint,
            "dateFrom": start.isoformat(),
            "dateTo": end.isoformat(),
            "status": "started",
        }
        diagnostics["requests"].append(step)
        return step

    def finish_snapshot_step(step: dict[str, Any], snapshot: Any) -> None:
        step["status"] = "ok"
        step["sourceStatus"] = getattr(snapshot, "source_status", None)
        step["rows"] = {
            "orders": len(getattr(snapshot, "orders", []) or []),
            "sales": len(getattr(snapshot, "sales", []) or []),
            "stocks": len(getattr(snapshot, "stocks", []) or []),
        }

    def finish_ads_step(step: dict[str, Any], snapshot: Any) -> None:
        step["status"] = "ok"
        step["rows"] = {"ads": len(getattr(snapshot, "rows", []) or [])}

    current_step = add_step("current_sources_cache", "repricer_source_cache", date_from, date_to)
    current_snapshot = build_cached_wb_reports_sources_snapshot(organization_id=actor.organization_id, date_from=date_from, date_to=date_to)
    finish_snapshot_step(current_step, current_snapshot)
    previous_step = add_step("previous_sources_cache", "repricer_source_cache", previous_from, previous_to)
    previous_snapshot = build_cached_wb_reports_sources_snapshot(organization_id=actor.organization_id, date_from=previous_from, date_to=previous_to)
    finish_snapshot_step(previous_step, previous_snapshot)
    current_ads_step = add_step("current_ads_cache", "repricer_ads_cache", date_from, date_to)
    current_ads = build_cached_ads_attribution_snapshot(organization_id=actor.organization_id, date_from=date_from, date_to=date_to, group_by="sku")
    finish_ads_step(current_ads_step, current_ads)
    previous_ads_step = add_step("previous_ads_cache", "repricer_ads_cache", previous_from, previous_to)
    previous_ads = build_cached_ads_attribution_snapshot(organization_id=actor.organization_id, date_from=previous_from, date_to=previous_to, group_by="sku")
    finish_ads_step(previous_ads_step, previous_ads)
    payload = _build_week_over_week_payload(
        date_range,
        current_snapshot,
        previous_snapshot,
        current_ads,
        previous_ads,
        organization_id=actor.organization_id,
    )
    payload["cache"] = {"status": "cache-only", "requestedRange": date_range}
    payload["diagnostics"] = diagnostics
    payload["reportJob"] = {
        "state": "completed",
        "reportId": "week-over-week",
        "dateFrom": date_from.isoformat(),
        "dateTo": date_to.isoformat(),
        "groupBy": "sku",
        "stage": "cache_only",
        "label": "WoW построен из repricer source cache для выбранного диапазона",
        "percent": 100,
        "finishedAt": _utc_now_iso(),
    }
    return payload


def _estimated_export_rows(
    report_id: ReportId,
    date_from: date,
    date_to: date,
    finance_allowed: bool,
    wb_token: str | None = None,
    organization_id: int | None = None,
) -> int:
    if report_id == "digest":
        return 1
    if report_id == "stock":
        if organization_id is None:
            return 0
        source_snapshot = build_cached_wb_reports_sources_snapshot(organization_id=organization_id, date_from=date_from, date_to=date_to)
        return len(source_snapshot.stocks)
    if report_id == "week-over-week":
        if organization_id is None:
            return 0
        source_snapshot = build_cached_wb_reports_sources_snapshot(organization_id=organization_id, date_from=date_from, date_to=date_to)
        return len(_orders_sales_by_nm(source_snapshot))
    if report_id == "ads":
        if organization_id is None:
            return 0
        ads_snapshot = build_cached_ads_attribution_snapshot(organization_id=organization_id, date_from=date_from, date_to=date_to, group_by="campaign")
        return len(ads_snapshot.rows)
    if report_id == "rnp":
        return len(
            build_rnp_report(
                date_from=date_from,
                date_to=date_to,
                group_by="sku",
                finance_allowed=finance_allowed,
                organization_id=organization_id or 1,
                wb_token=wb_token,
            ).rows
        )
    if report_id == "abc":
        return len(
            build_abc_report(
                date_from=date_from,
                date_to=date_to,
                group_by="sku",
                filters="",
                finance_allowed=finance_allowed,
                organization_id=organization_id,
            ).rows
        )
    if report_id == "pnl":
        return len(
            build_pnl_report(
                date_from=date_from,
                date_to=date_to,
                group_by="sku",
                requested_state="preliminary",
                finance_allowed=finance_allowed,
                organization_id=organization_id,
                wb_token=None,
            ).rows
        )
    return 0


def _repricer_rows_for_abc_report(
    *,
    request: Request,
    actor: Any,
    wb_token: str | None,
    date_from: date,
    date_to: date,
) -> list[dict[str, Any]]:
    from app.routers.wb_repricer_bff import _hydrate_org_repricer_state, _list_repricer_skus_for_request

    _hydrate_org_repricer_state(request)
    scenario = str(request.query_params.get("scenario") or "complete")
    period_days = max(1, min(90, (date_to - date_from).days + 1))
    return _list_repricer_skus_for_request(
        request,
        scenario,
        actor=actor,
        wb_token=wb_token,
        include_promotions=False,
        include_content=False,
        period_days=period_days,
        date_from=date_from,
        date_to=date_to,
        max_items=None,
        sort_by_demand=True,
    )


def _repricer_row_to_abc_row(row: dict[str, Any]) -> dict[str, Any]:
    meta = row.get("meta") if isinstance(row.get("meta"), dict) else {}
    analytics = row.get("analytics") if isinstance(row.get("analytics"), dict) else {}
    settings = row.get("settings") if isinstance(row.get("settings"), dict) else {}
    orders_units = _int_value(analytics.get("ordersUnits"))
    orders_kopecks = _int_value(analytics.get("revenueKopecks"))
    sales_units = _int_value(analytics.get("salesUnits"))
    sales_kopecks = _int_value(analytics.get("sellerRevenueKopecks") or analytics.get("revenueKopecks"))
    net_profit_kopecks = _int_value(analytics.get("netProfitKopecks") or analytics.get("factNetProfitKopecks"))
    return {
        "sku": str(meta.get("articleId") or meta.get("vendorCode") or row.get("articleId") or ""),
        "nmId": meta.get("nmId"),
        "name": meta.get("name") or meta.get("title"),
        "photoUrl": meta.get("photoUrl") or meta.get("imageUrl") or _extract_wb_media_url(meta, _int_value(meta.get("nmId"))),
        "productStatus": analytics.get("productStatus") or meta.get("status") or "unknown",
        "manager": meta.get("managerId") or settings.get("managerId"),
        "brand": meta.get("brand"),
        "category": meta.get("subject") or meta.get("category"),
        "abcCode": analytics.get("abcCode") or "CC",
        "priceWithSppKopecks": _int_value(
            analytics.get("avgPriceWithSppKopecks")
            or analytics.get("accountedBuyerPriceKopecks")
            or analytics.get("buyerPriceWithWalletKopecks")
        ),
        "ordersComposite": {"units": orders_units, "kopecks": orders_kopecks, "deltaPct": None},
        "salesComposite": {"units": sales_units, "kopecks": sales_kopecks, "deltaPct": None},
        "netTotalKopecks": net_profit_kopecks,
        "marginPct": _float_value(analytics.get("marginPct")),
        "adSpendKopecks": _int_value(analytics.get("adSpendKopecks")),
        "wbStockUnits": _int_value(analytics.get("wbStockUnits")),
        "buyoutPct": _float_value(analytics.get("buyoutPct")),
        "baskets": _int_value(analytics.get("baskets") if analytics.get("baskets") is not None else meta.get("basketsLast7d")),
        "logisticsCostPct": _float_value(analytics.get("logisticsCostPct")),
        "commissionCostPct": _float_value(analytics.get("commissionDisplayPct") or analytics.get("wbCommissionPct")),
        "storageCostPct": _float_value(analytics.get("storageCostPct")),
        "financeState": analytics.get("financeState"),
        "periodStatsState": analytics.get("periodStatsState"),
        "basketsState": analytics.get("basketsState"),
    }


def _abc_filtered_summary_from_rows(rows: list[dict[str, Any]], *, source_status: str, confidence: str) -> dict[str, Any]:
    sales_kopecks = sum(_int_value((row.get("salesComposite") or {}).get("kopecks")) for row in rows if isinstance(row, dict))
    profit_kopecks = sum(_int_value(row.get("netTotalKopecks") or row.get("profitKopecks")) for row in rows if isinstance(row, dict))
    margin_pct = round(profit_kopecks / sales_kopecks * 100, 2) if sales_kopecks > 0 else None
    return {
        "filterHash": "repricer-list",
        "skuCount": len(rows),
        "locomotiveCount": sum(1 for row in rows if str(row.get("productStatus")) == "locomotive"),
        "ordersCount": sum(_int_value((row.get("ordersComposite") or {}).get("units")) for row in rows if isinstance(row, dict)),
        "ordersKopecks": sum(_int_value((row.get("ordersComposite") or {}).get("kopecks")) for row in rows if isinstance(row, dict)),
        "profitKopecks": profit_kopecks,
        "marginPct": margin_pct,
        "adSpendKopecks": sum(_int_value(row.get("adSpendKopecks")) for row in rows if isinstance(row, dict)),
        "sourceStatus": source_status,
        "confidence": confidence,
    }


def _abc_row_cart_count(row: dict[str, Any]) -> int:
    return max(
        0,
        _int_value(
            row.get("baskets")
            or row.get("cartCount")
            or row.get("cartAdds")
            or row.get("addToCart")
            or row.get("addToCartCount")
            or row.get("basketCount")
        ),
    )


def _normalize_abc_report_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        baskets = _abc_row_cart_count(item)
        item["baskets"] = baskets
        item["cartCount"] = baskets
        if item.get("basketsDeltaPct") is None and item.get("cartCountDeltaPct") is not None:
            item["basketsDeltaPct"] = item.get("cartCountDeltaPct")
        if item.get("cartCountDeltaPct") is None and item.get("basketsDeltaPct") is not None:
            item["cartCountDeltaPct"] = item.get("basketsDeltaPct")
        normalized.append(item)
    return normalized


def _map_abc_to_report_response(payload: Any, date_range: dict[str, str]) -> dict[str, Any]:
    abc_rows = _normalize_abc_report_rows([row for row in getattr(payload, "rows", []) or [] if isinstance(row, dict)])
    source_status = getattr(payload, "sourceStatus", "partial")
    confidence = getattr(payload, "confidence", "unknown")
    blocker_ids = list(getattr(payload, "blockerIds", []) or [])
    summary_model = getattr(payload, "filteredSummary", None)
    filtered_summary = (
        summary_model.model_dump(mode="json")
        if hasattr(summary_model, "model_dump")
        else dict(summary_model or {})
    )
    if abc_rows and not _abc_rows_have_financial_activity(abc_rows):
        source_status = "partial"
        confidence = "low"
        if "WB_ABC_PERIOD_ACTIVITY_EMPTY" not in blocker_ids:
            blocker_ids.append("WB_ABC_PERIOD_ACTIVITY_EMPTY")
        filtered_summary["sourceStatus"] = source_status
        filtered_summary["confidence"] = confidence
    group_by = getattr(payload, "groupBy", "sku")
    return {
        "cacheVersion": ABC_REPORT_PAYLOAD_VERSION,
        "meta": _meta("abc", "ABC-анализ", "ABC and SKU profitability view.", "operational", source_status),
        "headline": "ABC summary for selected period.",
        "filters": {"dateRange": date_range, "groupBy": group_by},
        "kpis": [
            _kpi("sku_count", "SKU", str(filtered_summary.get("skuCount") or 0)),
            _kpi("orders", "Заказы", str(filtered_summary.get("ordersCount") or 0)),
            _kpi("orders_revenue", "Выручка", str(filtered_summary.get("ordersKopecks") or 0)),
            _kpi("profit", "Прибыль", str(filtered_summary.get("profitKopecks") or 0)),
        ],
        "chart": {
            "title": "Чистая прибыль по SKU",
            "valueLabel": "Чистая прибыль, коп",
            "points": [
                {"label": str(row.get("sku") or row.get("label") or index + 1), "value": int(row.get("netTotalKopecks") or row.get("profitKopecks") or 0)}
                for index, row in enumerate(abc_rows[:20])
                if isinstance(row, dict)
            ],
        },
        "columns": [
            {"key": "sku", "label": "Артикул", "sticky": True},
            {"key": "nmId", "label": "WB"},
            {"key": "abcCode", "label": "ABC", "format": "abc", "align": "center"},
            {"key": "productStatus", "label": "Статус"},
            {"key": "manager", "label": "Менеджер"},
            {"key": "brand", "label": "Бренд"},
            {"key": "category", "label": "Категория"},
            {"key": "clicks", "label": "Переходы WB", "format": "number", "align": "right"},
            {"key": "baskets", "label": "Корзины", "format": "number", "align": "right"},
            {"key": "basketsDeltaPct", "label": "Дин. корзин", "format": "percent", "align": "right"},
            {"key": "cartCrPct", "label": "CR корзин", "format": "percent", "align": "right"},
            {"key": "ordersComposite", "label": "Заказы шт/руб/динамика", "align": "right"},
            {"key": "salesComposite", "label": "Продажи шт/руб/динамика", "align": "right"},
            {"key": "netTotalKopecks", "label": "Чистая прибыль", "format": "currency", "align": "right"},
            {"key": "marginPct", "label": "Маржа", "format": "percent", "align": "right"},
            {"key": "adSpendKopecks", "label": "Реклама", "format": "currency", "align": "right"},
            {"key": "wbStockUnits", "label": "Остаток WB", "format": "number", "align": "right"},
            {"key": "logisticsCostPct", "label": "% логистика", "format": "percent", "align": "right"},
            {"key": "commissionCostPct", "label": "% комиссия", "format": "percent", "align": "right"},
            {"key": "storageCostPct", "label": "% хранение", "format": "percent", "align": "right"},
        ],
        "rows": abc_rows,
        "sourceStatus": source_status,
        "confidence": confidence,
        "blockerIds": blocker_ids,
        "sourceEvidence": [
            item.model_dump(mode="json") if hasattr(item, "model_dump") else item
            for item in (getattr(payload, "sourceEvidence", []) or [])
        ],
        "filteredSummary": filtered_summary,
    }


def _map_pnl_to_report_response(payload: Any, date_range: dict[str, str], cash_flow: dict[str, Any] | None = None) -> dict[str, Any]:
    financial_confirmation_status = "confirmed" if "WB-03" not in payload.blockerIds else "pending"
    return {
        "meta": _meta("pnl", "P&L", "Unit P&L report.", "financial", payload.sourceStatus),
        "headline": "Финансовые поля показываются с учетом finance_viewer policy.",
        "warning": None,
        "financialConfirmationStatus": financial_confirmation_status,
        "filters": {"dateRange": date_range, "groupBy": payload.groupBy},
        "kpis": [
            _kpi("revenue", "Выручка", str(payload.totals.revenueKopecks or 0)),
            _kpi("net_profit", "Чистая прибыль", str(payload.totals.netProfitKopecks or 0)),
            _kpi("margin_pct", "Маржа", f"{payload.totals.marginPct or 0}%"),
        ],
        "chart": {
            "title": "Маржа по строкам",
            "valueLabel": "Маржа, %",
            "points": [{"label": row.label, "value": row.marginPct or 0} for row in payload.rows],
        },
        "columns": [
            {"key": "label", "label": "SKU"},
            {"key": "revenueKopecks", "label": "Выручка"},
            {"key": "cogsKopecks", "label": "Себестоимость"},
            {"key": "commissionKopecks", "label": "Комиссия"},
            {"key": "logisticsKopecks", "label": "Логистика"},
            {"key": "storageKopecks", "label": "Хранение"},
            {"key": "taxKopecks", "label": "Налоги"},
            {"key": "adSpendKopecks", "label": "Реклама"},
            {"key": "netProfitKopecks", "label": "Чистая прибыль"},
            {"key": "marginPct", "label": "Маржа"},
        ],
        "rows": [row.model_dump(mode="json") for row in payload.rows],
        "cashFlow": cash_flow,
    }


def _map_cash_flow_to_expenses_response(
    cash_flow: dict[str, Any],
    date_range: dict[str, str],
    group_by: str,
    job: dict[str, Any] | None = None,
) -> dict[str, Any]:
    data = cash_flow.get("data") if isinstance(cash_flow.get("data"), dict) else {}
    source_rows = data.get("rows") if isinstance(data.get("rows"), list) else []
    period_label = f"{date_range['from']} — {date_range['to']}"
    rows = [
        {
            "id": f"cf_{index}",
            "category": str(row.get("article") or "Статья 1С"),
            "article": str(row.get("article") or "Статья 1С"),
            "amountKopecks": _int_value(row.get("amountKopecks")),
            "sourceLabel": "1С cash-flow",
            "flowType": str(row.get("type") or "expense"),
            "periodLabel": period_label,
            "approvalStatusLabel": "готово к P&L",
            "allocationBaseLabel": "статья ДДС",
            "allocationCoverageLabel": "100% статьи",
            "owner": "1С",
            "pending": "нет",
            "comment": "Операционная статья ДДС из 1С cash-flow.",
        }
        for index, row in enumerate(source_rows)
        if isinstance(row, dict) and row.get("type") == "expense" and row.get("operationalExpense") is True
    ]
    total_kopecks = data.get("totals", {}).get("operationalExpenseKopecks") if isinstance(data.get("totals"), dict) else None
    if total_kopecks is None:
        total_kopecks = sum(_int_value(row.get("amountKopecks")) for row in rows)
    source_status = "fresh" if cash_flow.get("status") == "ready" else "pending_financial"
    response = {
        "meta": _meta("expenses", "Расходы", "Статьи ДДС из 1С cash-flow для операционных расходов.", "financial", source_status),
        "headline": "Показываем операционные расходные статьи ДДС из 1С за выбранный период.",
        "warning": None if cash_flow.get("status") == "ready" else "Ждём 1С cash-flow для выбранного периода.",
        "financialConfirmationStatus": "final_financial" if cash_flow.get("status") == "ready" else "pending_financial",
        "filters": {"dateRange": date_range, "groupBy": group_by},
        "kpis": [
            _kpi("expense_rows", "Статей ДДС", str(len(rows))),
            _kpi("operational_expenses", "Опер. расходы", str(total_kopecks or 0)),
            _kpi("cash_flow_status", "1С cash-flow", str(cash_flow.get("status") or "pending")),
        ],
        "chart": {
            "title": "Операционные статьи ДДС",
            "valueLabel": "Сумма, коп",
            "points": [{"label": row["article"], "value": row["amountKopecks"]} for row in rows[:20]],
        },
        "columns": [
            {"key": "category", "label": "Статья", "sticky": True},
            {"key": "periodLabel", "label": "Период"},
            {"key": "amountKopecks", "label": "Сумма", "format": "currency", "align": "right"},
            {"key": "sourceLabel", "label": "Источник"},
            {"key": "allocationBaseLabel", "label": "База распределения"},
            {"key": "allocationCoverageLabel", "label": "Покрытие SKU"},
            {"key": "approvalStatusLabel", "label": "Статус"},
            {"key": "owner", "label": "Ответственный"},
            {"key": "pending", "label": "Действие"},
        ],
        "rows": rows,
        "cashFlow": cash_flow,
    }
    if job is not None:
        response["reportJob"] = _report_job_for_response(job)
    return response


def _map_rnp_to_report_response(payload: Any, date_range: dict[str, str]) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for row in payload.rows:
        item = row.model_dump(mode="json")
        item["ordersComposite"] = {
            "units": item.get("orderCount") or 0,
            "kopecks": item.get("orderSumKopecks") or 0,
            "deltaPct": item.get("orderCountDeltaPct"),
        }
        item["salesComposite"] = {
            "units": item.get("buyoutCount") or item.get("orderCount") or 0,
            "kopecks": item.get("buyoutSumKopecks") or item.get("orderSumKopecks") or 0,
            "deltaPct": item.get("orderSumDeltaPct"),
        }
        item["sourceStatus"] = item.get("sourceStatus") or payload.sourceStatus
        rows.append(item)

    total_open = sum(_int_value(row.get("openCount")) for row in rows)
    total_carts = sum(_row_basket_units(row) for row in rows if isinstance(row, dict))
    total_orders = sum(_int_value(row.get("orderCount")) for row in rows)
    total_order_sum = sum(_int_value(row.get("orderSumKopecks")) for row in rows)
    total_ad_spend = payload.adSpendKopecks or sum(_int_value(row.get("adSpendKopecks")) for row in rows)
    active_warehouse_keys = {
        str(warehouse.get("warehouseId") or warehouse.get("warehouseName"))
        for row in rows
        for warehouse in (row.get("warehouses") or [])
        if isinstance(warehouse, dict) and (warehouse.get("warehouseId") is not None or warehouse.get("warehouseName"))
    }
    tacoo_pct = round(total_ad_spend / total_order_sum * 100, 2) if total_order_sum > 0 else None
    return {
        "meta": _meta("rnp", "РНП", "Funnel and ad economics by SKU.", "operational", payload.sourceStatus),
        "cacheVersion": RNP_REPORT_PAYLOAD_VERSION,
        "headline": "РНП собирается из общей воронки WB Analytics и рекламной атрибуции WB Ads; органика рассчитана оценочно.",
        "comments": [comment for row in rows for comment in (row.get("comments") or [])],
        "auditEvents": [event for row in rows for event in (row.get("auditEvents") or [])],
        "filters": {"dateRange": date_range, "groupBy": payload.groupBy},
        "kpis": [
            _kpi("opens", "Открытия", str(total_open)),
            _kpi("carts", "Корзины", str(total_carts)),
            _kpi("orders", "Заказы", str(total_orders)),
            _kpi("ad_spend", "Реклама", str(total_ad_spend)),
            _kpi("tacoo", "TACoO", f"{tacoo_pct or 0}%"),
            _kpi("active_warehouses", "Активные склады", str(len(active_warehouse_keys))),
        ],
        "chart": {
            "title": "TACoO по SKU",
            "valueLabel": "TACoO, %",
            "points": [{"label": row.get("label") or row.get("sku") or str(row.get("nmId") or ""), "value": row.get("tacooPct") or 0} for row in rows],
        },
        "columns": [
            {"key": "sku", "label": "SKU"},
            {"key": "nmId", "label": "NM"},
            {"key": "productName", "label": "Товар"},
            {"key": "warehouseName", "label": "Основной склад WB"},
            {"key": "warehouses", "label": "Активные склады WB"},
            {"key": "openCount", "label": "Переходы"},
            {"key": "openCountDeltaPct", "label": "Дельта переходов"},
            {"key": "cartCount", "label": "Корзины"},
            {"key": "cartCountDeltaPct", "label": "Дельта корзин"},
            {"key": "ordersComposite", "label": "Заказы"},
            {"key": "salesComposite", "label": "Продажи"},
            {"key": "buyoutPct", "label": "Выкуп"},
            {"key": "adImpressions", "label": "Показы РК"},
            {"key": "adClicks", "label": "Клики РК"},
            {"key": "adCtrPct", "label": "CTR РК"},
            {"key": "adCartAdds", "label": "Корзины РК"},
            {"key": "adOrders", "label": "Заказы РК"},
            {"key": "adSalesKopecks", "label": "Выручка РК"},
            {"key": "adSpendKopecks", "label": "Реклама"},
            {"key": "acooPct", "label": "ACoO"},
            {"key": "tacooPct", "label": "TACoO"},
            {"key": "organicOrderCountEstimated", "label": "Орг. заказы"},
            {"key": "organicSalesKopecksEstimated", "label": "Орг. выручка"},
            {"key": "organicEstimate", "label": "Органика оценка"},
            {"key": "reasons", "label": "Причины"},
            {"key": "drrPct", "label": "ДРР legacy"},
            {"key": "roiPct", "label": "ROI"},
            {"key": "marginPct", "label": "Маржа"},
        ],
        "rows": rows,
        "formulaNotes": payload.formulaNotes,
        "sourceEvidence": [item.model_dump(mode="json") for item in payload.sourceEvidence],
        "adsSourceStatus": payload.adsSourceStatus,
        "diagnostics": payload.diagnostics,
    }


def _map_ads_to_report_response(date_range: dict[str, str], ads_snapshot: Any) -> dict[str, Any]:
    rows = []
    for row in ads_snapshot.rows:
        is_unallocated = row.attribution_level == "campaign_only"
        ad_spend_kopecks = row.ad_spend_kopecks or 0
        orders_kopecks = row.orders_kopecks or 0
        drr_pct = round((ad_spend_kopecks / orders_kopecks) * 100, 2) if orders_kopecks > 0 else None
        rows.append(
            {
                "campaignId": row.campaign_id or "unknown",
                "campaignName": row.campaign_name or f"Campaign {row.campaign_id or 'unknown'}",
                "campaignType": row.campaign_type or "unknown",
                "campaignStatus": row.campaign_status,
                "paymentType": row.payment_type,
                "campaignChangeTime": row.change_time,
                "manager": "maria",
                "sku": row.sku_id or "",
                "nmId": int(row.sku_id) if row.sku_id and row.sku_id.isdigit() else 0,
                "impressions": row.impressions or 0,
                "clicks": row.clicks or 0,
                "adClicks": row.clicks or 0,
                "ctrPct": round(((row.clicks or 0) / max(row.impressions or 1, 1)) * 100, 2),
                "baskets": row.cart_adds or 0,
                "orders": {"units": row.orders_count or 0, "kopecks": orders_kopecks, "deltaPct": 0},
                "sales": {"units": row.orders_count or 0, "kopecks": orders_kopecks, "deltaPct": 0},
                "adSpendKopecks": ad_spend_kopecks,
                "drrPct": drr_pct,
                "budgetCashKopecks": row.budget_cash_kopecks,
                "budgetNettingKopecks": row.budget_netting_kopecks,
                "budgetTotalKopecks": row.budget_total_kopecks,
                "unallocatedSpend": is_unallocated,
                "recommendation": "review" if is_unallocated else "keep",
                "recommendationStatus": "draft",
                "recommendationReason": "Расход не распределен по SKU: WB не вернул nms в fullstats." if is_unallocated else "SKU-атрибуция доступна для расчетов уровня SKU.",
                "attributionLevel": row.attribution_level,
                "confidence": row.confidence,
            }
        )
    daily_points_by_date: dict[str, int] = defaultdict(int)
    for daily_row in ads_snapshot.daily_rows:
        day = str(daily_row.get("date") or "")
        if not day:
            continue
        daily_points_by_date[day] += int(daily_row.get("adSpendKopecks") or 0)
    budget_by_campaign: dict[str, int] = {}
    for row in rows:
        campaign_id = str(row["campaignId"])
        budget = row.get("budgetTotalKopecks")
        if budget is not None:
            budget_by_campaign[campaign_id] = int(budget)
    cabinet_balance_kopecks = ads_snapshot.cabinet_balance.get("balanceKopecks") if isinstance(ads_snapshot.cabinet_balance, dict) else None
    return {
        "meta": _meta("ads", "Реклама", "Campaign-first ads report.", "operational", ads_snapshot.source_status),
        "headline": "Клики рекламы и переходы в карточку разделены; campaign_only не распределяется в SKU P&L.",
        "filters": {"dateRange": date_range, "groupBy": "campaign"},
        "kpis": [
            _kpi("ad_spend", "Расход", str(ads_snapshot.totals.get("ad_spend_kopecks", 0))),
            _kpi("orders_revenue", "Выручка", str(ads_snapshot.totals.get("orders_kopecks", 0))),
            _kpi("campaign_budget", "Бюджет РК", str(sum(budget_by_campaign.values())), "Текущий budget.total по кампаниям, не исторический остаток."),
            _kpi("cabinet_balance", "Баланс кабинета", str(cabinet_balance_kopecks or 0), "Текущий баланс рекламного кабинета, не бюджет конкретной РК."),
            _kpi("upd_rows", "Акты расходов", str(len(ads_snapshot.spend_documents))),
            _kpi("daily_rows", "Дневные строки", str(len(ads_snapshot.daily_rows))),
        ],
        "chart": {
            "title": "Расходы по дням",
            "valueLabel": "Расход, коп",
            "points": (
                [{"label": label, "value": value} for label, value in sorted(daily_points_by_date.items())]
                if daily_points_by_date
                else [{"label": row["campaignName"], "value": row["adSpendKopecks"]} for row in rows[:20]]
            ),
        },
        "columns": [
            {"key": "campaignName", "label": "РК"},
            {"key": "campaignType", "label": "Тип"},
            {"key": "campaignStatus", "label": "Статус"},
            {"key": "paymentType", "label": "Оплата"},
            {"key": "sku", "label": "SKU"},
            {"key": "nmId", "label": "WB"},
            {"key": "impressions", "label": "Показы"},
            {"key": "adClicks", "label": "Клики рекламы"},
            {"key": "ctrPct", "label": "CTR"},
            {"key": "baskets", "label": "Корзины"},
            {"key": "adSpendKopecks", "label": "Расход"},
            {"key": "budgetTotalKopecks", "label": "Бюджет РК"},
            {"key": "drrPct", "label": "ДРР"},
            {"key": "attributionLevel", "label": "Атрибуция"},
            {"key": "confidence", "label": "Уверенность"},
            {"key": "unallocatedSpend", "label": "Не распределено"},
            {"key": "recommendation", "label": "Рекомендация"},
            {"key": "recommendationReason", "label": "Основание"},
        ],
        "rows": rows,
        "sourceEvidence": [item.model_dump(mode="json") for item in ads_snapshot.source_evidence],
        "cabinetBalance": ads_snapshot.cabinet_balance,
        "spendDocuments": ads_snapshot.spend_documents,
        "dailyRows": ads_snapshot.daily_rows,
    }


def _ads_report_cache_is_usable(payload: dict[str, Any]) -> bool:
    rows = payload.get("rows")
    spend_documents = payload.get("spendDocuments")
    if not isinstance(rows, list) or not isinstance(spend_documents, list) or not spend_documents:
        return True
    spend_total = sum(int(item.get("adSpendKopecks") or 0) for item in spend_documents if isinstance(item, dict))
    if spend_total <= 0:
        return True
    row_spend_total = sum(int(item.get("adSpendKopecks") or 0) for item in rows if isinstance(item, dict))
    has_real_campaign_id = any(
        isinstance(item, dict) and str(item.get("campaignId") or "").isdigit() and int(item.get("campaignId") or 0) > 0
        for item in rows
    )
    return row_spend_total > 0 and has_real_campaign_id


def _build_ads_report_payload(
    *,
    actor: Any,
    date_from: date,
    date_to: date,
    date_range: dict[str, str],
    wb_token: str | None,
    refresh: bool = False,
) -> dict[str, Any]:
    group_by = "campaign"
    if not refresh:
        cached = get_ads_report_cache(
            organization_id=actor.organization_id,
            date_from=date_from,
            date_to=date_to,
            group_by=group_by,
        )
        if cached is not None:
            if _ads_report_cache_is_usable(cached):
                return cached

    ads_snapshot = build_cached_ads_attribution_snapshot(
        organization_id=actor.organization_id,
        date_from=date_from,
        date_to=date_to,
        group_by=group_by,
    )
    payload = _map_ads_to_report_response(date_range, ads_snapshot)
    stored = save_ads_report_cache(
        organization_id=actor.organization_id,
        date_from=date_from,
        date_to=date_to,
        group_by=group_by,
        payload=payload,
    )
    save_ads_history_snapshots(
        organization_id=actor.organization_id,
        rows=stored.get("rows") if isinstance(stored.get("rows"), list) else [],
        daily_rows=stored.get("dailyRows") if isinstance(stored.get("dailyRows"), list) else [],
        spend_documents=stored.get("spendDocuments") if isinstance(stored.get("spendDocuments"), list) else [],
    )
    return stored


def _build_digest_payload(
    date_range: dict[str, str],
    source_snapshot: Any,
    ads_snapshot: Any,
    plan_fact_payload: Any,
    funnel_snapshot: dict[str, Any] | None = None,
    report_summary: dict[str, Any] | None = None,
) -> dict[str, Any]:
    aggregates = _orders_sales_by_nm(source_snapshot)
    funnel_totals = funnel_snapshot.get("totals") if isinstance(funnel_snapshot, dict) and isinstance(funnel_snapshot.get("totals"), dict) else {}
    has_funnel = bool(funnel_totals.get("orderCount") or funnel_totals.get("buyoutCount") or funnel_totals.get("orderSumKopecks") or funnel_totals.get("buyoutSumKopecks"))
    summary = report_summary if isinstance(report_summary, dict) else {}
    total_orders = _int_value(summary["ordersUnits"]) if "ordersUnits" in summary else (_int_value(funnel_totals.get("orderCount")) if has_funnel else sum(item["orders_qty"] for item in aggregates.values()))
    total_sales_revenue = _int_value(summary["buyerRevenueKopecks"]) if "buyerRevenueKopecks" in summary else (_int_value(funnel_totals.get("buyoutSumKopecks")) if has_funnel else sum(item["sales_revenue"] for item in aggregates.values()))
    total_returns = _int_value(summary["returnsUnits"]) if "returnsUnits" in summary else (_int_value(funnel_totals.get("cancelCount")) if has_funnel else sum(item["returns_qty"] for item in aggregates.values()))
    total_ad_spend = _int_value(summary["adSpendKopecks"]) if "adSpendKopecks" in summary else ads_snapshot.totals.get("ad_spend_kopecks", 0)
    margin_profit = _int_value(summary["marginKopecks"]) if "marginKopecks" in summary else _preliminary_margin_kopecks(source_snapshot)
    margin_hint = (
        "Прибыль после себестоимости, расходов WB, рекламы и налога по настройкам SKU."
        if summary
        else "Предварительная прибыль после удержаний WB. Формула: seller payout - комиссии WB - логистика - штрафы - приемка - хранение."
    )
    stock_rows = [_stock_row_to_digest_payload(row) for row in source_snapshot.stocks]
    alerts = []
    for row in stock_rows:
        if row["availableUnits"] <= 0:
            alerts.append(
                {
                    "id": f"stock-oos-{row['nmId']}",
                    "alertType": "stock_oos",
                    "severity": "critical",
                    "entityType": "warehouse",
                    "entityId": str(row["nmId"]),
                    "title": f"{row['sku']} OOS",
                    "details": "availableUnits <= 0",
                    "createdAt": _utc_now_iso(),
                    "resolvedAt": None,
                    "route": "/wb/reports/stock",
                }
            )
    plan_fact_rows = []
    plan_fact_blockers = set(getattr(plan_fact_payload, "blockerIds", []) or [])
    if "WB-14A" not in plan_fact_blockers:
        for row in plan_fact_payload.rows:
            fact = row.factKopecks or 0
            plan = row.planKopecks or 0
            plan_fact_rows.append(
                {
                    "owner": "company" if row.ownerId == "company" else "manager",
                    "ownerId": row.ownerId,
                    "name": row.ownerLabel,
                    "planKopecks": plan,
                    "factKopecks": fact,
                    "completionPct": row.completionPct or 0,
                    "forecastKopecks": row.forecastKopecks or 0,
                    "deltaPct": round(((fact - plan) / plan * 100), 2) if plan else 0,
                    "needPerDayKopecks": row.minPerDayKopecks,
                    "status": "ok" if plan else "no_plan",
                    "factFreshness": "preliminary",
                }
            )
    funnel_weekly_balance = _build_funnel_weekly_balance(date_range, funnel_snapshot or {}) if has_funnel else None
    weekly_balance = funnel_weekly_balance or _build_weekly_balance(date_range, source_snapshot)
    period_cards = _build_period_cards(date_range, weekly_balance)
    if summary and period_cards:
        selected_orders = _int_value(summary.get("ordersUnits"))
        selected_sales = _int_value(summary.get("salesUnits"))
        period_cards[0].update(
            {
                "ordersUnits": selected_orders,
                "ordersKopecks": _int_value(funnel_totals.get("orderSumKopecks")),
                "salesUnits": selected_sales,
                "returnsUnits": _int_value(summary.get("returnsUnits")),
                "buyoutPct": round(selected_sales / selected_orders * 100, 1) if selected_orders > 0 else None,
                "revenueKopecks": _int_value(summary.get("buyerRevenueKopecks")),
            }
        )
    problem_rows = _build_digest_problem_rows(stock_rows, ads_snapshot)
    oos_count = sum(int(row.get("skuCount") or 0) for row in problem_rows if row.get("reason") == "oos_risk")
    ads_freshness_message = (
        "WB_TOKEN_REQUIRED"
        if "WB_TOKEN_REQUIRED" in (getattr(ads_snapshot, "blocker_ids", []) or [])
        else "promotion/adverts/fullstats chain"
    )
    return {
        "meta": _meta("digest", "Воронка продаж", "Сводка продаж и проблемных SKU.", "operational", source_snapshot.source_status),
        "cacheVersion": DIGEST_REPORT_PAYLOAD_VERSION,
        "headline": "Воронка продаж собрана из WB sales funnel, finance/stocks/ads и plan-fact.",
        "dateRange": date_range,
        "kpis": [
            _kpi("orders_qty", "Заказы, шт", str(total_orders), "Количество оформленных заказов WB за выбранный период по сводному кэшу репрайсера."),
            _kpi("sales_revenue", "Выкупили на сумму", str(total_sales_revenue), "Сумма выкупленных товаров по выручке покупателя за выбранный период, до удержаний WB."),
            _kpi(
                "margin_profit",
                "Марж. прибыль",
                str(margin_profit),
                margin_hint,
            ),
            _kpi("oos_risk", "OOS риск", f"{oos_count} SKU", "Товары с нулевым доступным остатком: остаток WB + возвраты от клиента = 0. Такие позиции могут перестать продаваться, пока не появится доступный остаток."),
            _kpi("ad_spend", "Реклама, коп", str(total_ad_spend), "Расходы на рекламу из финансовых удержаний WB; если их нет, используется WB Ads."),
            _kpi("returns_qty", "Возвраты, шт", str(total_returns), "Количество возвратов по продажам WB за выбранный период."),
        ],
        "planFactRows": plan_fact_rows,
        "freshness": [
            {"id": "orders", "label": "Orders", "sourceType": "operational", "state": _freshness_state(source_snapshot.source_status), "updatedAt": _utc_now_iso(), "message": "statistics orders stream"},
            {"id": "sales", "label": "Sales", "sourceType": "operational", "state": _freshness_state(source_snapshot.source_status), "updatedAt": _utc_now_iso(), "message": "statistics sales stream"},
            {"id": "stocks", "label": "Stocks", "sourceType": "operational", "state": _freshness_state(source_snapshot.source_status), "updatedAt": _utc_now_iso(), "message": "analytics warehouse_remains current snapshot"},
            {"id": "finance", "label": "Finance", "sourceType": "financial", "state": _freshness_state(source_snapshot.source_status), "updatedAt": _utc_now_iso(), "message": "realization details + finance sales reports reconciliation"},
            {"id": "ads", "label": "Ads", "sourceType": "operational", "state": _freshness_state(ads_snapshot.source_status), "updatedAt": _utc_now_iso(), "message": ads_freshness_message},
        ],
        "alerts": alerts,
        "charts": [
            {
                "title": weekly_balance["title"],
                "valueLabel": weekly_balance["valueLabel"],
                "compareLabel": weekly_balance["compareLabel"],
                "points": [
                    {
                        "label": row["label"],
                        "value": row["ordersUnits"],
                        "compareValue": row["salesUnits"],
                        "date": row["date"],
                        "ordersKopecks": row["ordersKopecks"],
                        "salesKopecks": row["salesKopecks"],
                        "returnsUnits": row["returnsUnits"],
                        "buyoutPct": row["buyoutPct"],
                    }
                    for row in weekly_balance["points"]
                ],
            }
        ],
        "weeklyBalance": weekly_balance,
        "funnelSummary": funnel_totals if has_funnel else None,
        "funnelSourceStatus": (funnel_snapshot or {}).get("status") if isinstance(funnel_snapshot, dict) else None,
        "periodCards": period_cards,
        "problemRows": problem_rows,
        "quickLinks": [
            {"title": "ABC", "description": "SKU таблица", "href": "/wb/reports/abc"},
            {"title": "РНП", "description": "Funnel + ads", "href": "/wb/reports/rnp"},
            {"title": "Реклама", "description": "Campaign attribution", "href": "/wb/reports/ads"},
            {"title": "Остатки", "description": "Склады WB", "href": "/wb/reports/stock"},
        ],
    }


def _digest_cache_key(date_from: date, date_to: date) -> str:
    return f"reports_digest_{DIGEST_REPORT_PAYLOAD_VERSION}_{date_from.isoformat()}_{date_to.isoformat()}"


def _digest_job_cache_key(date_from: date, date_to: date) -> str:
    return f"reports_digest_job_{date_from.isoformat()}_{date_to.isoformat()}"


BACKGROUND_REPORT_IDS = {"abc", "rnp", "ads", "pnl", "expenses", "stock", "week-over-week"}
ACTIVE_REPORT_JOB_STATES = {"queued", "running", "waiting_1c", "waiting_baskets_detail", "waiting_daily_detail"}
ACTIVE_REPORT_JOB_STAGES = {"queued", "refreshing_sources", "building_report"}
BACKGROUND_REPORT_JOB_STALE_AFTER = timedelta(minutes=15)
BACKGROUND_REPORT_QUEUED_STALE_AFTER = timedelta(seconds=30)
DIGEST_CACHE_TTL = timedelta(hours=24)
REPORT_PAYLOAD_CACHE_TTL = timedelta(hours=24)
ABC_REPORT_PAYLOAD_VERSION = "v9"
RNP_REPORT_PAYLOAD_VERSION = "v3"
STOCK_REPORT_PAYLOAD_VERSION = "v5"
WEEK_OVER_WEEK_REPORT_PAYLOAD_VERSION = "v2"


def _report_cache_key(report_id: str, date_from: date, date_to: date, group_by: str, source: str) -> str:
    return f"reports_payload_{report_id}_{date_from.isoformat()}_{date_to.isoformat()}_{group_by}_{source}"


def _report_job_cache_key(report_id: str, date_from: date, date_to: date, group_by: str, source: str | None = None) -> str:
    source_suffix = f"_{source}" if report_id == "pnl" and source else ""
    return f"reports_job_{report_id}_{date_from.isoformat()}_{date_to.isoformat()}_{group_by}{source_suffix}"


def _parse_report_job_timestamp(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _digest_cache_age_seconds(cache: dict[str, Any]) -> int | None:
    timestamp = (
        _parse_report_job_timestamp(cache.get("completedAt"))
        or _parse_report_job_timestamp(cache.get("fetchedAt"))
    )
    if timestamp is None:
        return None
    return max(0, int((datetime.now(timezone.utc) - timestamp).total_seconds()))


def _digest_cache_is_fresh(cache: dict[str, Any]) -> bool:
    age_seconds = _digest_cache_age_seconds(cache)
    digest = cache.get("digest") if isinstance(cache.get("digest"), dict) else None
    return (
        isinstance(digest, dict)
        and digest.get("cacheVersion") == DIGEST_REPORT_PAYLOAD_VERSION
        and age_seconds is not None
        and age_seconds <= int(DIGEST_CACHE_TTL.total_seconds())
    )


def _report_payload_cache_age_seconds(cache: dict[str, Any]) -> int | None:
    timestamp = (
        _parse_report_job_timestamp(cache.get("completedAt"))
        or _parse_report_job_timestamp(cache.get("fetchedAt"))
    )
    if timestamp is None:
        return None
    return max(0, int((datetime.now(timezone.utc) - timestamp).total_seconds()))


def _report_payload_cache_is_fresh(cache: dict[str, Any]) -> bool:
    age_seconds = _report_payload_cache_age_seconds(cache)
    return (
        isinstance(cache.get("report"), dict)
        and age_seconds is not None
        and age_seconds <= int(REPORT_PAYLOAD_CACHE_TTL.total_seconds())
    )


def _rnp_report_cache_has_funnel_signal(cache: dict[str, Any]) -> bool:
    report = cache.get("report") if isinstance(cache.get("report"), dict) else {}
    diagnostics = report.get("diagnostics") if isinstance(report.get("diagnostics"), dict) else {}
    summary = diagnostics.get("summary") if isinstance(diagnostics.get("summary"), dict) else {}
    funnel_rows = _int_value(summary.get("funnelRows"))
    if funnel_rows > 0:
        return True
    rows = report.get("rows") if isinstance(report.get("rows"), list) else []
    has_funnel_metric = any(
        isinstance(row, dict)
        and (
            _int_value(row.get("openCount")) > 0
            or _int_value(row.get("cartCount")) > 0
            or _int_value(row.get("orderCount")) > 0
            or _int_value(row.get("orderSumKopecks")) > 0
            or _int_value((row.get("ordersComposite") or {}).get("units") if isinstance(row.get("ordersComposite"), dict) else None) > 0
        )
        for row in rows
    )
    if has_funnel_metric:
        return True
    ads_rows = _int_value(summary.get("adsRows"))
    has_ads_only_rows = any(
        isinstance(row, dict)
        and (
            _int_value(row.get("adImpressions")) > 0
            or _int_value(row.get("adClicks")) > 0
            or _int_value(row.get("adOrders")) > 0
            or _int_value(row.get("adSpendKopecks")) > 0
        )
        for row in rows
    )
    return not (funnel_rows == 0 and (ads_rows > 0 or has_ads_only_rows))


def _report_payload_cache_is_usable(report_id: str, cache: dict[str, Any]) -> bool:
    if not _report_payload_cache_is_fresh(cache):
        return False
    if report_id == "rnp" and not _rnp_report_cache_has_funnel_signal(cache):
        return False
    if report_id == "rnp":
        report = cache.get("report") if isinstance(cache.get("report"), dict) else {}
        if report.get("cacheVersion") != RNP_REPORT_PAYLOAD_VERSION:
            return False
    if report_id == "stock":
        report = cache.get("report") if isinstance(cache.get("report"), dict) else {}
        if report.get("cacheVersion") != STOCK_REPORT_PAYLOAD_VERSION:
            return False
    if report_id == "abc":
        report = cache.get("report") if isinstance(cache.get("report"), dict) else {}
        if report.get("cacheVersion") != ABC_REPORT_PAYLOAD_VERSION:
            return False
    if report_id == "week-over-week":
        report = cache.get("report") if isinstance(cache.get("report"), dict) else {}
        if report.get("cacheVersion") != WEEK_OVER_WEEK_REPORT_PAYLOAD_VERSION:
            return False
        if not _week_report_has_period_activity(report):
            return False
    return True


def _report_payload_cache_meta(cache: dict[str, Any], date_range: dict[str, str], status: str | None = None) -> dict[str, Any]:
    age_seconds = _report_payload_cache_age_seconds(cache)
    fresh = age_seconds is not None and age_seconds <= int(REPORT_PAYLOAD_CACHE_TTL.total_seconds())
    return {
        "status": status or ("exact" if fresh else "stale"),
        "requestedRange": date_range,
        "fresh": fresh,
        "ageSeconds": age_seconds,
        "ttlSeconds": int(REPORT_PAYLOAD_CACHE_TTL.total_seconds()),
        "completedAt": cache.get("completedAt"),
        "fetchedAt": cache.get("fetchedAt"),
    }


def _save_exact_report_payload_cache(
    *,
    organization_id: int,
    report_id: str,
    date_from: date,
    date_to: date,
    group_by: str,
    source: str,
    report: dict[str, Any],
) -> dict[str, Any]:
    report = _normalize_report_basket_fields(report)
    cache = {
        "report": report,
        "dateFrom": date_from.isoformat(),
        "dateTo": date_to.isoformat(),
        "completedAt": _utc_now_iso(),
    }
    save_source_cache(organization_id, _report_cache_key(report_id, date_from, date_to, group_by, source), cache)
    return cache


def _basket_units_from_value(value: Any) -> int:
    if isinstance(value, dict):
        return max(
            0,
            _int_value(
                value.get("units")
                or value.get("value")
                or value.get("cartCount")
                or value.get("cartAdds")
                or value.get("baskets")
            ),
        )
    return max(0, _int_value(value))


def _row_basket_units(row: dict[str, Any]) -> int:
    for key in ("baskets", "cartCount", "cartAdds", "adCartAdds", "addToCart", "addToCartCount", "basketCount"):
        units = _basket_units_from_value(row.get(key))
        if units > 0:
            return units
    return 0


def _normalize_report_basket_row(row: dict[str, Any]) -> dict[str, Any]:
    item = dict(row)
    baskets = _row_basket_units(item)
    if baskets <= 0:
        return item
    existing_baskets = item.get("baskets")
    if isinstance(existing_baskets, dict):
        basket_payload = dict(existing_baskets)
        basket_payload.setdefault("units", baskets)
        item["baskets"] = basket_payload
    else:
        item["baskets"] = baskets
    item["cartCount"] = baskets
    item.setdefault("cartAdds", baskets)
    if item.get("basketsDeltaPct") is None and item.get("cartCountDeltaPct") is not None:
        item["basketsDeltaPct"] = item.get("cartCountDeltaPct")
    if item.get("cartCountDeltaPct") is None and item.get("basketsDeltaPct") is not None:
        item["cartCountDeltaPct"] = item.get("basketsDeltaPct")
    return item


def _normalize_report_basket_fields(report: dict[str, Any]) -> dict[str, Any]:
    result = dict(report)
    rows = result.get("rows")
    if isinstance(rows, list):
        result["rows"] = [_normalize_report_basket_row(row) if isinstance(row, dict) else row for row in rows]
    return result


def _date_range_from_report_cache(cache: dict[str, Any], fallback_from: date | None = None, fallback_to: date | None = None) -> tuple[date | None, date | None, dict[str, str] | None]:
    report = cache.get("report") if isinstance(cache.get("report"), dict) else cache.get("digest")
    filters = report.get("filters") if isinstance(report, dict) and isinstance(report.get("filters"), dict) else {}
    raw_range = filters.get("dateRange") if isinstance(filters.get("dateRange"), dict) else {}
    parsed_from = _parse_report_job_timestamp(raw_range.get("from")) if raw_range.get("from") else None
    parsed_to = _parse_report_job_timestamp(raw_range.get("to")) if raw_range.get("to") else None
    date_from = parsed_from.date() if parsed_from else None
    date_to = parsed_to.date() if parsed_to else None
    if date_from is None and cache.get("dateFrom"):
        parsed = _parse_report_job_timestamp(cache.get("dateFrom"))
        date_from = parsed.date() if parsed else None
    if date_to is None and cache.get("dateTo"):
        parsed = _parse_report_job_timestamp(cache.get("dateTo"))
        date_to = parsed.date() if parsed else None
    date_from = date_from or fallback_from
    date_to = date_to or fallback_to
    if date_from is None or date_to is None:
        return date_from, date_to, None
    return date_from, date_to, {"preset": "custom", "from": date_from.isoformat(), "to": date_to.isoformat()}


def _parse_report_payload_cache_key(source_key: str, report_id: str) -> tuple[date | None, date | None, str | None, str | None]:
    prefix = f"reports_payload_{report_id}_"
    if not source_key.startswith(prefix):
        return None, None, None, None
    tail = source_key[len(prefix):]
    match = re.match(r"(?P<date_from>\d{4}-\d{2}-\d{2})_(?P<date_to>\d{4}-\d{2}-\d{2})_(?P<group_by>[^_]+)_(?P<source>.+)$", tail)
    if not match:
        return None, None, None, None
    try:
        return (
            date.fromisoformat(match.group("date_from")),
            date.fromisoformat(match.group("date_to")),
            match.group("group_by"),
            match.group("source"),
        )
    except ValueError:
        return None, None, None, None


def _latest_report_payload_cache(
    *,
    organization_id: int,
    report_id: str,
    group_by: str,
    source: str,
    date_from: date | None = None,
    date_to: date | None = None,
) -> tuple[dict[str, Any], date, date] | None:
    requested_from = date_from
    requested_to = date_to
    if requested_from is not None and requested_to is not None:
        exact = get_source_cache(
            organization_id,
            _report_cache_key(report_id, requested_from, requested_to, group_by, source),
            slim=False,
        ) or {}
        if _report_payload_cache_is_usable(report_id, exact):
            return exact, requested_from, requested_to
    for cache in list_source_cache_by_prefix(organization_id, f"reports_payload_{report_id}_", limit=50, slim=False):
        source_key = str(cache.get("sourceKey") or "")
        fallback_from, fallback_to, cached_group_by, cached_source = _parse_report_payload_cache_key(source_key, report_id)
        if cached_group_by != group_by or cached_source != source:
            continue
        if not _report_payload_cache_is_usable(report_id, cache):
            continue
        cached_from, cached_to, _date_range = _date_range_from_report_cache(cache, fallback_from, fallback_to)
        if cached_from is None or cached_to is None:
            continue
        if requested_from is not None and cached_from != requested_from:
            continue
        if requested_to is not None and cached_to != requested_to:
            continue
        return cache, cached_from, cached_to
    return None


def _rule_metric_value(row: dict[str, Any], *keys: str) -> float | None:
    for key in keys:
        value = row.get(key)
        if isinstance(value, dict):
            value = value.get("percent", value.get("value", value.get("units")))
        parsed = _float_value(value)
        if parsed is not None:
            return parsed
    return None


def _rule_metrics_from_row(row: dict[str, Any]) -> dict[str, Any]:
    metrics: dict[str, Any] = {
        "abcCode": row.get("abcCode"),
        "ctrPct": _rule_metric_value(row, "ctrPct"),
        "crPct": _rule_metric_value(row, "crPct", "cartCrPct"),
        "cartToOrderPct": _rule_metric_value(row, "cartToOrderPct"),
        "buyoutPct": _rule_metric_value(row, "buyoutPct"),
        "marginPct": _rule_metric_value(row, "marginPct"),
        "drrPct": _rule_metric_value(row, "drrPct", "drrSalesPct", "drrOrdersPct"),
        "roiPct": _rule_metric_value(row, "roiPct", "romiPct"),
        "daysToOos": _rule_metric_value(row, "daysToOos"),
        "stockUnits": _rule_metric_value(row, "availableUnits", "wbStockUnits", "stockUnits"),
        "localizationPct": _rule_metric_value(row, "localizationPct"),
        "impressions": _rule_metric_value(row, "impressions", "views"),
    }
    if metrics["cartToOrderPct"] is None:
        orders = row.get("orders")
        baskets = row.get("baskets") or row.get("cartCount") or row.get("cartAdds") or row.get("adCartAdds")
        orders_units = _rule_metric_value({"value": orders}, "value")
        baskets_units = _rule_metric_value({"value": baskets}, "value")
        if orders_units is not None and baskets_units and baskets_units > 0:
            metrics["cartToOrderPct"] = orders_units / baskets_units * 100
    return metrics


def _apply_report_rules_to_payload(payload: dict[str, Any], organization_id: int) -> dict[str, Any]:
    profile = load_active_profile(organization_id)
    result = _normalize_report_basket_fields(payload)
    rows = result.get("rows") if isinstance(result.get("rows"), list) else []
    decorated: list[Any] = []
    oos_count = 0
    for raw in rows:
        if not isinstance(raw, dict):
            decorated.append(raw)
            continue
        row = dict(raw)
        evaluation = evaluate_metrics(_rule_metrics_from_row(row), profile).model_dump(mode="json")
        row["ruleEvaluation"] = evaluation
        row["ruleStatus"] = {"unknown": "Недостаточно данных", "risk": "Риск", "opportunity": "Возможность", "normal": "Норма"}.get(evaluation["status"], evaluation["status"])
        row["ruleReasons"] = " · ".join(evaluation.get("statusReasons") or []) or "Пороговых рекомендаций нет"
        row["ruleRecommendation"] = ", ".join(
            f"{item.get('type')} · черновик" for item in evaluation.get("recommendedActions", []) if isinstance(item, dict)
        ) or "—"
        reasons = {item.get("reason") for item in evaluation.get("recommendedActions", []) if isinstance(item, dict)}
        if "oos" in reasons:
            oos_count += 1
        if "loss" in reasons:
            row["productStatus"] = "loss"
        elif "oos" in reasons:
            row["productStatus"] = "OOS риск"
        elif "highDrr" in reasons:
            row["productStatus"] = "выше порога ДРР"
        elif reasons & {"badCr", "cWeak"}:
            row["productStatus"] = "неликвид"
        elif "aaGood" in reasons:
            row["productStatus"] = "локомотив"
        decorated.append(row)
    result["rows"] = decorated
    result["rulesProfileVersion"] = profile.version
    result["rulesProfile"] = {"name": profile.name, "preset": profile.preset}
    meta = result.get("meta")
    if isinstance(meta, dict):
        result["meta"] = {**meta, "rulesProfileVersion": profile.version}
    kpis = result.get("kpis")
    if isinstance(kpis, list):
        if not any(isinstance(item, dict) and item.get("id") == "rules_profile" for item in kpis):
            kpis.append({"id": "rules_profile", "label": "Правила", "value": f"v{profile.version}", "hint": f"{profile.name} · {profile.preset}"})
        for item in kpis:
            if isinstance(item, dict) and item.get("id") == "oos_risk":
                item["value"] = str(oos_count)
    columns = result.get("columns")
    if isinstance(columns, list) and rows:
        existing = {item.get("key") for item in columns if isinstance(item, dict)}
        if "ruleStatus" not in existing:
            columns.extend([
                {"key": "ruleStatus", "label": "Статус правил"},
                {"key": "ruleReasons", "label": "Причина"},
                {"key": "ruleRecommendation", "label": "Рекомендация"},
            ])
    cards = result.get("managementCards")
    if isinstance(cards, list):
        for card in cards:
            if isinstance(card, dict) and card.get("chip") == "OOS риск":
                card["value"] = f"{oos_count} SKU"
                card["meta"] = (
                    f"до {profile.config.qualityBands.daysToOos.warnBelow:g} дней покрытия "
                    f"или меньше {profile.config.qualityBands.stockUnits.criticalBelow:g} доступных единиц"
                )
                card["className"] = "danger" if oos_count else ""
    return result


def _completed_report_job_from_cache(
    report_id: str,
    date_from: date,
    date_to: date,
    group_by: str,
    cache: dict[str, Any],
    current_job: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        **(current_job or {}),
        "state": "completed",
        "reportId": report_id,
        "dateFrom": date_from.isoformat(),
        "dateTo": date_to.isoformat(),
        "groupBy": group_by,
        "stage": "cache",
        "label": f"Отчёт взят из готового кэша выбранного периода {date_from.isoformat()} — {date_to.isoformat()}",
        "percent": 100,
        "updatedAt": _utc_now_iso(),
        "reused": True,
        "cacheFresh": True,
        "cacheAgeSeconds": _report_payload_cache_age_seconds(cache),
        "cacheTtlSeconds": int(REPORT_PAYLOAD_CACHE_TTL.total_seconds()),
    }


def _report_job_is_reusable(job: dict[str, Any]) -> bool:
    state = job.get("state")
    if state in {"waiting_1c", "waiting_baskets_detail", "waiting_daily_detail"}:
        return True
    if state not in {"queued", "running"}:
        return False
    heartbeat = (
        _parse_report_job_timestamp(job.get("updatedAt"))
        or _parse_report_job_timestamp(job.get("queuedAt"))
        or _parse_report_job_timestamp(job.get("startedAt"))
    )
    if heartbeat is None:
        return False
    if state == "queued":
        return datetime.now(timezone.utc) - heartbeat <= BACKGROUND_REPORT_QUEUED_STALE_AFTER
    stale_after = BACKGROUND_REPORT_JOB_STALE_AFTER
    if job.get("reportId") == "week-over-week" and str(job.get("stage") or "").startswith("week-over-week-ads"):
        stale_after = timedelta(minutes=5)
    return datetime.now(timezone.utc) - heartbeat <= stale_after


def _report_job_is_active_refresh(job: dict[str, Any]) -> bool:
    state = str(job.get("state") or "")
    stage = str(job.get("stage") or "")
    return state in ACTIVE_REPORT_JOB_STATES and stage in ACTIVE_REPORT_JOB_STAGES and _report_job_is_reusable(job)


def _report_job_is_finished_refresh(job: dict[str, Any]) -> bool:
    state = str(job.get("state") or "")
    stage = str(job.get("stage") or "")
    kind = str(job.get("kind") or "")
    return state in {"completed", "failed"} and stage in {"completed", "failed"} and kind == "report_source_refresh"


def _report_job_for_response(job: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(job, dict) or not job:
        return job
    state = job.get("state")
    if state not in {"queued", "running"} or _report_job_is_reusable(job):
        return job
    return {
        **job,
        "state": "stale",
        "previousState": state,
        "staleAfterSeconds": int(BACKGROUND_REPORT_JOB_STALE_AFTER.total_seconds()),
        "label": f"Задача зависла: {job.get('label') or 'нет свежего heartbeat'}",
    }


def _empty_background_report(report_id: ReportId, date_range: dict[str, str], group_by: str, job: dict[str, Any]) -> dict[str, Any]:
    job = _report_job_for_response(job)
    return {
        "meta": _meta(report_id, report_id, "Отчёт ожидает фоновое обновление.", "operational", "stale"),
        "headline": "Отчёт ещё не собран для выбранного периода.",
        "filters": {"dateRange": date_range, "groupBy": group_by},
        "kpis": [], "chart": {"title": "Нет данных", "valueLabel": "-", "points": []}, "columns": [], "rows": [],
        "cache": {"status": "missing", "requestedRange": date_range}, "reportJob": job,
    }


def _digest_plan_cache_key(month: str) -> str:
    return f"reports_digest_plan_{month}"


def _apply_digest_plan(payload: dict[str, Any], plan: dict[str, Any]) -> None:
    company = plan.get("company") if isinstance(plan.get("company"), dict) else {}
    managers = plan.get("managers") if isinstance(plan.get("managers"), list) else []
    def kpi_value(kpi_id: str) -> int | None:
        item = next((candidate for candidate in payload.get("kpis", []) if candidate.get("id") == kpi_id), None)
        if not isinstance(item, dict):
            return None
        try:
            return int(item.get("value"))
        except (TypeError, ValueError):
            return None

    margin_fact = kpi_value("margin_profit")
    revenue_fact = kpi_value("sales_revenue")
    rows: list[dict[str, Any]] = []
    manager_count = max(len([item for item in managers if isinstance(item, dict)]), 1)
    month = str(plan.get("month") or "")
    try:
        plan_month = datetime.strptime(f"{month}-01", "%Y-%m-%d").date()
        days_in_month = ((plan_month.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)).day
        as_of = date.fromisoformat(str((payload.get("dateRange") or {}).get("to") or ""))
        elapsed_days = min(days_in_month, max(1, as_of.day if as_of.year == plan_month.year and as_of.month == plan_month.month else days_in_month))
    except ValueError:
        days_in_month = 30
        elapsed_days = 1

    def row(owner_id: str, name: str, values: dict[str, Any], margin_fact_value: int | None, revenue_fact_value: int | None) -> dict[str, Any]:
        margin_plan = int(values.get("marginPlanKopecks") or 0)
        revenue_plan = int(values.get("revenuePlanKopecks") or 0)
        metric_label = "Маржа" if margin_plan else "Выручка"
        plan_value = margin_plan or revenue_plan
        fact = margin_fact_value if margin_plan else revenue_fact_value
        forecast = round(fact / elapsed_days * days_in_month) if fact is not None else None
        remaining_days = max(1, days_in_month - elapsed_days)
        return {"owner": "company" if owner_id == "company" else "manager", "ownerId": owner_id, "name": name, "metricLabel": metric_label, "planKopecks": plan_value or None, "factKopecks": fact, "completionPct": round(fact / plan_value * 100, 1) if plan_value and fact is not None else None, "forecastKopecks": forecast, "needPerDayKopecks": max(0, plan_value - fact) // remaining_days if plan_value and fact is not None else None, "status": "no_plan" if not plan_value else "no_fact" if fact is None else "ok" if forecast is not None and forecast >= plan_value else "risk", "factFreshness": "preliminary", "revenuePlanKopecks": revenue_plan or None, "revenueFactKopecks": revenue_fact_value}
    rows.append(row("company", "Компания", company, margin_fact, revenue_fact))
    active = [item for item in managers if isinstance(item, dict)]
    for index, manager in enumerate(active):
        manager_margin_fact = margin_fact // manager_count if margin_fact is not None else None
        manager_revenue_fact = revenue_fact // manager_count if revenue_fact is not None else None
        rows.append(row(str(manager.get("id") or f"manager-{index}"), str(manager.get("name") or "Менеджер"), manager, manager_margin_fact, manager_revenue_fact))
    payload["planFactRows"] = rows


def _empty_digest_payload(date_range: dict[str, str]) -> dict[str, Any]:
    return {
        "meta": _meta("digest", "WB-витрина", "Дайджест ожидает фоновое обновление.", "operational", "stale"),
        "headline": "Дайджест ещё не собран для выбранного периода.", "dateRange": date_range,
        "kpis": [], "planFactRows": [], "freshness": [], "alerts": [], "charts": [], "periodCards": [], "problemRows": [], "quickLinks": [],
    }


def _build_digest_ads_snapshot(*, organization_id: int, date_from: date, date_to: date, wb_token: str | None) -> AdsAttributionSnapshot:
    return build_cached_ads_attribution_snapshot(
        organization_id=organization_id,
        date_from=date_from,
        date_to=date_to,
        group_by="sku",
    )


@router.get("/api/wb/reports/digest")
def get_reports_digest(
    request: Request,
    preset: str = Query(default="7d"),
    from_: str | None = Query(default=None, alias="from"),
    to: str | None = Query(default=None),
) -> dict[str, Any]:
    actor = actor_from_request(request)
    assert_permission_or_audit(
        actor=actor,
        permission="settings:read",
        action="reports.bff.digest.get",
        object_type="wb_report",
        object_id="digest",
        reason="actor cannot read digest report",
    )
    date_from, date_to, date_range = _range_from_preset(preset, from_, to)
    cached = get_source_cache(actor.organization_id, _digest_cache_key(date_from, date_to), slim=False) or {}
    digest = cached.get("digest") if isinstance(cached.get("digest"), dict) else None
    if isinstance(digest, dict) and digest.get("cacheVersion") != DIGEST_REPORT_PAYLOAD_VERSION:
        digest = None
    cache_status = "exact" if digest else "missing"
    selected_cache = cached if digest else {}
    if digest is None:
        latest = get_source_cache(actor.organization_id, "reports_digest_latest", slim=False) or {}
        digest = latest.get("digest") if isinstance(latest.get("digest"), dict) else None
        if isinstance(digest, dict) and digest.get("cacheVersion") != DIGEST_REPORT_PAYLOAD_VERSION:
            digest = None
        cache_status = "fallback" if digest else "missing"
        selected_cache = latest if digest else {}
    payload = dict(digest or _empty_digest_payload(date_range))
    plan = get_source_cache(actor.organization_id, _digest_plan_cache_key(date_to.strftime("%Y-%m")), slim=False) or {}
    if isinstance(plan, dict) and plan:
        _apply_digest_plan(payload, plan)
    job = get_source_cache(actor.organization_id, _digest_job_cache_key(date_from, date_to), slim=False) or {"state": "idle"}
    cache_age_seconds = _digest_cache_age_seconds(selected_cache)
    cache_fresh = (
        cache_status == "exact"
        and payload.get("cacheVersion") == DIGEST_REPORT_PAYLOAD_VERSION
        and cache_age_seconds is not None
        and cache_age_seconds <= int(DIGEST_CACHE_TTL.total_seconds())
    )
    if cache_status == "exact" and cache_fresh:
        job = {
            **job,
            "state": "completed",
            "stage": "cache",
            "label": "Воронка продаж взята из кэша за последние 24 часа",
            "percent": 100,
            "dateFrom": date_from.isoformat(),
            "dateTo": date_to.isoformat(),
            "updatedAt": _utc_now_iso(),
            "reused": True,
            "cacheFresh": True,
            "cacheAgeSeconds": cache_age_seconds,
            "cacheTtlSeconds": int(DIGEST_CACHE_TTL.total_seconds()),
        }
        save_source_cache(actor.organization_id, _digest_job_cache_key(date_from, date_to), job)
    payload["cache"] = {
        "status": cache_status,
        "requestedRange": date_range,
        "fresh": cache_fresh,
        "ageSeconds": cache_age_seconds,
        "ttlSeconds": int(DIGEST_CACHE_TTL.total_seconds()),
        "completedAt": selected_cache.get("completedAt"),
        "fetchedAt": selected_cache.get("fetchedAt"),
    }
    payload["digestJob"] = job
    record_audit_event(
        actor=actor,
        action="reports.bff.digest.get",
        object_type="wb_report",
        object_id="digest",
        before_state=None,
        after_state={"sourceStatus": payload["meta"]["freshnessState"], "cache": cache_status},
        reason="read bff digest report",
        approval_ref=None,
        evidence_refs=["WB-03", "WB-11_CLOSED_2026-05-29", "WB-02_CLOSED_2026-06-01"],
    )
    return payload


def _digest_plan_managers(organization_id: int) -> dict[str, str]:
    """Managers are organization users, never presentation-only frontend names."""
    return {
        user.userId: user.fullName
        for user in list_team_users(organization_id)
        if user.isActive and user.permissionProfile not in {"viewer", "admin"}
    }


def _normalize_digest_plan(raw: dict[str, Any], *, allowed_managers: dict[str, str] | None = None) -> dict[str, Any]:
    month = str(raw.get("month") or "")
    try:
        datetime.strptime(f"{month}-01", "%Y-%m-%d")
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="month must have YYYY-MM format") from exc

    def values(item: Any) -> dict[str, int]:
        item = item if isinstance(item, dict) else {}
        result: dict[str, int] = {}
        for key in ("revenuePlanKopecks", "marginPlanKopecks"):
            try:
                amount = int(item.get(key) or 0)
            except (TypeError, ValueError) as exc:
                raise HTTPException(status_code=422, detail=f"{key} must be a non-negative integer") from exc
            if amount < 0:
                raise HTTPException(status_code=422, detail=f"{key} must be a non-negative integer")
            result[key] = amount
        return result

    managers: list[dict[str, Any]] = []
    for index, item in enumerate(raw.get("managers") if isinstance(raw.get("managers"), list) else []):
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        if not name:
            continue
        manager_id = str(item.get("id") or f"manager-{index}")
        if allowed_managers is not None:
            if manager_id not in allowed_managers:
                continue
            name = allowed_managers[manager_id]
        managers.append({"id": manager_id, "name": name, **values(item)})
    return {"month": month, "company": values(raw.get("company")), "managers": managers, "updatedAt": _utc_now_iso()}


@router.get("/api/wb/reports/rules")
def get_report_rules(request: Request) -> dict[str, Any]:
    actor = actor_from_request(request)
    assert_permission_or_audit(
        actor=actor,
        permission="settings:read",
        action="reports.rules.get",
        object_type="wb_report_rule_profile",
        object_id=str(actor.organization_id),
        reason="actor cannot read report rules",
    )
    profile = load_active_profile(actor.organization_id)
    return {
        "profile": _rules_profile_payload(profile),
        "presets": {name: config.model_dump(mode="json") for name, config in PRESET_CONFIGS.items()},
        "automationActions": ["raise_price", "lower_price", "rnp", "liquidation", "stop_ads", "alert", "audit"],
        "canWrite": has_permission(actor, "settings:write"),
    }


@router.get("/api/wb/reports/rules/history")
def get_report_rules_history(request: Request, limit: int = Query(default=20, ge=1, le=100)) -> dict[str, Any]:
    actor = actor_from_request(request)
    assert_permission_or_audit(
        actor=actor,
        permission="settings:read",
        action="reports.rules.history",
        object_type="wb_report_rule_profile",
        object_id=str(actor.organization_id),
        reason="actor cannot read report rules history",
    )
    return {"items": [_rules_profile_payload(item) for item in list_profile_history(actor.organization_id, limit=limit)]}


@router.post("/api/wb/reports/rules/preview")
def preview_report_rules(request: Request, draft: RulesDraftRequest = Body(...)) -> dict[str, Any]:
    actor = actor_from_request(request)
    assert_permission_or_audit(
        actor=actor,
        permission="settings:write",
        action="reports.rules.preview",
        object_type="wb_report_rule_profile",
        object_id=str(actor.organization_id),
        reason="actor cannot preview report rules",
    )
    active = load_active_profile(actor.organization_id)
    if active.version != draft.expectedVersion:
        raise HTTPException(status_code=409, detail={"code": "RULES_VERSION_CONFLICT", "currentVersion": active.version})
    try:
        normalized = normalize_config(draft.config)
    except ReportRulesValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors) from exc
    rows, available_reports = _report_rules_preview_rows(actor.organization_id)
    preview = create_preview(rows, active, normalized)
    return {
        **preview,
        "availableReports": available_reports,
        "previewToken": issue_preview_token(actor.organization_id, active.version, normalized),
    }


@router.put("/api/wb/reports/rules")
def save_report_rules(request: Request, draft: RulesSaveRequest = Body(...)) -> dict[str, Any]:
    actor = actor_from_request(request)
    assert_permission_or_audit(
        actor=actor,
        permission="settings:write",
        action="reports.rules.save",
        object_type="wb_report_rule_profile",
        object_id=str(actor.organization_id),
        reason="actor cannot save report rules",
    )
    active = load_active_profile(actor.organization_id)
    try:
        normalized = normalize_config(draft.config)
        token_payload = verify_preview_token(draft.previewToken, actor.organization_id, draft.expectedVersion, normalized)
        saved = activate_profile(
            actor.organization_id,
            actor.user_id,
            draft.expectedVersion,
            draft.preset,
            draft.name.strip(),
            normalized,
        )
    except ReportRulesValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors) from exc
    except (PreviewTokenError, ProfileVersionConflict) as exc:
        current_version = load_active_profile(actor.organization_id).version
        raise HTTPException(status_code=409, detail={"code": "RULES_VERSION_CONFLICT", "message": str(exc), "currentVersion": current_version}) from exc
    record_audit_event(
        actor=actor,
        action="reports.rules.activate",
        object_type="wb_report_rule_profile",
        object_id=f"{actor.organization_id}:{saved.version}",
        before_state={"version": active.version, "preset": active.preset},
        after_state={"version": saved.version, "preset": saved.preset},
        reason="report rules activated after preview",
        approval_ref=str(token_payload.get("configHash")),
        evidence_refs=[f"rules-preview:{token_payload.get('configHash')}"],
    )
    return {"profile": _rules_profile_payload(saved)}


@router.get("/api/wb/reports/digest/plan")
def get_digest_plan(request: Request, month: str = Query(...)) -> dict[str, Any]:
    actor = actor_from_request(request)
    assert_permission_or_audit(actor=actor, permission="settings:read", action="reports.bff.digest.plan.get", object_type="wb_report", object_id="digest-plan", reason="actor cannot read digest plan")
    managers = _digest_plan_managers(actor.organization_id)
    normalized = _normalize_digest_plan({"month": month}, allowed_managers=managers)
    stored = get_source_cache(actor.organization_id, _digest_plan_cache_key(normalized["month"]), slim=False) or normalized
    if not isinstance(stored, dict):
        stored = normalized
    # Reconcile saved values with the current team: removed users disappear, new users appear with zero values.
    saved_by_id = {str(item.get("id")): item for item in stored.get("managers", []) if isinstance(item, dict)}
    def saved_values(item: Any) -> dict[str, int]:
        item = item if isinstance(item, dict) else {}
        return {
            key: max(0, int(item.get(key) or 0))
            for key in ("revenuePlanKopecks", "marginPlanKopecks")
        }

    stored["managers"] = [
        {"id": manager_id, "name": name, **saved_values(saved_by_id.get(manager_id))}
        for manager_id, name in managers.items()
    ]
    return stored


@router.post("/api/wb/reports/digest/plan")
def save_digest_plan(request: Request, raw_plan: dict[str, Any] = Body(...)) -> dict[str, Any]:
    actor = actor_from_request(request)
    assert_permission_or_audit(actor=actor, permission="settings:write", action="reports.bff.digest.plan.save", object_type="wb_report", object_id="digest-plan", reason="actor cannot save digest plan")
    plan = _normalize_digest_plan(raw_plan, allowed_managers=_digest_plan_managers(actor.organization_id))
    save_source_cache(actor.organization_id, _digest_plan_cache_key(plan["month"]), plan)
    return plan


@router.post("/api/wb/reports/digest/refresh")
def refresh_reports_digest(request: Request, preset: str = Query(default="7d"), from_: str | None = Query(default=None, alias="from"), to: str | None = Query(default=None)) -> dict[str, Any]:
    actor = actor_from_request(request)
    assert_permission_or_audit(actor=actor, permission="settings:read", action="reports.bff.digest.refresh", object_type="wb_report", object_id="digest", reason="actor cannot refresh digest report")
    date_from, date_to, _ = _range_from_preset(preset, from_, to)
    key = _digest_job_cache_key(date_from, date_to)
    current = get_source_cache(actor.organization_id, key, slim=False) or {}
    exact = get_source_cache(actor.organization_id, _digest_cache_key(date_from, date_to), slim=False) or {}
    exact_age_seconds = _digest_cache_age_seconds(exact)
    if _digest_cache_is_fresh(exact):
        payload = {
            **current,
            "state": "completed",
            "stage": "cache",
            "label": "Воронка продаж взята из кэша за последние 24 часа",
            "percent": 100,
            "dateFrom": date_from.isoformat(),
            "dateTo": date_to.isoformat(),
            "updatedAt": _utc_now_iso(),
            "reused": True,
            "cacheFresh": True,
            "cacheAgeSeconds": exact_age_seconds,
            "cacheTtlSeconds": int(DIGEST_CACHE_TTL.total_seconds()),
        }
        save_source_cache(actor.organization_id, key, payload)
        return payload
    if current.get("state") in {"queued", "running"}:
        return {**current, "reused": True}
    from app.repricer_tasks import build_digest_for_org
    task = build_digest_for_org.delay(actor.organization_id, date_from.isoformat(), date_to.isoformat(), has_permission(actor, "finance:read"), None)
    payload = {"state": "queued", "taskId": task.id, "dateFrom": date_from.isoformat(), "dateTo": date_to.isoformat(), "queuedAt": _utc_now_iso()}
    save_source_cache(actor.organization_id, key, payload)
    return {**payload, "reused": False}


@router.get("/api/wb/reports/digest/status")
def get_reports_digest_status(request: Request, preset: str = Query(default="7d"), from_: str | None = Query(default=None, alias="from"), to: str | None = Query(default=None)) -> dict[str, Any]:
    actor = actor_from_request(request)
    assert_permission_or_audit(actor=actor, permission="settings:read", action="reports.bff.digest.status", object_type="wb_report", object_id="digest", reason="actor cannot read digest job")
    date_from, date_to, _ = _range_from_preset(preset, from_, to)
    return get_source_cache(actor.organization_id, _digest_job_cache_key(date_from, date_to), slim=False) or {"state": "idle", "dateFrom": date_from.isoformat(), "dateTo": date_to.isoformat()}


@router.get("/api/wb/reports/{report_id}/latest-cache")
def get_reports_latest_cache(
    request: Request,
    report_id: Literal["digest", "abc", "rnp", "ads", "pnl", "expenses", "stock", "week-over-week"],
    groupBy: ReportGroupBy = Query(default="sku"),
    source: str = Query(default="operational"),
    preset: str = Query(default="latest"),
    from_: str | None = Query(default=None, alias="from"),
    to: str | None = Query(default=None),
) -> dict[str, Any]:
    actor = actor_from_request(request)
    assert_permission_or_audit(
        actor=actor,
        permission="settings:read",
        action="reports.bff.latest_cache.get",
        object_type="wb_report",
        object_id=report_id,
        reason="actor cannot read latest report cache",
    )
    if report_id == "digest":
        requested_from: date | None = None
        requested_to: date | None = None
        if preset != "latest" or from_ or to:
            requested_from, requested_to, _ = _range_from_preset(preset, from_, to)
        if requested_from is not None and requested_to is not None:
            candidates = [get_source_cache(actor.organization_id, _digest_cache_key(requested_from, requested_to), slim=False) or {}]
        else:
            candidates = [get_source_cache(actor.organization_id, "reports_digest_latest", slim=False) or {}]
            candidates.extend(
                cache
                for cache in list_source_cache_by_prefix(actor.organization_id, "reports_digest_", limit=50, slim=False)
                if re.match(rf"^reports_digest_{re.escape(DIGEST_REPORT_PAYLOAD_VERSION)}_\d{{4}}-\d{{2}}-\d{{2}}_\d{{4}}-\d{{2}}-\d{{2}}$", str(cache.get("sourceKey") or ""))
            )
        for cache in candidates:
            if not _digest_cache_is_fresh(cache):
                continue
            digest = cache.get("digest") if isinstance(cache.get("digest"), dict) else None
            if digest is None:
                continue
            date_from, date_to, date_range = _date_range_from_report_cache(cache)
            if date_from is None or date_to is None or date_range is None:
                continue
            if requested_from is not None and requested_to is not None and (date_from != requested_from or date_to != requested_to):
                continue
            payload = dict(digest)
            payload["cache"] = {
                "status": "latest",
                "requestedRange": date_range,
                "fresh": True,
                "ageSeconds": _digest_cache_age_seconds(cache),
                "ttlSeconds": int(DIGEST_CACHE_TTL.total_seconds()),
                "completedAt": cache.get("completedAt"),
                "fetchedAt": cache.get("fetchedAt"),
            }
            payload["digestJob"] = {
                "state": "completed",
                "stage": "cache",
                "label": "Воронка продаж взята из последнего свежего кэша",
                "percent": 100,
                "dateFrom": date_from.isoformat(),
                "dateTo": date_to.isoformat(),
                "updatedAt": _utc_now_iso(),
                "reused": True,
                "cacheFresh": True,
                "cacheAgeSeconds": _digest_cache_age_seconds(cache),
                "cacheTtlSeconds": int(DIGEST_CACHE_TTL.total_seconds()),
            }
            return payload
        raise HTTPException(status_code=404, detail="REPORT_LATEST_CACHE_MISSING")

    requested_from = None
    requested_to = None
    if preset != "latest" or from_ or to:
        requested_from, requested_to, _ = _range_from_preset(preset, from_, to)

    latest = _latest_report_payload_cache(
        organization_id=actor.organization_id,
        report_id=report_id,
        group_by=groupBy,
        source=source,
        date_from=requested_from,
        date_to=requested_to,
    )
    if latest is None:
        if report_id == "week-over-week" and requested_from is not None and requested_to is not None:
            date_range = {"preset": "custom", "from": requested_from.isoformat(), "to": requested_to.isoformat()}
            payload = _build_week_over_week_fallback_report(
                request=request,
                actor=actor,
                date_from=requested_from,
                date_to=requested_to,
                date_range=date_range,
                finance_allowed=has_permission(actor, "finance:read"),
                wb_token=None,
            )
            if _week_report_has_period_activity(payload):
                cache = _save_exact_report_payload_cache(
                    organization_id=actor.organization_id,
                    report_id=report_id,
                    date_from=requested_from,
                    date_to=requested_to,
                    group_by=groupBy,
                    source=source,
                    report=payload,
                )
                job = _completed_report_job_from_cache(report_id, requested_from, requested_to, groupBy, cache, payload.get("reportJob") if isinstance(payload.get("reportJob"), dict) else {})
                save_source_cache(actor.organization_id, _report_job_cache_key(report_id, requested_from, requested_to, groupBy), job)
                payload["cache"] = _report_payload_cache_meta(cache, date_range, "derived")
                payload["reportJob"] = job
                return payload
        raise HTTPException(status_code=404, detail="REPORT_LATEST_CACHE_MISSING")
    cache, date_from, date_to = latest
    report = cache.get("report") if isinstance(cache.get("report"), dict) else None
    if report is None:
        raise HTTPException(status_code=404, detail="REPORT_LATEST_CACHE_MISSING")
    date_range = {"preset": "custom", "from": date_from.isoformat(), "to": date_to.isoformat()}
    job = get_source_cache(actor.organization_id, _report_job_cache_key(report_id, date_from, date_to, groupBy, source), slim=False) or {}
    payload = dict(report)
    payload["cache"] = _report_payload_cache_meta(cache, date_range, "latest")
    payload["reportJob"] = _completed_report_job_from_cache(report_id, date_from, date_to, groupBy, cache, job)
    return payload


@router.get("/api/wb/reports/alerts")
def get_reports_alerts(
    request: Request,
    preset: str = Query(default="7d"),
    from_: str | None = Query(default=None, alias="from"),
    to: str | None = Query(default=None),
) -> dict[str, Any]:
    actor = actor_from_request(request)
    assert_permission_or_audit(
        actor=actor,
        permission="settings:read",
        action="reports.bff.alerts.get",
        object_type="wb_report",
        object_id="alerts",
        reason="actor cannot read report alerts",
    )
    date_from, date_to, _date_range = _range_from_preset(preset, from_, to)
    source_snapshot = build_cached_wb_reports_sources_snapshot(organization_id=actor.organization_id, date_from=date_from, date_to=date_to)
    items = []
    for row in source_snapshot.stocks:
        if row.available_units <= 0:
            items.append(
                {
                    "id": f"oos-{row.nm_id}-{row.warehouse_id or 0}",
                    "alertType": "stock_oos",
                    "severity": "critical",
                    "entityType": "warehouse",
                    "entityId": str(row.nm_id),
                    "title": f"OOS risk for NM {row.nm_id}",
                    "details": f"{row.warehouse_name or 'warehouse'} availableUnits <= 0",
                    "createdAt": _utc_now_iso(),
                    "resolvedAt": None,
                    "route": "/wb/reports/stock",
                }
            )
    return {"items": items}


@router.get("/api/wb/reports/export/{report_id}")
def get_reports_export(
    request: Request,
    report_id: ReportId,
    preset: str = Query(default="7d"),
    from_: str | None = Query(default=None, alias="from"),
    to: str | None = Query(default=None),
) -> dict[str, Any]:
    actor = actor_from_request(request)
    assert_permission_or_audit(
        actor=actor,
        permission="settings:read",
        action="reports.bff.export.get",
        object_type="wb_export",
        object_id=f"export:{report_id}",
        reason="actor cannot request report export",
    )
    date_from, date_to, _date_range = _range_from_preset(preset, from_, to)
    row_count = _estimated_export_rows(
        report_id,
        date_from,
        date_to,
        has_permission(actor, "finance:read"),
        wb_token=None,
        organization_id=actor.organization_id,
    )
    export = request_report_export(
        actor=actor,
        report_id=report_id,
        preset=preset,
        from_raw=from_,
        to_raw=to,
        row_count=row_count,
    )
    completed = materialize_report_export(
        actor=actor,
        export_id=export.exportId,
        row_count=row_count,
    )
    return {
        "exportId": completed.exportId,
        "jobId": completed.jobId,
        "status": completed.status,
        "fileName": completed.fileName,
        "rows": completed.rows,
        "emptySourceNote": completed.emptySourceNote,
        "downloadUrl": completed.downloadUrl,
    }


@router.post("/api/wb/reports/export/{report_id}")
def request_reports_export_job(
    request: Request,
    report_id: ReportExportId,
    preset: str = Query(default="7d"),
    from_: str | None = Query(default=None, alias="from"),
    to: str | None = Query(default=None),
) -> dict[str, Any]:
    actor = actor_from_request(request)
    assert_permission_or_audit(
        actor=actor,
        permission="settings:read",
        action="reports.bff.export.create",
        object_type="wb_export",
        object_id=f"export:{report_id}",
        reason="actor cannot create report export job",
    )
    date_from, date_to, _date_range = _range_from_preset(preset, from_, to)
    export = request_report_export(
        actor=actor,
        report_id=report_id,
        preset=preset,
        from_raw=from_,
        to_raw=to,
        row_count=_estimated_export_rows(
            report_id,
            date_from,
            date_to,
            has_permission(actor, "finance:read"),
            wb_token=None,
            organization_id=actor.organization_id,
        ),
    )
    record_audit_event(
        actor=actor,
        action="reports.bff.export.create",
        object_type="wb_export",
        object_id=export.exportId,
        before_state=None,
        after_state=export.model_dump(mode="json"),
        reason="queue async report export",
        approval_ref=None,
        evidence_refs=["REPORT_EXPORT_ASYNC_FLOW"],
    )
    return export.model_dump(mode="json")


@router.get("/api/wb/reports/export/jobs/{export_id}")
def get_reports_export_job(
    request: Request,
    export_id: str,
) -> dict[str, Any]:
    actor = actor_from_request(request)
    assert_permission_or_audit(
        actor=actor,
        permission="settings:read",
        action="reports.bff.export.get",
        object_type="wb_export",
        object_id=export_id,
        reason="actor cannot read report export job",
    )
    export = get_report_export_or_none(export_id)
    if export is None:
        raise HTTPException(status_code=404, detail="EXPORT_JOB_NOT_FOUND")
    completed = materialize_report_export(actor=actor, export_id=export_id, row_count=export.rows)
    return completed.model_dump(mode="json")


@router.get("/reports/cash-flow")
@router.get("/api/wb/reports/cash-flow")
def get_cash_flow_report(
    request: Request,
    from_: str = Query(alias="from"),
    to: str = Query(),
) -> dict[str, Any]:
    actor = actor_from_request(request)
    assert_permission_or_audit(
        actor=actor,
        permission="settings:read",
        action="reports.cash_flow.get",
        object_type="cash_flow",
        object_id=f"{from_}:{to}",
        reason="actor cannot read cash-flow report",
    )
    period_from = date.fromisoformat(from_)
    period_to = date.fromisoformat(to)
    return get_cash_flow_for_period(
        organization_id=actor.organization_id,
        period_from=period_from,
        period_to=period_to,
        requested_by=actor.user_id,
    )


@router.get("/api/wb/reports/{report_id}")
def get_reports_by_id(
    request: Request,
    report_id: ReportId,
    preset: str = Query(default="7d"),
    from_: str | None = Query(default=None, alias="from"),
    to: str | None = Query(default=None),
    groupBy: ReportGroupBy = Query(default="sku"),
    source: str = Query(default="operational"),
) -> dict[str, Any]:
    actor = actor_from_request(request)
    assert_permission_or_audit(
        actor=actor,
        permission="settings:read",
        action="reports.bff.get",
        object_type="wb_report",
        object_id=report_id,
        reason="actor cannot read bff report",
    )
    finance_allowed = has_permission(actor, "finance:read")
    wb_token = None if report_id in BACKGROUND_REPORT_IDS else _actor_wb_token(actor)
    date_from, date_to, date_range = _range_from_preset(preset, from_, to)

    if report_id == "expenses":
        cash_flow = get_cash_flow_for_period(
            organization_id=actor.organization_id,
            period_from=date_from,
            period_to=date_to,
            requested_by=actor.user_id,
        )
        job = get_source_cache(actor.organization_id, _report_job_cache_key(report_id, date_from, date_to, groupBy, source), slim=False) or {
            "state": "waiting_1c" if cash_flow.get("status") in {"pending", "processing"} else "completed",
            "reportId": report_id,
            "dateFrom": date_from.isoformat(),
            "dateTo": date_to.isoformat(),
            "groupBy": groupBy,
            "stage": "waiting_1c" if cash_flow.get("status") in {"pending", "processing"} else "completed",
            "label": "Ждём операционные расходы от 1С" if cash_flow.get("status") in {"pending", "processing"} else "Расходы из 1С готовы",
            "percent": 20 if cash_flow.get("status") in {"pending", "processing"} else 100,
        }
        return _map_cash_flow_to_expenses_response(cash_flow, date_range, groupBy, job)

    if report_id == "week-over-week":
        cache_key = _report_cache_key(report_id, date_from, date_to, groupBy, source)
        cached = get_source_cache(actor.organization_id, cache_key, slim=False) or {}
        report = cached.get("report") if isinstance(cached.get("report"), dict) else None
        job = get_source_cache(actor.organization_id, _report_job_cache_key(report_id, date_from, date_to, groupBy, source), slim=False) or {
            "state": "idle", "reportId": report_id, "dateFrom": date_from.isoformat(), "dateTo": date_to.isoformat(), "groupBy": groupBy,
        }
        if report is not None:
            if not _report_payload_cache_is_usable(report_id, cached):
                return _empty_background_report(report_id, date_range, groupBy, _report_job_for_response(job))
            job = _report_job_for_response(job)
            if _report_payload_cache_is_usable(report_id, cached):
                job = _completed_report_job_from_cache(report_id, date_from, date_to, groupBy, cached, job)
                save_source_cache(actor.organization_id, _report_job_cache_key(report_id, date_from, date_to, groupBy, source), job)
            payload = _apply_report_rules_to_payload(report, actor.organization_id)
            payload["cache"] = _report_payload_cache_meta(
                cached,
                date_range,
                "stale" if job.get("state") in {"queued", "running", "waiting_1c"} else None,
            )
            payload["reportJob"] = job
            return payload
        return _empty_background_report(report_id, date_range, groupBy, job)

    if report_id == "pnl":
        cache_key = _report_cache_key(report_id, date_from, date_to, groupBy, source)
        cached = get_source_cache(actor.organization_id, cache_key, slim=False) or {}
        report = cached.get("report") if isinstance(cached.get("report"), dict) else None
        job = get_source_cache(actor.organization_id, _report_job_cache_key(report_id, date_from, date_to, groupBy, source), slim=False) or {
            "state": "idle", "reportId": report_id, "dateFrom": date_from.isoformat(), "dateTo": date_to.isoformat(), "groupBy": groupBy,
        }
        if report is not None:
            job = _report_job_for_response(job)
            if _report_payload_cache_is_usable(report_id, cached):
                job = _completed_report_job_from_cache(report_id, date_from, date_to, groupBy, cached, job)
                save_source_cache(actor.organization_id, _report_job_cache_key(report_id, date_from, date_to, groupBy, source), job)
            payload = _apply_report_rules_to_payload(report, actor.organization_id)
            payload["cache"] = _report_payload_cache_meta(
                cached,
                date_range,
                "stale" if job.get("state") in {"queued", "running", "waiting_1c", "waiting_daily_detail"} else None,
            )
            payload["reportJob"] = job
            return payload
        return _empty_background_report(report_id, date_range, groupBy, job)

    daily_sources = REPORT_DAILY_SOURCES_BY_ID.get(report_id, ())
    if daily_sources:
        ready, missing_sources = _report_daily_sources_ready(actor.organization_id, daily_sources, date_from=date_from, date_to=date_to)
        if not ready:
            job_key = _report_job_cache_key(report_id, date_from, date_to, groupBy)
            current_job = get_source_cache(actor.organization_id, job_key, slim=False) or {}
            job = _report_waiting_daily_detail_job(report_id, date_from, date_to, groupBy, missing_sources, current_job)
            save_source_cache(actor.organization_id, job_key, job)
            return _empty_background_report(report_id, date_range, groupBy, job)

    if report_id == "stock":
        source_snapshot = build_cached_wb_reports_sources_snapshot(organization_id=actor.organization_id, date_from=date_from, date_to=date_to)
        payload = _apply_report_rules_to_payload(
            _build_stock_report_payload(date_range, source_snapshot, organization_id=actor.organization_id, wb_token=wb_token),
            actor.organization_id,
        )
        _save_exact_report_payload_cache(organization_id=actor.organization_id, report_id=report_id, date_from=date_from, date_to=date_to, group_by=groupBy, source=source, report=payload)
        return payload
    if report_id == "ads":
        payload = _apply_report_rules_to_payload(
            _build_ads_report_payload(
                actor=actor,
                date_from=date_from,
                date_to=date_to,
                date_range=date_range,
                wb_token=wb_token,
            ),
            actor.organization_id,
        )
        _save_exact_report_payload_cache(organization_id=actor.organization_id, report_id=report_id, date_from=date_from, date_to=date_to, group_by=groupBy, source=source, report=payload)
        return payload
    if report_id == "rnp":
        rnp_payload = build_rnp_report(
            date_from=date_from,
            date_to=date_to,
            group_by=groupBy,
            finance_allowed=finance_allowed,
            organization_id=actor.organization_id,
            wb_token=None,
        )
        payload = _apply_report_rules_to_payload(_map_rnp_to_report_response(rnp_payload, date_range), actor.organization_id)
        _save_exact_report_payload_cache(organization_id=actor.organization_id, report_id=report_id, date_from=date_from, date_to=date_to, group_by=groupBy, source=source, report=payload)
        return payload
    if report_id == "abc":
        abc_payload = build_abc_report(
            date_from=date_from,
            date_to=date_to,
            group_by=groupBy,
            filters="",
            finance_allowed=finance_allowed,
            organization_id=actor.organization_id,
        )
        abc_rows = _normalize_abc_report_rows([row for row in abc_payload.rows if isinstance(row, dict)])
        source_status = abc_payload.sourceStatus
        confidence = abc_payload.confidence
        blocker_ids = list(getattr(abc_payload, "blockerIds", []) or [])
        filtered_summary = abc_payload.filteredSummary.model_dump(mode="json")
        if not abc_rows:
            repricer_rows = _repricer_rows_for_abc_report(
                request=request,
                actor=actor,
                wb_token=wb_token,
                date_from=date_from,
                date_to=date_to,
            )
            abc_rows = [
                mapped
                for mapped in (_repricer_row_to_abc_row(row) for row in repricer_rows if isinstance(row, dict))
                if mapped.get("sku")
            ]
            if abc_rows:
                source_status = "partial"
                confidence = "medium" if _abc_rows_have_financial_activity(abc_rows) else "low"
                blocker_ids.append("WB_ABC_RUNTIME_FALLBACK_REPRICER_LIST")
                filtered_summary = _abc_filtered_summary_from_rows(
                    abc_rows,
                    source_status=source_status,
                    confidence=confidence,
                )
        abc_rows = _normalize_abc_report_rows(abc_rows)
        if abc_rows and not _abc_rows_have_financial_activity(abc_rows):
            source_status = "partial"
            confidence = "low"
            if "WB_ABC_PERIOD_ACTIVITY_EMPTY" not in blocker_ids:
                blocker_ids.append("WB_ABC_PERIOD_ACTIVITY_EMPTY")
            filtered_summary["sourceStatus"] = source_status
            filtered_summary["confidence"] = confidence
        payload = _apply_report_rules_to_payload({
            "cacheVersion": ABC_REPORT_PAYLOAD_VERSION,
            "meta": _meta("abc", "ABC-анализ", "ABC and SKU profitability view.", "operational", source_status),
            "headline": "ABC summary for selected period.",
            "filters": {"dateRange": date_range, "groupBy": groupBy},
            "kpis": [
                _kpi("sku_count", "SKU", str(filtered_summary.get("skuCount") or 0)),
                _kpi("orders", "Заказы", str(filtered_summary.get("ordersCount") or 0)),
                _kpi("orders_revenue", "Выручка", str(filtered_summary.get("ordersKopecks") or 0)),
                _kpi("profit", "Прибыль", str(filtered_summary.get("profitKopecks") or 0)),
            ],
            "chart": {
                "title": "Чистая прибыль по SKU",
                "valueLabel": "Чистая прибыль, коп",
                "points": [
                    {"label": str(row.get("sku") or row.get("label") or index + 1), "value": int(row.get("netTotalKopecks") or row.get("profitKopecks") or 0)}
                    for index, row in enumerate(abc_rows[:20])
                    if isinstance(row, dict)
                ],
            },
            "columns": [
                {"key": "sku", "label": "Артикул", "sticky": True},
                {"key": "nmId", "label": "WB"},
                {"key": "abcCode", "label": "ABC", "format": "abc", "align": "center"},
                {"key": "productStatus", "label": "Статус"},
                {"key": "manager", "label": "Менеджер"},
                {"key": "brand", "label": "Бренд"},
                {"key": "category", "label": "Категория"},
                {"key": "clicks", "label": "Переходы WB", "format": "number", "align": "right"},
                {"key": "baskets", "label": "Корзины", "format": "number", "align": "right"},
                {"key": "basketsDeltaPct", "label": "Дин. корзин", "format": "percent", "align": "right"},
                {"key": "cartCrPct", "label": "CR корзин", "format": "percent", "align": "right"},
                {"key": "ordersComposite", "label": "Заказы шт/руб/динамика", "align": "right"},
                {"key": "salesComposite", "label": "Продажи шт/руб/динамика", "align": "right"},
                {"key": "netTotalKopecks", "label": "Чистая прибыль", "format": "currency", "align": "right"},
                {"key": "marginPct", "label": "Маржа", "format": "percent", "align": "right"},
                {"key": "adSpendKopecks", "label": "Реклама", "format": "currency", "align": "right"},
                {"key": "wbStockUnits", "label": "Остаток WB", "format": "number", "align": "right"},
                {"key": "logisticsCostPct", "label": "% логистика", "format": "percent", "align": "right"},
                {"key": "commissionCostPct", "label": "% комиссия", "format": "percent", "align": "right"},
                {"key": "storageCostPct", "label": "% хранение", "format": "percent", "align": "right"},
            ],
            "rows": abc_rows,
            "sourceStatus": source_status,
            "confidence": confidence,
            "blockerIds": blocker_ids,
            "sourceEvidence": [item.model_dump(mode="json") for item in abc_payload.sourceEvidence],
            "filteredSummary": filtered_summary,
        }, actor.organization_id)
        _save_exact_report_payload_cache(organization_id=actor.organization_id, report_id=report_id, date_from=date_from, date_to=date_to, group_by=groupBy, source=source, report=payload)
        return payload
    if report_id == "pnl":
        source_mode = "final" if source == "financial" else "preliminary"
        cash_flow = get_cash_flow_for_period(
            organization_id=actor.organization_id,
            period_from=date_from,
            period_to=date_to,
            requested_by=actor.user_id,
        )
        pnl_payload = build_pnl_report(
            date_from=date_from,
            date_to=date_to,
            group_by=groupBy,
            requested_state=source_mode,
            finance_allowed=finance_allowed,
            organization_id=actor.organization_id,
            wb_token=None,
        )
        return _apply_report_rules_to_payload(_map_pnl_to_report_response(pnl_payload, date_range, cash_flow), actor.organization_id)

    return {
        "meta": _meta(report_id, report_id, "unknown report"),
        "headline": "No data",
        "filters": {"dateRange": date_range, "groupBy": groupBy},
        "kpis": [],
        "chart": {"title": "No data", "valueLabel": "-", "points": []},
        "columns": [],
        "rows": [],
    }


@router.post("/api/wb/reports/{report_id}/jobs")
def start_report_job(request: Request, report_id: Literal["abc", "rnp", "ads", "pnl", "expenses", "stock", "week-over-week"], preset: str = Query(default="7d"), from_: str | None = Query(default=None, alias="from"), to: str | None = Query(default=None), groupBy: ReportGroupBy = Query(default="sku"), source: str = Query(default="operational")) -> dict[str, Any]:
    actor = actor_from_request(request)
    assert_permission_or_audit(actor=actor, permission="settings:read", action="reports.bff.job.start", object_type="wb_report", object_id=report_id, reason="actor cannot refresh report")
    date_from, date_to, _ = _range_from_preset(preset, from_, to)
    key = _report_job_cache_key(report_id, date_from, date_to, groupBy, source)
    cache_key = _report_cache_key(report_id, date_from, date_to, groupBy, source)
    cached = get_source_cache(actor.organization_id, cache_key, slim=False) or {}
    current = get_source_cache(actor.organization_id, key, slim=False) or {}
    if _report_job_is_active_refresh(current):
        return {**current, "reused": True}
    if _report_payload_cache_is_usable(report_id, cached):
        payload = _completed_report_job_from_cache(report_id, date_from, date_to, groupBy, cached, current)
        save_source_cache(actor.organization_id, key, payload)
        return payload
    daily_sources = REPORT_DAILY_SOURCES_BY_ID.get(report_id, ())
    if daily_sources:
        ready, missing_sources = _report_daily_sources_ready(actor.organization_id, daily_sources, date_from=date_from, date_to=date_to)
        if not ready:
            from app.repricer_tasks import refresh_report_sources_for_org

            task = refresh_report_sources_for_org.delay(
                actor.organization_id,
                actor.user_id,
                report_id,
                date_from.isoformat(),
                date_to.isoformat(),
                groupBy,
                source,
                has_permission(actor, "finance:read"),
                None,
            )
            payload = {
                **_report_waiting_daily_detail_job(report_id, date_from, date_to, groupBy, missing_sources, current),
                "state": "queued",
                "taskId": task.id,
                "kind": "report_source_refresh",
                "stage": "queued",
                "label": "Готовим недостающие данные отчета",
                "percent": 0,
                "queuedAt": _utc_now_iso(),
                "updatedAt": _utc_now_iso(),
            }
            save_source_cache(actor.organization_id, key, payload)
            return {**payload, "reused": False}
    if _report_job_is_reusable(current):
        return {**current, "reused": True}
    cash_flow = None
    if report_id in {"pnl", "expenses"}:
        cash_flow = get_cash_flow_for_period(
            organization_id=actor.organization_id,
            period_from=date_from,
            period_to=date_to,
            requested_by=actor.user_id,
        )
    from app.repricer_tasks import build_report_for_org
    task = build_report_for_org.delay(actor.organization_id, actor.user_id, report_id, date_from.isoformat(), date_to.isoformat(), groupBy, source, has_permission(actor, "finance:read"), None)
    payload = {"state": "queued", "taskId": task.id, "reportId": report_id, "dateFrom": date_from.isoformat(), "dateTo": date_to.isoformat(), "groupBy": groupBy, "source": source, "queuedAt": _utc_now_iso()}
    save_source_cache(actor.organization_id, key, payload)
    return {**payload, "reused": False, **({"cashFlow": cash_flow} if cash_flow is not None else {})}


@router.post("/api/wb/reports/{report_id}/refresh-sources-job")
def start_report_source_refresh_job(
    request: Request,
    report_id: Literal["digest", "abc", "rnp", "ads", "pnl", "stock", "week-over-week"],
    preset: str = Query(default="7d"),
    from_: str | None = Query(default=None, alias="from"),
    to: str | None = Query(default=None),
    groupBy: ReportGroupBy = Query(default="sku"),
    source: str = Query(default="operational"),
) -> dict[str, Any]:
    actor = actor_from_request(request)
    assert_permission_or_audit(actor=actor, permission="settings:read", action="reports.bff.sources_refresh.start", object_type="wb_report", object_id=report_id, reason="actor cannot refresh report sources")
    date_from, date_to, _ = _range_from_preset(preset, from_, to)
    key = _digest_job_cache_key(date_from, date_to) if report_id == "digest" else _report_job_cache_key(report_id, date_from, date_to, groupBy, source)
    current = get_source_cache(actor.organization_id, key, slim=False) or {}
    if _report_job_is_active_refresh(current):
        return {**current, "reused": True}
    from app.repricer_tasks import refresh_report_sources_for_org
    task = refresh_report_sources_for_org.delay(actor.organization_id, actor.user_id, report_id, date_from.isoformat(), date_to.isoformat(), groupBy, source, has_permission(actor, "finance:read"), None)
    payload = {
        "state": "queued",
        "taskId": task.id,
        "kind": "report_source_refresh",
        "reportId": report_id,
        "dateFrom": date_from.isoformat(),
        "dateTo": date_to.isoformat(),
        "groupBy": groupBy,
        "stage": "queued",
        "label": "Обновление данных отчета поставлено в очередь",
        "percent": 0,
        "queuedAt": _utc_now_iso(),
        "updatedAt": _utc_now_iso(),
    }
    save_source_cache(actor.organization_id, key, payload)
    return {**payload, "reused": False}


@router.get("/api/wb/reports/{report_id}/jobs")
def get_report_job(request: Request, report_id: Literal["abc", "rnp", "ads", "pnl", "expenses", "stock", "week-over-week"], preset: str = Query(default="7d"), from_: str | None = Query(default=None, alias="from"), to: str | None = Query(default=None, alias="to"), groupBy: ReportGroupBy = Query(default="sku"), source: str = Query(default="operational")) -> dict[str, Any]:
    actor = actor_from_request(request)
    assert_permission_or_audit(actor=actor, permission="settings:read", action="reports.bff.job.status", object_type="wb_report", object_id=report_id, reason="actor cannot read report job")
    date_from, date_to, _ = _range_from_preset(preset, from_, to)
    key = _report_job_cache_key(report_id, date_from, date_to, groupBy, source)
    job = get_source_cache(actor.organization_id, key, slim=False) or {"state": "idle", "reportId": report_id, "dateFrom": date_from.isoformat(), "dateTo": date_to.isoformat(), "groupBy": groupBy}
    if _report_job_is_active_refresh(job):
        return _report_job_for_response({**job, "reused": True})
    if _report_job_is_finished_refresh(job):
        return _report_job_for_response({**job, "reused": True})
    cached = get_source_cache(actor.organization_id, _report_cache_key(report_id, date_from, date_to, groupBy, source), slim=False) or {}
    if _report_payload_cache_is_usable(report_id, cached):
        payload = _completed_report_job_from_cache(report_id, date_from, date_to, groupBy, cached, job)
        save_source_cache(actor.organization_id, key, payload)
        return payload
    return _report_job_for_response(job)


@router.post("/api/wb/reports/ads/refresh")
def refresh_ads_report_cache(
    request: Request,
    preset: str = Query(default="7d"),
    from_: str | None = Query(default=None, alias="from"),
    to: str | None = Query(default=None),
) -> dict[str, Any]:
    actor = actor_from_request(request)
    assert_permission_or_audit(
        actor=actor,
        permission="settings:read",
        action="reports.bff.ads.refresh",
        object_type="wb_report",
        object_id="ads",
        reason="actor cannot refresh ads report cache",
    )
    date_from, date_to, date_range = _range_from_preset(preset, from_, to)
    payload = _build_ads_report_payload(
        actor=actor,
        date_from=date_from,
        date_to=date_to,
        date_range=date_range,
        wb_token=None,
        refresh=False,
    )
    record_audit_event(
        actor=actor,
        action="reports.bff.ads.refresh",
        object_type="wb_report",
        object_id="ads",
        before_state=None,
        after_state={
            "rows": len(payload.get("rows") or []),
            "cache": payload.get("cache"),
        },
        reason="manual ads report cache refresh",
        approval_ref=None,
        evidence_refs=["wb_ads_report_cache", "wb_ads_campaign_status_snapshots", "wb_ads_campaign_budget_snapshots"],
    )
    return payload


@router.post("/api/wb/reports/rnp/refresh")
def refresh_rnp_report_cache(
    request: Request,
    preset: str = Query(default="7d"),
    from_: str | None = Query(default=None, alias="from"),
    to: str | None = Query(default=None),
    groupBy: ReportGroupBy = Query(default="sku"),
) -> dict[str, Any]:
    actor = actor_from_request(request)
    assert_permission_or_audit(
        actor=actor,
        permission="settings:read",
        action="reports.bff.rnp.refresh",
        object_type="wb_report",
        object_id="rnp",
        reason="actor cannot refresh rnp report cache",
    )
    finance_allowed = has_permission(actor, "finance:read")
    date_from, date_to, date_range = _range_from_preset(preset, from_, to)
    rnp_payload = build_rnp_report(
        date_from=date_from,
        date_to=date_to,
        group_by=groupBy,
        finance_allowed=finance_allowed,
        organization_id=actor.organization_id,
        wb_token=None,
        force_refresh=False,
    )
    payload = _map_rnp_to_report_response(rnp_payload, date_range)
    payload["cache"] = {"status": "refreshed"}
    record_audit_event(
        actor=actor,
        action="reports.bff.rnp.refresh",
        object_type="wb_report",
        object_id="rnp",
        before_state=None,
        after_state={
            "rows": len(payload.get("rows") or []),
            "sourceStatus": payload.get("meta", {}).get("freshnessState"),
        },
        reason="manual rnp report cache refresh",
        approval_ref=None,
        evidence_refs=["rnp_funnel_cache", "rnp_report_cache", "wb_ads_attribution"],
    )
    return payload
