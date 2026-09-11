"""Source refresh must hand off to a real Celery request with its own retry."""

from copy import deepcopy
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
