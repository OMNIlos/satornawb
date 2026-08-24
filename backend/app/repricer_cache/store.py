from __future__ import annotations

import json
import re
import time
from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy import delete, select, text, update
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.infra.db import get_session_factory
from app.infra.redis_client import get_redis_client
from app.repricer_cache.orm import WbRepricerGoodsCacheRow, WbRepricerSourceCacheRow

_REDIS_CACHE_TTL_SECONDS = 45
_REDIS_DISABLED_UNTIL = 0.0


def _optional_date(value: Any) -> date | None:
    try:
        return date.fromisoformat(str(value)[:10]) if value else None
    except (TypeError, ValueError):
        return None


def _optional_int(value: Any) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _source_cache_range_from_key(source_key: str) -> tuple[date | None, date | None]:
    dates = [_optional_date(value) for value in re.findall(r"\d{4}-\d{2}-\d{2}", source_key)]
    valid_dates = [value for value in dates if value is not None]
    return (valid_dates[-2], valid_dates[-1]) if len(valid_dates) >= 2 else (None, None)


def _source_cache_metadata(source_key: str, payload: dict[str, Any]) -> dict[str, Any]:
    daily_aggregates = payload.get("dailyAggregates")
    daily_dates = sorted(
        date_key
        for key in daily_aggregates.keys()
        if isinstance(daily_aggregates, dict)
        and (parsed := _optional_date(key)) is not None
        and (date_key := parsed.isoformat())
    ) if isinstance(daily_aggregates, dict) else []
    key_date_from, key_date_to = _source_cache_range_from_key(source_key)
    return {
        "range_date_from": _optional_date(payload.get("dateFrom")) or key_date_from,
        "range_date_to": _optional_date(payload.get("dateTo")) or key_date_to,
        "daily_detail_status": str(payload["dailyDetailStatus"]) if payload.get("dailyDetailStatus") is not None else None,
        "daily_detail_error": str(payload["dailyDetailError"]) if payload.get("dailyDetailError") is not None else None,
        "daily_detail_deferred_at": payload.get("dailyDetailDeferredAt"),
        "daily_detail_paused_at": payload.get("dailyDetailPausedAt"),
        "daily_detail_failed_at": payload.get("dailyDetailFailedAt"),
        "daily_detail_fetched_at": payload.get("dailyDetailFetchedAt"),
        "daily_detail_partial_at": payload.get("dailyDetailPartialAt"),
        "daily_detail_preserved_at": payload.get("dailyDetailPreservedAt"),
        "daily_detail_preserved_by": payload.get("dailyDetailPreservedBy"),
        "daily_detail_requests_completed": _optional_int(payload.get("dailyDetailRequestsCompleted")),
        "daily_detail_requests_total": _optional_int(payload.get("dailyDetailRequestsTotal")),
        "daily_aggregate_dates": daily_dates,
    }


def _run_db(db_fn):
    try:
        session_factory = get_session_factory()
        with session_factory() as session:
            return db_fn(session)
    except SQLAlchemyError:
        return None


def _redis_available() -> bool:
    return time.monotonic() >= _REDIS_DISABLED_UNTIL


def _disable_redis_briefly() -> None:
    global _REDIS_DISABLED_UNTIL
    _REDIS_DISABLED_UNTIL = time.monotonic() + 5


def _redis_get_json(key: str) -> dict[str, Any] | None:
    if not _redis_available():
        return None
    try:
        raw = get_redis_client().get(key)
        if raw is None:
            return None
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")
        payload = json.loads(raw)
        return payload if isinstance(payload, dict) else None
    except Exception:
        _disable_redis_briefly()
        return None


def _redis_get_json_list(key: str) -> list[dict[str, Any]] | None:
    if not _redis_available():
        return None
    try:
        raw = get_redis_client().get(key)
        if raw is None:
            return None
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")
        payload = json.loads(raw)
        if not isinstance(payload, list):
            return None
        return [item for item in payload if isinstance(item, dict)]
    except Exception:
        _disable_redis_briefly()
        return None


