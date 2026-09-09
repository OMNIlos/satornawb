from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app.main import create_app
from app.wb_reports_sprint_d import build_abc_report, build_pnl_report
from tests.auth_helpers import auth_headers


def client() -> TestClient:
    return TestClient(create_app())


def test_pnl_finance_viewer_gets_financial_fields_and_preliminary_state():
    api = client()
    response = api.get("/api/v1/wb-reports/pnl", headers=auth_headers(api, "finance_viewer"))

    assert response.status_code == 200
    payload = response.json()
    assert payload["reportState"] == "preliminary"
    assert payload["totals"]["revenueKopecks"] is not None
    assert payload["totals"]["netProfitKopecks"] is not None
    assert "WB-11" not in payload["blockerIds"]


def test_pnl_supports_operative_and_final_states():
    api = client()

    operative = api.get(
        "/api/v1/wb-reports/pnl",
        params={"source": "operative"},
        headers=auth_headers(api, "finance_viewer"),
    )
    assert operative.status_code == 200
    assert operative.json()["reportState"] == "operative"

    final = api.get(
        "/api/v1/wb-reports/pnl",
        params={"source": "final"},
        headers=auth_headers(api, "finance_viewer"),
    )
    assert final.status_code == 200
    final_payload = final.json()
    assert final_payload["reportState"] == "final"
    assert final_payload["blockerIds"] == []


def test_ads_weak_attribution_stays_campaign_level_and_not_sku_level():
    api = client()

    campaign = api.get(
        "/api/v1/wb-reports/ads/performance",
        params={"groupBy": "campaign"},
        headers=auth_headers(api, "finance_viewer"),
    )
    assert campaign.status_code == 200
    assert any(row["attributionLevel"] == "campaign_only" for row in campaign.json()["rows"])
    assert "WB-02" not in campaign.json()["blockerIds"]

    sku = api.get(
        "/api/v1/wb-reports/ads/performance",
        params={"groupBy": "sku"},
        headers=auth_headers(api, "finance_viewer"),
    )
    assert sku.status_code == 200
    assert sku.json()["rows"][0]["attributionLevel"] in {"exact_sku", "campaign_sku"}


def test_ads_bff_exposes_confirmed_budget_balance_upd_and_daily_sources():
    api = client()
    response = api.get("/api/wb/reports/ads", headers=auth_headers(api, "finance_viewer"))

    assert response.status_code == 200
    payload = response.json()
    kpis = {item["id"]: item for item in payload["kpis"]}
    assert int(kpis["campaign_budget"]["value"]) > 0
    assert int(kpis["cabinet_balance"]["value"]) > 0
    assert int(kpis["upd_rows"]["value"]) > 0
    assert int(kpis["daily_rows"]["value"]) > 0
    assert payload["spendDocuments"][0]["adSpendKopecks"] > 0
    assert payload["dailyRows"][0]["date"]
    assert any(row["unallocatedSpend"] for row in payload["rows"])
    assert any(source["sourceId"] == "wb-ads-budget" for source in payload["sourceEvidence"])
    assert any(source["sourceId"] == "wb-ads-balance" for source in payload["sourceEvidence"])
    assert any(source["sourceId"] == "wb-ads-upd" for source in payload["sourceEvidence"])


def test_ads_bff_refreshes_and_reuses_cached_report_payload(monkeypatch):
    api = client()
    headers = auth_headers(api, "finance_viewer")
    params = {"preset": "custom", "from": "2026-07-01", "to": "2026-07-01"}

    refreshed = api.post("/api/wb/reports/ads/refresh", params=params, headers=headers)
    assert refreshed.status_code == 200
    assert refreshed.json()["cache"]["status"] == "refreshed"

    def fail_live_builder(*_args, **_kwargs):
        raise AssertionError("GET must use ads report cache after refresh")

    monkeypatch.setattr("app.routers.wb_reports_bff.build_ads_attribution_snapshot", fail_live_builder)
    cached = api.get("/api/wb/reports/ads", params=params, headers=headers)

    assert cached.status_code == 200
    payload = cached.json()
    assert payload["cache"]["status"] == "hit"
    assert payload["rows"]


def test_rnp_has_confirmed_drr_formula_and_finance_viewer_can_see_roi():
    api = client()
    response = api.get("/api/v1/wb-reports/rnp", headers=auth_headers(api, "finance_viewer"))
    assert response.status_code == 200
    payload = response.json()
    assert payload["drrPct"] is not None
    assert payload["rows"][0]["roiPct"] is not None
    assert "WB-02" not in payload["blockerIds"]
    assert "WB-11" not in payload["blockerIds"]


def test_plan_fact_and_export_are_available_for_finance_viewer():
    api = client()

    plan_fact = api.get(
        "/api/v1/wb-reports/plan-fact",
        params={"dimension": "manager"},
        headers=auth_headers(api, "finance_viewer"),
    )
    assert plan_fact.status_code == 200
    row = plan_fact.json()["rows"][0]
    assert row["planKopecks"] is not None
    assert row["factKopecks"] is not None

    export = api.get(
        "/api/v1/wb-export/current-view",
        params={"filters": "group=locomotive"},
        headers=auth_headers(api, "finance_viewer"),
    )
    assert export.status_code == 200
    export_payload = export.json()
    assert export_payload["exportState"] == "ready"
    assert export_payload["fileName"] is not None


