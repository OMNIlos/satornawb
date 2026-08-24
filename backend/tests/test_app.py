import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from tests.auth_helpers import auth_headers


def client() -> TestClient:
    return TestClient(create_app())


def test_health_exposes_contract_version_and_price_apply_gate():
    response = client().get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["contractVersion"] == "0.19.05-runtime-boundary"
    assert response.json()["realPriceApplyEnabled"] is False


def test_production_refuses_weak_auth_secret(monkeypatch):
    monkeypatch.setenv("VELLA_ENV", "production")
    monkeypatch.setenv("VELLA_AUTH_SECRET", "change-this-secret")

    with pytest.raises(RuntimeError, match="VELLA_AUTH_SECRET"):
        create_app()


def test_production_disables_docs_and_legacy_1c_by_default(monkeypatch):
    monkeypatch.setenv("VELLA_ENV", "production")
    monkeypatch.setenv("VELLA_AUTH_SECRET", "a-random-production-auth-secret-that-is-long-enough")
    monkeypatch.delenv("VELLA_API_DOCS_ENABLED", raising=False)
    monkeypatch.delenv("VELLA_1C_ENABLED", raising=False)
    api = TestClient(create_app())

    assert api.get("/docs").status_code == 404
    assert api.get("/openapi.json").status_code == 404
    assert api.get("/api/1c/jobs").status_code == 404
    health = api.get("/health").json()
    assert health["apiDocsEnabled"] is False
    assert health["legacyOneCEnabled"] is False


def test_viewer_cannot_mutate_avito_integration_or_run_sync():
    api = client()
    headers = auth_headers(api, "viewer")

    regenerate = api.post("/api/v1/avito/orders/extension-token/regenerate", headers=headers)
    update_sync = api.put("/api/v1/avito/orders/returns-sync", headers=headers, json={"enabled": False})
    run_sync = api.post("/api/v1/avito/orders/returns-sync/run", headers=headers)

    assert regenerate.status_code == 403
    assert regenerate.json()["error"]["message"] == "NO_ACCESS:integrations:write"
    assert update_sync.status_code == 403
    assert update_sync.json()["error"]["message"] == "NO_ACCESS:integrations:write"
    assert run_sync.status_code == 403
    assert run_sync.json()["error"]["message"] == "NO_ACCESS:sync:run"


def test_source_registry_seed_is_available_from_backend_app():
    response = client().get("/api/v1/source-registry/blockers")

    assert response.status_code == 200
    blocker_ids = {row["blockerId"] for row in response.json()}
    assert {"WB-03", "WB-06", "WB-12", "WB-13", "WB-22", "WB-23"} <= blocker_ids


def test_sprint_d_reports_are_served_through_backend_app():
    api = client()
    viewer_headers = auth_headers(api, "viewer")

    pnl = api.get("/api/v1/wb-reports/pnl", headers=viewer_headers)
    assert pnl.status_code == 200
    assert pnl.json()["reportState"] == "preliminary"
    assert pnl.json()["blockerIds"] == []
    assert pnl.json()["rows"][0]["overheadKopecks"] is None
    assert pnl.json()["rows"][0]["adSpendKopecks"] is not None

    ads_sku = api.get("/api/v1/wb-reports/ads/performance", params={"groupBy": "sku"}, headers=viewer_headers)
    assert ads_sku.status_code == 200
    assert ads_sku.json()["rows"][0]["attributionLevel"] != "campaign_only"
    assert ads_sku.json()["totals"]["adSpendKopecks"] is not None

    rnp = api.get("/api/v1/wb-reports/rnp", headers=viewer_headers)
    assert rnp.status_code == 200
    assert rnp.json()["blockerIds"] == []
    assert rnp.json()["drrPct"] is not None
    assert rnp.json()["rows"][0]["roiPct"] is not None

    abc_all = api.get("/api/v1/wb-reports/abc", headers=viewer_headers).json()
    abc_filtered = api.get("/api/v1/wb-reports/abc", params={"filters": "status=locomotive"}, headers=viewer_headers).json()
    assert abc_all["filteredSummary"]["filterHash"] != abc_filtered["filteredSummary"]["filterHash"]
    assert abc_all["filteredSummary"]["profitKopecks"] is not None


def test_sprint_d_plan_fact_rating_and_export_are_available_for_viewer():
    api = client()
    viewer_headers = auth_headers(api, "viewer")

    plan_fact = api.get("/api/v1/wb-reports/plan-fact", params={"dimension": "manager"}, headers=viewer_headers)
    assert plan_fact.status_code == 200
    assert plan_fact.json()["blockerIds"] == ["WB-14A"]
    assert plan_fact.json()["rows"][0]["planKopecks"] is not None

    rating = api.get("/api/v1/wb-reports/sku-rating", headers=viewer_headers)
    assert rating.status_code == 200
    assert rating.json()["rows"][0]["scoreReasons"]
    assert rating.json()["rows"][0]["blockerIds"] == []

    export = api.get("/api/v1/wb-export/current-view", headers=viewer_headers)
    assert export.status_code == 200
    assert export.json()["exportState"] == "ready"
    assert export.json()["fileName"] is not None