def _redis_set_json_list(key: str, payload: list[dict[str, Any]], *, ttl: int = _REDIS_CACHE_TTL_SECONDS) -> None:
    if not _redis_available():
        return
    try:
        get_redis_client().setex(key, ttl, json.dumps(payload, ensure_ascii=False, separators=(",", ":")))
    except Exception:
        _disable_redis_briefly()


def _redis_set_json(key: str, payload: dict[str, Any], *, ttl: int = _REDIS_CACHE_TTL_SECONDS) -> None:
    if not _redis_available():
        return
    try:
        get_redis_client().setex(key, ttl, json.dumps(payload, ensure_ascii=False, separators=(",", ":")))
    except Exception:
        _disable_redis_briefly()


def _redis_delete(*keys: str) -> None:
    if not keys or not _redis_available():
        return
    try:
        get_redis_client().delete(*keys)
    except Exception:
        _disable_redis_briefly()


def _redis_delete_pattern(pattern: str) -> None:
    if not _redis_available():
        return
    try:
        client = get_redis_client()
        keys = list(client.scan_iter(match=pattern, count=100))
        if keys:
            client.delete(*keys)
    except Exception:
        _disable_redis_briefly()


def _goods_meta_cache_key(organization_id: int) -> str:
    return f"vella:repricer:goods-meta:{organization_id}"


def _goods_list_cache_key(organization_id: int) -> str:
    return f"vella:repricer:goods-list:{organization_id}"


def _source_cache_key(organization_id: int, source_key: str, *, slim: bool) -> str:
    return f"vella:repricer:source-cache:{organization_id}:{source_key}:slim{1 if slim else 0}"


def _source_cache_redis_allowed(source_key: str, *, slim: bool) -> bool:
    if source_key.startswith("sku_list_snapshot_"):
        return not slim
    if source_key.startswith("baskets_detail_status_"):
        return True
    if source_key in {
        "wb_sync_status",
        "reports_payload_materialization_status",
        "baskets_detail_active",
        "excel_imports",
        "promotion_thresholds",
    }:
        return True
    return False


def list_cached_goods_pages(organization_id: int) -> list[WbRepricerGoodsCacheRow]:
    def _db(session: Session) -> list[WbRepricerGoodsCacheRow]:
        return list(
            session.scalars(
                select(WbRepricerGoodsCacheRow)
                .where(WbRepricerGoodsCacheRow.organization_id == organization_id)
                .order_by(WbRepricerGoodsCacheRow.page_offset.asc())
            ).all()
        )

    return _run_db(_db) or []


def _slim_good_payload(item: dict[str, Any]) -> dict[str, Any]:
    sizes = item.get("sizes") or []
    first_size = sizes[0] if isinstance(sizes, list) and sizes and isinstance(sizes[0], dict) else {}
    return {
        "vendorCode": item.get("vendorCode"),
        "nmID": item.get("nmID"),
        "brand": item.get("brand"),
        "subjectName": item.get("subjectName"),
        "subjectID": item.get("subjectID"),
        "subjectId": item.get("subjectId"),
        "objectID": item.get("objectID"),
        "objectId": item.get("objectId"),
        "clubDiscount": item.get("clubDiscount"),
        "photos": item.get("photos"),
        "mediaFiles": item.get("mediaFiles"),
        "photoUrl": item.get("photoUrl") or item.get("imageUrl"),
        "sizes": [first_size] if first_size else [],
    }


def _slim_content_card(card: dict[str, Any]) -> dict[str, Any]:
    slim_sizes: list[dict[str, Any]] = []
    for size in card.get("sizes") or []:
        if not isinstance(size, dict):
            continue
        slim_sizes.append({"skus": size.get("skus") or []})
    return {
        "vendorCode": card.get("vendorCode"),
        "nmID": card.get("nmID"),
        "title": card.get("title"),
        "object": card.get("object"),
        "objectID": card.get("objectID"),
        "objectId": card.get("objectId"),
        "subjectName": card.get("subjectName"),
        "subjectID": card.get("subjectID"),
        "subjectId": card.get("subjectId"),
        "brand": card.get("brand"),
        "photos": card.get("photos"),
        "mediaFiles": card.get("mediaFiles"),
        "photoUrl": card.get("photoUrl") or card.get("imageUrl"),
        "sizes": slim_sizes,
    }


