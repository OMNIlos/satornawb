from __future__ import annotations

import json
import logging
from typing import Any

import httpx

from app.avito.orders import AvitoOrdersBrowserSnapshot
from app.config import get_settings
from app.reviews.openai_client import _extract_output_text


logger = logging.getLogger(__name__)

AVITO_ORDER_ITEM_EXTRACTION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["items"],
    "properties": {
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["key", "size", "color", "sellerArticle", "confidence", "notes"],
                "properties": {
                    "key": {"type": "string", "minLength": 1},
                    "size": {"type": ["string", "null"]},
                    "color": {"type": ["string", "null"]},
                    "sellerArticle": {"type": ["string", "null"]},
                    "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
                    "notes": {"type": "string"},
                },
            },
        },
    },
}


def _finalize_size_fallbacks(
    snapshot: AvitoOrdersBrowserSnapshot,
    metadata: dict[str, Any],
    *,
    ai_size_count: int = 0,
) -> tuple[AvitoOrdersBrowserSnapshot, dict[str, Any]]:
    fallback_count = 0
    missing_count = 0
    options = (snapshot.collector or {}).get("options") if isinstance(snapshot.collector, dict) else {}
    chat_ai = isinstance(options, dict) and options.get("sizeMode") == "chat_ai"
    for order in snapshot.orders:
        for index, item in enumerate(order.items):
            current = item
            if chat_ai and not current.size and current.descriptionSize:
                sources = dict(current.sources or {})
                sources["size"] = "description_fallback"
                current = current.model_copy(
                    update={"size": current.descriptionSize, "sources": sources}
                )
                order.items[index] = current
                fallback_count += 1
            if chat_ai and not current.size:
                missing_count += 1
    return snapshot, {
        **metadata,
        "aiSizeCount": ai_size_count,
        "descriptionFallbackCount": fallback_count,
        "missingFinalSizeCount": missing_count,
    }


