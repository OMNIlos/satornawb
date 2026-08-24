### Task 4: Hot Range Prewarm After WB Sync

**Files:**
- Create: `app/report_prewarm.py`
- Modify: `app/repricer_sync.py`
- Test: `tests/test_report_prewarm.py`

**Interfaces:**
- Consumes: `_report_job_cache_key` and `_report_cache_key` from `app.routers.wb_reports_bff`.
- Produces: `HOT_REPORT_IDS: tuple[str, ...]`.
- Produces: `HOT_RANGE_DAYS: tuple[int, ...]`.
- Produces: `prewarm_report_payloads(organization_id: int, user_id: str, sync_status: Mapping[str, Any], finance_allowed: bool, wb_token: str | None, enqueue: Callable[..., Any]) -> list[dict[str, Any]]`.

- [ ] **Step 1: Write failing prewarm tests**

Create `tests/test_report_prewarm.py`:

```python
from __future__ import annotations

from app.report_prewarm import prewarm_report_payloads


def test_prewarm_enqueues_hot_reports_and_ranges():
    calls: list[tuple] = []
    sync_status = {
        "state": "completed",
        "dateFrom": "2026-07-01",
        "dateTo": "2026-07-30",
        "periodDays": 30,
        "periodCacheSuffix": "30",
    }

    result = prewarm_report_payloads(
        organization_id=1,
        user_id="sync",
        sync_status=sync_status,
        finance_allowed=True,
        wb_token="token",
        enqueue=lambda *args: calls.append(args) or type("Task", (), {"id": f"task-{len(calls)}"})(),
    )

    report_ids = {item["reportId"] for item in result}
    assert {"abc", "rnp", "pnl", "ads", "stock", "week-over-week"} <= report_ids
    assert any(item["dateFrom"] == "2026-07-24" and item["dateTo"] == "2026-07-30" for item in result)
    assert any(item["dateFrom"] == "2026-07-01" and item["dateTo"] == "2026-07-30" for item in result)
    assert calls
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest -q tests/test_report_prewarm.py`

Expected: FAIL with `ModuleNotFoundError: No module named 'app.report_prewarm'`.

- [ ] **Step 3: Implement prewarm helper**

Create `app/report_prewarm.py`:

```python
from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Callable, Mapping

HOT_REPORT_IDS = ("abc", "rnp", "pnl", "ads", "stock", "week-over-week")
HOT_RANGE_DAYS = (1, 7, 14, 30)


def _date_or_none(value: Any) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def _hot_ranges(sync_status: Mapping[str, Any]) -> list[tuple[date, date]]:
    date_from = _date_or_none(sync_status.get("dateFrom"))
    date_to = _date_or_none(sync_status.get("dateTo"))
    if date_from is None or date_to is None or date_to < date_from:
        return []
    ranges: list[tuple[date, date]] = []
    for days in HOT_RANGE_DAYS:
        start = max(date_from, date_to - timedelta(days=days - 1))
        ranges.append((start, date_to))
    ranges.append((date_from, date_to))
    return list(dict.fromkeys(ranges))


def _group_by(report_id: str) -> str:
    return "warehouse" if report_id == "stock" else "campaign" if report_id == "ads" else "sku"


def prewarm_report_payloads(
    *,
    organization_id: int,
    user_id: str,
    sync_status: Mapping[str, Any],
    finance_allowed: bool,
    wb_token: str | None,
    enqueue: Callable[..., Any],
) -> list[dict[str, Any]]:
    queued: list[dict[str, Any]] = []
    for start, end in _hot_ranges(sync_status):
        for report_id in HOT_REPORT_IDS:
            group_by = _group_by(report_id)
            source = "financial" if report_id == "pnl" else "operational"
            task = enqueue(
                organization_id,
                user_id,
                report_id,
                start.isoformat(),
                end.isoformat(),
                group_by,
                source,
                finance_allowed,
                wb_token,
            )
            queued.append(
                {
                    "reportId": report_id,
                    "dateFrom": start.isoformat(),
                    "dateTo": end.isoformat(),
                    "groupBy": group_by,
                    "source": source,
                    "taskId": getattr(task, "id", None),
                }
            )
    return queued
```

- [ ] **Step 4: Hook prewarm after successful sync**

In `app/repricer_sync.py`, do not import Celery at module import time. Add a small optional callback parameter to `refresh_wb_data_sources`:

```python
def refresh_wb_data_sources(
    organization_id: int,
    wb_token: str | None = None,
    scenario: str = "complete",
    period_days: int | None = None,
    date_from: date | datetime | None = None,
    date_to: date | datetime | None = None,
    trigger: str = "manual",
    force: bool = False,
    execute_lock: bool = True,
    sources: list[str] | None = None,
    _progress_callback: Any | None = None,
    _prewarm_callback: Any | None = None,
) -> dict[str, Any]:
```

After `state = "completed" if ...`, before returning, add:

```python
        result_payload = finish_wb_sync(organization_id, status, state=state, steps=steps) if execute_lock else {"state": state, "steps": steps, **status}
        if state == "completed":
            callback = _prewarm_callback
            if callback is None:
                from app.report_prewarm import prewarm_report_payloads
                from app.repricer_tasks import build_report_for_org

                callback = lambda sync_payload: prewarm_report_payloads(
                    organization_id=organization_id,
                    user_id="wb-sync",
                    sync_status=sync_payload,
                    finance_allowed=True,
                    wb_token=wb_token,
                    enqueue=build_report_for_org.delay,
                )
            try:
                result_payload["reportPrewarm"] = callback(result_payload)
            except Exception as exc:
                result_payload["reportPrewarm"] = {"state": "failed", "error": str(exc)[:500]}
        return result_payload
```

Remove or replace the existing direct return at the end of the `try` block.

- [ ] **Step 5: Add sync hook test**

Append to `tests/test_report_prewarm.py`:

```python
def test_refresh_wb_data_sources_calls_prewarm_callback(monkeypatch):
    from app import repricer_sync

    monkeypatch.setattr("app.repricer_sync.start_wb_sync", lambda organization_id, trigger, period_days: {"runId": "sync-1", "trigger": trigger})
    monkeypatch.setattr("app.repricer_sync.finish_wb_sync", lambda _organization_id, status, state, steps, error=None: {"state": state, "steps": steps, **status})
    monkeypatch.setattr("app.repricer_sync.fetch_stock_aggregates", lambda *_args, **_kwargs: {})
    monkeypatch.setattr("app.repricer_sync.save_source_cache", lambda _organization_id, _key, payload: payload)
    monkeypatch.setattr("app.repricer_sync.get_source_cache", lambda *_args, **_kwargs: {})

    prewarm_calls: list[dict] = []
    result = repricer_sync.refresh_wb_data_sources(
        organization_id=1,
        wb_token="token",
        sources=["stocks"],
        execute_lock=True,
        _prewarm_callback=lambda payload: prewarm_calls.append(payload) or [{"reportId": "stock"}],
    )

    assert result["state"] == "completed"
    assert result["reportPrewarm"] == [{"reportId": "stock"}]
    assert prewarm_calls[0]["state"] == "completed"
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `pytest -q tests/test_report_prewarm.py`

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add app/report_prewarm.py app/repricer_sync.py tests/test_report_prewarm.py
git commit -m "feat: prewarm report payloads after wb sync"
```

---