def _slim_promotion(promotion: dict[str, Any]) -> dict[str, Any]:
    article_ids = promotion.get("articleIds") or []
    if isinstance(article_ids, set):
        article_ids = sorted(article_ids)
    threshold_nm_ids = []
    for item in promotion.get("thresholdNmIds") or []:
        try:
            threshold_nm_ids.append(int(item))
        except (TypeError, ValueError):
            continue
    threshold_statuses_by_nm_id = {}
    if isinstance(promotion.get("thresholdStatusesByNmId"), dict):
        threshold_statuses_by_nm_id = {
            str(key): str(value)
            for key, value in promotion["thresholdStatusesByNmId"].items()
            if key is not None and value
        }
    return {
        "id": promotion.get("id"),
        "name": promotion.get("name"),
        "type": promotion.get("type"),
        "status": promotion.get("status"),
        "startDate": promotion.get("startDate"),
        "endDate": promotion.get("endDate"),
        "daysUntilEnd": promotion.get("daysUntilEnd"),
        "daysUntilStart": promotion.get("daysUntilStart"),
        "eligibleSkuCount": promotion.get("eligibleSkuCount"),
        "participatingSkuCount": promotion.get("participatingSkuCount"),
        "participationPct": promotion.get("participationPct"),
        "excelLoaded": promotion.get("excelLoaded"),
        "excelStatus": promotion.get("excelStatus"),
        "excelFileName": promotion.get("excelFileName"),
        "excelLoadedAt": promotion.get("excelLoadedAt"),
        "thresholdRowsParsed": promotion.get("thresholdRowsParsed"),
        "thresholdNmIds": threshold_nm_ids,
        "thresholdStatusesByNmId": threshold_statuses_by_nm_id,
        "articleIds": [str(item) for item in article_ids if item],
    }


def slim_source_cache_payload(source_key: str, payload: dict[str, Any]) -> dict[str, Any]:
    slim = dict(payload)
    if source_key.startswith("finance_"):
        slim.pop("rows", None)
        return slim
    if source_key == "content_cards":
        cards = payload.get("cards")
        if isinstance(cards, list):
            slim["cards"] = [_slim_content_card(card) for card in cards if isinstance(card, dict)]
        return slim
    if source_key == "promotions":
        promotions = payload.get("promotions")
        if isinstance(promotions, list):
            slim["promotions"] = [_slim_promotion(item) for item in promotions if isinstance(item, dict)]
        return slim
    return slim


def list_cached_goods(organization_id: int) -> list[dict[str, Any]]:
    redis_key = _goods_list_cache_key(organization_id)
    cached = _redis_get_json_list(redis_key)
    if cached is not None:
        return cached

    goods: list[dict[str, Any]] = []
    seen: set[str] = set()
    for page in list_cached_goods_pages(organization_id):
        for item in page.goods_payload or []:
            if not isinstance(item, dict):
                continue
            vendor_code = str(item.get("vendorCode") or "")
            dedupe_key = vendor_code or str(item.get("nmID") or "")
            if not dedupe_key or dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            goods.append(_slim_good_payload(item))
    _redis_set_json_list(redis_key, goods)
    return goods


