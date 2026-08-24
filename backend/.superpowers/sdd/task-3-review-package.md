# Review Package Task 3 Final Re-review
Base: 339c574
Head: e28042d

## Commits
e28042d fix: preserve cached report metric semantics
ec2068d fix: cover cached report source ranges
01171d4 feat: materialize reports from wb sync cache

## Stat
 app/report_data_mart.py                            |   6 +-
 app/repricer_tasks.py                              |  62 ++---
 app/routers/wb_reports_bff.py                      | 297 +++++++++++++++++++++
 tests/test_report_data_mart.py                     |  47 ++++
 .../test_report_materialization_from_data_mart.py  | 165 ++++++++++++
 tests/test_wb_reports_bff.py                       |  15 +-
 6 files changed, 549 insertions(+), 43 deletions(-)

## Diff
diff --git a/app/report_data_mart.py b/app/report_data_mart.py
index 2d21a0b..1def023 100644
--- a/app/report_data_mart.py
+++ b/app/report_data_mart.py
@@ -75,21 +75,21 @@ def _is_stale(cache: Mapping[str, Any], *, now: datetime | None = None) -> bool:
     current = now or datetime.now(timezone.utc)
     return current - fetched_at > SOURCE_CACHE_TTL
 
 
 def _range_days(date_from: date, date_to: date) -> int:
     return max(1, (date_to - date_from).days + 1)
 
 
 def _candidate_keys(source: str, date_from: date, date_to: date, sync_status: Mapping[str, Any]) -> list[str]:
     days = _range_days(date_from, date_to)
-    keys: list[str] = []
+    keys = [f"{source}_{date_from.isoformat()}_{date_to.isoformat()}"]
     suffix = str(sync_status.get("periodCacheSuffix") or "").strip()
     if suffix:
         keys.append(f"{source}_{suffix}")
     keys.append(f"{source}_{days}")
     keys.append(source)
     return list(dict.fromkeys(keys))
 
 
 def _row_count(cache: Mapping[str, Any]) -> int | None:
     raw_count = cache.get("count")
