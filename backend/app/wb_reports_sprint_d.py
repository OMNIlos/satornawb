from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from hashlib import sha1
from typing import Any, Literal

from pydantic import BaseModel, Field
from vella_wb_19_05.models import (
    AbcFilteredSummary,
    AbcReportResponse,
    AdsAttributionPolicy,
    AdsPerformanceResponse,
    AdsPerformanceRow,
    AdsTotals,
    DatePeriod,
    DayAllocationSummary,
    ManualCost,
    PnlFieldMapping,
    PnlReportResponse,
    PnlRow,
    PnlTotals,
    ReportGroupBy,
    RnpReportResponse,
    RnpRow,
    SourceEvidence,
    utc_now,
)
from app.repricer_bff import DEFAULT_ALGORITHM_SETTINGS, TYPE_DEFAULTS, _article_type, _extract_wb_media_url
from app.repricer_cache.store import (
    finance_cache_uses_current_revenue_basis,
    get_source_cache,
    list_cached_goods,
    list_source_cache_ranges_by_prefix,
    save_source_cache,
)
from app.repricer_persistence.store import load_algorithm_settings, load_runtime_state
from app.repricer_sync import (
    _good_buyer_price_no_wallet_kopecks,
    _good_seller_price_kopecks,
    _normalize_period_range,
    _period_cache_suffix,
)
from app.wb_api.ads_runtime import AdsAttributionRow, AdsAttributionSnapshot
from app.wb_api.rnp_runtime import build_rnp_snapshot


PnlRequestedState = Literal["operative", "preliminary", "final"]
PlanFactDimension = Literal["company", "manager", "brand"]

DEFAULT_FROM = date(2026, 5, 1)
DEFAULT_TO = date(2026, 5, 28)
PNL_REPORT_CACHE_VERSION = "v3"
PNL_REPORT_CACHE_TTL = timedelta(hours=24)
PNL_REPORT_STALE_TTL = timedelta(hours=24)


class PlanFactRow(BaseModel):
    rowId: str = Field(min_length=1)
    dimension: PlanFactDimension
    ownerId: str = Field(min_length=1)
    ownerLabel: str = Field(min_length=1)
    metric: Literal["margin_profit_kopecks", "revenue_kopecks"]
    planKopecks: int | None = Field(default=None, ge=0)
    factKopecks: int | None = Field(default=None, ge=0)
    deviationKopecks: int | None = None
    completionPct: float | None = None
    forecastKopecks: int | None = Field(default=None, ge=0)
    minPerDayKopecks: int | None = None
    sourceStatus: Literal["fresh", "partial", "stale", "blocked", "unknown"]
    confidence: Literal["high", "medium", "low", "blocked"]
    blockerIds: list[str] = Field(default_factory=list)


class PlanFactResponse(BaseModel):
    sourceStatus: Literal["fresh", "partial", "stale", "blocked", "unknown"]
    confidence: Literal["high", "medium", "low", "blocked"]
    blockerIds: list[str]
    sourceEvidence: list[SourceEvidence]
    calculatedAt: datetime
    period: DatePeriod
    dimension: PlanFactDimension
    rows: list[PlanFactRow]


class RatingLink(BaseModel):
    kind: Literal["sku_drawer", "repricer", "liquidation"]
    href: str = Field(min_length=1)


class RatingRow(BaseModel):
    skuId: str = Field(min_length=1)
    nmId: int = Field(gt=0)
    group: Literal["locomotive", "profitable", "promising", "weak", "loss_maker", "new"]
    score: int = Field(ge=0, le=100)
    scoreReasons: list[str]
    links: list[RatingLink]
    sourceStatus: Literal["fresh", "partial", "stale", "blocked", "unknown"]
    confidence: Literal["high", "medium", "low", "blocked"]
    blockerIds: list[str] = Field(default_factory=list)


class SkuRatingResponse(BaseModel):
    sourceStatus: Literal["fresh", "partial", "stale", "blocked", "unknown"]
    confidence: Literal["high", "medium", "low", "blocked"]
    blockerIds: list[str]
    sourceEvidence: list[SourceEvidence]
    calculatedAt: datetime
    period: DatePeriod
    rows: list[RatingRow]


class ExportCurrentViewResponse(BaseModel):
    exportState: Literal["ready", "no_access"]
    reason: str | None = None
    fileName: str | None = None
    format: Literal["xlsx"]
    sourceStatus: Literal["fresh", "partial", "stale", "blocked", "unknown"]
    confidence: Literal["high", "medium", "low", "blocked"]
    blockerIds: list[str]
    sourceEvidence: list[SourceEvidence]
    generatedAt: datetime


def _period(date_from: date, date_to: date) -> DatePeriod:
    return DatePeriod(dateFrom=date_from, dateTo=date_to)


def _evidence(source_id: str, source_type: Literal["wb_api", "wb_excel", "manual", "derived", "mock"], source_name: str, fields: list[str]) -> list[SourceEvidence]:
    return [
        SourceEvidence(
            sourceId=source_id,
            sourceType=source_type,
            sourceName=source_name,
            lastSyncedAt=utc_now(),
            freshnessTtlMinutes=1440,
            fieldsUsed=fields,
        )
    ]


def _calc_margin_pct(net_profit_kopecks: int, revenue_kopecks: int) -> float:
    if revenue_kopecks <= 0:
        return 0.0
    return round(net_profit_kopecks / revenue_kopecks * 100, 2)


def _calc_drr_pct(ad_spend_kopecks: int, revenue_kopecks: int) -> float:
    if revenue_kopecks <= 0:
        return 0.0
    return round(ad_spend_kopecks / revenue_kopecks * 100, 2)


def _calc_roi_pct(ad_spend_kopecks: int, revenue_kopecks: int) -> float:
    if ad_spend_kopecks <= 0:
        return 0.0
    return round((revenue_kopecks - ad_spend_kopecks) / ad_spend_kopecks * 100, 2)


def _finance_commission_kopecks(finance: dict[str, Any]) -> int:
    actual = _int_or_zero(finance.get("commissionKopecks"))
    actual_available = (
        _int_or_zero(finance.get("reportedCommissionRows")) > 0
        or finance.get("commissionSource") == "buyerRevenueKopecks-payableKopecks-acquiringKopecks"
        or ("reportedCommissionRows" not in finance and actual != 0)
    )
    return actual if actual_available else _int_or_zero(finance.get("commissionFormulaKopecks"))


def _abc_financial_components(
    *,
    finance: dict[str, Any],
    settings: dict[str, Any],
    ads: dict[str, Any],
    revenue_kopecks: int,
    sales_units: int,
    cogs_kopecks: int | None = None,
) -> dict[str, int]:
    cogs = _nonnegative_int(settings.get("cogsKopecks")) * sales_units if cogs_kopecks is None else cogs_kopecks
    commission = _finance_commission_kopecks(finance)
    logistics = _int_or_zero(finance.get("logisticsKopecks"))
    penalty_signed = _int_or_zero(finance.get("penaltyKopecks"))
    deduction_signed = _int_or_zero(finance.get("deductionKopecks"))
    storage = _int_or_zero(finance.get("storageKopecks"))
    acceptance = _int_or_zero(finance.get("acceptanceKopecks"))
    penalty = max(0, penalty_signed)
    deduction = max(0, deduction_signed)
    additional_payment_signed = _int_or_zero(finance.get("additionalPaymentKopecks"))
    finance_other_expenses = max(0, -additional_payment_signed)
    compensation = max(0, additional_payment_signed) + max(0, -penalty_signed) + max(0, -deduction_signed)
    finance_credits = compensation - finance_other_expenses
    acquiring = _int_or_zero(finance.get("acquiringKopecks"))
    loyalty_cost = _int_or_zero(finance.get("loyaltyCostKopecks"))
    ad_spend = _nonnegative_int(ads.get("adSpendKopecks"))
    other_expenses = (
        _nonnegative_int(settings.get("otherExpensePerSaleKopecks")) * sales_units
        + int(round(revenue_kopecks * _nonnegative_float_or_zero(settings.get("otherExpensePricePct")) / 100))
    )
    tax = int(round(revenue_kopecks * _nonnegative_float_or_zero(settings.get("taxPct")) / 100))
    expenses = cogs + commission + logistics + storage + acceptance + penalty + deduction + finance_other_expenses + acquiring + loyalty_cost + ad_spend + other_expenses + tax - compensation
    net_profit = revenue_kopecks - expenses
    return {
        "revenueKopecks": revenue_kopecks,
        "cogsKopecks": cogs,
        "commissionKopecks": commission,
        "logisticsKopecks": logistics,
        "storageKopecks": storage,
        "acceptanceKopecks": acceptance,
        "penaltyKopecks": penalty,
        "deductionKopecks": deduction,
        "financeCreditsKopecks": finance_credits,
        "financeOtherExpensesKopecks": finance_other_expenses,
        "compensationKopecks": compensation,
        "acquiringKopecks": acquiring,
        "loyaltyCostKopecks": loyalty_cost,
        "adSpendKopecks": ad_spend,
        "otherExpensesKopecks": other_expenses,
        "taxKopecks": tax,
        "netProfitKopecks": net_profit,
    }


def _int_or_zero(value: Any) -> int:
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


def _nonnegative_int(value: Any) -> int:
    return max(0, _int_or_zero(value))


def _float_or_none(value: Any) -> float | None:
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


def _nonnegative_float_or_zero(value: Any) -> float:
    parsed = _float_or_none(value)
    return max(0.0, float(parsed or 0))


def _first_float_or_none(row: dict[str, Any], *keys: str) -> float | None:
    for key in keys:
        value = _float_or_none(row.get(key))
        if value is not None:
            return value
    return None


def _first_nonnegative_int_or_none(row: dict[str, Any], *keys: str) -> int | None:
    value = _first_float_or_none(row, *keys)
    return max(0, int(round(value))) if value is not None else None


def _abc_funnel_impressions(row: dict[str, Any]) -> int | None:
    return _first_nonnegative_int_or_none(
        row,
        "impressions",
        "viewCountTotal",
        "viewCount",
        "views",
        "viewsCount",
        "showCount",
        "showCountTotal",
        "impressionCount",
    )


def _abc_funnel_open_count(row: dict[str, Any]) -> int | None:
    return _first_nonnegative_int_or_none(row, "openCount", "openCardCount", "openCard")


def _abc_funnel_cart_count(row: dict[str, Any]) -> int | None:
    return _first_nonnegative_int_or_none(
        row,
        "cartCount",
        "cartAdds",
        "addToCart",
        "addToCartCount",
        "basketCount",
        "baskets",
    )


def _parse_cache_date(value: Any) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def _cache_matches_range(cache: dict[str, Any], date_from: date, date_to: date) -> bool:
    return str(cache.get("dateFrom") or "") == date_from.isoformat() and str(cache.get("dateTo") or "") == date_to.isoformat()


def _cache_covers_range(cache: dict[str, Any], date_from: date, date_to: date) -> bool:
    cache_from = _parse_cache_date(cache.get("dateFrom"))
    cache_to = _parse_cache_date(cache.get("dateTo"))
    return bool(cache_from and cache_to and cache_from <= date_from and cache_to >= date_to)


def _merge_aggregate_row(target: dict[str, Any], source: dict[str, Any]) -> None:
    for key, value in source.items():
        if key.startswith("_") or value is None:
            continue
        if isinstance(value, bool):
            target[key] = bool(target.get(key)) or value
            continue
        if isinstance(value, (int, float)):
            if key.endswith("Pct") or key in {"sppPct", "commissionPct", "discountPct", "buyoutPct"}:
                target[key] = value
            else:
                target[key] = target.get(key, 0) + value
            continue
        if key not in target:
            target[key] = value


def _rollup_daily_aggregates(daily_aggregates: dict[str, Any], date_from: date, date_to: date) -> dict[str, dict[str, Any]]:
    rolled: dict[str, dict[str, Any]] = {}
    for day_key, day_rows in daily_aggregates.items():
        day = _parse_cache_date(day_key)
        if day is None or day < date_from or day > date_to or not isinstance(day_rows, dict):
            continue
        for nm_id, source_row in day_rows.items():
            if not isinstance(source_row, dict):
                continue
            row = rolled.setdefault(str(nm_id), {})
            _merge_aggregate_row(row, source_row)
    return rolled


