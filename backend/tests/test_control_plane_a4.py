from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import create_app
from tests.auth_helpers import auth_headers


def client() -> TestClient:
    return TestClient(create_app())


def settings_payload(max_step: float, mode: str = "manual") -> dict:
    return {
        "settings": {
            "strategyMode": mode,
            "applyScope": "sku",
            "maxPriceStepPctPerHour": max_step,
            "minMarginKopecks": 1000,
            "targetMarginPct": 18.5,
            "pminGuardEnabled": True,
            "pmaxGuardEnabled": True,
            "nightModeEnabled": False,
            "nightWindowStartHour": 1,
            "nightWindowEndHour": 5,
            "sppFallbackMode": "block",
        },
        "status": "draft",
    }


def test_settings_validation_rejects_price_step_above_19pct():
    api = client()
    response = api.post(
        "/api/v1/settings/versions",
        json=settings_payload(max_step=19.0),
        headers=auth_headers(api, "settings_editor"),
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_viewer_cannot_create_settings_and_blocked_attempt_is_audited():
    api = client()
    response = api.post(
        "/api/v1/settings/versions",
        json=settings_payload(max_step=5.0),
        headers=auth_headers(api, "viewer"),
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "HTTP_403"

    audit = api.get(
        "/api/v1/audit/events",
        params={"actionPrefix": "blocked.settings.version.create", "limit": 50},
        headers=auth_headers(api, "admin"),
    )
    assert audit.status_code == 200
    assert any(item["action"] == "blocked.settings.version.create" for item in audit.json()["items"])


def test_settings_versioning_diff_and_activation_flow():
    api = client()
    first = api.post(
        "/api/v1/settings/versions",
        json=settings_payload(max_step=5.0, mode="manual"),
        headers=auth_headers(api, "settings_editor"),
    )
    second = api.post(
        "/api/v1/settings/versions",
        json=settings_payload(max_step=6.0, mode="strategy_4599"),
        headers=auth_headers(api, "settings_editor"),
    )
    assert first.status_code == 200
    assert second.status_code == 200

    v1 = first.json()["data"]["version"]
    v2 = second.json()["data"]["version"]

    diff = api.get(
        f"/api/v1/settings/versions/{v2}/diff",
        params={"fromVersion": v1},
        headers=auth_headers(api, "settings_editor"),
    )
    assert diff.status_code == 200
    fields = {item["field"] for item in diff.json()["data"]["changedFields"]}
    assert {"maxPriceStepPctPerHour", "strategyMode"} <= fields

    activate = api.post(
        f"/api/v1/settings/versions/{v2}/activate",
        json={"reason": "approve for dry-run", "approvalRef": "APR-A4-001"},
        headers=auth_headers(api, "admin"),
    )
    assert activate.status_code == 200
    assert activate.json()["data"]["status"] == "active"


def test_sync_jobs_noop_flow_and_audit():
    api = client()
    created = api.post(
        "/api/v1/sync-jobs",
        json={"jobType": "source_poll", "source": "wb-prices", "period": "2026-05-01..2026-05-26", "staleAfterMinutes": 60},
        headers=auth_headers(api, "admin"),
    )
    assert created.status_code == 200
    job_id = created.json()["data"]["jobId"]

    run_noop = api.post(f"/api/v1/sync-jobs/{job_id}/run-noop", headers=auth_headers(api, "admin"))
    assert run_noop.status_code == 200
    assert run_noop.json()["data"]["status"] == "success"

    tick = api.post("/api/v1/sync-jobs/noop-tick", params={"limit": 5}, headers=auth_headers(api, "admin"))
    assert tick.status_code == 200
    assert tick.json()["data"]["totalProcessed"] >= 0


def test_price_apply_placeholder_logs_blocked_action():
    api = client()
    blocked = api.post(
        "/api/v1/wb-repricer/actions/price-apply-placeholder",
        params={"articleId": "FBBT_42"},
        headers=auth_headers(api, "price_sender"),
    )
    assert blocked.status_code == 409
    assert blocked.json()["error"]["code"] == "HTTP_409"

    audit = api.get(
        "/api/v1/audit/events",
        params={"actionPrefix": "blocked.price.apply", "limit": 50},
        headers=auth_headers(api, "admin"),
    )
    assert audit.status_code == 200
    assert any(item["objectId"] == "FBBT_42" for item in audit.json()["items"])


def test_price_apply_endpoint_blocks_direct_commit_without_draft_workflow():
    api = client()
    response = api.post(
        "/api/v1/wb-repricer/actions/price-apply",
        json={
            "scenario": "complete",
            "dryRun": False,
            "rows": [{"nmId": 123456, "priceKopecks": 139000, "discountPct": 12}],
        },
        headers=auth_headers(api, "price_sender"),
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "HTTP_409"

    audit = api.get(
        "/api/v1/audit/events",
        params={"actionPrefix": "blocked.price.apply.direct_commit", "limit": 50},
        headers=auth_headers(api, "admin"),
    )
    assert audit.status_code == 200
    assert any(item["action"] == "blocked.price.apply.direct_commit" for item in audit.json()["items"])
