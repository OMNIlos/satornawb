### Task 3: Cached Source Materializers for Stock, Ads, and Week-over-Week

**Files:**
- Modify: `app/routers/wb_reports_bff.py`
- Modify: `app/repricer_tasks.py`
- Test: `tests/test_report_materialization_from_data_mart.py`

**Interfaces:**
- Consumes: `ReportSourceBundle.sources` from Task 1.
- Produces: `_build_stock_report_from_data_mart(date_range: dict[str, str], bundle: ReportSourceBundle, organization_id: int) -> dict[str, Any]`.
- Produces: `_build_ads_report_from_data_mart(date_range: dict[str, str], bundle: ReportSourceBundle) -> dict[str, Any]`.
- Produces: `_build_week_over_week_from_data_mart(date_range: dict[str, str], current_bundle: ReportSourceBundle, previous_bundle: ReportSourceBundle, organization_id: int) -> dict[str, Any]`.

- [ ] **Step 1: Write failing tests for cached materializers**

Append to `tests/test_report_materialization_from_data_mart.py`:

```python
def test_stock_job_materializes_from_cached_stocks(monkeypatch):
    saved: dict[str, dict] = {}
    source_state = {
        "wb_sync_status": {"state": "completed", "dateFrom": "2026-07-01", "dateTo": "2026-07-07", "periodDays": 7, "periodCacheSuffix": "7"},
        "stocks_7": {
            "dateFrom": "2026-07-01",
            "dateTo": "2026-07-07",
            "fetchedAt": "2026-07-07T12:00:00+00:00",
            "aggregates": {"101": {"nmId": 101, "sku": "SKU-101", "wbStockUnits": 5, "warehouseName": "Коледино"}},
        },
        "period_stats_7": {
            "dateFrom": "2026-07-01",
            "dateTo": "2026-07-07",
            "fetchedAt": "2026-07-07T12:00:00+00:00",
            "aggregates": {"101": {"ordersUnits": 14, "salesUnits": 7}},
        },
    }

    monkeypatch.setattr(wb_reports_bff, "get_source_cache", lambda _organization_id, key, **_kwargs: source_state.get(key, {}))
    monkeypatch.setattr(wb_reports_bff, "save_source_cache", lambda _organization_id, key, payload: saved.__setitem__(key, payload))
    monkeypatch.setattr(
        wb_reports_bff,
        "build_wb_reports_sources_snapshot",
        lambda **_kwargs: pytest.fail("stock materializer must use cached source bundle"),
    )

    result = repricer_tasks.build_report_for_org.run(
        1, "user-1", "stock", "2026-07-01", "2026-07-07", "warehouse", "operational", True, "wb-token"
    )

    assert result["state"] == "completed"
    payloads = [payload for key, payload in saved.items() if key.startswith("reports_payload_stock")]
    assert payloads
    report = payloads[-1]["report"]
    assert report["meta"]["id"] == "stock"
    assert report["rows"][0]["nmId"] == 101
    assert report["rows"][0]["availableUnits"] == 5
    assert report["sourceCoverage"][0]["status"] == "exact"


def test_week_over_week_job_returns_null_deltas_when_previous_range_missing(monkeypatch):
    saved: dict[str, dict] = {}
    source_state = {
        "wb_sync_status": {"state": "completed", "dateFrom": "2026-07-01", "dateTo": "2026-07-07", "periodDays": 7, "periodCacheSuffix": "7"},
        "finance_7": {"dateFrom": "2026-07-01", "dateTo": "2026-07-07", "fetchedAt": "2026-07-07T12:00:00+00:00", "aggregates": {"101": {"salesUnits": 2, "sellerRevenueKopecks": 20000}}},
        "period_stats_7": {"dateFrom": "2026-07-01", "dateTo": "2026-07-07", "fetchedAt": "2026-07-07T12:00:00+00:00", "aggregates": {"101": {"ordersUnits": 3, "revenueKopecks": 30000}}},
        "ads_7": {"dateFrom": "2026-07-01", "dateTo": "2026-07-07", "fetchedAt": "2026-07-07T12:00:00+00:00", "aggregates": {"101": {"adSpendKopecks": 400, "cartCount": 5}}},
        "baskets_7": {"dateFrom": "2026-07-01", "dateTo": "2026-07-07", "fetchedAt": "2026-07-07T12:00:00+00:00", "aggregates": {"101": {"cartCount": 5}}},
        "stocks_7": {"dateFrom": "2026-07-01", "dateTo": "2026-07-07", "fetchedAt": "2026-07-07T12:00:00+00:00", "aggregates": {"101": {"nmId": 101, "sku": "SKU-101", "wbStockUnits": 8}}},
    }

    monkeypatch.setattr(wb_reports_bff, "get_source_cache", lambda _organization_id, key, **_kwargs: source_state.get(key, {}))
    monkeypatch.setattr(wb_reports_bff, "save_source_cache", lambda _organization_id, key, payload: saved.__setitem__(key, payload))
    monkeypatch.setattr(
        wb_reports_bff,
        "build_wb_reports_sources_snapshot",
        lambda **_kwargs: pytest.fail("WoW materializer must use cached source bundles"),
    )
    monkeypatch.setattr(
        wb_reports_bff,
        "build_ads_attribution_snapshot",
        lambda **_kwargs: pytest.fail("WoW materializer must use cached ads bundles"),
    )

    result = repricer_tasks.build_report_for_org.run(
        1, "user-1", "week-over-week", "2026-07-01", "2026-07-07", "sku", "operational", True, "wb-token"
    )

    assert result["state"] == "completed"
    payloads = [payload for key, payload in saved.items() if key.startswith("reports_payload_week-over-week")]
    report = payloads[-1]["report"]
    assert report["rows"][0]["sku"] == "SKU-101"
    assert report["rows"][0]["orders"]["units"] == 3
    assert report["rows"][0]["orders"]["deltaPct"] is None
    assert report["cache"]["previousRangeStatus"] == "source_cache_miss"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest -q tests/test_report_materialization_from_data_mart.py -k "materializes_from_cached or previous_range_missing"`

