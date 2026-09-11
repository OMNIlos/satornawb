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
        repricer_tasks.build_digest_for_org, "delay",
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


@pytest.mark.parametrize("report_id,previous", [("abc", "v17"), ("pnl", "v3"), ("week-over-week", "v2")])
@pytest.mark.parametrize("suffix", ["", "/latest-cache"])
def test_monetary_report_readers_reject_previous_payloads(runtime, report_id, previous, suffix):
    seed(runtime, report_id)
    key = reports._report_cache_key(report_id, START, END, "sku", "operational", organization_id=1)
    current = deepcopy(runtime.cache[1, key])
    current["report"]["rows"][0]["netProfitKopecks"] = 9000
    old = deepcopy(current)
    old["report"]["cacheVersion"] = previous
    old["report"]["rows"][0]["netProfitKopecks"] = 987654321
    # Seed both the previous physical key and old metadata at the current key.
    old_key = key.replace(current["report"]["cacheVersion"], previous, 1)
    runtime.cache[1, old_key] = old
    runtime.cache[1, key] = old
    response = runtime.api.get(f"/api/wb/reports/{report_id}{suffix}", params=PARAMS)
    assert response.status_code == (404 if suffix else 200)
    assert "987654321" not in response.text
    runtime.cache[1, key] = current
    response = runtime.api.get(f"/api/wb/reports/{report_id}{suffix}", params=PARAMS)
    assert response.status_code == 200
    assert response.json()["rows"][0]["netProfitKopecks"] == 9000


@pytest.mark.parametrize("location", ["exact", "latest"])
def test_digest_reader_rejects_previous_monetary_payload(runtime, location):
    key = reports._digest_cache_key(START, END) if location == "exact" else "reports_digest_latest"
    old_key = f"reports_digest_v12_{START}_{END}" if location == "exact" else key
    old = {"completedAt": reports._utc_now_iso(), "digest": {
        "meta": {"freshnessState": "cached"},
        "cacheVersion": "v12", "kpis": [{"id": "margin_profit", "value": "987654321"}],
    }}
    runtime.cache[1, old_key] = old
    runtime.cache[1, key] = old
    response = runtime.api.get("/api/wb/reports/digest", params=PARAMS)
    assert response.status_code == 200
    assert "987654321" not in response.text
    runtime.cache[1, key] = {"completedAt": reports._utc_now_iso(), "digest": {
        "meta": {"freshnessState": "cached"},
        "cacheVersion": reports.DIGEST_REPORT_PAYLOAD_VERSION,
        "kpis": [{"id": "margin_profit", "value": "9000"}],
    }}
    response = runtime.api.get("/api/wb/reports/digest", params=PARAMS)
    assert response.status_code == 200
    assert response.json()["kpis"][0]["value"] == "9000"


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


@pytest.mark.parametrize("report_id", ["abc", "pnl", "week-over-week"])
@pytest.mark.parametrize("state", ["completed", "failed"])
@pytest.mark.parametrize(
    "suffix,params",
    [("", PARAMS), ("/jobs", PARAMS), ("/latest-cache", {}), ("/latest-cache", PARAMS)],
)
def test_cached_reads_preserve_finished_source_refresh(
    runtime, report_id, state, suffix, params
):
    key, job = seed(runtime, report_id, state=state, stage=state)
    job.update(kind="report_source_refresh", sync={"state": "completed"})
    if state == "failed":
        job["error"] = "synthetic build failure"
    runtime.cache[1, key] = deepcopy(job)
    response = runtime.api.get(f"/api/wb/reports/{report_id}{suffix}", params=params)
    assert response.status_code == 200
    if suffix == "/jobs":
        assert response.json() == {**job, "reused": True}
    else:
        assert response.json()["rows"][0]["sku"] == "SKU-1"
        assert response.json()["reportJob"] == job
    assert runtime.cache[1, key] == job
    assert runtime.writes == runtime.builds == runtime.refreshes == []


@pytest.mark.parametrize("report_id", ["abc", "pnl", "week-over-week"])
@pytest.mark.parametrize("state", ["completed", "failed"])
def test_normal_start_can_use_cache_after_finished_source_refresh(runtime, report_id, state):
    key, job = seed(runtime, report_id, state=state, stage=state)
    job.update(kind="report_source_refresh", sync={"state": "completed"})
    runtime.cache[1, key] = deepcopy(job)
    response = runtime.api.post(f"/api/wb/reports/{report_id}/jobs", params=PARAMS)
    assert response.status_code == 200
    assert response.json()["state"] == "completed"
    assert response.json()["stage"] == "cache"
    assert response.json()["cacheFresh"] is True
    assert runtime.cache[1, key] == response.json()
    assert runtime.builds == runtime.refreshes == []


