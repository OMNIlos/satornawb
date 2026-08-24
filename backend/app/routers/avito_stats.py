from __future__ import annotations

from datetime import date, datetime, timezone, timedelta
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request

from app.avito.auth import resolve_user_avito_access_token
from app.avito.stats import AvitoStatsClient, AvitoStatsDailyPoint, AvitoStatsFetchRequest, AvitoStatsItem, build_avito_stats_client
from app.cabinet.store import get_organization_avito_credentials_secret, get_user_avito_credentials_secret
from app.config import get_settings
from app.control_plane.auth import actor_from_request, has_permission
from app.repricer_cache.store import get_source_cache, save_source_cache


router = APIRouter(tags=["avito-stats"])


def _date_range(date_from: date | None, date_to: date | None, period_days: int) -> tuple[date, date, int]:
    end = date_to or date.today()
    start = date_from or (end - timedelta(days=period_days - 1))
    if start > end:
        raise HTTPException(status_code=422, detail="AVITO_STATS_INVALID_PERIOD")
    days = (end - start).days + 1
    if days > 270:
        raise HTTPException(status_code=422, detail="AVITO_STATS_PERIOD_TOO_DEEP")
    return start, end, days


def _metric_value(value: int | None) -> int:
    return value if value is not None else 0


def _ratio(numerator: int | None, denominator: int | None) -> float | None:
    if numerator is None or denominator is None:
        return None
    if denominator <= 0:
        return 0.0
    return round(numerator / denominator * 100, 2)


def _control_flags(row: AvitoStatsItem) -> list[str]:
    flags: list[str] = []
    if row.views is not None and row.views > 0 and row.contacts == 0:
        flags.append("no_contacts")
    if row.sourceStatus == "stale":
        flags.append("stale_source")
    if row.sourceStatus == "partial":
        flags.append("partial_source")
    return flags


def _row_payload(row: AvitoStatsItem) -> dict[str, Any]:
    return {
        **row.model_dump(mode="json"),
        "contactConversionPct": _ratio(row.contacts, row.views),
        "orderConversionPct": _ratio(row.orders, row.contacts),
        "buyoutPct": _ratio(row.buyouts, row.orders),
        "controlFlags": _control_flags(row),
    }


def _summary(rows: list[AvitoStatsItem]) -> dict[str, Any]:
    def total_or_none(metric: str) -> int | None:
        values = [getattr(row, metric) for row in rows]
        present = [value for value in values if value is not None]
        return sum(present) if present else None

    totals = {
        metric: total_or_none(metric)
        for metric in (
            "impressions",
            "views",
            "contactsMessenger",
            "contacts",
            "contactsShowPhone",
            "contactsShowPhoneAndMessenger",
            "favorites",
            "spendKopecks",
            "orders",
            "buyouts",
        )
    }
    return {
        **totals,
        "conversionPct": _ratio(totals["contacts"], totals["views"]),
        "messengerConversionPct": _ratio(totals["contactsMessenger"], totals["views"]),
        "orderConversionPct": _ratio(totals["orders"], totals["contacts"]),
        "buyoutPct": _ratio(totals["buyouts"], totals["orders"]),
        "problemRows": sum(1 for row in rows if _control_flags(row)),
    }


def _timeline(points: list[AvitoStatsDailyPoint]) -> list[dict[str, Any]]:
    buckets: dict[str, dict[str, Any]] = {}
    for point in points:
        key = point.date.isoformat()
        bucket = buckets.setdefault(
            key,
            {
                "date": key,
                "impressions": 0,
                "views": 0,
                "contactsMessenger": 0,
                "contacts": 0,
                "contactsShowPhone": 0,
                "contactsShowPhoneAndMessenger": 0,
                "favorites": 0,
                "spendKopecks": 0,
                "orders": 0,
                "buyouts": 0,
            },
        )
        for metric in (
            "impressions",
            "views",
            "contactsMessenger",
            "contacts",
            "contactsShowPhone",
            "contactsShowPhoneAndMessenger",
            "favorites",
            "spendKopecks",
            "orders",
            "buyouts",
        ):
            bucket[metric] += _metric_value(getattr(point, metric))
    return [buckets[key] for key in sorted(buckets)]


def _cache_key(start: date, end: date, account_ids: list[str]) -> str:
    account_part = ",".join(sorted(account_ids)) if account_ids else "all"
    return f"avito_stats:{start.isoformat()}:{end.isoformat()}:{account_part}"


