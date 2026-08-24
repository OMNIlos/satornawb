# Task 6: Final Verification Report

## Final Backend Fix

### Status

DONE_WITH_CONCERNS

### Commit

- `97b0020 fix: harden report prewarm cache safety`

### Fixes

- Aggregate source bundles now require exact range coverage; broader finance, ads, period stats, and basket totals remain partial.
- Automatic prewarm is limited to cache-only `stock` and `week-over-week` materializers with exact source coverage.
- Prewarm skips existing payloads and queued, running, or completed jobs.
- P&L, RNP, ABC, Ads, and digest are excluded from automatic prewarm and documented as follow-ups.
- WoW emits null classification fields when source data has no real `productStatus` or `abcCode`.
- POST report job creation returns `source_cache_miss` without calling `.delay()` when required source coverage is invalid.

### Tests

- `pytest -q tests/test_report_data_mart.py tests/test_report_materialization_from_data_mart.py tests/test_report_prewarm.py tests/test_wb_reports_bff.py::test_report_job_endpoint_returns_source_cache_miss_without_enqueuing tests/test_wb_reports_bff.py::test_week_over_week_job_endpoint_starts_and_reuses_task tests/test_wb_reports_bff.py::test_week_over_week_job_endpoint_reuses_completed_cached_report tests/test_wb_reports_bff.py::test_week_over_week_job_endpoint_restarts_stale_running_job`: PASS, 23 tests.
- `git diff --check`: PASS.

### Concerns

- The full `tests/test_wb_reports_bff.py` run did not complete within two minutes and was terminated. All four router tests affected by this patch pass.
- Pytest reports a pre-existing Windows permission warning for `.pytest_cache`; it does not affect test results.
