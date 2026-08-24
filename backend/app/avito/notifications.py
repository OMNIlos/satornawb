from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.avito.chats import AvitoChatRow, AvitoChatsFetchResult
from app.avito.listings import AvitoListingRow, AvitoListingsFetchResult
from app.avito.orders import AvitoOrderRow, AvitoOrdersFetchResult
from app.avito.reviews import AvitoReviewRow, AvitoReviewsFetchResult


AvitoNotificationSeverity = Literal["critical", "warning", "info"]
AvitoNotificationEntityType = Literal["account", "order", "review", "system"]


class AvitoNotificationEvent(BaseModel):
    id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    details: str = ""
    severity: AvitoNotificationSeverity = "info"
    category: Literal["avito"] = "avito"
    source: str = "Авито"
    manager: str = "Авито"
    createdAt: str
    readAt: str | None = None
    entityType: AvitoNotificationEntityType = "system"
    entityId: str = Field(min_length=1)
    route: str = "/avito/notifications"
    blockedActions: list[str] = Field(default_factory=list)
    freshness: dict[str, Any] | None = None
    raw: dict[str, Any] | None = None


class AvitoNotificationsResult(BaseModel):
    status: Literal["synced", "partial", "blocked"]
    summary: dict[str, Any]
    items: list[AvitoNotificationEvent] = Field(default_factory=list)
    rulesRows: list[list[str]] = Field(default_factory=list)
    recipientRows: list[list[str]] = Field(default_factory=list)
    channelRows: list[list[str]] = Field(default_factory=list)
    historyRows: list[list[str]] = Field(default_factory=list)
    source: dict[str, Any]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _event_time(*values: str | None) -> str:
    for value in values:
        if value:
            return value
    return _now_iso()


def _freshness(label: str, state: str, updated_at: str | None = None) -> dict[str, str]:
    return {"label": label, "state": state, "updatedAt": updated_at or _now_iso()}


def _event(
    *,
    event_id: str,
    title: str,
    details: str,
    severity: AvitoNotificationSeverity,
    source: str,
    created_at: str | None,
    entity_type: AvitoNotificationEntityType,
    entity_id: str,
    route: str,
    blocked_actions: list[str] | None = None,
    manager: str = "Авито",
    freshness: dict[str, Any] | None = None,
    raw: dict[str, Any] | None = None,
) -> AvitoNotificationEvent:
    return AvitoNotificationEvent(
        id=event_id,
        title=title,
        details=details,
        severity=severity,
        source=source,
        manager=manager,
        createdAt=created_at or _now_iso(),
        entityType=entity_type,
        entityId=entity_id,
        route=route,
        blockedActions=blocked_actions or [],
        freshness=freshness,
        raw=raw,
    )


def _unread_chat_events(result: AvitoChatsFetchResult | None) -> list[AvitoNotificationEvent]:
    if result is None:
        return []
    events: list[AvitoNotificationEvent] = []
    for chat in result.chats:
        if not chat.unread:
            continue
        item = f" · {chat.itemTitle}" if chat.itemTitle else ""
        buyer = chat.buyerName or "Покупатель"
        events.append(
            _event(
                event_id=f"avito-chat-unread:{chat.chatId}",
                title=f"Новый чат Авито: {buyer}",
                details=(chat.preview or "В диалоге есть непрочитанное сообщение.") + item,
                severity="warning",
                source="Сообщения Авито",
                created_at=_event_time(chat.lastMessageAt, chat.updatedAt),
                entity_type="account",
                entity_id=chat.chatId,
                route="/avito/chats",
                blocked_actions=["Ответ без проверки товара и сроков"],
                manager="Сообщения",
                freshness=_freshness("Сообщения", "актуально", chat.updatedAt or chat.lastMessageAt),
                raw={"accountId": chat.accountId, "itemId": chat.itemId, "chatType": chat.chatType},
            )
        )
    return events