def test_viewer_sees_all_financial_sections_except_monthly_company_costs():
    api = client()
    viewer_headers = auth_headers(api, "viewer")

    pnl = api.get("/api/v1/wb-reports/pnl", headers=viewer_headers)
    assert pnl.status_code == 200
    pnl_payload = pnl.json()
    assert pnl_payload["rows"][0]["overheadKopecks"] is None
    assert pnl_payload["rows"][0]["adSpendKopecks"] is not None
    assert pnl_payload["manualCosts"][-1]["costId"] == "overhead"
    assert pnl_payload["manualCosts"][-1]["amountKopecks"] is None

    export = api.get("/api/v1/wb-export/current-view", headers=viewer_headers)
    assert export.status_code == 200
    assert export.json()["exportState"] == "ready"


def test_pnl_uses_repricer_finance_cache_before_legacy_runtime(monkeypatch):
    def fake_get_source_cache(_organization_id: int, source_key: str, *, slim: bool = False):
        if source_key == "finance_2026-06-01_2026-06-30":
            return {
                "fetchedAt": "2026-06-30T08:00:00+00:00",
                "dateFrom": "2026-06-01",
                "dateTo": "2026-06-30",
                "aggregates": {
                    "123456": {
                        "salesUnits": 2,
                        "sellerRevenueKopecks": 200_000,
                        "buyerRevenueKopecks": 190_000,
                        "commissionFormulaKopecks": 20_000,
                        "commissionKopecks": 18_000,
                        "logisticsKopecks": 7_000,
                        "storageKopecks": 1_000,
                        "acceptanceKopecks": 500,
                        "penaltyKopecks": -300,
                        "deductionKopecks": 200,
                        "additionalPaymentKopecks": 100,
                        "acquiringKopecks": 3_000,
                    }
                },
            }
        if source_key == "ads_2026-06-01_2026-06-30":
            return {
                "fetchedAt": "2026-06-30T08:00:00+00:00",
                "dateFrom": "2026-06-01",
                "dateTo": "2026-06-30",
                "aggregates": {"123456": {"adSpendKopecks": 4_000}},
            }
        return None

    monkeypatch.setattr("app.wb_reports_sprint_d.get_source_cache", fake_get_source_cache)
    monkeypatch.setattr(
        "app.wb_reports_sprint_d.list_cached_goods",
        lambda _organization_id: [{"nmID": 123456, "vendorCode": "FBBT_42", "brand": "Satorna", "subjectName": "Футболки"}],
    )
    monkeypatch.setattr(
        "app.wb_reports_sprint_d.load_runtime_state",
        lambda _organization_id: {
            "skuSettingsOverrides": {"FBBT_42": {"cogsKopecks": 45_000}},
            "skuMetaOverrides": {"FBBT_42": {"managerId": "maria", "status": "locomotive"}},
        },
    )
    monkeypatch.setattr(
        "app.wb_reports_sprint_d.load_algorithm_settings",
        lambda _organization_id: {"taxPct": 6, "otherExpensePricePct": 5, "otherExpensePerSaleRub": 0},
    )

    payload = build_pnl_report(
        date_from=date(2026, 6, 1),
        date_to=date(2026, 6, 30),
        group_by="sku",
        requested_state="final",
        finance_allowed=True,
        organization_id=77,
    )

    row = payload.rows[0]
    assert row.rowId == "nm-123456"
    assert row.cogsKopecks == 90_000
    assert row.commissionKopecks == 20_000
    assert row.logisticsKopecks == 7_000
    assert row.storageKopecks == 1_700
    assert row.adSpendKopecks == 4_000
    assert row.taxKopecks == 12_000
    assert row.overheadKopecks == 10_000
    assert row.netProfitKopecks == 52_700
    assert payload.reportState == "final"
    assert payload.sourceEvidence[0].sourceId == "wb-finance-sales-reports-detailed-cache"
    assert all(mapping.sourceId != "wb-statistics-realization-details" for mapping in payload.fieldMapping)


def test_pnl_finance_cache_does_not_require_live_ads_token(monkeypatch):
    def fake_get_source_cache(_organization_id: int, source_key: str, *, slim: bool = False):
        if source_key == "finance_2026-06-01_2026-06-30":
            return {
                "fetchedAt": "2026-06-30T08:00:00+00:00",
                "aggregates": {
                    "123456": {
                        "salesUnits": 1,
                        "sellerRevenueKopecks": 100_000,
                        "commissionKopecks": 10_000,
                        "logisticsKopecks": 5_000,
                    }
                },
            }
        return None

    def fail_live_ads_call(*_args, **_kwargs):
        raise RuntimeError("VELLA_WB_ADS_API_TOKEN is required when VELLA_WB_API_MODE=real")

    monkeypatch.setattr("app.wb_reports_sprint_d.get_source_cache", fake_get_source_cache)
    monkeypatch.setattr("app.wb_reports_sprint_d.build_ads_attribution_snapshot", fail_live_ads_call)
    monkeypatch.setattr("app.wb_reports_sprint_d.list_cached_goods", lambda _organization_id: [{"nmID": 123456, "vendorCode": "FBBT_42"}])
    monkeypatch.setattr("app.wb_reports_sprint_d.load_runtime_state", lambda _organization_id: {})
    monkeypatch.setattr("app.wb_reports_sprint_d.load_algorithm_settings", lambda _organization_id: {"taxPct": 0})

    payload = build_pnl_report(
        date_from=date(2026, 6, 1),
        date_to=date(2026, 6, 30),
        group_by="sku",
        requested_state="final",
        finance_allowed=True,
        organization_id=77,
    )

    assert payload.sourceStatus == "partial"
    assert payload.confidence == "medium"
    assert payload.blockerIds == ["WB-02"]
    assert payload.reportState == "preliminary"
    assert payload.rows[0].adSpendKopecks == 0
    assert any(evidence.sourceId == "wb-ads-attribution-cache" for evidence in payload.sourceEvidence)


