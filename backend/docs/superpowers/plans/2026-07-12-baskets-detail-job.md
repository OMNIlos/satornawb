# Baskets Detail Job Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make regular basket sync fast and load daily detail as an observable background job for the selected date range.

**Architecture:** Aggregate basket fetch and daily basket fetch are separate services. A persisted per-organization detail status drives frontend polling and a range-specific cache stores completed daily rows.

**Tech Stack:** Python, FastAPI BackgroundTasks, pytest, React, TypeScript, Vitest.

## Global Constraints

- Regular WB sync must never request daily basket detail.
- Detail progress updates before and after each WB request.
- Detail failure must preserve aggregate basket cache.
- Status and cache are organization-scoped and range-specific.
- Frontend must stop following stale run IDs after a range change.

### Task 1: Backend aggregate heartbeat and detail job

**Files:** `app/repricer_bff.py`, `app/repricer_sync.py`, `app/routers/wb_repricer_bff.py`, `tests/test_wb_repricer_bff.py`.

- [ ] Add failing tests proving regular sync passes `include_daily=False`, aggregate heartbeat advances by SKU batch, detail request totals equal days multiplied by SKU batches, and completed detail merges into the exact range cache.
- [ ] Implement optional basket progress callbacks and a detail-only daily fetch path.
- [ ] Add start/status endpoints backed by organization-scoped source-cache status.
- [ ] Run focused backend tests.

### Task 2: Frontend range-triggered detail loader

**Files:** `D:/ogni-frontend/frontend/src/features/wb-repricer/liveParityData.ts`, `D:/ogni-frontend/frontend/src/features/vella-parity/VellaHtmlParityPage.tsx`, relevant tests.

- [ ] Add typed start/status API helpers.
- [ ] Start detail after the applied products-period event, poll the returned run ID, and ignore stale-range responses.
- [ ] Render request/day/batch progress and reload live products/reports on completion.
- [ ] Run Vitest and TypeScript checks.

### Task 3: Integration verification

- [ ] Review cache merging, run isolation, and absence of token/nmID leakage in status.
- [ ] Run backend focused tests, frontend tests, compile, and typecheck.
