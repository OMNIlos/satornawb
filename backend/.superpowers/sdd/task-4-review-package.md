# Review Package Task 4 Re-review
Base: e28042d
Head: 535f422

## Commits
535f422 fix: restrict report prewarm coverage
62ab4bc feat: prewarm report payloads after wb sync

## Stat
 app/report_prewarm.py        | 73 +++++++++++++++++++++++++++++++++
 app/repricer_sync.py         | 33 ++++++++++++++-
 tests/test_report_prewarm.py | 98 ++++++++++++++++++++++++++++++++++++++++++++
 3 files changed, 202 insertions(+), 2 deletions(-)

## Diff
diff --git a/app/report_prewarm.py b/app/report_prewarm.py
new file mode 100644
index 0000000..d05593e
--- /dev/null
+++ b/app/report_prewarm.py
@@ -0,0 +1,73 @@
+from __future__ import annotations
+
+from datetime import date, timedelta
+from typing import Any, Callable, Mapping
+
+
+# ABC is excluded until it has a cache-only materializer; its current job triggers a WB sync.
+HOT_REPORT_IDS = ("rnp", "pnl", "ads", "stock", "week-over-week")
+HOT_RANGE_DAYS = (1, 7, 14, 30)
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
+def _group_by(report_id: str) -> str:
+    return "warehouse" if report_id == "stock" else "campaign" if report_id == "ads" else "sku"
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
+) -> list[dict[str, Any]]:
+    queued: list[dict[str, Any]] = []
+    for start, end in _hot_ranges(sync_status):
+        for report_id in HOT_REPORT_IDS:
+            group_by = _group_by(report_id)
+            source = "financial" if report_id == "pnl" else "operational"
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
index 98d7947..259cbda 100644
--- a/app/repricer_sync.py
+++ b/app/repricer_sync.py
@@ -43,20 +43,21 @@ try:
     import httpx
 except Exception:  # pragma: no cover - httpx is a runtime dependency, kept defensive for import safety
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
 
 
 def _good_nm_id(good: dict[str, Any]) -> int | None:
@@ -660,20 +661,21 @@ def refresh_wb_data_sources(
     period_days: int = 30,
     date_from: date | None = None,
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
             organization_id,
             trigger=trigger,
@@ -699,20 +701,44 @@ def refresh_wb_data_sources(
         "WB repricer sync started org=%s trigger=%s periodDays=%s sources=%s token=%s",
         organization_id,
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
         "baskets": ("Считаем добавления в корзину", "WB API · воронка продаж"),
     }
@@ -814,45 +840,47 @@ def refresh_wb_data_sources(
                 period_days=resolved_period_days,
                 date_from=date_from,
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
         dependent = [source for source in resolved_sources if source in {"finance", "baskets"}]
         with progress_lock:
             persist_parallel_progress()
         with ThreadPoolExecutor(max_workers=4, thread_name_prefix="wb-sync") as executor:
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
                 external_spp_matched_count = 0
                 wb_sync_price_change_count = 0
@@ -1048,17 +1076,18 @@ def refresh_wb_data_sources(
                         include_daily=False,
                         progress_callback=report_baskets_progress,
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
diff --git a/tests/test_report_prewarm.py b/tests/test_report_prewarm.py
new file mode 100644
index 0000000..b81b6f6
--- /dev/null
+++ b/tests/test_report_prewarm.py
@@ -0,0 +1,98 @@
+from __future__ import annotations
+
+from app.report_prewarm import prewarm_report_payloads
+
+
+def test_prewarm_enqueues_hot_reports_and_ranges():
+    calls: list[tuple] = []
+    sync_status = {
+        "state": "completed",
+        "dateFrom": "2026-07-01",
+        "dateTo": "2026-07-30",
+        "periodDays": 30,
+        "periodCacheSuffix": "30",
+    }
+
+    result = prewarm_report_payloads(
+        organization_id=1,
+        user_id="sync",
+        sync_status=sync_status,
+        finance_allowed=True,
+        wb_token="token",
+        enqueue=lambda *args: calls.append(args) or type("Task", (), {"id": f"task-{len(calls)}"})(),
+    )
+
+    report_ids = {item["reportId"] for item in result}
+    assert "abc" not in report_ids
+    assert {"rnp", "pnl", "ads", "stock", "week-over-week"} <= report_ids
+    assert any(item["dateFrom"] == "2026-07-24" and item["dateTo"] == "2026-07-30" for item in result)
+    assert any(item["dateFrom"] == "2026-07-01" and item["dateTo"] == "2026-07-30" for item in result)
+    assert calls
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