def test_pnl_uses_repricing_period_cache_when_exact_range_cache_is_missing(monkeypatch):
    def fake_get_source_cache(_organization_id: int, source_key: str, *, slim: bool = False):
        if source_key == "finance_30":
            return {
                "fetchedAt": "2026-06-30T08:00:00+00:00",
                "aggregates": {
                    "123456": {
                        "salesUnits": 2,
                        "sellerRevenueKopecks": 200_000,
                        "commissionFormulaKopecks": 20_000,
                        "logisticsKopecks": 7_000,
                        "penaltyKopecks": 1_000,
                    }
                },
            }
        return None

    monkeypatch.setattr("app.wb_reports_sprint_d.get_source_cache", fake_get_source_cache)
    monkeypatch.setattr("app.wb_reports_sprint_d.list_cached_goods", lambda _organization_id: [{"nmID": 123456, "vendorCode": "FBBT_42"}])
    monkeypatch.setattr("app.wb_reports_sprint_d.load_runtime_state", lambda _organization_id: {})
    monkeypatch.setattr("app.wb_reports_sprint_d.load_algorithm_settings", lambda _organization_id: {"taxPct": 0})

    payload = build_pnl_report(
        date_from=date(2026, 6, 2),
        date_to=date(2026, 7, 1),
        group_by="sku",
        requested_state="preliminary",
        finance_allowed=True,
        organization_id=77,
    )

    assert payload.rows
    assert payload.rows[0].cogsKopecks == 76_000
    assert payload.rows[0].commissionKopecks == 20_000
    assert payload.rows[0].storageKopecks == 1_000


def test_pnl_finance_cache_normalizes_negative_revenue_rows(monkeypatch):
    def fake_get_source_cache(_organization_id: int, source_key: str, *, slim: bool = False):
        if source_key == "finance_2026-06-01_2026-06-30":
            return {
                "fetchedAt": "2026-06-30T08:00:00+00:00",
                "aggregates": {
                    "123456": {
                        "salesUnits": -1,
                        "sellerRevenueKopecks": -139_000,
                        "commissionKopecks": -10_000,
                        "logisticsKopecks": -5_000,
                        "storageKopecks": -1_000,
                    }
                },
            }
        return None

    monkeypatch.setattr("app.wb_reports_sprint_d.get_source_cache", fake_get_source_cache)
    monkeypatch.setattr("app.wb_reports_sprint_d.list_cached_goods", lambda _organization_id: [{"nmID": 123456, "vendorCode": "FBBT_42"}])
    monkeypatch.setattr("app.wb_reports_sprint_d.load_runtime_state", lambda _organization_id: {})
    monkeypatch.setattr(
        "app.wb_reports_sprint_d.load_algorithm_settings",
        lambda _organization_id: {"taxPct": 6, "otherExpensePricePct": 5, "otherExpensePerSaleRub": 0},
    )

    payload = build_pnl_report(
        date_from=date(2026, 6, 1),
        date_to=date(2026, 6, 30),
        group_by="sku",
        requested_state="preliminary",
        finance_allowed=True,
        organization_id=77,
    )

    row = payload.rows[0]
    assert row.revenueKopecks == 0
    assert row.taxKopecks == 0
    assert row.overheadKopecks == 0
    assert row.commissionKopecks == 0
    assert row.logisticsKopecks == 0
    assert row.storageKopecks == 0
    assert row.netProfitKopecks == -139_000


