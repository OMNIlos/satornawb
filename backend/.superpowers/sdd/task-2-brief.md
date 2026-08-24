### Task 2: Cache-Only Report Materialization Guard

**Files:**
- Modify: `app/routers/wb_reports_bff.py`
- Modify: `app/repricer_tasks.py`
- Test: `tests/test_report_materialization_from_data_mart.py`

**Interfaces:**
- Consumes: `load_report_source_bundle(...) -> ReportSourceBundle` from Task 1.
- Produces: `REPORT_REQUIRED_SOURCES: dict[str, tuple[str, ...]]` in `app.routers.wb_reports_bff`.
- Produces: `_report_source_cache_miss_payload(report_id: ReportId, date_range: dict[str, str], group_by: str, bundle: ReportSourceBundle, job: dict[str, Any]) -> dict[str, Any]`.
- Produces: `_assert_report_sources_available(report_id: str, bundle: ReportSourceBundle) -> None` in `app.repricer_tasks`.

- [ ] **Step 1: Write failing tests for missing source caches**

Create `tests/test_report_materialization_from_data_mart.py`:

```python
from __future__ import annotations

from datetime import date

import pytest

from app import repricer_tasks
from app.routers import wb_reports_bff
from tests.test_app import auth_headers, client


def test_background_report_get_returns_source_cache_miss_without_live_wb(monkeypatch):
    def fake_get_source_cache(_organization_id: int, key: str, *, slim: bool = False):
        if key == "wb_sync_status":
            return {"state": "completed", "dateFrom": "2026-07-01", "dateTo": "2026-07-07", "periodDays": 7, "periodCacheSuffix": "7"}
        return {}

    monkeypatch.setattr("app.routers.wb_reports_bff.get_source_cache", fake_get_source_cache)
    monkeypatch.setattr(
        "app.routers.wb_reports_bff.build_wb_reports_sources_snapshot",
        lambda **_kwargs: pytest.fail("GET must not call WB source snapshot"),
    )

    api = client()
    response = api.get(
        "/api/wb/reports/stock?preset=custom&from=2026-07-01&to=2026-07-07&groupBy=warehouse",
        headers=auth_headers(api, "viewer"),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["cache"]["status"] == "source_cache_miss"
    assert "stocks" in payload["cache"]["missingSources"]
    assert payload["rows"] == []
    assert payload["reportJob"]["state"] in {"idle", "stale", "failed"}


def test_report_job_fails_fast_on_missing_source_cache(monkeypatch):
    saved: dict[str, dict] = {}

    def fake_get_source_cache(_organization_id: int, key: str, *, slim: bool = False):
        if key == "wb_sync_status":
            return {"state": "completed", "dateFrom": "2026-07-01", "dateTo": "2026-07-07", "periodDays": 7, "periodCacheSuffix": "7"}
        return {}

    monkeypatch.setattr(wb_reports_bff, "get_source_cache", fake_get_source_cache)
    monkeypatch.setattr(wb_reports_bff, "save_source_cache", lambda _organization_id, key, payload: saved.__setitem__(key, payload))
    monkeypatch.setattr(
        wb_reports_bff,
        "build_wb_reports_sources_snapshot",
        lambda **_kwargs: pytest.fail("materialization job must not call WB source snapshot when cache is missing"),
    )

    with pytest.raises(RuntimeError, match="source_cache_miss"):
        repricer_tasks.build_report_for_org.run(
            1,
            "user-1",
            "stock",
            "2026-07-01",
            "2026-07-07",
            "warehouse",
            "operational",
            True,
            "wb-token",
        )

    failed_jobs = [payload for key, payload in saved.items() if key.startswith("reports_job_stock")]
    assert failed_jobs
    assert failed_jobs[-1]["state"] == "failed"
    assert failed_jobs[-1]["error"] == "source_cache_miss: stocks"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest -q tests/test_report_materialization_from_data_mart.py`

Expected: FAIL because `wb_reports_bff` does not yet expose `source_cache_miss` for background report GET and `build_report_for_org` still reaches live builder branches.