@@ -120,20 +120,24 @@ def load_report_source_bundle(
     for source in required_sources:
         selected_key = source
         selected_cache: dict[str, Any] | None = None
         selected_status: SourceStatus = "missing"
         for key in _candidate_keys(source, date_from, date_to, sync_status):
             cache = get_cache(organization_id, key, slim=False) or {}
             if not cache:
                 continue
             selected_key = key
             selected_cache = cache
+            snapshot_fetched_at = _parse_datetime(cache.get("fetchedAt") or cache.get("finishedAt") or cache.get("completedAt"))
+            if source == "stocks" and key == "stocks" and snapshot_fetched_at is not None:
+                selected_status = "exact"
+                break
             if source_cache_matches_range(cache, date_from, date_to):
                 selected_status = "exact"
                 break
             if source_cache_covers_range(cache, date_from, date_to):
                 selected_status = "covering"
                 break
             selected_status = "partial"
 
         if selected_cache is None:
             missing_sources.append(source)
diff --git a/app/repricer_tasks.py b/app/repricer_tasks.py
index b0697a7..2700f72 100644
--- a/app/repricer_tasks.py
+++ b/app/repricer_tasks.py
@@ -89,26 +89,39 @@ def build_report_for_org(self, organization_id: int, user_id: str, report_id: st
         if required_sources:
             bundle = reports.load_report_source_bundle(
                 organization_id=organization_id,
                 date_from=date_from,
                 date_to=date_to,
                 required_sources=required_sources,
                 get_cache=reports.get_source_cache,
             )
             _assert_report_sources_available(report_id, bundle)
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
                 organization_id=organization_id,
                 wb_token=wb_token,
@@ -152,56 +165,37 @@ def build_report_for_org(self, organization_id: int, user_id: str, report_id: st
             cash_flow = reports.get_cash_flow_for_period(organization_id=organization_id, period_from=date_from, period_to=date_to, requested_by=user_id)
             if cash_flow.get("status") in {"pending", "processing"}:
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
     except Exception as exc:
         result = {"state": "failed", "taskId": self.request.id, "reportId": report_id, "dateFrom": date_from_iso, "dateTo": date_to_iso, "groupBy": group_by, "finishedAt": reports._utc_now_iso(), "error": str(exc)[:500]}
diff --git a/app/routers/wb_reports_bff.py b/app/routers/wb_reports_bff.py
index bf9f8cf..8a65861 100644
--- a/app/routers/wb_reports_bff.py
+++ b/app/routers/wb_reports_bff.py
@@ -158,20 +158,26 @@ def _previous_period(date_from: date, date_to: date) -> tuple[date, date]:
     previous_to = date_from - timedelta(days=1)
     return previous_to - timedelta(days=period_days - 1), previous_to
 
 
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
         if nm_id <= 0:
             continue
@@ -2330,20 +2336,311 @@ def _source_coverage_payload(bundle: ReportSourceBundle) -> list[dict[str, Any]]
             "dateFrom": item.date_from,
             "dateTo": item.date_to,
             "fetchedAt": item.fetched_at,
             "rowsCount": item.rows_count,
             "error": item.error,
         }
         for item in bundle.by_source.values()
     ]
 
 
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
+                "productStatus": "средний",
+                "abcCode": "CC",
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
diff --git a/tests/test_report_data_mart.py b/tests/test_report_data_mart.py
index aa45f17..527ac88 100644
--- a/tests/test_report_data_mart.py
+++ b/tests/test_report_data_mart.py
@@ -45,10 +45,57 @@ def test_load_report_source_bundle_reports_missing_and_stale_sources():
         get_cache=fake_get_cache,
     )
 
     assert bundle.covered is False
     assert bundle.status == "source_cache_miss"
     assert bundle.by_source["finance"].status == "stale"
     assert bundle.by_source["ads"].status == "exact"
     assert bundle.by_source["baskets"].status == "missing"
     assert bundle.missing_sources == ["baskets"]
     assert bundle.sources["ads"]["aggregates"]["101"]["adSpendKopecks"] == 1200
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
diff --git a/tests/test_report_materialization_from_data_mart.py b/tests/test_report_materialization_from_data_mart.py
index aa8d6c5..56dcfd0 100644
--- a/tests/test_report_materialization_from_data_mart.py
+++ b/tests/test_report_materialization_from_data_mart.py
@@ -68,10 +68,175 @@ def test_report_job_fails_fast_on_missing_source_cache(monkeypatch):
             "warehouse",
             "operational",
             True,
             "wb-token",
         )
 
     failed_jobs = [payload for key, payload in saved.items() if key.startswith("reports_job_stock")]
     assert failed_jobs
     assert failed_jobs[-1]["state"] == "failed"
     assert failed_jobs[-1]["error"] == "source_cache_miss: stocks"
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
diff --git a/tests/test_wb_reports_bff.py b/tests/test_wb_reports_bff.py
index ef5390b..f5fc2ed 100644
--- a/tests/test_wb_reports_bff.py
+++ b/tests/test_wb_reports_bff.py
@@ -486,28 +486,25 @@ def test_week_over_week_live_builder_uses_own_sources_not_abc_or_repricer(monkey
 
     assert snapshot_calls == [(date(2026, 6, 13), date(2026, 7, 14)), (date(2026, 5, 12), date(2026, 6, 12))]
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
     fetched_at = datetime.now(timezone.utc).isoformat()
     source_caches = {
         "wb_sync_status": {
             "state": "completed",
             "dateFrom": "2026-07-07",
             "dateTo": "2026-07-13",
             "periodDays": 7,
             "periodCacheSuffix": "7",
         },
         **{
@@ -515,40 +512,42 @@ def test_week_over_week_task_builds_current_and_previous_source_ranges(monkeypat
                 "dateFrom": "2026-07-07",
                 "dateTo": "2026-07-13",
                 "fetchedAt": fetched_at,
             }
             for source in wb_reports_bff.REPORT_REQUIRED_SOURCES["week-over-week"]
         },
     }
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
     monkeypatch.setattr(wb_reports_bff, "get_source_cache", lambda _organization_id, key, **_kwargs: source_caches.get(key, {}))
 
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
             {"nmId": 101, "finishedPrice": 1000, "lastChangeDate": "2026-05-02T10:00:00+03:00"},
             {"nmId": 101, "finishedPrice": 1200, "lastChangeDate": "2026-05-02T11:00:00+03:00"},