def test_pnl_report_response_is_cached_for_two_hours(monkeypatch):
    """Retain the historical node ID; current cache contract is 24h, no stale window."""
    source_cache: dict[str, dict] = {}
    finance_reads = {"count": 0}
    monkeypatch.setattr("app.wb_reports_sprint_d.list_source_cache_ranges_by_prefix", lambda *_args, **_kwargs: [])

    def fake_get_source_cache(_organization_id: int, source_key: str, *, slim: bool = False):
        if source_key.startswith("pnl_report_"):
            return source_cache.get(source_key)
        if source_key == "finance_2026-06-01_2026-06-30":
            finance_reads["count"] += 1
            return {
                "revenueBasis": "retailAmount",
                "financeSchemaVersion": "v3",
                "fetchedAt": "2026-06-30T08:00:00+00:00",
                "aggregates": {
                    "123456": {
                        "salesUnits": 1,
                        "sellerRevenueKopecks": 100_000,
                        "commissionKopecks": 10_000,
                    }
                },
            }
        return None

    def fake_save_source_cache(_organization_id: int, source_key: str, payload: dict):
        stored = dict(payload)
        stored["fetchedAt"] = datetime.now(timezone.utc).isoformat()
        source_cache[source_key] = stored
        return stored

    monkeypatch.setattr("app.wb_reports_sprint_d.get_source_cache", fake_get_source_cache)
    monkeypatch.setattr("app.wb_reports_sprint_d.save_source_cache", fake_save_source_cache)
    monkeypatch.setattr("app.wb_reports_sprint_d.list_cached_goods", lambda _organization_id: [{"nmID": 123456, "vendorCode": "FBBT_42"}])
    monkeypatch.setattr("app.wb_reports_sprint_d.load_runtime_state", lambda _organization_id: {})
    monkeypatch.setattr("app.wb_reports_sprint_d.load_algorithm_settings", lambda _organization_id: {"taxPct": 0})

    first = build_pnl_report(
        date_from=date(2026, 6, 1),
        date_to=date(2026, 6, 30),
        group_by="sku",
        requested_state="preliminary",
        finance_allowed=True,
        organization_id=77,
    )
    second = build_pnl_report(
        date_from=date(2026, 6, 1),
        date_to=date(2026, 6, 30),
        group_by="sku",
        requested_state="preliminary",
        finance_allowed=True,
        organization_id=77,
    )

    assert finance_reads["count"] == 1
    assert first.rows[0].revenueKopecks == second.rows[0].revenueKopecks == 100_000
    assert any(key.startswith("pnl_report_") for key in source_cache)
    cached_payload = next(iter(source_cache.values()))
    assert cached_payload["ttlSeconds"] == 86400
    assert cached_payload["staleTtlSeconds"] == 86400

    cached_payload["fetchedAt"] = (datetime.now(timezone.utc) - timedelta(hours=3)).isoformat()
    finance_reads["count"] = 0

    still_cached = build_pnl_report(
        date_from=date(2026, 6, 1),
        date_to=date(2026, 6, 30),
        group_by="sku",
        requested_state="preliminary",
        finance_allowed=True,
        organization_id=77,
    )

    assert finance_reads["count"] == 0
    assert still_cached == first

    cached_payload["fetchedAt"] = (datetime.now(timezone.utc) - timedelta(hours=25)).isoformat()
    rebuilt = build_pnl_report(
        date_from=date(2026, 6, 1), date_to=date(2026, 6, 30),
        group_by="sku", requested_state="preliminary", finance_allowed=True,
        organization_id=77,
    )
    assert finance_reads["count"] == 1
    assert rebuilt.rows[0].revenueKopecks == 100_000
    assert next(iter(source_cache.values()))["fetchedAt"] != cached_payload["fetchedAt"]


