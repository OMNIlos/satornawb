"""Report payload caches must preserve the builder's finance permission scope."""

from copy import deepcopy
from datetime import date
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app import repricer_tasks
from app.main import create_app
from app.routers import wb_reports_bff as reports
from tests.auth_helpers import auth_headers

START, END = date(2026, 8, 17), date(2026, 8, 23)
PARAMS = {"preset": "custom", "from": START.isoformat(), "to": END.isoformat()}
PRIVATE_CASH_FLOW = {
    "status": "ready",
    "data": {
        "rows": [
            {
                "article": "synthetic-private-rent",
                "type": "expense",
                "operationalExpense": True,
                "amountKopecks": 164_000,
            }
        ],
        "totals": {"operationalExpenseKopecks": 164_000},
        "balances": {"closingBalanceKopecks": 130_000},
    },
}


@pytest.fixture
def cache(monkeypatch):
    entries = {}
    monkeypatch.setattr(
        reports,
        "get_source_cache",
        lambda org, key, **kw: deepcopy(entries.get((org, key))),
    )
    monkeypatch.setattr(
        reports,
        "save_source_cache",
        lambda org, key, value: entries.__setitem__((org, key), deepcopy(value)),
    )
    monkeypatch.setattr(
        reports,
        "list_source_cache_by_prefix",
        lambda org, prefix, **kw: [
            {**deepcopy(value), "sourceKey": key}
            for (owner, key), value in reversed(list(entries.items()))
            if owner == org and key.startswith(prefix)
        ],
    )
    monkeypatch.setattr(
        repricer_tasks, "_report_snapshot_sources_ready", lambda *args, **kw: (True, [])
    )
    monkeypatch.setattr(
        reports, "get_cash_flow_for_period", lambda **kw: deepcopy(PRIVATE_CASH_FLOW)
    )

    def build_report(**kwargs):
        row = {
            "label": "SKU-1",
            "revenueKopecks": 100_000,
            "overheadKopecks": 12_345 if kwargs["finance_allowed"] else None,
        }
        return SimpleNamespace(
            blockerIds=[],
            sourceStatus="fresh",
            groupBy="sku",
            totals=SimpleNamespace(
                revenueKopecks=100_000, netProfitKopecks=20_000, marginPct=20
            ),
            rows=[
                SimpleNamespace(
                    label="SKU-1", marginPct=20, model_dump=lambda **kw: deepcopy(row)
                )
            ],
        )

    monkeypatch.setattr(reports, "build_pnl_report", build_report)
    return entries


@pytest.mark.parametrize(
    "endpoint,params",
    [
        ("/api/wb/reports/pnl", PARAMS),
        ("/api/wb/reports/pnl/latest-cache", {}),
        ("/api/wb/reports/pnl/latest-cache", PARAMS),
    ],
)
@pytest.mark.parametrize("build_order", [(True, False), (False, True)])
def test_worker_and_readers_keep_both_permission_variants(
    cache, endpoint, params, build_order
):
    for finance_allowed in build_order:
        result = repricer_tasks.build_report_for_org.run(
            1,
            "synthetic-user",
            "pnl",
            START.isoformat(),
            END.isoformat(),
            "sku",
            "operational",
            finance_allowed,
            None,
        )
        assert result["state"] == "completed"
    api = TestClient(create_app())
    for profile, expected in (("viewer", None), ("finance_viewer", 12_345)):
        response = api.get(endpoint, params=params, headers=auth_headers(api, profile))
        assert response.status_code == 200
        assert response.json()["rows"][0]["overheadKopecks"] == expected
        assert response.json()["cashFlow"] == (
            PRIVATE_CASH_FLOW if expected is not None else None
        )
    assert (
        len([key for org, key in cache if key.startswith("reports_payload_pnl_")]) == 2
    )