- [ ] **Step 3: Add required source mapping and miss payload**

In `app/routers/wb_reports_bff.py`, import Task 1 types:

```python
from app.report_data_mart import ReportSourceBundle, load_report_source_bundle
```

Add near `BACKGROUND_REPORT_IDS`:

```python
REPORT_REQUIRED_SOURCES: dict[str, tuple[str, ...]] = {
    "abc": ("finance", "period_stats", "ads", "baskets", "stocks"),
    "rnp": ("rnp_funnel", "ads"),
    "pnl": ("finance", "ads"),
    "ads": ("ads",),
    "stock": ("stocks", "period_stats"),
    "week-over-week": ("finance", "period_stats", "ads", "baskets", "stocks"),
}
```

Add helper:

```python
def _source_coverage_payload(bundle: ReportSourceBundle) -> list[dict[str, Any]]:
    return [
        {
            "source": item.source,
            "sourceKey": item.source_key,
            "status": item.status,
            "dateFrom": item.date_from,
            "dateTo": item.date_to,
            "fetchedAt": item.fetched_at,
            "rowsCount": item.rows_count,
            "error": item.error,
        }
        for item in bundle.by_source.values()
    ]


def _report_source_cache_miss_payload(
    report_id: ReportId,
    date_range: dict[str, str],
    group_by: str,
    bundle: ReportSourceBundle,
    job: dict[str, Any],
) -> dict[str, Any]:
    return {
        "meta": _meta(report_id, report_id, "Отчёт ожидает WB sync для выбранного периода.", "operational", "stale"),
        "headline": "Для выбранного периода нет всех нужных source cache. Запустите WB sync или дождитесь расписания.",
        "filters": {"dateRange": date_range, "groupBy": group_by},
        "kpis": [],
        "chart": {"title": "Нет данных", "valueLabel": "-", "points": []},
        "columns": [],
        "rows": [],
        "cache": {
            "status": "source_cache_miss",
            "requestedRange": date_range,
            "missingSources": bundle.missing_sources,
            "sourceCoverage": _source_coverage_payload(bundle),
            "syncStatus": bundle.sync_status,
        },
        "sourceCoverage": _source_coverage_payload(bundle),
        "reportJob": _report_job_for_response(job),
    }
```

- [ ] **Step 4: Use source coverage in background report GET**

In `get_reports_by_id`, inside the `if report_id in BACKGROUND_REPORT_IDS:` branch and before `_empty_background_report(...)`, add:

```python
        bundle = load_report_source_bundle(
            organization_id=actor.organization_id,
            date_from=date_from,
            date_to=date_to,
            required_sources=REPORT_REQUIRED_SOURCES.get(report_id, ()),
        )
        if not bundle.covered:
            return _report_source_cache_miss_payload(report_id, date_range, groupBy, bundle, job)
```

For `week-over-week`, keep the existing branch but add the same bundle check before returning `_empty_background_report(...)`.

- [ ] **Step 5: Fail fast in the Celery report task**

In `app/repricer_tasks.py`, inside `build_report_for_org` after `progress("queued", "Задача принята", 0)`, add:

```python
        required_sources = reports.REPORT_REQUIRED_SOURCES.get(report_id, ())
        if required_sources:
            bundle = reports.load_report_source_bundle(
                organization_id=organization_id,
                date_from=date_from,
                date_to=date_to,
                required_sources=required_sources,
            )
            if not bundle.covered:
                missing = ", ".join(bundle.missing_sources) or "partial_source_cache"
                raise RuntimeError(f"source_cache_miss: {missing}")
```

Keep the existing `except Exception as exc:` path so the job saves `state = failed`.

- [ ] **Step 6: Run tests to verify they pass**

Run: `pytest -q tests/test_report_materialization_from_data_mart.py tests/test_report_data_mart.py`

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add app/routers/wb_reports_bff.py app/repricer_tasks.py tests/test_report_materialization_from_data_mart.py
git commit -m "feat: guard reports with source cache coverage"
```

---

