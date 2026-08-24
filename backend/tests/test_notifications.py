from __future__ import annotations

from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.main import create_app
from app.notifications import record_wb_sync_notification
from tests.auth_helpers import auth_headers


def client() -> TestClient:
    return TestClient(create_app())


def test_notifications_api_returns_and_marks_wb_sync_event_read():
    api = client()
    headers = auth_headers(api, "admin")
    run_id = f"wb_sync_test_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}"
    record_wb_sync_notification(
        1,
        {
            "state": "completed",
            "runId": run_id,
            "finishedAt": datetime.now(timezone.utc).isoformat(),
            "periodDays": 30,
            "steps": [{"source": "goods", "status": "ok", "count": 12}],
        },
    )

    listing = api.get("/api/v1/notifications", headers=headers)
    assert listing.status_code == 200
    items = listing.json()["data"]["items"]
    event = next(item for item in items if item["entityId"] == run_id)
    assert event["title"] == "WB-данные обновлены"
    assert event["readAt"] is None

    marked = api.post(f"/api/v1/notifications/{event['id']}/read", headers=headers)
    assert marked.status_code == 200
    marked_items = marked.json()["data"]["items"]
    marked_event = next(item for item in marked_items if item["id"] == event["id"])
    assert marked_event["readAt"] is not None
