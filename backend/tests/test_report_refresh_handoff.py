"""Source refresh must hand off to a real Celery request with its own retry."""

from copy import deepcopy
from datetime import date
from types import SimpleNamespace

import pytest
from celery.exceptions import Ignore, Retry

from app import repricer_tasks as tasks
from app.routers import wb_reports_bff as reports


def run_as_worker(task, args, kwargs=None, **options):
    task.push_request(
        id=options.get("task_id", "refresh-task"),
        args=args,
        kwargs=kwargs or {},
        called_directly=False,
        is_eager=False,
        retries=options.get("retries", 0),
    )
    try:
        return task.run(*args, **(kwargs or {}))
    finally:
        task.pop_request()


@pytest.fixture
def runtime(monkeypatch):
    state = SimpleNamespace(
        cache={}, writes=[], queue=[], refreshes=[], ready=False, cash_status="pending"
    )

    def save(org, key, payload):
        state.cache[org, key] = deepcopy(payload)
        state.writes.append(deepcopy(payload))

    def refresh(**kwargs):
        state.refreshes.append(kwargs)
        return {"state": "completed", "steps": [{"source": "finance", "status": "ok"}]}

    def enqueue(args=None, kwargs=None, **options):
        state.queue.append((args, kwargs, options))
        return SimpleNamespace(id=options.get("task_id"))

    monkeypatch.setattr(tasks, "_report_refresh_wb_token", lambda *args: "synthetic")
    monkeypatch.setattr(tasks, "refresh_wb_data_sources", refresh)
    monkeypatch.setattr(
        tasks,
        "_report_snapshot_sources_ready",
        lambda *args: (state.ready, ["finance"]),
    )
    monkeypatch.setattr(tasks.build_report_for_org, "apply_async", enqueue)
    monkeypatch.setattr(tasks.build_digest_for_org, "apply_async", enqueue)
    monkeypatch.setattr(
        tasks.build_digest_for_org, "AsyncResult",
        lambda task_id: SimpleNamespace(id=task_id),
    )
    monkeypatch.setattr(
        tasks.build_report_for_org,
        "AsyncResult",
        lambda task_id: SimpleNamespace(id=task_id),
    )
    monkeypatch.setattr(reports, "save_source_cache", save)
    monkeypatch.setattr(
        reports,
        "get_source_cache",
        lambda org, key, **kw: deepcopy(state.cache.get((org, key))),
    )
    monkeypatch.setattr(
        reports, "get_cash_flow_for_period", lambda **kw: {"status": state.cash_status}
    )
    monkeypatch.setattr(reports, "build_pnl_report", lambda **kw: SimpleNamespace())
    payload = {
        "cacheVersion": reports.PNL_REPORT_PAYLOAD_VERSION,
        "rows": [{"sku": "SKU-1"}],
    }
    monkeypatch.setattr(
        reports, "_map_pnl_to_report_response", lambda *args, **kwargs: deepcopy(payload)
    )
    monkeypatch.setattr(
        reports, "_build_ads_report_payload", lambda **kw: deepcopy(payload)
    )
    monkeypatch.setattr(
        reports, "_apply_report_rules_to_payload", lambda payload, org: payload
    )
    monkeypatch.setattr(reports, "build_cached_wb_reports_sources_snapshot", lambda **kw: SimpleNamespace())
    monkeypatch.setattr(reports, "_build_digest_ads_snapshot", lambda **kw: SimpleNamespace())
    monkeypatch.setattr(reports, "_build_digest_funnel_snapshot", lambda **kw: {})
    monkeypatch.setattr(reports, "build_plan_fact_report", lambda **kw: SimpleNamespace())
    monkeypatch.setattr(tasks, "_digest_report_summary", lambda *args: {})
    monkeypatch.setattr(
        reports, "_build_digest_payload",
        lambda *args: {"cacheVersion": reports.DIGEST_REPORT_PAYLOAD_VERSION, "rows": [{"sku": "SKU-1"}]},
    )
    return state


def refresh_args(report_id):
    return (
        1,
        "synthetic-user",
        report_id,
        "2026-08-17",
        "2026-08-23",
        "sku",
        "operational",
        False,
        None,
    )


@pytest.mark.parametrize("report_id", ["ads", "pnl"])
def test_refresh_hands_off_without_completing_a_waiting_report(runtime, report_id):
    with pytest.raises(Ignore):
        run_as_worker(tasks.refresh_report_sources_for_org, refresh_args(report_id))
    assert len(runtime.queue) == len(runtime.refreshes) == 1
    args, kwargs, options = runtime.queue[0]
    assert args == refresh_args(report_id)
    assert options["task_id"] == "refresh-task"
    assert runtime.writes[-1]["state"] == "running"
    assert runtime.writes[-1]["stage"] == "building_report"
    result = run_as_worker(tasks.build_report_for_org, args, kwargs, **options)
    assert result["state"] == "waiting_daily_detail"
    assert result["taskId"] == "refresh-task"
    assert result["kind"] == "report_source_refresh"
    assert result["sync"]["state"] == "completed"
    assert not any(row["state"] in {"completed", "failed"} for row in runtime.writes)


