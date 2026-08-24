# Final Backend Review Package Re-review
Repo: D:\ogni-elfs
Base: d639cc9
Head: 97b0020

## Commits
97b0020 fix: harden report prewarm cache safety
d1e74e3 docs: note abc report data mart follow up
535f422 fix: restrict report prewarm coverage
62ab4bc feat: prewarm report payloads after wb sync
e28042d fix: preserve cached report metric semantics
ec2068d fix: cover cached report source ranges
01171d4 feat: materialize reports from wb sync cache
339c574 test: seed pnl cache in cash flow integration
5166fbe test: seed report cache prerequisites in task tests
0f40f90 test: isolate report cache guard from auth harness
c37014b feat: guard reports with source cache coverage
f3f5766 feat: add report data mart coverage reader
369a498 chore: ignore superpowers scratch files

## Stat
 .gitignore                                         |   1 +
 app/report_data_mart.py                            | 177 +++++++++
 app/report_prewarm.py                              | 112 ++++++
 app/repricer_sync.py                               |  34 +-
 app/repricer_tasks.py                              |  80 +++--
 app/routers/wb_reports_bff.py                      | 396 ++++++++++++++++++++-
 .../2026-07-15-wb-sync-report-data-mart-design.md  |   8 +
 tests/test_one_c_cash_flow.py                      |  29 +-
 tests/test_report_data_mart.py                     | 127 +++++++
 .../test_report_materialization_from_data_mart.py  | 244 +++++++++++++
 tests/test_report_prewarm.py                       | 163 +++++++++
 tests/test_repricer_tasks.py                       |  14 +
 tests/test_wb_reports_bff.py                       | 100 +++++-
 13 files changed, 1434 insertions(+), 51 deletions(-)

## Diff
diff --git a/.gitignore b/.gitignore
index 98358dd..8094c99 100644
--- a/.gitignore
+++ b/.gitignore
@@ -9,8 +9,9 @@ venv/
 .env
 .env.*
 !.env.example
 dist/
 build/
 *.egg-info/
 var/1c_cash_flow_jobs.json
 var/1c_cash_flow_logs.json
+.superpowers/
diff --git a/app/report_data_mart.py b/app/report_data_mart.py
new file mode 100644
index 0000000..f686b68
--- /dev/null
+++ b/app/report_data_mart.py
@@ -0,0 +1,177 @@
+from __future__ import annotations
+
+from dataclasses import dataclass
+from datetime import date, datetime, timedelta, timezone
+from typing import Any, Callable, Iterable, Literal, Mapping
+
+from app.repricer_cache.store import get_source_cache
+
+SourceStatus = Literal["exact", "covering", "stale", "partial", "missing"]
+BundleStatus = Literal["covered", "partial", "source_cache_miss"]
+
+SOURCE_CACHE_TTL = timedelta(hours=24)
+
+
+@dataclass(frozen=True)
+class SourceCoverage:
+    source: str
+    source_key: str
+    status: SourceStatus
+    date_from: str | None = None
+    date_to: str | None = None
+    fetched_at: str | None = None
+    rows_count: int | None = None
+    error: str | None = None
+
+
+@dataclass(frozen=True)
+class ReportSourceBundle:
+    organization_id: int
+    date_from: date
+    date_to: date
+    status: BundleStatus
+    covered: bool
+    by_source: dict[str, SourceCoverage]
+    sources: dict[str, dict[str, Any]]
+    missing_sources: list[str]
+    sync_status: dict[str, Any]
+
+
+def _parse_date(value: Any) -> date | None:
+    if not value:
+        return None
+    try:
+        return date.fromisoformat(str(value)[:10])
+    except ValueError:
+        return None
+
+
+def _parse_datetime(value: Any) -> datetime | None:
+    if not value:
+        return None
+    try:
+        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
+    except ValueError:
+        return None
+    if parsed.tzinfo is None:
+        return parsed.replace(tzinfo=timezone.utc)
+    return parsed.astimezone(timezone.utc)
+
+
+def source_cache_matches_range(cache: Mapping[str, Any], date_from: date, date_to: date) -> bool:
+    return _parse_date(cache.get("dateFrom")) == date_from and _parse_date(cache.get("dateTo")) == date_to
+
+
+def source_cache_covers_range(cache: Mapping[str, Any], date_from: date, date_to: date) -> bool:
+    cached_from = _parse_date(cache.get("dateFrom"))
+    cached_to = _parse_date(cache.get("dateTo"))
+    return cached_from is not None and cached_to is not None and cached_from <= date_from and cached_to >= date_to
+
+
+def _is_stale(cache: Mapping[str, Any], *, now: datetime | None = None) -> bool:
+    fetched_at = _parse_datetime(cache.get("fetchedAt") or cache.get("finishedAt") or cache.get("completedAt"))
+    if fetched_at is None:
+        return False
+    current = now or datetime.now(timezone.utc)
+    return current - fetched_at > SOURCE_CACHE_TTL
+
+
+def _range_days(date_from: date, date_to: date) -> int:
+    return max(1, (date_to - date_from).days + 1)
+
+
+def _candidate_keys(source: str, date_from: date, date_to: date, sync_status: Mapping[str, Any]) -> list[str]:
+    days = _range_days(date_from, date_to)
+    keys = [f"{source}_{date_from.isoformat()}_{date_to.isoformat()}"]
+    suffix = str(sync_status.get("periodCacheSuffix") or "").strip()
+    if suffix:
+        keys.append(f"{source}_{suffix}")
+    keys.append(f"{source}_{days}")
+    keys.append(source)
+    return list(dict.fromkeys(keys))
+
+
+def _row_count(cache: Mapping[str, Any]) -> int | None:
+    raw_count = cache.get("count")
+    if isinstance(raw_count, int):
+        return raw_count
+    aggregates = cache.get("aggregates")
+    if isinstance(aggregates, dict):
+        return len(aggregates)
+    rows = cache.get("rows")
+    if isinstance(rows, list):
+        return len(rows)
+    return None
+
+
+def load_report_source_bundle(
+    *,
+    organization_id: int,
+    date_from: date,
+    date_to: date,
+    required_sources: Iterable[str],
+    get_cache: Callable[..., dict[str, Any] | None] = get_source_cache,
+) -> ReportSourceBundle:
+    sync_status = get_cache(organization_id, "wb_sync_status", slim=False) or {}
+    by_source: dict[str, SourceCoverage] = {}
+    sources: dict[str, dict[str, Any]] = {}
+    missing_sources: list[str] = []
+
+    for source in required_sources:
+        selected_key = source
+        selected_cache: dict[str, Any] | None = None
+        selected_status: SourceStatus = "missing"
+        for key in _candidate_keys(source, date_from, date_to, sync_status):
+            cache = get_cache(organization_id, key, slim=False) or {}
+            if not cache:
+                continue
+            selected_key = key
+            selected_cache = cache
+            snapshot_fetched_at = _parse_datetime(cache.get("fetchedAt") or cache.get("finishedAt") or cache.get("completedAt"))
+            if source == "stocks" and key == "stocks" and snapshot_fetched_at is not None:
+                selected_status = "exact"
+                break
+            if source_cache_matches_range(cache, date_from, date_to):
+                selected_status = "exact"
+                break
+            selected_status = "partial"
+
+        if selected_cache is None:
+            missing_sources.append(source)
+            by_source[source] = SourceCoverage(source=source, source_key=selected_key, status="missing")
+            continue
+
+        if selected_status in {"exact", "covering"} and _is_stale(selected_cache):
+            selected_status = "stale"
+        sources[source] = selected_cache
+        by_source[source] = SourceCoverage(
+            source=source,
+            source_key=selected_key,
+            status=selected_status,
+            date_from=str(selected_cache.get("dateFrom")) if selected_cache.get("dateFrom") else None,
+            date_to=str(selected_cache.get("dateTo")) if selected_cache.get("dateTo") else None,
+            fetched_at=str(selected_cache.get("fetchedAt")) if selected_cache.get("fetchedAt") else None,
+            rows_count=_row_count(selected_cache),
+            error=str(selected_cache.get("error")) if selected_cache.get("error") else None,
+        )
+        if selected_status == "missing":
+            missing_sources.append(source)
+
+    if missing_sources:
+        status: BundleStatus = "source_cache_miss"
+    elif any(item.status in {"stale", "partial"} for item in by_source.values()):
+        status = "partial"
+    else:
+        status = "covered"
+
+    return ReportSourceBundle(
+        organization_id=organization_id,
+        date_from=date_from,
+        date_to=date_to,
+        status=status,
+        covered=status == "covered",
+        by_source=by_source,
+        sources=sources,
+        missing_sources=missing_sources,
+        sync_status=sync_status,
+    )
diff --git a/app/report_prewarm.py b/app/report_prewarm.py
new file mode 100644
index 0000000..a1318e7
--- /dev/null
+++ b/app/report_prewarm.py
@@ -0,0 +1,112 @@
+from __future__ import annotations
+
+from datetime import date, timedelta
+from typing import Any, Callable, Mapping
+
+from app.report_data_mart import load_report_source_bundle
+from app.repricer_cache.store import get_source_cache
+
+
+# Keep automatic prewarm limited to proven cache-only materializers. ABC, RNP, P&L,
+# Ads, and digest need dedicated cache-only/permission-safe materializers first.
+PREWARM_REPORTS: dict[str, dict[str, Any]] = {
+    "stock": {
+        "group_by": "warehouse",
+        "source": "operational",
+        "required_sources": ("stocks", "period_stats"),
+    },
+    "week-over-week": {
+        "group_by": "sku",
+        "source": "operational",
+        "required_sources": ("finance", "period_stats", "ads", "baskets", "stocks"),
+    },
+}
+HOT_REPORT_IDS = tuple(PREWARM_REPORTS)
+HOT_RANGE_DAYS = (1, 7, 14, 30)
+DEDUPED_JOB_STATES = {"queued", "running", "completed"}
+
+
+def _date_or_none(value: Any) -> date | None:
+    if not value:
+        return None
+    try:
+        return date.fromisoformat(str(value)[:10])
+    except ValueError:
+        return None
+
+
+def _hot_ranges(sync_status: Mapping[str, Any]) -> list[tuple[date, date]]:
+    date_from = _date_or_none(sync_status.get("dateFrom"))
+    date_to = _date_or_none(sync_status.get("dateTo"))
+    if date_from is None or date_to is None or date_to < date_from:
+        return []
+    ranges: list[tuple[date, date]] = []
+    for days in HOT_RANGE_DAYS:
+        start = max(date_from, date_to - timedelta(days=days - 1))
+        ranges.append((start, date_to))
+    ranges.append((date_from, date_to))
+    return list(dict.fromkeys(ranges))
+
+
+def _report_cache_key(report_id: str, date_from: date, date_to: date, group_by: str, source: str) -> str:
+    return f"reports_payload_{report_id}_{date_from.isoformat()}_{date_to.isoformat()}_{group_by}_{source}"
+
+
+def _report_job_cache_key(report_id: str, date_from: date, date_to: date, group_by: str) -> str:
+    return f"reports_job_{report_id}_{date_from.isoformat()}_{date_to.isoformat()}_{group_by}"
+
+
+def prewarm_report_payloads(
+    *,
+    organization_id: int,
+    user_id: str,
+    sync_status: Mapping[str, Any],
+    finance_allowed: bool,
+    wb_token: str | None,
+    enqueue: Callable[..., Any],
+    get_cache: Callable[..., dict[str, Any] | None] = get_source_cache,
+) -> list[dict[str, Any]]:
+    queued: list[dict[str, Any]] = []
+    for start, end in _hot_ranges(sync_status):
+        for report_id in HOT_REPORT_IDS:
+            config = PREWARM_REPORTS[report_id]
+            group_by = str(config["group_by"])
+            source = str(config["source"])
+            payload_key = _report_cache_key(report_id, start, end, group_by, source)
+            if get_cache(organization_id, payload_key, slim=False):
+                continue
+            job_key = _report_job_cache_key(report_id, start, end, group_by)
+            job = get_cache(organization_id, job_key, slim=False) or {}
+            if job.get("state") in DEDUPED_JOB_STATES:
+                continue
+            bundle = load_report_source_bundle(
+                organization_id=organization_id,
+                date_from=start,
+                date_to=end,
+                required_sources=config["required_sources"],
+                get_cache=get_cache,
+            )
+            if not bundle.covered:
+                continue
+            task = enqueue(
+                organization_id,
+                user_id,
+                report_id,
+                start.isoformat(),
+                end.isoformat(),
+                group_by,
+                source,
+                finance_allowed,
+                wb_token,
+            )
+            queued.append(
+                {
+                    "reportId": report_id,
+                    "dateFrom": start.isoformat(),
+                    "dateTo": end.isoformat(),
+                    "groupBy": group_by,
+                    "source": source,
+                    "taskId": getattr(task, "id", None),
+                }
+            )
+    return queued
diff --git a/app/repricer_sync.py b/app/repricer_sync.py
index 98d7947..18adc7d 100644
--- a/app/repricer_sync.py
+++ b/app/repricer_sync.py
@@ -45,16 +45,17 @@ except Exception:  # pragma: no cover - httpx is a runtime dependency, kept defe
     httpx = None  # type: ignore[assignment]
 
 
 SYNC_STATUS_KEY = "wb_sync_status"
 SYNC_HISTORY_KEY = "wb_sync_history"
 SYNC_STALE_AFTER_MINUTES = 30
 SYNC_EMPTY_RUNNING_STALE_AFTER_SECONDS = 90
 SYNC_DEFAULT_SOURCES = ("goods", "content", "promotions", "stocks", "period-stats", "finance", "ads", "baskets")
