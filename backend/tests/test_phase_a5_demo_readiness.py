from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.main import create_app
from tests.auth_helpers import auth_headers
from vella_wb_19_05.models import AdsPerformanceResponse, PnlReportResponse, PriceGuardResponse, RnpReportResponse
from vella_wb_19_05.stubs import build_ads_performance_stub, build_pnl_report_stub, build_price_guard_stub, build_rnp_report_stub


def client() -> TestClient:
    return TestClient(create_app())


def _dump(model):
    return model.model_dump(mode="python")


def test_account_health_default_is_ready_without_blockers():
    api = client()
    response = api.get("/api/v1/wb/account/health", headers=auth_headers(api, "viewer"))

    assert response.status_code == 200
    payload = response.json()
    assert payload["sourceStatus"] == "ready"
    assert payload["authState"] == "token_ok"
    assert payload["blockerIds"] == []


def test_account_health_missing_token_is_unknown_missing_access():
    api = client()
    response = api.get("/api/v1/wb/account/health", params={"scenario": "missing_token"}, headers=auth_headers(api, "viewer"))

    assert response.status_code == 200
    payload = response.json()
    assert payload["sourceStatus"] == "unknown"
    assert payload["authState"] == "missing_access"
    assert payload["blockerIds"] == []


def test_account_health_check_is_audited_without_secret_leakage():
    api = client()
    viewer_headers = auth_headers(api, "viewer")
    health = api.get(
        "/api/v1/wb/account/health",
        params={"scenario": "missing_scope"},
        headers=viewer_headers,
    )
    assert health.status_code == 200

    events = api.get(
        "/api/v1/audit/events",
        params={"actionPrefix": "wb.token_health.check"},
        headers=viewer_headers,
    )
    assert events.status_code == 200
    payload = events.json()
    assert payload["total"] >= 1
    event = payload["items"][0]
    assert event["action"] == "wb.token_health.check"
    assert event["objectType"] == "wb_account"
    assert event["afterState"]["authState"] == "scope_missing"
    assert "token" not in "".join(event["afterState"].keys()).lower()


def test_source_registry_demo_route_supports_module_wb():
    response = client().get("/api/v1/source-registry", params={"module": "wb"})

    assert response.status_code == 200
    payload = response.json()
    assert payload
    assert all(item["status"] in {"blocked", "unknown", "resolved"} for item in payload)
    assert all(item["evidenceRef"].startswith("docs/open-questions-current.md#") for item in payload)


def test_pnl_final_rejects_blockers():
    payload = _dump(build_pnl_report_stub())
    payload["reportState"] = "final"

    with pytest.raises(ValidationError):
        PnlReportResponse.model_validate(payload)


def test_ads_sku_rejects_campaign_only():
    payload = _dump(build_ads_performance_stub(group_by="sku"))
    payload["rows"][0]["attributionLevel"] = "campaign_only"

    with pytest.raises(ValidationError):
        AdsPerformanceResponse.model_validate(payload)


def test_ads_blocked_requires_wb02():
    payload = _dump(build_ads_performance_stub())
    payload["blockerIds"] = ["WB-23"]

    with pytest.raises(ValidationError):
        AdsPerformanceResponse.model_validate(payload)


def test_rnp_missing_drr_requires_wb11():
    payload = _dump(build_rnp_report_stub())
    payload["blockerIds"] = ["WB-02", "WB-23"]

    with pytest.raises(ValidationError):
        RnpReportResponse.model_validate(payload)


def test_price_guard_apply_rejects_blockers():
    payload = _dump(build_price_guard_stub("FBBT_42"))
    payload["canApply"] = True

    with pytest.raises(ValidationError):
        PriceGuardResponse.model_validate(payload)


def test_price_guard_apply_rejects_stale_spp():
    payload = _dump(build_price_guard_stub("FBBT_42"))
    payload["canApply"] = True
    payload["blockedReason"] = None
    payload["freezeState"] = "none"
    payload["blockerIds"] = []
    payload["guardTriggers"] = []

    with pytest.raises(ValidationError):
        PriceGuardResponse.model_validate(payload)
