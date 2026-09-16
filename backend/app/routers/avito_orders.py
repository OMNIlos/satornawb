from __future__ import annotations

import hashlib
import html
import re
import secrets
from datetime import date, datetime, timedelta, timezone
from typing import Any

import httpx
from fastapi import APIRouter, HTTPException, Query, Request, Response

from app.avito.auth import resolve_user_avito_access_token
from app.avito.listings import AvitoListingDetailsFetchRequest, AvitoListingsFetchRequest, build_avito_listings_client
from app.avito.orders import (
    AVITO_ORDER_STATUSES,
    AvitoOrderRow,
    AvitoOrdersBrowserSnapshot,
    AvitoOrdersFetchRequest,
    build_avito_orders_client,
    merge_browser_snapshot_orders,
)
from app.avito.orders_ai import enrich_avito_orders_snapshot_with_ai
from app.avito.orders_picking_xlsx import build_avito_orders_picking_xlsx
from app.avito.returns import AvitoReturnCandidate, extract_return_candidates, match_return_candidates
from app.avito.returns_store import enrich_existing_return_candidates, list_active_return_candidates
from app.avito.returns_tasks import (
    AVITO_RETURNS_SYNC_STATUS_KEY,
    get_returns_sync_settings,
    save_returns_sync_settings,
)
from app.cabinet.store import get_organization_avito_credentials_secret, get_user_avito_credentials_secret
from app.config import get_settings
from app.control_plane.auth import actor_from_request, has_permission
from app.repricer_cache.store import get_source_cache, get_source_cache_by_source_key, save_source_cache


router = APIRouter(tags=["avito-orders"])

AVITO_ORDERS_BROWSER_SNAPSHOT_KEY = "avito_orders_browser_snapshot"
AVITO_ORDERS_EXTENSION_TOKEN_KEY = "avito_orders_extension_token"
AVITO_ORDERS_EXTENSION_TOKEN_PREFIX = "avito_orders_extension_token_hash_"

_AVITO_PUBLIC_COLOR_CACHE: dict[str, str | None] = {}


def _date_from(value: date | None, period_days: int) -> tuple[date, int]:
    today = date.today()
    start = value or (today - timedelta(days=period_days - 1))
    if start > today:
        start = today - timedelta(days=period_days - 1)
    days = (today - start).days + 1
    if days <= 0:
        raise HTTPException(status_code=422, detail="AVITO_ORDERS_INVALID_PERIOD")
    if days > 183:
        raise HTTPException(status_code=422, detail="AVITO_ORDERS_PERIOD_TOO_DEEP")
    return start, days


def _statuses(values: list[str]) -> list[str]:
    normalized: list[str] = []
    allowed = set(AVITO_ORDER_STATUSES)
    for value in values:
        for part in str(value).split(","):
            status = part.strip()
            if not status:
                continue
            if status not in allowed:
                raise HTTPException(status_code=422, detail=f"AVITO_ORDERS_UNKNOWN_STATUS:{status}")
            normalized.append(status)
    return list(dict.fromkeys(normalized))


def _cache_key(start: date, statuses: list[str], page: int, limit: int) -> str:
    status_part = ",".join(statuses) if statuses else "all"
    return f"avito_orders:{start.isoformat()}:{status_part}:p{page}:l{limit}"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _extension_bearer_token(request: Request) -> str | None:
    authorization = request.headers.get("authorization") or ""
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        return None
    raw = token.strip()
    return raw if raw.startswith("sat_avito_") else None


def _hash_extension_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _extension_token_source_key(token_hash: str) -> str:
    return f"{AVITO_ORDERS_EXTENSION_TOKEN_PREFIX}{token_hash}"