def test_1c_retry_requeues_only_build_with_same_identity_and_context(runtime):
    runtime.ready = True
    with pytest.raises(Ignore):
        run_as_worker(tasks.refresh_report_sources_for_org, refresh_args("pnl"))
    args, kwargs, options = runtime.queue[0]
    with pytest.raises(Retry):
        run_as_worker(tasks.build_report_for_org, args, kwargs, **options)
    assert runtime.writes[-1]["state"] == "waiting_1c"
    assert runtime.writes[-1]["kind"] == "report_source_refresh"
    assert len(runtime.queue) == 2
    retry_args, retry_kwargs, retry_options = runtime.queue[1]
    assert retry_args == args and retry_kwargs == kwargs
    assert retry_options["task_id"] == "refresh-task"
    assert retry_options["countdown"] == 3
    assert retry_options["retries"] == 1
    runtime.cash_status = "ready"
    result = run_as_worker(
        tasks.build_report_for_org, retry_args, retry_kwargs, **retry_options
    )
    assert result["state"] == "completed"
    assert result["taskId"] == "refresh-task"
    assert result["kind"] == "report_source_refresh"
    assert result["sync"] == kwargs["source_refresh"]
    assert len(runtime.refreshes) == 1
    assert not any(row.get("state") == "failed" for row in runtime.writes)


def test_failed_replacement_remains_a_failed_refresh(runtime):
    runtime.ready = True
    runtime.cash_status = "error"
    with pytest.raises(Ignore):
        run_as_worker(tasks.refresh_report_sources_for_org, refresh_args("pnl"))
    args, kwargs, options = runtime.queue[0]
    with pytest.raises(RuntimeError, match="1С"):
        run_as_worker(tasks.build_report_for_org, args, kwargs, **options)
    failed = runtime.writes[-1]
    assert failed["state"] == failed["stage"] == "failed"
    assert failed["taskId"] == "refresh-task"
    assert failed["sync"] == kwargs["source_refresh"]
    assert reports._report_job_is_finished_refresh(failed)


def test_standalone_build_keeps_existing_contract(runtime):
    runtime.ready = True
    result = run_as_worker(tasks.build_report_for_org, refresh_args("ads"))
    assert result["state"] == "completed"
    assert "kind" not in result and "sync" not in result
    assert runtime.refreshes == runtime.queue == []


def test_digest_refresh_replaces_inline_build_with_same_task(runtime):
    with pytest.raises(Ignore):
        run_as_worker(tasks.refresh_report_sources_for_org, refresh_args("digest"))
    assert len(runtime.queue) == len(runtime.refreshes) == 1
    args, kwargs, options = runtime.queue[0]
    assert args == (1, "2026-08-17", "2026-08-23", False, None)
    assert kwargs == {"source_refresh": {"state": "completed", "steps": [{"source": "finance", "status": "ok"}]}}
    assert options["task_id"] == "refresh-task"
    assert runtime.writes[-1]["state"] == "running"
    assert runtime.writes[-1]["stage"] == "building_report"
    assert not any("digest" in row or row["state"] in {"completed", "failed"} for row in runtime.writes)
    result = run_as_worker(tasks.build_digest_for_org, args, kwargs, **options)
    terminal = [row for row in runtime.writes if row.get("state") in {"completed", "failed"}]
    assert terminal == [result]
    assert result["state"] == "completed"
    assert result["taskId"] == "refresh-task"


@pytest.mark.parametrize("fail", [False, True])
def test_digest_builder_preserves_refresh_context_at_every_stage(runtime, monkeypatch, fail):
    sync = {"state": "completed", "steps": [{"source": "finance", "status": "ok"}]}

    def funnel(**kwargs):
        kwargs["progress_callback"]("funnel-page", "Page loaded", 90)
        if fail:
            raise RuntimeError("digest build failed")
        return {}

    monkeypatch.setattr(reports, "_build_digest_funnel_snapshot", funnel)
    args = (1, "2026-08-17", "2026-08-23", False, None)
    if fail:
        with pytest.raises(RuntimeError, match="digest build failed"):
            run_as_worker(tasks.build_digest_for_org, args, {"source_refresh": sync})
    else:
        run_as_worker(tasks.build_digest_for_org, args, {"source_refresh": sync})
    jobs = [row for row in runtime.writes if "state" in row]
    for job in jobs:
        assert job["taskId"] == "refresh-task"
        assert job["kind"] == "report_source_refresh"
        assert job["sync"] == sync
        assert job["dateFrom"] == "2026-08-17" and job["dateTo"] == "2026-08-23"
        if job["state"] == "running":
            assert reports._report_job_is_active_refresh(job)
    assert jobs[-1]["state"] == jobs[-1]["stage"] == ("failed" if fail else "completed")
    assert reports._report_job_is_finished_refresh(jobs[-1])
    assert len([job for job in jobs if job["state"] in {"completed", "failed"}]) == 1
    key = reports._digest_cache_key(date(2026, 8, 17), date(2026, 8, 23))
    if fail:
        assert (1, key) not in runtime.cache
        assert (1, "reports_digest_latest") not in runtime.cache
    else:
        assert runtime.cache[1, key] == runtime.cache[1, "reports_digest_latest"]
        assert runtime.cache[1, key]["digest"]["rows"] == [{"sku": "SKU-1"}]
    assert runtime.refreshes == runtime.queue == []


def test_standalone_digest_build_keeps_five_positional_arguments(runtime):
    result = run_as_worker(tasks.build_digest_for_org, (1, "2026-08-17", "2026-08-23", False, None))
    assert result["state"] == "completed"
    for job in runtime.writes:
        assert "kind" not in job and "sync" not in job
    assert runtime.refreshes == runtime.queue == []