def _snapshot_items(snapshot: AvitoOrdersBrowserSnapshot, options: dict[str, Any]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    need_size = options.get("sizeMode") == "chat_ai"
    need_color = bool(options.get("colorFromDescription"))
    need_article = bool(options.get("articleFromDescription"))
    for order_index, order in enumerate(snapshot.orders):
        for item_index, item in enumerate(order.items):
            wants_size = need_size and not item.size and bool(str(item.chatText or "").strip())
            wants_color = need_color and not item.color and bool(str(item.description or item.chatText or "").strip())
            wants_article = need_article and not item.sellerArticle and bool(str(item.description or item.chatText or "").strip())
            if not wants_size and not wants_color and not wants_article:
                continue
            description = str(item.description or "").strip()[:1500]
            chat = str(item.chatText or "").strip()[-4000:]
            text = "\n".join(
                part
                for part in (
                    f"Название: {item.title}" if item.title else "",
                    f"Описание: {description}" if description else "",
                    f"Чат: {chat}" if chat else "",
                )
                if part
            )[:6000]
            if not text.strip():
                continue
            items.append(
                {
                    "key": f"{order_index}:{item_index}",
                    "orderId": order.orderId,
                    "marketplaceId": order.marketplaceId,
                    "title": item.title,
                    "needSize": wants_size,
                    "needColor": wants_color,
                    "needSellerArticle": wants_article,
                    "text": text,
                }
            )
    return items


def enrich_avito_orders_snapshot_with_ai(snapshot: AvitoOrdersBrowserSnapshot, *, client: httpx.Client | None = None) -> tuple[AvitoOrdersBrowserSnapshot, dict[str, Any]]:
    options = (snapshot.collector or {}).get("options") if isinstance(snapshot.collector, dict) else {}
    if not isinstance(options, dict):
        logger.warning("[AVITO_ORDERS_AI] skipped collector_options_missing")
        return _finalize_size_fallbacks(
            snapshot, {"status": "skipped", "reason": "collector_options_missing"}
        )
    if options.get("sizeMode") != "chat_ai" and not options.get("colorFromDescription") and not options.get("articleFromDescription"):
        logger.warning("[AVITO_ORDERS_AI] skipped ai_fields_disabled options=%s", options)
        return _finalize_size_fallbacks(
            snapshot, {"status": "skipped", "reason": "ai_fields_disabled"}
        )
    settings = get_settings()
    if not settings.openai_api_key:
        logger.warning("[AVITO_ORDERS_AI] skipped openai_api_key_missing")
        return _finalize_size_fallbacks(
            snapshot, {"status": "skipped", "reason": "openai_api_key_missing"}
        )

    items = _snapshot_items(snapshot, options)
    if not items:
        logger.warning("[AVITO_ORDERS_AI] skipped nothing_to_extract options=%s orders=%s", options, len(snapshot.orders))
        return _finalize_size_fallbacks(
            snapshot, {"status": "skipped", "reason": "nothing_to_extract"}
        )
    logger.warning("[AVITO_ORDERS_AI] sending items=%s options=%s", len(items), options)

    close_client = False
    if client is None:
        client = httpx.Client(base_url=settings.openai_api_base_url, timeout=settings.openai_review_timeout_seconds)
        close_client = True
    try:
        response = client.post(
            "/responses" if str(client.base_url).rstrip("/").endswith("/v1") else "/v1/responses",
            headers={"Authorization": f"Bearer {settings.openai_api_key}", "Content-Type": "application/json"},
            json={
                "model": settings.openai_review_model,
                "input": [
                    {
                        "role": "system",
                        "content": (
                            "Ты извлекаешь недостающие поля товара Avito для листа подбора. "
                            "Размер извлекай только если needSize=true: бери финальный подтвержденный размер из чата, если покупатель менял решение. "
                            "Цвет извлекай только если needColor=true и рядом есть явная метка Цвет/Color в описании или характеристиках. "
                            "Не извлекай цвет из названия товара: слова вроде Platinum, White Pony, Light, Blue, Black могут быть частью модели или принта. "
                            "Артикул продавца извлекай только если needSellerArticle=true и рядом есть маркеры арт, артикул, sku или похожее. "
                            "Не придумывай значения. Для отключенных или не найденных полей возвращай null."
                        ),
                    },
                    {"role": "user", "content": json.dumps({"items": items}, ensure_ascii=False, sort_keys=True)},
                ],
                "text": {
                    "format": {
                        "type": "json_schema",
                        "name": "avito_order_item_extraction",
                        "strict": True,
                        "schema": AVITO_ORDER_ITEM_EXTRACTION_SCHEMA,
                    }
                },
            },
        )
        response.raise_for_status()
        output_text = _extract_output_text(response.json())
        if output_text is None:
            logger.warning("[AVITO_ORDERS_AI] failed openai_response_without_text items=%s", len(items))
            return _finalize_size_fallbacks(
                snapshot,
                {
                    "status": "failed",
                    "reason": "openai_response_without_text",
                    "itemsSent": len(items),
                },
            )
        parsed = json.loads(output_text)
        extracted = parsed.get("items") if isinstance(parsed, dict) else []
        by_key = {str(item.get("key")): item for item in extracted if isinstance(item, dict)}
        updated = 0
        ai_size_count = 0
        for order_index, order in enumerate(snapshot.orders):
            for item_index, item in enumerate(order.items):
                found = by_key.get(f"{order_index}:{item_index}")
                if not found:
                    continue
                patch: dict[str, Any] = {}
                if (
                    not item.size
                    and found.get("size")
                    and found.get("confidence") in {"high", "medium"}
                ):
                    sources = dict(item.sources or {})
                    sources["size"] = "chat_ai"
                    patch["size"] = str(found["size"]).strip()
                    patch["sources"] = sources
                    ai_size_count += 1
                if not item.color and found.get("color"):
                    patch["color"] = str(found["color"]).strip()
                if not item.sellerArticle and found.get("sellerArticle"):
                    patch["sellerArticle"] = str(found["sellerArticle"]).strip()
                if patch:
                    order.items[item_index] = item.model_copy(update=patch)
                    updated += 1
        logger.warning("[AVITO_ORDERS_AI] completed sent=%s returned=%s updated=%s", len(items), len(by_key), updated)
        return _finalize_size_fallbacks(
            snapshot,
            {
                "status": "completed",
                "itemsSent": len(items),
                "itemsReturned": len(by_key),
                "itemsUpdated": updated,
                "model": settings.openai_review_model,
            },
            ai_size_count=ai_size_count,
        )
    except Exception as exc:
        logger.warning("[AVITO_ORDERS_AI] failed reason=%s items=%s", str(exc)[:500], len(items))
        return _finalize_size_fallbacks(
            snapshot,
            {"status": "failed", "reason": str(exc)[:500], "itemsSent": len(items)},
        )
    finally:
        if close_client:
            client.close()
