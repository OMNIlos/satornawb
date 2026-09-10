"""P&L payload caches must preserve the builder's finance permission scope."""

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
        reports, "get_cash_flow_for_period", lambda **kw: {"status": "ready"}
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
@pytest.mark.parametrize("legacy_suffix", ["", "_nofinance"])
def test_reader_does_not_reuse_old_unscoped_financial_payload(
    cache, endpoint, params, status, legacy_suffix
):
    # Older endpoints accepted arbitrary source strings; a suffix alone is not provenance.
    key = f"reports_payload_pnl_{START}_{END}_sku_operational{legacy_suffix}"
    cache[1, key] = {
        "completedAt": reports._utc_now_iso(),
        "dateFrom": str(START),
        "dateTo": str(END),
        "report": {
            "cacheVersion": "v1",
            "rows": [{"label": "PRIVATE", "overheadKopecks": 12_345}],
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
    assert len(enqueued) == 1
    assert enqueued[0][-2:] == (finance_allowed, None)
