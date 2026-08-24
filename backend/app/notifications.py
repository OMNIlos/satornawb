from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.repricer_cache.store import get_source_cache, save_source_cache


NotificationSeverity = Literal["critical", "warning", "info"]
NotificationCategory = Literal["reports", "prices", "orders", "avito", "ai", "system"]
NotificationFreshnessState = Literal["fresh", "partial", "stale", "pending"]

NOTIFICATIONS_SOURCE_KEY = "notifications"
MAX_NOTIFICATIONS = 200


class NotificationFreshness(BaseModel):
    label: str
    state: NotificationFreshnessState
    updatedAt: str


class NotificationReportFile(BaseModel):
    id: str
    report: str
    period: str
    rows: int = Field(ge=0)
    size: str
    format: Literal["XLS", "XLSX", "CSV", "PDF"]
    fileName: str
    generatedAt: str


class NotificationEvent(BaseModel):
    id: str
    title: str
    details: str
    severity: NotificationSeverity
    category: NotificationCategory
    source: str
    manager: str
    createdAt: str
    readAt: str | None = None
    entityType: Literal["sku", "report", "order", "account", "review", "system"]
    entityId: str
    route: str | None = None
    blockedActions: list[str] = Field(default_factory=list)
    freshness: NotificationFreshness | None = None
    reportFile: NotificationReportFile | None = None


class NotificationsResponse(BaseModel):
    items: list[NotificationEvent]


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _notification_payload(organization_id: int) -> dict[str, Any]:
    payload = get_source_cache(organization_id, NOTIFICATIONS_SOURCE_KEY, slim=False) or {}
    if not isinstance(payload.get("items"), list):
        payload["items"] = []
    return payload


def _save_notifications(organization_id: int, items: list[dict[str, Any]]) -> None:
    save_source_cache(
        organization_id,
        NOTIFICATIONS_SOURCE_KEY,
        {
            "items": items[:MAX_NOTIFICATIONS],
            "count": min(len(items), MAX_NOTIFICATIONS),
        },
    )


def _validated_items(raw_items: list[Any]) -> list[NotificationEvent]:
    items: list[NotificationEvent] = []
    for raw in raw_items:
        if not isinstance(raw, dict):
            continue
        try:
            items.append(NotificationEvent.model_validate(raw))
        except Exception:
            continue
    return sorted(items, key=lambda item: item.createdAt, reverse=True)


def list_notifications(organization_id: int) -> list[NotificationEvent]:
    payload = _notification_payload(organization_id)
    return _validated_items(payload.get("items") or [])


def record_notification(organization_id: int, notification: NotificationEvent) -> NotificationEvent:
    current = [item.model_dump(mode="json") for item in list_notifications(organization_id)]
    next_item = notification.model_dump(mode="json")
    merged = [next_item]
    merged.extend(item for item in current if item.get("id") != notification.id)
    _save_notifications(organization_id, merged)
    return notification


def mark_notification_read(organization_id: int, notification_id: str) -> list[NotificationEvent]:
    now = _utc_now_iso()
    items = [item.model_dump(mode="json") for item in list_notifications(organization_id)]
    changed = False
    for item in items:
        if item.get("id") == notification_id and not item.get("readAt"):
            item["readAt"] = now
            changed = True
    if changed:
        _save_notifications(organization_id, items)
    return list_notifications(organization_id)


def mark_all_notifications_read(organization_id: int) -> list[NotificationEvent]:
    now = _utc_now_iso()
    items = [item.model_dump(mode="json") for item in list_notifications(organization_id)]
    changed = False
    for item in items:
        if not item.get("readAt"):
            item["readAt"] = now
            changed = True
    if changed:
        _save_notifications(organization_id, items)
    return list_notifications(organization_id)