def _extension_token_status_payload(payload: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(payload, dict) or not payload.get("activeHash"):
        return {"configured": False}
    return {
        "configured": True,
        "tokenPrefix": payload.get("tokenPrefix"),
        "createdAt": payload.get("createdAt"),
        "rotatedAt": payload.get("rotatedAt"),
        "lastUsedAt": payload.get("lastUsedAt"),
    }


def _returns_sync_settings_payload(organization_id: int) -> dict[str, Any]:
    sync_settings = get_returns_sync_settings(organization_id)
    sync_status = get_source_cache(organization_id, AVITO_RETURNS_SYNC_STATUS_KEY, slim=False) or {}
    candidates = _enriched_return_candidates(organization_id)
    last_auto = sync_settings.get("lastAutoDispatchedAt")
    next_run_at = None
    if last_auto:
        try:
            last_dt = datetime.fromisoformat(str(last_auto).replace("Z", "+00:00"))
            if last_dt.tzinfo is None:
                last_dt = last_dt.replace(tzinfo=timezone.utc)
            next_run_at = (last_dt + timedelta(minutes=int(sync_settings["intervalMinutes"]))).isoformat()
        except (TypeError, ValueError):
            next_run_at = None
    return {
        **sync_settings,
        "nextRunAt": next_run_at,
        "status": sync_status if isinstance(sync_status, dict) else {},
        "inventory": _return_inventory_meta(candidates, 0),
        "items": [candidate.model_dump(mode="json") for candidate in candidates[:500]],
    }


def _resolve_extension_token_organization(token: str) -> int | None:
    token_hash = _hash_extension_token(token)
    token_row = get_source_cache_by_source_key(_extension_token_source_key(token_hash), slim=False) or None
    if not isinstance(token_row, dict):
        return None
    organization_id = token_row.get("organizationId")
    try:
        resolved_organization_id = int(organization_id)
    except (TypeError, ValueError):
        return None
    status = get_source_cache(resolved_organization_id, AVITO_ORDERS_EXTENSION_TOKEN_KEY, slim=False) or {}
    if status.get("activeHash") != token_hash:
        return None
    status["lastUsedAt"] = _now_iso()
    save_source_cache(resolved_organization_id, AVITO_ORDERS_EXTENSION_TOKEN_KEY, status)
    return resolved_organization_id


def _cache_hit_payload(cached: dict[str, Any]) -> dict[str, Any]:
    payload = dict(cached)
    source = dict(payload.get("source") or {})
    cache = dict(source.get("cache") or {})
    cache["status"] = "hit"
    source["cache"] = cache
    source["error"] = None
    payload["source"] = source
    return payload


def _browser_snapshot_from_cache(organization_id: int) -> AvitoOrdersBrowserSnapshot | None:
    cached = get_source_cache(organization_id, AVITO_ORDERS_BROWSER_SNAPSHOT_KEY, slim=False) or None
    if not isinstance(cached, dict):
        return None
    try:
        return AvitoOrdersBrowserSnapshot.model_validate(cached)
    except Exception:
        return None


def _browser_snapshot_meta(snapshot: AvitoOrdersBrowserSnapshot | None) -> dict[str, Any] | None:
    if snapshot is None:
        return None
    collector = snapshot.collector or {}
    ai_extraction = snapshot.aiExtraction or {}
    return {
        "capturedAt": snapshot.capturedAt,
        "pageUrl": snapshot.pageUrl,
        "orders": len(snapshot.orders),
        "returns": len(snapshot.returns),
        "items": sum(len(order.items) for order in [*snapshot.orders, *snapshot.returns]),
        "collector": collector,
        "aiExtraction": ai_extraction,
    }


def _int_or_zero(value: int | None) -> int:
    return value if value is not None else 0


def _summary(rows: list[AvitoOrderRow], total: int) -> dict[str, Any]:
    status_counts: dict[str, int] = {}
    action_required = 0
    returns = 0
    disputes = 0
    totals = [row.totalKopecks for row in rows if row.totalKopecks is not None]
    for row in rows:
        status_counts[row.status] = status_counts.get(row.status, 0) + 1
        if any(action.required for action in row.availableActions):
            action_required += 1
        if row.status == "on_return" or row.returnStatus:
            returns += 1
        if row.status == "in_dispute":
            disputes += 1
    return {
        "total": total or len(rows),
        "shown": len(rows),
        "confirmation": status_counts.get("on_confirmation", 0),
        "readyToShip": status_counts.get("ready_to_ship", 0),
        "inTransit": status_counts.get("in_transit", 0),
        "delivered": status_counts.get("delivered", 0),
        "closed": status_counts.get("closed", 0),
        "canceled": status_counts.get("canceled", 0),
        "returns": returns,
        "disputes": disputes,
        "requiredActions": action_required,
        "items": sum(sum(item.quantity for item in row.items) for row in rows),
        "totalKopecks": sum(_int_or_zero(value) for value in totals) if totals else None,
        "statusCounts": status_counts,
    }


def _response_payload(
    *,
    status: str,
    start: date,
    days: int,
    statuses: list[str],
    page: int,
    limit: int,
    rows: list[AvitoOrderRow],
    total: int,
    diagnostics: dict[str, Any] | None = None,
    error: Any | None = None,
    browser_snapshot: AvitoOrdersBrowserSnapshot | None = None,
    return_inventory: dict[str, Any] | None = None,
) -> dict[str, Any]:
    settings = get_settings()
    return {
        "status": status,
        "period": {"dateFrom": start.isoformat(), "days": days},
        "filters": {"statuses": statuses, "page": page, "limit": limit},
        "summary": _summary(rows, total),
        "rows": [row.model_dump(mode="json") for row in rows],
        "source": {
            "mode": "live",
            "cache": {"status": "fresh", "savedAt": datetime.now(timezone.utc).isoformat()},
            "api": {
                "ordersEndpoint": "GET /order-management/1/orders",
                "transitionEndpoint": "POST /order-management/1/order/applyTransition",
                "maxDepthDays": 183,
                "readOnly": True,
                "baseUrl": settings.avito_api_base_url,
            },
            "diagnostics": diagnostics,
            "error": error,
            "browserSnapshot": _browser_snapshot_meta(browser_snapshot),
            "returnInventory": return_inventory,
        },
    }


def _merge_browser_snapshot_payload(payload: dict[str, Any], *, organization_id: int) -> dict[str, Any]:
    snapshot = _browser_snapshot_from_cache(organization_id)
    if snapshot is None:
        return _attach_return_inventory_payload(payload, organization_id=organization_id)
    rows = [AvitoOrderRow.model_validate(row) for row in payload.get("rows") or [] if isinstance(row, dict)]
    merge_browser_snapshot_orders(rows, snapshot)
    _enrich_missing_colors_from_public_avito(rows)
    payload["rows"] = [row.model_dump(mode="json") for row in rows]
    summary = dict(payload.get("summary") or {})
    summary.update(_summary(rows, int(summary.get("total") or len(rows))))
    payload["summary"] = summary
    source = dict(payload.get("source") or {})
    source["browserSnapshot"] = _browser_snapshot_meta(snapshot)
    payload["source"] = source
    _attach_return_inventory_payload(payload, organization_id=organization_id)
    return payload


def _return_inventory_meta(candidates: list[Any], matched_items: int) -> dict[str, Any]:
    last_synced_at = next((str(candidate.lastSeenAt) for candidate in candidates if candidate.lastSeenAt), None)
    return {
        "status": "ready",
        "candidates": len(candidates),
        "matchedItems": matched_items,
        "lastSyncedAt": last_synced_at,
    }


def _return_candidate_order_row(candidate: AvitoReturnCandidate) -> AvitoOrderRow:
    return AvitoOrderRow(
        orderId=candidate.returnOrderId,
        marketplaceId=candidate.marketplaceId,
        accountId=candidate.accountId,
        accountName=candidate.accountName,
        status=candidate.status or "on_return",
        returnStatus=candidate.returnStatus,
        updatedAt=candidate.sourceUpdatedAt,
        items=[
            {
                "itemId": candidate.itemId,
                "title": candidate.title,
                "quantity": candidate.quantity,
                "sellerArticle": candidate.sellerArticle,
                "size": candidate.size,
                "color": candidate.color,
                "imageUrl": candidate.imageUrl,
            }
        ],
    )


def _enriched_return_candidates(organization_id: int) -> list[AvitoReturnCandidate]:
    candidates = list_active_return_candidates(organization_id)
    snapshot = _browser_snapshot_from_cache(organization_id)
    if snapshot is None or (not snapshot.orders and not snapshot.returns):
        return candidates
    rows = [_return_candidate_order_row(candidate) for candidate in candidates]
    merge_browser_snapshot_orders(rows, snapshot)
    enriched = extract_return_candidates(rows)
    for index, candidate in enumerate(candidates):
        if index >= len(enriched):
            continue
        enriched[index].lastSeenAt = candidate.lastSeenAt
        if not enriched[index].sourceUpdatedAt:
            enriched[index].sourceUpdatedAt = candidate.sourceUpdatedAt
    return enriched


def _enrich_orders_with_return_matches(rows: list[AvitoOrderRow], *, organization_id: int) -> dict[str, Any]:
    try:
        candidates = _enriched_return_candidates(organization_id)
    except Exception:
        return {"status": "unavailable", "candidates": 0, "matchedItems": 0, "error": "avito_return_inventory_unavailable"}
    matched_items = 0
    for order in rows:
        for item in order.items:
            matches = match_return_candidates(item, order=order, candidates=candidates)
            item.returnMatches = matches
            item.reuseSuggestion = matches[0] if matches else None
            if matches:
                matched_items += 1
    return _return_inventory_meta(candidates, matched_items)


def _attach_return_inventory_payload(payload: dict[str, Any], *, organization_id: int) -> dict[str, Any]:
    rows = [AvitoOrderRow.model_validate(row) for row in payload.get("rows") or [] if isinstance(row, dict)]
    return_inventory = _enrich_orders_with_return_matches(rows, organization_id=organization_id)
    payload["rows"] = [row.model_dump(mode="json") for row in rows]
    source = dict(payload.get("source") or {})
    source["returnInventory"] = return_inventory
    payload["source"] = source
    return payload


def _slugify_avito_title(title: str) -> str:
    mapping = {
        "а": "a",
        "б": "b",
        "в": "v",
        "г": "g",
        "д": "d",
        "е": "e",
        "ё": "e",
        "ж": "zh",
        "з": "z",
        "и": "i",
        "й": "y",
        "к": "k",
        "л": "l",
        "м": "m",
        "н": "n",
        "о": "o",
        "п": "p",
        "р": "r",
        "с": "s",
        "т": "t",
        "у": "u",
        "ф": "f",
        "х": "h",
        "ц": "ts",
        "ч": "ch",
        "ш": "sh",
        "щ": "sch",
        "ъ": "",
        "ы": "y",
        "ь": "",
        "э": "e",
        "ю": "yu",
        "я": "ya",
    }
    normalized = "".join(mapping.get(char, char) for char in str(title or "").lower())
    return re.sub(r"_+", "_", re.sub(r"[^a-z0-9]+", "_", normalized)).strip("_")


def _public_avito_item_url(title: str, item_id: str) -> str | None:
    slug = _slugify_avito_title(title)
    if not slug or not item_id:
        return None
    return f"https://www.avito.ru/voronezh/odezhda_obuv_aksessuary/{slug}_{item_id}"


def _plain_text_from_html(value: str) -> str:
    without_scripts = re.sub(r"<(?:script|style)\b[^>]*>.*?</(?:script|style)>", "\n", value, flags=re.I | re.S)
    with_breaks = re.sub(r"<[^>]+>", "\n", without_scripts)
    return re.sub(r"[ \t\r\f\v]+", " ", html.unescape(with_breaks)).strip()


def _color_from_public_item_html(value: str) -> str | None:
    text = _plain_text_from_html(value)
    match = re.search(r"(?:^|\n|\s)Цвет\s*[:—–-]?\s*([А-Яа-яЁёA-Za-z -]{3,30})(?:\n|$)", text, flags=re.I)
    if not match:
        return None
    color = re.split(r"[,.;|]", match.group(1).strip())[0].strip().lower()
    if len(color) > 24 or re.search(r"\d", color):
        return None
    return color or None


def _fetch_public_avito_color(title: str, item_id: str) -> str | None:
    cached = _AVITO_PUBLIC_COLOR_CACHE.get(item_id)
    if item_id in _AVITO_PUBLIC_COLOR_CACHE:
        return cached
    url = _public_avito_item_url(title, item_id)
    if not url:
        _AVITO_PUBLIC_COLOR_CACHE[item_id] = None
        return None
    try:
        with httpx.Client(timeout=5.0, follow_redirects=True, headers={"User-Agent": "Mozilla/5.0"}) as client:
            response = client.get(url)
        if response.status_code >= 400:
            _AVITO_PUBLIC_COLOR_CACHE[item_id] = None
            return None
        color = _color_from_public_item_html(response.text)
        _AVITO_PUBLIC_COLOR_CACHE[item_id] = color
        return color
    except Exception:
        _AVITO_PUBLIC_COLOR_CACHE[item_id] = None
        return None


def _enrich_missing_colors_from_public_avito(rows: list[AvitoOrderRow]) -> None:
    for order in rows:
        for item in order.items:
            if item.color or not item.itemId:
                continue
            color = _fetch_public_avito_color(item.title, str(item.itemId))
            if color:
                item.color = color


def _browser_snapshot_rows(snapshot: AvitoOrdersBrowserSnapshot, *, statuses: list[str]) -> list[AvitoOrderRow]:
    rows: list[AvitoOrderRow] = []
    browser_orders = [(order, order.status or "ready_to_ship") for order in snapshot.orders]
    browser_orders.extend((order, order.status or "on_return") for order in snapshot.returns)
    for index, (order, fallback_status) in enumerate(browser_orders):
        row_status = fallback_status
        if statuses and row_status not in statuses:
            continue
        items = [
            {
                "itemId": item.itemId,
                "title": item.title or "Товар Авито",
                "quantity": item.quantity or 1,
                "priceKopecks": item.priceKopecks,
                "sellerArticle": item.sellerArticle,
                "size": item.size,
                "color": item.color,
                "imageUrl": item.imageUrl,
            }
            for item in order.items
        ]
        total = sum((item.priceKopecks or 0) * (item.quantity or 1) for item in order.items)
        rows.append(
            AvitoOrderRow.model_validate(
                {
                    "orderId": order.orderId or order.marketplaceId or f"browser-order-{index + 1}",
                    "marketplaceId": order.marketplaceId,
                    "accountId": order.accountId,
                    "accountName": order.accountName or "Авито",
                    "status": row_status,
                    "deliveryService": order.deliveryService,
                    "trackNumber": order.trackNumber,
                    "buyerName": order.buyerName,
                    "recipientName": order.recipientName,
                    "totalKopecks": total or None,
                    "items": items or [{"title": "Товар Авито", "quantity": 1}],
                    "availableActions": [],
                    "sourceStatus": "fresh",
                }
            )
        )
    return rows


def _snapshot_identity_values(snapshot: AvitoOrdersBrowserSnapshot) -> set[str]:
    values: set[str] = set()
    for order in [*snapshot.orders, *snapshot.returns]:
        for value in (order.orderId, order.marketplaceId):
            text = str(value or "").strip()
            if text:
                values.add(text)
    return values


def _row_identity_values(row: AvitoOrderRow) -> set[str]:
    return {text for text in (str(row.orderId or "").strip(), str(row.marketplaceId or "").strip()) if text}


def _snapshot_filtered_rows(
    rows: list[AvitoOrderRow],
    snapshot: AvitoOrdersBrowserSnapshot,
) -> list[AvitoOrderRow]:
    identities = _snapshot_identity_values(snapshot)
    if not identities:
        return rows
    return [row for row in rows if _row_identity_values(row) & identities]


def _fetch_orders_filtered_by_snapshot(
    client: Any,
    *,
    snapshot: AvitoOrdersBrowserSnapshot,
    start: date,
    statuses: list[str],
) -> tuple[list[AvitoOrderRow], int, str, dict[str, Any] | None, Any | None]:
    identities = _snapshot_identity_values(snapshot)
    rows: list[AvitoOrderRow] = []
    total = 0
    last_diagnostics: dict[str, Any] | None = None
    last_error: Any | None = None
    if not identities:
        return rows, 0, "synced", {"source": "browser_snapshot_without_order_ids"}, None
    for api_page in range(1, 101):
        result = client.fetch_orders(AvitoOrdersFetchRequest(dateFrom=start, statuses=statuses, limit=20, page=api_page))
        last_diagnostics = result.diagnostics
        last_error = result.error.model_dump(mode="json") if hasattr(result.error, "model_dump") else result.error
        if result.status == "blocked":
            return rows, len(rows), result.status, last_diagnostics, last_error
        matched = _snapshot_filtered_rows(result.orders, snapshot)
        rows.extend(matched)
        total = result.total or total
        found = set().union(*(_row_identity_values(row) for row in rows)) if rows else set()
        if identities.issubset(found) or not result.orders or (total and api_page * 20 >= total):
            break
    rows = _snapshot_filtered_rows(list({row.orderId: row for row in rows}.values()), snapshot)
    merge_browser_snapshot_orders(rows, snapshot)
    diagnostics = {
        **(last_diagnostics or {}),
        "source": "api_filtered_by_browser_snapshot",
        "snapshotOrders": len(snapshot.orders),
        "snapshotIdentities": len(identities),
        "matchedOrders": len(rows),
    }
    return rows, len(rows), "synced", diagnostics, last_error


def _browser_snapshot_payload(
    snapshot: AvitoOrdersBrowserSnapshot,
    *,
    start: date,
    days: int,
    statuses: list[str],
    page: int,
    limit: int,
) -> dict[str, Any]:
    all_rows = _browser_snapshot_rows(snapshot, statuses=statuses)
    page_start = (page - 1) * limit
    rows = all_rows[page_start : page_start + limit]
    payload = _response_payload(
        status="synced",
        start=start,
        days=days,
        statuses=statuses,
        page=page,
        limit=limit,
        rows=rows,
        total=len(all_rows),
        diagnostics={"source": "browser_snapshot_only"},
        browser_snapshot=snapshot,
    )
    source = dict(payload.get("source") or {})
    source["mode"] = "browser-snapshot"
    source["api"] = {**dict(source.get("api") or {}), "readOnly": True, "usedForRows": False}
    payload["source"] = source
    return payload


def _orders_client_for_request(request: Request):
    actor = actor_from_request(request)
    if not has_permission(actor, "cabinet:read"):
        raise HTTPException(status_code=403, detail="NO_ACCESS:cabinet:read")
    credentials = get_user_avito_credentials_secret(actor.user_id) or get_organization_avito_credentials_secret(actor.organization_id)
    if credentials is None:
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
        raise HTTPException(status_code=409, detail="AVITO_OAUTH_FAILED") from exc

    client = build_avito_orders_client(
        access_token=access_token,
        base_url=settings.avito_api_base_url,
        timeout_seconds=settings.avito_api_timeout_seconds,
    )
    return actor, client, access_token


def _text_or_none(*values: Any) -> str | None:
    for value in values:
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return None


def _listing_cache_key(start: date, end: date) -> str:
    return f"avito_listings_v2:{start.isoformat()}:{end.isoformat()}:all"


def _listing_dicts_from_cache(organization_id: int, start: date, end: date) -> list[dict[str, Any]]:
    cached = get_source_cache(organization_id, _listing_cache_key(start, end), slim=False) or None
    rows = cached.get("rows") if isinstance(cached, dict) else None
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


def _enrich_orders_from_listing_rows(rows: list[AvitoOrderRow], listing_rows: list[dict[str, Any]]) -> None:
    by_item_id = {
        str(row.get("itemId") or row.get("id") or row.get("avitoId") or ""): row
        for row in listing_rows
        if row.get("itemId") or row.get("id") or row.get("avitoId")
    }
    for order in rows:
        for item in order.items:
            listing = by_item_id.get(str(item.itemId or ""))
            if not listing:
                continue
            if not item.sellerArticle:
                item.sellerArticle = _text_or_none(listing.get("sellerArticle"), listing.get("seller_article"), listing.get("vendorCode"), listing.get("sku"))
            if not item.size:
                item.size = _text_or_none(listing.get("size"), listing.get("productSize"), listing.get("product_size"))
            if not item.color:
                item.color = _text_or_none(listing.get("color"), listing.get("colour"))
            if not item.imageUrl:
                item.imageUrl = _text_or_none(listing.get("imageUrl"), listing.get("image_url"))
            if not order.accountName or order.accountName == "Авито":
                order.accountName = _text_or_none(listing.get("accountName"), order.accountName)


def _missing_detail_item_ids(rows: list[AvitoOrderRow]) -> list[str]:
    result: list[str] = []
    for order in rows:
        for item in order.items:
            if not item.itemId:
                continue
            if item.size and item.color and item.sellerArticle and item.imageUrl and order.accountName and order.accountName != "Авито":
                continue
            result.append(str(item.itemId))
    return list(dict.fromkeys(result))


def _enrich_orders_for_picking(rows: list[AvitoOrderRow], *, organization_id: int, access_token: str, start: date) -> None:
    end = date.today()
    listing_rows = _listing_dicts_from_cache(organization_id, start, end)
    settings = get_settings()
    client = None
    if not listing_rows:
        try:
            client = build_avito_listings_client(
                access_token=access_token,
                base_url=settings.avito_api_base_url,
                timeout_seconds=settings.avito_api_timeout_seconds,
            )
            result = client.fetch_listings(AvitoListingsFetchRequest(dateFrom=start, dateTo=end))
            if result.status != "blocked":
                listing_rows = [row.model_dump(mode="json") for row in result.rows]
        except Exception:
            listing_rows = []
    if listing_rows:
        _enrich_orders_from_listing_rows(rows, listing_rows)
    missing_item_ids = _missing_detail_item_ids(rows)
    if missing_item_ids:
        try:
            client = client or build_avito_listings_client(
                access_token=access_token,
                base_url=settings.avito_api_base_url,
                timeout_seconds=settings.avito_api_timeout_seconds,
            )
            details = client.fetch_listing_details(AvitoListingDetailsFetchRequest(itemIds=missing_item_ids))
            if details.status != "blocked":
                _enrich_orders_from_listing_rows(rows, [row.model_dump(mode="json") for row in details.rows])
        except Exception:
            return


@router.get("/api/v1/avito/orders/extension-token")
def get_avito_orders_extension_token_status(request: Request) -> dict[str, Any]:
    actor = actor_from_request(request)
    if not has_permission(actor, "cabinet:read"):
        raise HTTPException(status_code=403, detail="NO_ACCESS:cabinet:read")
    return _extension_token_status_payload(get_source_cache(actor.organization_id, AVITO_ORDERS_EXTENSION_TOKEN_KEY, slim=False))


@router.post("/api/v1/avito/orders/extension-token/regenerate")
def regenerate_avito_orders_extension_token(request: Request) -> dict[str, Any]:
    actor = actor_from_request(request)
    if not has_permission(actor, "integrations:write"):
        raise HTTPException(status_code=403, detail="NO_ACCESS:integrations:write")
    token = f"sat_avito_{secrets.token_urlsafe(32)}"
    token_hash = _hash_extension_token(token)
    now = _now_iso()
    previous = get_source_cache(actor.organization_id, AVITO_ORDERS_EXTENSION_TOKEN_KEY, slim=False) or {}
    payload = {
        "activeHash": token_hash,
        "tokenPrefix": token[:18],
        "createdAt": previous.get("createdAt") or now,
        "rotatedAt": now,
        "lastUsedAt": None,
    }
    save_source_cache(actor.organization_id, AVITO_ORDERS_EXTENSION_TOKEN_KEY, payload)
    save_source_cache(
        actor.organization_id,
        _extension_token_source_key(token_hash),
        {"tokenHash": token_hash, "createdAt": now, "tokenPrefix": token[:18]},
    )
    return {**_extension_token_status_payload(payload), "token": token}


@router.post("/api/v1/avito/orders/browser-snapshot")
def save_avito_orders_browser_snapshot(request: Request, snapshot: AvitoOrdersBrowserSnapshot) -> dict[str, Any]:
    extension_token = _extension_bearer_token(request)
    if extension_token:
        organization_id = _resolve_extension_token_organization(extension_token)
        if organization_id is None:
            raise HTTPException(status_code=401, detail="AVITO_EXTENSION_TOKEN_INVALID")
    else:
        actor = actor_from_request(request)
        if not has_permission(actor, "cabinet:read"):
            raise HTTPException(status_code=403, detail="NO_ACCESS:cabinet:read")
        organization_id = actor.organization_id
    snapshot, ai_extraction = enrich_avito_orders_snapshot_with_ai(snapshot)
    snapshot = snapshot.model_copy(update={"aiExtraction": ai_extraction})
    payload = snapshot.model_dump(mode="json")
    payload["savedAt"] = _now_iso()
    save_source_cache(organization_id, AVITO_ORDERS_BROWSER_SNAPSHOT_KEY, payload)
    if snapshot.returns:
        return_rows = _browser_snapshot_rows(snapshot, statuses=["on_return"])
        enrich_existing_return_candidates(organization_id, extract_return_candidates(return_rows))
    return {"ok": True, "browserSnapshot": _browser_snapshot_meta(snapshot)}


@router.get("/api/v1/avito/orders/returns-sync")
def get_avito_returns_sync_settings(request: Request) -> dict[str, Any]:
    extension_token = _extension_bearer_token(request)
    if extension_token:
        organization_id = _resolve_extension_token_organization(extension_token)
        if organization_id is None:
            raise HTTPException(status_code=401, detail="AVITO_EXTENSION_TOKEN_INVALID")
        return _returns_sync_settings_payload(organization_id)
    actor = actor_from_request(request)
    if not has_permission(actor, "cabinet:read"):
        raise HTTPException(status_code=403, detail="NO_ACCESS:cabinet:read")
    return _returns_sync_settings_payload(actor.organization_id)


@router.put("/api/v1/avito/orders/returns-sync")
def update_avito_returns_sync_settings(request: Request, payload: dict[str, Any]) -> dict[str, Any]:
    actor = actor_from_request(request)
    if not has_permission(actor, "integrations:write"):
        raise HTTPException(status_code=403, detail="NO_ACCESS:integrations:write")
    save_returns_sync_settings(actor.organization_id, payload)
    return _returns_sync_settings_payload(actor.organization_id)


@router.post("/api/v1/avito/orders/returns-sync/run")
def run_avito_returns_sync(request: Request) -> dict[str, Any]:
    actor = actor_from_request(request)
    if not has_permission(actor, "sync:run"):
        raise HTTPException(status_code=403, detail="NO_ACCESS:sync:run")
    from app.avito.returns_tasks import sync_returns_for_org

    async_result = sync_returns_for_org.delay(actor.organization_id, "manual", True)
    status_payload = {
        "state": "queued",
        "organizationId": actor.organization_id,
        "taskId": async_result.id,
        "queuedAt": _now_iso(),
        "trigger": "manual",
    }
    save_source_cache(actor.organization_id, AVITO_RETURNS_SYNC_STATUS_KEY, status_payload)
    return {**_returns_sync_settings_payload(actor.organization_id), "taskId": async_result.id}


@router.get("/api/v1/avito/orders")
def get_avito_orders(
    request: Request,
    date_from: date | None = Query(default=None, alias="dateFrom"),
    period_days: int = Query(default=30, alias="periodDays", ge=1, le=183),
    status: list[str] = Query(default_factory=list, alias="status"),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=20),
    force_refresh: bool = Query(default=False, alias="forceRefresh"),
) -> dict[str, Any]:
    actor = actor_from_request(request)
    if not has_permission(actor, "cabinet:read"):
        raise HTTPException(status_code=403, detail="NO_ACCESS:cabinet:read")
    start, days = _date_from(date_from, period_days)
    statuses = _statuses(status)
    browser_snapshot = _browser_snapshot_from_cache(actor.organization_id)
    if browser_snapshot is not None:
        try:
            _actor, client, _access_token = _orders_client_for_request(request)
            all_rows, total, result_status, diagnostics, error = _fetch_orders_filtered_by_snapshot(
                client,
                snapshot=browser_snapshot,
                start=start,
                statuses=statuses,
            )
            if result_status != "blocked" and all_rows:
                _enrich_missing_colors_from_public_avito(all_rows)
                page_start = (page - 1) * limit
                rows = all_rows[page_start : page_start + limit]
                return_inventory = _enrich_orders_with_return_matches(rows, organization_id=actor.organization_id)
                payload = _response_payload(
                    status=result_status,
                    start=start,
                    days=days,
                    statuses=statuses,
                    page=page,
                    limit=limit,
                    rows=rows,
                    total=total,
                    diagnostics=diagnostics,
                    error=error,
                    browser_snapshot=browser_snapshot,
                    return_inventory=return_inventory,
                )
                source = dict(payload.get("source") or {})
                source["mode"] = "api-filtered-by-browser-snapshot"
                source["api"] = {**dict(source.get("api") or {}), "usedForRows": True}
                payload["source"] = source
                return payload
            fallback = _browser_snapshot_payload(browser_snapshot, start=start, days=days, statuses=statuses, page=page, limit=limit)
            source = dict(fallback.get("source") or {})
            source["diagnostics"] = {
                **dict(source.get("diagnostics") or {}),
                "apiFilterStatus": result_status,
                "apiFilterDiagnostics": diagnostics,
            }
            source["error"] = error
            fallback["source"] = source
            return _attach_return_inventory_payload(fallback, organization_id=actor.organization_id)
        except HTTPException:
            raise
        except Exception:
            fallback = _browser_snapshot_payload(browser_snapshot, start=start, days=days, statuses=statuses, page=page, limit=limit)
            source = dict(fallback.get("source") or {})
            source["diagnostics"] = {
                **dict(source.get("diagnostics") or {}),
                "apiFilterStatus": "failed",
                "apiFilterError": "avito_orders_filter_unavailable",
            }
            fallback["source"] = source
            return _attach_return_inventory_payload(fallback, organization_id=actor.organization_id)
    source_key = _cache_key(start, statuses, page, limit)
    cached = get_source_cache(actor.organization_id, source_key, slim=False) or None
    if not force_refresh and isinstance(cached, dict) and cached.get("status") != "blocked" and cached.get("rows") is not None:
        return _merge_browser_snapshot_payload(_cache_hit_payload(cached), organization_id=actor.organization_id)

    _actor, client, _access_token = _orders_client_for_request(request)
    result = client.fetch_orders(AvitoOrdersFetchRequest(dateFrom=start, statuses=statuses, limit=limit, page=page))
    browser_snapshot = _browser_snapshot_from_cache(actor.organization_id)
    merge_browser_snapshot_orders(result.orders, browser_snapshot)
    _enrich_missing_colors_from_public_avito(result.orders)
    return_inventory = _enrich_orders_with_return_matches(result.orders, organization_id=actor.organization_id)
    payload = _response_payload(
        status=result.status,
        start=start,
        days=days,
        statuses=statuses,
        page=page,
        limit=limit,
        rows=result.orders,
        total=result.total,
        diagnostics=result.diagnostics,
        error=result.error.model_dump(mode="json") if hasattr(result.error, "model_dump") else result.error,
        browser_snapshot=browser_snapshot,
        return_inventory=return_inventory,
    )
    if result.status != "blocked":
        save_source_cache(actor.organization_id, source_key, payload)
    return payload


