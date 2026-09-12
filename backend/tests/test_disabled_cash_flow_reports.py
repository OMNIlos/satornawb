"""Disabled 1C must not enqueue work or turn missing expenses into profit."""

from copy import deepcopy
from datetime import date
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app import repricer_tasks
from app.main import create_app
from app.report_rules.store import _default as default_report_rules
from app.routers import one_c_cash_flow, wb_reports_bff as reports
from tests.auth_helpers import auth_headers
from tests.test_sprint_d_reports import _signed_pnl_source


START, END = date(2026, 5, 1), date(2026, 5, 28)
PARAMS = {"preset": "custom", "from": str(START), "to": str(END)}


@pytest.fixture
def disabled_source(monkeypatch, tmp_path):
    monkeypatch.setenv("VELLA_1C_ENABLED", "false")
    jobs_path = tmp_path / "cash-flow.json"
    monkeypatch.setattr(one_c_cash_flow, "JOBS_PATH", jobs_path)
    cache = {}
    monkeypatch.setattr(reports, "get_source_cache", lambda org, key, **kw: deepcopy(cache.get((org, key))))
    monkeypatch.setattr(reports, "save_source_cache", lambda org, key, value: cache.__setitem__((org, key), deepcopy(value)))
    monkeypatch.setattr(reports, "list_source_cache_by_prefix", lambda org, prefix, **kw: [
        {**deepcopy(value), "sourceKey": key} for (owner, key), value in cache.items()
        if owner == org and key.startswith(prefix)
    ])
    monkeypatch.setattr(reports, "load_active_profile", default_report_rules)
    monkeypatch.setattr(repricer_tasks, "_report_snapshot_sources_ready", lambda *a, **kw: (True, []))
    return jobs_path, cache


def test_disabled_cash_flow_preserves_existing_jobs_and_does_not_create_new_ones(disabled_source, monkeypatch):
    jobs_path, _ = disabled_source
    monkeypatch.setenv("VELLA_1C_ENABLED", "true")
    existing = one_c_cash_flow.get_cash_flow_for_period(organization_id=1, period_from=START, period_to=END)
    assert existing["status"] == "pending"
    before = jobs_path.read_bytes()
    monkeypatch.setenv("VELLA_1C_ENABLED", "false")
    for organization_id in (1, 2):
        assert one_c_cash_flow.get_cash_flow_for_period(
            organization_id=organization_id, period_from=START, period_to=END
        ) == {"status": "disabled"}
    assert jobs_path.read_bytes() == before


@pytest.mark.parametrize("source", ["operational", "financial"])
@pytest.mark.parametrize("finance_allowed", [False, True])
def test_disabled_1c_builds_partial_wb_pnl_without_profit_or_retries(disabled_source, monkeypatch, source, finance_allowed):
    jobs_path, cache = disabled_source
    _signed_pnl_source(monkeypatch, 0)
    result = repricer_tasks.build_report_for_org.run(
        1, "synthetic-user", "pnl", str(START), str(END), "sku", source, finance_allowed, None,
        source_refresh={"state": "completed", "steps": []},
    )
    assert result["state"] == "completed"
    assert result["kind"] == "report_source_refresh"
    assert not jobs_path.exists()

    key = reports._report_cache_key("pnl", START, END, "sku", source, organization_id=1, finance_allowed=finance_allowed)
    report = cache[1, key]["report"]
    assert len(report["rows"]) == 1
    row = report["rows"][0]
    assert row["revenueKopecks"] == 10_000
    assert row["netProfitKopecks"] is row["overheadKopecks"] is row["marginPct"] is None
    assert row["sourceStatus"] == "partial"
    assert report["meta"]["freshnessState"] == "pending_financial"
    assert report["blockerIds"] == ["ONE_C_DISABLED"]
    assert report["financialConfirmationStatus"] == "pending"
    assert "1С" in report["warning"]
    assert report["cashFlow"] == ({"status": "disabled"} if finance_allowed else None)
    assert {kpi["id"]: kpi["value"] for kpi in report["kpis"] if kpi["id"] != "rules_profile"} == {
        "revenue": "10000", "net_profit": "—", "margin_pct": "—",
    }
    assert report["chart"]["points"] == []
    api = TestClient(create_app())
    response = api.get("/api/wb/reports/pnl", params={**PARAMS, "source": source},
                       headers=auth_headers(api, "finance_viewer" if finance_allowed else "viewer"))
    assert response.status_code == 200
    assert response.json()["rows"] == report["rows"]
    assert response.json()["cashFlow"] == report["cashFlow"]


