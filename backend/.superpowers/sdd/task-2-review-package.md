# Review Package Task 2 Re-review 2
Base: f3f5766
Head: 339c574

## Commits
339c574 test: seed pnl cache in cash flow integration
5166fbe test: seed report cache prerequisites in task tests
0f40f90 test: isolate report cache guard from auth harness
c37014b feat: guard reports with source cache coverage

## Stat
 app/repricer_tasks.py                              | 18 +++++
 app/routers/wb_reports_bff.py                      | 70 ++++++++++++++++++++
 tests/test_one_c_cash_flow.py                      | 29 +++++++-
 .../test_report_materialization_from_data_mart.py  | 77 ++++++++++++++++++++++
 tests/test_repricer_tasks.py                       | 14 ++++
 tests/test_wb_reports_bff.py                       | 20 +++++-
 6 files changed, 226 insertions(+), 2 deletions(-)

## Diff
diff --git a/app/repricer_tasks.py b/app/repricer_tasks.py
index f6f606c..b0697a7 100644
--- a/app/repricer_tasks.py
+++ b/app/repricer_tasks.py
@@ -16,23 +16,31 @@ from app.repricer_execution import StrategyExecuteOptions, execute_all_assigned_
 from app.repricer_persistence.store import (
     append_execution_run,
     flush_repricer_bff_state,
     hydrate_repricer_bff_state,
     list_execution_runs,
     list_organization_ids,
     load_runtime_state,
 )
 from app.repricer_sync import get_wb_sync_status, is_wb_sync_running, record_wb_sync_history_event, refresh_wb_data_sources
 from app.repricer_bff import list_repricer_skus
+from app.report_data_mart import ReportSourceBundle
 from app.wb_api.client import RateLimitedWbApiClient, build_wb_client
 
 
+def _assert_report_sources_available(report_id: str, bundle: ReportSourceBundle) -> None:
+    if bundle.covered:
+        return
+    missing = bundle.missing_sources[0] if bundle.missing_sources else "partial_source_cache"
+    raise RuntimeError(f"source_cache_miss: {missing}")
+
+
 @celery_app.task(name="reports.build_digest_for_org", bind=True, max_retries=0)
 def build_digest_for_org(self, organization_id: int, date_from_iso: str, date_to_iso: str, finance_allowed: bool, wb_token: str | None) -> dict[str, Any]:
     """Build one exact digest range outside the request/response lifecycle."""
     from datetime import date as date_type
     from app.routers import wb_reports_bff as reports
 
     date_from = date_type.fromisoformat(date_from_iso)
     date_to = date_type.fromisoformat(date_to_iso)
     date_range = {"preset": "custom", "from": date_from_iso, "to": date_to_iso}
     job_key = reports._digest_job_cache_key(date_from, date_to)
