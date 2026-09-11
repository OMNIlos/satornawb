"""Reading cached reports must not complete or overwrite live background work."""

from copy import deepcopy
from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app import repricer_tasks
from app.main import create_app
from app.routers import wb_reports_bff as reports
from tests.auth_helpers import auth_headers

START, END = date(2026, 8, 17), date(2026, 8, 23)
PARAMS = {"preset": "custom", "from": str(START), "to": str(END)}


@pytest.fixture
def runtime(monkeypatch):
    state = SimpleNamespace(cache={}, writes=[], builds=[], refreshes=[], ready=False)

    def save(org, key, payload):
        state.writes.append(key)
        state.cache[org, key] = deepcopy(payload)

    def enqueue(target, args):
        target.append(args)
        return SimpleNamespace(id="synthetic-task")

    monkeypatch.setattr(
        reports,
        "get_source_cache",
        lambda org, key, **kw: deepcopy(state.cache.get((org, key))),
    )
    monkeypatch.setattr(reports, "save_source_cache", save)
    monkeypatch.setattr(
        reports,
        "list_source_cache_by_prefix",
        lambda org, prefix, **kw: [
            {**deepcopy(value), "sourceKey": key}
            for (owner, key), value in state.cache.items()
            if owner == org and key.startswith(prefix)
        ],
    )
    monkeypatch.setattr(reports, "_abc_economics_version", lambda org: "cafef00d")
    readiness = lambda *args, **kw: (state.ready, [] if state.ready else ["ads"])
    monkeypatch.setattr(reports, "_report_daily_sources_ready", readiness)
    monkeypatch.setattr(repricer_tasks, "_report_snapshot_sources_ready", readiness)
    monkeypatch.setattr(
        reports, "get_cash_flow_for_period", lambda **kw: {"status": "ready"}
    )
    monkeypatch.setattr(
        repricer_tasks.build_report_for_org,
        "delay",
        lambda *args: enqueue(state.builds, args),
    )
    monkeypatch.setattr(
        repricer_tasks.refresh_report_sources_for_org,
        "delay",
        lambda *args: enqueue(state.refreshes, args),
    )
    state.api = TestClient(create_app())
    state.api.headers.update(auth_headers(state.api, "viewer"))
    return state


def seed(
    runtime, report_id, *, cached=True, state="running", stage="refreshing_sources"
):
    job = {
        "reportId": report_id,
        "state": state,
        "stage": stage,
        "taskId": "live-task",
        "updatedAt": reports._utc_now_iso(),
        "percent": 37,
        "label": "Loading source",
    }
    key = reports._report_job_cache_key(report_id, START, END, "sku", "operational")
    runtime.cache[1, key] = deepcopy(job)
    if cached:
        versions = {
            "abc": reports.ABC_REPORT_PAYLOAD_VERSION,
            "pnl": reports.PNL_REPORT_PAYLOAD_VERSION,
            "week-over-week": reports.WEEK_OVER_WEEK_REPORT_PAYLOAD_VERSION,
        }
        payload_key = reports._report_cache_key(
            report_id, START, END, "sku", "operational", organization_id=1
        )
        runtime.cache[1, payload_key] = {
            "completedAt": reports._utc_now_iso(),
            "dateFrom": str(START),
            "dateTo": str(END),
            "report": {
                "cacheVersion": versions[report_id],
                "economicsVersion": "cafef00d",
                "rows": [{"sku": "SKU-1", "orders": {"units": 1}}],
            },
        }
    return key, job


@pytest.mark.parametrize("report_id", ["abc", "pnl", "week-over-week"])
@pytest.mark.parametrize(
    "suffix,params", [("", PARAMS), ("/latest-cache", {}), ("/latest-cache", PARAMS)]
)
def test_cached_report_reads_preserve_active_job_without_writes(
    runtime, report_id, suffix, params
):
    key, job = seed(runtime, report_id)
    response = runtime.api.get(f"/api/wb/reports/{report_id}{suffix}", params=params)
    assert response.status_code == 200
    assert response.json()["rows"]
    assert response.json()["reportJob"] == job
    assert runtime.cache[1, key] == job
    assert runtime.writes == []
    repeated = runtime.api.post(f"/api/wb/reports/{report_id}/jobs", params=PARAMS)
    assert repeated.status_code == 200
    assert repeated.json()["reused"] is True
    assert runtime.builds == runtime.refreshes == []