def test_price_guard_and_review_approval_are_blocked_by_default():
    api = client()

    guard = api.get("/api/v1/wb-repricer/sku/FBBT_42/price-guard")
    assert guard.status_code == 200
    assert guard.json()["canApply"] is False
    assert guard.json()["freezeState"] == "frozen"
    assert guard.json()["blockerIds"] == []

    review = api.get("/api/v1/wb-reviews/wb-review-006/approval", params={"rating": 2})
    assert review.status_code == 200
    assert review.json()["approvalState"] == "required"
    assert review.json()["externalSendAllowed"] is False


def test_backend_rejects_invalid_report_group_by():
    api = client()
    response = api.get("/api/v1/wb-reports/pnl", params={"groupBy": "not-a-group"}, headers=auth_headers(api, "viewer"))

    assert response.status_code == 422


def test_repricer_discovery_source_map_keeps_spp_and_apply_blocked():
    response = client().get("/api/v1/wb-discovery/repricer/source-map")

    assert response.status_code == 200
    payload = response.json()
    assert payload["overallStatus"] == "ready"
    assert payload["realPriceApplyEnabled"] is False
    assert payload["canUnblockPriceGuard"] is True

    clusters = {cluster["blockerId"]: cluster for cluster in payload["clusters"]}
    assert {"WB-06", "WB-22", "WB-23"} <= set(clusters)
    assert clusters["WB-06"]["status"] == "confirmed"
    assert clusters["WB-23"]["status"] == "confirmed"
    assert all(candidate["status"] == "confirmed" for candidate in clusters["WB-06"]["candidates"])

    price_apply_candidates = clusters["WB-22"]["candidates"]
    assert any(candidate["path"] == "/api/v2/upload/task" for candidate in price_apply_candidates)
    assert all(not candidate["canRunInReadOnlyDiscovery"] for candidate in price_apply_candidates if candidate["riskLevel"] != "read_only")


def test_repricer_discovery_readiness_matches_price_guard_blockers():
    response = client().get("/api/v1/wb-discovery/repricer/readiness")

    assert response.status_code == 200
    payload = response.json()
    assert payload["canUnblockPriceGuard"] is True
    assert payload["realPriceApplyEnabled"] is False
    assert payload["blockingIds"] == []
    assert payload["nextProbeOrder"] == []


def test_read_prices_probe_endpoint_is_executable_but_does_not_unblock_apply():
    response = client().post("/api/v1/wb-discovery/repricer/probes/read-prices", json={"scenario": "complete", "articleId": "FBBT_42"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["probeKind"] == "read_prices"
    assert payload["sourceStatus"] == "fresh"
    assert payload["blockerIds"] == []
    assert payload["priceGuardPreview"]["canApply"] is False
    assert payload["priceGuardPreview"]["freezeState"] == "requires_review"


def test_read_prices_probe_endpoint_keeps_wb06_for_missing_spp_fields():
    response = client().post("/api/v1/wb-discovery/repricer/probes/read-prices", json={"scenario": "missing_spp"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["sourceStatus"] == "blocked"
    assert payload["blockerIds"] == ["WB-06"]
    assert payload["priceGuardPreview"]["canApply"] is False
    assert payload["priceGuardPreview"]["freezeState"] == "source_blocked"


def test_task_history_probe_endpoint_keeps_wb22_for_missing_row_errors():
    response = client().post("/api/v1/wb-discovery/repricer/probes/task-history", json={"scenario": "missing_task_errors"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["probeKind"] == "task_history"
    assert "WB-22" in payload["blockerIds"]
    assert payload["priceGuardPreview"]["canApply"] is False


def test_upload_lifecycle_probe_endpoint_returns_mapping_without_manual_checks():
    response = client().post(
        "/api/v1/wb-discovery/repricer/probes/upload-lifecycle",
        json={"scenario": "complete", "uploadId": 146567, "maxPolls": 3},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["probeKind"] == "upload_lifecycle"
    assert payload["lifecycleMap"]["uploadId"] == 146567
    assert payload["lifecycleMap"]["observations"]
    assert payload["lifecycleMap"]["proposedState"] in {"accepted", "processing", "queued", "requires_attention", "unknown"}


def test_mutating_price_upload_has_no_discovery_execution_route():
    response = client().post("/api/v1/wb-discovery/repricer/probes/upload-task", json={})

    assert response.status_code == 404