def _order_events(result: AvitoOrdersFetchResult | None) -> list[AvitoNotificationEvent]:
    if result is None:
        return []
    events: list[AvitoNotificationEvent] = []
    for order in result.orders:
        required = [action.name for action in order.availableActions if action.required]
        if order.status not in {"on_confirmation", "ready_to_ship", "in_dispute", "on_return"} and not required:
            continue
        first_title = order.items[0].title if order.items else "Заказ Авито"
        severity: AvitoNotificationSeverity = "critical" if order.status in {"in_dispute", "on_return"} else "warning"
        events.append(
            _event(
                event_id=f"avito-order:{order.orderId}:{order.status}",
                title=f"Заказ Авито: {order_status_label(order.status)}",
                details=f"{first_title} · {order.deliveryService or 'доставка Avito'} · {order.trackNumber or 'трек не указан'}",
                severity=severity,
                source="Заказы Авито",
                created_at=_event_time(order.updatedAt, order.createdAt),
                entity_type="order",
                entity_id=order.orderId,
                route="/avito/orders",
                blocked_actions=required or ["Изменение статуса заказа без ручного решения"],
                manager="Производство",
                freshness=_freshness("Заказы", "актуально", order.updatedAt or order.createdAt),
                raw={"status": order.status, "marketplaceId": order.marketplaceId},
            )
        )
    return events


def order_status_label(status: str) -> str:
    return {
        "on_confirmation": "на подтверждение",
        "ready_to_ship": "к отгрузке",
        "in_transit": "в пути",
        "delivered": "доставлен",
        "closed": "закрыт",
        "canceled": "отменён",
        "on_return": "возврат",
        "in_dispute": "спор",
    }.get(status, status or "неизвестный статус")


def _review_events(result: AvitoReviewsFetchResult | None) -> list[AvitoNotificationEvent]:
    if result is None:
        return []
    events: list[AvitoNotificationEvent] = []
    for review in result.reviews:
        if review.answer is not None and review.score > 3:
            continue
        severity: AvitoNotificationSeverity = "critical" if review.score <= 2 else "warning"
        if review.score > 3 and not review.canAnswer:
            severity = "info"
        events.append(
            _event(
                event_id=f"avito-review:{review.reviewId}",
                title=f"Отзыв Авито {review.score}★",
                details=f"{review.buyerName}: {review.text or 'без текста'} · {review.itemTitle or 'объявление не указано'}",
                severity=severity,
                source="Отзывы Авито",
                created_at=review.createdAt,
                entity_type="review",
                entity_id=review.reviewId,
                route="/avito/reviews",
                blocked_actions=["Автоответ без approve"] if review.canAnswer else [],
                manager="Отзывы",
                freshness=_freshness("Отзывы", "актуально", review.createdAt),
                raw={"score": review.score, "canAnswer": review.canAnswer, "itemId": review.itemId},
            )
        )
    return events


def _listing_events(result: AvitoListingsFetchResult | None) -> list[AvitoNotificationEvent]:
    if result is None:
        return []
    events: list[AvitoNotificationEvent] = []
    problematic: list[AvitoListingRow] = [row for row in result.rows if row.status in {"blocked", "removed", "old"}]
    for row in problematic[:25]:
        severity: AvitoNotificationSeverity = "critical" if row.status == "blocked" else "warning"
        events.append(
            _event(
                event_id=f"avito-listing:{row.itemId}:{row.status}",
                title=f"Объявление Авито: {listing_status_label(row.status)}",
                details=f"{row.title} · {row.accountName} · статус {row.status}",
                severity=severity,
                source="Объявления Авито",
                created_at=row.updatedAt,
                entity_type="account",
                entity_id=row.itemId,
                route="/avito/listings",
                blocked_actions=["Публикация XML/изменений без проверки реестра"],
                manager="Объявления",
                freshness=_freshness("Объявления", "актуально" if row.sourceStatus == "fresh" else "частично", row.updatedAt),
                raw={"accountId": row.accountId, "status": row.status},
            )
        )
    return events


def listing_status_label(status: str) -> str:
    return {"blocked": "заблокировано", "removed": "снято", "old": "неактивно"}.get(status, status or "статус требует проверки")


def _section_error_events(errors: dict[str, Any]) -> list[AvitoNotificationEvent]:
    events: list[AvitoNotificationEvent] = []
    for name, error in errors.items():
        message = str(error.get("message") or error.get("code") or "источник недоступен") if isinstance(error, dict) else str(error)
        events.append(
            _event(
                event_id=f"avito-source:{name}:{message}",
                title=f"{name}: источник Авито недоступен",
                details=message,
                severity="critical" if "401" in message or "403" in message else "warning",
                source="Доступ Авито",
                created_at=None,
                entity_type="system",
                entity_id=f"avito-source-{name}",
                route="/settings/profile" if "401" in message or "403" in message else "/avito/notifications",
                blocked_actions=["Live-обновление раздела"],
                manager="Админ",
                freshness=_freshness("Доступ Авито", "требует проверки"),
                raw={"section": name, "error": error},
            )
        )
    return events