@pytest.mark.parametrize("report_id", ["abc", "pnl", "week-over-week"])
def test_explicit_refresh_retries_failed_job_once_even_with_cache(runtime, report_id):
    key, job = seed(runtime, report_id, state="failed", stage="failed")
    job["kind"] = "report_source_refresh"
    runtime.cache[1, key] = deepcopy(job)
    for reused in (False, True):
        response = runtime.api.post(
            f"/api/wb/reports/{report_id}/refresh-sources-job", params=PARAMS
        )
        assert response.status_code == 200
        assert response.json()["state"] == "queued"
        assert response.json()["reused"] is reused
    assert len(runtime.refreshes) == 1
    assert runtime.builds == []


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
def test_source_refresh_reuses_its_replacement_builder(runtime, monkeypatch, state, stage):
    monkeypatch.setattr(
        reports, "get_cash_flow_for_period",
        lambda **kw: pytest.fail("reused job must not request 1C again"),
    )
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


@pytest.mark.parametrize("state", ["completed", "failed"])
def test_wow_derived_cache_preserves_finished_refresh(runtime, monkeypatch, state):
    key, job = seed(runtime, "week-over-week", cached=False, state=state, stage=state)
    job.update(kind="report_source_refresh", sync={"state": "completed"})
    runtime.cache[1, key] = deepcopy(job)
    monkeypatch.setattr(
        reports, "_build_week_over_week_fallback_report",
        lambda **kw: {"rows": [{"sku": "SKU-1", "orders": {"units": 1}}]},
    )
    response = runtime.api.get("/api/wb/reports/week-over-week/latest-cache", params=PARAMS)
    assert response.status_code == 200
    assert response.json()["rows"][0]["sku"] == "SKU-1"
    assert response.json()["cache"]["status"] == "derived"
    assert response.json()["reportJob"] == job
    assert runtime.cache[1, key] == job
    payload_key = reports._report_cache_key("week-over-week", START, END, "sku", "operational")
    assert runtime.writes == [payload_key]
    assert runtime.builds == runtime.refreshes == []


@pytest.mark.parametrize("state,stage", [("running", "pnl"), ("queued", "")])
def test_missing_source_does_not_start_refresh_over_active_build(
    runtime, monkeypatch, state, stage
):
    monkeypatch.setattr(
        reports, "get_cash_flow_for_period",
        lambda **kw: pytest.fail("reused job must not request 1C again"),
    )
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


@pytest.mark.parametrize("endpoint", ["jobs", "refresh-sources-job"])
@pytest.mark.parametrize("ready", [False, True])
@pytest.mark.parametrize("finance_allowed", [False, True])
def test_pnl_prepares_1c_before_either_dispatch(
    runtime, monkeypatch, endpoint, ready, finance_allowed
):
    runtime.ready = ready
    requested = []
    dispatched = []
    cash_flow = {
        "status": "ready",
        "data": {"totals": {"operationalExpenseKopecks": 164_000}},
    }

    def prepare(**kwargs):
        requested.append(kwargs)
        return cash_flow

    def enqueue(kind, args):
        assert len(requested) == 1, "1C must be prepared before any Celery dispatch"
        assert requested[0]["organization_id"] == 1
        assert requested[0]["period_from"] == START
        assert requested[0]["period_to"] == END
        assert requested[0]["requested_by"] == args[1]
        dispatched.append((kind, args))
        return SimpleNamespace(id="synthetic-task")

    monkeypatch.setattr(reports, "get_cash_flow_for_period", prepare)
    monkeypatch.setattr(
        repricer_tasks.build_report_for_org, "delay",
        lambda *args: enqueue("build", args),
    )
    monkeypatch.setattr(
        repricer_tasks.refresh_report_sources_for_org, "delay",
        lambda *args: enqueue("refresh", args),
    )
    headers = auth_headers(runtime.api, "finance_viewer" if finance_allowed else "viewer")
    key = reports._report_job_cache_key("pnl", START, END, "sku", "operational")
    for reused in (False, True):
        response = runtime.api.post(
            f"/api/wb/reports/pnl/{endpoint}", params=PARAMS, headers=headers
        )
        assert response.status_code == 200
        assert response.json()["state"] == "queued"
        assert response.json()["reused"] is reused
        if not reused and endpoint == "jobs":
            assert response.json()["cashFlow"] == (cash_flow if finance_allowed else None)
        else:
            assert "cashFlow" not in response.json()
        assert "cashFlow" not in runtime.cache[1, key]
    assert len(requested) == len(dispatched) == 1
    assert dispatched[0][0] == ("build" if ready and endpoint == "jobs" else "refresh")
    assert dispatched[0][1][-2:] == (finance_allowed, None)


