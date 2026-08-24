# Live Week-over-Week Report Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make `/wb/reports/week-over-week` use real cached background-report data while preserving the existing visual screen.

**Architecture:** Extend the existing Celery `build_report_for_org` flow with a WoW branch. Build current and previous equal ranges from existing WB snapshots, normalize them into the existing report response shape, cache by organization/range/grouping, and let the frontend start/poll the job before rendering the cached payload.

**Tech Stack:** FastAPI, Celery, existing `source_cache`, Python/pytest, React/TypeScript, Vitest.

## Global Constraints

- Preserve the current WoW layout, labels, classes, and column order.
- Reuse existing WB sources; do not add a new WB integration.
- Do not infer or auto-apply SPP prices.
- Missing values are `null`/unavailable, never fabricated zeroes.
- Keep stale cached data visible while refresh is running.

---

### Task 1: Backend WoW range and payload contract

**Files:**
- Modify: `app/routers/wb_reports_bff.py`
- Test: `tests/test_wb_reports_bff.py`

**Interfaces:**
- Produce `_previous_period(date_from: date, date_to: date) -> tuple[date, date]`.
- Produce `_build_week_over_week_payload(date_range, current_snapshot, previous_snapshot, current_ads, previous_ads) -> dict[str, Any]`.

- [ ] Write failing tests for equal previous range, nonzero metric deltas, and null delta when baseline is unavailable.
- [ ] Run `pytest -q tests/test_wb_reports_bff.py -k week_over_week` and confirm failure because the current builder has no previous snapshot and hardcoded zeroes.
- [ ] Implement range pairing and a metric delta helper with `None` for missing/zero baselines.
- [ ] Build current physical values from existing sources and previous values from the preceding range; keep existing `meta`, `filters`, `columns`, OOS fields, and visual labels.
- [ ] Run the focused tests and confirm they pass.
- [ ] Commit `feat: build real week-over-week report payload`.

### Task 2: Backend background job and cache lifecycle

**Files:**
- Modify: `app/routers/wb_reports_bff.py`
- Modify: `app/repricer_tasks.py`
- Test: `tests/test_wb_reports_bff.py`

**Interfaces:**
- `BACKGROUND_REPORT_IDS` includes `week-over-week`.
- `build_report_for_org(... report_id="week-over-week" ...)` stores the exact response under the existing report cache key and updates the existing job cache key.

- [ ] Write failing tests for WoW job creation, duplicate job reuse, cache-only GET, and completed job response.
- [ ] Run the focused tests and confirm failure because the current job routes reject WoW and the task has no WoW branch.
- [ ] Add WoW to the route literals/allowlist and implement the task branch using existing source snapshot builders and the WoW payload builder.
- [ ] Ensure GET does not invoke WB when no cache exists; it returns the existing empty background response plus `reportJob`.
- [ ] Ensure a running job exposes stale cached data and a safe error on failure.
- [ ] Run focused backend tests and confirm they pass.
- [ ] Commit `feat: run week-over-week through report jobs`.

### Task 3: Backend source correctness and history state

**Files:**
- Modify: `app/routers/wb_reports_bff.py`
- Modify: `app/reports_history.py`
- Test: `tests/test_wb_reports_bff.py`
- Test: `tests/test_reports_history.py` (create if absent)

**Interfaces:**
- WoW rows expose `historySource`, `wasOutOfStock`, and exactly seven availability entries.
- Existing captured/backfilled semantics remain explicit.

- [ ] Write failing tests proving baskets/ads are sourced when cached, profit/margin are not seller revenue placeholders, and incomplete history is marked backfilled.
- [ ] Run the tests and confirm failure against current zero-valued baskets/margin and seller-revenue profit.
- [ ] Reuse existing ads and finance/ABC/RNP-derived fields where available; return `None` plus source metadata when unavailable.
- [ ] Keep the current seven-day history shape but prevent missing history from being presented as captured.
- [ ] Run backend report and history tests.
- [ ] Commit `fix: make week-over-week sources explicit`.

### Task 4: Frontend live WoW data flow

**Files:**
- Modify: `D:\ogni-frontend\frontend\src\features\vella-parity\VellaHtmlParityPage.tsx`
- Modify: `D:\ogni-frontend\frontend\src\features\wb-reports\api.ts`
- Modify: `D:\ogni-frontend\frontend\src\features\wb-reports\types.ts`
- Test: `D:\ogni-frontend\frontend\src\features\wb-reports\repository.test.ts`
- Test: frontend component/API tests adjacent to `VellaHtmlParityPage` (create only if the existing test setup supports it)

**Interfaces:**
- Add WoW live state with `loading | ready | error` and backend `reportJob`/`cache` fields.
- Add `fetchReportJob(reportId, dateRange)` and `startReportJob(reportId, dateRange)` using `/api/wb/reports/{reportId}/jobs`.

- [ ] Write failing tests proving the WoW route starts/reuses the job, reads the backend rows, and does not render hardcoded `+12.4%`/`+9.1%` values.
- [ ] Run the frontend tests and confirm failure because `WeekReportIsland` currently has no fetch and `WeekWorkbenchIsland` uses literals.
- [ ] Implement a live WoW hook following the existing RNP/Stock polling pattern, with a bounded timer and cancellation on unmount.
- [ ] Replace mock signals and legacy `renderSecondaryReports` table binding with backend-driven rows while preserving DOM classes and visual structure.
- [ ] Wire existing filters to the live row set and show unavailable values for null metrics.
- [ ] Run focused frontend tests and typecheck.
- [ ] Commit `feat: connect week-over-week screen to live report data`.

### Task 5: Verification and rendered smoke test

**Files:**
- Modify only if verification reveals a defect.

- [ ] Run `pytest -q tests/test_wb_reports_bff.py tests/test_reports_history.py`.
- [ ] Run the frontend report tests and the repository's typecheck/build command.
- [ ] Start the frontend using its existing package script and verify `/wb/reports/week-over-week` renders the real loading/data states without framework overlays or console errors.
- [ ] Exercise one date-range/job refresh and one report filter; verify the visible state changes.
- [ ] Inspect `git diff` and `git status`; report any remaining limitations instead of claiming unverified success.
