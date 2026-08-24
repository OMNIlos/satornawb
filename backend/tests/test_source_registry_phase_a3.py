from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.main import create_app
from app.source_registry.schemas import SourceRegistryItem


def client() -> TestClient:
    return TestClient(create_app())


def test_source_registry_entries_are_exposed_with_formula_and_blockers():
    response = client().get("/api/v1/source-registry/entries")

    assert response.status_code == 200
    items = response.json()["data"]
    assert len(items) > 20
    first = items[0]
    assert first["formulaId"].startswith("frm-")
    assert isinstance(first["blockerIds"], list)
    assert first["freshnessConfidence"]


def test_source_registry_filtering_by_module_and_blocker():
    response = client().get(
        "/api/v1/source-registry/entries/paginated",
        params={"module": "repricer", "blockerId": "WB-03", "limit": 200},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] > 0
    assert all(item["module"] == "repricer" for item in payload["items"])
    assert all("WB-03" in item["blockerIds"] for item in payload["items"])


def test_blocker_catalog_is_seeded_from_open_questions_register():
    response = client().get("/api/v1/source-registry/blockers/catalog", params={"lifecycleStatus": "BLOCKER"})

    assert response.status_code == 200
    rows = response.json()["data"]
    ids = {row["blockerId"] for row in rows}
    assert {"WB-01", "WB-03"} <= ids
    assert "WB-22" not in ids
    assert "WB-23" not in ids


def test_registry_unresolved_blockers_endpoint_returns_blocker_ids():
    response = client().get("/api/v1/source-registry/entries/unresolved-blockers")

    assert response.status_code == 200
    unresolved = set(response.json()["data"])
    assert "WB-03" in unresolved
    assert "WB-22" not in unresolved
    assert "WB-23" not in unresolved


def test_ads_registry_distinguishes_confirmed_sources_from_own_cache_and_business_config():
    response = client().get(
        "/api/v1/source-registry/entries/paginated",
        params={"screen": "/wb/reports/ads", "limit": 200},
    )

    assert response.status_code == 200
    rows = response.json()["items"]
    by_metric = {row["metricAction"]: row for row in rows}
    assert by_metric["Campaign budget"]["status"] == "confirmed"
    assert by_metric["Ads cabinet balance"]["status"] == "confirmed"
    assert by_metric["Daily ads dynamics"]["status"] == "confirmed"
    assert by_metric["Historical status breakdown"]["status"] == "requires_own_cache"
    assert by_metric["Max DRR/review thresholds"]["status"] == "business_config"


def test_stock_registry_contains_confirmed_api_sources_and_manual_gaps():
    response = client().get(
        "/api/v1/source-registry/entries/paginated",
        params={"screen": "/wb/reports/stock", "limit": 200},
    )

    assert response.status_code == 200
    rows = response.json()["items"]
    by_metric = {row["metricAction"].strip("`"): row for row in rows}
    expected_sources = {
        "wb_stock_current",
        "wb_stock_remains_async",
        "seller_stock_current",
        "raw_orders",
        "raw_sales",
        "buyer_region_sales",
        "stock_product_metrics",
        "stock_size_office_metrics",
        "wb_offices_dim",
        "fbw_warehouses_dim",
        "box_tariffs",
        "pallet_tariffs",
        "finance_logistics_fact",
        "local_orders_exact",
        "ktr_table",
        "krp_table",
        "stock_decision_rules",
    }
    assert expected_sources <= set(by_metric)
    assert by_metric["wb_stock_current"]["status"] == "confirmed"
    assert by_metric["raw_orders"]["status"] == "confirmed"
    assert by_metric["raw_orders"]["blockerIds"] == ["WB-01"]
    assert by_metric["buyer_region_sales"]["status"] == "confirmed"
    assert "no warehouse dimension" in by_metric["buyer_region_sales"]["freshnessConfidence"]
    assert by_metric["local_orders_exact"]["status"] == "manual_fallback"
    assert set(by_metric["local_orders_exact"]["blockerIds"]) == {"WB-01", "WB-17"}
    assert by_metric["ktr_table"]["status"] == "manual_fallback"
    assert by_metric["stock_decision_rules"]["status"] == "business_config"


def test_confirmed_registry_row_requires_full_lineage_payload():
    with pytest.raises(ValidationError):
        SourceRegistryItem(
            rowId=999,
            screen="/wb/reports",
            metricAction="Broken confirmed row",
            module="reports",
            sourceName="",
            sourceField="",
            formulaText="",
            formulaId="",
            refreshPolicy="",
            fallbackPolicy="",
            freshnessConfidence="",
            status="confirmed",
            blockerIds=[],
            criticalForApply=False,
            sourceRef="test",
        )
