# Background WB Report Jobs Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Serve RNP, Ads, P&L and Stock from persisted cache and refresh them only in deduplicated background jobs, while the frontend never renders static mock tables.

**Architecture:** Reuse the digest task/status pattern with report-specific cache/job keys in `source_cache`. GET becomes cache-only, POST creates/reuses a Celery task, and status polling drives the React report islands. The legacy Vella renderer is fenced out of the four report roots.

**Tech Stack:** FastAPI, Celery, existing `source_cache`, React/TypeScript, Vitest, pytest.

## Global Constraints

- No new DB tables; reuse persisted caches already in the project.
- Exactly one active job per organization/report/range/groupBy.
- GET report endpoints must never synchronously call WB for these four reports.
- No static/mocked report rows may be visible in loading or error state.

---

### Task 1: Generalize report job state in the backend

**Files:**
- Modify: `app/routers/wb_reports_bff.py`
- Modify: `app/repricer_tasks.py`
- Test: `tests/test_wb_reports_bff.py`

**Interfaces:**
- Produces `_report_job_cache_key(report_id, date_from, date_to, group_by)` and cache-only GET payloads with `reportJob`.
- Produces `POST/GET /api/wb/reports/{report_id}/jobs`.

- [ ] Write failing tests proving GET returns a cached report plus running status and does not call its builder; POST reuses an existing running job.
- [ ] Run `pytest -q tests/test_wb_reports_bff.py -k report_job` and verify red.
- [ ] Implement shared job/cache-key helpers, cache-only GET behavior and job routes.
- [ ] Add a Celery `build_report_for_org` task that records queued/running/completed/failed state and persists the exact report cache.
- [ ] Run the focused pytest selection and verify green.

### Task 2: Put each report builder behind the shared job

**Files:**
- Modify: `app/routers/wb_reports_bff.py`
- Modify: `app/repricer_tasks.py`
- Test: `tests/test_wb_reports_bff.py`

**Interfaces:**
- Consumes `build_report_for_org` and `_report_job_cache_key` from Task 1.
- Produces cache payloads for `rnp`, `ads`, `pnl`, `stock` using their current response mappers.

- [ ] Write failing tests for each report id to prove the task saves its exact response and a failed task retains the last ready response.
- [ ] Run `pytest -q tests/test_wb_reports_bff.py -k "report_job and (rnp or ads or pnl or stock)"` and verify red.
- [ ] Move each current synchronous builder invocation into the task dispatch path, preserving financial permission and groupBy inputs.
- [ ] Run focused backend tests and the existing `tests/test_sprint_d_reports.py` / `tests/test_rnp_runtime.py` selections.

### Task 3: Replace secondary-report legacy DOM completely

**Files:**
- Modify: `frontend/src/features/vella-parity/VellaHtmlParityPage.tsx`
- Modify: `frontend/src/features/vella-static/vella-source.test.ts`

**Interfaces:**
- Each island renders its own loading, stale-ready, empty and error table state.
- `renderSecondaryReports` cannot mutate `#tab-rnp`, `#tab-ads`, `#tab-pnl` or `#tab-stock`.

- [ ] Write failing source tests asserting no secondary legacy bridge is installed for these roots and no fallback row rendering is reachable.
- [ ] Run `npm test -- --run src/features/vella-static/vella-source.test.ts -t "secondary"` and verify red.
- [ ] Remove the legacy secondary-row bridge for the four reports and make each full root replacement authoritative.
- [ ] Run the focused frontend test and TypeScript typecheck.

### Task 4: Connect UI to jobs and polling

**Files:**
- Modify: `frontend/src/features/vella-parity/VellaHtmlParityPage.tsx`
- Modify: `frontend/src/features/vella-static/vella-source.test.ts`

**Interfaces:**
- POST job then polls GET status until `completed` or `failed`.
- Ready stale payload remains visible during refresh; failure offers retry.

- [ ] Write failing tests for job creation/polling paths and explicit error-only table state.
- [ ] Run the focused test and verify red.
- [ ] Implement a shared React report-job hook used by RNP, Ads, P&L and Stock.
- [ ] Run focused tests, `npx tsc -b --noEmit`, backend focused tests and `git diff --check`.