def _slice_daily_aggregates(daily_aggregates: dict[str, Any], date_from: date, date_to: date) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for day_key, day_rows in daily_aggregates.items():
        day = _parse_cache_date(day_key)
        if day is not None and date_from <= day <= date_to:
            result[str(day_key)] = day_rows
    return result


def _covered_cache_from_daily(
    cache: dict[str, Any],
    *,
    prefix: str,
    suffix: str,
    resolved_days: int,
    date_from: date,
    date_to: date,
) -> dict[str, Any]:
    if not _cache_covers_range(cache, date_from, date_to):
        return {}
    daily_aggregates = cache.get("dailyAggregates")
    if not isinstance(daily_aggregates, dict):
        return {}
    aggregates = _rollup_daily_aggregates(daily_aggregates, date_from, date_to)
    if not aggregates and cache.get("aggregates"):
        return {}
    payload = dict(cache)
    payload["aggregates"] = aggregates
    payload["count"] = len(aggregates)
    payload["dateFrom"] = date_from.isoformat()
    payload["dateTo"] = date_to.isoformat()
    payload["periodDays"] = resolved_days
    payload["periodCacheSuffix"] = suffix
    payload["dailyAggregates"] = _slice_daily_aggregates(daily_aggregates, date_from, date_to)
    payload["coveredByCache"] = {
        "source": prefix,
        "dateFrom": cache.get("dateFrom"),
        "dateTo": cache.get("dateTo"),
        "periodDays": cache.get("periodDays"),
        "periodCacheSuffix": cache.get("periodCacheSuffix"),
    }
    return payload


def _sync_status_covering_keys(organization_id: int, prefix: str, date_from: date, date_to: date) -> list[str]:
    status = get_source_cache(organization_id, "wb_sync_status", slim=False) or {}
    if not isinstance(status, dict) or not _cache_covers_range(status, date_from, date_to):
        return []
    keys: list[str] = []
    suffix = str(status.get("periodCacheSuffix") or "").strip()
    if suffix:
        keys.append(f"{prefix}_{suffix}")
    period_days = status.get("periodDays")
    if period_days:
        keys.append(f"{prefix}_{period_days}")
    return list(dict.fromkeys(keys))


def _source_cache_covering_keys(organization_id: int, prefix: str, date_from: date, date_to: date) -> list[str]:
    keys: list[str] = []
    for cache in list_source_cache_ranges_by_prefix(organization_id, f"{prefix}_", limit=200):
        if not isinstance(cache, dict):
            continue
        cache_from = _parse_cache_date(cache.get("dateFrom"))
        cache_to = _parse_cache_date(cache.get("dateTo"))
        source_key = str(cache.get("sourceKey") or "")
        if cache_from and cache_to and cache_from <= date_from and cache_to >= date_to and source_key:
            keys.append(source_key)
    return list(dict.fromkeys(keys))


def _enrich_cache_with_covering_daily_aggregates(
    organization_id: int,
    prefix: str,
    cache: dict[str, Any],
    *,
    suffix: str,
    resolved_days: int,
    date_from: date,
    date_to: date,
) -> dict[str, Any]:
    if prefix != "baskets":
        return cache
    if isinstance(cache.get("dailyAggregates"), dict) and cache["dailyAggregates"]:
        return cache
    current_keys = {f"{prefix}_{suffix}", f"{prefix}_{resolved_days}"}
    for covering_key in [
        *_sync_status_covering_keys(organization_id, prefix, date_from, date_to),
        *_source_cache_covering_keys(organization_id, prefix, date_from, date_to),
    ]:
        if covering_key in current_keys:
            continue
        covering = get_source_cache(organization_id, covering_key, slim=False) or {}
        rolled = _covered_cache_from_daily(
            covering,
            prefix=prefix,
            suffix=suffix,
            resolved_days=resolved_days,
            date_from=date_from,
            date_to=date_to,
        )
        daily_aggregates = rolled.get("dailyAggregates") if isinstance(rolled, dict) else None
        if isinstance(daily_aggregates, dict) and daily_aggregates:
            enriched = dict(cache)
            enriched["dailyAggregates"] = daily_aggregates
            enriched["dailyCoveredByCache"] = rolled.get("coveredByCache")
            return enriched
    return cache


def _compatible_period_cache(cache: dict[str, Any], *, require_current_finance_basis: bool) -> dict[str, Any]:
    return cache if not require_current_finance_basis or finance_cache_uses_current_revenue_basis(cache) else {}


def _period_cache(
    organization_id: int,
    prefix: str,
    date_from: date,
    date_to: date,
    *,
    require_current_finance_basis: bool = False,
) -> dict[str, Any]:
    require_current_finance_basis = require_current_finance_basis or prefix == "finance"
    try:
        _range_start, _range_end, resolved_days = _normalize_period_range(30, date_from=date_from, date_to=date_to)
    except ValueError:
        return {}
    suffix = _period_cache_suffix(resolved_days, date_from=date_from, date_to=date_to)
    exact = _compatible_period_cache(
        get_source_cache(organization_id, f"{prefix}_{suffix}", slim=False) or {},
        require_current_finance_basis=require_current_finance_basis,
    )
    if exact:
        has_range = bool(exact.get("dateFrom") or exact.get("dateTo"))
        if not has_range or _cache_matches_range(exact, date_from, date_to):
            return _enrich_cache_with_covering_daily_aggregates(
                organization_id,
                prefix,
                exact,
                suffix=suffix,
                resolved_days=resolved_days,
                date_from=date_from,
                date_to=date_to,
            )
        rolled_exact = _covered_cache_from_daily(
            exact,
            prefix=prefix,
            suffix=suffix,
            resolved_days=resolved_days,
            date_from=date_from,
            date_to=date_to,
        )
        if rolled_exact:
            return rolled_exact
    fallback = _compatible_period_cache(
        get_source_cache(organization_id, f"{prefix}_{resolved_days}", slim=False) or {},
        require_current_finance_basis=require_current_finance_basis,
    )
    if fallback:
        has_range = bool(fallback.get("dateFrom") or fallback.get("dateTo"))
        if not has_range or _cache_matches_range(fallback, date_from, date_to):
            return _enrich_cache_with_covering_daily_aggregates(
                organization_id,
                prefix,
                fallback,
                suffix=suffix,
                resolved_days=resolved_days,
                date_from=date_from,
                date_to=date_to,
            )
    for covering_key in _sync_status_covering_keys(organization_id, prefix, date_from, date_to):
        if covering_key in {f"{prefix}_{suffix}", f"{prefix}_{resolved_days}"}:
            continue
        covering = _compatible_period_cache(
            get_source_cache(organization_id, covering_key, slim=False) or {},
            require_current_finance_basis=require_current_finance_basis,
        )
        rolled = _covered_cache_from_daily(
            covering,
            prefix=prefix,
            suffix=suffix,
            resolved_days=resolved_days,
            date_from=date_from,
            date_to=date_to,
        )
        if rolled:
            return rolled
    for covering_key in _source_cache_covering_keys(organization_id, prefix, date_from, date_to):
        if covering_key in {f"{prefix}_{suffix}", f"{prefix}_{resolved_days}"}:
            continue
        covering = _compatible_period_cache(
            get_source_cache(organization_id, covering_key, slim=False) or {},
            require_current_finance_basis=require_current_finance_basis,
        )
        rolled = _covered_cache_from_daily(
            covering,
            prefix=prefix,
            suffix=suffix,
            resolved_days=resolved_days,
            date_from=date_from,
            date_to=date_to,
        )
        if rolled:
            return rolled
    return {}


def _pnl_report_cache_key(
    *,
    date_from: date,
    date_to: date,
    group_by: ReportGroupBy,
    requested_state: PnlRequestedState,
    finance_allowed: bool,
) -> str:
    raw = "|".join(
        [
            PNL_REPORT_CACHE_VERSION,
            date_from.isoformat(),
            date_to.isoformat(),
            str(group_by),
            str(requested_state),
            "finance" if finance_allowed else "nofinance",
        ]
    )
    return f"pnl_report_{sha1(raw.encode('utf-8')).hexdigest()[:16]}"