@pytest.mark.parametrize(
    "endpoint,params,status",
    [
        ("/api/wb/reports/pnl", PARAMS, 200),
        ("/api/wb/reports/pnl/latest-cache", {}, 404),
        ("/api/wb/reports/pnl/latest-cache", PARAMS, 404),
    ],
)
@pytest.mark.parametrize(
    "legacy_prefix,legacy_suffix,version",
    [("", "", "v1"), ("", "_nofinance", "v1"), ("v2_", "_nofinance", "v2")],
)
def test_reader_does_not_reuse_old_unscoped_financial_payload(
    cache, endpoint, params, status, legacy_prefix, legacy_suffix, version
):
    # Older endpoints accepted arbitrary source strings; a suffix alone is not provenance.
    key = f"reports_payload_pnl_{legacy_prefix}{START}_{END}_sku_operational{legacy_suffix}"
    cache[1, key] = {
        "completedAt": reports._utc_now_iso(),
        "dateFrom": str(START),
        "dateTo": str(END),
        "report": {
            "cacheVersion": version,
            "rows": [
                {
                    "label": "PRIVATE",
                    "overheadKopecks": None if version == "v2" else 12_345,
                }
            ],
            "cashFlow": deepcopy(PRIVATE_CASH_FLOW),
        },
    }
    api = TestClient(create_app())
    response = api.get(endpoint, params=params, headers=auth_headers(api, "viewer"))
    assert response.status_code == status
    assert not response.json().get("rows")


def test_exact_cache_writer_uses_finance_scope(cache):
    for finance_allowed in (True, False):
        reports._save_exact_report_payload_cache(
            organization_id=1,
            report_id="pnl",
            date_from=START,
            date_to=END,
            group_by="sku",
            source="financial",
            finance_allowed=finance_allowed,
            report={
                "cacheVersion": reports.PNL_REPORT_PAYLOAD_VERSION,
                "rows": [{"overheadKopecks": 12_345 if finance_allowed else None}],
            },
        )
    assert len(cache) == 2
    for finance_allowed, expected in ((True, 12_345), (False, None)):
        latest = reports._latest_report_payload_cache(
            organization_id=1,
            report_id="pnl",
            group_by="sku",
            source="financial",
            finance_allowed=finance_allowed,
        )
        assert latest is not None
        assert latest[0]["report"]["rows"][0]["overheadKopecks"] == expected


@pytest.mark.parametrize(
    "profile,finance_allowed", [("viewer", False), ("finance_viewer", True)]
)
def test_job_endpoints_select_the_callers_permission_cache(
    cache, monkeypatch, profile, finance_allowed
):
    repricer_tasks.build_report_for_org.run(
        1,
        "synthetic-user",
        "pnl",
        str(START),
        str(END),
        "sku",
        "operational",
        not finance_allowed,
        None,
    )
    job_key = reports._report_job_cache_key("pnl", START, END, "sku", "operational")
    cache.pop((1, job_key))
    monkeypatch.setattr(
        reports, "_report_daily_sources_ready", lambda *args, **kw: (True, [])
    )
    enqueued = []

    def enqueue(*args):
        enqueued.append(args)
        return SimpleNamespace(id="synthetic-task")

    monkeypatch.setattr(repricer_tasks.build_report_for_org, "delay", enqueue)
    api = TestClient(create_app())
    headers = auth_headers(api, profile)
    status = api.get("/api/wb/reports/pnl/jobs", params=PARAMS, headers=headers)
    assert status.status_code == 200
    assert status.json()["state"] == "idle"
    started = api.post("/api/wb/reports/pnl/jobs", params=PARAMS, headers=headers)
    assert started.status_code == 200
    assert started.json()["state"] == "queued"
    assert started.json()["cashFlow"] == (
        PRIVATE_CASH_FLOW if finance_allowed else None
    )
    assert len(enqueued) == 1
    assert enqueued[0][-2:] == (finance_allowed, None)


@pytest.mark.parametrize(
    "method,path",
    [
        ("GET", "/reports/cash-flow"),
        ("GET", "/api/wb/reports/cash-flow"),
        ("GET", "/api/wb/reports/expenses"),
        ("GET", "/api/wb/reports/expenses/latest-cache"),
        ("GET", "/api/wb/reports/expenses/jobs"),
        ("POST", "/api/wb/reports/expenses/jobs"),
    ],
)
@pytest.mark.parametrize("profile", ["viewer", "finance_viewer"])
def test_cash_flow_and_expenses_require_finance_access(
    cache, monkeypatch, method, path, profile
):
    reports._save_exact_report_payload_cache(
        organization_id=1,
        report_id="expenses",
        date_from=START,
        date_to=END,
        group_by="sku",
        source="operational",
        report={
            "rows": [{"amountKopecks": 164_000}],
            "cashFlow": deepcopy(PRIVATE_CASH_FLOW),
        },
    )
    reads = []

    def read_cash_flow(**kwargs):
        reads.append(kwargs)
        return deepcopy(PRIVATE_CASH_FLOW)

    monkeypatch.setattr(reports, "get_cash_flow_for_period", read_cash_flow)
    api = TestClient(create_app())
    response = api.request(
        method, path, params=PARAMS, headers=auth_headers(api, profile)
    )
    assert response.status_code == (403 if profile == "viewer" else 200)
    if profile == "viewer":
        assert "finance:read" in response.text
        assert (
            "164000" not in response.text
            and "synthetic-private-rent" not in response.text
        )
        assert reads == []
    elif not path.endswith("/jobs"):
        actual = response.json() if "cash-flow" in path else response.json()["cashFlow"]
        assert actual == PRIVATE_CASH_FLOW


