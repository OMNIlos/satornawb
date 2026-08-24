from fastapi.testclient import TestClient

from app.main import create_app


def client() -> TestClient:
    return TestClient(create_app())


def test_wb23_freshness_policy_endpoint_exposes_critical_metrics():
    response = client().get("/api/v1/wb-repricer/wb23/freshness-policies")

    assert response.status_code == 200
    payload = response.json()["data"]
    metric_ids = {item["metricId"] for item in payload}
    assert {
        "current_price_before_spp",
        "current_price_after_spp",
        "spp_pct",
        "margin_rub_pct",
        "pmin_pmax_validation",
        "price_apply_status",
    } <= metric_ids


_DEMO_NM_ID = 123456


def test_price_metrics_endpoint_uses_supplier_orders_spp_fallback():
    response = client().get(
        "/api/v1/wb-repricer/sku/FBBT_42/price-metrics",
        params={"scenario": "complete", "nmId": _DEMO_NM_ID},
    )

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["sourceStatus"] == "fresh"
    metric_by_id = {item["metricId"]: item for item in payload["metrics"]}
    assert metric_by_id["current_price_before_spp"]["value"] is not None
    assert metric_by_id["current_price_after_spp"]["value"] is not None
    assert metric_by_id["spp_pct"]["value"] == 26
    assert metric_by_id["current_price_before_spp"]["fieldSource"] == "sizes[].discountedPrice"
    assert metric_by_id["spp_pct"]["fieldSource"] == "supplier.orders.spp"


def test_price_metrics_endpoint_marks_missing_spp_fields_as_blocked_without_orders():
    response = client().get(
        "/api/v1/wb-repricer/sku/FBBT_42/price-metrics",
        params={"scenario": "missing_spp", "nmId": 999999},
    )

    assert response.status_code == 200
    payload = response.json()["data"]
    metric_by_id = {item["metricId"]: item for item in payload["metrics"]}
    assert metric_by_id["current_price_before_spp"]["sourceStatus"] == "fresh"
    assert metric_by_id["current_price_after_spp"]["sourceStatus"] == "blocked"
    assert metric_by_id["spp_pct"]["sourceStatus"] == "blocked"


def test_margin_preview_blocks_without_live_buyer_plane_price():
    response = client().post(
        "/api/v1/wb-repricer/sku/FBBT_42/margin-preview",
        json={
            "scenario": "complete",
            "nmId": _DEMO_NM_ID,
            "costPriceKopecks": 60_000,
            "wbCommissionPct": 20,
            "logisticsKopecks": 5_000,
            "acquiringKopecks": 1_000,
            "taxKopecks": 2_000,
        },
    )

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["sellPriceKopecks"] is None
    assert payload["wbCommissionKopecks"] is None
    assert payload["marginRubKopecks"] is None
    assert payload["marginPct"] is None
    assert payload["sourceStatus"] == "blocked"


def test_pmin_pmax_validation_rejects_unsafe_price():
    response = client().post(
        "/api/v1/wb-repricer/sku/FBBT_42/pmin-pmax/validate",
        json={
            "scenario": "complete",
            "nmId": _DEMO_NM_ID,
            "candidateBuyerPriceKopecks": 20_000,
            "costPriceKopecks": 60_000,
            "wbCommissionPct": 20,
            "targetMarginPct": 10,
            "logisticsKopecks": 5_000,
            "taxKopecks": 2_000,
            "fixedCostsKopecks": 1_000,
            "pMaxKopecks": 200_000,
        },
    )

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["isValid"] is False
    assert "candidate_buyer_price_below_p_min" in payload["reasons"]


def test_apply_status_endpoint_maps_wb_status_codes():
    response = client().get("/api/v1/wb-repricer/uploads/146567/apply-status", params={"scenario": "complete"})

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["wbStatus"] == 3
    assert payload["statusLabel"] == "success"
    assert payload["blockerIds"] == []
