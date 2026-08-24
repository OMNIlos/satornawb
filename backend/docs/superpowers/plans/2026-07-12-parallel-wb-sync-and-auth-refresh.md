# Parallel WB Sync and Auth Refresh Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add four-way WB source concurrency and reliable production session renewal.

**Architecture:** A locked sync coordinator schedules independent and goods-dependent source workers. Auth uses production-safe cross-site cookies, terminal client cleanup, and bounded refresh rotation grace.

**Tech Stack:** Python, FastAPI, SQLAlchemy, pytest, React, TypeScript, Vitest.

## Global Constraints

- Never run more than four WB source workers.
- Finance and baskets wait for goods when goods is requested.
- One source failure must not cancel unrelated sources.
- Refresh cookies remain HttpOnly and are never exposed to JavaScript.
- Terminal refresh failure clears only application authentication state.

### Task 1: Parallel sync coordinator

**Files:** `app/repricer_sync.py`, `tests/test_wb_repricer_bff.py`

- [ ] Add failing overlap, max-four, dependency, ordering, and partial-result tests.
- [ ] Implement locked status snapshots and the two-phase executor schedule.
- [ ] Run focused sync tests.

### Task 2: Auth refresh recovery

**Files:** `app/config.py`, `app/routers/auth.py`, `app/cabinet/orm.py`, `app/cabinet/store.py`, `app/control_plane/auth.py`, auth migrations/tests, `D:/ogni-frontend/frontend/src/lib/api.ts`, `api.test.ts`.

- [ ] Add failing production-cookie, rotation-grace, and terminal-client-cleanup tests.
- [ ] Implement production cookie policy and bounded previous-token grace.
- [ ] Clear frontend auth after terminal refresh 401.
- [ ] Run focused auth tests and TypeScript checks.

### Task 3: Integration verification

- [ ] Review both diffs for shared-state conflicts and secrets.
- [ ] Run focused backend suites, frontend tests, and typecheck.