@@ -70,20 +78,30 @@ def build_report_for_org(self, organization_id: int, user_id: str, report_id: st
     date_from = date_type.fromisoformat(date_from_iso)
     date_to = date_type.fromisoformat(date_to_iso)
     date_range = {"preset": "custom", "from": date_from_iso, "to": date_to_iso}
     job_key = reports._report_job_cache_key(report_id, date_from, date_to, group_by)
     cache_key = reports._report_cache_key(report_id, date_from, date_to, group_by, source)
     started_at = reports._utc_now_iso()
     def progress(stage: str, label: str, percent: int, state: str = "running") -> None:
         reports.save_source_cache(organization_id, job_key, {"state": state, "taskId": self.request.id, "reportId": report_id, "dateFrom": date_from_iso, "dateTo": date_to_iso, "groupBy": group_by, "stage": stage, "label": label, "percent": percent, "startedAt": started_at, "updatedAt": reports._utc_now_iso()})
     progress("queued", "Задача принята", 0)
     try:
+        required_sources = reports.REPORT_REQUIRED_SOURCES.get(report_id, ())
+        if required_sources:
+            bundle = reports.load_report_source_bundle(
+                organization_id=organization_id,
+                date_from=date_from,
+                date_to=date_to,
+                required_sources=required_sources,
+                get_cache=reports.get_source_cache,
+            )
+            _assert_report_sources_available(report_id, bundle)
         if report_id == "stock":
             progress("sources", "Загружаем остатки WB", 20)
             snapshot = reports.build_wb_reports_sources_snapshot(date_from=date_from, date_to=date_to, wb_token=wb_token, progress_callback=progress)
             report = reports._build_stock_report_payload(date_range, snapshot, organization_id=organization_id, wb_token=wb_token)
         elif report_id == "ads":
             progress("ads", "Загружаем рекламу WB", 20)
             report = reports._build_ads_report_payload(actor=SimpleNamespace(organization_id=organization_id, user_id=user_id), date_from=date_from, date_to=date_to, date_range=date_range, wb_token=wb_token, refresh=True)
         elif report_id == "rnp":
             progress("rnp", "Собираем воронку РНП", 20)
             payload = reports.build_rnp_report(date_from=date_from, date_to=date_to, group_by=group_by, finance_allowed=finance_allowed, organization_id=organization_id, wb_token=wb_token, force_refresh=True, progress_callback=progress)
diff --git a/app/routers/wb_reports_bff.py b/app/routers/wb_reports_bff.py
index a0ce385..bf9f8cf 100644
--- a/app/routers/wb_reports_bff.py
+++ b/app/routers/wb_reports_bff.py
@@ -7,20 +7,21 @@ from typing import Any, Literal
 from fastapi import APIRouter, Body, HTTPException, Query, Request
 
 from app.cabinet.store import get_user_wb_token_secret
 from app.cabinet.store import list_team_users
 from app.config import get_settings
 from app.control_plane.auth import actor_from_request, has_permission
 from app.control_plane.store import assert_permission_or_audit, record_audit_event
 from app.routers.one_c_cash_flow import get_cash_flow_for_period
 from app.reports_exports import ReportExportId, get_report_export_or_none, materialize_report_export, request_report_export
 from app.reports_history import ensure_daily_stock_history
+from app.report_data_mart import ReportSourceBundle, load_report_source_bundle
 from app.repricer_cache.store import get_source_cache, list_cached_goods, save_source_cache
 from app.wb_ads_cache.store import get_ads_report_cache, save_ads_history_snapshots, save_ads_report_cache
 from app.wb_api.ads_runtime import AdsAttributionSnapshot, build_ads_attribution_snapshot
 from app.wb_api.client import (
     RateLimitedWbApiClient,
     WbApiRequest,
     build_wb_analytics_client,
     build_wb_common_client,
     build_wb_marketplace_client,
     build_wb_supplies_client,
@@ -2160,20 +2161,28 @@ def _build_digest_payload(date_range: dict[str, str], source_snapshot: Any, ads_
 
 def _digest_cache_key(date_from: date, date_to: date) -> str:
     return f"reports_digest_{date_from.isoformat()}_{date_to.isoformat()}"
 
 
 def _digest_job_cache_key(date_from: date, date_to: date) -> str:
     return f"reports_digest_job_{date_from.isoformat()}_{date_to.isoformat()}"
 
 
 BACKGROUND_REPORT_IDS = {"abc", "rnp", "ads", "pnl", "stock", "week-over-week"}
+REPORT_REQUIRED_SOURCES: dict[str, tuple[str, ...]] = {
+    "abc": ("finance", "period_stats", "ads", "baskets", "stocks"),
+    "rnp": ("rnp_funnel", "ads"),
+    "pnl": ("finance", "ads"),
+    "ads": ("ads",),
+    "stock": ("stocks", "period_stats"),
+    "week-over-week": ("finance", "period_stats", "ads", "baskets", "stocks"),
+}
 BACKGROUND_REPORT_JOB_STALE_AFTER = timedelta(minutes=15)
 DIGEST_CACHE_TTL = timedelta(hours=24)
 REPORT_PAYLOAD_CACHE_TTL = timedelta(hours=24)
 
 
 def _report_cache_key(report_id: str, date_from: date, date_to: date, group_by: str, source: str) -> str:
     return f"reports_payload_{report_id}_{date_from.isoformat()}_{date_to.isoformat()}_{group_by}_{source}"
 
 
 def _report_job_cache_key(report_id: str, date_from: date, date_to: date, group_by: str) -> str:
@@ -2305,20 +2314,63 @@ def _empty_background_report(report_id: ReportId, date_range: dict[str, str], gr
     job = _report_job_for_response(job)
     return {
         "meta": _meta(report_id, report_id, "Отчёт ожидает фоновое обновление.", "operational", "stale"),
         "headline": "Отчёт ещё не собран для выбранного периода.",
         "filters": {"dateRange": date_range, "groupBy": group_by},
         "kpis": [], "chart": {"title": "Нет данных", "valueLabel": "-", "points": []}, "columns": [], "rows": [],
         "cache": {"status": "missing", "requestedRange": date_range}, "reportJob": job,
     }
 
 
+def _source_coverage_payload(bundle: ReportSourceBundle) -> list[dict[str, Any]]:
+    return [
+        {
+            "source": item.source,
+            "sourceKey": item.source_key,
+            "status": item.status,
+            "dateFrom": item.date_from,
+            "dateTo": item.date_to,
+            "fetchedAt": item.fetched_at,
+            "rowsCount": item.rows_count,
+            "error": item.error,
+        }
+        for item in bundle.by_source.values()
+    ]
+
+
+def _report_source_cache_miss_payload(
+    report_id: ReportId,
+    date_range: dict[str, str],
+    group_by: str,
+    bundle: ReportSourceBundle,
+    job: dict[str, Any],
+) -> dict[str, Any]:
+    return {
+        "meta": _meta(report_id, report_id, "Отчёт ожидает WB sync для выбранного периода.", "operational", "stale"),
+        "headline": "Для выбранного периода нет всех нужных source cache. Запустите WB sync или дождитесь расписания.",
+        "filters": {"dateRange": date_range, "groupBy": group_by},
+        "kpis": [],
+        "chart": {"title": "Нет данных", "valueLabel": "-", "points": []},
+        "columns": [],
+        "rows": [],
+        "cache": {
+            "status": "source_cache_miss",
+            "requestedRange": date_range,
+            "missingSources": bundle.missing_sources,
+            "sourceCoverage": _source_coverage_payload(bundle),
+            "syncStatus": bundle.sync_status,
+        },
+        "sourceCoverage": _source_coverage_payload(bundle),
+        "reportJob": _report_job_for_response(job),
+    }
+
+
 def _digest_plan_cache_key(month: str) -> str:
     return f"reports_digest_plan_{month}"
 
 
 def _apply_digest_plan(payload: dict[str, Any], plan: dict[str, Any]) -> None:
     company = plan.get("company") if isinstance(plan.get("company"), dict) else {}
     managers = plan.get("managers") if isinstance(plan.get("managers"), list) else []
     def kpi_value(kpi_id: str) -> int | None:
         item = next((candidate for candidate in payload.get("kpis", []) if candidate.get("id") == kpi_id), None)
         if not isinstance(item, dict):
@@ -2832,20 +2884,29 @@ def get_reports_by_id(
                 job = _completed_report_job_from_cache(report_id, date_from, date_to, groupBy, cached, job)
                 save_source_cache(actor.organization_id, _report_job_cache_key(report_id, date_from, date_to, groupBy), job)
             payload = dict(report)
             payload["cache"] = _report_payload_cache_meta(
                 cached,
                 date_range,
                 "stale" if job.get("state") in {"queued", "running", "waiting_1c"} else None,
             )
             payload["reportJob"] = job
             return payload
+        bundle = load_report_source_bundle(
+            organization_id=actor.organization_id,
+            date_from=date_from,
+            date_to=date_to,
+            required_sources=REPORT_REQUIRED_SOURCES.get(report_id, ()),
+            get_cache=get_source_cache,
+        )
+        if not bundle.covered:
+            return _report_source_cache_miss_payload(report_id, date_range, groupBy, bundle, job)
         return _empty_background_report(report_id, date_range, groupBy, job)
 
     if report_id in BACKGROUND_REPORT_IDS:
         cache_key = _report_cache_key(report_id, date_from, date_to, groupBy, source)
         cached = get_source_cache(actor.organization_id, cache_key, slim=False) or {}
         report = cached.get("report") if isinstance(cached.get("report"), dict) else None
         job = get_source_cache(actor.organization_id, _report_job_cache_key(report_id, date_from, date_to, groupBy), slim=False) or {
             "state": "idle", "reportId": report_id, "dateFrom": date_from.isoformat(), "dateTo": date_to.isoformat(), "groupBy": groupBy,
         }
         if report is not None:
@@ -2854,20 +2915,29 @@ def get_reports_by_id(
                 job = _completed_report_job_from_cache(report_id, date_from, date_to, groupBy, cached, job)
                 save_source_cache(actor.organization_id, _report_job_cache_key(report_id, date_from, date_to, groupBy), job)
             payload = dict(report)
             payload["cache"] = _report_payload_cache_meta(
                 cached,
                 date_range,
                 "stale" if job.get("state") in {"queued", "running", "waiting_1c"} else None,
             )
             payload["reportJob"] = job
             return payload
+        bundle = load_report_source_bundle(
+            organization_id=actor.organization_id,
+            date_from=date_from,
+            date_to=date_to,
+            required_sources=REPORT_REQUIRED_SOURCES.get(report_id, ()),
+            get_cache=get_source_cache,
+        )
+        if not bundle.covered:
+            return _report_source_cache_miss_payload(report_id, date_range, groupBy, bundle, job)
         return _empty_background_report(report_id, date_range, groupBy, job)
 
     if report_id == "stock":
         source_snapshot = build_wb_reports_sources_snapshot(date_from=date_from, date_to=date_to, wb_token=wb_token)
         return _build_stock_report_payload(
             date_range,
             source_snapshot,
             organization_id=actor.organization_id,
             wb_token=wb_token,
         )
diff --git a/tests/test_one_c_cash_flow.py b/tests/test_one_c_cash_flow.py
index 6cc7d04..5a28450 100644
--- a/tests/test_one_c_cash_flow.py
+++ b/tests/test_one_c_cash_flow.py
@@ -1,11 +1,11 @@
-from datetime import date
+from datetime import date, datetime, timezone
 
 from fastapi.testclient import TestClient
 from sqlalchemy import create_engine
 from sqlalchemy.orm import sessionmaker
 
 from app.main import create_app
 from tests.auth_helpers import auth_headers
 
 
 def client() -> TestClient:
@@ -122,20 +122,47 @@ def test_cash_flow_job_queue_roundtrip_and_pnl_attachment(tmp_path, monkeypatch)
     assert ready_payload["data"]["totals"]["operationalExpenseKopecks"] == 164_000
     assert ready_payload["data"]["totals"]["incomeKopecks"] == 515_000
     assert ready_payload["data"]["balances"]["closingBalanceKopecks"] == 130_000
     operational_articles = [
         row["article"]
         for row in ready_payload["data"]["rows"]
         if row["operationalExpense"]
     ]
     assert operational_articles == ["Аренда помещений", "Заработная плата", "Оплата поставщикам_расходники"]
 
+    fetched_at = datetime.now(timezone.utc).isoformat()
+    report_cache.update(
+        {
+            (1, "wb_sync_status"): {
+                "state": "completed",
+                "dateFrom": "2026-06-01",
+                "dateTo": "2026-06-30",
+                "periodDays": 30,
+                "periodCacheSuffix": "30",
+                "finishedAt": fetched_at,
+                "fetchedAt": fetched_at,
+            },
+            (1, "finance_30"): {
+                "dateFrom": "2026-06-01",
+                "dateTo": "2026-06-30",
+                "fetchedAt": fetched_at,
+                "aggregates": {},
+            },
+            (1, "ads_30"): {
+                "dateFrom": "2026-06-01",
+                "dateTo": "2026-06-30",
+                "fetchedAt": fetched_at,
+                "aggregates": {},
+            },
+        }
+    )
+
     from app import repricer_tasks
 
     repricer_tasks.build_report_for_org.run(
         1,
         "finance-viewer@vella.local",
         "pnl",
         "2026-06-01",
         "2026-06-30",
         "sku",
         "financial",
diff --git a/tests/test_report_materialization_from_data_mart.py b/tests/test_report_materialization_from_data_mart.py
new file mode 100644
index 0000000..aa8d6c5
--- /dev/null
+++ b/tests/test_report_materialization_from_data_mart.py
@@ -0,0 +1,77 @@
+from __future__ import annotations
+
+from types import SimpleNamespace
+
+import pytest
+
+from app import repricer_tasks
+from app.routers import wb_reports_bff
+
+
+def test_background_report_get_returns_source_cache_miss_without_live_wb(monkeypatch):
+    def fake_get_source_cache(_organization_id: int, key: str, *, slim: bool = False):
+        if key == "wb_sync_status":
+            return {"state": "completed", "dateFrom": "2026-07-01", "dateTo": "2026-07-07", "periodDays": 7, "periodCacheSuffix": "7"}
+        return {}
+
+    monkeypatch.setattr("app.routers.wb_reports_bff.get_source_cache", fake_get_source_cache)
+    monkeypatch.setattr(
+        wb_reports_bff,
+        "actor_from_request",
+        lambda _request: SimpleNamespace(organization_id=1, user_id="user-1"),
+    )
+    monkeypatch.setattr(wb_reports_bff, "assert_permission_or_audit", lambda **_kwargs: None)
+    monkeypatch.setattr(wb_reports_bff, "has_permission", lambda _actor, _permission: False)
+    monkeypatch.setattr(
+        "app.routers.wb_reports_bff.build_wb_reports_sources_snapshot",
+        lambda **_kwargs: pytest.fail("GET must not call WB source snapshot"),
+    )
+
+    payload = wb_reports_bff.get_reports_by_id(
+        SimpleNamespace(),
+        "stock",
+        preset="custom",
+        from_="2026-07-01",
+        to="2026-07-07",
+        groupBy="warehouse",
+    )
+
+    assert payload["cache"]["status"] == "source_cache_miss"
+    assert "stocks" in payload["cache"]["missingSources"]
+    assert payload["rows"] == []
+    assert payload["reportJob"]["state"] in {"idle", "stale", "failed"}
+
+
+def test_report_job_fails_fast_on_missing_source_cache(monkeypatch):
+    saved: dict[str, dict] = {}
+
+    def fake_get_source_cache(_organization_id: int, key: str, *, slim: bool = False):
+        if key == "wb_sync_status":
+            return {"state": "completed", "dateFrom": "2026-07-01", "dateTo": "2026-07-07", "periodDays": 7, "periodCacheSuffix": "7"}
+        return {}
+
+    monkeypatch.setattr(wb_reports_bff, "get_source_cache", fake_get_source_cache)
+    monkeypatch.setattr(wb_reports_bff, "save_source_cache", lambda _organization_id, key, payload: saved.__setitem__(key, payload))
+    monkeypatch.setattr(
+        wb_reports_bff,
+        "build_wb_reports_sources_snapshot",
+        lambda **_kwargs: pytest.fail("materialization job must not call WB source snapshot when cache is missing"),
+    )
+
+    with pytest.raises(RuntimeError, match="source_cache_miss"):
+        repricer_tasks.build_report_for_org.run(
+            1,
+            "user-1",
+            "stock",
+            "2026-07-01",
+            "2026-07-07",
+            "warehouse",
+            "operational",
+            True,
+            "wb-token",
+        )
+
+    failed_jobs = [payload for key, payload in saved.items() if key.startswith("reports_job_stock")]
+    assert failed_jobs
+    assert failed_jobs[-1]["state"] == "failed"
+    assert failed_jobs[-1]["error"] == "source_cache_miss: stocks"
diff --git a/tests/test_repricer_tasks.py b/tests/test_repricer_tasks.py
index 0efe8f2..c44bbb3 100644
--- a/tests/test_repricer_tasks.py
+++ b/tests/test_repricer_tasks.py
@@ -345,21 +345,35 @@ def test_scheduler_wb_sync_skips_stale_running_sync(monkeypatch):
     assert history_events[0]["decision"] == "skip"
     assert history_events[0]["reason"] == "wb_sync_stale"
     assert history_events[0]["intervalMinutes"] == 720
     assert history_events[0]["lastStatus"]["state"] == "stale"
 
 
 def test_pnl_report_task_waits_for_1c_before_building(monkeypatch):
     from app.routers import wb_reports_bff as reports
 
     saved_states: list[dict] = []
+    source_caches = {
+        "wb_sync_status": {
+            "state": "completed",
+            "dateFrom": "2026-05-01",
+            "dateTo": "2026-05-31",
+            "periodDays": 31,
+            "periodCacheSuffix": "31",
+        },
+        **{
+            source: {"dateFrom": "2026-05-01", "dateTo": "2026-05-31"}
+            for source in reports.REPORT_REQUIRED_SOURCES["pnl"]
+        },
+    }
     monkeypatch.setattr(reports, "get_cash_flow_for_period", lambda **_kwargs: {"status": "pending", "job_id": "cf_waiting"})
+    monkeypatch.setattr(reports, "get_source_cache", lambda _organization_id, key, **_kwargs: source_caches.get(key, {}))
     monkeypatch.setattr(reports, "save_source_cache", lambda _organization_id, _key, payload: saved_states.append(payload))
     monkeypatch.setattr(reports, "build_pnl_report", lambda **_kwargs: pytest.fail("P&L must not build before 1C is ready"))
 
     with pytest.raises(Retry):
         repricer_tasks.build_report_for_org.run(
             1,
             "finance@example.test",
             "pnl",
             "2026-05-01",
             "2026-05-31",
diff --git a/tests/test_wb_reports_bff.py b/tests/test_wb_reports_bff.py
index af8bc8a..ef5390b 100644
--- a/tests/test_wb_reports_bff.py
+++ b/tests/test_wb_reports_bff.py
@@ -494,29 +494,47 @@ def test_week_over_week_live_builder_uses_own_sources_not_abc_or_repricer(monkey
 
 
 def test_week_over_week_task_builds_current_and_previous_source_ranges(monkeypatch):
     from app import repricer_tasks
     from app.routers import wb_reports_bff
 
     calls: list[tuple[date, date]] = []
     saved: dict[str, dict] = {}
     snapshot = SimpleNamespace(source_status="fresh", orders=[], sales=[], stocks=[])
     ads = SimpleNamespace(rows=[])
+    fetched_at = datetime.now(timezone.utc).isoformat()
+    source_caches = {
+        "wb_sync_status": {
+            "state": "completed",
+            "dateFrom": "2026-07-07",
+            "dateTo": "2026-07-13",
+            "periodDays": 7,
+            "periodCacheSuffix": "7",
+        },
+        **{
+            source: {
+                "dateFrom": "2026-07-07",
+                "dateTo": "2026-07-13",
+                "fetchedAt": fetched_at,
+            }
+            for source in wb_reports_bff.REPORT_REQUIRED_SOURCES["week-over-week"]
+        },
+    }
     monkeypatch.setattr(
         wb_reports_bff,
         "build_wb_reports_sources_snapshot",
         lambda *, date_from, date_to, **_kwargs: (calls.append((date_from, date_to)) or snapshot),
     )
     monkeypatch.setattr(wb_reports_bff, "build_ads_attribution_snapshot", lambda **_kwargs: ads)
     monkeypatch.setattr(wb_reports_bff, "_build_week_over_week_payload", lambda *args, **_kwargs: {"meta": {"id": "week-over-week"}, "rows": []})
     monkeypatch.setattr(wb_reports_bff, "save_source_cache", lambda _organization_id, key, payload: saved.__setitem__(key, payload))
-    monkeypatch.setattr(wb_reports_bff, "get_source_cache", lambda *_args, **_kwargs: {})
+    monkeypatch.setattr(wb_reports_bff, "get_source_cache", lambda _organization_id, key, **_kwargs: source_caches.get(key, {}))
 
     result = repricer_tasks.build_report_for_org.run(
         1,
         "viewer",
         "week-over-week",
         "2026-07-07",
         "2026-07-13",
         "sku",
         "operational",
         False,
