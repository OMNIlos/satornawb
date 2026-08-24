from __future__ import annotations

from fastapi import APIRouter, Request

from app.control_plane.auth import actor_from_request
from app.contracts.envelopes import DataEnvelope
from app.notifications import (
    NotificationsResponse,
    list_notifications,
    mark_all_notifications_read,
    mark_notification_read,
)
from app.repricer_sync import get_wb_sync_status
from app.notifications import record_wb_sync_notification


router = APIRouter()


@router.get("/api/v1/notifications", response_model=DataEnvelope[NotificationsResponse])
def get_notifications(request: Request) -> DataEnvelope[NotificationsResponse]:
    actor = actor_from_request(request)
    status = get_wb_sync_status(actor.organization_id)
    if status.get("state") == "stale":
        record_wb_sync_notification(actor.organization_id, status)
    return DataEnvelope(data=NotificationsResponse(items=list_notifications(actor.organization_id)))


@router.post("/api/v1/notifications/{notificationId}/read", response_model=DataEnvelope[NotificationsResponse])
def post_notification_read(request: Request, notificationId: str) -> DataEnvelope[NotificationsResponse]:
    actor = actor_from_request(request)
    return DataEnvelope(data=NotificationsResponse(items=mark_notification_read(actor.organization_id, notificationId)))


@router.post("/api/v1/notifications/read-all", response_model=DataEnvelope[NotificationsResponse])
def post_notifications_read_all(request: Request) -> DataEnvelope[NotificationsResponse]:
    actor = actor_from_request(request)
    return DataEnvelope(data=NotificationsResponse(items=mark_all_notifications_read(actor.organization_id)))