def cached_goods_meta(organization_id: int) -> dict[str, Any]:
    redis_key = _goods_meta_cache_key(organization_id)
    cached = _redis_get_json(redis_key)
    if cached is not None:
        return cached

    def _db(session: Session) -> dict[str, Any]:
        row = session.execute(
            text(
                """
                SELECT
                    count(*) AS pages_cached,
                    coalesce(sum(json_array_length(goods_payload)), 0) AS total_cached,
                    coalesce(max(page_offset + page_limit), 0) AS next_offset,
                    coalesce(max(page_limit), 1000) AS page_limit,
                    max(fetched_at) AS latest_fetched_at
                FROM wb_repricer_goods_cache
                WHERE organization_id = :organization_id
                """
            ),
            {"organization_id": organization_id},
        ).mappings().first()
        latest_fetched_at = row["latest_fetched_at"].isoformat() if row and row["latest_fetched_at"] else None
        return {
            "pagesCached": int(row["pages_cached"] or 0) if row else 0,
            "totalCached": int(row["total_cached"] or 0) if row else 0,
            "nextOffset": int(row["next_offset"] or 0) if row else 0,
            "pageLimit": int(row["page_limit"] or 1000) if row else 1000,
            "latestFetchedAt": latest_fetched_at,
        }

    meta = _run_db(_db) or {
        "pagesCached": 0,
        "totalCached": 0,
        "nextOffset": 0,
        "pageLimit": 1000,
        "latestFetchedAt": None,
    }
    _redis_set_json(redis_key, meta)
    return meta


def save_goods_page(
    *,
    organization_id: int,
    page_offset: int,
    page_limit: int,
    goods: list[dict[str, Any]],
    wb_request_id: str | None,
    replace_all: bool = False,
) -> dict[str, Any]:
    now = datetime.now(timezone.utc)

    def _db(session: Session) -> dict[str, Any]:
        if replace_all:
            session.execute(delete(WbRepricerGoodsCacheRow).where(WbRepricerGoodsCacheRow.organization_id == organization_id))
        row = session.scalar(
            select(WbRepricerGoodsCacheRow).where(
                WbRepricerGoodsCacheRow.organization_id == organization_id,
                WbRepricerGoodsCacheRow.page_offset == page_offset,
                WbRepricerGoodsCacheRow.page_limit == page_limit,
            )
        )
        if row is None:
            row = WbRepricerGoodsCacheRow(
                organization_id=organization_id,
                page_offset=page_offset,
                page_limit=page_limit,
                goods_payload=goods,
                wb_request_id=wb_request_id,
                fetched_at=now,
                updated_at=now,
            )
            session.add(row)
        else:
            row.goods_payload = goods
            row.wb_request_id = wb_request_id
            row.fetched_at = now
            row.updated_at = now
        session.commit()
        _redis_delete(_goods_meta_cache_key(organization_id), _goods_list_cache_key(organization_id))
        return cached_goods_meta(organization_id)

    return _run_db(_db) or {
        "pagesCached": 0,
        "totalCached": 0,
        "nextOffset": 0,
        "pageLimit": page_limit,
        "latestFetchedAt": None,
    }


def compact_heavy_source_cache_rows(organization_id: int) -> None:
    """Drop finance raw rows in Postgres without loading the full JSON into app memory."""
    _redis_delete_pattern(f"vella:repricer:source-cache:{organization_id}:finance_*")

    def _db(session: Session) -> None:
        now = datetime.now(timezone.utc)
        session.execute(
            text(
                """
                UPDATE wb_repricer_source_cache
                SET payload = (payload::jsonb - 'rows')::json,
                    updated_at = :updated_at
                WHERE organization_id = :organization_id
                  AND source_key LIKE 'finance_%'
                  AND (payload::jsonb ? 'rows')
                """
            ),
            {"organization_id": organization_id, "updated_at": now},
        )
        session.commit()

    _run_db(_db)


