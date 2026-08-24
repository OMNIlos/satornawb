# Task 3 Report: Cached Source Materializers for Stock, Ads, and Week-over-Week

## Status

DONE_WITH_CONCERNS

## Clarification Applied

The Task 3 brief omitted the Ads branch replacement even though its title and required interfaces included Ads. The user confirmed that Ads is in scope. This implementation adds `_build_ads_report_from_data_mart(...)`, routes the Ads background job through it after the Task 2 guard, and verifies it does not invoke `build_ads_attribution_snapshot(...)`.

## Implementation

- Added cached data-mart materializers for Stock, Ads, and Week-over-Week in `app/routers/wb_reports_bff.py`.
- Routed Stock, Ads, and Week-over-Week job branches in `app/repricer_tasks.py` through `load_report_source_bundle(...)` and the materializers after the existing source-coverage guard.
- Removed direct live WB source/ads builder calls from those three job branches.
- Kept source coverage and cache metadata on each materialized report.
- Preserved unavailable cached metrics as `None`; in particular, WoW treats every non-covered previous bundle as unavailable and returns `previousRangeStatus: source_cache_miss` with null deltas.
- Updated the directly affected legacy WoW task test from live-source expectations to cache-only expectations.

## TDD Evidence

1. Added Stock, Ads, and WoW cache-materialization tests before production edits.
2. Initial run reached the Task 2 guard because the brief's fixed `2026-07-07` `fetchedAt` value is now older than the 24-hour cache TTL. Test fixtures now use `_utc_now_iso()` so they exercise materialization rather than cache expiry.
3. Red run after that change failed at the intended forbidden calls:
   - Stock: `build_wb_reports_sources_snapshot(...)`
   - Ads: `build_ads_attribution_snapshot(...)`
   - WoW: `build_wb_reports_sources_snapshot(...)`
4. Green runs:
   - `pytest -q tests/test_report_materialization_from_data_mart.py -k "materializes_from_cached or previous_range_missing"` -> `3 passed, 2 deselected`
   - `pytest -q tests/test_report_materialization_from_data_mart.py` -> `5 passed`
   - `pytest -q tests/test_wb_reports_bff.py::test_week_over_week_task_materializes_current_and_previous_cache_ranges tests/test_report_materialization_from_data_mart.py` -> `6 passed`
   - `git diff --check` -> clean

## Concern

`pytest -q tests/test_wb_reports_bff.py tests/test_report_materialization_from_data_mart.py` exceeded the 120-second command limit before returning output. The directly affected legacy test and full Task 3 test module pass independently. Pytest also reports a non-fatal permission warning when writing `.pytest_cache`.

## Review Fixes

- `app/report_data_mart.py` now probes `source_YYYY-MM-DD_YYYY-MM-DD` first, independently of `wb_sync_status.periodCacheSuffix`, so current and previous explicit-range bundles are discoverable.
- Timestamped bare `stocks` snapshots now receive typed `exact` coverage (or `stale` through the existing TTL check) without fabricated range metadata.
- Stock materialization now uses `availableUnits`, then `wbStockUnits`, then `quantity + inWayFromClient`; it restores the operational stock table fields and columns, including decision and comment.
- Ads materialization is explicitly a SKU-level source-cache report. It no longer invents campaign identity or claims campaign attribution when sync aggregates do not contain it.
- Added a positive WoW explicit-previous-range test that verifies `previousRangeStatus: exact` and a non-null order delta.

## Review Fix Verification

- `pytest -q tests/test_report_data_mart.py tests/test_report_materialization_from_data_mart.py` -> `10 passed`
- `pytest -q tests/test_wb_reports_bff.py::test_week_over_week_task_materializes_current_and_previous_cache_ranges` -> `1 passed`
- `python -m compileall -q app/report_data_mart.py app/routers/wb_reports_bff.py app/repricer_tasks.py` -> passed
- `git diff --check` -> clean

## Final Metric Correctness Fixes

- WoW now reads the covered previous Ads aggregate and subtracts its `adSpendKopecks` when calculating previous profit and margin deltas.
- Added a shared stock snapshot availability rule: explicit `availableUnits`, otherwise `quantity + inWayFromClient`, otherwise `wbStockUnits`. Both Stock and WoW now use it.
- Cached WoW no longer derives seven-day availability or stock-out counts from a single stock snapshot; the history-like fields remain `null` without genuine history.
- Stock `daysToOos` now remains `null` when known orders are zero.

## Final Metric Verification

- `pytest -q tests/test_report_data_mart.py tests/test_report_materialization_from_data_mart.py` -> `10 passed`
- `pytest -q tests/test_wb_reports_bff.py::test_week_over_week_task_materializes_current_and_previous_cache_ranges` -> `1 passed`
- `git diff --check` -> clean
