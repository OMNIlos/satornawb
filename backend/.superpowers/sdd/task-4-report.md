# Task 4: Hot Range Prewarm After WB Sync

## Status

Completed with concerns.

## Implementation

- Added `app/report_prewarm.py` with the required `HOT_REPORT_IDS`, `HOT_RANGE_DAYS`, date-range normalization, report grouping, and task-enqueue payload generation.
- Added `_prewarm_callback` to `refresh_wb_data_sources` and attach `reportPrewarm` only to completed sync results.
- The default callback lazily imports `prewarm_report_payloads` and `build_report_for_org` in the completed, locked-sync path. `app.report_prewarm` does not import Celery task objects at module load time.
- Any prewarm exception is contained as `reportPrewarm: {"state": "failed", "error": ...}` and cannot fail the WB sync.
- The parallel WB sync completion path applies the same prewarm result handling. Its internal per-source worker calls use a no-op callback so they cannot enqueue duplicate prewarms.
- Cache-only/internal calls with `execute_lock=False` do not invoke the default Celery prewarm callback. Explicit injected callbacks still run, enabling isolated testing and preventing report-internal cache refreshes from recursively enqueuing report jobs.

## Tests

- Added `tests/test_report_prewarm.py`.
- Confirmed the initial RED state: `pytest -q tests/test_report_prewarm.py` failed with `ModuleNotFoundError: No module named 'app.report_prewarm'`.
- Final focused run: `pytest -q tests/test_report_prewarm.py` passed: 2 tests.
- `git diff --check` passed.

## Concern

- `pytest -q tests/test_wb_repricer_bff.py` exceeded the 120-second command timeout twice. The focused prewarm tests pass; the suite timeout is recorded as residual verification risk.
- Pytest emits an existing warning that it cannot write `.pytest_cache` due to filesystem access denial.

## Review Fixes

- Removed `abc` from `HOT_REPORT_IDS`. A code comment records that ABC remains excluded until it has a cache-only materializer because its current job triggers a WB sync.
- Added `REPORT_PREWARM_REQUIRED_SOURCES` and gate the default callback on a completed, locked sync that updated `stocks`, `period-stats`, `finance`, `ads`, and `baskets`. Partial source syncs now return without a `reportPrewarm` key and do not import the report task or call Celery.
- Kept explicit `_prewarm_callback` behavior unchanged, including the existing focused callback test. Parallel internal source calls retain their no-op callback, preventing duplicate prewarms.
- Extended `tests/test_report_prewarm.py` for ABC exclusion, partial locked-sync skipping, and contained failure from the lazily imported default prewarm helper.

## Review Fix Verification

- `pytest -q tests/test_report_prewarm.py`: 4 passed.
- `pytest -q tests/test_wb_repricer_bff.py::test_wb_sync_goods_step_persists_spp_heartbeat_progress`: 1 passed.
- `git diff --check`: passed.

## Remaining Concern

- The existing `.pytest_cache` access-denied warning remains; it does not affect test outcomes.