def _client(access_token: str) -> AvitoStatsClient:
    settings = get_settings()
    try:
        return build_avito_stats_client(
            mode="live",
            access_token=access_token,
            base_url=settings.avito_api_base_url,
            timeout_seconds=settings.avito_api_timeout_seconds,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


def _response_payload(
    *,
    status: str,
    start: date,
    end: date,
    days: int,
    rows: list[AvitoStatsItem],
    accounts: list[Any],
    daily: list[AvitoStatsDailyPoint] | None = None,
    error: Any | None = None,
    cache_status: str = "fresh",
    diagnostics: dict[str, Any] | None = None,
) -> dict[str, Any]:
    sorted_rows = sorted(rows, key=lambda item: (_metric_value(item.views), _metric_value(item.contacts), _metric_value(item.favorites)), reverse=True)
    settings = get_settings()
    return {
        "status": status,
        "period": {"dateFrom": start.isoformat(), "dateTo": end.isoformat(), "days": days},
        "summary": _summary(sorted_rows),
        "timeline": _timeline(daily or []),
        "accounts": [account.model_dump(mode="json") for account in accounts],
        "rows": [_row_payload(row) for row in sorted_rows],
        "source": {
            "mode": "live",
            "cache": {
                "status": cache_status,
                "savedAt": datetime.now(timezone.utc).isoformat(),
            },
            "api": {
                "baseUrl": settings.avito_api_base_url,
                "tokenEndpoint": "POST /token",
                "itemsEndpoint": "GET /core/v1/items",
                "statsEndpoint": "POST /stats/v2/accounts/{user_id}/items",
                "maxItemIdsPerRequest": 1000,
                "maxDepthDays": 270,
            },
            "diagnostics": diagnostics,
            "error": error.model_dump(mode="json") if hasattr(error, "model_dump") else error,
        },
    }


def _stale_cached_payload(cached: dict[str, Any], error: Any | None) -> dict[str, Any]:
    payload = dict(cached)
    payload["status"] = "partial"
    source = dict(payload.get("source") or {})
    cache = dict(source.get("cache") or {})
    cache["status"] = "stale"
    source["cache"] = cache
    source["error"] = error.model_dump(mode="json") if hasattr(error, "model_dump") else error
    payload["source"] = source
    return payload


def _cache_hit_payload(cached: dict[str, Any]) -> dict[str, Any]:
    payload = dict(cached)
    source = dict(payload.get("source") or {})
    cache = dict(source.get("cache") or {})
    cache["status"] = "hit"
    source["cache"] = cache
    source["error"] = None
    payload["source"] = source
    return payload


@router.get("/api/v1/avito/stats")
def get_avito_stats(
    request: Request,
    date_from: date | None = Query(default=None, alias="dateFrom"),
    date_to: date | None = Query(default=None, alias="dateTo"),
    period_days: int = Query(default=30, alias="periodDays", ge=1, le=270),
    account_id: list[str] = Query(default_factory=list, alias="accountId"),
    force_refresh: bool = Query(default=False, alias="forceRefresh"),
) -> dict[str, Any]:
    actor = actor_from_request(request)
    if not has_permission(actor, "cabinet:read"):
        raise HTTPException(status_code=403, detail="NO_ACCESS:cabinet:read")
    start, end, days = _date_range(date_from, date_to, period_days)
    source_key = _cache_key(start, end, account_id)
    cached = get_source_cache(actor.organization_id, source_key, slim=False) or None
    if not force_refresh and isinstance(cached, dict) and cached.get("rows"):
        return _cache_hit_payload(cached)

    credentials = get_user_avito_credentials_secret(actor.user_id) or get_organization_avito_credentials_secret(actor.organization_id)
    if credentials is None:
        if isinstance(cached, dict) and cached.get("rows"):
            return _stale_cached_payload(cached, {"code": "credentials_required", "message": "AVITO_CREDENTIALS_REQUIRED"})
        raise HTTPException(status_code=409, detail="AVITO_CREDENTIALS_REQUIRED")

    settings = get_settings()
    try:
        access_token = resolve_user_avito_access_token(
            user_id=actor.user_id,
            credentials=credentials,
            base_url=settings.avito_api_base_url,
            timeout_seconds=settings.avito_api_timeout_seconds,
        )
    except Exception as exc:
        if isinstance(cached, dict) and cached.get("rows"):
            return _stale_cached_payload(cached, {"code": "oauth_error", "message": str(exc)})
        raise HTTPException(status_code=409, detail="AVITO_OAUTH_FAILED") from exc

    result = _client(access_token).fetch_stats(AvitoStatsFetchRequest(dateFrom=start, dateTo=end, accountIds=account_id, grouping="totals"))
    if result.status == "blocked":
        if isinstance(cached, dict) and cached.get("rows"):
            return _stale_cached_payload(cached, result.error)
        return _response_payload(
            status=result.status,
            start=start,
            end=end,
            days=days,
            rows=[],
            accounts=[],
            daily=[],
            error=result.error,
            cache_status="miss",
        )

    payload = _response_payload(
        status=result.status,
        start=start,
        end=end,
        days=days,
        rows=result.items,
        accounts=result.accounts,
        daily=result.daily,
        error=result.error,
        diagnostics=result.diagnostics,
    )
    save_source_cache(actor.organization_id, source_key, payload)
    return payload