def _parse_cache_datetime(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _get_cached_pnl_response(
    *,
    organization_id: int,
    cache_key: str,
) -> PnlReportResponse | None:
    cache = get_source_cache(organization_id, cache_key, slim=False) or {}
    fetched_at = _parse_cache_datetime(cache.get("fetchedAt"))
    if fetched_at is None:
        return None
    report = cache.get("report")
    if not isinstance(report, dict):
        return None
    age = datetime.now(timezone.utc) - fetched_at
    if age > PNL_REPORT_STALE_TTL:
        return None
    try:
        cached_report = PnlReportResponse.model_validate(report)
    except ValueError:
        return None
    if age <= PNL_REPORT_CACHE_TTL:
        return cached_report
    return _mark_pnl_report_stale(cached_report)


def _mark_pnl_report_stale(report: PnlReportResponse) -> PnlReportResponse:
    payload = report.model_dump(mode="json")
    payload["sourceStatus"] = "stale"
    if payload.get("reportState") == "final":
        payload["reportState"] = "preliminary"
    if payload.get("confidence") == "high":
        payload["confidence"] = "medium"
    totals = payload.get("totals")
    if isinstance(totals, dict):
        totals["sourceStatus"] = "stale"
        if totals.get("confidence") == "high":
            totals["confidence"] = "medium"
    for row in payload.get("rows") or []:
        if not isinstance(row, dict):
            continue
        row["sourceStatus"] = "stale"
        if row.get("confidence") == "high":
            row["confidence"] = "medium"
    day_allocation = payload.get("dayAllocation")
    if isinstance(day_allocation, dict):
        day_allocation["sourceStatus"] = "stale"
    return PnlReportResponse.model_validate(payload)


def _save_pnl_response_cache(
    *,
    organization_id: int,
    cache_key: str,
    report: PnlReportResponse,
) -> None:
    save_source_cache(
        organization_id,
        cache_key,
        {
            "ttlSeconds": int(PNL_REPORT_CACHE_TTL.total_seconds()),
            "staleTtlSeconds": int(PNL_REPORT_STALE_TTL.total_seconds()),
            "report": report.model_dump(mode="json"),
        },
    )


def _goods_index(organization_id: int, content_cards_cache: dict[str, Any] | None = None) -> dict[int, dict[str, Any]]:
    result: dict[int, dict[str, Any]] = {}
    for good in list_cached_goods(organization_id):
        nm_id = _int_or_zero(good.get("nmID") or good.get("nmId"))
        if nm_id <= 0:
            continue
        result[nm_id] = good
    cards = (content_cards_cache if content_cards_cache is not None else get_source_cache(organization_id, "content_cards", slim=False) or {}).get("cards") or []
    for card in cards:
        if not isinstance(card, dict):
            continue
        nm_id = _int_or_zero(card.get("nmID") or card.get("nmId"))
        if nm_id <= 0:
            continue
        good = result.get(nm_id, {})
        merged = {**good, **{key: value for key, value in card.items() if value is not None}}
        for key in (
            "sizes",
            "discountedPrice",
            "price",
            "buyerPriceNoWalletKopecks",
            "buyerPriceNoWallet",
            "buyerPriceKopecks",
            "buyerPrice",
            "clientPrice",
        ):
            if good.get(key) is not None:
                merged[key] = good[key]
        result[nm_id] = merged
    return result


def _photo_url_for_good(good: dict[str, Any], nm_id: int) -> str | None:
    return _extract_wb_media_url(good, nm_id)


def _sku_settings(
    organization_id: int,
    article_id: str,
) -> dict[str, Any]:
    runtime = load_runtime_state(organization_id) or {}
    algorithm = dict(DEFAULT_ALGORITHM_SETTINGS)
    algorithm.update(load_algorithm_settings(organization_id) or {})
    return _sku_settings_from_state(article_id, runtime=runtime, algorithm=algorithm)


def _sku_settings_from_state(
    article_id: str,
    *,
    runtime: dict[str, Any],
    algorithm: dict[str, Any],
    effective_on: date | None = None,
) -> dict[str, Any]:
    defaults = dict(TYPE_DEFAULTS.get(_article_type(article_id), TYPE_DEFAULTS["F"]))
    cogs_source = "type_default"
    cogs_effective_from: str | None = None
    cogs_key = {"F": "tshirt", "H": "hoodie", "L": "longsleeve"}.get(_article_type(article_id))
    cogs_by_garment = algorithm.get("cogsByGarmentRub")
    if cogs_key and isinstance(cogs_by_garment, dict):
        cogs_rub = _float_or_none(cogs_by_garment.get(cogs_key))
        if cogs_rub and cogs_rub > 0:
            defaults["cogsKopecks"] = int(round(cogs_rub * 100))
            cogs_source = "algorithm_garment"

    garment_history = (algorithm.get("cogsByGarmentHistory") or {}).get(cogs_key) if cogs_key else None
    if effective_on is not None and isinstance(garment_history, list):
        effective_entries = []
        for index, entry in enumerate(garment_history):
            if not isinstance(entry, dict) or "cogsRub" not in entry:
                continue
            effective_from = _parse_cache_date(entry.get("effectiveFrom")) or date.min
            if effective_from <= effective_on:
                effective_entries.append((effective_from, index, entry))
        if effective_entries:
            _effective_from, _index, entry = max(effective_entries, key=lambda item: item[:2])
            cogs_rub = _float_or_none(entry.get("cogsRub"))
            if cogs_rub is not None and cogs_rub > 0:
                defaults["cogsKopecks"] = int(round(cogs_rub * 100))
                cogs_source = "algorithm_garment_history"
            else:
                cogs_source = "type_default_after_algorithm_override"
            cogs_effective_from = entry.get("effectiveFrom")

    settings = {
        "cogsKopecks": int(defaults.get("cogsKopecks") or 0),
        "taxPct": float(_float_or_none(algorithm.get("taxPct")) or 0),
        "otherExpensePricePct": float(_float_or_none(algorithm.get("otherExpensePricePct")) or 0),
        "otherExpensePerSaleKopecks": int(round(float(_float_or_none(algorithm.get("otherExpensePerSaleRub")) or 0) * 100)),
    }
    base_cogs_kopecks = settings["cogsKopecks"]
    base_cogs_source = cogs_source
    base_cogs_effective_from = cogs_effective_from
    overrides = (runtime.get("skuSettingsOverrides") or {}).get(article_id)
    if isinstance(overrides, dict):
        for key in ("cogsKopecks", "taxPct", "otherExpensePricePct", "otherExpensePerSaleKopecks"):
            if overrides.get(key) is not None:
                settings[key] = overrides[key]
        if overrides.get("cogsKopecks") is not None:
            cogs_source = "sku_override"
            cogs_effective_from = None

    history = (runtime.get("cogsHistory") or {}).get(article_id)
    if effective_on is not None and isinstance(history, list):
        effective_entries = []
        for index, entry in enumerate(history):
            if not isinstance(entry, dict) or "cogsKopecks" not in entry:
                continue
            effective_from = _parse_cache_date(entry.get("effectiveFrom")) or date.min
            if effective_from <= effective_on:
                effective_entries.append((effective_from, index, entry))
        if effective_entries:
            _effective_from, _index, entry = max(effective_entries, key=lambda item: item[:2])
            if entry.get("cogsKopecks") is not None:
                settings["cogsKopecks"] = entry["cogsKopecks"]
                cogs_source = "sku_history"
            else:
                settings["cogsKopecks"] = base_cogs_kopecks
                cogs_source = f"{base_cogs_source}_after_sku_override"
                cogs_effective_from = (
                    max((base_cogs_effective_from, entry.get("effectiveFrom")), key=lambda raw: _parse_cache_date(raw) or date.min)
                    if base_cogs_effective_from and entry.get("effectiveFrom")
                    else None
                )
            if entry.get("cogsKopecks") is not None:
                cogs_effective_from = entry.get("effectiveFrom")
    settings["cogsSource"] = cogs_source
    settings["cogsEffectiveFrom"] = cogs_effective_from
    return settings


def _abc_period_cogs(
    *,
    nm_id: int,
    article_id: str,
    finance: dict[str, Any],
    finance_cache: dict[str, Any],
    runtime: dict[str, Any],
    algorithm: dict[str, Any],
    date_from: date,
    date_to: date,
) -> tuple[int, dict[str, Any]]:
    net_units = _int_or_zero(finance.get("netSalesUnits")) if "netSalesUnits" in finance else _int_or_zero(finance.get("salesUnits")) - _int_or_zero(finance.get("returnsUnits"))
    end_settings = _sku_settings_from_state(
        article_id,
        runtime=runtime,
        algorithm=algorithm,
        effective_on=date_to,
    )
    end_settings["cogsEvidenceStatus"] = "dated" if end_settings.get("cogsEffectiveFrom") else "undated"
    daily = finance_cache.get("dailyAggregates")
    if not isinstance(daily, dict):
        end_settings["cogsEvidenceStatus"] = "period_end_fallback"
        end_settings["cogsSource"] = f"{end_settings['cogsSource']}_period_end_fallback"
        return _nonnegative_int(end_settings.get("cogsKopecks")) * net_units, end_settings

    daily_units = 0
    cogs = 0
    has_undated_units = False
    for day_key, rows in daily.items():
        day = _parse_cache_date(day_key)
        row = rows.get(str(nm_id)) if isinstance(rows, dict) else None
        if day is None or day < date_from or day > date_to or not isinstance(row, dict):
            continue
        units = _int_or_zero(row.get("netSalesUnits")) if "netSalesUnits" in row else _int_or_zero(row.get("salesUnits")) - _int_or_zero(row.get("returnsUnits"))
        daily_units += units
        settings = _sku_settings_from_state(
            article_id,
            runtime=runtime,
            algorithm=algorithm,
            effective_on=day,
        )
        has_undated_units = has_undated_units or (units != 0 and not settings.get("cogsEffectiveFrom"))
        cogs += _nonnegative_int(settings.get("cogsKopecks")) * units
    if daily_units == net_units:
        if has_undated_units or not end_settings.get("cogsEffectiveFrom"):
            end_settings["cogsEvidenceStatus"] = "undated"
            end_settings["cogsSource"] = f"{end_settings['cogsSource']}_undated"
        return cogs, end_settings
    end_settings["cogsEvidenceStatus"] = "period_end_fallback"
    end_settings["cogsSource"] = f"{end_settings['cogsSource']}_period_end_fallback"
    return _nonnegative_int(end_settings.get("cogsKopecks")) * net_units, end_settings


def _sku_meta(
    organization_id: int,
    article_id: str,
) -> dict[str, Any]:
    runtime = load_runtime_state(organization_id) or {}
    return _sku_meta_from_state(article_id, runtime=runtime)


def _sku_meta_from_state(article_id: str, *, runtime: dict[str, Any]) -> dict[str, Any]:
    overrides = (runtime.get("skuMetaOverrides") or {}).get(article_id)
    return overrides if isinstance(overrides, dict) else {}


def _label_for_group(
    group_by: ReportGroupBy,
    *,
    nm_id: int,
    article_id: str,
    good: dict[str, Any],
    meta: dict[str, Any],
) -> tuple[str, str, str | None, str | None, str | None]:
    brand = str(good.get("brand") or meta.get("brand") or "unknown-brand")
    manager = str(meta.get("managerId") or "unassigned")
    category = str(good.get("subjectName") or good.get("subject") or "unknown-category")
    status = str(meta.get("status") or "unknown-status")
    sku = article_id or f"NM_{nm_id}"
    if group_by == "brand":
        return f"brand-{brand}", brand, f"brand-{brand}", None, None
    if group_by == "manager":
        return f"manager-{manager}", manager, None, manager, None
    if group_by == "category":
        return f"category-{category}", category, brand, manager, None
    if group_by == "status":
        return f"status-{status}", status, brand, manager, None
    return f"nm-{nm_id}", sku, brand, manager, sku


def _add_amount(target: dict[str, Any], key: str, amount: int) -> None:
    target[key] = _int_or_zero(target.get(key)) + amount


_PNL_NONNEGATIVE_AMOUNT_KEYS = (
    "revenueKopecks",
    "cogsKopecks",
    "commissionKopecks",
    "logisticsKopecks",
    "storageKopecks",
    "adSpendKopecks",
    "taxKopecks",
    "overheadKopecks",
)


def _normalize_pnl_row_amounts(row: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(row)
    for key in _PNL_NONNEGATIVE_AMOUNT_KEYS:
        normalized[key] = max(0, _int_or_zero(normalized.get(key)))
    normalized["netProfitKopecks"] = _int_or_zero(normalized.get("netProfitKopecks"))
    return normalized


def _build_cached_pnl_report(
    *,
    organization_id: int,
    date_from: date,
    date_to: date,
    group_by: ReportGroupBy,
    requested_state: PnlRequestedState,
    finance_allowed: bool,
) -> PnlReportResponse | None:
    finance_cache = _period_cache(organization_id, "finance", date_from, date_to)
    aggregates = finance_cache.get("aggregates") if isinstance(finance_cache.get("aggregates"), dict) else {}
    if not aggregates:
        return None

    ads_cache = _period_cache(organization_id, "ads", date_from, date_to)
    ads_aggregates = ads_cache.get("aggregates") if isinstance(ads_cache.get("aggregates"), dict) else {}
    content_cards_cache = get_source_cache(organization_id, "content_cards", slim=False) or {}
    goods_by_nm = _goods_index(organization_id, content_cards_cache)
    runtime = load_runtime_state(organization_id) or {}
    algorithm = dict(DEFAULT_ALGORITHM_SETTINGS)
    algorithm.update(load_algorithm_settings(organization_id) or {})
    rows_by_key: dict[str, dict[str, Any]] = {}

    for raw_nm_id, finance in aggregates.items():
        if not isinstance(finance, dict):
            continue
        nm_id = _int_or_zero(raw_nm_id)
        if nm_id <= 0:
            nm_id = _int_or_zero(finance.get("nmId") or finance.get("nmID"))
        if nm_id <= 0:
            continue

        good = goods_by_nm.get(nm_id, {})
        article_id = str(good.get("vendorCode") or finance.get("vendorCode") or finance.get("sku") or f"NM_{nm_id}").strip()
        meta = _sku_meta_from_state(article_id, runtime=runtime)
        settings = _sku_settings_from_state(article_id, runtime=runtime, algorithm=algorithm)
        group_key, label, brand_id, manager_id, sku_id = _label_for_group(
            group_by,
            nm_id=nm_id,
            article_id=article_id,
            good=good,
            meta=meta,
        )

        sales_units = max(0, _int_or_zero(finance.get("salesUnits")))
        returns_units = max(0, _int_or_zero(finance.get("returnsUnits")))
        net_sales_units = max(0, sales_units - returns_units)
        revenue = _int_or_zero(finance.get("sellerRevenueKopecks") or finance.get("revenueGrossKopecks"))
        revenue_base = max(0, revenue)
        cogs = _nonnegative_int(settings.get("cogsKopecks")) * net_sales_units
        commission = max(0, _finance_commission_kopecks(finance))
        logistics = _nonnegative_int(finance.get("logisticsKopecks"))
        penalty_signed = _int_or_zero(finance.get("penaltyKopecks"))
        deduction_signed = _int_or_zero(finance.get("deductionKopecks"))
        storage = (
            _nonnegative_int(finance.get("storageKopecks"))
            + _nonnegative_int(finance.get("acceptanceKopecks"))
            + max(0, penalty_signed)
            + max(0, deduction_signed)
            + _nonnegative_int(finance.get("loyaltyCostKopecks"))
        )
        finance_credits = _nonnegative_int(finance.get("additionalPaymentKopecks")) + max(0, -penalty_signed) + max(0, -deduction_signed)
        acquiring = _nonnegative_int(finance.get("acquiringKopecks"))
        ads_row = ads_aggregates.get(str(nm_id)) if isinstance(ads_aggregates.get(str(nm_id)), dict) else {}
        ads = _nonnegative_int(
            finance.get("adSpendKopecks")
            if finance.get("financeAdSpendAuthoritative")
            else ads_row.get("adSpendKopecks") if isinstance(ads_row, dict) else 0
        )
        other_expenses = (
            _nonnegative_int(settings.get("otherExpensePerSaleKopecks")) * sales_units
            + int(round(revenue_base * _nonnegative_float_or_zero(settings.get("otherExpensePricePct")) / 100))
        )
        tax = int(round(revenue_base * _nonnegative_float_or_zero(settings.get("taxPct")) / 100))
        overhead = other_expenses
        net_profit = revenue - (cogs + commission + logistics + storage + acquiring + ads + tax + overhead - finance_credits)

        row = rows_by_key.setdefault(
            group_key,
            {
                "rowId": group_key,
                "label": label,
                "brandId": brand_id,
                "managerId": manager_id,
                "skuId": sku_id,
                "revenueKopecks": 0,
                "cogsKopecks": 0,
                "commissionKopecks": 0,
                "logisticsKopecks": 0,
                "storageKopecks": 0,
                "adSpendKopecks": 0,
                "taxKopecks": 0,
                "overheadKopecks": 0,
                "netProfitKopecks": 0,
            },
        )
        for key, amount in (
            ("revenueKopecks", revenue),
            ("cogsKopecks", cogs),
            ("commissionKopecks", commission),
            ("logisticsKopecks", logistics),
            ("storageKopecks", storage),
            ("adSpendKopecks", ads),
            ("taxKopecks", tax),
            ("overheadKopecks", overhead),
            ("netProfitKopecks", net_profit),
        ):
            _add_amount(row, key, amount)

    if not rows_by_key:
        return None

    finance_ads_authoritative = any(
        isinstance(row, dict) and row.get("financeAdSpendAuthoritative") for row in aggregates.values()
    )
    ads_blockers = [] if ads_cache or finance_ads_authoritative else ["WB-02"]
    source_status: Literal["fresh", "partial", "stale", "blocked", "unknown"] = "fresh" if not ads_blockers else "partial"
    confidence: Literal["high", "medium", "low", "blocked"] = "high" if source_status == "fresh" else "medium"
    if not finance_allowed:
        source_status = "partial"
        confidence = "medium"

    rows: list[PnlRow] = []
    for raw_row in sorted(rows_by_key.values(), key=lambda item: str(item["label"])):
        row = _normalize_pnl_row_amounts(raw_row)
        rows.append(
            PnlRow(
                **{
                    **row,
                    "overheadKopecks": row["overheadKopecks"] if finance_allowed else None,
                    "marginPct": _calc_margin_pct(_int_or_zero(row["netProfitKopecks"]), _int_or_zero(row["revenueKopecks"])),
                    "sourceStatus": source_status,
                    "confidence": confidence,
                }
            )
        )

    total_revenue = sum(_int_or_zero(row.revenueKopecks) for row in rows)
    total_net_profit = sum(_int_or_zero(row.netProfitKopecks) for row in rows)
    total_storage = sum(_int_or_zero(row.storageKopecks) for row in rows)
    total_tax = sum(_int_or_zero(row.taxKopecks) for row in rows)
    total_overhead = sum(_int_or_zero(row.overheadKopecks) for row in rows)
    blockers = sorted(set(ads_blockers))
    report_state: Literal["operative", "preliminary", "final", "blocked"] = requested_state
    if requested_state == "final" and blockers:
        report_state = "preliminary"

    fetched_at = finance_cache.get("fetchedAt")
    evidence_synced_at = None
    if isinstance(fetched_at, str):
        try:
            evidence_synced_at = datetime.fromisoformat(fetched_at)
        except ValueError:
            evidence_synced_at = None

    source_evidence = [
        SourceEvidence(
            sourceId="wb-finance-sales-reports-detailed-cache",
            sourceType="wb_api",
            sourceName="WB Finance /api/finance/v1/sales-reports/detailed cached by repricer sync",
            lastSyncedAt=evidence_synced_at or utc_now(),
            freshnessTtlMinutes=1440,
            fieldsUsed=[
                "sellerRevenueKopecks",
                "buyerRevenueKopecks",
                "commissionKopecks",
                "commissionFormulaKopecks",
                "logisticsKopecks",
                "storageKopecks",
                "acceptanceKopecks",
                "penaltyKopecks",
                "deductionKopecks",
                "additionalPaymentKopecks",
                "rewardAdjustmentKopecks",
                "paymentScheduleKopecks",
                "cashbackAmountKopecks",
                "cashbackCommissionChangeKopecks",
                "loyaltyCostKopecks",
                "adSpendKopecks",
                "acquiringKopecks",
                "salesUnits",
            ],
        ),
    ]
    if finance_ads_authoritative:
        source_evidence.extend(
            _evidence(
                "wb-finance-promotion-deduction",
                "wb_api",
                "WB Promotion deduction from final finance report",
                ["adSpendKopecks"],
            )
        )
    elif ads_cache:
        source_evidence.extend(
            _evidence(
                "wb-ads-attribution-cache",
                "wb_api",
                "WB Ads spend cached by repricer sync",
                ["adSpendKopecks"],
            )
        )
    else:
        source_evidence.extend(
            _evidence(
                "wb-ads-attribution-cache",
                "wb_api",
                "WB Ads spend cache is absent; SKU ad spend is reported as no cached spend and P&L is partial",
                ["adSpendKopecks"],
            )
        )
    source_evidence.extend(
        _evidence(
            "wb-pnl-runtime",
            "derived",
            "Runtime P&L from repricer source cache and SKU settings",
            ["finance_aggregates", "sku_settings", "ads_aggregates", "netProfit"],
        )
    )

    return PnlReportResponse(
        sourceStatus=source_status,
        confidence=confidence,
        blockerIds=blockers,
        sourceEvidence=source_evidence,
        calculatedAt=utc_now(),
        period=_period(date_from, date_to),
        reportState=report_state,
        groupBy=group_by,
        totals=PnlTotals(
            revenueKopecks=total_revenue,
            netProfitKopecks=total_net_profit,
            marginPct=_calc_margin_pct(total_net_profit, total_revenue),
            sourceStatus=source_status,
            confidence=confidence,
        ),
        rows=rows,
        fieldMapping=_pnl_field_mapping(),
        manualCosts=[
            ManualCost(costId="storage", label="Storage/acceptance/penalties/deductions", amountKopecks=total_storage, allocationBase="sku", sourceStatus="fresh", blockerIds=[]),
            ManualCost(costId="tax", label="Tax", amountKopecks=total_tax, allocationBase="sku", sourceStatus="fresh", blockerIds=[]),
            ManualCost(
                costId="overhead",
                label="Operating expenses",
                amountKopecks=total_overhead if finance_allowed else None,
                allocationBase="sku",
                sourceStatus="fresh" if finance_allowed else "partial",
                blockerIds=[],
            ),
        ],
        dayAllocation=DayAllocationSummary(
            allocationDateField="saleDt/rrDate",
            expenseDateField="rrDate",
            rule="finance detailed rows are aggregated by nmId inside the selected report period; SKU manual costs use the same period and sales units",
            sourceStatus=source_status,
            blockerIds=blockers,
        ),
    )


def _pnl_field_mapping() -> list[PnlFieldMapping]:
    return [
        PnlFieldMapping(
            metricId="revenue",
            metricLabel="Revenue",
            sourceId="wb-finance-sales-reports-detailed-cache",
            sourceField="retailAmount",
            formula="revenueKopecks = sum(finance.sellerRevenueKopecks) by nmId",
            fallback="period_stats.revenueKopecks, then no_data",
            blockerIds=[],
        ),
        PnlFieldMapping(
            metricId="cogs",
            metricLabel="COGS",
            sourceId="repricer-sku-settings",
            sourceField="cogsKopecks",
            formula="cogsKopecks = SKU settings/imported cogsKopecks * max(finance.salesUnits - finance.returnsUnits, 0)",
            fallback="type defaults from repricer settings",
            blockerIds=[],
        ),
        PnlFieldMapping(
            metricId="commission",
            metricLabel="Commission expense",
            sourceId="wb-finance-sales-reports-detailed-cache",
            sourceField="commissionPercent/ppvzSalesCommission",
            formula="commissionKopecks = reported ppvzSalesCommission when available, else commissionFormulaKopecks",
            fallback="нет данных",
            blockerIds=[],
        ),
        PnlFieldMapping(
            metricId="logistics",
            metricLabel="Logistics expense",
            sourceId="wb-finance-sales-reports-detailed-cache",
            sourceField="rebillLogisticCost/deliveryAmount/deliveryService",
            formula="logisticsKopecks uses monetary logistics fields; dlv_prc is not used as ruble logistics",
            fallback="нет данных",
            blockerIds=[],
        ),
        PnlFieldMapping(
            metricId="storage",
            metricLabel="Storage, acceptance and WB adjustments",
            sourceId="wb-finance-sales-reports-detailed-cache",
            sourceField="paidStorage/paidAcceptance/penalty/deduction/additionalPayment/paymentSchedule/cashbackAmount/cashbackCommissionChange",
            formula="storage line = storage + acceptance + signed penalty + signed deduction + loyalty costs; normalized additionalPayment credits reduce net expense",
            fallback="manual_input",
            blockerIds=[],
        ),
        PnlFieldMapping(
            metricId="ads",
            metricLabel="Ads spend",
            sourceId="wb-ads-attribution-cache",
            sourceField="adSpendKopecks",
            formula="finance WB Promotion deduction when available; otherwise adSpendKopecks from ads_{period}",
            fallback="WB Ads runtime attribution snapshot or zero when no matching SKU spend",
            blockerIds=[],
        ),
        PnlFieldMapping(
            metricId="tax",
            metricLabel="Tax expense",
            sourceId="repricer-algorithm-settings",
            sourceField="taxPct",
            formula="taxKopecks = sellerRevenueKopecks * taxPct / 100",
            fallback="manual taxPct setting",
            blockerIds=[],
        ),
        PnlFieldMapping(
            metricId="overhead",
            metricLabel="Operating expenses",
            sourceId="repricer-sku-settings",
            sourceField="otherExpensePerSaleKopecks/otherExpensePricePct",
            formula="overheadKopecks = otherExpensePerSaleKopecks * salesUnits + revenue * otherExpensePricePct / 100; hidden without finance:read",
            fallback="0",
            blockerIds=[],
        ),
    ]


def _empty_pnl_report_from_cache_miss(
    *,
    date_from: date,
    date_to: date,
    group_by: ReportGroupBy,
    requested_state: PnlRequestedState,
    finance_allowed: bool,
) -> PnlReportResponse:
    blockers = ["WB_PNL_FINANCE_CACHE_MISSING"]
    return PnlReportResponse(
        sourceStatus="blocked",
        confidence="blocked",
        blockerIds=blockers,
        sourceEvidence=_evidence(
            "wb-pnl-cache-miss",
            "derived",
            "P&L report is cache-only; repricer finance cache is missing for the selected period",
            ["finance_aggregates", "ads_aggregates", "sku_settings"],
        ),
        calculatedAt=utc_now(),
        period=_period(date_from, date_to),
        reportState="blocked",
        groupBy=group_by,
        totals=PnlTotals(
            revenueKopecks=0,
            netProfitKopecks=0,
            marginPct=None,
            sourceStatus="blocked",
            confidence="blocked",
        ),
        rows=[],
        fieldMapping=_pnl_field_mapping(),
        manualCosts=[
            ManualCost(costId="storage", label="Storage/acceptance/penalties/deductions", amountKopecks=0, allocationBase="sku", sourceStatus="blocked", blockerIds=blockers),
            ManualCost(costId="tax", label="Tax", amountKopecks=0, allocationBase="sku", sourceStatus="blocked", blockerIds=blockers),
            ManualCost(
                costId="overhead",
                label="Operating expenses",
                amountKopecks=0 if finance_allowed else None,
                allocationBase="sku",
                sourceStatus="blocked",
                blockerIds=blockers,
            ),
        ],
        dayAllocation=DayAllocationSummary(
            allocationDateField="saleDt/rrDate",
            expenseDateField="rrDate",
            rule="P&L waits for cached finance aggregates produced by WB sync; report runtime does not fetch WB directly",
            sourceStatus="blocked",
            blockerIds=blockers,
        ),
    )


def build_pnl_report(
    date_from: date,
    date_to: date,
    group_by: ReportGroupBy,
    requested_state: PnlRequestedState,
    finance_allowed: bool,
    organization_id: int | None = None,
    wb_token: str | None = None,
    progress_callback: Any | None = None,
) -> PnlReportResponse:
    pnl_cache_key = None
    if organization_id is not None:
        pnl_cache_key = _pnl_report_cache_key(
            date_from=date_from,
            date_to=date_to,
            group_by=group_by,
            requested_state=requested_state,
            finance_allowed=finance_allowed,
        )
        cached_pnl = _get_cached_pnl_response(organization_id=organization_id, cache_key=pnl_cache_key)
        if cached_pnl is not None:
            return cached_pnl

        cached_report = _build_cached_pnl_report(
            organization_id=organization_id,
            date_from=date_from,
            date_to=date_to,
            group_by=group_by,
            requested_state=requested_state,
            finance_allowed=finance_allowed,
        )
        if cached_report is not None:
            _save_pnl_response_cache(organization_id=organization_id, cache_key=pnl_cache_key, report=cached_report)
            return cached_report
        return _empty_pnl_report_from_cache_miss(
            date_from=date_from,
            date_to=date_to,
            group_by=group_by,
            requested_state=requested_state,
            finance_allowed=finance_allowed,
        )

    return _empty_pnl_report_from_cache_miss(
        date_from=date_from,
        date_to=date_to,
        group_by=group_by,
        requested_state=requested_state,
        finance_allowed=finance_allowed,
    )

def _build_cached_ads_snapshot(
    *,
    organization_id: int,
    date_from: date,
    date_to: date,
    group_by: ReportGroupBy,
) -> AdsAttributionSnapshot:
    ads_cache = _period_cache(organization_id, "ads", date_from, date_to)
    aggregates = _cache_aggregates(ads_cache)
    rows: list[AdsAttributionRow] = []
    totals = {
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
        nm_id = _int_or_zero(aggregate.get("nmId") or aggregate.get("nmID") or raw_key)
        campaign_id_raw = aggregate.get("campaignId") or aggregate.get("advertId") or aggregate.get("advert_id")
        campaign_id = str(campaign_id_raw) if campaign_id_raw not in (None, "") else None
        ad_spend = _nonnegative_int(aggregate.get("adSpendKopecks") or aggregate.get("spendKopecks") or aggregate.get("sumKopecks"))
        impressions = _nonnegative_int(aggregate.get("adImpressions") or aggregate.get("impressions") or aggregate.get("views"))
        clicks = _nonnegative_int(aggregate.get("adClicks") or aggregate.get("clicks"))
        cart_adds = _nonnegative_int(aggregate.get("adCartAdds") or aggregate.get("cartAdds") or aggregate.get("cartCount") or aggregate.get("baskets"))
        orders_count = _nonnegative_int(aggregate.get("adOrders") or aggregate.get("ordersCount") or aggregate.get("orderCount") or aggregate.get("orders"))
        orders_kopecks = _nonnegative_int(aggregate.get("adSalesKopecks") or aggregate.get("ordersKopecks") or aggregate.get("orderSumKopecks") or aggregate.get("salesKopecks"))
        if not any((nm_id > 0, campaign_id, ad_spend, impressions, clicks, cart_adds, orders_count, orders_kopecks)):
            continue
        totals["ad_spend_kopecks"] += ad_spend
        totals["impressions"] += impressions
        totals["clicks"] += clicks
        totals["cart_adds"] += cart_adds
        totals["orders_count"] += orders_count
        totals["orders_kopecks"] += orders_kopecks
        sku_id = str(nm_id) if nm_id > 0 else None
        rows.append(
            AdsAttributionRow(
                campaign_id=campaign_id,
                sku_id=sku_id,
                attribution_level="campaign_sku" if sku_id and campaign_id else ("exact_sku" if sku_id else "campaign_only"),
                confidence="high" if ad_spend or orders_count else "medium",
                ad_spend_kopecks=ad_spend,
                impressions=impressions,
                clicks=clicks,
                cart_adds=cart_adds,
                orders_count=orders_count,
                orders_kopecks=orders_kopecks,
                campaign_name=str(aggregate.get("campaignName") or aggregate.get("advertName") or "") or None,
                campaign_type=aggregate.get("campaignType") or aggregate.get("advertType"),
                campaign_status=aggregate.get("campaignStatus") or aggregate.get("status"),
                payment_type=aggregate.get("paymentType"),
            )
        )
    has_any_data = bool(rows)
    return AdsAttributionSnapshot(
        source_status="fresh" if has_any_data else "blocked",
        confidence="high" if has_any_data else "blocked",
        blocker_ids=[] if has_any_data else ["WB_ADS_CACHE_EMPTY"],
        source_evidence=_evidence(
            "wb-ads-attribution-cache",
            "wb_api",
            "WB Ads cached by repricer sync",
            ["adSpendKopecks", "adImpressions", "adClicks", "adOrders", "adSalesKopecks"],
        ),
        totals=totals,
        rows=rows,
        diagnostics={"summary": {"source": "repricer_ads_cache", "rows": len(rows)}},
    )


def build_ads_performance_report(
    date_from: date,
    date_to: date,
    group_by: ReportGroupBy,
    finance_allowed: bool,
    organization_id: int | None = None,
    wb_token: str | None = None,
) -> AdsPerformanceResponse:
    snapshot = _build_cached_ads_snapshot(
        organization_id=organization_id or 1,
        date_from=date_from,
        date_to=date_to,
        group_by=group_by,
    )

    ad_spend = snapshot.totals.get("ad_spend_kopecks")
    orders_kopecks = snapshot.totals.get("orders_kopecks")
    drr_pct = _calc_drr_pct(ad_spend or 0, orders_kopecks or 0)
    roi_pct = _calc_roi_pct(ad_spend or 0, orders_kopecks or 0)
    romi_pct = roi_pct

    blocker_ids = snapshot.blocker_ids
    source_status = snapshot.source_status
    confidence_top = snapshot.confidence

    def to_row(index: int, row: AdsAttributionRow) -> AdsPerformanceRow:
        ad_spend_row = row.ad_spend_kopecks
        orders_row = row.orders_kopecks
        return AdsPerformanceRow(
            rowId=f"{group_by}-{row.campaign_id or 'unknown'}-{row.sku_id or index}",
            campaignId=row.campaign_id,
            skuId=row.sku_id,
            brandId="brand-satorna",
            managerId="maria",
            adSpendKopecks=ad_spend_row,
            impressions=row.impressions,
            clicks=row.clicks,
            cartAdds=row.cart_adds,
            ordersCount=row.orders_count,
            ordersKopecks=orders_row,
            drrPct=_calc_drr_pct(ad_spend_row or 0, orders_row or 0),
            romiPct=_calc_roi_pct(ad_spend_row or 0, orders_row or 0),
            roiPct=_calc_roi_pct(ad_spend_row or 0, orders_row or 0),
            attributionLevel=row.attribution_level,
            confidence=row.confidence,
        )

    rows = [to_row(index, row) for index, row in enumerate(snapshot.rows, start=1)]
    if not rows:
        fallback_attribution: Literal["exact_sku", "campaign_sku", "campaign_only", "unknown"] = (
            "campaign_sku" if group_by == "sku" else "campaign_only"
        )
        fallback_confidence: Literal["high", "medium", "low", "blocked"] = "medium" if group_by == "sku" else "low"
        rows = [
            AdsPerformanceRow(
                rowId=f"{group_by}-fallback",
                campaignId="unattributed",
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
                attributionLevel=fallback_attribution,
                confidence=fallback_confidence,
            )
        ]

    return AdsPerformanceResponse(
        sourceStatus=source_status,
        confidence=confidence_top,
        blockerIds=blocker_ids,
        sourceEvidence=snapshot.source_evidence,
        calculatedAt=utc_now(),
        period=_period(date_from, date_to),
        groupBy=group_by,
        totals=AdsTotals(
            adSpendKopecks=ad_spend,
            impressions=snapshot.totals.get("impressions"),
            clicks=snapshot.totals.get("clicks"),
            cartAdds=snapshot.totals.get("cart_adds"),
            ordersCount=snapshot.totals.get("orders_count"),
            ordersKopecks=orders_kopecks,
            drrPct=drr_pct,
            romiPct=romi_pct,
            roiPct=roi_pct,
        ),
        rows=rows,
        attributionPolicy=AdsAttributionPolicy(
            allowedSkuLevels=["exact_sku", "campaign_sku"],
            campaignOnlyCanAllocateToSkuPnl=False,
            notes=[
                "campaign_only attribution is kept campaign-level and is not allocated to SKU P&L",
                "weak attribution is returned with low/medium confidence only",
            ],
        ),
    )


def build_rnp_report(
    date_from: date,
    date_to: date,
    group_by: ReportGroupBy,
    finance_allowed: bool,
    organization_id: int = 1,
    wb_token: str | None = None,
    force_refresh: bool = False,
    progress_callback: Any | None = None,
) -> RnpReportResponse:
    snapshot = build_rnp_snapshot(
        date_from=date_from,
        date_to=date_to,
        group_by=group_by,
        organization_id=organization_id,
        wb_token=wb_token,
        force_refresh=force_refresh,
        progress_callback=progress_callback,
    )
    return RnpReportResponse(
        sourceStatus=snapshot.source_status,
        confidence=snapshot.confidence,
        blockerIds=snapshot.blocker_ids,
        sourceEvidence=snapshot.source_evidence,
        calculatedAt=snapshot.calculated_at,
        period=_period(date_from, date_to),
        groupBy=group_by,
        rows=snapshot.rows,
        adSpendKopecks=snapshot.ad_spend_kopecks,
        drrPct=snapshot.drr_pct,
        formulaNotes=snapshot.formula_notes,
        adsSourceStatus=snapshot.ads_source_status,
        diagnostics=snapshot.diagnostics,
    )


def _abc_letter(rank_index: int, total: int) -> str:
    if total <= 0:
        return "C"
    ratio = (rank_index + 1) / total
    if ratio <= 0.2:
        return "A"
    if ratio <= 0.5:
        return "B"
    return "C"


def _composite_metric(units: int, kopecks: int, delta_pct: float | None = None) -> dict[str, Any]:
    return {
        "units": units,
        "unitsLabel": "шт",
        "kopecks": kopecks,
        "deltaPct": delta_pct,
        "deltaLabel": f"{delta_pct:+.1f}%" if delta_pct is not None else "—",
    }


def _cache_aggregates(cache: dict[str, Any]) -> dict[str, dict[str, Any]]:
    aggregates = cache.get("aggregates")
    return aggregates if isinstance(aggregates, dict) else {}


def _stock_cache(organization_id: int, date_from: date, date_to: date) -> dict[str, Any]:
    period_stock = _period_cache(organization_id, "stocks", date_from, date_to)
    if period_stock:
        return period_stock
    return get_source_cache(organization_id, "stocks", slim=False) or {}


def _abc_filter_status(filters: str) -> str | None:
    for part in str(filters or "").split("&"):
        key, sep, value = part.partition("=")
        if sep and key.strip() == "status" and value.strip():
            return value.strip()
    return None


def _aggregate_sum(aggregates: dict[str, Any], *keys: str) -> int:
    total = 0
    for row in aggregates.values():
        if not isinstance(row, dict):
            continue
        total += sum(_int_or_zero(row.get(key)) for key in keys)
    return total


def _abc_group_rows(rows: list[dict[str, Any]], group_by: ReportGroupBy) -> list[dict[str, Any]]:
    if group_by == "sku":
        return rows
    key_by_group = {
        "brand": "brand",
        "manager": "manager",
        "category": "category",
        "status": "productStatus",
    }.get(group_by)
    if key_by_group is None:
        return rows

    grouped: dict[str, dict[str, Any]] = {}
    for row in rows:
        label = str(row.get(key_by_group) or "Не задано")
        bucket = grouped.setdefault(
            label,
            {
                "sku": label,
                "label": label,
                "productStatus": row.get("productStatus"),
                "brand": row.get("brand"),
                "category": row.get("category"),
                "manager": row.get("manager"),
                "ordersUnits": 0,
                "ordersKopecks": 0,
                "salesUnits": 0,
                "salesKopecks": 0,
                "adSpendKopecks": 0,
                "acquiringKopecks": 0,
                "acceptanceKopecks": 0,
                "penaltyKopecks": 0,
                "deductionKopecks": 0,
                "additionalPaymentKopecks": 0,
                "financeCreditsKopecks": 0,
                "rewardAdjustmentKopecks": 0,
                "paymentScheduleKopecks": 0,
                "loyaltyCostKopecks": 0,
                "taxKopecks": 0,
                "otherExpensesKopecks": 0,
                "netTotalKopecks": 0,
                "wbStockUnits": 0,
                "baskets": 0,
                "impressions": 0,
                "clicks": 0,
                "sourceStatus": row.get("sourceStatus", "partial"),
                "confidence": row.get("confidence", "medium"),
            },
        )
        for key in (
            "ordersUnits",
            "ordersKopecks",
            "salesUnits",
            "salesKopecks",
            "adSpendKopecks",
            "acquiringKopecks",
            "acceptanceKopecks",
            "penaltyKopecks",
            "deductionKopecks",
            "additionalPaymentKopecks",
            "financeCreditsKopecks",
            "rewardAdjustmentKopecks",
            "paymentScheduleKopecks",
            "loyaltyCostKopecks",
            "taxKopecks",
            "otherExpensesKopecks",
            "netTotalKopecks",
            "wbStockUnits",
            "baskets",
            "impressions",
            "clicks",
        ):
            bucket[key] += _int_or_zero(row.get(key))

    result = []
    for bucket in grouped.values():
        sales = bucket["salesKopecks"]
        profit = bucket["netTotalKopecks"]
        bucket["marginPct"] = profit / sales * 100 if sales > 0 else None
        bucket["ordersComposite"] = _composite_metric(bucket["ordersUnits"], bucket["ordersKopecks"])
        bucket["salesComposite"] = _composite_metric(bucket["salesUnits"], bucket["salesKopecks"])
        bucket["ctrPct"] = bucket["clicks"] / bucket["impressions"] * 100 if bucket["impressions"] else None
        bucket["cartCrPct"] = bucket["ordersUnits"] / bucket["baskets"] * 100 if bucket["baskets"] else None
        bucket["abcCode"] = "BB"
        result.append(bucket)
    return sorted(result, key=lambda item: _int_or_zero(item.get("netTotalKopecks")), reverse=True)


def _promotion_label(promotion: dict[str, Any]) -> str:
    raw = promotion.get("name") or promotion.get("title") or promotion.get("promotionName")
    if raw:
        return str(raw)
    promotion_id = promotion.get("id") or promotion.get("promotionID") or promotion.get("promotionId")
    return f"Акция {promotion_id}" if promotion_id else "Акция WB"


def _promotion_int_values(value: Any) -> set[int]:
    if value is None:
        return set()
    if isinstance(value, dict):
        value = value.keys()
    if isinstance(value, (str, int, float)):
        value = [value]
    result: set[int] = set()
    if not isinstance(value, (list, tuple, set)):
        return result
    for item in value:
        try:
            numeric = int(item)
        except (TypeError, ValueError):
            continue
        if numeric > 0:
            result.add(numeric)
    return result


def _promotion_text_values(value: Any) -> set[str]:
    if value is None:
        return set()
    if isinstance(value, (str, int, float)):
        value = [value]
    result: set[str] = set()
    if not isinstance(value, (list, tuple, set)):
        return result
    for item in value:
        text = str(item).strip()
        if text:
            result.add(text)
    return result


def _cached_promotions_for_abc(organization_id: int) -> list[dict[str, Any]]:
    promotions_cache = get_source_cache(organization_id, "promotions", slim=True) or {}
    raw_promotions = promotions_cache.get("promotions") if isinstance(promotions_cache, dict) else None
    if not isinstance(raw_promotions, list):
        return []

    thresholds_cache = get_source_cache(organization_id, "promotion_thresholds", slim=True) or {}
    by_promotion = thresholds_cache.get("byPromotionId") if isinstance(thresholds_cache, dict) else None
    by_promotion = by_promotion if isinstance(by_promotion, dict) else {}

    merged: list[dict[str, Any]] = []
    for promotion in raw_promotions:
        if not isinstance(promotion, dict):
            continue
        row = dict(promotion)
        promotion_id = row.get("id") or row.get("promotionID") or row.get("promotionId")
        imported = by_promotion.get(str(promotion_id)) if promotion_id is not None else None
        if isinstance(imported, dict):
            imported_nm_ids = _promotion_int_values(imported.get("thresholdNmIds"))
            if imported_nm_ids:
                row["thresholdNmIds"] = sorted(_promotion_int_values(row.get("thresholdNmIds")) | imported_nm_ids)
            if isinstance(imported.get("thresholdStatusesByNmId"), dict):
                statuses = dict(row.get("thresholdStatusesByNmId") or {})
                statuses.update(imported["thresholdStatusesByNmId"])
                row["thresholdStatusesByNmId"] = statuses
        merged.append(row)
    return merged


def _active_promotion_for_sku(article_id: str, nm_id: int, promotions: list[dict[str, Any]]) -> dict[str, Any] | None:
    article = str(article_id or "").strip()
    for status in ("active", "upcoming"):
        for promotion in promotions:
            if promotion.get("status") != status:
                continue
            if article and article in _promotion_text_values(promotion.get("articleIds")):
                return promotion
            nm_ids = _promotion_int_values(promotion.get("thresholdNmIds")) | _promotion_int_values(promotion.get("nmIds"))
            if nm_id > 0 and nm_id in nm_ids:
                return promotion
    return None


def _abc_promotion_lookup(promotions: list[dict[str, Any]]) -> dict[str, dict[Any, dict[str, Any]]]:
    lookup: dict[str, dict[Any, dict[str, Any]]] = {
        "activeArticle": {},
        "activeNm": {},
        "upcomingArticle": {},
        "upcomingNm": {},
    }
    for promotion in promotions:
        status = str(promotion.get("status") or "")
        if status not in {"active", "upcoming"}:
            continue
        article_key = f"{status}Article"
        nm_key = f"{status}Nm"
        for article in _promotion_text_values(promotion.get("articleIds")):
            lookup[article_key].setdefault(article, promotion)
        nm_ids = _promotion_int_values(promotion.get("thresholdNmIds")) | _promotion_int_values(promotion.get("nmIds"))
        for nm_id in nm_ids:
            lookup[nm_key].setdefault(nm_id, promotion)
    return lookup


def _abc_ktr_rows(organization_id: int) -> list[dict[str, Any]]:
    cache = get_source_cache(organization_id, "ktr_table", slim=False) or {}
    data = cache.get("data")
    if isinstance(data, dict):
        data = data.get("items") or data.get("data") or data.get("rows")
    return [row for row in data if isinstance(row, dict)] if isinstance(data, list) else []


def _abc_ktr_value(rows: list[dict[str, Any]], localization_pct: float | None) -> float | None:
    if localization_pct is None:
        return None
    for row in rows:
        lower = _first_float_or_none(row, "fromPct", "from", "min")
        upper = _first_float_or_none(row, "toPct", "to", "max")
        value = _first_float_or_none(row, "ktr", "ktrIndex", "value")
        if lower is not None and upper is not None and value is not None and lower <= localization_pct <= upper:
            return value
    return None


def _active_promotion_from_lookup(
    article_id: str,
    nm_id: int,
    lookup: dict[str, dict[Any, dict[str, Any]]],
) -> dict[str, Any] | None:
    article = str(article_id or "").strip()
    if article:
        promotion = lookup["activeArticle"].get(article) or lookup["upcomingArticle"].get(article)
        if promotion:
            return promotion
    if nm_id > 0:
        return lookup["activeNm"].get(nm_id) or lookup["upcomingNm"].get(nm_id)
    return None


def _build_abc_report_from_snapshots(
    *,
    organization_id: int,
    date_from: date,
    date_to: date,
    group_by: ReportGroupBy,
    filters: str,
    finance_allowed: bool,
    progress_callback: Any | None = None,
) -> AbcReportResponse | None:
    finance_cache = _period_cache(
        organization_id,
        "finance",
        date_from,
        date_to,
        require_current_finance_basis=True,
    )
    finance_basis_compatible = not finance_cache or finance_cache_uses_current_revenue_basis(finance_cache)
    finance_source_available = finance_allowed and bool(finance_cache) and finance_basis_compatible
    finance_aggregates = _cache_aggregates(finance_cache) if finance_source_available else {}

    ads_cache = _period_cache(organization_id, "ads", date_from, date_to)
    ads_source_available = bool(ads_cache)
    ads_aggregates = _cache_aggregates(ads_cache)
    period_stats_cache = _period_cache(organization_id, "period_stats", date_from, date_to)
    period_stats_aggregates = _cache_aggregates(period_stats_cache)
    baskets_cache = _period_cache(organization_id, "baskets", date_from, date_to)
    baskets_aggregates = _cache_aggregates(baskets_cache)
    stock_cache = _stock_cache(organization_id, date_from, date_to)
    stock_aggregates = _cache_aggregates(stock_cache)
    content_cards_cache = get_source_cache(organization_id, "content_cards", slim=False) or {}
    goods_by_nm = _goods_index(organization_id, content_cards_cache)
    status_filter = _abc_filter_status(filters)
    blockers: list[str] = []
    if not finance_allowed:
        blockers.append("WB_ABC_FINANCE_FORBIDDEN")
    elif finance_cache and not finance_basis_compatible:
        blockers.append("WB_ABC_FINANCE_REVENUE_BASIS_INCOMPATIBLE")
    elif not finance_cache:
        blockers.append("WB_ABC_FINANCE_CACHE_MISSING")
    if not baskets_cache:
        blockers.append("WB_ABC_SALES_FUNNEL_CACHE_MISSING")
    if not ads_cache:
        blockers.append("WB_ABC_ADS_CACHE_MISSING")
    if not period_stats_cache:
        blockers.append("WB_ABC_PERIOD_STATS_CACHE_MISSING")
    if not stock_cache:
        blockers.append("WB_ABC_STOCK_CACHE_MISSING")
    if not content_cards_cache:
        blockers.append("WB_ABC_CONTENT_CARDS_CACHE_MISSING")
    if any(
        _int_or_zero(row.get("sellerRevenueMissingRows")) > 0
        for row in finance_aggregates.values()
        if isinstance(row, dict)
    ):
        blockers.append("WB_ABC_RETAIL_AMOUNT_MISSING")
    ktr_rows = _abc_ktr_rows(organization_id)
    if not ktr_rows:
        blockers.append("WB_ABC_KTR_TABLE_MISSING")
    source_status: Literal["fresh", "partial", "stale", "blocked", "unknown"] = "fresh" if finance_allowed and not blockers else "partial"
    confidence: Literal["high", "medium", "low", "blocked"] = "high" if source_status == "fresh" else "medium"
    rows: list[dict[str, Any]] = []
    cogs_evidence_statuses: set[str] = set()
    promotions = _cached_promotions_for_abc(organization_id)
    promotion_lookup = _abc_promotion_lookup(promotions)
    runtime = load_runtime_state(organization_id) or {}
    algorithm = dict(DEFAULT_ALGORITHM_SETTINGS)
    algorithm.update(load_algorithm_settings(organization_id) or {})

    row_sources = (finance_aggregates, baskets_aggregates, period_stats_aggregates, ads_aggregates, stock_aggregates)
    all_nm_ids = sorted(
        {
            str(raw_nm_id)
            for source in row_sources
            for raw_nm_id, aggregate in source.items()
            if isinstance(aggregate, dict) and _int_or_zero(raw_nm_id) > 0
        }
        | {str(nm_id) for nm_id in goods_by_nm},
        key=lambda value: _int_or_zero(value),
    )
    total_nm_ids = len(all_nm_ids)
    if progress_callback:
        progress_callback({"phase": "abc-build", "processed": 0, "total": total_nm_ids})
    for index, raw_nm_id in enumerate(all_nm_ids, start=1):
        nm_id = _int_or_zero(raw_nm_id)
        if nm_id <= 0:
            continue
        finance = finance_aggregates.get(str(nm_id)) or {}
        good = goods_by_nm.get(nm_id, {})
        baskets = baskets_aggregates.get(str(nm_id)) or {}
        article_id = str(good.get("vendorCode") or good.get("vendor_code") or finance.get("vendorCode") or baskets.get("vendorCode") or f"NM_{nm_id}")
        settings = _sku_settings_from_state(article_id, runtime=runtime, algorithm=algorithm, effective_on=date_to)
        meta = _sku_meta_from_state(article_id, runtime=runtime)
        product_status = str(meta.get("status") or "unknown")
        if status_filter and product_status != status_filter:
            continue

        stock = stock_aggregates.get(str(nm_id)) or {}
        period_stats = period_stats_aggregates.get(str(nm_id)) or {}
        ads = ads_aggregates.get(str(nm_id)) or {}

        funnel_orders_units = _first_nonnegative_int_or_none(baskets, "orderCount", "ordersCount", "orders")
        funnel_orders_kopecks = _first_nonnegative_int_or_none(baskets, "orderSumKopecks", "ordersKopecks")
        finance_sales_units = (
            _int_or_zero(finance.get("netSalesUnits"))
            if "netSalesUnits" in finance
            else _int_or_zero(finance.get("salesUnits")) - _int_or_zero(finance.get("returnsUnits"))
        )
        sales_units_for_costs = finance_sales_units if finance else 0
        sales_units = sales_units_for_costs
        seller_revenue = _int_or_zero(finance.get("sellerRevenueKopecks")) if finance else 0
        orders_units = funnel_orders_units if funnel_orders_units is not None else 0
        orders_kopecks = funnel_orders_kopecks if funnel_orders_kopecks is not None else 0
        sales_kopecks = seller_revenue
        finance_row_complete = finance_source_available and _int_or_zero(finance.get("sellerRevenueMissingRows")) == 0
        profit_row_complete = finance_row_complete and ads_source_available
        cogs_total, cogs_settings = _abc_period_cogs(
            nm_id=nm_id,
            article_id=article_id,
            finance=finance,
            finance_cache=finance_cache,
            runtime=runtime,
            algorithm=algorithm,
            date_from=date_from,
            date_to=date_to,
        )
        cogs_evidence_statuses.add(str(cogs_settings.get("cogsEvidenceStatus") or "undated"))
        financial = _abc_financial_components(
            finance=finance,
            settings=settings,
            ads=ads,
            revenue_kopecks=seller_revenue,
            sales_units=sales_units_for_costs,
            cogs_kopecks=cogs_total,
        )
        cogs = financial["cogsKopecks"]
        commission = financial["commissionKopecks"]
        logistics = financial["logisticsKopecks"]
        storage = financial["storageKopecks"]
        acceptance = financial["acceptanceKopecks"]
        penalty = financial["penaltyKopecks"]
        deduction = financial["deductionKopecks"]
        finance_credits = financial["financeCreditsKopecks"]
        finance_other_expenses = financial["financeOtherExpensesKopecks"]
        compensation = financial["compensationKopecks"]
        acquiring = financial["acquiringKopecks"]
        loyalty_cost = financial["loyaltyCostKopecks"]
        ad_spend = financial["adSpendKopecks"]
        tax = financial["taxKopecks"]
        overhead = financial["otherExpensesKopecks"]
        net_profit = financial["netProfitKopecks"]
        gross_margin = sales_kopecks - cogs
        funnel_baskets = _abc_funnel_cart_count(baskets)
        baskets_count = funnel_baskets if funnel_baskets is not None else 0
        funnel_impressions = _abc_funnel_impressions(baskets)
        funnel_opens = _abc_funnel_open_count(baskets)
        traffic_impressions = funnel_impressions
        traffic_clicks = funnel_opens
        funnel_stock_units = _first_nonnegative_int_or_none(baskets, "wbStockUnits")
        stock_data_available = funnel_stock_units is not None or bool(stock)
        stock_units = funnel_stock_units if funnel_stock_units is not None else max(0, _int_or_zero(stock.get("wbStockUnits") or stock.get("stockUnits") or stock.get("quantity")))
        price_before_spp = _good_seller_price_kopecks(good)
        price_with_spp = _good_buyer_price_no_wallet_kopecks(good)
        cogs_per_unit = _nonnegative_int(cogs_settings.get("cogsKopecks"))
        cart_to_order_pct = orders_units / baskets_count * 100 if baskets_count > 0 else None
        clicks_delta_pct = _first_float_or_none(baskets, "openCountDeltaPct", "clicksDeltaPct")
        baskets_delta_pct = _first_float_or_none(baskets, "cartCountDeltaPct", "basketsDeltaPct")
        orders_delta_pct = _first_float_or_none(baskets, "orderCountDeltaPct", "ordersDeltaPct")
        sales_delta_pct = _first_float_or_none(finance, "salesDeltaPct")
        buyout_count = _first_nonnegative_int_or_none(baskets, "buyoutCount", "buyoutsCount", "buyouts")
        buyout_pct = buyout_count / orders_units * 100 if buyout_count is not None and orders_units > 0 else None
        gross_sales_units = _nonnegative_int(finance.get("salesUnits"))
        returns_units = _nonnegative_int(finance.get("returnsUnits"))
        gross_sales_kopecks = _nonnegative_int(finance.get("grossSalesKopecks"))
        returns_kopecks = _nonnegative_int(finance.get("returnsKopecks"))
        average_sale_price = gross_sales_kopecks / gross_sales_units if gross_sales_units > 0 else None
        cancelled_orders_units = _nonnegative_int(period_stats.get("cancelledOrdersUnits")) if period_stats else None
        turnover_days = stock_units * max(1, (date_to - date_from).days + 1) / sales_units if stock_units >= 0 and sales_units > 0 else None
        localization_pct = _first_float_or_none(baskets, "localizationPct", "localizationPercent")
        promotion = _active_promotion_from_lookup(article_id, nm_id, promotion_lookup)
        promotion_name = _promotion_label(promotion) if promotion else None
        promotion_id = (
            promotion.get("id") or promotion.get("promotionID") or promotion.get("promotionId")
            if promotion
            else None
        )

        row = {
            "sku": article_id,
            "nmId": nm_id,
            "photoUrl": _photo_url_for_good(good, nm_id),
            "productName": str(good.get("title") or good.get("name") or baskets.get("productName") or article_id),
            "productStatus": product_status,
            "managerId": meta.get("managerId"),
            "manager": meta.get("managerName") or meta.get("managerId") or "Не задано",
            "brand": str(good.get("brand") or good.get("brandName") or baskets.get("brand") or meta.get("brand") or "Не задано"),
            "category": str(good.get("subjectName") or good.get("subject") or baskets.get("category") or "Не задано"),
            "priceBeforeSppKopecks": price_before_spp,
            "priceWithSppKopecks": price_with_spp,
            "averageSalePriceKopecks": average_sale_price,
            "cogsPerUnitKopecks": cogs_per_unit,
            "cogsKopecks": cogs if finance_source_available else None,
            "cogsSource": cogs_settings.get("cogsSource"),
            "cogsEffectiveFrom": cogs_settings.get("cogsEffectiveFrom"),
            "cogsEvidenceStatus": cogs_settings.get("cogsEvidenceStatus"),
            "grossMarginKopecks": gross_margin if finance_row_complete else None,
            "grossMarginPct": gross_margin / sales_kopecks * 100 if finance_row_complete and sales_kopecks > 0 else None,
            "profitabilityPct": net_profit / sales_kopecks * 100 if profit_row_complete and sales_kopecks > 0 else None,
            "marginPct": net_profit / sales_kopecks * 100 if profit_row_complete and sales_kopecks > 0 else None,
            "marginKopecks": (int(round(net_profit / max(sales_units_for_costs, 1))) if sales_units_for_costs else net_profit) if profit_row_complete else None,
            "marginDeltaPct": None,
            "impressions": traffic_impressions,
            "clicks": traffic_clicks,
            "clicksDeltaPct": clicks_delta_pct,
            "ctrPct": traffic_clicks / traffic_impressions * 100 if traffic_impressions and traffic_clicks is not None else None,
            "baskets": baskets_count if baskets else None,
            "cartCrPct": cart_to_order_pct,
            "basketsDeltaPct": baskets_delta_pct,
            "ordersUnits": orders_units,
            "ordersDeltaPct": orders_delta_pct,
            "ordersKopecks": orders_kopecks,
            "cancelledOrdersUnits": cancelled_orders_units,
            "ordersComposite": _composite_metric(orders_units, orders_kopecks, orders_delta_pct) if baskets else None,
            "salesUnits": sales_units if finance_row_complete else None,
            "salesDeltaPct": sales_delta_pct,
            "salesKopecks": sales_kopecks if finance_row_complete else None,
            "grossSalesUnits": gross_sales_units if finance_row_complete else None,
            "returnsUnits": returns_units if finance_row_complete else None,
            "grossSalesKopecks": gross_sales_kopecks if finance_row_complete else None,
            "returnsKopecks": returns_kopecks if finance_row_complete else None,
            "salesComposite": _composite_metric(sales_units, sales_kopecks, sales_delta_pct) if finance_row_complete else None,
            "adSpendKopecks": ad_spend if ads_source_available else None,
            "adSpendSource": "wb_ads_api" if ads_source_available else None,
            "commissionKopecks": commission if finance_source_available else None,
            "commissionSource": finance.get("commissionSource"),
            "logisticsKopecks": logistics if finance_source_available else None,
            "storageKopecks": storage if finance_source_available else None,
            "acquiringKopecks": acquiring if finance_source_available else None,
            "acceptanceKopecks": acceptance if finance_source_available else None,
            "penaltyKopecks": penalty if finance_source_available else None,
            "deductionKopecks": deduction if finance_source_available else None,
            "additionalPaymentKopecks": _int_or_zero(finance.get("additionalPaymentKopecks")) if finance_source_available else None,
            "financeCreditsKopecks": finance_credits if finance_source_available else None,
            "financeOtherExpensesKopecks": finance_other_expenses if finance_source_available else None,
            "totalOtherExpensesKopecks": overhead + finance_other_expenses if finance_row_complete else None,
            "compensationKopecks": compensation if finance_source_available else None,
            "rewardAdjustmentKopecks": _int_or_zero(finance.get("rewardAdjustmentKopecks")) if finance_source_available else None,
            "paymentScheduleKopecks": _int_or_zero(finance.get("paymentScheduleKopecks")) if finance_source_available else None,
            "loyaltyCostKopecks": loyalty_cost if finance_source_available else None,
            "taxKopecks": tax if finance_row_complete else None,
            "otherExpensesKopecks": overhead if finance_row_complete else None,
            "drrOrdersPct": ad_spend / orders_kopecks * 100 if ads_source_available and orders_kopecks > 0 else None,
            "drrSalesPct": ad_spend / sales_kopecks * 100 if profit_row_complete and sales_kopecks > 0 else None,
            "netPerUnitKopecks": (int(round(net_profit / max(sales_units_for_costs, 1))) if sales_units_for_costs else net_profit) if profit_row_complete else None,
            "netTotalKopecks": net_profit if profit_row_complete else None,
            "logisticsCostPct": logistics / seller_revenue * 100 if seller_revenue > 0 else None,
            "logisticsDeltaPct": None,
            "commissionCostPct": commission / seller_revenue * 100 if seller_revenue > 0 else None,
            "commissionDeltaPct": None,
            "storageCostPct": storage / seller_revenue * 100 if seller_revenue > 0 else None,
            "storageDeltaPct": None,
            "ktrIndex": _abc_ktr_value(ktr_rows, localization_pct),
            "localizationPct": localization_pct,
            "wbStockUnits": stock_units if stock_data_available else None,
            "wbStockKopecks": stock_units * price_with_spp if stock_data_available and price_with_spp is not None else None,
            "turnoverDays": turnover_days if stock_data_available else None,
            "daysToOos": turnover_days if stock_data_available else None,
            "promotionStatus": "yes" if promotion else "no",
            "promotionStatusText": promotion_name,
            "promotionName": promotion_name,
            "promotionId": promotion_id,
            "promotionType": promotion.get("type") if promotion else None,
            "abcCode": "CC",
            "buyoutPct": buyout_pct,
            "sourceStatus": source_status,
            "confidence": confidence,
        }
        rows.append(row)
        if progress_callback and (index % 100 == 0 or index == total_nm_ids):
            progress_callback({"phase": "abc-build", "processed": index, "total": total_nm_ids})

    if "undated" in cogs_evidence_statuses or any(not row.get("cogsEffectiveFrom") for row in rows):
        blockers.append("WB_ABC_COGS_EFFECTIVE_DATE_MISSING")
    if "period_end_fallback" in cogs_evidence_statuses:
        blockers.append("WB_ABC_COGS_DAILY_COVERAGE_MISMATCH")
    source_status = "fresh" if finance_allowed and not blockers else "partial"
    confidence = "high" if source_status == "fresh" else "medium"
    for row in rows:
        row["sourceStatus"] = source_status
        row["confidence"] = confidence
        row["blockerIds"] = list(blockers)

    sales_rank = sorted(rows, key=lambda row: (_int_or_zero(row.get("salesKopecks")), _int_or_zero(row.get("salesUnits")), _int_or_zero(row.get("ordersUnits"))), reverse=True)
    profit_rank = sorted(rows, key=lambda row: _int_or_zero(row.get("netTotalKopecks")), reverse=True)
    sales_letters = {row["nmId"]: _abc_letter(index, len(sales_rank)) for index, row in enumerate(sales_rank)}
    profit_letters = {row["nmId"]: _abc_letter(index, len(profit_rank)) for index, row in enumerate(profit_rank)}
    for row in rows:
        row["abcCode"] = f"{sales_letters.get(row['nmId'], 'C')}{profit_letters.get(row['nmId'], 'C')}"

    rows = sorted(rows, key=lambda row: (_int_or_zero(row.get("salesKopecks")), _int_or_zero(row.get("netTotalKopecks"))), reverse=True)
    output_rows = _abc_group_rows(rows, group_by)
    finance_values_complete = finance_source_available and "WB_ABC_RETAIL_AMOUNT_MISSING" not in blockers
    profit_values_complete = finance_values_complete and ads_source_available
    total_orders = sum(_int_or_zero(row.get("ordersUnits")) for row in rows) if baskets_cache else None
    total_orders_kopecks = sum(_int_or_zero(row.get("ordersKopecks")) for row in rows) if baskets_cache else None
    total_profit = sum(_int_or_zero(row.get("netTotalKopecks")) for row in rows) if profit_values_complete else None
    total_sales = sum(_int_or_zero(row.get("salesKopecks")) for row in rows) if finance_values_complete else None
    total_returns = sum(_int_or_zero(row.get("returnsKopecks")) for row in rows) if finance_values_complete else None
    total_baskets = sum(_int_or_zero(row.get("baskets")) for row in rows) if baskets_cache else None
    total_ad_spend = sum(_int_or_zero(row.get("adSpendKopecks")) for row in rows) if ads_source_available else None

    source_evidence = [
        SourceEvidence(
            sourceId="wb-finance-sales-reports-detailed-cache",
            sourceType="wb_api",
            sourceName="WB Finance /api/finance/v1/sales-reports/detailed snapshot from repricer sync",
            lastSyncedAt=_parse_cache_datetime(finance_cache.get("fetchedAt")) or utc_now(),
            freshnessTtlMinutes=1440,
            fieldsUsed=["salesUnits", "returnsUnits", "netSalesUnits", "grossSalesKopecks", "returnsKopecks", "sellerRevenueKopecks", "commissionKopecks", "logisticsKopecks", "storageKopecks", "acceptanceKopecks", "penaltyKopecks", "deductionKopecks", "additionalPaymentKopecks", "loyaltyCostKopecks", "acquiringKopecks"],
        ),
        SourceEvidence(
            sourceId="wb-sales-funnel-products-cache",
            sourceType="wb_api",
            sourceName="WB Analytics /api/analytics/v3/sales-funnel/products",
            lastSyncedAt=_parse_cache_datetime(baskets_cache.get("fetchedAt")) or utc_now(),
            freshnessTtlMinutes=1440,
            fieldsUsed=["openCount", "cartCount", "orderCount", "orderSumKopecks", "buyoutCount", "localizationPct"],
        ),
        SourceEvidence(
            sourceId="wb-period-stats-cache",
            sourceType="wb_api",
            sourceName="WB Statistics orders/sales period snapshot",
            lastSyncedAt=_parse_cache_datetime(period_stats_cache.get("fetchedAt")) or utc_now(),
            freshnessTtlMinutes=1440,
            fieldsUsed=["cancelledOrdersUnits"],
        ),
        SourceEvidence(
            sourceId="wb-ads-cache",
            sourceType="wb_api",
            sourceName="WB Promotion campaign statistics",
            lastSyncedAt=_parse_cache_datetime(ads_cache.get("fetchedAt")) or utc_now(),
            freshnessTtlMinutes=1440,
            fieldsUsed=["adSpendKopecks"],
        ),
        SourceEvidence(
            sourceId="wb-current-goods-cache",
            sourceType="wb_api",
            sourceName="WB goods/prices and content cards current snapshots",
            lastSyncedAt=_parse_cache_datetime(content_cards_cache.get("fetchedAt")) or utc_now(),
            freshnessTtlMinutes=60,
            fieldsUsed=["vendorCode", "nmID", "title", "photoUrl", "brand", "subjectName", "priceBeforeSppKopecks", "priceWithSppKopecks"],
        ),
        SourceEvidence(
            sourceId="platform-ktr-table",
            sourceType="manual",
            sourceName="Organization KTR lookup table",
            lastSyncedAt=utc_now(),
            freshnessTtlMinutes=1440,
            fieldsUsed=["ktrIndex"],
        ),
        SourceEvidence(
            sourceId="platform-abc-settings",
            sourceType="manual",
            sourceName="Organization SKU settings, COGS history and ABC algorithm rules",
            lastSyncedAt=utc_now(),
            freshnessTtlMinutes=1440,
            fieldsUsed=["productStatus", "managerId", "cogsKopecks", "cogsEffectiveFrom", "taxPct", "otherExpensePricePct"],
        ),
        *_evidence("wb-abc-derived", "derived", "ABC calculations from canonical snapshots", ["abcCode", "averageSalePriceKopecks", "cartCrPct", "grossMarginKopecks", "profitabilityPct", "turnoverDays"]),
    ]

    return AbcReportResponse(
        sourceStatus=source_status,
        confidence=confidence,
        blockerIds=blockers,
        sourceEvidence=source_evidence,
        calculatedAt=utc_now(),
        period=_period(date_from, date_to),
        filteredSummary=AbcFilteredSummary(
            filterHash=sha1(f"{date_from}:{date_to}:{group_by}:{filters}".encode("utf-8")).hexdigest()[:12],
            skuCount=len(rows),
            locomotiveCount=sum(1 for row in rows if str(row.get("productStatus")) == "locomotive"),
            basketsCount=total_baskets,
            ordersCount=total_orders,
            ordersKopecks=total_orders_kopecks,
            salesKopecks=total_sales,
            returnsKopecks=total_returns,
            profitKopecks=total_profit,
            marginPct=total_profit / total_sales * 100 if total_profit is not None and total_sales is not None and total_sales > 0 else None,
            adSpendKopecks=total_ad_spend,
            sourceStatus=source_status,
            confidence=confidence,
        ),
        rows=output_rows,
    )


def _empty_abc_report_from_snapshot_miss(date_from: date, date_to: date, group_by: ReportGroupBy, filters: str) -> AbcReportResponse:
    return AbcReportResponse(
        sourceStatus="partial",
        confidence="low",
        blockerIds=["WB_ABC_FINANCE_CACHE_MISSING"],
        sourceEvidence=_evidence(
            "wb-abc-runtime-cache-miss",
            "derived",
            "ABC report did not find repricer finance snapshot for selected period",
            ["finance", "period_stats", "ads", "baskets", "stocks"],
        ),
        calculatedAt=utc_now(),
        period=_period(date_from, date_to),
        filteredSummary=AbcFilteredSummary(
            filterHash=sha1(f"{date_from}:{date_to}:{group_by}:{filters}".encode("utf-8")).hexdigest()[:12],
            skuCount=0,
            locomotiveCount=None,
            ordersCount=None,
            ordersKopecks=None,
            profitKopecks=None,
            marginPct=None,
            adSpendKopecks=None,
            sourceStatus="partial",
            confidence="low",
        ),
        rows=[],
    )


def build_abc_report(
    date_from: date,
    date_to: date,
    group_by: ReportGroupBy,
    filters: str,
    finance_allowed: bool,
    organization_id: int | None = None,
    progress_callback: Any | None = None,
) -> AbcReportResponse:
    if organization_id is not None:
        snapshot_report = _build_abc_report_from_snapshots(
            organization_id=organization_id,
            date_from=date_from,
            date_to=date_to,
            group_by=group_by,
            filters=filters,
            finance_allowed=finance_allowed,
            progress_callback=progress_callback,
        )
        if snapshot_report is not None:
            return snapshot_report
        return _empty_abc_report_from_snapshot_miss(date_from, date_to, group_by, filters)

    filter_hash = sha1(f"{date_from}:{date_to}:{group_by}:{filters}".encode("utf-8")).hexdigest()[:12]
    ad_spend = 420_000
    blockers: list[str] = []

    return AbcReportResponse(
        sourceStatus="partial",
        confidence="medium",
        blockerIds=blockers,
        sourceEvidence=_evidence(
            "wb-abc-runtime",
            "derived",
            "ABC filtered summary runtime layer",
            ["filterHash", "skuCount", "ordersKopecks", "profitKopecks", "adSpendKopecks"],
        ),
        calculatedAt=utc_now(),
        period=_period(date_from, date_to),
        filteredSummary=AbcFilteredSummary(
            filterHash=filter_hash,
            skuCount=11 if filters else 32,
            locomotiveCount=4 if filters else 9,
            ordersCount=92 if filters else 261,
            ordersKopecks=1_140_000 if filters else 3_320_000,
            profitKopecks=273_000,
            marginPct=23.95,
            adSpendKopecks=ad_spend,
            sourceStatus="partial",
            confidence="medium",
        ),
        rows=[],
    )


def build_plan_fact_report(date_from: date, date_to: date, dimension: PlanFactDimension, finance_allowed: bool) -> PlanFactResponse:
    days_left = max(1, (date_to - date_from).days // 2)
    plan = 5_000_000
    fact = 3_250_000
    deviation = fact - plan
    completion = round(fact / plan * 100, 2)
    forecast = 4_960_000
    min_per_day = int((plan - fact) / days_left)

    blockers: list[str] = ["WB-14A"]
    source_status: Literal["fresh", "partial", "stale", "blocked", "unknown"] = "partial"
    conf: Literal["high", "medium", "low", "blocked"] = "medium"

    row = PlanFactRow(
        rowId=f"{dimension}-maria",
        dimension=dimension,
        ownerId="maria" if dimension != "company" else "company",
        ownerLabel="Мария" if dimension != "company" else "Компания",
        metric="margin_profit_kopecks",
        planKopecks=plan,
        factKopecks=fact,
        deviationKopecks=deviation,
        completionPct=completion,
        forecastKopecks=forecast,
        minPerDayKopecks=min_per_day,
        sourceStatus=source_status,
        confidence=conf,
        blockerIds=[],
    )

    return PlanFactResponse(
        sourceStatus=source_status,
        confidence=conf,
        blockerIds=blockers,
        sourceEvidence=_evidence(
            "wb-plan-fact-runtime",
            "derived",
            "Plan-fact runtime layer",
            ["plan", "fact", "deviation", "completion", "forecast", "minPerDay"],
        ),
        calculatedAt=utc_now(),
        period=_period(date_from, date_to),
        dimension=dimension,
        rows=[row],
    )


def build_sku_rating_report(date_from: date, date_to: date, finance_allowed: bool) -> SkuRatingResponse:
    blockers: list[str] = []
    source_status: Literal["fresh", "partial", "stale", "blocked", "unknown"] = "partial"
    confidence: Literal["high", "medium", "low", "blocked"] = "medium"
    reasons = [
        "ABC sales class A",
        "healthy conversion and basket trend",
    ]
    row = RatingRow(
        skuId="FBBT_42",
        nmId=123456,
        group="locomotive",
        score=84,
        scoreReasons=reasons,
        links=[
            RatingLink(kind="sku_drawer", href="/wb/repricer/sku/FBBT_42"),
            RatingLink(kind="repricer", href="/wb/repricer?sku=FBBT_42"),
            RatingLink(kind="liquidation", href="/wb/repricer/liquidation?sku=FBBT_42"),
        ],
        sourceStatus=source_status,
        confidence=confidence,
        blockerIds=blockers,
    )

    return SkuRatingResponse(
        sourceStatus=source_status,
        confidence=confidence,
        blockerIds=blockers,
        sourceEvidence=_evidence(
            "wb-sku-rating-runtime",
            "derived",
            "SKU rating runtime layer",
            ["group", "score", "scoreReasons", "links"],
        ),
        calculatedAt=utc_now(),
        period=_period(date_from, date_to),
        rows=[row],
    )


def build_export_response(finance_allowed: bool, filters: str, period_from: date, period_to: date) -> ExportCurrentViewResponse:
    file_stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    file_name = f"wb_report_export_{file_stamp}.xlsx" if finance_allowed else f"wb_report_export_limited_{file_stamp}.xlsx"
    return ExportCurrentViewResponse(
        exportState="ready",
        reason=None if finance_allowed else "monthly company costs are masked for this permission set",
        fileName=file_name,
        format="xlsx",
        sourceStatus="fresh" if finance_allowed else "partial",
        confidence="high" if finance_allowed else "medium",
        blockerIds=[],
        sourceEvidence=_evidence(
            "wb-export-runtime" if finance_allowed else "wb-export-runtime-limited",
            "derived",
            "Export current view metadata and visibility policy",
            ["filters", "period", "columns", "sourceFreshness", "sourceConfidence", "visibilityPolicy"],
        ),
        generatedAt=utc_now(),
    )