@pytest.fixture
def abc_cache(cache, monkeypatch):
    monkeypatch.setattr(reports, "_abc_economics_version", lambda org: "cafef00d")

    def build_abc(**kwargs):
        assert (kwargs["organization_id"], kwargs["date_from"], kwargs["date_to"]) == (1, START, END)
        allowed = kwargs["finance_allowed"]
        return SimpleNamespace(
            groupBy="sku", sourceStatus="fresh" if allowed else "partial", confidence="high",
            blockerIds=[] if allowed else ["WB_ABC_FINANCE_FORBIDDEN"], sourceEvidence=[],
            rows=[{
                "sku": "SYNTHETIC-ABC", "nmId": 101,
                "ordersComposite": {"units": 1, "kopecks": 90_000},
                "commissionKopecks": 12_345 if allowed else None,
                "netTotalKopecks": 45_678 if allowed else None,
            }],
            filteredSummary=SimpleNamespace(model_dump=lambda **kw: {
                "skuCount": 1, "ordersCount": 1, "ordersKopecks": 90_000,
                "profitKopecks": 45_678 if allowed else None,
            }),
        )

    monkeypatch.setattr(reports, "build_abc_report", build_abc)
    return cache


@pytest.mark.parametrize("build_order", [(True, False), (False, True)])
@pytest.mark.parametrize("suffix,params", [("", PARAMS), ("/latest-cache", PARAMS), ("/latest-cache", {})])
def test_abc_worker_and_readers_keep_both_permission_variants(abc_cache, build_order, suffix, params):
    for allowed in build_order:
        result = repricer_tasks.build_report_for_org.run(
            1, "synthetic-user", "abc", str(START), str(END), "sku", "operational", allowed, None
        )
        assert result["state"] == "completed"
    api = TestClient(create_app())
    for profile, expected in (("viewer", None), ("finance_viewer", 12_345)):
        response = api.get(f"/api/wb/reports/abc{suffix}", params=params, headers=auth_headers(api, profile))
        assert response.status_code == 200
        assert response.json()["rows"][0]["sku"] == "SYNTHETIC-ABC"
        assert response.json()["rows"][0].get("commissionKopecks") == expected
        assert ("WB_ABC_FINANCE_FORBIDDEN" in response.json()["blockerIds"]) == (expected is None)
    assert len([key for org, key in abc_cache if key.startswith("reports_payload_abc_")]) == 2


@pytest.mark.parametrize("build_order", [(True, False), (False, True)])
def test_abc_http_writers_keep_both_permission_variants(abc_cache, monkeypatch, build_order):
    monkeypatch.setattr(reports, "_report_daily_sources_ready", lambda *args, **kw: (True, []))
    api = TestClient(create_app())
    for allowed in build_order:
        response = api.get(
            "/api/wb/reports/abc", params=PARAMS,
            headers=auth_headers(api, "finance_viewer" if allowed else "viewer"),
        )
        assert response.status_code == 200
        assert response.json()["rows"][0].get("commissionKopecks") == (12_345 if allowed else None)
    assert len([key for org, key in abc_cache if key.startswith("reports_payload_abc_")]) == 2


def test_abc_exact_writer_and_latest_lookup_keep_finance_scope(abc_cache):
    for allowed in (True, False):
        reports._save_exact_report_payload_cache(
            organization_id=1, report_id="abc", date_from=START, date_to=END,
            group_by="sku", source="operational", finance_allowed=allowed,
            report={"cacheVersion": reports.ABC_REPORT_PAYLOAD_VERSION,
                    "rows": [{"commissionKopecks": 12_345 if allowed else None}]},
        )
    assert len(abc_cache) == 2
    for allowed in (True, False):
        latest = reports._latest_report_payload_cache(
            organization_id=1, report_id="abc", group_by="sku", source="operational", finance_allowed=allowed
        )
        assert latest is not None
        assert latest[0]["report"]["rows"][0]["commissionKopecks"] == (12_345 if allowed else None)


