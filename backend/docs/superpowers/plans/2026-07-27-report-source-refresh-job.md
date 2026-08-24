# Report Source Refresh Job Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a per-report background refresh that loads only the WB sources needed for the selected report/date range, rebuilds the exact report snapshot, and shows progress in the React reports UI.

**Architecture:** Reuse `refresh_wb_data_sources(...)` for targeted source loading and reuse `build_report_for_org` for snapshot construction. Add a new Celery task that writes progress into the existing `reports_job_*` cache key, then expose it through a new BFF endpoint and existing job polling.

**Tech Stack:** FastAPI routers, Celery tasks, Postgres-backed `wb_repricer_source_cache`, React/TypeScript reports page.

## Global Constraints

- Do not run full cold onboarding sync from the report button.
- Keep stale report rows visible during refresh.
- Use source sets already required by report snapshots.
- Baskets refresh must request daily detail when the report depends on baskets.
- Keep changes scoped to WB reports BFF/tasks/frontend reports page.

---

### Task 1: Backend Job Contract

**Files:**
- Modify: `app/repricer_tasks.py`
- Modify: `app/routers/wb_reports_bff.py`
- Test: `tests/test_repricer_tasks.py`
- Test: `tests/test_wb_reports_bff.py`

**Interfaces:**
- Produces: `refresh_report_sources_for_org(self, organization_id, user_id, report_id, date_from_iso, date_to_iso, group_by, source, finance_allowed, wb_token) -> dict[str, Any]`
- Produces: `POST /api/wb/reports/{report_id}/refresh-sources-job`
- Consumes: `refresh_wb_data_sources(...)`, `build_report_for_org.run(...)`, existing `_report_job_cache_key(...)`

- [ ] Write failing tests for report-to-source mapping and job progress.
- [ ] Implement helper mapping report IDs to source lists and baskets daily detail flag.
- [ ] Implement Celery task that writes `queued`, `refreshing_sources`, `building_report`, `completed` or `failed`.
- [ ] Implement endpoint that queues the new task and reuses current job key.
- [ ] Verify targeted backend tests pass.

### Task 2: Frontend Button And Progress

**Files:**
- Modify: `frontend/src/features/wb-reports/api.ts`
- Modify: `frontend/src/features/wb-reports/WbReportsPage.tsx`

**Interfaces:**
- Consumes: `POST /api/wb/reports/{report_id}/refresh-sources-job`
- Produces: `refreshReportSourcesJob(reportId, dateRange, groupBy?)`
- Extends: `ReportJobState` with `refreshing_sources`, `building_report`

- [ ] Add API client function.
- [ ] Add button near Export for non-digest report pages and digest if supported.
- [ ] Show compact progress bar and stage label while job state is active.
- [ ] Keep old report data visible while refresh runs.
- [ ] Reload report after `completed`.
- [ ] Verify TypeScript passes.

### Task 3: Verification

**Files:**
- Test commands only.

- [ ] Run targeted backend tests for new refresh job and existing daily readiness.
- [ ] Run `python -m py_compile` for touched backend modules.
- [ ] Run frontend `npm run typecheck`.
- [ ] Report any known generated-file side effects.