def _step_summary(steps: list[dict[str, Any]]) -> str:
    labels = {
        "goods": "товары",
        "content": "контент",
        "promotions": "акции",
        "stocks": "остатки",
        "period-stats": "продажи",
        "finance": "финансы",
        "baskets": "корзины",
    }
    parts: list[str] = []
    for step in steps:
        source = str(step.get("source") or "")
        label = labels.get(source, source or "источник")
        status = str(step.get("status") or "")
        count = step.get("count")
        if status == "ok" and count is not None:
            parts.append(f"{label}: {count}")
        elif status:
            parts.append(f"{label}: {status}")
    return ", ".join(parts) if parts else "нет подробностей по шагам"


def _step_errors(steps: list[dict[str, Any]]) -> list[str]:
    errors: list[str] = []
    for step in steps:
        if step.get("status") != "error":
            continue
        source = str(step.get("source") or "source")
        error = str(step.get("error") or "ошибка источника")
        errors.append(f"{source}: {error}")
    return errors


def build_wb_sync_notification(status: dict[str, Any]) -> NotificationEvent | None:
    state = str(status.get("state") or "")
    if state not in {"completed", "partial", "failed", "stale"}:
        return None

    run_id = str(status.get("runId") or f"wb-sync-{_utc_now_iso()}")
    finished_at = str(status.get("finishedAt") or _utc_now_iso())
    period_days = int(status.get("periodDays") or 30)
    steps = status.get("steps") if isinstance(status.get("steps"), list) else []
    typed_steps = [step for step in steps if isinstance(step, dict)]
    summary = _step_summary(typed_steps)
    errors = _step_errors(typed_steps)

    if state == "completed":
        return NotificationEvent(
            id=f"wb-sync-{run_id}-completed",
            title="WB-данные обновлены",
            details=f"Синхронизация WB завершилась успешно за период {period_days} дней. Источники: {summary}.",
            severity="info",
            category="system",
            source="WB sync",
            manager="Система",
            createdAt=finished_at,
            entityType="system",
            entityId=run_id,
            route="/wb/repricer",
            blockedActions=[],
            freshness=NotificationFreshness(label="WB sync", state="fresh", updatedAt=finished_at),
        )

    if state == "partial":
        return NotificationEvent(
            id=f"wb-sync-{run_id}-partial",
            title="WB-данные обновлены частично",
            details=f"Часть источников WB не загрузилась. Успешные и проблемные шаги: {summary}. Ошибки: {'; '.join(errors) if errors else 'без текста ошибки'}.",
            severity="warning",
            category="system",
            source="WB sync",
            manager="Система",
            createdAt=finished_at,
            entityType="system",
            entityId=run_id,
            route="/wb/repricer",
            blockedActions=["Автоматические решения по неполным источникам"],
            freshness=NotificationFreshness(label="WB sync", state="partial", updatedAt=finished_at),
        )

    if state == "failed":
        return NotificationEvent(
            id=f"wb-sync-{run_id}-failed",
            title="WB sync не завершился",
            details=str(status.get("error") or "Синхронизация WB завершилась ошибкой."),
            severity="critical",
            category="system",
            source="WB sync",
            manager="Система",
            createdAt=finished_at,
            entityType="system",
            entityId=run_id,
            route="/wb/repricer",
            blockedActions=["Обновление зависимых витрин", "Автоматические решения по свежим данным WB"],
            freshness=NotificationFreshness(label="WB sync", state="stale", updatedAt=finished_at),
        )

    return NotificationEvent(
        id=f"wb-sync-{run_id}-stale",
        title="WB sync завис",
        details="Backend считает синхронизацию устаревшей: run был запущен, но не завершился в ожидаемое окно.",
        severity="warning",
        category="system",
        source="WB sync",
        manager="Система",
        createdAt=_utc_now_iso(),
        entityType="system",
        entityId=run_id,
        route="/wb/repricer",
        blockedActions=["Новые ручные refresh-запуски до проверки состояния"],
        freshness=NotificationFreshness(label="WB sync", state="stale", updatedAt=str(status.get("startedAt") or _utc_now_iso())),
    )


def record_wb_sync_notification(organization_id: int, status: dict[str, Any]) -> NotificationEvent | None:
    notification = build_wb_sync_notification(status)
    if notification is None:
        return None
    return record_notification(organization_id, notification)