def get_source_cache(
    organization_id: int,
    source_key: str,
    *,
    slim: bool = False,
) -> dict[str, Any] | None:
    redis_key = _source_cache_key(organization_id, source_key, slim=slim)
    redis_allowed = _source_cache_redis_allowed(source_key, slim=slim)
    if redis_allowed:
        cached = _redis_get_json(redis_key)
        if cached is not None:
            return cached

    def _db(session: Session) -> dict[str, Any] | None:
        row = session.scalar(
            select(WbRepricerSourceCacheRow).where(
                WbRepricerSourceCacheRow.organization_id == organization_id,
                WbRepricerSourceCacheRow.source_key == source_key,
            )
        )
        if row is None:
            return None
        payload = dict(row.payload or {})
        payload.setdefault("fetchedAt", row.fetched_at.isoformat())
        if slim:
            return slim_source_cache_payload(source_key, payload)
        return payload

    payload = _run_db(_db)
    if payload is not None and redis_allowed:
        _redis_set_json(redis_key, payload)
    return payload


def get_source_cache_by_source_key(
    source_key: str,
    *,
    slim: bool = False,
) -> dict[str, Any] | None:
    def _db(session: Session) -> dict[str, Any] | None:
        row = session.scalar(
            select(WbRepricerSourceCacheRow)
            .where(WbRepricerSourceCacheRow.source_key == source_key)
            .order_by(WbRepricerSourceCacheRow.fetched_at.desc())
            .limit(1)
        )
        if row is None:
            return None
        payload = dict(row.payload or {})
        payload.setdefault("fetchedAt", row.fetched_at.isoformat())
        payload["organizationId"] = row.organization_id
        payload["sourceKey"] = row.source_key
        return slim_source_cache_payload(row.source_key, payload) if slim else payload

    return _run_db(_db)


def list_source_cache_by_prefix(
    organization_id: int,
    source_key_prefix: str,
    *,
    limit: int = 25,
    slim: bool = False,
) -> list[dict[str, Any]]:
    safe_limit = max(1, min(100, int(limit)))

    def _db(session: Session) -> list[dict[str, Any]]:
        rows = list(
            session.scalars(
                select(WbRepricerSourceCacheRow)
                .where(
                    WbRepricerSourceCacheRow.organization_id == organization_id,
                    WbRepricerSourceCacheRow.source_key.like(f"{source_key_prefix}%"),
                )
                .order_by(WbRepricerSourceCacheRow.fetched_at.desc())
                .limit(safe_limit)
            ).all()
        )
        result: list[dict[str, Any]] = []
        for row in rows:
            payload = dict(row.payload or {})
            payload.setdefault("fetchedAt", row.fetched_at.isoformat())
            payload["sourceKey"] = row.source_key
            result.append(slim_source_cache_payload(row.source_key, payload) if slim else payload)
        return result

    return _run_db(_db) or []


def list_source_cache_ranges_by_prefix(
    organization_id: int,
    source_key_prefix: str,
    *,
    limit: int = 100,
) -> list[dict[str, Any]]:
    safe_limit = max(1, min(500, int(limit)))

    def _db(session: Session) -> list[dict[str, Any]]:
        rows = session.execute(
            text(
                """
                SELECT
                    source_key,
                    range_date_from,
                    range_date_to,
                    daily_detail_status,
                    daily_detail_error,
                    daily_detail_deferred_at,
                    daily_detail_paused_at,
                    daily_detail_failed_at,
                    daily_detail_fetched_at,
                    daily_detail_partial_at,
                    daily_detail_preserved_at,
                    daily_detail_preserved_by,
                    daily_detail_requests_completed,
                    daily_detail_requests_total,
                    daily_aggregate_dates,
                    fetched_at
                FROM wb_repricer_source_cache
                WHERE organization_id = :organization_id
                  AND source_key LIKE :source_key_pattern
                ORDER BY fetched_at DESC
                LIMIT :limit
                """
            ),
            {
                "organization_id": organization_id,
                "source_key_pattern": f"{source_key_prefix}%",
                "limit": safe_limit,
            },
        ).mappings()
        result: list[dict[str, Any]] = []
        for row in rows:
            key_date_from, key_date_to = _source_cache_range_from_key(row["source_key"])
            range_date_from = row["range_date_from"] or key_date_from
            range_date_to = row["range_date_to"] or key_date_to
            daily_dates = sorted(str(value)[:10] for value in (row["daily_aggregate_dates"] or []) if value)
            result.append(
                {
                    "sourceKey": row["source_key"],
                    "dateFrom": range_date_from.isoformat() if isinstance(range_date_from, date) else range_date_from,
                    "dateTo": range_date_to.isoformat() if isinstance(range_date_to, date) else range_date_to,
                    "dailyDetailStatus": row["daily_detail_status"],
                    "dailyDetailError": row["daily_detail_error"],
                    "dailyDetailDeferredAt": row["daily_detail_deferred_at"],
                    "dailyDetailPausedAt": row["daily_detail_paused_at"],
                    "dailyDetailFailedAt": row["daily_detail_failed_at"],
                    "dailyDetailFetchedAt": row["daily_detail_fetched_at"],
                    "dailyDetailPartialAt": row["daily_detail_partial_at"],
                    "dailyDetailPreservedAt": row["daily_detail_preserved_at"],
                    "dailyDetailPreservedBy": row["daily_detail_preserved_by"],
                    "dailyDetailRequestsCompleted": row["daily_detail_requests_completed"],
                    "dailyDetailRequestsTotal": row["daily_detail_requests_total"],
                    "dailyAggregatesDays": len(daily_dates) if daily_dates else None,
                    "dailyAggregateDates": daily_dates,
                    "fetchedAt": row["fetched_at"].isoformat() if row["fetched_at"] else None,
                }
            )
        return result

    return _run_db(_db) or []