@pytest.mark.parametrize("params", [PARAMS, {}])
def test_old_expenses_cache_cannot_restore_waiting_for_disabled_source(disabled_source, params):
    _, cache = disabled_source
    key = reports._report_cache_key("expenses", START, END, "sku", "operational")
    old = {
        "report": {"rows": [], "cashFlow": {"status": "pending", "job_id": "old-job"}},
        "dateFrom": str(START), "dateTo": str(END), "completedAt": reports._utc_now_iso(),
    }
    cache[1, key] = deepcopy(old)
    api = TestClient(create_app())
    response = api.get("/api/wb/reports/expenses/latest-cache", params=params,
                       headers=auth_headers(api, "finance_viewer"))
    assert response.status_code == 404
    assert cache[1, key] == old


@pytest.mark.parametrize("report_id", ["pnl", "expenses"])
@pytest.mark.parametrize("was_enabled", [False, True])
def test_current_version_cache_is_rejected_when_1c_mode_changes(disabled_source, monkeypatch, report_id, was_enabled):
    _, cache = disabled_source
    finance_allowed = report_id == "expenses"
    version = reports.PNL_REPORT_PAYLOAD_VERSION if report_id == "pnl" else reports.EXPENSES_REPORT_PAYLOAD_VERSION
    report = {"cacheVersion": version, "rows": []}
    if report_id == "pnl":
        report["blockerIds"] = [] if was_enabled else ["ONE_C_DISABLED"]
    report["cashFlow"] = {"status": "ready" if was_enabled else "disabled"} if finance_allowed else None
    key = reports._report_cache_key(report_id, START, END, "sku", "operational", organization_id=1, finance_allowed=finance_allowed)
    cached = {"report": report, "dateFrom": str(START), "dateTo": str(END), "completedAt": reports._utc_now_iso()}
    cache[1, key] = deepcopy(cached)
    api = TestClient(create_app())
    headers = auth_headers(api, "finance_viewer" if finance_allowed else "viewer")
    monkeypatch.setenv("VELLA_1C_ENABLED", str(was_enabled).lower())
    for params in (PARAMS, {}):
        assert api.get(f"/api/wb/reports/{report_id}/latest-cache", params=params, headers=headers).status_code == 200
    monkeypatch.setenv("VELLA_1C_ENABLED", str(not was_enabled).lower())
    for params in (PARAMS, {}):
        assert api.get(f"/api/wb/reports/{report_id}/latest-cache", params=params, headers=headers).status_code == 404
    enqueued = []
    monkeypatch.setattr(reports, "_report_daily_sources_ready", lambda *a, **kw: (True, []))
    monkeypatch.setattr(repricer_tasks.build_report_for_org, "delay", lambda *a: enqueued.append(a) or SimpleNamespace(id="synthetic-rebuild"))
    response = api.post(f"/api/wb/reports/{report_id}/jobs", params=PARAMS, headers=headers)
    assert response.status_code == 200
    assert response.json()["state"] == "queued"
    assert len(enqueued) == 1
    assert cache[1, key] == cached


def test_disabled_expenses_are_unavailable_not_ready_zeroes(disabled_source):
    jobs_path, cache = disabled_source
    api = TestClient(create_app())
    response = api.get("/api/wb/reports/expenses", params=PARAMS, headers=auth_headers(api, "finance_viewer"))
    assert response.status_code == 200
    report = response.json()
    assert report["cashFlow"] == {"status": "disabled"}
    assert report["rows"] == report["chart"]["points"] == []
    assert report["meta"]["freshnessState"] == "pending_financial"
    assert report["financialConfirmationStatus"] == "pending_financial"
    assert "отключена" in report["warning"]
    assert {kpi["id"]: kpi["value"] for kpi in report["kpis"]} == {
        "expense_rows": "—", "operational_expenses": "—", "cash_flow_status": "disabled",
    }
    assert report["reportJob"]["state"] != "waiting_1c"
    assert "готов" not in report["reportJob"]["label"].lower()
    result = repricer_tasks.build_report_for_org.run(
        1, "synthetic-user", "expenses", str(START), str(END), "sku", "operational", True, None,
    )
    assert result["state"] == "completed"
    key = reports._report_cache_key("expenses", START, END, "sku", "operational", organization_id=1, finance_allowed=True)
    assert [kpi for kpi in cache[1, key]["report"]["kpis"] if kpi["id"] != "rules_profile"] == report["kpis"]
    assert not jobs_path.exists()