Expected: FAIL because cached stock and WoW materializers do not exist.

- [ ] **Step 3: Add stock cached materializer**

In `app/routers/wb_reports_bff.py`, add:

```python
def _aggregate_map(bundle: ReportSourceBundle, source: str) -> dict[str, dict[str, Any]]:
    payload = bundle.sources.get(source) or {}
    aggregates = payload.get("aggregates")
    return aggregates if isinstance(aggregates, dict) else {}


def _build_stock_report_from_data_mart(date_range: dict[str, str], bundle: ReportSourceBundle, organization_id: int) -> dict[str, Any]:
    stock_aggregates = _aggregate_map(bundle, "stocks")
    period_stats = _aggregate_map(bundle, "period_stats")
    rows: list[dict[str, Any]] = []
    for raw_nm_id, stock in stock_aggregates.items():
        if not isinstance(stock, dict):
            continue
        nm_id = _int_value(stock.get("nmId") or raw_nm_id)
        stats = period_stats.get(str(nm_id), {})
        available = _int_value(stock.get("availableUnits") or stock.get("wbStockUnits") or stock.get("quantity"))
        orders_units = _int_value(stats.get("ordersUnits"))
        days = max(1, (date.fromisoformat(date_range["to"]) - date.fromisoformat(date_range["from"])).days + 1)
        rows.append(
            {
                "sku": str(stock.get("sku") or stock.get("vendorCode") or f"NM_{nm_id}"),
                "nmId": nm_id,
                "warehouseName": stock.get("warehouseName") or "all_wb_warehouses",
                "clusterName": stock.get("clusterName") or stock.get("regionName") or "unknown",
                "wbStockUnits": available,
                "fromClientUnits": _int_value(stock.get("fromClientUnits") or stock.get("inWayFromClient")),
                "toClientUnits": _int_value(stock.get("toClientUnits") or stock.get("inWayToClient")),
                "availableUnits": available,
                "ordersPerDay": round(orders_units / days, 2) if orders_units else 0,
                "daysToOos": round(available / max(orders_units / days, 0.01), 1) if available else 0,
                "ktrIndex": None,
                "localizationPct": None,
                "logisticsPerUnitKopecks": None,
                "decision": "норма" if available > 0 else "draft",
                "decisionStatus": "confirmed" if available > 0 else "draft",
                "historyCoverageDays": 0,
                "historySource": "source_cache",
            }
        )
    return {
        "meta": _meta("stock", "Остатки WB", "Остатки построены из WB sync source cache.", "operational", "fresh" if bundle.covered else "partial"),
        "headline": "Отчёт построен из source cache последнего WB sync.",
        "filters": {"dateRange": date_range, "groupBy": "warehouse"},
        "kpis": [_kpi("stock_rows", "SKU x складов", str(len(rows)))],
        "chart": {"title": "Доступность по складам", "valueLabel": "Доступно, шт", "points": [{"label": row["warehouseName"], "value": row["availableUnits"]} for row in rows[:20]]},
        "columns": [
            {"key": "sku", "label": "Артикул"},
            {"key": "nmId", "label": "WB"},
            {"key": "warehouseName", "label": "Склад WB"},
            {"key": "availableUnits", "label": "Доступно"},
        ],
        "rows": rows,
        "sourceCoverage": _source_coverage_payload(bundle),
    }
```