@router.get("/api/v1/avito/orders/picking-list.xlsx")
def get_avito_orders_picking_list_xlsx(
    request: Request,
    date_from: date | None = Query(default=None, alias="dateFrom"),
    period_days: int = Query(default=30, alias="periodDays", ge=1, le=183),
    status: list[str] = Query(default_factory=list, alias="status"),
) -> Response:
    start, _days = _date_from(date_from, period_days)
    statuses = _statuses(status)
    actor = actor_from_request(request)
    if not has_permission(actor, "cabinet:read"):
        raise HTTPException(status_code=403, detail="NO_ACCESS:cabinet:read")
    browser_snapshot = _browser_snapshot_from_cache(actor.organization_id)
    actor, client, access_token = _orders_client_for_request(request)
    if browser_snapshot is not None:
        rows, _total, result_status, _diagnostics, error = _fetch_orders_filtered_by_snapshot(
            client,
            snapshot=browser_snapshot,
            start=start,
            statuses=statuses,
        )
        if result_status == "blocked":
            rows = _browser_snapshot_rows(browser_snapshot, statuses=statuses)
        if rows:
            _enrich_orders_for_picking(rows, organization_id=actor.organization_id, access_token=access_token, start=start)
            merge_browser_snapshot_orders(rows, browser_snapshot)
            _enrich_missing_colors_from_public_avito(rows)
            content = build_avito_orders_picking_xlsx(rows, date_from=start)
            filename = f"avito-picking-list-{start.isoformat()}.xlsx"
            return Response(
                content=content,
                media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                headers={"Content-Disposition": f'attachment; filename="{filename}"'},
            )
        if error:
            raise HTTPException(status_code=502, detail=error)
    rows: list[AvitoOrderRow] = []
    total = 0
    limit = 20
    for page in range(1, 101):
        result = client.fetch_orders(AvitoOrdersFetchRequest(dateFrom=start, statuses=statuses, limit=limit, page=page))
        if result.status == "blocked":
            raise HTTPException(status_code=502, detail=result.error.model_dump(mode="json") if hasattr(result.error, "model_dump") else result.error)
        rows.extend(result.orders)
        total = result.total or total
        if not result.orders or (total and len(rows) >= total):
            break

    _enrich_orders_for_picking(rows, organization_id=actor.organization_id, access_token=access_token, start=start)
    merge_browser_snapshot_orders(rows, _browser_snapshot_from_cache(actor.organization_id))
    _enrich_missing_colors_from_public_avito(rows)
    content = build_avito_orders_picking_xlsx(rows, date_from=start)
    filename = f"avito-picking-list-{start.isoformat()}.xlsx"
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