def test_abc_report_uses_repricer_period_cache_without_own_report_cache(monkeypatch):
    finance_reads = {"count": 0}

    def fake_get_source_cache(_organization_id: int, source_key: str, *, slim: bool = False):
        if source_key.startswith("abc_report_"):
            raise AssertionError("ABC report must not read its own response cache")
        if source_key == "finance_2026-06-01_2026-06-30":
            finance_reads["count"] += 1
            return {
                "fetchedAt": "2026-06-30T08:00:00+00:00",
                "dateFrom": "2026-06-01",
                "dateTo": "2026-06-30",
                "aggregates": {
                    "111": {
                        "salesUnits": 10,
                        "sellerRevenueKopecks": 1_000_000,
                        "buyerRevenueKopecks": 1_100_000,
                        "commissionFormulaKopecks": 100_000,
                        "logisticsKopecks": 50_000,
                        "storageKopecks": 10_000,
                        "netProfitKopecks": 0,
                    },
                    "222": {
                        "salesUnits": 1,
                        "sellerRevenueKopecks": 100_000,
                        "buyerRevenueKopecks": 110_000,
                        "commissionFormulaKopecks": 10_000,
                        "logisticsKopecks": 5_000,
                        "storageKopecks": 1_000,
                        "netProfitKopecks": 0,
                    },
                },
            }
        if source_key == "ads_2026-06-01_2026-06-30":
            return {
                "fetchedAt": "2026-06-30T08:00:00+00:00",
                "dateFrom": "2026-06-01",
                "dateTo": "2026-06-30",
                "aggregates": {
                    "111": {"adSpendKopecks": 20_000},
                    "222": {"adSpendKopecks": 60_000},
                },
            }
        if source_key == "stocks_2026-06-01_2026-06-30":
            return {
                "aggregates": {
                    "111": {"stockUnits": 15, "wbStockUnits": 15},
                    "222": {"stockUnits": 4, "wbStockUnits": 4},
                }
            }
        if source_key == "period_stats_2026-06-01_2026-06-30":
            return {
                "aggregates": {
                    "111": {"ordersUnits": 12, "ordersKopecks": 1_200_000, "baskets": 30, "buyoutPct": 80},
                    "222": {"ordersUnits": 2, "ordersKopecks": 200_000, "baskets": 3, "buyoutPct": 40},
                }
            }
        return None

    def fake_save_source_cache(_organization_id: int, source_key: str, payload: dict):
        raise AssertionError("ABC report must not write its own response cache")

    monkeypatch.setattr("app.wb_reports_sprint_d.get_source_cache", fake_get_source_cache)
    monkeypatch.setattr("app.wb_reports_sprint_d.save_source_cache", fake_save_source_cache)
    monkeypatch.setattr("app.wb_reports_sprint_d.list_source_cache_ranges_by_prefix", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(
        "app.wb_reports_sprint_d.list_cached_goods",
        lambda _organization_id: [
            {"nmID": 111, "vendorCode": "FBBT_11", "brand": "Satorna", "subjectName": "Футболки"},
            {"nmID": 222, "vendorCode": "HBBT_22", "brand": "Satorna", "subjectName": "Худи"},
        ],
    )
    monkeypatch.setattr(
        "app.wb_reports_sprint_d.load_runtime_state",
        lambda _organization_id: {
            "skuSettingsOverrides": {
                "FBBT_11": {"cogsKopecks": 30_000},
                "HBBT_22": {"cogsKopecks": 80_000},
            },
            "skuMetaOverrides": {
                "FBBT_11": {"managerId": "maria", "status": "locomotive"},
                "HBBT_22": {"managerId": "irina", "status": "liquidation"},
            },
        },
    )
    monkeypatch.setattr(
        "app.wb_reports_sprint_d.load_algorithm_settings",
        lambda _organization_id: {"taxPct": 0, "otherExpensePricePct": 0, "otherExpensePerSaleRub": 0},
    )

    first = build_abc_report(
        date_from=date(2026, 6, 1),
        date_to=date(2026, 6, 30),
        group_by="sku",
        filters="",
        finance_allowed=True,
        organization_id=77,
    )
    second = build_abc_report(
        date_from=date(2026, 6, 1),
        date_to=date(2026, 6, 30),
        group_by="sku",
        filters="",
        finance_allowed=True,
        organization_id=77,
    )

    assert finance_reads["count"] == 2
    assert len(first.rows) == 2
    assert first.rows[0]["abcCode"] == "BB"
    assert first.rows[0]["sku"] == "FBBT_11"
    assert first.rows[0]["productStatus"] == "locomotive"
    assert first.rows[0]["ordersComposite"]["units"] == 12
    assert first.rows[0]["salesComposite"]["units"] == 10
    assert first.rows[0]["adSpendKopecks"] == 20_000
    assert first.rows[0]["wbStockUnits"] == 15
    assert first.filteredSummary.skuCount == 2
    assert first.filteredSummary.locomotiveCount == 1
    assert first.filteredSummary.ordersCount == 14
    assert first.filteredSummary.adSpendKopecks == 80_000
    assert second.rows[0]["abcCode"] == first.rows[0]["abcCode"]


def test_abc_report_prefers_sales_funnel_orders_and_buyouts_for_portal_metrics(monkeypatch):
    def fake_get_source_cache(_organization_id: int, source_key: str, *, slim: bool = False):
        if source_key.startswith("abc_report_"):
            return None
        if source_key == "finance_2026-06-01_2026-06-30":
            return {
                "fetchedAt": "2026-06-30T08:00:00+00:00",
                "aggregates": {
                    "111": {
                        "salesUnits": 10,
                        "sellerRevenueKopecks": 1_000_000,
                        "buyerRevenueKopecks": 1_100_000,
                        "commissionFormulaKopecks": 100_000,
                    }
                },
            }
        if source_key == "period_stats_2026-06-01_2026-06-30":
            return {"aggregates": {"111": {"ordersUnits": 12, "ordersKopecks": 1_200_000, "salesUnits": 10, "revenueKopecks": 1_000_000}}}
        if source_key == "ads_2026-06-01_2026-06-30":
            return {"aggregates": {"111": {"adImpressions": 10, "adClicks": 2, "adSpendKopecks": 50_000}}}
        if source_key == "baskets_2026-06-01_2026-06-30":
            return {
                "aggregates": {
                    "111": {
                        "impressions": 1_000,
                        "openCount": 200,
                        "cartCount": 90,
                        "orderCount": 40,
                        "orderSumKopecks": 4_000_000,
                        "buyoutCount": 25,
                        "buyoutSumKopecks": 2_500_000,
                        "buyoutPct": 62.5,
                    }
                }
            }
        return None

    monkeypatch.setattr("app.wb_reports_sprint_d.get_source_cache", fake_get_source_cache)
    monkeypatch.setattr("app.wb_reports_sprint_d.save_source_cache", lambda _organization_id, _source_key, payload: payload)
    monkeypatch.setattr("app.wb_reports_sprint_d.list_source_cache_ranges_by_prefix", lambda *_args, **_kwargs: [])
    monkeypatch.setattr("app.wb_reports_sprint_d.list_cached_goods", lambda _organization_id: [{"nmID": 111, "vendorCode": "FBBT_11"}])
    monkeypatch.setattr("app.wb_reports_sprint_d.load_runtime_state", lambda _organization_id: {"skuSettingsOverrides": {}, "skuMetaOverrides": {}})
    monkeypatch.setattr("app.wb_reports_sprint_d.load_algorithm_settings", lambda _organization_id: {"taxPct": 0, "otherExpensePricePct": 0, "otherExpensePerSaleRub": 0})

    report = build_abc_report(
        date_from=date(2026, 6, 1),
        date_to=date(2026, 6, 30),
        group_by="sku",
        filters="",
        finance_allowed=True,
        organization_id=77,
    )

    row = report.rows[0]
    assert row["impressions"] == 1_000
    assert row["clicks"] == 200
    assert row["ctrPct"] == 20
    assert row["baskets"] == 90
    assert row["cartCrPct"] == 45
    assert row["ordersComposite"]["units"] == 40
    assert row["ordersComposite"]["kopecks"] == 4_000_000
    assert row["salesComposite"]["units"] == 25
    assert row["salesComposite"]["kopecks"] == 2_500_000
    assert row["buyoutPct"] == 62.5
    assert report.filteredSummary.ordersCount == 40
    assert report.filteredSummary.ordersKopecks == 4_000_000


def test_abc_report_net_profit_uses_full_finance_formula(monkeypatch):
    def fake_get_source_cache(_organization_id: int, source_key: str, *, slim: bool = False):
        if source_key == "finance_2026-06-01_2026-06-30":
            return {
                "aggregates": {
                    "111": {
                        "salesUnits": 2,
                        "sellerRevenueKopecks": 1_000_000,
                        "commissionFormulaKopecks": 100_000,
                        "logisticsKopecks": 50_000,
                        "storageKopecks": 10_000,
                        "acceptanceKopecks": 5_000,
                        "penaltyKopecks": 3_000,
                        "deductionKopecks": 2_000,
                        "additionalPaymentKopecks": 4_000,
                        "acquiringKopecks": 20_000,
                    }
                }
            }
        if source_key == "ads_2026-06-01_2026-06-30":
            return {"aggregates": {"111": {"adSpendKopecks": 30_000}}}
        if source_key == "period_stats_2026-06-01_2026-06-30":
            return {"aggregates": {"111": {"ordersUnits": 2, "ordersKopecks": 1_100_000, "salesUnits": 2, "revenueKopecks": 1_000_000}}}
        if source_key == "baskets_2026-06-01_2026-06-30":
            return {"aggregates": {"111": {"cartCount": 4, "orderCount": 2, "buyoutCount": 2, "buyoutSumKopecks": 1_000_000}}}
        return {"aggregates": {}} if source_key == "stocks_2026-06-01_2026-06-30" else None

    monkeypatch.setattr("app.wb_reports_sprint_d.get_source_cache", fake_get_source_cache)
    monkeypatch.setattr("app.wb_reports_sprint_d.list_source_cache_ranges_by_prefix", lambda *_args, **_kwargs: [])
    monkeypatch.setattr("app.wb_reports_sprint_d.list_cached_goods", lambda _organization_id: [{"nmID": 111, "vendorCode": "FBBT_11"}])
    monkeypatch.setattr(
        "app.wb_reports_sprint_d.load_runtime_state",
        lambda _organization_id: {"skuSettingsOverrides": {"FBBT_11": {"cogsKopecks": 200_000}}, "skuMetaOverrides": {}},
    )
    monkeypatch.setattr("app.wb_reports_sprint_d.load_algorithm_settings", lambda _organization_id: {"taxPct": 6, "otherExpensePricePct": 1, "otherExpensePerSaleKopecks": 1_000})

    report = build_abc_report(
        date_from=date(2026, 6, 1),
        date_to=date(2026, 6, 30),
        group_by="sku",
        filters="",
        finance_allowed=True,
        organization_id=77,
    )

    row = report.rows[0]
    assert row["netTotalKopecks"] == 314_000
    assert row["acquiringKopecks"] == 20_000
    assert row["acceptanceKopecks"] == 5_000
    assert row["additionalPaymentKopecks"] == 4_000
    assert report.filteredSummary.profitKopecks == 314_000


def test_abc_report_totals_include_baskets_only_snapshot_rows(monkeypatch):
    def fake_get_source_cache(_organization_id: int, source_key: str, *, slim: bool = False):
        if source_key == "finance_2026-06-01_2026-06-30":
            return {"aggregates": {"111": {"salesUnits": 1, "sellerRevenueKopecks": 100_000}}}
        if source_key == "baskets_2026-06-01_2026-06-30":
            return {
                "aggregates": {
                    "111": {"cartCount": 10, "orderCount": 2, "buyoutCount": 1},
                    "222": {"cartCount": 1_000, "orderCount": 0, "buyoutCount": 0},
                }
            }
        return {"aggregates": {}} if source_key in {"period_stats_2026-06-01_2026-06-30", "ads_2026-06-01_2026-06-30"} else None

    monkeypatch.setattr("app.wb_reports_sprint_d.get_source_cache", fake_get_source_cache)
    monkeypatch.setattr("app.wb_reports_sprint_d.list_source_cache_ranges_by_prefix", lambda *_args, **_kwargs: [])
    monkeypatch.setattr("app.wb_reports_sprint_d.list_cached_goods", lambda _organization_id: [{"nmID": 111, "vendorCode": "SKU_111"}, {"nmID": 222, "vendorCode": "SKU_222"}])
    monkeypatch.setattr("app.wb_reports_sprint_d.load_runtime_state", lambda _organization_id: {"skuSettingsOverrides": {}, "skuMetaOverrides": {}})
    monkeypatch.setattr("app.wb_reports_sprint_d.load_algorithm_settings", lambda _organization_id: {"taxPct": 0, "otherExpensePricePct": 0, "otherExpensePerSaleRub": 0})

    report = build_abc_report(
        date_from=date(2026, 6, 1),
        date_to=date(2026, 6, 30),
        group_by="sku",
        filters="",
        finance_allowed=True,
        organization_id=77,
    )

    assert sum(row["baskets"] for row in report.rows) == 1_010
    assert {row["nmId"] for row in report.rows} == {111, 222}


def test_abc_report_keeps_funnel_opens_separate_when_impressions_missing(monkeypatch):
    def fake_get_source_cache(_organization_id: int, source_key: str, *, slim: bool = False):
        if source_key.startswith("abc_report_"):
            return None
        if source_key == "finance_2026-06-01_2026-06-30":
            return {
                "aggregates": {
                    "111": {
                        "salesUnits": 10,
                        "sellerRevenueKopecks": 1_000_000,
                    }
                }
            }
        if source_key == "ads_2026-06-01_2026-06-30":
            return {"aggregates": {"111": {"adImpressions": 75_835, "adClicks": 6_154, "adSpendKopecks": 50_000}}}
        if source_key == "baskets_2026-06-01_2026-06-30":
            return {
                "aggregates": {
                    "111": {
                        "openCount": 38_417,
                        "cartCount": 4_267,
                        "orderCount": 1_495,
                        "orderSumKopecks": 2_442_024_00,
                    }
                }
            }
        return None

    monkeypatch.setattr("app.wb_reports_sprint_d.get_source_cache", fake_get_source_cache)
    monkeypatch.setattr("app.wb_reports_sprint_d.save_source_cache", lambda _organization_id, _source_key, payload: payload)
    monkeypatch.setattr("app.wb_reports_sprint_d.list_source_cache_ranges_by_prefix", lambda *_args, **_kwargs: [])
    monkeypatch.setattr("app.wb_reports_sprint_d.list_cached_goods", lambda _organization_id: [{"nmID": 111, "vendorCode": "FBBT_11"}])
    monkeypatch.setattr("app.wb_reports_sprint_d.load_runtime_state", lambda _organization_id: {"skuSettingsOverrides": {}, "skuMetaOverrides": {}})
    monkeypatch.setattr("app.wb_reports_sprint_d.load_algorithm_settings", lambda _organization_id: {"taxPct": 0, "otherExpensePricePct": 0, "otherExpensePerSaleRub": 0})

    report = build_abc_report(
        date_from=date(2026, 6, 1),
        date_to=date(2026, 6, 30),
        group_by="sku",
        filters="",
        finance_allowed=True,
        organization_id=77,
    )

    row = report.rows[0]
    assert row["impressions"] == 0
    assert row["clicks"] == 38_417
    assert row["ctrPct"] == 0
    assert row["baskets"] == 4_267
    assert row["ordersComposite"]["units"] == 1_495


def test_abc_report_uses_covering_repricer_daily_cache(monkeypatch):
    source_cache: dict[str, dict] = {}

    def fake_get_source_cache(_organization_id: int, source_key: str, *, slim: bool = False):
        if source_key.startswith("abc_report_"):
            return None
        if source_key == "wb_sync_status":
            return {
                "dateFrom": "2026-06-01",
                "dateTo": "2026-07-08",
                "periodDays": 38,
                "periodCacheSuffix": "2026-06-01_2026-07-08",
            }
        if source_key == "finance_2026-06-01_2026-07-08":
            return {
                "fetchedAt": "2026-07-08T08:00:00+00:00",
                "dateFrom": "2026-06-01",
                "dateTo": "2026-07-08",
                "periodDays": 38,
                "periodCacheSuffix": "2026-06-01_2026-07-08",
                "dailyAggregates": {
                    "2026-06-01": {
                        "111": {"salesUnits": 99, "sellerRevenueKopecks": 9_900_000},
                    },
                    "2026-06-02": {
                        "111": {
                            "salesUnits": 3,
                            "sellerRevenueKopecks": 300_000,
                            "buyerRevenueKopecks": 330_000,
                            "commissionFormulaKopecks": 30_000,
                            "logisticsKopecks": 15_000,
                            "storageKopecks": 3_000,
                        },
                    },
                    "2026-07-08": {
                        "111": {
                            "salesUnits": 2,
                            "sellerRevenueKopecks": 200_000,
                            "buyerRevenueKopecks": 220_000,
                            "commissionFormulaKopecks": 20_000,
                            "logisticsKopecks": 10_000,
                            "storageKopecks": 2_000,
                        },
                    },
                },
            }
        if source_key == "period_stats_2026-06-01_2026-07-08":
            return {
                "dateFrom": "2026-06-01",
                "dateTo": "2026-07-08",
                "dailyAggregates": {
                    "2026-06-02": {"111": {"ordersUnits": 4, "ordersKopecks": 400_000, "baskets": 7}},
                    "2026-07-08": {"111": {"ordersUnits": 3, "ordersKopecks": 300_000, "baskets": 5}},
                },
            }
        return source_cache.get(source_key)

    monkeypatch.setattr("app.wb_reports_sprint_d.get_source_cache", fake_get_source_cache)
    monkeypatch.setattr("app.wb_reports_sprint_d.save_source_cache", lambda _organization_id, key, payload: source_cache.setdefault(key, payload))
    monkeypatch.setattr(
        "app.wb_reports_sprint_d.list_cached_goods",
        lambda _organization_id: [{"nmID": 111, "vendorCode": "FBBT_11", "brand": "Satorna", "subjectName": "Футболки"}],
    )
    monkeypatch.setattr(
        "app.wb_reports_sprint_d.load_runtime_state",
        lambda _organization_id: {
            "skuSettingsOverrides": {"FBBT_11": {"cogsKopecks": 10_000}},
            "skuMetaOverrides": {"FBBT_11": {"managerId": "maria", "status": "locomotive"}},
        },
    )
    monkeypatch.setattr(
        "app.wb_reports_sprint_d.load_algorithm_settings",
        lambda _organization_id: {"taxPct": 0, "otherExpensePricePct": 0, "otherExpensePerSaleRub": 0},
    )

    report = build_abc_report(
        date_from=date(2026, 6, 2),
        date_to=date(2026, 7, 8),
        group_by="sku",
        filters="",
        finance_allowed=True,
        organization_id=77,
    )

    assert len(report.rows) == 1
    assert report.rows[0]["sku"] == "FBBT_11"
    assert report.rows[0]["salesComposite"]["units"] == 5
    assert report.rows[0]["salesComposite"]["kopecks"] == 500_000
    assert report.rows[0]["ordersComposite"]["units"] == 7
    assert report.filteredSummary.skuCount == 1


def test_abc_report_without_cache_returns_empty_backend_state_not_static_summary(monkeypatch):
    monkeypatch.setattr("app.wb_reports_sprint_d.get_source_cache", lambda *_args, **_kwargs: {})
    monkeypatch.setattr("app.wb_reports_sprint_d.save_source_cache", lambda *_args, **_kwargs: None)
    monkeypatch.setattr("app.wb_reports_sprint_d.list_cached_goods", lambda _organization_id: [])

    report = build_abc_report(
        date_from=date(2026, 6, 2),
        date_to=date(2026, 7, 8),
        group_by="sku",
        filters="",
        finance_allowed=True,
        organization_id=77,
    )

    assert report.rows == []
    assert report.filteredSummary.skuCount == 0
    assert report.filteredSummary.ordersKopecks == 0
    assert report.filteredSummary.profitKopecks == 0
    assert report.filteredSummary.adSpendKopecks == 0
    assert report.sourceStatus == "partial"


def test_bff_abc_returns_sku_rows_not_summary_only(monkeypatch):
    def fake_build_abc_report(**_kwargs):
        report = build_abc_report(
            date_from=date(2026, 6, 1),
            date_to=date(2026, 6, 30),
            group_by="sku",
            filters="",
            finance_allowed=True,
            organization_id=None,
        )
        payload = report.model_dump(mode="python")
        payload["rows"] = [
            {
                "sku": "FBBT_11",
                "nmId": 111,
                "productStatus": "locomotive",
                "abcCode": "AA",
                "ordersComposite": {"units": 12, "kopecks": 1_200_000, "deltaPct": 0},
                "salesComposite": {"units": 10, "kopecks": 1_000_000, "deltaPct": 0},
                "netTotalKopecks": 790_000,
                "marginPct": 79,
                "adSpendKopecks": 20_000,
                "wbStockUnits": 15,
            }
        ]
        return type(report).model_validate(payload)

    monkeypatch.setattr("app.routers.wb_reports_bff.build_abc_report", fake_build_abc_report)

    api = client()
    response = api.get("/api/wb/reports/abc", headers=auth_headers(api, "viewer"))

    assert response.status_code == 200
    payload = response.json()
    assert payload["meta"]["id"] == "abc"
    assert payload["rows"][0]["sku"] == "FBBT_11"
    assert payload["rows"][0]["abcCode"] == "AA"
    assert payload["columns"][0]["key"] == "sku"


def test_bff_abc_uses_repricer_rows_when_report_cache_is_empty(monkeypatch):
    def fake_build_abc_report(**_kwargs):
        return build_abc_report(
            date_from=date(2026, 6, 1),
            date_to=date(2026, 6, 30),
            group_by="sku",
            filters="",
            finance_allowed=True,
            organization_id=77,
        )

    monkeypatch.setattr("app.routers.wb_reports_bff.build_abc_report", fake_build_abc_report)
    monkeypatch.setattr(
        "app.routers.wb_reports_bff._repricer_rows_for_abc_report",
        lambda **_kwargs: [
            {
                "meta": {
                    "articleId": "FBBT_11",
                    "nmId": 111,
                    "name": "Футболка",
                    "brand": "Vella",
                    "subject": "Футболки",
                    "managerId": "maria",
                },
                "analytics": {
                    "abcCode": "BA",
                    "productStatus": "locomotive",
                    "ordersUnits": 7,
                    "revenueKopecks": 700_000,
                    "salesUnits": 5,
                    "sellerRevenueKopecks": 500_000,
                    "netProfitKopecks": 180_000,
                    "marginPct": 36,
                    "adSpendKopecks": 20_000,
                    "wbStockUnits": 12,
                    "baskets": 15,
                    "financeState": "ok",
                },
            }
        ],
        raising=False,
    )

    api = client()
    response = api.get(
        "/api/wb/reports/abc?preset=custom&from=2026-06-02&to=2026-07-08&groupBy=sku",
        headers=auth_headers(api, "viewer"),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["rows"][0]["sku"] == "FBBT_11"
    assert payload["rows"][0]["abcCode"] == "BA"
    assert payload["rows"][0]["ordersComposite"]["units"] == 7
    assert payload["rows"][0]["salesComposite"]["kopecks"] == 500_000
    assert payload["filteredSummary"]["skuCount"] == 1
    assert payload["filteredSummary"]["ordersCount"] == 7