def get_covering_source_cache(
    organization_id: int,
    source_key_prefix: str,
    *,
    date_from: date,
    date_to: date,
    slim: bool = False,
) -> dict[str, Any] | None:
    def _db(session: Session) -> dict[str, Any] | None:
        row = session.scalar(
            select(WbRepricerSourceCacheRow)
            .where(
                WbRepricerSourceCacheRow.organization_id == organization_id,
                WbRepricerSourceCacheRow.source_key.like(f"{source_key_prefix}%"),
                text("(payload::jsonb ? 'dailyAggregates')"),
                text("jsonb_typeof((payload::jsonb)->'dailyAggregates') = 'object'"),
                text("(payload::jsonb)->'dailyAggregates' <> '{}'::jsonb"),
                text("(payload->>'dateFrom') <= :date_from"),
                text("(payload->>'dateTo') >= :date_to"),
            )
            .params(date_from=date_from.isoformat(), date_to=date_to.isoformat())
            .order_by(WbRepricerSourceCacheRow.fetched_at.desc())
            .limit(1)
        )
        if row is None:
            return None
        payload = dict(row.payload or {})
        payload.setdefault("fetchedAt", row.fetched_at.isoformat())
        payload["sourceKey"] = row.source_key
        return slim_source_cache_payload(row.source_key, payload) if slim else payload

    return _run_db(_db)


def get_source_cache_fetched_at(organization_id: int, source_key: str) -> str | None:
    if _source_cache_redis_allowed(source_key, slim=True):
        cached = _redis_get_json(_source_cache_key(organization_id, source_key, slim=True))
        if cached is not None:
            fetched_at = cached.get("fetchedAt")
            return str(fetched_at) if fetched_at else None

    def _db(session: Session) -> str | None:
        row = session.scalar(
            select(WbRepricerSourceCacheRow.fetched_at).where(
                WbRepricerSourceCacheRow.organization_id == organization_id,
                WbRepricerSourceCacheRow.source_key == source_key,
            )
        )
        return row.isoformat() if row is not None else None

    return _run_db(_db)


