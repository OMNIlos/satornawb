# WB Sync Windowed Architecture Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move cold WB fetching into staged and periodic sync profiles while preserving existing report/repricer APIs and formulas.

**Architecture:** Add a small backend sync planner that defines onboarding, periodic, and nightly windows. Wire the planner into existing Celery/manual sync as metadata first, and make ordinary baskets sync aggregate-only while keeping daily detail available through the existing background endpoint.

**Tech Stack:** Python, FastAPI, Celery, pytest, React, TypeScript.

## Global Constraints

- Do not remove or rename existing report/repricer endpoints.
- Do not change repricer/report formulas in this phase.
- Default user-triggered sync must not fetch daily Sales Funnel detail.
- Daily baskets detail must remain available via the existing background detail job.
- Any WB API fetching added by this work must happen through sync jobs, not read endpoints.

### Task 1: Sync Profile Planner

**Files:**
- Create: `app/wb_sync_plan.py`
- Test: `tests/test_wb_sync_plan.py`

- [x] Add tests for onboarding, periodic, nightly, and estimate profiles.
- [x] Implement immutable sync profile dataclasses and helper functions.
- [x] Run `pytest tests/test_wb_sync_plan.py -q`.

### Task 2: Aggregate-Only Default Baskets Sync

**Files:**
- Modify: `app/repricer_sync.py`
- Test: `tests/test_wb_repricer_bff.py`

- [x] Update the existing baskets sync test to expect deferred daily detail by default.
- [x] Add an opt-in test proving daily detail still runs when explicitly requested.
- [x] Add `baskets_include_daily_detail` and profile metadata to `refresh_wb_data_sources`.
- [x] Run targeted sync tests.

### Task 3: Scheduler Uses Short Windows

**Files:**
- Modify: `app/repricer_tasks.py`
- Test: `tests/test_repricer_tasks.py`

- [x] Add scheduler test proving regular runs use the hourly operational profile and a 2-day window.
- [x] Implement profile selection for scheduled sync while preserving manual full sync behavior.
- [x] Run targeted scheduler tests.

### Task 4: Manual Sync Status Metadata

**Files:**
- Modify: `app/routers/wb_repricer_bff.py`
- Test: `tests/test_wb_repricer_bff.py`

- [x] Add test for `/sync/run` returning profile/window metadata.
- [x] Pass planner metadata through `begin_wb_sync` and background task.
- [x] Run targeted endpoint tests.

### Task 5: Frontend Status Surfacing

**Files:**
- Modify: `D:/ogni-frontend/frontend/src/features/wb-repricer/liveParityData.ts`
- Modify: `D:/ogni-frontend/frontend/src/features/vella-parity/VellaHtmlParityPage.tsx`
- Test: existing frontend tests if available.

- [x] Extend sync status TypeScript shape with optional profile/window fields.
- [x] Show profile/window text in existing sync status UI without changing report API calls.
- [x] Run focused Vitest/typecheck.

### Task 6: Onboarding And Nightly Workers

**Files:**
- Modify: `app/repricer_tasks.py`
- Modify: `app/routers/cabinet.py`
- Modify: `app/infra/celery_app.py`
- Test: `tests/test_repricer_tasks.py`, `tests/test_cabinet_system.py`, `tests/test_infra_baseline.py`

- [x] Add onboarding task that runs `onboarding-7d`, `onboarding-30d`, then `backfill-180d`.
- [x] Enqueue onboarding after WB token save in real sync mode without calling WB API inside the HTTP request.
- [x] Add nightly reconciliation task and all-org dispatcher.
- [x] Add nightly dispatcher to Celery beat.

### Task 7: Background Report Pre-Sync

**Files:**
- Modify: `app/repricer_tasks.py`
- Test: `tests/test_repricer_tasks.py`, `tests/test_stock_report_cache_persistence.py`

- [x] Add exact-range report sync helper through `refresh_wb_data_sources`.
- [x] Pre-sync stock report sources before stock background payload build.
- [x] Pre-sync ads report sources before ads background payload build.
- [x] Pre-sync RNP funnel sources before RNP background payload build.
- [x] Pre-sync digest sources before digest background build.
- [x] Add a cache-only `WbReportsSourcesSnapshot` adapter and use it in stock/digest background jobs.
- [ ] Fully replace remaining report runtime snapshot builders with cache-only adapters.

### Task 8: Sync Plan Visibility

**Files:**
- Modify: `app/routers/wb_repricer_bff.py`
- Modify: `D:/ogni-frontend/frontend/src/features/wb-repricer/liveParityData.ts`
- Modify: `D:/ogni-frontend/frontend/src/features/vella-parity/VellaHtmlParityPage.tsx`

- [x] Extend `/api/v1/wb-repricer/sync/status` with `syncPlan` entries for onboarding, periodic, and nightly profiles.
- [x] Show running profile, next run, cadence, source list, and estimate in the repricer sync panel.
- [x] Keep current per-source progress bars for the active run.