def test_missing_source_read_preserves_refresh_and_does_not_allow_duplicate(runtime):
    key, job = seed(runtime, "ads", cached=False)
    response = runtime.api.get("/api/wb/reports/ads", params=PARAMS)
    assert response.status_code == 200
    assert response.json()["rows"] == []
    assert response.json()["reportJob"] == job
    assert runtime.cache[1, key] == job
    assert runtime.writes == []
    repeated = runtime.api.post(
        "/api/wb/reports/ads/refresh-sources-job", params=PARAMS
    )
    assert repeated.status_code == 200
    assert repeated.json()["reused"] is True
    assert runtime.refreshes == []


@pytest.mark.parametrize(
    "state,stage", [("running", "pnl"), ("waiting_1c", "waiting_1c")]
)
def test_source_refresh_reuses_its_replacement_builder(runtime, state, stage):
    key, job = seed(runtime, "pnl", cached=False, state=state, stage=stage)
    job["kind"] = "report_source_refresh"
    runtime.cache[1, key] = job
    response = runtime.api.post(
        "/api/wb/reports/pnl/refresh-sources-job", params=PARAMS
    )
    assert response.status_code == 200
    assert response.json()["reused"] is True
    assert runtime.cache[1, key] == job
    assert runtime.writes == runtime.refreshes == []


@pytest.mark.parametrize("active", [False, True])
def test_wow_derived_latest_cache_preserves_real_live_job(runtime, monkeypatch, active):
    key, job = seed(runtime, "week-over-week", cached=False)
    if not active:
        runtime.cache.pop((1, key))
    monkeypatch.setattr(
        reports,
        "_build_week_over_week_fallback_report",
        lambda **kwargs: {
            "rows": [{"sku": "SKU-1", "orders": {"units": 1}}],
            "reportJob": {"state": "completed", "taskId": None, "percent": 100},
        },
    )
    response = runtime.api.get(
        "/api/wb/reports/week-over-week/latest-cache", params=PARAMS
    )
    assert response.status_code == 200
    assert response.json()["rows"][0]["sku"] == "SKU-1"
    assert response.json()["cache"]["status"] == "derived"
    if active:
        assert response.json()["reportJob"] == job
        assert runtime.cache[1, key] == job
        assert key not in runtime.writes
    else:
        assert response.json()["reportJob"]["state"] == "completed"
        assert runtime.cache[1, key]["state"] == "completed"
    payload_key = reports._report_cache_key(
        "week-over-week", START, END, "sku", "operational"
    )
    assert runtime.cache[1, payload_key]["report"]["rows"]


@pytest.mark.parametrize("state,stage", [("running", "pnl"), ("queued", "")])
def test_missing_source_does_not_start_refresh_over_active_build(runtime, state, stage):
    key, job = seed(runtime, "pnl", cached=False, state=state, stage=stage)
    response = runtime.api.post("/api/wb/reports/pnl/jobs", params=PARAMS)
    assert response.status_code == 200
    assert response.json()["reused"] is True
    assert runtime.cache[1, key] == job
    assert runtime.writes == runtime.builds == runtime.refreshes == []


@pytest.mark.parametrize(
    "state,stage", [("running", "pnl"), ("queued", ""), ("waiting_1c", "waiting_1c")]
)
@pytest.mark.parametrize("suffix", ["", "/jobs"])
def test_cache_does_not_complete_other_active_build_stages(
    runtime, state, stage, suffix
):
    key, job = seed(runtime, "pnl", state=state, stage=stage)
    response = runtime.api.get(f"/api/wb/reports/pnl{suffix}", params=PARAMS)
    assert response.status_code == 200
    actual = response.json() if suffix else response.json()["reportJob"]
    assert actual["state"] == state
    assert actual["stage"] == stage
    assert actual["percent"] == 37
    assert runtime.cache[1, key] == job
    assert runtime.writes == []