def test_pnl_completed_cache_does_not_request_1c(runtime, monkeypatch):
    key, _ = seed(runtime, "pnl", state="completed", stage="completed")
    monkeypatch.setattr(
        reports, "get_cash_flow_for_period",
        lambda **kw: pytest.fail("usable cache needs no 1C request"),
    )
    response = runtime.api.post("/api/wb/reports/pnl/jobs", params=PARAMS)
    assert response.status_code == 200
    assert response.json()["state"] == runtime.cache[1, key]["state"] == "completed"
    assert runtime.builds == runtime.refreshes == []


def seed_digest(runtime, *, cached=True, state="running", stage="funnel"):
    job = {
        "state": state, "stage": stage, "taskId": "digest-task",
        "dateFrom": str(START), "dateTo": str(END),
        "updatedAt": reports._utc_now_iso(), "percent": 82,
        "kind": "report_source_refresh", "sync": {"state": "completed"},
    }
    key = reports._digest_job_cache_key(START, END)
    runtime.cache[1, key] = deepcopy(job)
    if cached:
        runtime.cache[1, reports._digest_cache_key(START, END)] = {
            "dateFrom": str(START), "dateTo": str(END),
            "completedAt": reports._utc_now_iso(),
            "digest": {
                "cacheVersion": reports.DIGEST_REPORT_PAYLOAD_VERSION,
                "meta": {"freshnessState": "cached"}, "rows": [{"sku": "SKU-1"}],
            },
        }
    return key, job


@pytest.mark.parametrize("cached", [False, True])
@pytest.mark.parametrize("state,stage", [("queued", "queued"), ("running", "funnel")])
@pytest.mark.parametrize("endpoint", ["", "/refresh", "/refresh-sources-job"])
def test_digest_read_and_refresh_preserve_live_job(runtime, cached, state, stage, endpoint):
    key, job = seed_digest(runtime, cached=cached, state=state, stage=stage)
    method = runtime.api.post if endpoint else runtime.api.get
    response = method(f"/api/wb/reports/digest{endpoint}", params=PARAMS)
    assert response.status_code == 200
    if endpoint:
        assert response.json() == {**job, "reused": True}
    else:
        assert response.json()["digestJob"] == job
    assert runtime.cache[1, key] == job
    assert runtime.writes == runtime.builds == runtime.refreshes == []


@pytest.mark.parametrize("params", [{}, PARAMS])
@pytest.mark.parametrize("state,stage", [("running", "funnel"), ("failed", "failed")])
def test_digest_latest_reads_selected_period_job(runtime, params, state, stage):
    key, job = seed_digest(runtime, state=state, stage=stage)
    # Another period must not supply the status for the selected cached payload.
    runtime.cache[1, reports._digest_job_cache_key(END, END)] = {"state": "completed"}
    response = runtime.api.get("/api/wb/reports/digest/latest-cache", params=params)
    assert response.status_code == 200
    assert response.json()["rows"] == [{"sku": "SKU-1"}]
    assert response.json()["digestJob"] == job
    assert runtime.cache[1, key] == job
    assert runtime.writes == []


@pytest.mark.parametrize("suffix", ["", "/status"])
def test_digest_failed_refresh_remains_visible_with_fresh_cache(runtime, suffix):
    key, job = seed_digest(runtime, state="failed", stage="failed")
    response = runtime.api.get(f"/api/wb/reports/digest{suffix}", params=PARAMS)
    assert response.status_code == 200
    assert (response.json() if suffix else response.json()["digestJob"]) == job
    assert runtime.cache[1, key] == job
    assert runtime.writes == []