- [ ] **Step 4: Add week-over-week cached materializer**

In `app/routers/wb_reports_bff.py`, add:

```python
def _build_week_over_week_from_data_mart(
    date_range: dict[str, str],
    current_bundle: ReportSourceBundle,
    previous_bundle: ReportSourceBundle,
    organization_id: int,
) -> dict[str, Any]:
    current_finance = _aggregate_map(current_bundle, "finance")
    current_period = _aggregate_map(current_bundle, "period_stats")
    current_ads = _aggregate_map(current_bundle, "ads")
    current_baskets = _aggregate_map(current_bundle, "baskets")
    current_stocks = _aggregate_map(current_bundle, "stocks")
    previous_period = _aggregate_map(previous_bundle, "period_stats")
    previous_finance = _aggregate_map(previous_bundle, "finance")
    previous_baskets = _aggregate_map(previous_bundle, "baskets")
    rows: list[dict[str, Any]] = []

    for raw_nm_id, period in current_period.items():
        if not isinstance(period, dict):
            continue
        nm_id = _int_value(period.get("nmId") or raw_nm_id)
        finance = current_finance.get(str(nm_id), {})
        ads = current_ads.get(str(nm_id), {})
        baskets = current_baskets.get(str(nm_id), {})
        stock = current_stocks.get(str(nm_id), {})
        previous = previous_period.get(str(nm_id), {})
        previous_finance_row = previous_finance.get(str(nm_id), {})
        previous_basket_row = previous_baskets.get(str(nm_id), {})
        orders_units = _int_value(period.get("ordersUnits"))
        sales_units = _int_value(finance.get("salesUnits") or period.get("salesUnits"))
        revenue = _int_value(finance.get("sellerRevenueKopecks") or period.get("revenueKopecks"))
        previous_revenue = _int_value(previous_finance_row.get("sellerRevenueKopecks") or previous.get("revenueKopecks"))
        profit = revenue - _int_value(finance.get("commissionKopecks")) - _int_value(finance.get("logisticsKopecks")) - _int_value(ads.get("adSpendKopecks"))
        previous_profit = previous_revenue - _int_value(previous_finance_row.get("commissionKopecks")) - _int_value(previous_finance_row.get("logisticsKopecks"))
        stock_units = _int_value(stock.get("availableUnits") or stock.get("wbStockUnits") or stock.get("quantity"))
        rows.append(
            {
                "sku": str(stock.get("sku") or finance.get("sku") or period.get("sku") or f"NM_{nm_id}"),
                "nmId": nm_id,
                "productName": stock.get("productName") or finance.get("productName"),
                "productStatus": "средний",
                "abcCode": "CC",
                "orders": {"units": orders_units, "kopecks": _int_value(period.get("ordersKopecks") or period.get("revenueKopecks")), "deltaPct": _delta_pct(orders_units, _int_value(previous.get("ordersUnits")))},
                "sales": {"units": sales_units, "kopecks": revenue, "deltaPct": _delta_pct(sales_units, _int_value(previous_finance_row.get("salesUnits") or previous.get("salesUnits")))},
                "baskets": {"units": _int_value(baskets.get("cartCount") or baskets.get("baskets")), "kopecks": None, "deltaPct": _delta_pct(_int_value(baskets.get("cartCount") or baskets.get("baskets")), _int_value(previous_basket_row.get("cartCount") or previous_basket_row.get("baskets")))},
                "marginPct": {"percent": _calc_margin_pct(profit, revenue), "deltaPct": _delta_pct(_calc_margin_pct(profit, revenue), _calc_margin_pct(previous_profit, previous_revenue))},
                "profit": {"kopecks": profit, "deltaPct": _delta_pct(profit, previous_profit if previous_bundle.covered else None)},
                "wasOutOfStock": stock_units <= 0,
                "stockAvailability7d": [stock_units > 0] * 7,
                "stockOutDays": 0 if stock_units > 0 else 7,
                "stockSnapshotCoveragePct": 0,
                "historySource": "source_cache",
                "conclusion": "WoW построен из cached source snapshots.",
            }
        )

    payload = _week_over_week_shell(date_range, rows, source_status="fresh" if current_bundle.covered else "partial")
    payload["cache"] = {
        "status": "exact" if current_bundle.covered else current_bundle.status,
        "previousRangeStatus": "exact" if previous_bundle.covered else previous_bundle.status,
        "sourceCoverage": _source_coverage_payload(current_bundle),
    }
    payload["sourceCoverage"] = _source_coverage_payload(current_bundle)
    return payload
```