@pytest.mark.parametrize("legacy_suffix", ["", "_nofinance"])
@pytest.mark.parametrize("suffix,params,status", [("", PARAMS, 200), ("/latest-cache", PARAMS, 404), ("/latest-cache", {}, 404)])
def test_abc_readers_reject_old_unscoped_finance_cache(abc_cache, monkeypatch, legacy_suffix, suffix, params, status):
    # An arbitrary old source ending in _nofinance is not permission provenance.
    key = f"reports_payload_abc_v16_cafef00d_org1_{START}_{END}_sku_operational{legacy_suffix}"
    abc_cache[1, key] = {
        "completedAt": reports._utc_now_iso(), "dateFrom": str(START), "dateTo": str(END),
        "report": {"cacheVersion": "v16", "economicsVersion": "cafef00d",
                   "rows": [{"sku": "PRIVATE-OLD", "commissionKopecks": 12_345}]},
    }
    monkeypatch.setattr(reports, "_report_daily_sources_ready", lambda *args, **kw: (False, ["finance"]))
    api = TestClient(create_app())
    response = api.get(f"/api/wb/reports/abc{suffix}", params=params, headers=auth_headers(api, "viewer"))
    assert response.status_code == status
    assert not response.json().get("rows")
    assert "PRIVATE-OLD" not in response.text


@pytest.mark.parametrize("allowed", [True, False])
def test_abc_job_endpoints_select_the_callers_permission_cache(abc_cache, monkeypatch, allowed):
    repricer_tasks.build_report_for_org.run(
        1, "synthetic-user", "abc", str(START), str(END), "sku", "operational", not allowed, None
    )
    abc_cache.pop((1, reports._report_job_cache_key("abc", START, END, "sku", "operational")))
    monkeypatch.setattr(reports, "_report_daily_sources_ready", lambda *args, **kw: (True, []))
    enqueued = []

    def enqueue(*args):
        enqueued.append(args)
        return SimpleNamespace(id="synthetic-task")

    monkeypatch.setattr(repricer_tasks.build_report_for_org, "delay", enqueue)
    api = TestClient(create_app())
    headers = auth_headers(api, "finance_viewer" if allowed else "viewer")
    status = api.get("/api/wb/reports/abc/jobs", params=PARAMS, headers=headers)
    assert status.status_code == 200
    assert status.json()["state"] == "idle"
    started = api.post("/api/wb/reports/abc/jobs", params=PARAMS, headers=headers)
    assert started.status_code == 200
    assert started.json()["state"] == "queued"
    assert len(enqueued) == 1 and enqueued[0][-2:] == (allowed, None)


def test_scheduled_abc_snapshot_is_saved_in_finance_scope(abc_cache, monkeypatch):
    monkeypatch.setattr("app.routers.wb_repricer_bff._build_repricer_sku_snapshot", lambda *args, **kw: {})
    monkeypatch.setattr(
        repricer_tasks, "_report_snapshot_sources_ready",
        lambda org, sources, *args: (sources == ("period-stats", "finance", "ads", "baskets"), []),
    )
    for name in ("build_cached_wb_reports_sources_snapshot", "_build_digest_ads_snapshot", "_build_digest_funnel_snapshot", "build_plan_fact_report"):
        monkeypatch.setattr(reports, name, lambda *args, **kw: None)
    monkeypatch.setattr(reports, "_build_digest_payload", lambda *args: {})
    monkeypatch.setattr(repricer_tasks, "_digest_report_summary", lambda *args: {})
    save_exact = reports._save_exact_report_payload_cache

    def save(**kwargs):
        if kwargs["report_id"] == "abc":
            assert kwargs.get("finance_allowed") is True
        return save_exact(**kwargs)

    monkeypatch.setattr(reports, "_save_exact_report_payload_cache", save)
    profile = SimpleNamespace(period_days=7, date_from=START, date_to=END, sources=("period-stats",), window_kind="periodic")
    result = repricer_tasks._materialize_report_snapshots_for_profile(1, profile, persist_progress=False)
    assert result["state"] == "completed", result
    assert "abc" in result["reports"]
    key = reports._report_cache_key("abc", START, END, "sku", "operational", organization_id=1, finance_allowed=True)
    assert abc_cache[1, key]["report"]["rows"][0]["commissionKopecks"] == 12_345
    assert (1, reports._report_cache_key("abc", START, END, "sku", "operational", organization_id=1)) not in abc_cache
