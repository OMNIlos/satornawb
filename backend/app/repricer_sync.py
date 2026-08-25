from __future__ import annotations

import hashlib
import logging
import ssl
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import date, datetime, timedelta, timezone
from typing import Any, Callable
from uuid import uuid4

from fastapi import HTTPException

from app.config import get_settings
from app.wb_api.price_units import kopecks_to_wb_price_rubles, wb_goods_price_to_kopecks
from app.repricer_bff import (
    ALGORITHM_SETTINGS_STATE,
    FRONTEND_STRATEGY_ASSIGNMENTS,
    SKU_META_OVERRIDES,
    _fetch_content_cards,
    _nm_ids_from_goods,
    _promotions_for_cache,
    fetch_baskets_aggregates,
    fetch_baskets_daily_detail,
    fetch_ads_spend_aggregates,
    fetch_catalog_goods_page,
    fetch_finance_report_aggregates,
    fetch_period_stats_aggregates,
    fetch_stock_aggregates,
    list_promotions,
    record_repricer_changelog_event,
    WbSalesFunnelDeferred,
)
from app.repricer_cache.store import (
    get_source_cache,
    list_cached_goods,
    list_source_cache_ranges_by_prefix,
    save_goods_page,
    save_source_cache,
)
from app.notifications import record_wb_sync_notification

try:
    import httpx
except Exception:  # pragma: no cover - httpx is a runtime dependency, kept defensive for import safety
    httpx = None  # type: ignore[assignment]


SYNC_STATUS_KEY = "wb_sync_status"
SYNC_HISTORY_KEY = "wb_sync_history"
SYNC_STALE_AFTER_MINUTES = 30
SYNC_EMPTY_RUNNING_STALE_AFTER_SECONDS = 90
SYNC_LONG_RUNNING_STALE_GRACE_SECONDS = 1800
SYNC_DEFAULT_SOURCES = ("goods", "content", "promotions", "stocks", "period-stats", "finance", "ads", "baskets")
EXTERNAL_SPP_BATCH_SIZE = 100
EXTERNAL_SPP_BATCH_INTERVAL_SECONDS = 10.0
logger = logging.getLogger(__name__)


def _good_article_id(good: dict[str, Any]) -> str:
    return str(good.get("vendorCode") or good.get("articleId") or "").strip()


def _good_nm_id(good: dict[str, Any]) -> int | None:
    try:
        value = int(good.get("nmID") or good.get("nmId") or 0)
    except (TypeError, ValueError):
        return None
    return value if value > 0 else None


def _good_first_size(good: dict[str, Any]) -> dict[str, Any]:
    sizes = good.get("sizes") if isinstance(good.get("sizes"), list) else []
    first_size = sizes[0] if sizes and isinstance(sizes[0], dict) else {}
    return first_size


def _first_good_price_kopecks(good: dict[str, Any], *keys: str) -> int | None:
    first_size = _good_first_size(good)
    for source in (first_size, good):
        for key in keys:
            raw = source.get(key)
            if key.endswith("Kopecks") and raw not in (None, ""):
                try:
                    value = int(round(float(raw)))
                except (TypeError, ValueError):
                    value = 0
            else:
                value = wb_goods_price_to_kopecks(raw)
            if value > 0:
                return value
    return None


def _good_seller_price_kopecks(good: dict[str, Any]) -> int | None:
    return _first_good_price_kopecks(good, "discountedPrice", "price")


def _good_buyer_price_no_wallet_kopecks(good: dict[str, Any]) -> int | None:
    buyer_price = _first_good_price_kopecks(
        good,
        "buyerPriceNoWalletKopecks",
        "buyerPriceNoWallet",
        "buyerPriceKopecks",
        "buyerPrice",
        "clientPrice",
    )
    seller_price = _good_seller_price_kopecks(good)
    return buyer_price if not buyer_price or not seller_price or buyer_price <= seller_price else None


