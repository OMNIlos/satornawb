# Task 2: Cache-Only Report Materialization Guard

## Status

DONE_WITH_CONCERNS

## Implemented

- Added `REPORT_REQUIRED_SOURCES` with the required source sets for all background reports.
- Added GET-time source coverage checks for `week-over-week` and other background reports before they return the empty background payload.
- Added the `source_cache_miss` response payload, including requested range, missing sources, source coverage, sync status, empty rows, and the normalized job state.
- Added a queued-job guard that loads the required source bundle and persists a failed job before any live report builder runs when coverage is unavailable.
- Added `_assert_report_sources_available(...)` in `app.repricer_tasks`.
- Passed the router cache getter explicitly into `load_report_source_bundle(...)` so the guard uses the same cache dependency as the router and remains testable with the required monkeypatches.
- Added the requested regression tests in `tests/test_report_materialization_from_data_mart.py`.

## TDD Evidence

- Red run attempted: `pytest -q tests/test_report_materialization_from_data_mart.py`
  - Timed out after 124 seconds without pytest output.
- Green run attempted: `pytest -q tests/test_report_materialization_from_data_mart.py tests/test_report_data_mart.py`
  - Timed out after 304 seconds, then again after 124 seconds, without pytest output.
- Passing focused coverage test: `pytest -q tests/test_report_data_mart.py`
  - Result: `2 passed, 1 warning` in 0.41s.
- Passing direct task guard check:
  - Used the same missing-cache inputs as the requested task test.
  - Confirmed `RuntimeError("source_cache_miss: stocks")`, a saved failed report job with that error, and no live WB source builder invocation.
- Static validation: `python -m compileall -q app/routers/wb_reports_bff.py app/repricer_tasks.py tests/test_report_materialization_from_data_mart.py` passed.

## Concern

The integration test module stalls before pytest emits collection or test output in this workspace. Direct module imports succeed, and the task guard behavior passes when invoked directly. The remaining unverified path is the FastAPI/TestClient GET assertion in the new test, pending resolution of the local pytest/TestClient/auth harness stall.

## Task 2 Fix

The stall was isolated to `auth_headers(api, "viewer")` in the first regression test, before the report GET ran. The test no longer imports or uses `tests.test_app.client` or `auth_headers`; it now calls `wb_reports_bff.get_reports_by_id(...)` directly with a fake request and monkeypatched actor, permission, cache, and live-WB collaborators.

Verification after the fix:

- `pytest -q tests/test_report_materialization_from_data_mart.py`: `2 passed, 1 warning` in 1.31s.
- `pytest -q tests/test_report_data_mart.py tests/test_report_materialization_from_data_mart.py`: `4 passed, 1 warning` in 1.34s.

The remaining warning is pytest's inability to write `.pytest_cache` due to workspace permissions; it does not affect test execution.

## Legacy Test Compatibility Fix

The cache-only guard correctly prevented legacy task tests from reaching their intended live-builder or 1C-retry branches when their source-cache prerequisites were absent.

- `test_week_over_week_task_builds_current_and_previous_source_ranges` now seeds fresh exact coverage for all `REPORT_REQUIRED_SOURCES["week-over-week"]` sources and `wb_sync_status`. It continues to verify that the pre-Task-3 job path invokes current and previous live source builders after coverage is present.
- `test_pnl_report_task_waits_for_1c_before_building` now seeds exact `finance` and `ads` coverage with `wb_sync_status`, so it deterministically reaches its intended 1C `Retry` assertion instead of calling the real cache store.

Verification after the legacy compatibility fix:

- `pytest -q tests/test_wb_reports_bff.py::test_week_over_week_task_builds_current_and_previous_source_ranges`: `1 passed, 1 warning` in 1.68s.
- `pytest -q tests/test_report_materialization_from_data_mart.py tests/test_report_data_mart.py`: `4 passed, 1 warning` in 1.31s.
- `pytest -q tests/test_repricer_tasks.py::test_pnl_report_task_waits_for_1c_before_building`: `1 passed, 1 warning` in 1.27s.

## Cash-Flow Fixture Compatibility Fix

`test_cash_flow_job_queue_roundtrip_and_pnl_attachment` now seeds its local `report_cache` before the P&L task call with a completed `wb_sync_status` record and fresh exact `finance_30` and `ads_30` entries for 2026-06-01 through 2026-06-30. This satisfies the P&L source-cache guard while retaining the existing cash-flow attachment assertions.

Verification after the cash-flow fixture fix:

- `pytest -q tests/test_one_c_cash_flow.py::test_cash_flow_job_queue_roundtrip_and_pnl_attachment` timed out after 184 seconds without pytest output in this workspace's existing TestClient/auth harness.
- `pytest -q tests/test_wb_reports_bff.py::test_week_over_week_task_builds_current_and_previous_source_ranges tests/test_report_materialization_from_data_mart.py tests/test_report_data_mart.py`: `5 passed, 1 warning` in 1.76s.