def test_finished_daily_wait_can_enqueue_once_after_sources_arrive(runtime):
    result = repricer_tasks.build_report_for_org.run(
        1,
        "synthetic-user",
        "ads",
        str(START),
        str(END),
        "sku",
        "operational",
        False,
        None,
    )
    assert result["state"] == "waiting_daily_detail"
    runtime.ready = True
    for reused in (False, True):
        response = runtime.api.post("/api/wb/reports/ads/jobs", params=PARAMS)
        assert response.status_code == 200
        assert response.json()["state"] == "queued"
        assert response.json()["reused"] is reused
    assert len(runtime.builds) == 1
    assert runtime.refreshes == []


@pytest.mark.parametrize("waiting", ["waiting_daily_detail", "waiting_baskets_detail"])
def test_external_data_wait_is_not_a_live_worker(waiting):
    assert not reports._report_job_is_reusable(
        {"state": waiting, "updatedAt": reports._utc_now_iso()}
    )


@pytest.mark.parametrize("heartbeat", ["expired", "missing"])
def test_abandoned_1c_wait_is_stale_and_can_restart_once(runtime, heartbeat):
    key, job = seed(runtime, "pnl", cached=False, state="waiting_1c", stage="waiting_1c")
    if heartbeat == "expired":
        job["updatedAt"] = (
            datetime.now(timezone.utc) - reports.BACKGROUND_REPORT_JOB_STALE_AFTER
            - timedelta(seconds=1)
        ).isoformat()
    else:
        job.pop("updatedAt")
    runtime.cache[1, key] = deepcopy(job)
    runtime.ready = True
    for suffix in ("", "/jobs"):
        response = runtime.api.get(f"/api/wb/reports/pnl{suffix}", params=PARAMS)
        assert response.status_code == 200
        status = response.json() if suffix else response.json()["reportJob"]
        assert status["state"] == "stale"
        assert status["previousState"] == "waiting_1c"
    assert runtime.cache[1, key] == job
    assert runtime.writes == runtime.builds == runtime.refreshes == []
    for reused in (False, True):
        response = runtime.api.post("/api/wb/reports/pnl/jobs", params=PARAMS)
        assert response.status_code == 200
        assert response.json()["state"] == "queued"
        assert response.json()["reused"] is reused
    assert len(runtime.builds) == 1
    assert runtime.refreshes == []


def test_explicit_refresh_can_replace_abandoned_1c_wait_once(runtime):
    key, job = seed(runtime, "pnl", cached=False, state="waiting_1c", stage="waiting_1c")
    job["kind"] = "report_source_refresh"
    job["updatedAt"] = (
        datetime.now(timezone.utc) - reports.BACKGROUND_REPORT_JOB_STALE_AFTER
        - timedelta(seconds=1)
    ).isoformat()
    runtime.cache[1, key] = job
    for reused in (False, True):
        response = runtime.api.post("/api/wb/reports/pnl/refresh-sources-job", params=PARAMS)
        assert response.status_code == 200
        assert response.json()["state"] == "queued"
        assert response.json()["reused"] is reused
    assert len(runtime.refreshes) == 1
    assert runtime.builds == []


def test_expenses_pending_source_without_worker_is_not_a_stale_task(runtime, monkeypatch):
    monkeypatch.setattr(
        reports, "get_cash_flow_for_period", lambda **kw: {"status": "pending"}
    )
    response = runtime.api.get("/api/wb/reports/expenses", params=PARAMS, headers=auth_headers(runtime.api, "finance_viewer"))
    assert response.status_code == 200
    assert response.json()["reportJob"]["state"] == "waiting_1c"
    assert not response.json()["reportJob"].get("taskId")
    assert runtime.writes == runtime.builds == runtime.refreshes == []


def test_stale_worker_can_be_completed_from_valid_cache(runtime):
    key, job = seed(runtime, "pnl")
    job["updatedAt"] = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    runtime.cache[1, key] = job
    response = runtime.api.get("/api/wb/reports/pnl", params=PARAMS)
    assert response.status_code == 200
    assert response.json()["reportJob"]["state"] == "completed"
    assert runtime.cache[1, key]["state"] == "completed"