def get_source_cache_meta_fields(organization_id: int, source_key: str) -> dict[str, Any]:
    if _source_cache_redis_allowed(source_key, slim=True):
        cached = _redis_get_json(_source_cache_key(organization_id, source_key, slim=True))
        if cached is not None:
            fetched_at = cached.get("fetchedAt")
            if source_key.startswith("finance_"):
                return {
                    "fetchedAt": fetched_at,
                    "cachedGoodsNmIds": cached.get("cachedGoodsNmIds"),
                    "matchedCachedGoodsNmIds": cached.get("matchedCachedGoodsNmIds"),
                }
            if source_key.startswith("baskets_"):
                return {
                    "fetchedAt": fetched_at,
                    "requestedNmIds": cached.get("requestedNmIds"),
                    "matchedNmIds": cached.get("matchedNmIds"),
                }
            return {"fetchedAt": fetched_at} if fetched_at else {}

    def _optional_int(value: Any) -> int | None:
        try:
            return int(value) if value is not None else None
        except (TypeError, ValueError):
            return None

    def _db(session: Session) -> dict[str, Any]:
        row = session.execute(
            text(
                """
                SELECT
                    fetched_at,
                    payload->>'cachedGoodsNmIds' AS cached_goods_nm_ids,
                    payload->>'matchedCachedGoodsNmIds' AS matched_cached_goods_nm_ids,
                    payload->>'requestedNmIds' AS requested_nm_ids,
                    payload->>'matchedNmIds' AS matched_nm_ids
                FROM wb_repricer_source_cache
                WHERE organization_id = :organization_id
                  AND source_key = :source_key
                LIMIT 1
                """
            ),
            {"organization_id": organization_id, "source_key": source_key},
        ).mappings().first()
        if row is None:
            return {}
        fetched_at = row["fetched_at"].isoformat() if row["fetched_at"] else None
        if source_key.startswith("finance_"):
            return {
                "fetchedAt": fetched_at,
                "cachedGoodsNmIds": _optional_int(row["cached_goods_nm_ids"]),
                "matchedCachedGoodsNmIds": _optional_int(row["matched_cached_goods_nm_ids"]),
            }
        if source_key.startswith("baskets_"):
            return {
                "fetchedAt": fetched_at,
                "requestedNmIds": _optional_int(row["requested_nm_ids"]),
                "matchedNmIds": _optional_int(row["matched_nm_ids"]),
            }
        return {"fetchedAt": fetched_at} if fetched_at else {}

    return _run_db(_db) or {}


def save_source_cache(organization_id: int, source_key: str, payload: dict[str, Any]) -> dict[str, Any]:
    stored_payload = dict(payload)
    if source_key.startswith("finance_"):
        stored_payload.pop("rows", None)
    now = datetime.now(timezone.utc)
    metadata = _source_cache_metadata(source_key, stored_payload)
    _redis_delete(
        _source_cache_key(organization_id, source_key, slim=False),
        _source_cache_key(organization_id, source_key, slim=True),
    )
    redis_full_allowed = _source_cache_redis_allowed(source_key, slim=False)
    redis_slim_allowed = _source_cache_redis_allowed(source_key, slim=True)

    def _db(session: Session) -> dict[str, Any]:
        update_statement = (
            update(WbRepricerSourceCacheRow)
            .where(
                WbRepricerSourceCacheRow.organization_id == organization_id,
                WbRepricerSourceCacheRow.source_key == source_key,
            )
            .values(payload=stored_payload, fetched_at=now, updated_at=now, **metadata)
        )
        result = session.execute(update_statement)
        if result.rowcount == 0:
            row = WbRepricerSourceCacheRow(
                organization_id=organization_id,
                source_key=source_key,
                payload=stored_payload,
                fetched_at=now,
                updated_at=now,
                **metadata,
            )
            session.add(row)
            try:
                session.commit()
            except IntegrityError:
                session.rollback()
                session.execute(update_statement)
                session.commit()
        else:
            session.commit()
        result = dict(stored_payload)
        result["fetchedAt"] = now.isoformat()
        if redis_full_allowed:
            _redis_set_json(_source_cache_key(organization_id, source_key, slim=False), result)
        if redis_slim_allowed:
            _redis_set_json(_source_cache_key(organization_id, source_key, slim=True), slim_source_cache_payload(source_key, result))
        return result

    result = _run_db(_db)
    if result is not None:
        return result
    fallback = dict(stored_payload)
    fallback["fetchedAt"] = now.isoformat()
    return fallback