@pytest.mark.parametrize("state", ["queued", "running"])
@pytest.mark.parametrize("heartbeat", ["missing", "expired"])
@pytest.mark.parametrize("suffix", ["", "/status", "/refresh"])
def test_digest_abandoned_job_is_stale_and_restarts_once(runtime, state, heartbeat, suffix):
    key, job = seed_digest(runtime, cached=False, state=state)
    if heartbeat == "missing":
        job.pop("updatedAt")
    else:
        limit = (reports.BACKGROUND_REPORT_QUEUED_STALE_AFTER if state == "queued"
                 else reports.BACKGROUND_REPORT_JOB_STALE_AFTER)
        job["updatedAt"] = (datetime.now(timezone.utc) - limit - timedelta(seconds=1)).isoformat()
    runtime.cache[1, key] = deepcopy(job)
    if suffix != "/refresh":
        response = runtime.api.get(f"/api/wb/reports/digest{suffix}", params=PARAMS)
        assert response.status_code == 200
        actual = response.json() if suffix else response.json()["digestJob"]
        assert actual["state"] == "stale"
        assert actual["previousState"] == state
        assert actual["taskId"] == "digest-task"
    assert runtime.cache[1, key] == job
    assert runtime.writes == []
    for reused in (False, True):
        response = runtime.api.post("/api/wb/reports/digest/refresh", params=PARAMS)
        assert response.status_code == 200
        assert response.json()["state"] == "queued"
        assert response.json()["reused"] is reused
    assert runtime.builds == [(1, str(START), str(END), False, None)]
    assert runtime.refreshes == []


def test_digest_latest_exposes_stale_job_with_fresh_cache(runtime):
    key, job = seed_digest(runtime)
    job.pop("updatedAt")
    runtime.cache[1, key] = deepcopy(job)
    response = runtime.api.get("/api/wb/reports/digest/latest-cache")
    assert response.status_code == 200
    assert response.json()["digestJob"]["state"] == "stale"
    assert response.json()["digestJob"]["taskId"] == "digest-task"
    assert runtime.cache[1, key] == job
    assert runtime.writes == []


@pytest.mark.parametrize("state", ["missing", "completed", "stale", "failed"])
def test_digest_refresh_keeps_fresh_cache_fast_path(runtime, state):
    key, job = seed_digest(runtime, state=state, stage=state)
    if state == "missing":
        runtime.cache.pop((1, key))
    response = runtime.api.post("/api/wb/reports/digest/refresh", params=PARAMS)
    assert response.status_code == 200
    assert response.json()["state"] == "completed"
    assert response.json()["cacheFresh"] is True
    assert runtime.cache[1, key]["state"] == "completed"
    assert runtime.builds == runtime.refreshes == []


def test_digest_latest_without_job_keeps_completed_cache_response(runtime):
    key, _ = seed_digest(runtime)
    runtime.cache.pop((1, key))
    response = runtime.api.get("/api/wb/reports/digest/latest-cache")
    assert response.status_code == 200
    assert response.json()["digestJob"]["state"] == "completed"
    assert response.json()["digestJob"]["dateFrom"] == str(START)
    assert runtime.writes == []


@pytest.mark.parametrize("endpoint", ["", "/refresh"])
def test_digest_cache_preserves_standalone_builder_without_refresh_kind(runtime, endpoint):
    key, job = seed_digest(runtime)
    job.pop("kind")
    job.pop("sync")
    runtime.cache[1, key] = deepcopy(job)
    method = runtime.api.post if endpoint else runtime.api.get
    response = method(f"/api/wb/reports/digest{endpoint}", params=PARAMS)
    assert response.status_code == 200
    actual = response.json() if endpoint else response.json()["digestJob"]
    assert actual["state"] == "running" and actual["taskId"] == "digest-task"
    assert runtime.cache[1, key] == job
    assert runtime.writes == runtime.builds == runtime.refreshes == []


@pytest.mark.parametrize("missing", [False, True])
def test_digest_read_can_complete_abandoned_job_from_fresh_cache(runtime, missing):
    key, job = seed_digest(runtime)
    job.pop("updatedAt")
    if missing:
        runtime.cache.pop((1, key))
    else:
        runtime.cache[1, key] = job
    response = runtime.api.get("/api/wb/reports/digest", params=PARAMS)
    assert response.status_code == 200
    assert response.json()["digestJob"]["state"] == "completed"
    assert response.json()["rows"] == [{"sku": "SKU-1"}]
    assert runtime.cache[1, key]["state"] == "completed"
    assert runtime.builds == runtime.refreshes == []