def _sort_events(items: list[AvitoNotificationEvent], limit: int) -> list[AvitoNotificationEvent]:
    return sorted(items, key=lambda item: item.createdAt, reverse=True)[:limit]


def apply_read_marks(items: list[AvitoNotificationEvent], read_marks: dict[str, str]) -> list[AvitoNotificationEvent]:
    marked: list[AvitoNotificationEvent] = []
    for item in items:
        if item.id in read_marks:
            item = item.model_copy(update={"readAt": read_marks[item.id]})
        marked.append(item)
    return marked


def build_avito_notifications_result(
    *,
    chats: AvitoChatsFetchResult | None,
    orders: AvitoOrdersFetchResult | None,
    reviews: AvitoReviewsFetchResult | None,
    listings: AvitoListingsFetchResult | None,
    errors: dict[str, Any],
    read_marks: dict[str, str],
    limit: int,
) -> AvitoNotificationsResult:
    raw_items = [
        *_unread_chat_events(chats),
        *_order_events(orders),
        *_review_events(reviews),
        *_listing_events(listings),
        *_section_error_events(errors),
    ]
    items = apply_read_marks(_sort_events(raw_items, limit), read_marks)
    unread = sum(1 for item in items if item.readAt is None)
    status: Literal["synced", "partial", "blocked"] = "partial" if errors else "synced"
    if errors and not items:
        status = "blocked"
    return AvitoNotificationsResult(
        status=status,
        summary={
            "total": len(items),
            "unread": unread,
            "critical": sum(1 for item in items if item.severity == "critical"),
            "warning": sum(1 for item in items if item.severity == "warning"),
            "info": sum(1 for item in items if item.severity == "info"),
            "sectionsBlocked": len(errors),
        },
        items=items,
        rulesRows=[
            ["Непрочитанный чат", "Сообщения", "Проверка", "Оператор", "Внутренняя лента", "сразу после обновления", "active", "включено"],
            ["Заказ требует действия", "Заказы", "Проверка", "Производство", "Внутренняя лента", "только просмотр", "active", "включено"],
            ["Низкий отзыв", "Отзывы", "Критично", "Отзывы", "Внутренняя лента", "ответ после подтверждения", "active", "включено"],
            ["Объявление снято или заблокировано", "Объявления", "Критично", "Объявления", "Внутренняя лента", "публикация остановлена", "warn", "контроль"],
            ["Доступ Авито недоступен", "Доступ Авито", "Критично", "Администратор", "Внутренняя лента", "проверить подключение", "blocked", "нужна настройка"],
        ],
        recipientRows=[
            ["Сообщения", "оператор", "чаты и сроки ответа", "внутренняя лента", "включено"],
            ["Производство", "производство", "заказы и отгрузка", "внутренняя лента", "только просмотр"],
            ["Отзывы", "отзывы", "низкие отзывы и черновики AI", "внутренняя лента", "после подтверждения"],
            ["Администратор", "администратор", "доступ, лимиты и ошибки", "внутренняя лента", "все аккаунты"],
        ],
        channelRows=[
            ["Внутренняя лента", "включён", "все события Авито", "после обновления данных", "on"],
            ["Вебхуки Авито", "готовится", "сообщения, заказы и отзывы", "нужен публичный HTTPS-адрес", "warn"],
            ["Telegram", "не подключён", "срочные события владельцу", "нужна отдельная интеграция", "blocked"],
        ],
        historyRows=[
            [item.createdAt[11:16] if len(item.createdAt) >= 16 else item.createdAt, item.title, item.manager, "внутренняя лента", "получено", "active"]
            for item in items[:8]
        ],
        source={
            "mode": "live",
            "cache": {"status": "актуально", "savedAt": _now_iso()},
            "api": {
                "chatsEndpoint": "Сообщения Авито",
                "messagesEndpoint": "История сообщений Авито",
                "ordersEndpoint": "Заказы Авито",
                "reviewsEndpoint": "Отзывы Авито",
                "ratingEndpoint": "Рейтинг Авито",
                "itemsEndpoint": "Объявления Авито",
                "webhookEndpoint": "Вебхуки Авито",
                "readOnly": "только просмотр",
            },
            "errors": errors,
        },
    )
