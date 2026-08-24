# P&L / 1C Job Lifecycle Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create shared 1C cash-flow jobs immediately and complete P&L only after 1C returns operating expenses.

**Architecture:** Persist 1C jobs in a Postgres table with JSON fallback for database-less tests. The API creates the cash-flow row before Celery dispatch; the task uses Celery retries while the row is pending, and the frontend renders `waiting_1c` as an active state.

**Tech Stack:** FastAPI, SQLAlchemy 2, Alembic, PostgreSQL, Celery, React, TypeScript, Pytest, Vitest.

## Global Constraints

- Preserve existing 1C endpoint payloads.
- Do not block a Celery worker while waiting.
- Do not run browser/headless tests.
- Keep JSON only as a local/test fallback, not production coordination.

---

### Task 1: Shared cash-flow persistence

**Files:**
- Create: `app/cash_flow/orm.py`
- Create: `app/cash_flow/store.py`
- Create: `alembic/versions/20260713_0014_one_c_cash_flow_jobs.py`
- Modify: `alembic/env.py`
- Modify: `app/routers/one_c_cash_flow.py`
- Test: `tests/test_one_c_cash_flow.py`

- [x] Add a database round-trip test using the store boundary.
- [x] Implement indexed, idempotent Postgres persistence and atomic claiming.
- [x] Preserve explicit JSON fallback and verify existing tests.

### Task 2: Immediate P&L request and waiting lifecycle

**Files:**
- Modify: `app/routers/wb_reports_bff.py`
- Modify: `app/repricer_tasks.py`
- Test: `tests/test_wb_reports_bff.py`
- Test: `tests/test_repricer_tasks.py`

- [x] Add a failing test that P&L job start exposes a 1C job immediately.
- [x] Add a failing task test that pending cash-flow produces `waiting_1c` without building P&L.
- [x] Create cash-flow before dispatch and retry the Celery task until cash-flow is ready.
- [x] Verify focused backend tests.

### Task 3: Frontend waiting state

**Files:**
- Modify: `D:/ogni-frontend/frontend/src/features/vella-parity/pnlReportJob.ts`
- Modify: `D:/ogni-frontend/frontend/src/features/vella-parity/pnlReportJob.test.ts`

- [x] Add a failing Vitest case for `waiting_1c`.
- [x] Render it as a non-terminal active state with an explicit 1C label.
- [x] Verify Vitest and TypeScript without headless tests.

### Task 4: Final verification

- [x] Run focused backend and frontend tests.
- [x] Run backend compile/import checks, Alembic head check, and frontend TypeScript.
- [x] Inspect both repository diffs and commit scoped changes to `main`.
