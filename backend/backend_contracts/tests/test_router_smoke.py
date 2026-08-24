from fastapi import FastAPI
from fastapi.testclient import TestClient

from vella_wb_19_05.router import router


def client() -> TestClient:
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_report_and_guard_stubs_serialize_through_fastapi():
    api = client()

    pnl = api.get("/api/v1/wb-reports/pnl")
    assert pnl.status_code == 200
    assert pnl.json()["reportState"] == "blocked"
    assert pnl.json()["sourceEvidence"][0]["sourceType"] == "mock"

    ads_sku = api.get("/api/v1/wb-reports/ads/performance", params={"groupBy": "sku"})
    assert ads_sku.status_code == 200
    assert ads_sku.json()["rows"][0]["attributionLevel"] != "campaign_only"

    rnp = api.get("/api/v1/wb-reports/rnp")
    assert rnp.status_code == 200
    assert {"WB-02", "WB-11"} <= set(rnp.json()["blockerIds"])

    abc_default = api.get("/api/v1/wb-reports/abc").json()
    abc_filtered = api.get("/api/v1/wb-reports/abc", params={"filters": "status=locomotive"}).json()
    assert abc_default["filteredSummary"]["filterHash"] != abc_filtered["filteredSummary"]["filterHash"]

    guard = api.get("/api/v1/wb-repricer/sku/FBBT_42/price-guard")
    assert guard.status_code == 200
    assert guard.json()["canApply"] is False

    invalid_group = api.get("/api/v1/wb-reports/ads/performance", params={"groupBy": "not-a-group"})
    assert invalid_group.status_code == 422


def test_review_approval_and_source_registry_stubs_serialize_through_fastapi():
    api = client()

    blockers = api.get("/api/v1/source-registry/blockers")
    assert blockers.status_code == 200
    assert {"WB-02", "WB-06", "WB-22", "WB-23"} <= {row["blockerId"] for row in blockers.json()}

    low_rating = api.get("/api/v1/wb-reviews/wb-review-006/approval", params={"rating": 2})
    assert low_rating.status_code == 200
    assert low_rating.json()["externalSendAllowed"] is False

    safe_rating = api.get("/api/v1/wb-reviews/wb-review-001/approval", params={"rating": 5})
    assert safe_rating.status_code == 200
    assert safe_rating.json()["sendState"] == "ready_to_send"