def _goods_by_identity(goods: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for good in goods:
        if not isinstance(good, dict):
            continue
        nm_id = _good_nm_id(good)
        article_id = _good_article_id(good)
        if nm_id is not None:
            result[f"nm:{nm_id}"] = good
        if article_id:
            result[f"article:{article_id}"] = good
    return result


def _wb_sync_event_id(run_id: str, article_id: str, field: str) -> str:
    digest = hashlib.sha1(f"{run_id}:{article_id}:{field}".encode("utf-8")).hexdigest()[:16]
    return f"wb-sync-{digest}"


def record_wb_sync_price_change_events(
    previous_goods: list[dict[str, Any]],
    current_goods: list[dict[str, Any]],
    *,
    organization_id: int,
    run_id: str | None = None,
) -> int:
    previous_by_identity = _goods_by_identity(previous_goods)
    event_run_id = run_id or f"sync-{_utc_now().isoformat()}"
    recorded = 0
    for current in current_goods:
        if not isinstance(current, dict):
            continue
        article_id = _good_article_id(current)
        nm_id = _good_nm_id(current)
        previous = previous_by_identity.get(f"nm:{nm_id}") if nm_id is not None else None
        if previous is None and article_id:
            previous = previous_by_identity.get(f"article:{article_id}")
        if previous is None or not article_id:
            continue
        sku_name = str(current.get("title") or current.get("name") or previous.get("title") or previous.get("name") or article_id)
        comparisons = (
            (
                "seller_before_spp",
                _good_seller_price_kopecks(previous),
                _good_seller_price_kopecks(current),
                "WB sync обновил цену до СПП",
            ),
            (
                "buyer_after_spp",
                _good_buyer_price_no_wallet_kopecks(previous),
                _good_buyer_price_no_wallet_kopecks(current),
                "WB sync обновил цену с СПП",
            ),
        )
        for field, old_price, new_price, reason in comparisons:
            if old_price is None or new_price is None or old_price == new_price:
                continue
            record_repricer_changelog_event(
                article_id=article_id,
                sku_name=sku_name,
                old_price_kopecks=old_price,
                new_price_kopecks=new_price,
                trigger="wb_sync",
                margin_after_pct=0,
                actor={"id": "wb-sync", "name": "WB Sync", "role": "system"},
                source="wb_sync",
                scope="sku",
                reason=reason,
                old_value=f"{field}:{old_price}",
                new_value=f"{field}:{new_price}",
                organization_id=organization_id,
                event_id=_wb_sync_event_id(event_run_id, article_id, field),
            )
            recorded += 1
    return recorded


def _unique_nm_ids_from_goods(goods: list[dict[str, Any]]) -> list[int]:
    seen: set[int] = set()
    result: list[int] = []
    for good in goods:
        nm_id = _good_nm_id(good)
        if nm_id is None or nm_id in seen:
            continue
        seen.add(nm_id)
        result.append(nm_id)
    return result


def fetch_external_spp_prices(
    nm_ids: list[int],
    *,
    api_token: str | None = None,
    api_base_url: str | None = None,
    timeout_seconds: float | None = None,
    sleep_fn: Callable[[float], None] | None = None,
    progress_callback: Callable[[dict[str, Any]], None] | None = None,
) -> dict[int, int]:
    """Fetch live buyer prices after SPP from the 41-spp API.

    The API accepts up to 100 nm IDs joined by semicolon and requires a
    10-second gap between batched requests.
    """
    if httpx is None:
        raise RuntimeError("httpx is required for external SPP price fetch")
    settings = get_settings()
    token = api_token or settings.spp_api_token
    if not token:
        return {}
    base_url = (api_base_url or settings.spp_api_base_url).rstrip("/")
    timeout = float(timeout_seconds if timeout_seconds is not None else settings.spp_api_timeout_seconds)
    sleeper = sleep_fn or time.sleep
    unique_nm_ids = []
    seen: set[int] = set()
    for nm_id in nm_ids:
        try:
            value = int(nm_id)
        except (TypeError, ValueError):
            continue
        if value <= 0 or value in seen:
            continue
        seen.add(value)
        unique_nm_ids.append(value)

    prices: dict[int, int] = {}
    batch_total = (len(unique_nm_ids) + EXTERNAL_SPP_BATCH_SIZE - 1) // EXTERNAL_SPP_BATCH_SIZE
    headers = {
        "accept": "application/json",
        "Authorization": token if token.startswith("Bearer ") else f"Bearer {token}",
    }
    verify_ssl = ssl.create_default_context() if settings.spp_api_verify_ssl else False
    with httpx.Client(timeout=timeout, verify=verify_ssl) as client:
        for start in range(0, len(unique_nm_ids), EXTERNAL_SPP_BATCH_SIZE):
            if start > 0:
                sleeper(EXTERNAL_SPP_BATCH_INTERVAL_SECONDS)
            batch = unique_nm_ids[start : start + EXTERNAL_SPP_BATCH_SIZE]
            if not batch:
                continue
            response = client.get(
                f"{base_url}/prices",
                params={"nm": ";".join(str(item) for item in batch)},
                headers=headers,
            )
            response.raise_for_status()
            payload = response.json()
            rows = payload.get("prices") if isinstance(payload, dict) else None
            if not isinstance(rows, list):
                continue
            for row in rows:
                if not isinstance(row, dict):
                    continue
                try:
                    nm_id = int(row.get("nm") or 0)
                    product = wb_goods_price_to_kopecks(row.get("product"))
                except (TypeError, ValueError):
                    continue
                if nm_id > 0 and product > 0 and str(row.get("status") or "ok") == "ok":
                    prices[nm_id] = product
            if progress_callback is not None:
                progress_callback(
                    {
                        "batchCurrent": start // EXTERNAL_SPP_BATCH_SIZE + 1,
                        "batchTotal": batch_total,
                        "itemsCompleted": min(start + len(batch), len(unique_nm_ids)),
                        "itemsTotal": len(unique_nm_ids),
                    }
                )
    return prices


def _apply_external_spp_prices_to_goods(goods: list[dict[str, Any]], prices_by_nm: dict[int, int]) -> int:
    matched = 0
    for good in goods:
        nm_id = _good_nm_id(good)
        if nm_id is None:
            continue
        buyer_price_kopecks = prices_by_nm.get(nm_id)
        if buyer_price_kopecks is None or buyer_price_kopecks <= 0:
            continue
        target_sizes = good.get("sizes") if isinstance(good.get("sizes"), list) else []
        target_size = dict(target_sizes[0]) if target_sizes and isinstance(target_sizes[0], dict) else {}
        seller_price_kopecks = _good_seller_price_kopecks(good)
        if seller_price_kopecks and buyer_price_kopecks > seller_price_kopecks:
            continue
        buyer_price_rubles = kopecks_to_wb_price_rubles(buyer_price_kopecks)
        target_size["buyerPriceNoWalletKopecks"] = buyer_price_kopecks
        target_size["buyerPriceNoWallet"] = buyer_price_rubles
        target_size["buyerPriceKopecks"] = buyer_price_kopecks
        target_size["buyerPrice"] = buyer_price_rubles
        target_size["clientPrice"] = buyer_price_rubles
        good["sizes"] = [target_size]
        matched += 1
    return matched


def _mark_new_goods_as_warmup(previous_goods: list[dict[str, Any]], current_goods: list[dict[str, Any]]) -> int:
    previous_articles = {_good_article_id(item) for item in previous_goods if _good_article_id(item)}
    previous_nm_ids = {_good_nm_id(item) for item in previous_goods if _good_nm_id(item) is not None}
    if not previous_articles and not previous_nm_ids:
        return 0
    marked = 0
    for good in current_goods:
        article_id = _good_article_id(good)
        nm_id = _good_nm_id(good)
        if not article_id:
            continue
        if article_id in previous_articles or (nm_id is not None and nm_id in previous_nm_ids):
            continue
        overrides = SKU_META_OVERRIDES.setdefault(article_id, {})
        if not overrides.get("status"):
            overrides["status"] = "warmup"
            overrides["assignmentSource"] = "sync_new_goods"
            overrides["assignedAt"] = _utc_now().isoformat()
            overrides["warmupDaysLeft"] = int(ALGORITHM_SETTINGS_STATE.get("warmupDays") or 10)
            marked += 1
    return marked


def _release_warmup_goods_by_baskets(goods: list[dict[str, Any]], baskets_payload: dict[str, Any]) -> int:
    threshold = max(0, int(ALGORITHM_SETTINGS_STATE.get("warmupExitBaskets") or 40))
    if threshold <= 0:
        return 0
    aggregates = baskets_payload.get("aggregates") if isinstance(baskets_payload.get("aggregates"), dict) else {}
    released = 0
    for good in goods:
        article_id = _good_article_id(good)
        nm_id = _good_nm_id(good)
        if not article_id or nm_id is None:
            continue
        overrides = SKU_META_OVERRIDES.get(article_id) or {}
        if str(overrides.get("status") or "") != "warmup":
            continue
        basket_count = int((aggregates.get(str(nm_id)) or {}).get("cartCount") or 0)
        if basket_count < threshold:
            continue
        next_overrides = SKU_META_OVERRIDES.setdefault(article_id, {})
        next_overrides["status"] = "auto"
        next_overrides["assignmentSource"] = "warmup_exit_baskets"
        next_overrides["assignedAt"] = _utc_now().isoformat()
        next_overrides["warmupDaysLeft"] = None
        next_overrides["basketsLast7d"] = basket_count
        FRONTEND_STRATEGY_ASSIGNMENTS[article_id] = {
            "strategyId": "baskets_orders",
            "source": "warmup_exit_baskets",
            "assignedAt": _utc_now().isoformat(),
            "config": {},
        }
        released += 1
    return released


class WbSyncAlreadyRunning(RuntimeError):
    pass


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _period_start_for_days(period_days: int, now: datetime | None = None) -> datetime:
    resolved_now = now or _utc_now()
    today_start = datetime.combine(resolved_now.date(), datetime.min.time(), tzinfo=timezone.utc)
    return today_start - timedelta(days=max(1, int(period_days)) - 1)


def _normalize_period_range(
    period_days: int,
    *,
    date_from: date | None = None,
    date_to: date | None = None,
    now: datetime | None = None,
) -> tuple[datetime, datetime, int]:
    resolved_today = (now or _utc_now()).date()
    end = date_to or resolved_today
    start = date_from or (end - timedelta(days=max(1, int(period_days)) - 1))
    if start > end:
        raise ValueError("dateFrom must be before or equal to dateTo")
    resolved_days = (end - start).days + 1
    if resolved_days < 1 or resolved_days > 90:
        raise ValueError("date range must be between 1 and 90 days")
    return (
        datetime.combine(start, datetime.min.time(), tzinfo=timezone.utc),
        datetime.combine(end, datetime.min.time(), tzinfo=timezone.utc),
        resolved_days,
    )


def _period_cache_suffix(period_days: int, *, date_from: date | None = None, date_to: date | None = None) -> str:
    if date_from is None and date_to is None:
        return str(max(1, int(period_days)))
    start, end, _resolved_days = _normalize_period_range(period_days, date_from=date_from, date_to=date_to)
    return f"{start.date().isoformat()}_{end.date().isoformat()}"


def _cache_date_from_payload(value: Any) -> date | None:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    try:
        return date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return None


def _cache_range_from_payload(cache: dict[str, Any]) -> tuple[date, date] | None:
    cache_from = _cache_date_from_payload(cache.get("dateFrom"))
    cache_to = _cache_date_from_payload(cache.get("dateTo"))
    if cache_from and cache_to:
        return cache_from, cache_to
    return None


def _baskets_daily_seed_from_recent_cache(
    organization_id: int,
    *,
    range_start: datetime,
    range_end: datetime,
) -> tuple[dict[str, dict[str, dict[str, Any]]], list[dict[str, Any]]]:
    seed_start = max(range_start.date(), range_end.date() - timedelta(days=6))
    seed_end = range_end.date()
    if seed_start > seed_end:
        return {}, []
    seed_key = f"baskets_{_period_cache_suffix((seed_end - seed_start).days + 1, date_from=seed_start, date_to=seed_end)}"
    seed_caches: list[dict[str, Any]] = []
    exact_cache = get_source_cache(organization_id, seed_key, slim=False) or {}
    if isinstance(exact_cache.get("dailyAggregates"), dict):
        seed_caches.append(exact_cache)
        if exact_cache.get("dateFrom") and exact_cache.get("dateTo"):
            selected_daily = {
                day_key: rows
                for day_key, rows in exact_cache["dailyAggregates"].items()
                if isinstance(day_key, str)
                and isinstance(rows, dict)
                and range_start.date().isoformat() <= day_key <= range_end.date().isoformat()
            }
            selected_chunks = [
                dict(chunk)
                for chunk in (exact_cache.get("chunks") if isinstance(exact_cache.get("chunks"), list) else [])
                if isinstance(chunk, dict) and range_start.date().isoformat() <= str(chunk.get("date") or "") <= range_end.date().isoformat()
            ]
            return selected_daily, selected_chunks
    overlap_start = range_start.date()
    overlap_end = range_end.date()
    for cache_meta in list_source_cache_ranges_by_prefix(organization_id, "baskets_", limit=100):
        if not isinstance(cache_meta, dict):
            continue
        cache_range = _cache_range_from_payload(cache_meta)
        if cache_range is None:
            continue
        cache_from, cache_to = cache_range
        if cache_to < overlap_start or cache_from > overlap_end:
            continue
        source_key = str(cache_meta.get("sourceKey") or "")
        cache = get_source_cache(organization_id, source_key, slim=False) if source_key else cache_meta
        if not isinstance(cache, dict):
            continue
        if source_key == seed_key and seed_caches:
            continue
        if isinstance(cache.get("dailyAggregates"), dict):
            seed_caches.append(cache)
    selected_daily: dict[str, dict[str, dict[str, Any]]] = {}
    selected_chunks: list[dict[str, Any]] = []
    seen_chunk_keys: set[tuple[str, int]] = set()
    for seed_cache in seed_caches:
        seed_daily = seed_cache.get("dailyAggregates")
        if isinstance(seed_daily, dict):
            for day_key, rows in seed_daily.items():
                if (
                    isinstance(day_key, str)
                    and isinstance(rows, dict)
                    and overlap_start.isoformat() <= day_key <= overlap_end.isoformat()
                ):
                    selected_daily[day_key] = rows
        for chunk in (seed_cache.get("chunks") if isinstance(seed_cache.get("chunks"), list) else []):
            if not isinstance(chunk, dict):
                continue
            day = str(chunk.get("date") or "")
            if not (overlap_start.isoformat() <= day <= overlap_end.isoformat()):
                continue
            try:
                chunk_key = (day, int(chunk.get("chunkIndex")))
            except (TypeError, ValueError):
                continue
            if chunk_key in seen_chunk_keys:
                continue
            selected_chunks.append(dict(chunk))
            seen_chunk_keys.add(chunk_key)
    return selected_daily, selected_chunks


def _parse_iso(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed
    except ValueError:
        return None


def _history_event_time(event: dict[str, Any]) -> datetime | None:
    for key in ("observedAt", "finishedAt", "startedAt", "updatedAt"):
        parsed = _parse_iso(event.get(key))
        if parsed is not None:
            return parsed.astimezone(timezone.utc)
    return None


def _prune_sync_history_items(items: list[dict[str, Any]], *, now: datetime | None = None, hours: int = 24, limit: int = 200) -> list[dict[str, Any]]:
    resolved_now = now or _utc_now()
    cutoff = resolved_now - timedelta(hours=max(1, int(hours)))
    pruned = [
        item
        for item in items
        if isinstance(item, dict) and ((_history_event_time(item) or resolved_now) >= cutoff)
    ]
    pruned.sort(key=lambda item: (_history_event_time(item) or datetime.min.replace(tzinfo=timezone.utc)), reverse=True)
    return pruned[: max(1, int(limit))]


def record_wb_sync_history_event(organization_id: int, event: dict[str, Any]) -> dict[str, Any]:
    now = _utc_now()
    payload = get_source_cache(organization_id, SYNC_HISTORY_KEY, slim=False) or {}
    items = payload.get("items") if isinstance(payload.get("items"), list) else []
    next_event = dict(event or {})
    next_event.setdefault("id", f"wb_sync_event_{uuid4().hex[:16]}")
    next_event.setdefault("observedAt", now.isoformat())
    next_items = _prune_sync_history_items([next_event, *[item for item in items if isinstance(item, dict)]], now=now)
    return save_source_cache(
        organization_id,
        SYNC_HISTORY_KEY,
        {
            "hours": 24,
            "count": len(next_items),
            "items": next_items,
            "updatedAt": now.isoformat(),
        },
    )


def list_wb_sync_history(organization_id: int, *, hours: int = 24, limit: int = 100) -> list[dict[str, Any]]:
    payload = get_source_cache(organization_id, SYNC_HISTORY_KEY, slim=False) or {}
    items = payload.get("items") if isinstance(payload.get("items"), list) else []
    return _prune_sync_history_items([item for item in items if isinstance(item, dict)], hours=hours, limit=limit)


def get_wb_sync_status(organization_id: int) -> dict[str, Any]:
    payload = get_source_cache(organization_id, SYNC_STATUS_KEY, slim=False) or {}
    state = str(payload.get("state") or "idle")
    started_at = _parse_iso(payload.get("startedAt"))
    updated_at = _parse_iso(payload.get("updatedAt"))
    last_seen_at = updated_at or started_at
    steps = payload.get("steps") or []
    empty_running_timeout = (
        timedelta(seconds=SYNC_EMPTY_RUNNING_STALE_AFTER_SECONDS)
        if state == "running" and not steps
        else timedelta(minutes=SYNC_STALE_AFTER_MINUTES)
    )
    estimated_seconds = int(payload.get("estimatedSeconds") or 0)
    if estimated_seconds > 0:
        empty_running_timeout = max(
            empty_running_timeout,
            timedelta(seconds=estimated_seconds + SYNC_LONG_RUNNING_STALE_GRACE_SECONDS),
        )
    stale = bool(state == "running" and last_seen_at and _utc_now() - last_seen_at > empty_running_timeout)
    running = state == "running" and not stale
    result = {
        "state": "running" if running else state,
        "running": running,
        "stale": stale,
        "runId": payload.get("runId"),
        "taskId": payload.get("taskId"),
        "trigger": payload.get("trigger"),
        "startedAt": payload.get("startedAt"),
        "finishedAt": payload.get("finishedAt"),
        "periodDays": payload.get("periodDays"),
        "dateFrom": payload.get("dateFrom"),
        "dateTo": payload.get("dateTo"),
        "periodCacheSuffix": payload.get("periodCacheSuffix"),
        "sources": payload.get("sources") or [],
        "tokenFingerprint": payload.get("tokenFingerprint"),
        "syncProfile": payload.get("syncProfile"),
        "syncProfileLabel": payload.get("syncProfileLabel"),
        "windowKind": payload.get("windowKind"),
        "cadenceMinutes": payload.get("cadenceMinutes"),
        "basketsDailyDetail": payload.get("basketsDailyDetail"),
        "estimatedRequests": payload.get("estimatedRequests"),
        "estimatedSeconds": payload.get("estimatedSeconds"),
        "estimateExplanation": payload.get("estimateExplanation"),
        "currentSource": payload.get("currentSource"),
        "steps": steps,
        "error": payload.get("error"),
        "updatedAt": payload.get("updatedAt"),
    }
    if stale and state == "running":
        result["state"] = "stale"
        result["running"] = False
    return result


def is_wb_sync_running(organization_id: int) -> bool:
    return bool(get_wb_sync_status(organization_id).get("running"))


def _save_status(organization_id: int, payload: dict[str, Any]) -> dict[str, Any]:
    return save_source_cache(organization_id, SYNC_STATUS_KEY, payload)


def abandon_stale_wb_sync(
    organization_id: int,
    *,
    reason: str = "stale_replaced",
    status: dict[str, Any] | None = None,
) -> dict[str, Any]:
    current = status or get_wb_sync_status(organization_id)
    if not (current.get("stale") or current.get("state") == "stale"):
        return current
    now = _utc_now().isoformat()
    steps = []
    for step in current.get("steps") or []:
        if not isinstance(step, dict):
            continue
        next_step = dict(step)
        if next_step.get("status") == "running":
            next_step["status"] = "error"
            next_step["error"] = "WB sync heartbeat expired"
        steps.append(next_step)
    payload = {
        **current,
        "state": "failed",
        "running": False,
        "stale": False,
        "currentSource": None,
        "steps": steps,
        "error": reason,
        "finishedAt": current.get("finishedAt") or now,
        "updatedAt": now,
    }
    _save_status(organization_id, payload)
    record_wb_sync_history_event(
        organization_id,
        {
            "type": "sync_abandoned",
            "reason": reason,
            "runId": current.get("runId"),
            "state": current.get("state"),
            "trigger": current.get("trigger"),
            "startedAt": current.get("startedAt"),
            "updatedAt": current.get("updatedAt"),
            "observedAt": now,
            "syncProfile": current.get("syncProfile"),
            "syncProfileLabel": current.get("syncProfileLabel"),
            "windowKind": current.get("windowKind"),
        },
    )
    return payload


def wb_token_fingerprint(token: str | None) -> str | None:
    if not token:
        return None
    digest = hashlib.sha256(token.encode("utf-8")).hexdigest()[:12]
    return f"wb_{digest}"


def _normalize_sources(sources: list[str] | tuple[str, ...] | set[str] | None) -> list[str]:
    allowed = set(SYNC_DEFAULT_SOURCES)
    if not sources:
        normalized = list(SYNC_DEFAULT_SOURCES)
    else:
        normalized = []
        for source in sources:
            value = str(source or "").strip()
            if value in allowed and value not in normalized:
                normalized.append(value)
    if not bool(ALGORITHM_SETTINGS_STATE.get("fullSyncPromotionsEnabled", True)):
        normalized = [source for source in normalized if source != "promotions"]
    return normalized


def begin_wb_sync(
    organization_id: int,
    *,
    trigger: str,
    period_days: int,
    date_from: date | None = None,
    date_to: date | None = None,
    force: bool = False,
    sources: list[str] | tuple[str, ...] | set[str] | None = None,
    token_fingerprint: str | None = None,
    sync_profile: str | None = None,
    sync_profile_label: str | None = None,
    window_kind: str | None = None,
    cadence_minutes: int | None = None,
    baskets_daily_detail: bool = False,
    estimated_requests: int | None = None,
    estimated_seconds: int | None = None,
    estimate_explanation: str | None = None,
) -> dict[str, Any]:
    status = get_wb_sync_status(organization_id)
    if status.get("running") and not force:
        raise WbSyncAlreadyRunning(str(status.get("runId") or "wb-sync-running"))
    now = _utc_now().isoformat()
    resolved_sources = _normalize_sources(sources)
    range_start, range_end, resolved_period_days = _normalize_period_range(period_days, date_from=date_from, date_to=date_to)
    period_suffix = _period_cache_suffix(period_days, date_from=date_from, date_to=date_to)
    payload = {
        "state": "running",
        "running": True,
        "runId": f"wb_sync_{uuid4().hex[:16]}",
        "trigger": trigger,
        "startedAt": now,
        "finishedAt": None,
        "periodDays": resolved_period_days,
        "dateFrom": range_start.date().isoformat(),
        "dateTo": range_end.date().isoformat(),
        "periodCacheSuffix": period_suffix,
        "sources": resolved_sources,
        "tokenFingerprint": token_fingerprint,
        **({"syncProfile": sync_profile} if sync_profile else {}),
        **({"syncProfileLabel": sync_profile_label} if sync_profile_label else {}),
        **({"windowKind": window_kind} if window_kind else {}),
        **({"cadenceMinutes": cadence_minutes} if cadence_minutes is not None else {}),
        "basketsDailyDetail": baskets_daily_detail,
        **({"estimatedRequests": estimated_requests} if estimated_requests is not None else {}),
        **({"estimatedSeconds": estimated_seconds} if estimated_seconds is not None else {}),
        **({"estimateExplanation": estimate_explanation} if estimate_explanation else {}),
        "currentSource": None,
        "steps": [],
        "error": None,
        "updatedAt": now,
    }
    _save_status(organization_id, payload)
    record_wb_sync_history_event(
        organization_id,
        {
            "type": "sync_started",
            "runId": payload.get("runId"),
            "state": payload.get("state"),
            "trigger": trigger,
            "startedAt": payload.get("startedAt"),
            "periodDays": payload.get("periodDays"),
            "dateFrom": payload.get("dateFrom"),
            "dateTo": payload.get("dateTo"),
            "periodCacheSuffix": payload.get("periodCacheSuffix"),
            "sources": payload.get("sources") or [],
            "tokenFingerprint": payload.get("tokenFingerprint"),
            "syncProfile": payload.get("syncProfile"),
            "syncProfileLabel": payload.get("syncProfileLabel"),
            "windowKind": payload.get("windowKind"),
            "cadenceMinutes": payload.get("cadenceMinutes"),
            "basketsDailyDetail": payload.get("basketsDailyDetail"),
            "estimatedRequests": payload.get("estimatedRequests"),
            "estimatedSeconds": payload.get("estimatedSeconds"),
            "estimateExplanation": payload.get("estimateExplanation"),
        },
    )
    return payload


def queue_wb_sync(
    organization_id: int,
    *,
    trigger: str,
    task_id: str,
    sync_profile: str,
    sync_profile_label: str,
    window_kind: str,
    sources: list[str] | tuple[str, ...] | set[str] | None = None,
) -> dict[str, Any]:
    previous = get_wb_sync_status(organization_id)
    now = _utc_now().isoformat()
    payload = {
        "state": "queued",
        "running": False,
        "runId": None,
        "taskId": task_id,
        "trigger": trigger,
        "startedAt": now,
        "finishedAt": previous.get("finishedAt"),
        "periodDays": previous.get("periodDays"),
        "dateFrom": previous.get("dateFrom"),
        "dateTo": previous.get("dateTo"),
        "periodCacheSuffix": previous.get("periodCacheSuffix"),
        "sources": _normalize_sources(sources),
        "syncProfile": sync_profile,
        "syncProfileLabel": sync_profile_label,
        "windowKind": window_kind,
        "currentSource": None,
        "steps": [
            {
                "source": source,
                "status": "pending",
                "progressPercent": 0,
                "progressCurrent": 0,
                "progressTotal": None,
                "phase": "queued",
                "message": "Ожидает старт фоновой задачи",
                "request": "WB sync queue",
            }
            for source in _normalize_sources(sources)
        ],
        "error": None,
        "updatedAt": now,
    }
    _save_status(organization_id, payload)
    record_wb_sync_history_event(
        organization_id,
        {
            "type": "sync_queued",
            "state": "queued",
            "trigger": trigger,
            "taskId": task_id,
            "startedAt": now,
            "sources": payload.get("sources") or [],
            "syncProfile": sync_profile,
            "syncProfileLabel": sync_profile_label,
            "windowKind": window_kind,
        },
    )
    return payload


def finish_wb_sync(organization_id: int, status: dict[str, Any], *, state: str, steps: list[dict[str, Any]], error: str | None = None) -> dict[str, Any]:
    payload = {
        **status,
        "state": state,
        "running": False,
        "finishedAt": _utc_now().isoformat(),
        "currentSource": None,
        "steps": steps,
        "error": error,
        "updatedAt": _utc_now().isoformat(),
    }
    _save_status(organization_id, payload)
    record_wb_sync_history_event(
        organization_id,
        {
            "type": "sync_finished",
            "runId": payload.get("runId"),
            "state": state,
            "trigger": payload.get("trigger"),
            "startedAt": payload.get("startedAt"),
            "finishedAt": payload.get("finishedAt"),
            "periodDays": payload.get("periodDays"),
            "dateFrom": payload.get("dateFrom"),
            "dateTo": payload.get("dateTo"),
            "periodCacheSuffix": payload.get("periodCacheSuffix"),
            "sources": payload.get("sources") or [],
            "syncProfile": payload.get("syncProfile"),
            "syncProfileLabel": payload.get("syncProfileLabel"),
            "windowKind": payload.get("windowKind"),
            "cadenceMinutes": payload.get("cadenceMinutes"),
            "basketsDailyDetail": payload.get("basketsDailyDetail"),
            "steps": steps,
            "error": error,
        },
    )
    record_wb_sync_notification(organization_id, payload)
    return payload


def _step_ok(name: str, **extra: Any) -> dict[str, Any]:
    return {"source": name, "status": "ok", **extra}


def _exception_message(exc: Exception) -> str:
    if isinstance(exc, HTTPException):
        detail = exc.detail
        if isinstance(detail, dict):
            message = detail.get("message")
            code = detail.get("code")
            details = detail.get("details")
            upstream_path = details.get("upstreamPath") if isinstance(details, dict) else None
            upstream_url = details.get("upstreamUrl") if isinstance(details, dict) else None
            rate_limit = details.get("rateLimit") if isinstance(details, dict) else None
            retry_after = rate_limit.get("retryAfterSeconds") if isinstance(rate_limit, dict) else None
            retry_suffix = f"; повтор через {retry_after} сек" if retry_after else ""
            if code == "wb_transport_error":
                suffix = f" ({upstream_url or upstream_path})" if upstream_url or upstream_path else ""
                return f"WB transport timeout{suffix}: WB не ответил после нескольких попыток"
            if message:
                url_suffix = f"; URL: {upstream_url}" if upstream_url else ""
                return f"{message}{retry_suffix}{url_suffix}"
            if code:
                url_suffix = f"; URL: {upstream_url}" if upstream_url else ""
                return f"{code}{retry_suffix}{url_suffix}"
        if isinstance(detail, str):
            return detail
    return str(exc)


def _step_error(name: str, exc: Exception) -> dict[str, Any]:
    return {"source": name, "status": "error", "error": _exception_message(exc)}


def _step_partial(name: str, exc: Exception, **extra: Any) -> dict[str, Any]:
    return {"source": name, "status": "partial", "error": _exception_message(exc), **extra}


def _step_paused(name: str, exc: WbSalesFunnelDeferred, **extra: Any) -> dict[str, Any]:
    retry_after = int(round(exc.retry_after_seconds))
    resume_at = _utc_now() + timedelta(seconds=max(0, retry_after))
    return {
        "source": name,
        "status": "paused",
        "reason": "wb_rate_limited_long_retry",
        "retryAfterSeconds": retry_after,
        "resumeAt": resume_at.isoformat(),
        "message": str(exc),
        **extra,
    }


def _save_running_progress(organization_id: int, status: dict[str, Any], steps: list[dict[str, Any]], current_source: str | None) -> None:
    payload = {
        **status,
        "state": "running",
        "running": True,
        "currentSource": current_source,
        "steps": steps,
        "updatedAt": _utc_now().isoformat(),
    }
    status.update(payload)
    _save_status(organization_id, payload)


def refresh_wb_data_sources(
    *,
    organization_id: int,
    wb_token: str | None,
    scenario: str = "complete",
    period_days: int = 30,
    date_from: date | None = None,
    date_to: date | None = None,
    trigger: str = "manual",
    force: bool = False,
    execute_lock: bool = True,
    sources: list[str] | tuple[str, ...] | set[str] | None = None,
    initial_status: dict[str, Any] | None = None,
    token_fingerprint: str | None = None,
    sync_profile: str | None = None,
    sync_profile_label: str | None = None,
    window_kind: str | None = None,
    cadence_minutes: int | None = None,
    baskets_include_daily_detail: bool = False,
    estimated_requests: int | None = None,
    estimated_seconds: int | None = None,
    estimate_explanation: str | None = None,
    _progress_callback: Callable[[dict[str, Any]], None] | None = None,
    _parallelize: bool = True,
) -> dict[str, Any]:
    resolved_sources = _normalize_sources(sources)
    resolved_token_fingerprint = token_fingerprint or wb_token_fingerprint(wb_token)
    range_start, range_end, resolved_period_days = _normalize_period_range(period_days, date_from=date_from, date_to=date_to)
    period_suffix = _period_cache_suffix(period_days, date_from=date_from, date_to=date_to)
    status = initial_status if initial_status is not None else (
        begin_wb_sync(
            organization_id,
            trigger=trigger,
            period_days=resolved_period_days,
            date_from=date_from,
            date_to=date_to,
            force=force,
            sources=resolved_sources,
            token_fingerprint=resolved_token_fingerprint,
            sync_profile=sync_profile,
            sync_profile_label=sync_profile_label,
            window_kind=window_kind,
            cadence_minutes=cadence_minutes,
            baskets_daily_detail=baskets_include_daily_detail,
            estimated_requests=estimated_requests,
            estimated_seconds=estimated_seconds,
            estimate_explanation=estimate_explanation,
        ) if execute_lock else {
            "runId": f"wb_sync_{uuid4().hex[:16]}",
            "trigger": trigger,
            "startedAt": _utc_now().isoformat(),
            "periodDays": resolved_period_days,
            "dateFrom": range_start.date().isoformat(),
            "dateTo": range_end.date().isoformat(),
            "periodCacheSuffix": period_suffix,
            "sources": resolved_sources,
            "tokenFingerprint": resolved_token_fingerprint,
            **({"syncProfile": sync_profile} if sync_profile else {}),
            **({"syncProfileLabel": sync_profile_label} if sync_profile_label else {}),
            **({"windowKind": window_kind} if window_kind else {}),
            **({"cadenceMinutes": cadence_minutes} if cadence_minutes is not None else {}),
            "basketsDailyDetail": baskets_include_daily_detail,
            **({"estimatedRequests": estimated_requests} if estimated_requests is not None else {}),
            **({"estimatedSeconds": estimated_seconds} if estimated_seconds is not None else {}),
            **({"estimateExplanation": estimate_explanation} if estimate_explanation else {}),
        }
    )
    status.update(
        {
            **({"syncProfile": sync_profile} if sync_profile else {}),
            **({"syncProfileLabel": sync_profile_label} if sync_profile_label else {}),
            **({"windowKind": window_kind} if window_kind else {}),
            **({"cadenceMinutes": cadence_minutes} if cadence_minutes is not None else {}),
            "basketsDailyDetail": baskets_include_daily_detail,
            **({"estimatedRequests": estimated_requests} if estimated_requests is not None else {}),
            **({"estimatedSeconds": estimated_seconds} if estimated_seconds is not None else {}),
            **({"estimateExplanation": estimate_explanation} if estimate_explanation else {}),
        }
    )
    logger.info(
        "WB repricer sync started org=%s trigger=%s periodDays=%s sources=%s token=%s",
        organization_id,
        trigger,
        resolved_period_days,
        ",".join(resolved_sources),
        resolved_token_fingerprint or "none",
    )
    steps: list[dict[str, Any]] = []
    fatal_error: str | None = None

    source_progress_copy: dict[str, tuple[str, str]] = {
        "goods": ("Запрашиваем каталог товаров WB", "WB API · каталог товаров"),
        "content": ("Получаем карточки товаров", "WB API · карточки контента"),
        "promotions": ("Получаем акции и скидки", "WB API · календарь акций"),
        "stocks": ("Загружаем остатки по складам", "WB API · отчёт по остаткам"),
        "period-stats": ("Получаем заказы и продажи за период", "WB API · статистика периода"),
        "finance": ("Загружаем финансовый отчёт", "WB API · детализация финансов"),
        "ads": ("Получаем расходы на рекламу", "WB API · статистика рекламы"),
        "baskets": ("Считаем добавления в корзину", "WB API · воронка продаж"),
    }

    def start_step(name: str) -> dict[str, Any]:
        message, request_label = source_progress_copy.get(name, ("Обновляем источник WB", "WB API"))
        step = {
            "source": name,
            "status": "running",
            "startedAt": _utc_now().isoformat(),
            "progressPercent": 5,
            "progressCurrent": 0,
            "progressTotal": None,
            "phase": "request",
            "message": message,
            "request": request_label,
        }
        steps.append(step)
        if _progress_callback is not None:
            _progress_callback(deepcopy(step))
        if execute_lock:
            _save_running_progress(organization_id, status, steps, name)
        return step

    def update_step(step: dict[str, Any], **progress: Any) -> None:
        step.update(progress)
        if _progress_callback is not None:
            _progress_callback(deepcopy(step))
        if execute_lock:
            _save_running_progress(organization_id, status, steps, str(step.get("source") or "") or None)

    def finish_step(step: dict[str, Any], payload: dict[str, Any]) -> None:
        payload_status = str(payload.get("status") or "")
        progress = {
            "progressPercent": 100,
            "progressCurrent": step.get("progressTotal") if step.get("progressTotal") is not None else step.get("progressCurrent"),
            "progressTotal": step.get("progressTotal"),
            "phase": (
                "completed"
                if payload_status in {"ok", "skipped"}
                else "partial"
                if payload_status == "partial"
                else "paused"
                if payload_status == "paused"
                else "failed"
            ),
            "message": (
                "Этап завершён"
                if payload_status in {"ok", "skipped"}
                else payload.get("message")
                or payload.get("error")
                or ("Этап поставлен на паузу" if payload_status == "paused" else "Этап частично завершён")
            ),
            "request": step.get("request"),
        }
        step.clear()
        step.update(payload, **progress)
        step["finishedAt"] = _utc_now().isoformat()
        if _progress_callback is not None:
            _progress_callback(deepcopy(step))
        if execute_lock:
            _save_running_progress(organization_id, status, steps, None)

    if _parallelize and len(resolved_sources) > 1:
        progress_lock = threading.RLock()
        ordered_steps = [
            {
                "source": source,
                "status": "pending",
                "progressPercent": 0,
                "progressCurrent": 0,
                "progressTotal": None,
                "phase": "pending",
                "message": "Ожидает свободный слот",
                "request": source_progress_copy.get(source, ("", "WB API"))[1],
            }
            for source in resolved_sources
        ]
        step_by_source = {str(step["source"]): step for step in ordered_steps}

        def persist_parallel_progress() -> None:
            active_sources = [
                str(item.get("source"))
                for item in ordered_steps
                if item.get("status") == "running"
            ]
            if not execute_lock:
                return
            payload = {
                **status,
                "state": "running",
                "running": True,
                "currentSource": active_sources[0] if active_sources else None,
                "activeSources": active_sources,
                "steps": deepcopy(ordered_steps),
                "updatedAt": _utc_now().isoformat(),
            }
            status.update(payload)
            _save_status(organization_id, payload)

        def receive_progress(next_step: dict[str, Any]) -> None:
            source = str(next_step.get("source") or "")
            with progress_lock:
                target = step_by_source[source]
                target.clear()
                target.update(deepcopy(next_step))
                persist_parallel_progress()

        def run_one(source: str) -> dict[str, Any]:
            return refresh_wb_data_sources(
                organization_id=organization_id,
                wb_token=wb_token,
                scenario=scenario,
                period_days=resolved_period_days,
                date_from=date_from,
                date_to=date_to,
                trigger=trigger,
                force=force,
                execute_lock=False,
                sources=[source],
                initial_status=status,
                token_fingerprint=resolved_token_fingerprint,
                sync_profile=sync_profile,
                sync_profile_label=sync_profile_label,
                window_kind=window_kind,
                cadence_minutes=cadence_minutes,
                baskets_include_daily_detail=baskets_include_daily_detail,
                estimated_requests=estimated_requests,
                estimated_seconds=estimated_seconds,
                estimate_explanation=estimate_explanation,
                _progress_callback=receive_progress,
                _parallelize=False,
            )

        independent = [
            source
            for source in resolved_sources
            if source in {"goods", "content", "promotions", "stocks", "period-stats", "ads"}
        ]
        dependent = [source for source in resolved_sources if source in {"finance", "baskets"}]
        with progress_lock:
            persist_parallel_progress()
        with ThreadPoolExecutor(max_workers=4, thread_name_prefix="wb-sync") as executor:
            futures = {source: executor.submit(run_one, source) for source in independent}
            if "goods" in futures:
                futures["goods"].result()
            futures.update({source: executor.submit(run_one, source) for source in dependent})
            for future in futures.values():
                future.result()

        if set(resolved_sources) & {"goods", "content", "promotions", "stocks", "period-stats", "finance", "ads", "baskets"}:
            snapshot_step = {
                "source": "sku-snapshot",
                "status": "running",
                "progressPercent": 0,
                "progressCurrent": 0,
                "progressTotal": None,
                "phase": "build",
                "message": "Собираем быстрый кэш таблицы репрайсера",
                "request": "local cache",
            }
            ordered_steps.append(snapshot_step)
            with progress_lock:
                persist_parallel_progress()
            try:
                from app import repricer_bff as repricer_bff_module
                from app.routers.wb_repricer_bff import _build_repricer_sku_snapshot

                repricer_bff_module.fetch_commission_tariffs(scenario, wb_token=wb_token, force=True)
                snapshot = _build_repricer_sku_snapshot(
                    organization_id,
                    scenario,
                    wb_token=wb_token,
                    resolved_period_days=resolved_period_days,
                    period_suffix=period_suffix,
                    range_start=range_start,
                    range_end=range_end,
                    include_promotions=False,
                    include_content=False,
                )
                snapshot_step.update(
                    _step_ok(
                        "sku-snapshot",
                        count=int(snapshot.get("total") or 0),
                        cacheKey=snapshot.get("sourceKey"),
                    )
                )
            except Exception as exc:
                snapshot_step.update(_step_error("sku-snapshot", exc))
            snapshot_step["progressPercent"] = 100
            with progress_lock:
                persist_parallel_progress()

        state_value = "completed" if all(step.get("status") in {"ok", "skipped"} for step in ordered_steps) else "partial"
        return (
            finish_wb_sync(organization_id, status, state=state_value, steps=ordered_steps)
            if execute_lock
            else {**status, "state": state_value, "steps": ordered_steps}
        )

    try:
        if "goods" in resolved_sources:
            step = start_step("goods")
            try:
                previous_goods = list_cached_goods(organization_id)
                fetched_goods: list[dict[str, Any]] = []
                total_saved = 0
                external_spp_matched_count = 0
                wb_sync_price_change_count = 0
                offset = 0
                limit = 1000
                cache: dict[str, Any] = {}
                while True:
                    page = fetch_catalog_goods_page(scenario, wb_token=wb_token, limit=limit, offset=offset)
                    goods = page.get("goods") or []
                    estimated_total = max(len(previous_goods), offset + len(goods))
                    update_step(
                        step,
                        phase="catalog",
                        progressPercent=10,
                        progressCurrent=offset + len(goods),
                        progressTotal=estimated_total or None,
                        message=f"Каталог WB: получено {offset + len(goods)} товаров",
                        request="WB API · страница каталога до 1000 товаров",
                    )
                    try:
                        page_nm_ids = _unique_nm_ids_from_goods(goods)

                        def report_spp_progress(progress: dict[str, Any]) -> None:
                            completed = offset + int(progress.get("itemsCompleted") or 0)
                            total = max(estimated_total, offset + int(progress.get("itemsTotal") or 0))
                            batch_current = offset // EXTERNAL_SPP_BATCH_SIZE + int(progress.get("batchCurrent") or 0)
                            batch_total = max(batch_current, (total + EXTERNAL_SPP_BATCH_SIZE - 1) // EXTERNAL_SPP_BATCH_SIZE)
                            percent = 10 + round(85 * completed / total) if total > 0 else 10
                            update_step(
                                step,
                                phase="spp",
                                progressPercent=min(95, percent),
                                progressCurrent=completed,
                                progressTotal=total or None,
                                message=f"Получаем цены после СПП: пачка {batch_current} из {batch_total}",
                                request="41-SPP · до 100 артикулов в запросе",
                            )

                        external_spp_prices = fetch_external_spp_prices(page_nm_ids, progress_callback=report_spp_progress)
                        external_spp_matched_count += _apply_external_spp_prices_to_goods(goods, external_spp_prices)
                    except Exception as exc:
                        logger.warning("External SPP price fetch failed org=%s offset=%s: %s", organization_id, offset, exc)
                    fetched_goods.extend([item for item in goods if isinstance(item, dict)])
                    wb_sync_price_change_count += record_wb_sync_price_change_events(
                        previous_goods,
                        goods,
                        organization_id=organization_id,
                        run_id=str(status.get("runId") or ""),
                    )
                    total_saved += len(goods)
                    cache = save_goods_page(
                        organization_id=organization_id,
                        page_offset=offset,
                        page_limit=limit,
                        goods=goods,
                        wb_request_id=page.get("wbRequestId"),
                        replace_all=offset == 0,
                    )
                    if len(goods) < limit or not goods:
                        break
                    offset += limit
                new_warmup_count = _mark_new_goods_as_warmup(previous_goods, fetched_goods)
                finish_step(
                    step,
                    _step_ok(
                        "goods",
                        count=total_saved,
                        cache=cache,
                        newWarmupCount=new_warmup_count,
                        externalSppMatchedCount=external_spp_matched_count,
                        wbSyncPriceChangeCount=wb_sync_price_change_count,
                    ),
                )
            except Exception as exc:
                finish_step(step, _step_error("goods", exc))

        if "content" in resolved_sources:
            step = start_step("content")
            try:
                def report_content_progress(progress: dict[str, Any]) -> None:
                    progress_current = progress.get("progressCurrent")
                    progress_total = progress.get("progressTotal")
                    pct = step.get("progressPercent") or 5
                    if isinstance(progress_current, int) and isinstance(progress_total, int) and progress_total > 0:
                        pct = min(95, max(5, round(progress_current / progress_total * 95)))
                    update_step(
                        step,
                        phase=progress.get("phase") or "cards",
                        progressPercent=pct,
                        progressCurrent=progress_current if isinstance(progress_current, int) else step.get("progressCurrent"),
                        progressTotal=progress_total if isinstance(progress_total, int) else step.get("progressTotal"),
                        message=progress.get("message") or "Получаем карточки товаров",
                        request="WB Content API · карточки товаров",
                        retryAfterSeconds=progress.get("retryAfterSeconds"),
                    )

                cards = _fetch_content_cards(scenario, wb_token=wb_token, progress_callback=report_content_progress)
                save_source_cache(organization_id, "content_cards", {"cards": cards, "count": len(cards)})
                finish_step(step, _step_ok("content", count=len(cards)))
            except Exception as exc:
                finish_step(step, _step_error("content", exc))

        if "promotions" in resolved_sources:
            step = start_step("promotions")
            try:
                promotions = list_promotions(scenario, wb_token=wb_token, fail_open=False)
                promotions_for_cache = _promotions_for_cache(promotions)
                save_source_cache(organization_id, "promotions", {"promotions": promotions_for_cache, "count": len(promotions_for_cache)})
                finish_step(step, _step_ok("promotions", count=len(promotions_for_cache)))
            except Exception as exc:
                finish_step(step, _step_error("promotions", exc))

        if "stocks" in resolved_sources:
            step = start_step("stocks")
            try:
                aggregates = fetch_stock_aggregates(scenario, wb_token=wb_token, date_from=range_start, date_to=range_end)
                save_source_cache(organization_id, "stocks", {"aggregates": aggregates, "count": len(aggregates)})
                finish_step(step, _step_ok("stocks", count=len(aggregates)))
            except Exception as exc:
                finish_step(step, _step_error("stocks", exc))

        if "period-stats" in resolved_sources:
            step = start_step("period-stats")
            try:
                period_stats_payload = fetch_period_stats_aggregates(scenario, wb_token=wb_token, date_from=range_start, date_to=range_end)
                aggregates = period_stats_payload.get("aggregates") if isinstance(period_stats_payload.get("aggregates"), dict) else period_stats_payload
                save_source_cache(
                    organization_id,
                    f"period_stats_{period_suffix}",
                    {
                        **(period_stats_payload if isinstance(period_stats_payload, dict) and "aggregates" in period_stats_payload else {}),
                        "aggregates": aggregates,
                        "count": len(aggregates),
                        "periodDays": resolved_period_days,
                        "dateFrom": range_start.date().isoformat(),
                        "dateTo": range_end.date().isoformat(),
                    },
                )
                finish_step(step, _step_ok("period-stats", count=len(aggregates)))
            except Exception as exc:
                finish_step(step, _step_error("period-stats", exc))

        if "finance" in resolved_sources:
            step = start_step("finance")
            try:
                finance_payload = fetch_finance_report_aggregates(scenario, wb_token=wb_token, date_from=range_start, date_to=range_end)
                finance_aggregates = finance_payload.get("aggregates") if isinstance(finance_payload.get("aggregates"), dict) else {}
                cached_goods_nm_ids = {str(nm_id) for nm_id in _nm_ids_from_goods(list_cached_goods(organization_id))}
                matched_cached_goods_nm_ids = len(set(finance_aggregates.keys()) & cached_goods_nm_ids)
                save_source_cache(
                    organization_id,
                    f"finance_{period_suffix}",
                    {
                        **finance_payload,
                        "periodDays": resolved_period_days,
                        "cachedGoodsNmIds": len(cached_goods_nm_ids),
                        "matchedCachedGoodsNmIds": matched_cached_goods_nm_ids,
                    },
                )
                finish_step(step, _step_ok("finance", count=int(finance_payload.get("count") or 0), matchedCachedGoodsNmIds=matched_cached_goods_nm_ids))
            except Exception as exc:
                finish_step(step, _step_error("finance", exc))

        if "ads" in resolved_sources:
            step = start_step("ads")
            try:
                def report_ads_progress(progress: dict[str, Any]) -> None:
                    completed_requests = int(progress.get("requestsCompleted") or 0)
                    total_requests = max(1, int(progress.get("requestsTotal") or 1))
                    processed_campaigns = int(progress.get("campaignsProcessed") or 0)
                    total_campaigns = int(progress.get("campaignsTotal") or 0)
                    percent = 5 if completed_requests <= 0 else 5 + round(90 * completed_requests / total_requests)
                    update_step(
                        step,
                        phase=str(progress.get("phase") or "fullstats"),
                        progressPercent=min(95, max(5, percent)),
                        progressCurrent=processed_campaigns,
                        progressTotal=total_campaigns or None,
                        message=str(progress.get("message") or (
                            f"Реклама WB: обработано {processed_campaigns} из {total_campaigns} кампаний"
                            if total_campaigns > 0
                            else "Реклама WB: активных кампаний не найдено"
                        )),
                        request=f"WB Ads · fullstats · запрос {min(completed_requests + 1, total_requests)} из {total_requests}",
                    )

                ads_payload = fetch_ads_spend_aggregates(
                    scenario,
                    wb_token=wb_token,
                    date_from=range_start,
                    date_to=range_end,
                    progress_callback=report_ads_progress,
                )
                save_source_cache(
                    organization_id,
                    f"ads_{period_suffix}",
                    {
                        **ads_payload,
                        "periodDays": resolved_period_days,
                    },
                )
                finish_step(step, _step_ok("ads", count=int(ads_payload.get("count") or 0), campaignCount=ads_payload.get("campaignCount")))
            except Exception as exc:
                finish_step(step, _step_error("ads", exc))

        if "baskets" in resolved_sources:
            step = start_step("baskets")
            try:
                cached_goods = list_cached_goods(organization_id)
                nm_ids = _nm_ids_from_goods(cached_goods)
                if not nm_ids:
                    finish_step(step, {"source": "baskets", "status": "skipped", "reason": "no_cached_goods_nm_ids"})
                else:
                    baskets_cache_key = f"baskets_{period_suffix}"
                    previous_baskets_cache = get_source_cache(organization_id, baskets_cache_key, slim=False) or {}
                    previous_daily_aggregates = previous_baskets_cache.get("dailyAggregates") if isinstance(previous_baskets_cache.get("dailyAggregates"), dict) else {}
                    previous_chunks = previous_baskets_cache.get("chunks") if isinstance(previous_baskets_cache.get("chunks"), list) else []
                    previous_cache_from = _parse_iso(previous_baskets_cache.get("dateFrom"))
                    previous_cache_to = _parse_iso(previous_baskets_cache.get("dateTo"))
                    if not (
                        previous_cache_from
                        and previous_cache_to
                        and previous_cache_from.date() == range_start.date()
                        and previous_cache_to.date() == range_end.date()
                    ):
                        previous_daily_aggregates = {}
                        previous_chunks = []
                    seed_daily_aggregates, seed_chunks = _baskets_daily_seed_from_recent_cache(
                        organization_id,
                        range_start=range_start,
                        range_end=range_end,
                    )
                    if seed_daily_aggregates:
                        previous_daily_aggregates = {**previous_daily_aggregates, **seed_daily_aggregates}
                        existing_chunk_keys: set[tuple[str, int]] = set()
                        for item in previous_chunks:
                            if not isinstance(item, dict) or item.get("date") is None or item.get("chunkIndex") is None:
                                continue
                            try:
                                existing_chunk_keys.add((str(item.get("date")), int(item.get("chunkIndex"))))
                            except (TypeError, ValueError):
                                continue
                        for chunk in seed_chunks:
                            try:
                                chunk_key = (str(chunk.get("date")), int(chunk.get("chunkIndex")))
                            except (TypeError, ValueError):
                                continue
                            if chunk_key not in existing_chunk_keys:
                                previous_chunks.append(chunk)
                                existing_chunk_keys.add(chunk_key)

                    def report_baskets_progress(progress: dict[str, Any]) -> None:
                        current = int(progress.get("processedNmIds") or 0)
                        total = int(progress.get("totalNmIds") or len(nm_ids))
                        completed_requests = int(progress.get("requestsCompleted") or 0)
                        total_requests = max(1, int(progress.get("requestsTotal") or 1))
                        update_step(
                            step,
                            phase=str(progress.get("phase") or "request"),
                            progressPercent=min(20, max(5, round(completed_requests / total_requests * 15) + 5)),
                            progressCurrent=current,
                            progressTotal=total,
                            message=str(progress.get("message") or f"Корзины за период: обработано {current} из {total} товаров"),
                            request=f"WB API · воронка продаж · запрос {min(completed_requests + 1, total_requests)} из {total_requests}",
                        )

                    payload = fetch_baskets_aggregates(
                        scenario,
                        wb_token=wb_token,
                        period_days=resolved_period_days,
                        date_from=range_start,
                        date_to=range_end,
                        nm_ids=[],
                        include_daily=False,
                        progress_callback=report_baskets_progress,
                    )
                    preserved_daily_aggregates = previous_daily_aggregates if not baskets_include_daily_detail else {}
                    preserved_chunks = previous_chunks if not baskets_include_daily_detail else []
                    if baskets_include_daily_detail:
                        daily_aggregates = previous_daily_aggregates
                        daily_status = "pending"
                    elif preserved_daily_aggregates:
                        daily_aggregates = preserved_daily_aggregates
                        daily_status = str(previous_baskets_cache.get("dailyDetailStatus") or "partial")
                    else:
                        daily_aggregates = payload.get("dailyAggregates") or {}
                        daily_status = "deferred"
                    payload = {
                        **payload,
                        "dailyAggregates": daily_aggregates,
                        "dailyAggregatesDays": len(daily_aggregates),
                        "dailyDetailStatus": daily_status,
                        **({"chunks": preserved_chunks} if preserved_chunks else {}),
                        **({"dailyDetailDeferredAt": _utc_now().isoformat()} if not baskets_include_daily_detail and not preserved_daily_aggregates else {}),
                        **({"dailyDetailPreservedAt": _utc_now().isoformat(), "dailyDetailPreservedBy": "aggregate_refresh"} if not baskets_include_daily_detail and preserved_daily_aggregates else {}),
                    }
                    save_source_cache(organization_id, baskets_cache_key, payload)

                    if baskets_include_daily_detail:
                        detail_failed_step: dict[str, Any] | None = None

                        def save_baskets_detail_day(day: str, day_rows: dict[str, Any], progress: dict[str, Any]) -> None:
                            existing_daily = payload.get("dailyAggregates") if isinstance(payload.get("dailyAggregates"), dict) else {}
                            next_daily = {**existing_daily, day: day_rows}
                            payload.update(
                                {
                                    "dailyAggregates": next_daily,
                                    "dailyAggregatesDays": len(next_daily),
                                    "dailyDetailStatus": "partial",
                                    "dailyDetailPartialAt": _utc_now().isoformat(),
                                    "dailyDetailRequestsCompleted": progress.get("requestsCompleted"),
                                    "dailyDetailRequestsTotal": progress.get("requestsTotal"),
                                }
                            )
                            save_source_cache(organization_id, baskets_cache_key, payload)

                        def save_baskets_detail_chunk(day: str, chunk_index: int, day_rows: dict[str, Any], progress: dict[str, Any]) -> None:
                            existing_daily = payload.get("dailyAggregates") if isinstance(payload.get("dailyAggregates"), dict) else {}
                            existing_day = existing_daily.get(day) if isinstance(existing_daily.get(day), dict) else {}
                            next_daily = {**existing_daily, day: {**existing_day, **day_rows}}
                            existing_chunks = payload.get("chunks") if isinstance(payload.get("chunks"), list) else []
                            chunk_status = str(progress.get("status") or ("failed" if progress.get("phase") == "failed" else "done"))
                            chunk_record = {
                                "type": "daily",
                                "date": day,
                                "chunkIndex": chunk_index,
                                "status": chunk_status,
                                "attempts": 1,
                                **({"lastError": str(progress.get("lastError"))} if progress.get("lastError") else {}),
                            }
                            next_chunks = [
                                item
                                for item in existing_chunks
                                if not (
                                    isinstance(item, dict)
                                    and item.get("type") == "daily"
                                    and item.get("date") == day
                                    and item.get("chunkIndex") == chunk_index
                                )
                            ]
                            next_chunks.append(chunk_record)
                            payload.update(
                                {
                                    "dailyAggregates": next_daily,
                                    "dailyAggregatesDays": len(next_daily),
                                    "dailyDetailStatus": "partial",
                                    "dailyDetailPartialAt": _utc_now().isoformat(),
                                    "dailyDetailRequestsCompleted": progress.get("requestsCompleted"),
                                    "dailyDetailRequestsTotal": progress.get("requestsTotal"),
                                    "chunks": next_chunks,
                                }
                            )
                            save_source_cache(organization_id, baskets_cache_key, payload)

                        def report_baskets_detail_progress(progress: dict[str, Any]) -> None:
                            completed_requests = int(progress.get("requestsCompleted") or 0)
                            total_requests = max(1, int(progress.get("requestsTotal") or 1))
                            day_index = int(progress.get("dayIndex") or 0)
                            days_total = int(progress.get("daysTotal") or resolved_period_days)
                            batch_index = int(progress.get("batch") or 0)
                            batches_total = int(progress.get("batchesTotal") or 0)
                            update_step(
                                step,
                                phase=str(progress.get("phase") or "daily-detail"),
                                progressPercent=min(99, max(21, 20 + round(completed_requests / total_requests * 79))),
                                progressCurrent=completed_requests,
                                progressTotal=total_requests,
                                message=str(progress.get("message") or f"Корзины по дням: обработано {completed_requests} из {total_requests} запросов"),
                                request=(
                                    f"WB API · дневная воронка · день {day_index}/{days_total}"
                                    + (f" · пачка SKU {batch_index}/{batches_total}" if batches_total else "")
                                ),
                            )

                        try:
                            detail = fetch_baskets_daily_detail(
                                scenario,
                                wb_token=wb_token,
                                date_from=range_start,
                                date_to=range_end,
                                nm_ids=[],
                                progress_callback=report_baskets_detail_progress,
                                existing_daily_aggregates=previous_daily_aggregates,
                                existing_chunks=previous_chunks,
                                day_completed_callback=save_baskets_detail_day,
                                chunk_completed_callback=save_baskets_detail_chunk,
                            )
                            payload = {
                                **payload,
                                "dailyAggregates": detail.get("dailyAggregates") or {},
                                "dailyAggregatesDays": len(detail.get("dailyAggregates") or {}),
                                "dailyDetailFetchedAt": _utc_now().isoformat(),
                                "dailyDetailStatus": "partial" if detail.get("failedChunks") else "fetched",
                                "dailyDetailRequestsCompleted": detail.get("requestsCompleted"),
                                "dailyDetailRequestsTotal": detail.get("requestsTotal"),
                                "chunks": detail.get("chunks") or payload.get("chunks") or [],
                                "failedChunks": detail.get("failedChunks") or [],
                                **({"dailyDetailError": f"Не удалось загрузить {len(detail.get('failedChunks') or [])} частей корзин. Повторите загрузку, чтобы добрать их."} if detail.get("failedChunks") else {}),
                            }
                            save_source_cache(organization_id, baskets_cache_key, payload)
                        except WbSalesFunnelDeferred as exc:
                            payload.update(
                                {
                                    "dailyDetailStatus": "partial",
                                    "dailyDetailPausedAt": _utc_now().isoformat(),
                                    "dailyDetailRetryAfterSeconds": int(round(exc.retry_after_seconds)),
                                    "dailyDetailError": str(exc),
                                }
                            )
                            save_source_cache(organization_id, baskets_cache_key, payload)
                            detail_failed_step = _step_paused("baskets", exc, count=int(payload.get("count") or 0), requestedNmIds=payload.get("requestedNmIds"), matchedNmIds=payload.get("matchedNmIds"))
                        except Exception as exc:
                            payload.update(
                                {
                                    "dailyDetailStatus": "partial",
                                    "dailyDetailError": _exception_message(exc),
                                    "dailyDetailFailedAt": _utc_now().isoformat(),
                                }
                            )
                            save_source_cache(organization_id, baskets_cache_key, payload)
                            detail_failed_step = _step_partial("baskets", exc, count=int(payload.get("count") or 0), requestedNmIds=payload.get("requestedNmIds"), matchedNmIds=payload.get("matchedNmIds"))
                    released_warmup_count = _release_warmup_goods_by_baskets(cached_goods, payload)
                    if baskets_include_daily_detail and detail_failed_step is not None:
                        finish_step(step, {**detail_failed_step, "releasedWarmupCount": released_warmup_count})
                    else:
                        finish_step(step, _step_ok("baskets", count=int(payload.get("count") or 0), requestedNmIds=payload.get("requestedNmIds"), matchedNmIds=payload.get("matchedNmIds"), releasedWarmupCount=released_warmup_count))
            except Exception as exc:
                finish_step(step, _step_error("baskets", exc))

        if execute_lock and set(resolved_sources) & {"goods", "content", "promotions", "stocks", "period-stats", "finance", "ads", "baskets"}:
            step = start_step("sku-snapshot")
            try:
                from app import repricer_bff as repricer_bff_module
                from app.routers.wb_repricer_bff import _build_repricer_sku_snapshot

                repricer_bff_module.fetch_commission_tariffs(scenario, wb_token=wb_token, force=True)
                snapshot = _build_repricer_sku_snapshot(
                    organization_id,
                    scenario,
                    wb_token=wb_token,
                    resolved_period_days=resolved_period_days,
                    period_suffix=period_suffix,
                    range_start=range_start,
                    range_end=range_end,
                    include_promotions=False,
                    include_content=False,
                )
                finish_step(
                    step,
                    _step_ok(
                        "sku-snapshot",
                        count=int(snapshot.get("total") or 0),
                        cacheKey=snapshot.get("sourceKey"),
                    ),
                )
            except Exception as exc:
                finish_step(step, _step_error("sku-snapshot", exc))

        state = "completed" if all(step.get("status") in {"ok", "skipped"} for step in steps) else "partial"
        return finish_wb_sync(organization_id, status, state=state, steps=steps) if execute_lock else {**status, "state": state, "steps": steps}
    except Exception as exc:
        fatal_error = str(exc)
        raise
    finally:
        if fatal_error and execute_lock:
            finish_wb_sync(organization_id, status, state="failed", steps=steps, error=fatal_error)