+REPORT_PREWARM_REQUIRED_SOURCES = frozenset({"stocks", "period-stats", "finance", "ads", "baskets"})
 EXTERNAL_SPP_BATCH_SIZE = 100
 EXTERNAL_SPP_BATCH_INTERVAL_SECONDS = 10.0
 logger = logging.getLogger(__name__)
 
 
 def _good_article_id(good: dict[str, Any]) -> str:
     return str(good.get("vendorCode") or good.get("articleId") or "").strip()
 
@@ -662,16 +663,17 @@ def refresh_wb_data_sources(
     date_to: date | None = None,
     trigger: str = "manual",
     force: bool = False,
     execute_lock: bool = True,
     sources: list[str] | tuple[str, ...] | set[str] | None = None,
     initial_status: dict[str, Any] | None = None,
     token_fingerprint: str | None = None,
     _progress_callback: Callable[[dict[str, Any]], None] | None = None,
+    _prewarm_callback: Any | None = None,
     _parallelize: bool = True,
 ) -> dict[str, Any]:
     resolved_sources = _normalize_sources(sources)
     resolved_token_fingerprint = token_fingerprint or wb_token_fingerprint(wb_token)
     range_start, range_end, resolved_period_days = _normalize_period_range(period_days, date_from=date_from, date_to=date_to)
     period_suffix = _period_cache_suffix(period_days, date_from=date_from, date_to=date_to)
     status = initial_status if initial_status is not None else (
         begin_wb_sync(
@@ -701,16 +703,41 @@ def refresh_wb_data_sources(
         trigger,
         resolved_period_days,
         ",".join(resolved_sources),
         resolved_token_fingerprint or "none",
     )
     steps: list[dict[str, Any]] = []
     fatal_error: str | None = None
 
+    def with_report_prewarm(result_payload: dict[str, Any]) -> dict[str, Any]:
+        if result_payload.get("state") != "completed":
+            return result_payload
+        callback = _prewarm_callback
+        if callback is None:
+            if not execute_lock or not REPORT_PREWARM_REQUIRED_SOURCES.issubset(resolved_sources):
+                return result_payload
+            from app.report_prewarm import prewarm_report_payloads
+            from app.repricer_tasks import build_report_for_org
+
+            callback = lambda sync_payload: prewarm_report_payloads(
+                organization_id=organization_id,
+                user_id="wb-sync",
+                sync_status=sync_payload,
+                finance_allowed=True,
+                wb_token=wb_token,
+                enqueue=build_report_for_org.delay,
+                get_cache=get_source_cache,
+            )
+        try:
+            result_payload["reportPrewarm"] = callback(result_payload)
+        except Exception as exc:
+            result_payload["reportPrewarm"] = {"state": "failed", "error": str(exc)[:500]}
+        return result_payload
+
     source_progress_copy: dict[str, tuple[str, str]] = {
         "goods": ("Запрашиваем каталог товаров WB", "WB API · каталог товаров"),
         "content": ("Получаем карточки товаров", "WB API · карточки контента"),
         "promotions": ("Получаем акции и скидки", "WB API · календарь акций"),
         "stocks": ("Загружаем остатки по складам", "WB API · отчёт по остаткам"),
         "period-stats": ("Получаем заказы и продажи за период", "WB API · статистика периода"),
         "finance": ("Загружаем финансовый отчёт", "WB API · детализация финансов"),
         "ads": ("Получаем расходы на рекламу", "WB API · статистика рекламы"),
@@ -816,16 +843,17 @@ def refresh_wb_data_sources(
                 date_to=date_to,
                 trigger=trigger,
                 force=force,
                 execute_lock=False,
                 sources=[source],
                 initial_status=status,
                 token_fingerprint=resolved_token_fingerprint,
                 _progress_callback=receive_progress,
+                _prewarm_callback=lambda _sync_payload: [],
                 _parallelize=False,
             )
 
         independent = [
             source
             for source in resolved_sources
             if source in {"goods", "content", "promotions", "stocks", "period-stats", "ads"}
         ]
@@ -836,21 +864,22 @@ def refresh_wb_data_sources(
             futures = {source: executor.submit(run_one, source) for source in independent}
             if "goods" in futures:
                 futures["goods"].result()
             futures.update({source: executor.submit(run_one, source) for source in dependent})
             for future in futures.values():
                 future.result()
 
         state_value = "completed" if not any(step.get("status") == "error" for step in ordered_steps) else "partial"
-        return (
+        result_payload = (
             finish_wb_sync(organization_id, status, state=state_value, steps=ordered_steps)
             if execute_lock
             else {"state": state_value, "steps": ordered_steps, **status}
         )
+        return with_report_prewarm(result_payload)
 
     try:
         if "goods" in resolved_sources:
             step = start_step("goods")
             try:
                 previous_goods = list_cached_goods(organization_id)
                 fetched_goods: list[dict[str, Any]] = []
                 total_saved = 0
@@ -1050,15 +1079,16 @@ def refresh_wb_data_sources(
                     )
                     save_source_cache(organization_id, f"baskets_{period_suffix}", payload)
                     released_warmup_count = _release_warmup_goods_by_baskets(cached_goods, payload)
                     finish_step(step, _step_ok("baskets", count=int(payload.get("count") or 0), requestedNmIds=payload.get("requestedNmIds"), matchedNmIds=payload.get("matchedNmIds"), releasedWarmupCount=released_warmup_count))
             except Exception as exc:
                 finish_step(step, _step_error("baskets", exc))
 
         state = "completed" if not any(step.get("status") == "error" for step in steps) else "partial"
-        return finish_wb_sync(organization_id, status, state=state, steps=steps) if execute_lock else {"state": state, "steps": steps, **status}
+        result_payload = finish_wb_sync(organization_id, status, state=state, steps=steps) if execute_lock else {"state": state, "steps": steps, **status}
+        return with_report_prewarm(result_payload)
     except Exception as exc:
         fatal_error = str(exc)
         raise
     finally:
         if fatal_error and execute_lock:
             finish_wb_sync(organization_id, status, state="failed", steps=steps, error=fatal_error)
diff --git a/app/repricer_tasks.py b/app/repricer_tasks.py
index f6f606c..2700f72 100644
--- a/app/repricer_tasks.py
+++ b/app/repricer_tasks.py
@@ -18,19 +18,27 @@ from app.repricer_persistence.store import (
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
@@ -72,23 +80,46 @@ def build_report_for_org(self, organization_id: int, user_id: str, report_id: st
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
-            progress("sources", "Загружаем остатки WB", 20)
-            snapshot = reports.build_wb_reports_sources_snapshot(date_from=date_from, date_to=date_to, wb_token=wb_token, progress_callback=progress)
-            report = reports._build_stock_report_payload(date_range, snapshot, organization_id=organization_id, wb_token=wb_token)
+            progress("stock-cache", "Собираем остатки из WB sync cache", 30)
+            bundle = reports.load_report_source_bundle(
+                organization_id=organization_id,
+                date_from=date_from,
+                date_to=date_to,
+                required_sources=reports.REPORT_REQUIRED_SOURCES["stock"],
+                get_cache=reports.get_source_cache,
+            )
+            report = reports._build_stock_report_from_data_mart(date_range, bundle, organization_id)
         elif report_id == "ads":
-            progress("ads", "Загружаем рекламу WB", 20)
-            report = reports._build_ads_report_payload(actor=SimpleNamespace(organization_id=organization_id, user_id=user_id), date_from=date_from, date_to=date_to, date_range=date_range, wb_token=wb_token, refresh=True)
+            progress("ads-cache", "Собираем рекламу из WB sync cache", 30)
+            bundle = reports.load_report_source_bundle(
+                organization_id=organization_id,
+                date_from=date_from,
+                date_to=date_to,
+                required_sources=reports.REPORT_REQUIRED_SOURCES["ads"],
+                get_cache=reports.get_source_cache,
+            )
+            report = reports._build_ads_report_from_data_mart(date_range, bundle)
         elif report_id == "rnp":
             progress("rnp", "Собираем воронку РНП", 20)
             payload = reports.build_rnp_report(date_from=date_from, date_to=date_to, group_by=group_by, finance_allowed=finance_allowed, organization_id=organization_id, wb_token=wb_token, force_refresh=True, progress_callback=progress)
             progress("rnp-map", "Готовим таблицу РНП", 95)
             report = reports._map_rnp_to_report_response(payload, date_range)
         elif report_id == "abc":
             progress("abc-sources", "Обновляем WB источники для ABC", 10)
             sync_result = refresh_wb_data_sources(
@@ -136,52 +167,33 @@ def build_report_for_org(self, organization_id: int, user_id: str, report_id: st
                 label = "1С забрала задачу, ждём статьи ДДС" if cash_flow.get("status") == "processing" else "Ждём статьи ДДС от 1С"
                 progress("waiting_1c", label, 20, "waiting_1c")
                 raise self.retry(countdown=3)
             if cash_flow.get("status") != "ready":
                 raise RuntimeError(f"1C cash-flow job failed: {cash_flow.get('status') or 'unknown'}")
             progress("expenses", "Собираем статьи ДДС из 1С", 80)
             report = reports._map_cash_flow_to_expenses_response(cash_flow, date_range, group_by)
         elif report_id == "week-over-week":
-            progress("week-over-week", "Загружаем текущий период WB", 20)
-            current_snapshot = reports.build_wb_reports_sources_snapshot(
+            progress("week-cache", "Собираем WoW из WB sync cache", 30)
+            current_bundle = reports.load_report_source_bundle(
+                organization_id=organization_id,
                 date_from=date_from,
                 date_to=date_to,
-                wb_token=wb_token,
-                progress_callback=progress,
+                required_sources=reports.REPORT_REQUIRED_SOURCES["week-over-week"],
+                get_cache=reports.get_source_cache,
             )
             previous_from, previous_to = reports._previous_period(date_from, date_to)
-            progress("week-over-week-previous", "Загружаем предыдущий период WB", 60)
-            previous_snapshot = reports.build_wb_reports_sources_snapshot(
-                date_from=previous_from,
-                date_to=previous_to,
-                wb_token=wb_token,
-                progress_callback=progress,
-            )
-            progress("week-over-week-ads", "Загружаем рекламу WB", 80)
-            current_ads = reports.build_ads_attribution_snapshot(
-                date_from=date_from,
-                date_to=date_to,
-                group_by="sku",
-                wb_token=wb_token,
-            )
-            previous_ads = reports.build_ads_attribution_snapshot(
+            previous_bundle = reports.load_report_source_bundle(
+                organization_id=organization_id,
                 date_from=previous_from,
                 date_to=previous_to,
-                group_by="sku",
-                wb_token=wb_token,
-            )
-            report = reports._build_week_over_week_payload(
-                date_range,
-                current_snapshot,
-                previous_snapshot,
-                current_ads,
-                previous_ads,
-                organization_id=organization_id,
+                required_sources=reports.REPORT_REQUIRED_SOURCES["week-over-week"],
+                get_cache=reports.get_source_cache,
             )
+            report = reports._build_week_over_week_from_data_mart(date_range, current_bundle, previous_bundle, organization_id)
         else:
             raise ValueError(f"Unsupported background report: {report_id}")
         reports.save_source_cache(organization_id, cache_key, {"report": report, "completedAt": reports._utc_now_iso()})
         result = {"state": "completed", "taskId": self.request.id, "reportId": report_id, "dateFrom": date_from_iso, "dateTo": date_to_iso, "groupBy": group_by, "stage": "completed", "label": "Отчёт готов", "percent": 100, "finishedAt": reports._utc_now_iso()}
         reports.save_source_cache(organization_id, job_key, result)
         return result
     except Retry:
         raise
diff --git a/app/routers/wb_reports_bff.py b/app/routers/wb_reports_bff.py
index a0ce385..278026f 100644
--- a/app/routers/wb_reports_bff.py
+++ b/app/routers/wb_reports_bff.py
@@ -9,16 +9,17 @@ from fastapi import APIRouter, Body, HTTPException, Query, Request
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
@@ -159,16 +160,22 @@ def _previous_period(date_from: date, date_to: date) -> tuple[date, date]:
 
 
 def _delta_pct(current: int | float | None, previous: int | float | None) -> float | None:
     if current is None or previous in (None, 0):
         return None
     return round((current - previous) / abs(previous) * 100, 2)
 
 
+def _calc_margin_pct(profit: int | float | None, revenue: int | float | None) -> float | None:
+    if profit is None or revenue in (None, 0):
+        return None
+    return round(profit / revenue * 100, 2)
+
+
 def _ads_by_nm(ads_snapshot: Any | None) -> dict[int, dict[str, int]]:
     result: dict[int, dict[str, int]] = defaultdict(lambda: {"baskets": 0, "ad_spend": 0})
     for row in getattr(ads_snapshot, "rows", []) or []:
         raw_nm_id = getattr(row, "sku_id", None)
         try:
             nm_id = int(raw_nm_id)
         except (TypeError, ValueError):
             continue
@@ -2162,16 +2169,24 @@ def _digest_cache_key(date_from: date, date_to: date) -> str:
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
 
@@ -2307,16 +2322,350 @@ def _empty_background_report(report_id: ReportId, date_range: dict[str, str], gr
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
+def _aggregate_map(bundle: ReportSourceBundle, source: str) -> dict[str, dict[str, Any]]:
+    payload = bundle.sources.get(source) or {}
+    aggregates = payload.get("aggregates")
+    return aggregates if isinstance(aggregates, dict) else {}
+
+
+def _optional_int_value(value: Any) -> int | None:
+    if isinstance(value, bool) or value is None:
+        return None
+    if isinstance(value, int):
+        return value
+    if isinstance(value, float):
+        return int(round(value))
+    if isinstance(value, str):
+        try:
+            return int(round(float(value.replace(",", ".").strip())))
+        except ValueError:
+            return None
+    return None
+
+
+def _first_known_int(row: dict[str, Any], *keys: str) -> int | None:
+    for key in keys:
+        if key in row and row[key] is not None:
+            return _optional_int_value(row[key])
+    return None
+
+
+def _stock_available_units(stock: dict[str, Any]) -> int | None:
+    available = _first_known_int(stock, "availableUnits")
+    if available is not None:
+        return available
+    quantity = _first_known_int(stock, "quantity")
+    if quantity is not None:
+        from_client_units = _first_known_int(stock, "fromClientUnits", "inWayFromClient")
+        return quantity + from_client_units if from_client_units is not None else quantity
+    return _first_known_int(stock, "wbStockUnits")
+
+
+def _materialization_cache(bundle: ReportSourceBundle) -> dict[str, Any]:
+    return {
+        "status": "exact" if bundle.covered else bundle.status,
+        "sourceCoverage": _source_coverage_payload(bundle),
+    }
+
+
+def _build_stock_report_from_data_mart(
+    date_range: dict[str, str],
+    bundle: ReportSourceBundle,
+    organization_id: int,
+) -> dict[str, Any]:
+    stock_aggregates = _aggregate_map(bundle, "stocks")
+    period_stats = _aggregate_map(bundle, "period_stats")
+    days = max(1, (date.fromisoformat(date_range["to"]) - date.fromisoformat(date_range["from"])).days + 1)
+    rows: list[dict[str, Any]] = []
+    for raw_nm_id, stock in stock_aggregates.items():
+        if not isinstance(stock, dict):
+            continue
+        nm_id = _optional_int_value(stock.get("nmId")) or _optional_int_value(raw_nm_id)
+        if nm_id is None:
+            continue
+        stats = period_stats.get(str(nm_id), {})
+        stats = stats if isinstance(stats, dict) else {}
+        wb_stock_units = _first_known_int(stock, "wbStockUnits", "quantity")
+        from_client_units = _first_known_int(stock, "fromClientUnits", "inWayFromClient")
+        available = _stock_available_units(stock)
+        orders_units = _first_known_int(stats, "ordersUnits")
+        orders_per_day = round(orders_units / days, 2) if orders_units is not None else None
+        days_to_oos = round(available / (orders_units / days), 1) if available is not None and orders_units is not None and orders_units > 0 else None
+        rows.append(
+            {
+                "sku": str(stock.get("sku") or stock.get("vendorCode") or f"NM_{nm_id}"),
+                "nmId": nm_id,
+                "warehouseName": stock.get("warehouseName") or "all_wb_warehouses",
+                "clusterName": stock.get("clusterName") or stock.get("regionName") or "unknown",
+                "wbStockUnits": wb_stock_units,
+                "fromClientUnits": from_client_units,
+                "toClientUnits": _first_known_int(stock, "toClientUnits", "inWayToClient"),
+                "availableUnits": available,
+                "ordersPerDay": orders_per_day,
+                "daysToOos": days_to_oos,
+                "ktrIndex": None,
+                "localizationPct": None,
+                "logisticsPerUnitKopecks": None,
+                "decision": "норма" if available is not None and available > 0 else "draft",
+                "decisionStatus": "confirmed" if available is not None and available > 0 else "draft",
+                "comment": "Источник: WB sync source cache." if available is not None else "В source cache нет доступного остатка.",
+                "historyCoverageDays": 0,
+                "historySource": "source_cache",
+            }
+        )
+    return {
+        "meta": _meta("stock", "Остатки WB", "Остатки построены из WB sync source cache.", "operational", "fresh" if bundle.covered else "partial"),
+        "headline": "Отчёт построен из source cache последнего WB sync.",
+        "filters": {"dateRange": date_range, "groupBy": "warehouse"},
+        "kpis": [_kpi("stock_rows", "SKU x складов", str(len(rows)))],
+        "chart": {"title": "Доступность по складам", "valueLabel": "Доступно, шт", "points": [{"label": row["warehouseName"], "value": row["availableUnits"]} for row in rows[:20]]},
+        "columns": [
+            {"key": "sku", "label": "Артикул"},
+            {"key": "nmId", "label": "WB"},
+            {"key": "warehouseName", "label": "Склад WB"},
+            {"key": "clusterName", "label": "Кластер"},
+            {"key": "wbStockUnits", "label": "Остаток WB"},
+            {"key": "fromClientUnits", "label": "От клиента"},
+            {"key": "toClientUnits", "label": "К клиенту"},
+            {"key": "availableUnits", "label": "Доступно"},
+            {"key": "ordersPerDay", "label": "Заказы/день"},
+            {"key": "daysToOos", "label": "Дней до OOS"},
+            {"key": "ktrIndex", "label": "КТР"},
+            {"key": "localizationPct", "label": "Локализация"},
+            {"key": "logisticsPerUnitKopecks", "label": "Логистика/шт"},
+            {"key": "decision", "label": "Решение"},
+            {"key": "decisionStatus", "label": "Статус"},
+            {"key": "comment", "label": "Комментарий"},
+            {"key": "historySource", "label": "Источник истории"},
+        ],
+        "rows": rows,
+        "cache": _materialization_cache(bundle),
+        "sourceCoverage": _source_coverage_payload(bundle),
+    }
+
+
+def _build_ads_report_from_data_mart(date_range: dict[str, str], bundle: ReportSourceBundle) -> dict[str, Any]:
+    rows: list[dict[str, Any]] = []
+    for raw_nm_id, aggregate in _aggregate_map(bundle, "ads").items():
+        if not isinstance(aggregate, dict):
+            continue
+        nm_id = _optional_int_value(aggregate.get("nmId")) or _optional_int_value(raw_nm_id)
+        campaign_id = aggregate.get("campaignId")
+        impressions = _first_known_int(aggregate, "adImpressions", "impressions")
+        clicks = _first_known_int(aggregate, "adClicks", "clicks")
+        baskets = _first_known_int(aggregate, "adCartAdds", "cartCount", "baskets")
+        orders_units = _first_known_int(aggregate, "adOrders", "ordersCount")
+        orders_kopecks = _first_known_int(aggregate, "adRevenueKopecks", "ordersKopecks")
+        ad_spend = _first_known_int(aggregate, "adSpendKopecks")
+        attribution_level = aggregate.get("attributionLevel")
+        is_unallocated = attribution_level == "campaign_only" if attribution_level is not None else None
+        rows.append(
+            {
+                "campaignId": campaign_id,
+                "campaignName": aggregate.get("campaignName"),
+                "campaignType": aggregate.get("campaignType"),
+                "campaignStatus": aggregate.get("campaignStatus"),
+                "paymentType": aggregate.get("paymentType"),
+                "campaignChangeTime": aggregate.get("campaignChangeTime"),
+                "manager": aggregate.get("manager"),
+                "sku": str(aggregate.get("sku") or aggregate.get("vendorCode") or f"NM_{nm_id}") if nm_id is not None else None,
+                "nmId": nm_id,
+                "impressions": impressions,
+                "clicks": clicks,
+                "adClicks": clicks,
+                "ctrPct": round(clicks / impressions * 100, 2) if clicks is not None and impressions not in (None, 0) else None,
+                "baskets": baskets,
+                "orders": {"units": orders_units, "kopecks": orders_kopecks, "deltaPct": None},
+                "sales": {"units": orders_units, "kopecks": orders_kopecks, "deltaPct": None},
+                "adSpendKopecks": ad_spend,
+                "drrPct": round(ad_spend / orders_kopecks * 100, 2) if ad_spend is not None and orders_kopecks not in (None, 0) else None,
+                "budgetCashKopecks": _first_known_int(aggregate, "budgetCashKopecks"),
+                "budgetNettingKopecks": _first_known_int(aggregate, "budgetNettingKopecks"),
+                "budgetTotalKopecks": _first_known_int(aggregate, "budgetTotalKopecks"),
+                "unallocatedSpend": is_unallocated,
+                "recommendation": "review" if is_unallocated is True else ("keep" if attribution_level is not None else None),
+                "recommendationStatus": "draft",
+                "recommendationReason": "Расход не распределен по SKU: WB не вернул nms в fullstats." if is_unallocated is True else ("SKU-атрибуция доступна для расчетов уровня SKU." if attribution_level is not None else None),
+                "attributionLevel": attribution_level,
+                "confidence": aggregate.get("confidence"),
+            }
+        )
+    known_spend = [row["adSpendKopecks"] for row in rows if row["adSpendKopecks"] is not None]
+    known_revenue = [row["orders"]["kopecks"] for row in rows if row["orders"]["kopecks"] is not None]
+    return {
+        "meta": _meta("ads", "Реклама", "SKU-level реклама из WB sync source cache без campaign-first attribution.", "operational", "fresh" if bundle.covered else "partial"),
+        "headline": "Отчёт построен из SKU-level source cache последнего WB sync; campaign attribution недоступна в этом источнике.",
+        "filters": {"dateRange": date_range, "groupBy": "sku"},
+        "kpis": [
+            _kpi("ad_spend", "Расход", str(sum(known_spend)) if len(known_spend) == len(rows) else "нет данных"),
+            _kpi("orders_revenue", "Выручка", str(sum(known_revenue)) if len(known_revenue) == len(rows) else "нет данных"),
+        ],
+        "chart": {"title": "Расходы по SKU", "valueLabel": "Расход, коп", "points": [{"label": row["sku"] or (f"NM_{row['nmId']}" if row["nmId"] is not None else "unknown"), "value": row["adSpendKopecks"]} for row in rows[:20]]},
+        "columns": [
+            {"key": "campaignName", "label": "РК"},
+            {"key": "sku", "label": "SKU"},
+            {"key": "nmId", "label": "WB"},
+            {"key": "adSpendKopecks", "label": "Расход"},
+        ],
+        "rows": rows,
+        "cache": _materialization_cache(bundle),
+        "sourceCoverage": _source_coverage_payload(bundle),
+    }
+
+
+def _build_week_over_week_from_data_mart(
+    date_range: dict[str, str],
+    current_bundle: ReportSourceBundle,
+    previous_bundle: ReportSourceBundle,
+    organization_id: int,
+) -> dict[str, Any]:
+    current_finance = _aggregate_map(current_bundle, "finance")
+    current_period = _aggregate_map(current_bundle, "period_stats")
+    current_ads = _aggregate_map(current_bundle, "ads")
+    current_baskets = _aggregate_map(current_bundle, "baskets")
+    current_stocks = _aggregate_map(current_bundle, "stocks")
+    previous_period = _aggregate_map(previous_bundle, "period_stats") if previous_bundle.covered else {}
+    previous_finance = _aggregate_map(previous_bundle, "finance") if previous_bundle.covered else {}
+    previous_ads = _aggregate_map(previous_bundle, "ads") if previous_bundle.covered else {}
+    previous_baskets = _aggregate_map(previous_bundle, "baskets") if previous_bundle.covered else {}
+    rows: list[dict[str, Any]] = []
+
+    for raw_nm_id, period in current_period.items():
+        if not isinstance(period, dict):
+            continue
+        nm_id = _optional_int_value(period.get("nmId")) or _optional_int_value(raw_nm_id)
+        if nm_id is None:
+            continue
+        finance = current_finance.get(str(nm_id), {})
+        ads = current_ads.get(str(nm_id), {})
+        baskets = current_baskets.get(str(nm_id), {})
+        stock = current_stocks.get(str(nm_id), {})
+        previous = previous_period.get(str(nm_id), {})
+        previous_finance_row = previous_finance.get(str(nm_id), {})
+        previous_ads_row = previous_ads.get(str(nm_id), {})
+        previous_basket_row = previous_baskets.get(str(nm_id), {})
+        finance = finance if isinstance(finance, dict) else {}
+        ads = ads if isinstance(ads, dict) else {}
+        baskets = baskets if isinstance(baskets, dict) else {}
+        stock = stock if isinstance(stock, dict) else {}
+        previous = previous if isinstance(previous, dict) else {}
+        previous_finance_row = previous_finance_row if isinstance(previous_finance_row, dict) else {}
+        previous_ads_row = previous_ads_row if isinstance(previous_ads_row, dict) else {}
+        previous_basket_row = previous_basket_row if isinstance(previous_basket_row, dict) else {}
+        orders_units = _first_known_int(period, "ordersUnits")
+        orders_kopecks = _first_known_int(period, "ordersKopecks", "revenueKopecks")
+        sales_units = _first_known_int(finance, "salesUnits")
+        if sales_units is None:
+            sales_units = _first_known_int(period, "salesUnits")
+        revenue = _first_known_int(finance, "sellerRevenueKopecks")
+        if revenue is None:
+            revenue = _first_known_int(period, "revenueKopecks")
+        previous_orders = _first_known_int(previous, "ordersUnits")
+        previous_sales = _first_known_int(previous_finance_row, "salesUnits")
+        if previous_sales is None:
+            previous_sales = _first_known_int(previous, "salesUnits")
+        previous_revenue = _first_known_int(previous_finance_row, "sellerRevenueKopecks")
+        if previous_revenue is None:
+            previous_revenue = _first_known_int(previous, "revenueKopecks")
+        baskets_units = _first_known_int(baskets, "cartCount", "baskets")
+        previous_baskets_units = _first_known_int(previous_basket_row, "cartCount", "baskets")
+        current_costs = [
+            _first_known_int(finance, "commissionKopecks"),
+            _first_known_int(finance, "logisticsKopecks"),
+            _first_known_int(ads, "adSpendKopecks"),
+        ]
+        previous_costs = [
+            _first_known_int(previous_finance_row, "commissionKopecks"),
+            _first_known_int(previous_finance_row, "logisticsKopecks"),
+            _first_known_int(previous_ads_row, "adSpendKopecks"),
+        ]
+        profit = revenue - sum(current_costs) if revenue is not None and all(cost is not None for cost in current_costs) else None
+        previous_profit = previous_revenue - sum(previous_costs) if previous_revenue is not None and all(cost is not None for cost in previous_costs) else None
+        stock_units = _stock_available_units(stock)
+        rows.append(
+            {
+                "sku": str(stock.get("sku") or finance.get("sku") or period.get("sku") or f"NM_{nm_id}"),
+                "nmId": nm_id,
+                "productName": stock.get("productName") or finance.get("productName"),
+                "productStatus": stock.get("productStatus") or finance.get("productStatus") or period.get("productStatus"),
+                "abcCode": stock.get("abcCode") or finance.get("abcCode") or period.get("abcCode"),
+                "orders": {"units": orders_units, "kopecks": orders_kopecks, "deltaPct": _delta_pct(orders_units, previous_orders)},
+                "sales": {"units": sales_units, "kopecks": revenue, "deltaPct": _delta_pct(sales_units, previous_sales)},
+                "baskets": {"units": baskets_units, "kopecks": None, "deltaPct": _delta_pct(baskets_units, previous_baskets_units)},
+                "marginPct": {"percent": _calc_margin_pct(profit, revenue), "deltaPct": _delta_pct(_calc_margin_pct(profit, revenue), _calc_margin_pct(previous_profit, previous_revenue))},
+                "profit": {"kopecks": profit, "deltaPct": _delta_pct(profit, previous_profit if previous_bundle.covered else None)},
+                "price": {"kopecks": None, "deltaPct": None},
+                "wasOutOfStock": stock_units <= 0 if stock_units is not None else None,
+                "stockAvailability7d": None,
+                "stockOutDays": None,
+                "stockSnapshotCoveragePct": None,
+                "historySource": "source_cache",
+                "conclusion": "WoW построен из cached source snapshots.",
+            }
+        )
+
+    payload = _week_over_week_shell(date_range, rows, source_status="fresh" if current_bundle.covered else "partial")
+    payload["cache"] = {
+        **_materialization_cache(current_bundle),
+        "previousRangeStatus": "exact" if previous_bundle.covered else "source_cache_miss",
+    }
+    payload["sourceCoverage"] = _source_coverage_payload(current_bundle)
+    return payload
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
@@ -2834,16 +3183,25 @@ def get_reports_by_id(
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
@@ -2856,16 +3214,25 @@ def get_reports_by_id(
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
@@ -3005,27 +3372,54 @@ def get_reports_by_id(
         "rows": [],
     }
 
 
 @router.post("/api/wb/reports/{report_id}/jobs")
 def start_report_job(request: Request, report_id: Literal["abc", "rnp", "ads", "pnl", "expenses", "stock", "week-over-week"], preset: str = Query(default="7d"), from_: str | None = Query(default=None, alias="from"), to: str | None = Query(default=None), groupBy: ReportGroupBy = Query(default="sku"), source: str = Query(default="operational")) -> dict[str, Any]:
     actor = actor_from_request(request)
     assert_permission_or_audit(actor=actor, permission="settings:read", action="reports.bff.job.start", object_type="wb_report", object_id=report_id, reason="actor cannot refresh report")
-    date_from, date_to, _ = _range_from_preset(preset, from_, to)
+    date_from, date_to, date_range = _range_from_preset(preset, from_, to)
     key = _report_job_cache_key(report_id, date_from, date_to, groupBy)
     cache_key = _report_cache_key(report_id, date_from, date_to, groupBy, source)
     cached = get_source_cache(actor.organization_id, cache_key, slim=False) or {}
     current = get_source_cache(actor.organization_id, key, slim=False) or {}
     if _report_payload_cache_is_fresh(cached):
         payload = _completed_report_job_from_cache(report_id, date_from, date_to, groupBy, cached, current)
         save_source_cache(actor.organization_id, key, payload)
         return payload
     if _report_job_is_reusable(current):
         return {**current, "reused": True}
+    required_sources = REPORT_REQUIRED_SOURCES.get(report_id, ())
+    if required_sources:
+        bundle = load_report_source_bundle(
+            organization_id=actor.organization_id,
+            date_from=date_from,
+            date_to=date_to,
+            required_sources=required_sources,
+            get_cache=get_source_cache,
+        )
+        if not bundle.covered:
+            source_coverage = _source_coverage_payload(bundle)
+            return {
+                "state": "source_cache_miss",
+                "reportId": report_id,
+                "dateFrom": date_from.isoformat(),
+                "dateTo": date_to.isoformat(),
+                "groupBy": groupBy,
+                "cache": {
+                    "status": "source_cache_miss",
+                    "requestedRange": date_range,
+                    "missingSources": bundle.missing_sources,
+                    "sourceCoverage": source_coverage,
+                    "syncStatus": bundle.sync_status,
+                },
+                "sourceCoverage": source_coverage,
+                "reused": False,
+            }
     cash_flow = None
     if report_id in {"pnl", "expenses"}:
         cash_flow = get_cash_flow_for_period(
             organization_id=actor.organization_id,
             period_from=date_from,
             period_to=date_to,
             requested_by=actor.user_id,
         )
diff --git a/docs/superpowers/specs/2026-07-15-wb-sync-report-data-mart-design.md b/docs/superpowers/specs/2026-07-15-wb-sync-report-data-mart-design.md
index bdeabc2..90c2cc3 100644
--- a/docs/superpowers/specs/2026-07-15-wb-sync-report-data-mart-design.md
+++ b/docs/superpowers/specs/2026-07-15-wb-sync-report-data-mart-design.md
@@ -155,15 +155,23 @@ Frontend tests should cover:
 ## Migration Plan
 
 1. Add the data mart reader module and tests around existing source cache shapes.
 2. Convert report jobs to use data mart readers before live WB fallbacks.
 3. Remove or fence direct WB runtime calls from report materialization paths.
 4. Add hot range prewarm after successful WB sync.
 5. Tighten frontend loading/stale states and optional neighbor prefetch.
 
+## Known Follow-Up
+
+- Automatic prewarm is limited to `stock` and `week-over-week`, and only runs for exact current-range source coverage. Broader aggregate caches cannot materialize shorter ranges until daily rollups exist.
+- ABC still needs a cache-only builder; its current job refreshes WB sources internally.
+- RNP and digest still have materialization paths that can call WB APIs and need cache-only builders before automatic prewarm.
+- P&L needs a fully cache-only materializer plus permission-aware report payload caching before automatic prewarm.
+- Ads needs a cache-only campaign materializer that correctly honors `group_by=campaign` before automatic prewarm.
+
 ## Non-Goals
 
 - Do not add a broad new database schema in the first pass.
 - Do not change report visual layouts.
 - Do not change pricing/repricer behavior.
 - Do not silently run full WB sync from every report tab click.
 - Do not merge all report data into one huge cache payload.
diff --git a/tests/test_one_c_cash_flow.py b/tests/test_one_c_cash_flow.py
index 6cc7d04..5a28450 100644
--- a/tests/test_one_c_cash_flow.py
+++ b/tests/test_one_c_cash_flow.py
@@ -1,9 +1,9 @@
-from datetime import date
+from datetime import date, datetime, timezone
 
 from fastapi.testclient import TestClient
 from sqlalchemy import create_engine
 from sqlalchemy.orm import sessionmaker
 
 from app.main import create_app
 from tests.auth_helpers import auth_headers
 
@@ -124,16 +124,43 @@ def test_cash_flow_job_queue_roundtrip_and_pnl_attachment(tmp_path, monkeypatch)
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
diff --git a/tests/test_report_data_mart.py b/tests/test_report_data_mart.py
new file mode 100644
index 0000000..ed20431
--- /dev/null
+++ b/tests/test_report_data_mart.py
@@ -0,0 +1,127 @@
+from __future__ import annotations
+
+from datetime import date, datetime, timedelta, timezone
+
+from app.report_data_mart import (
+    load_report_source_bundle,
+    source_cache_covers_range,
+    source_cache_matches_range,
+)
+
+
+def test_source_cache_exact_and_covering_ranges():
+    exact = {"dateFrom": "2026-07-01", "dateTo": "2026-07-07", "fetchedAt": datetime.now(timezone.utc).isoformat()}
+    covering = {"dateFrom": "2026-07-01", "dateTo": "2026-07-31", "fetchedAt": datetime.now(timezone.utc).isoformat()}
+
+    assert source_cache_matches_range(exact, date(2026, 7, 1), date(2026, 7, 7)) is True
+    assert source_cache_matches_range(covering, date(2026, 7, 3), date(2026, 7, 9)) is False
+    assert source_cache_covers_range(covering, date(2026, 7, 3), date(2026, 7, 9)) is True
+
+
+def test_load_report_source_bundle_reports_missing_and_stale_sources():
+    now = datetime.now(timezone.utc)
+    old = now - timedelta(days=3)
+    source_state = {
+        "finance_7": {"dateFrom": "2026-07-01", "dateTo": "2026-07-07", "fetchedAt": old.isoformat(), "aggregates": {"101": {"salesUnits": 2}}},
+        "ads_7": {"dateFrom": "2026-07-01", "dateTo": "2026-07-07", "fetchedAt": now.isoformat(), "aggregates": {"101": {"adSpendKopecks": 1200}}},
+        "wb_sync_status": {
+            "state": "completed",
+            "dateFrom": "2026-07-01",
+            "dateTo": "2026-07-07",
+            "periodDays": 7,
+            "periodCacheSuffix": "7",
+            "finishedAt": now.isoformat(),
+        },
+    }
+
+    def fake_get_cache(_organization_id: int, source_key: str, *, slim: bool = False):
+        return source_state.get(source_key)
+
+    bundle = load_report_source_bundle(
+        organization_id=1,
+        date_from=date(2026, 7, 1),
+        date_to=date(2026, 7, 7),
+        required_sources=["finance", "ads", "baskets"],
+        get_cache=fake_get_cache,
+    )
+
+    assert bundle.covered is False
+    assert bundle.status == "source_cache_miss"
+    assert bundle.by_source["finance"].status == "stale"
+    assert bundle.by_source["ads"].status == "exact"
+    assert bundle.by_source["baskets"].status == "missing"
+    assert bundle.missing_sources == ["baskets"]
+    assert bundle.sources["ads"]["aggregates"]["101"]["adSpendKopecks"] == 1200
+
+
+def test_load_report_source_bundle_treats_fresh_bare_stocks_as_exact_snapshot():
+    source_state = {
+        "stocks": {
+            "fetchedAt": datetime.now(timezone.utc).isoformat(),
+            "aggregates": {"101": {"quantity": 5}},
+        }
+    }
+
+    bundle = load_report_source_bundle(
+        organization_id=1,
+        date_from=date(2026, 7, 1),
+        date_to=date(2026, 7, 7),
+        required_sources=["stocks"],
+        get_cache=lambda _organization_id, key, **_kwargs: source_state.get(key),
+    )
+
+    assert bundle.covered is True
+    assert bundle.by_source["stocks"].source_key == "stocks"
+    assert bundle.by_source["stocks"].status == "exact"
+    assert bundle.by_source["stocks"].date_from is None
+    assert bundle.by_source["stocks"].date_to is None
+
+
+def test_load_report_source_bundle_finds_explicit_range_suffix_before_sync_suffix():
+    source_state = {
+        "wb_sync_status": {"periodCacheSuffix": "30"},
+        "finance_2026-06-24_2026-06-30": {
+            "dateFrom": "2026-06-24",
+            "dateTo": "2026-06-30",
+            "fetchedAt": datetime.now(timezone.utc).isoformat(),
+            "aggregates": {"101": {"salesUnits": 2}},
+        },
+    }
+
+    bundle = load_report_source_bundle(
+        organization_id=1,
+        date_from=date(2026, 6, 24),
+        date_to=date(2026, 6, 30),
+        required_sources=["finance"],
+        get_cache=lambda _organization_id, key, **_kwargs: source_state.get(key),
+    )
+
+    assert bundle.covered is True
+    assert bundle.by_source["finance"].source_key == "finance_2026-06-24_2026-06-30"
+    assert bundle.by_source["finance"].status == "exact"
+
+
+def test_load_report_source_bundle_does_not_materialize_aggregate_subranges():
+    fetched_at = datetime.now(timezone.utc).isoformat()
+    source_state = {
+        "wb_sync_status": {"periodCacheSuffix": "30"},
+        "finance_30": {"dateFrom": "2026-07-01", "dateTo": "2026-07-30", "fetchedAt": fetched_at, "aggregates": {}},
+        "ads_30": {"dateFrom": "2026-07-01", "dateTo": "2026-07-30", "fetchedAt": fetched_at, "aggregates": {}},
+        "period_stats_30": {"dateFrom": "2026-07-01", "dateTo": "2026-07-30", "fetchedAt": fetched_at, "aggregates": {}},
+    }
+
+    bundle = load_report_source_bundle(
+        organization_id=1,
+        date_from=date(2026, 7, 24),
+        date_to=date(2026, 7, 30),
+        required_sources=["finance", "ads", "period_stats"],
+        get_cache=lambda _organization_id, key, **_kwargs: source_state.get(key),
+    )
+
+    assert bundle.covered is False
+    assert bundle.status == "partial"
+    assert {source: coverage.status for source, coverage in bundle.by_source.items()} == {
+        "finance": "partial",
+        "ads": "partial",
+        "period_stats": "partial",
+    }
diff --git a/tests/test_report_materialization_from_data_mart.py b/tests/test_report_materialization_from_data_mart.py
new file mode 100644
index 0000000..bd2cb61
--- /dev/null
+++ b/tests/test_report_materialization_from_data_mart.py
@@ -0,0 +1,244 @@
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
+
+
+def test_stock_job_materializes_from_cached_stocks(monkeypatch):
+    saved: dict[str, dict] = {}
+    fetched_at = wb_reports_bff._utc_now_iso()
+    source_state = {
+        "wb_sync_status": {"state": "completed", "dateFrom": "2026-07-01", "dateTo": "2026-07-07", "periodDays": 7, "periodCacheSuffix": "7"},
+        "stocks": {
+            "fetchedAt": fetched_at,
+            "aggregates": {"101": {"nmId": 101, "sku": "SKU-101", "wbStockUnits": 0, "quantity": 2, "inWayFromClient": 3, "warehouseName": "Коледино"}},
+        },
+        "period_stats_2026-07-01_2026-07-07": {
+            "dateFrom": "2026-07-01",
+            "dateTo": "2026-07-07",
+            "fetchedAt": fetched_at,
+            "aggregates": {"101": {"ordersUnits": 0, "salesUnits": 7}},
+        },
+    }
+
+    monkeypatch.setattr(wb_reports_bff, "get_source_cache", lambda _organization_id, key, **_kwargs: source_state.get(key, {}))
+    monkeypatch.setattr(wb_reports_bff, "save_source_cache", lambda _organization_id, key, payload: saved.__setitem__(key, payload))
+    monkeypatch.setattr(
+        wb_reports_bff,
+        "build_wb_reports_sources_snapshot",
+        lambda **_kwargs: pytest.fail("stock materializer must use cached source bundle"),
+    )
+
+    result = repricer_tasks.build_report_for_org.run(
+        1, "user-1", "stock", "2026-07-01", "2026-07-07", "warehouse", "operational", True, "wb-token"
+    )
+
+    assert result["state"] == "completed"
+    payloads = [payload for key, payload in saved.items() if key.startswith("reports_payload_stock")]
+    assert payloads
+    report = payloads[-1]["report"]
+    assert report["meta"]["id"] == "stock"
+    assert report["rows"][0]["nmId"] == 101
+    assert report["rows"][0]["availableUnits"] == 5
+    assert report["rows"][0]["fromClientUnits"] == 3
+    assert report["rows"][0]["daysToOos"] is None
+    assert report["rows"][0]["comment"]
+    assert report["sourceCoverage"][0]["status"] == "exact"
+
+
+def test_ads_job_materializes_from_cached_ads(monkeypatch):
+    saved: dict[str, dict] = {}
+    fetched_at = wb_reports_bff._utc_now_iso()
+    source_state = {
+        "wb_sync_status": {"state": "completed", "dateFrom": "2026-07-01", "dateTo": "2026-07-07", "periodDays": 7, "periodCacheSuffix": "7"},
+        "ads_2026-07-01_2026-07-07": {
+            "dateFrom": "2026-07-01",
+            "dateTo": "2026-07-07",
+            "fetchedAt": fetched_at,
+            "aggregates": {
+                "101": {
+                    "nmId": 101,
+                    "adSpendKopecks": 400,
+                    "adImpressions": 50,
+                    "adClicks": 5,
+                    "adCartAdds": 3,
+                    "adOrders": 2,
+                    "adRevenueKopecks": 800,
+                }
+            },
+        },
+    }
+
+    monkeypatch.setattr(wb_reports_bff, "get_source_cache", lambda _organization_id, key, **_kwargs: source_state.get(key, {}))
+    monkeypatch.setattr(wb_reports_bff, "save_source_cache", lambda _organization_id, key, payload: saved.__setitem__(key, payload))
+    monkeypatch.setattr(
+        wb_reports_bff,
+        "build_ads_attribution_snapshot",
+        lambda **_kwargs: pytest.fail("ads materializer must use cached source bundle"),
+    )
+
+    result = repricer_tasks.build_report_for_org.run(
+        1, "user-1", "ads", "2026-07-01", "2026-07-07", "campaign", "operational", True, "wb-token"
+    )
+
+    assert result["state"] == "completed"
+    payloads = [payload for key, payload in saved.items() if key.startswith("reports_payload_ads")]
+    assert payloads
+    report = payloads[-1]["report"]
+    assert report["meta"]["id"] == "ads"
+    assert report["rows"][0]["nmId"] == 101
+    assert report["rows"][0]["campaignId"] is None
+    assert report["rows"][0]["campaignName"] is None
+    assert report["rows"][0]["adClicks"] == 5
+    assert report["rows"][0]["adSpendKopecks"] == 400
+    assert report["sourceCoverage"][0]["status"] == "exact"
+
+
+def test_week_over_week_job_returns_null_deltas_when_previous_range_missing(monkeypatch):
+    saved: dict[str, dict] = {}
+    fetched_at = wb_reports_bff._utc_now_iso()
+    source_state = {
+        "wb_sync_status": {"state": "completed", "dateFrom": "2026-07-01", "dateTo": "2026-07-07", "periodDays": 7, "periodCacheSuffix": "7"},
+        "finance_2026-07-01_2026-07-07": {"dateFrom": "2026-07-01", "dateTo": "2026-07-07", "fetchedAt": fetched_at, "aggregates": {"101": {"salesUnits": 2, "sellerRevenueKopecks": 20000}}},
+        "period_stats_2026-07-01_2026-07-07": {"dateFrom": "2026-07-01", "dateTo": "2026-07-07", "fetchedAt": fetched_at, "aggregates": {"101": {"ordersUnits": 3, "revenueKopecks": 30000}}},
+        "ads_2026-07-01_2026-07-07": {"dateFrom": "2026-07-01", "dateTo": "2026-07-07", "fetchedAt": fetched_at, "aggregates": {"101": {"adSpendKopecks": 400, "adCartAdds": 5}}},
+        "baskets_2026-07-01_2026-07-07": {"dateFrom": "2026-07-01", "dateTo": "2026-07-07", "fetchedAt": fetched_at, "aggregates": {"101": {"cartCount": 5}}},
+        "stocks": {"fetchedAt": fetched_at, "aggregates": {"101": {"nmId": 101, "sku": "SKU-101", "wbStockUnits": 0, "quantity": 2, "inWayFromClient": 3}}},
+    }
+
+    monkeypatch.setattr(wb_reports_bff, "get_source_cache", lambda _organization_id, key, **_kwargs: source_state.get(key, {}))
+    monkeypatch.setattr(wb_reports_bff, "save_source_cache", lambda _organization_id, key, payload: saved.__setitem__(key, payload))
+    monkeypatch.setattr(
+        wb_reports_bff,
+        "build_wb_reports_sources_snapshot",
+        lambda **_kwargs: pytest.fail("WoW materializer must use cached source bundles"),
+    )
+    monkeypatch.setattr(
+        wb_reports_bff,
+        "build_ads_attribution_snapshot",
+        lambda **_kwargs: pytest.fail("WoW materializer must use cached ads bundles"),
+    )
+
+    result = repricer_tasks.build_report_for_org.run(
+        1, "user-1", "week-over-week", "2026-07-01", "2026-07-07", "sku", "operational", True, "wb-token"
+    )
+
+    assert result["state"] == "completed"
+    payloads = [payload for key, payload in saved.items() if key.startswith("reports_payload_week-over-week")]
+    report = payloads[-1]["report"]
+    assert report["rows"][0]["sku"] == "SKU-101"
+    assert report["rows"][0]["productStatus"] is None
+    assert report["rows"][0]["abcCode"] is None
+    assert report["rows"][0]["orders"]["units"] == 3
+    assert report["rows"][0]["orders"]["deltaPct"] is None
+    assert report["cache"]["previousRangeStatus"] == "source_cache_miss"
+
+
+def test_week_over_week_job_uses_explicit_previous_range_cache_for_deltas(monkeypatch):
+    saved: dict[str, dict] = {}
+    fetched_at = wb_reports_bff._utc_now_iso()
+    source_state = {
+        "wb_sync_status": {"state": "completed", "periodCacheSuffix": "30"},
+        "finance_2026-07-01_2026-07-07": {"dateFrom": "2026-07-01", "dateTo": "2026-07-07", "fetchedAt": fetched_at, "aggregates": {"101": {"salesUnits": 3, "sellerRevenueKopecks": 30000, "commissionKopecks": 1000, "logisticsKopecks": 500}}},
+        "period_stats_2026-07-01_2026-07-07": {"dateFrom": "2026-07-01", "dateTo": "2026-07-07", "fetchedAt": fetched_at, "aggregates": {"101": {"ordersUnits": 3, "revenueKopecks": 30000}}},
+        "ads_2026-07-01_2026-07-07": {"dateFrom": "2026-07-01", "dateTo": "2026-07-07", "fetchedAt": fetched_at, "aggregates": {"101": {"adSpendKopecks": 400, "adCartAdds": 5}}},
+        "baskets_2026-07-01_2026-07-07": {"dateFrom": "2026-07-01", "dateTo": "2026-07-07", "fetchedAt": fetched_at, "aggregates": {"101": {"cartCount": 5}}},
+        "finance_2026-06-24_2026-06-30": {"dateFrom": "2026-06-24", "dateTo": "2026-06-30", "fetchedAt": fetched_at, "aggregates": {"101": {"salesUnits": 2, "sellerRevenueKopecks": 20000, "commissionKopecks": 1000, "logisticsKopecks": 500}}},
+        "period_stats_2026-06-24_2026-06-30": {"dateFrom": "2026-06-24", "dateTo": "2026-06-30", "fetchedAt": fetched_at, "aggregates": {"101": {"ordersUnits": 2, "revenueKopecks": 20000}}},
+        "ads_2026-06-24_2026-06-30": {"dateFrom": "2026-06-24", "dateTo": "2026-06-30", "fetchedAt": fetched_at, "aggregates": {"101": {"adSpendKopecks": 300, "adCartAdds": 4}}},
+        "baskets_2026-06-24_2026-06-30": {"dateFrom": "2026-06-24", "dateTo": "2026-06-30", "fetchedAt": fetched_at, "aggregates": {"101": {"cartCount": 4}}},
+        "stocks": {"fetchedAt": fetched_at, "aggregates": {"101": {"nmId": 101, "sku": "SKU-101", "wbStockUnits": 0, "quantity": 2, "inWayFromClient": 3}}},
+    }
+
+    monkeypatch.setattr(wb_reports_bff, "get_source_cache", lambda _organization_id, key, **_kwargs: source_state.get(key, {}))
+    monkeypatch.setattr(wb_reports_bff, "save_source_cache", lambda _organization_id, key, payload: saved.__setitem__(key, payload))
+    monkeypatch.setattr(wb_reports_bff, "build_wb_reports_sources_snapshot", lambda **_kwargs: pytest.fail("WoW materializer must use cached source bundles"))
+    monkeypatch.setattr(wb_reports_bff, "build_ads_attribution_snapshot", lambda **_kwargs: pytest.fail("WoW materializer must use cached ads bundles"))
+
+    result = repricer_tasks.build_report_for_org.run(
+        1, "user-1", "week-over-week", "2026-07-01", "2026-07-07", "sku", "operational", True, "wb-token"
+    )
+
+    assert result["state"] == "completed"
+    payloads = [payload for key, payload in saved.items() if key.startswith("reports_payload_week-over-week")]
+    report = payloads[-1]["report"]
+    assert report["cache"]["previousRangeStatus"] == "exact"
+    assert report["rows"][0]["orders"]["deltaPct"] == 50.0
+    assert report["rows"][0]["profit"]["deltaPct"] == 54.4
+    assert report["rows"][0]["wasOutOfStock"] is False
+    assert report["rows"][0]["stockAvailability7d"] is None
+    assert report["rows"][0]["stockOutDays"] is None
+    assert report["rows"][0]["stockSnapshotCoveragePct"] is None
diff --git a/tests/test_report_prewarm.py b/tests/test_report_prewarm.py
new file mode 100644
index 0000000..864bf92
--- /dev/null
+++ b/tests/test_report_prewarm.py
@@ -0,0 +1,163 @@
+from __future__ import annotations
+
+from datetime import datetime, timezone
+
+import pytest
+
+from app.report_prewarm import prewarm_report_payloads
+
+
+def _exact_source_state(sync_status: dict, date_from: str, date_to: str) -> dict[str, dict]:
+    fetched_at = datetime.now(timezone.utc).isoformat()
+    state = {
+        "wb_sync_status": sync_status,
+        "stocks": {"fetchedAt": fetched_at, "aggregates": {}},
+    }
+    for source in ("finance", "period_stats", "ads", "baskets"):
+        state[f"{source}_{date_from}_{date_to}"] = {
+            "dateFrom": date_from,
+            "dateTo": date_to,
+            "fetchedAt": fetched_at,
+            "aggregates": {},
+        }
+    return state
+
+
+def test_prewarm_enqueues_only_cache_only_reports_with_exact_coverage():
+    calls: list[tuple] = []
+    sync_status = {
+        "state": "completed",
+        "dateFrom": "2026-07-01",
+        "dateTo": "2026-07-30",
+        "periodDays": 30,
+        "periodCacheSuffix": "30",
+    }
+    source_state = _exact_source_state(sync_status, "2026-07-01", "2026-07-30")
+
+    result = prewarm_report_payloads(
+        organization_id=1,
+        user_id="sync",
+        sync_status=sync_status,
+        finance_allowed=True,
+        wb_token="token",
+        enqueue=lambda *args: calls.append(args) or type("Task", (), {"id": f"task-{len(calls)}"})(),
+        get_cache=lambda _organization_id, key, **_kwargs: source_state.get(key),
+    )
+
+    report_ids = {item["reportId"] for item in result}
+    assert report_ids == {"stock", "week-over-week"}
+    assert report_ids.isdisjoint({"abc", "rnp", "pnl", "ads", "digest"})
+    assert {(item["dateFrom"], item["dateTo"]) for item in result} == {("2026-07-01", "2026-07-30")}
+    assert len(calls) == 2
+
+
+def test_prewarm_skips_reports_without_exact_source_coverage():
+    calls: list[tuple] = []
+    sync_status = {"dateFrom": "2026-07-01", "dateTo": "2026-07-07", "periodCacheSuffix": "7"}
+    source_state = {
+        "wb_sync_status": sync_status,
+        "stocks": {"fetchedAt": datetime.now(timezone.utc).isoformat(), "aggregates": {}},
+    }
+
+    result = prewarm_report_payloads(
+        organization_id=1,
+        user_id="sync",
+        sync_status=sync_status,
+        finance_allowed=True,
+        wb_token="token",
+        enqueue=lambda *args: calls.append(args),
+        get_cache=lambda _organization_id, key, **_kwargs: source_state.get(key),
+    )
+
+    assert result == []
+    assert calls == []
+
+
+@pytest.mark.parametrize("job_state", ["queued", "running", "completed"])
+def test_prewarm_dedupes_existing_payload_and_jobs(job_state):
+    calls: list[tuple] = []
+    sync_status = {"dateFrom": "2026-07-01", "dateTo": "2026-07-07", "periodCacheSuffix": "7"}
+    source_state = _exact_source_state(sync_status, "2026-07-01", "2026-07-07")
+    source_state["reports_payload_stock_2026-07-01_2026-07-07_warehouse_operational"] = {"report": {"rows": []}}
+    source_state["reports_job_week-over-week_2026-07-01_2026-07-07_sku"] = {"state": job_state}
+
+    result = prewarm_report_payloads(
+        organization_id=1,
+        user_id="sync",
+        sync_status=sync_status,
+        finance_allowed=True,
+        wb_token="token",
+        enqueue=lambda *args: calls.append(args),
+        get_cache=lambda _organization_id, key, **_kwargs: source_state.get(key),
+    )
+
+    assert result == []
+    assert calls == []
+
+
+def test_refresh_wb_data_sources_calls_prewarm_callback(monkeypatch):
+    from app import repricer_sync
+
+    monkeypatch.setattr("app.repricer_sync.fetch_stock_aggregates", lambda *_args, **_kwargs: {})
+    monkeypatch.setattr("app.repricer_sync.save_source_cache", lambda _organization_id, _key, payload: payload)
+
+    prewarm_calls: list[dict] = []
+    result = repricer_sync.refresh_wb_data_sources(
+        organization_id=1,
+        wb_token="token",
+        sources=["stocks"],
+        execute_lock=False,
+        _prewarm_callback=lambda payload: prewarm_calls.append(payload) or [{"reportId": "stock"}],
+    )
+
+    assert result["state"] == "completed"
+    assert result["reportPrewarm"] == [{"reportId": "stock"}]
+    assert prewarm_calls[0]["state"] == "completed"
+
+
+def test_refresh_wb_data_sources_skips_default_prewarm_for_partial_locked_sync(monkeypatch):
+    from app import report_prewarm, repricer_sync
+
+    monkeypatch.setattr("app.repricer_sync.begin_wb_sync", lambda *_args, **_kwargs: {"runId": "sync-1"})
+    monkeypatch.setattr("app.repricer_sync.finish_wb_sync", lambda _organization_id, status, state, steps, error=None: {**status, "state": state, "steps": steps})
+    monkeypatch.setattr("app.repricer_sync.fetch_stock_aggregates", lambda *_args, **_kwargs: {})
+    monkeypatch.setattr("app.repricer_sync.save_source_cache", lambda _organization_id, _key, payload: payload)
+    prewarm_calls: list[dict] = []
+    monkeypatch.setattr(report_prewarm, "prewarm_report_payloads", lambda **kwargs: prewarm_calls.append(kwargs) or [])
+
+    result = repricer_sync.refresh_wb_data_sources(
+        organization_id=1,
+        wb_token="token",
+        sources=["stocks"],
+    )
+
+    assert result["state"] == "completed"
+    assert "reportPrewarm" not in result
+    assert prewarm_calls == []
+
+
+def test_refresh_wb_data_sources_contains_default_prewarm_failure(monkeypatch):
+    from app import report_prewarm, repricer_sync
+
+    monkeypatch.setattr("app.repricer_sync.begin_wb_sync", lambda *_args, **_kwargs: {"runId": "sync-1"})
+    monkeypatch.setattr("app.repricer_sync.finish_wb_sync", lambda _organization_id, status, state, steps, error=None: {**status, "state": state, "steps": steps})
+    monkeypatch.setattr("app.repricer_sync.fetch_stock_aggregates", lambda *_args, **_kwargs: {})
+    monkeypatch.setattr("app.repricer_sync.fetch_period_stats_aggregates", lambda *_args, **_kwargs: {"aggregates": {}})
+    monkeypatch.setattr("app.repricer_sync.fetch_finance_report_aggregates", lambda *_args, **_kwargs: {"aggregates": {}, "count": 0})
+    monkeypatch.setattr("app.repricer_sync.fetch_ads_spend_aggregates", lambda *_args, **_kwargs: {})
+    monkeypatch.setattr("app.repricer_sync.list_cached_goods", lambda _organization_id: [])
+    monkeypatch.setattr("app.repricer_sync.save_source_cache", lambda _organization_id, _key, payload: payload)
+
+    def fail_prewarm(**_kwargs):
+        raise RuntimeError("prewarm unavailable")
+
+    monkeypatch.setattr(report_prewarm, "prewarm_report_payloads", fail_prewarm)
+
+    result = repricer_sync.refresh_wb_data_sources(
+        organization_id=1,
+        wb_token="token",
+        sources=["stocks", "period-stats", "finance", "ads", "baskets"],
+    )
+
+    assert result["state"] == "completed"
+    assert result["reportPrewarm"] == {"state": "failed", "error": "prewarm unavailable"}
diff --git a/tests/test_repricer_tasks.py b/tests/test_repricer_tasks.py
index 0efe8f2..c44bbb3 100644
--- a/tests/test_repricer_tasks.py
+++ b/tests/test_repricer_tasks.py
@@ -347,17 +347,31 @@ def test_scheduler_wb_sync_skips_stale_running_sync(monkeypatch):
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
diff --git a/tests/test_wb_reports_bff.py b/tests/test_wb_reports_bff.py
index af8bc8a..f3288bf 100644
--- a/tests/test_wb_reports_bff.py
+++ b/tests/test_wb_reports_bff.py
@@ -21,16 +21,32 @@ from app.wb_api.client import FakeWbApiClient, WbApiRequest
 from app.wb_api.reports_sources_runtime import WbStockRow
 from tests.auth_helpers import auth_headers
 
 
 def client() -> TestClient:
     return TestClient(create_app())
 
 
+def _exact_wow_source_state(date_from: str, date_to: str) -> dict[str, dict]:
+    fetched_at = datetime.now(timezone.utc).isoformat()
+    state = {
+        "wb_sync_status": {"periodCacheSuffix": "custom"},
+        "stocks": {"fetchedAt": fetched_at, "aggregates": {}},
+    }
+    for source in ("finance", "period_stats", "ads", "baskets"):
+        state[f"{source}_{date_from}_{date_to}"] = {
+            "dateFrom": date_from,
+            "dateTo": date_to,
+            "fetchedAt": fetched_at,
+            "aggregates": {},
+        }
+    return state
+
+
 def test_bff_digest_endpoint_returns_frontend_shape():
     api = client()
     response = api.get("/api/wb/reports/digest", headers=auth_headers(api, "viewer"))
     assert response.status_code == 200
     payload = response.json()
     assert payload["meta"]["id"] == "digest"
     assert isinstance(payload["kpis"], list)
     assert isinstance(payload["planFactRows"], list)
@@ -58,16 +74,46 @@ def test_digest_refresh_reuses_existing_running_job(monkeypatch):
     assert response.json()["taskId"] == "digest-task-1"
     assert response.json()["reused"] is True
 
 
 def test_report_job_cache_key_scopes_report_range_and_grouping():
     assert _report_job_cache_key("stock", date(2026, 6, 1), date(2026, 6, 7), "warehouse") == "reports_job_stock_2026-06-01_2026-06-07_warehouse"
 
 
+def test_report_job_endpoint_returns_source_cache_miss_without_enqueuing(monkeypatch):
+    from app import repricer_tasks
+    from app.routers import wb_reports_bff
+
+    monkeypatch.setattr(wb_reports_bff, "get_source_cache", lambda *_args, **_kwargs: {})
+    monkeypatch.setattr(
+        repricer_tasks.build_report_for_org,
+        "delay",
+        lambda *_args, **_kwargs: pytest.fail("source cache miss must not enqueue a report job"),
+    )
+    monkeypatch.setattr(wb_reports_bff, "actor_from_request", lambda _request: SimpleNamespace(organization_id=1, user_id="viewer"))
+    monkeypatch.setattr(wb_reports_bff, "assert_permission_or_audit", lambda **_kwargs: None)
+    monkeypatch.setattr(wb_reports_bff, "has_permission", lambda *_args, **_kwargs: False)
+    monkeypatch.setattr(wb_reports_bff, "_actor_wb_token", lambda _actor: None)
+
+    result = wb_reports_bff.start_report_job(
+        SimpleNamespace(),
+        "stock",
+        preset="custom",
+        from_="2026-07-01",
+        to="2026-07-07",
+        groupBy="warehouse",
+        source="operational",
+    )
+
+    assert result["state"] == "source_cache_miss"
+    assert result["cache"]["status"] == "source_cache_miss"
+    assert result["cache"]["missingSources"] == ["stocks", "period_stats"]
+
+
 def test_week_over_week_uses_equal_previous_period():
     assert _previous_period(date(2026, 7, 7), date(2026, 7, 13)) == (date(2026, 6, 30), date(2026, 7, 6))
 
 
 def test_week_over_week_returns_real_deltas_for_current_and_previous_snapshots():
     current = SimpleNamespace(
         source_status="fresh",
         orders=[
@@ -149,19 +195,20 @@ def test_week_over_week_enriches_rows_from_cached_catalog(monkeypatch):
     assert row["category"] == "Real Category"
 
 
 def test_week_over_week_job_endpoint_starts_and_reuses_task(monkeypatch):
     from app import repricer_tasks
     from app.routers import wb_reports_bff
 
     saved: dict[str, dict] = {}
+    source_state = _exact_wow_source_state("2026-07-07", "2026-07-13")
     monkeypatch.setattr(
         "app.routers.wb_reports_bff.get_source_cache",
-        lambda _organization_id, key, slim=False: saved.get(key, {}),
+        lambda _organization_id, key, slim=False: saved.get(key) or source_state.get(key, {}),
     )
     monkeypatch.setattr(
         "app.routers.wb_reports_bff.save_source_cache",
         lambda _organization_id, key, payload: saved.__setitem__(key, payload),
     )
     monkeypatch.setattr(
         repricer_tasks.build_report_for_org,
         "delay",
@@ -184,23 +231,26 @@ def test_week_over_week_job_endpoint_starts_and_reuses_task(monkeypatch):
 def test_week_over_week_job_endpoint_reuses_completed_cached_report(monkeypatch):
     from app import repricer_tasks
     from app.routers import wb_reports_bff
 
     delay_calls: list[tuple] = []
 
     def fake_cache(_organization_id, key, slim=False):
         if key.startswith("reports_payload_week-over-week"):
-            return {"report": {"meta": {"id": "week-over-week"}, "rows": [{"sku": "CACHED"}]}}
+            return {
+                "report": {"meta": {"id": "week-over-week"}, "rows": [{"sku": "CACHED"}]},
+                "completedAt": datetime.now(timezone.utc).isoformat(),
+            }
         if key.startswith("reports_job_week-over-week"):
             return {"state": "completed", "taskId": "done-task", "reportId": "week-over-week"}
         return {}
 
     monkeypatch.setattr("app.routers.wb_reports_bff.get_source_cache", fake_cache)
-    monkeypatch.setattr("app.routers.wb_reports_bff.save_source_cache", lambda *_args, **_kwargs: pytest.fail("cached report should not enqueue a new job"))
+    monkeypatch.setattr("app.routers.wb_reports_bff.save_source_cache", lambda _organization_id, _key, payload: payload)
     monkeypatch.setattr(
         repricer_tasks.build_report_for_org,
         "delay",
         lambda *args, **_kwargs: delay_calls.append(args) or type("Task", (), {"id": "unexpected"})(),
     )
     monkeypatch.setattr(wb_reports_bff, "actor_from_request", lambda _request: SimpleNamespace(organization_id=1, user_id="viewer"))
     monkeypatch.setattr(wb_reports_bff, "assert_permission_or_audit", lambda **_kwargs: None)
     monkeypatch.setattr(wb_reports_bff, "has_permission", lambda *_args, **_kwargs: False)
@@ -223,19 +273,26 @@ def test_week_over_week_job_endpoint_reuses_completed_cached_report(monkeypatch)
 
 def test_week_over_week_job_endpoint_restarts_stale_running_job(monkeypatch):
     from app import repricer_tasks
     from app.routers import wb_reports_bff
 
     stale_updated_at = (datetime.now(timezone.utc) - timedelta(minutes=16)).isoformat()
     saved: dict[str, dict] = {}
     delay_calls: list[tuple] = []
+    source_state = _exact_wow_source_state("2026-07-07", "2026-07-13")
+
+    def fake_cache(_organization_id, key, slim=False):
+        if key.startswith("reports_job_week-over-week"):
+            return saved.get(key, {"state": "running", "taskId": "stale-task", "updatedAt": stale_updated_at})
+        return source_state.get(key, {})
+
     monkeypatch.setattr(
         "app.routers.wb_reports_bff.get_source_cache",
-        lambda _organization_id, key, slim=False: saved.get(key, {"state": "running", "taskId": "stale-task", "updatedAt": stale_updated_at}),
+        fake_cache,
     )
     monkeypatch.setattr(
         "app.routers.wb_reports_bff.save_source_cache",
         lambda _organization_id, key, payload: saved.__setitem__(key, payload),
     )
 
     def delay(*args, **_kwargs):
         delay_calls.append(args)
@@ -488,47 +545,64 @@ def test_week_over_week_live_builder_uses_own_sources_not_abc_or_repricer(monkey
     assert payload["cache"]["status"] == "live"
     assert [step["stage"] for step in payload["diagnostics"]["requests"]] == ["current_sources", "previous_sources", "current_ads", "previous_ads"]
     assert payload["diagnostics"]["requests"][0]["rows"]["orders"] == 2
     assert payload["rows"][0]["orders"]["units"] == 2
     assert payload["rows"][0]["orders"]["deltaPct"] == 100.0
     assert payload["rows"][0]["sales"]["kopecks"] == 100_000
 
 
-def test_week_over_week_task_builds_current_and_previous_source_ranges(monkeypatch):
+def test_week_over_week_task_materializes_current_and_previous_cache_ranges(monkeypatch):
     from app import repricer_tasks
     from app.routers import wb_reports_bff
 
-    calls: list[tuple[date, date]] = []
     saved: dict[str, dict] = {}
-    snapshot = SimpleNamespace(source_status="fresh", orders=[], sales=[], stocks=[])
-    ads = SimpleNamespace(rows=[])
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
-        lambda *, date_from, date_to, **_kwargs: (calls.append((date_from, date_to)) or snapshot),
+        lambda **_kwargs: pytest.fail("WoW task must use cached source bundles"),
+    )
+    monkeypatch.setattr(
+        wb_reports_bff,
+        "build_ads_attribution_snapshot",
+        lambda **_kwargs: pytest.fail("WoW task must use cached ads bundles"),
     )
-    monkeypatch.setattr(wb_reports_bff, "build_ads_attribution_snapshot", lambda **_kwargs: ads)
-    monkeypatch.setattr(wb_reports_bff, "_build_week_over_week_payload", lambda *args, **_kwargs: {"meta": {"id": "week-over-week"}, "rows": []})
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
         None,
     )
 
-    assert calls == [(date(2026, 7, 7), date(2026, 7, 13)), (date(2026, 6, 30), date(2026, 7, 6))]
     assert result["state"] == "completed"
     assert any(key.startswith("reports_payload_week-over-week") for key in saved)
 
 
 def test_digest_payload_builds_weekly_balance_periods_and_real_problem_rows():
     source_snapshot = SimpleNamespace(
         source_status="fresh",
         orders=[