- [ ] **Step 5: Route task branches to cached materializers**

In `app/repricer_tasks.py`, replace the `stock` branch body with:

```python
        if report_id == "stock":
            progress("stock-cache", "Собираем остатки из WB sync cache", 30)
            bundle = reports.load_report_source_bundle(
                organization_id=organization_id,
                date_from=date_from,
                date_to=date_to,
                required_sources=reports.REPORT_REQUIRED_SOURCES["stock"],
            )
            report = reports._build_stock_report_from_data_mart(date_range, bundle, organization_id)
```

Replace the `week-over-week` branch body with:

```python
        elif report_id == "week-over-week":
            progress("week-cache", "Собираем WoW из WB sync cache", 30)
            current_bundle = reports.load_report_source_bundle(
                organization_id=organization_id,
                date_from=date_from,
                date_to=date_to,
                required_sources=reports.REPORT_REQUIRED_SOURCES["week-over-week"],
            )
            previous_from, previous_to = reports._previous_period(date_from, date_to)
            previous_bundle = reports.load_report_source_bundle(
                organization_id=organization_id,
                date_from=previous_from,
                date_to=previous_to,
                required_sources=reports.REPORT_REQUIRED_SOURCES["week-over-week"],
            )
            report = reports._build_week_over_week_from_data_mart(date_range, current_bundle, previous_bundle, organization_id)
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `pytest -q tests/test_report_materialization_from_data_mart.py`

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add app/routers/wb_reports_bff.py app/repricer_tasks.py tests/test_report_materialization_from_data_mart.py
git commit -m "feat: materialize reports from wb sync cache"
```

---

