# WB Sync Detailed Progress Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restore 100-SKU 41-SPP batches and provide live detailed progress for all eight WB sync sources.

**Architecture:** Extend the existing cached sync step dictionaries with additive progress metadata. Emit heartbeats from the goods/SPP loop and render the same metadata in an expandable frontend panel.

**Tech Stack:** Python, FastAPI, pytest, React, TypeScript, Vite.

## Global Constraints

- Never persist WB or SPP tokens or full nmID lists in sync status.
- External 41-SPP requests contain at most 100 unique nmIDs.
- Active long-running work refreshes `updatedAt` within each goods page.
- Existing sync clients remain compatible because all new fields are optional.

---

### Task 1: External SPP batch and callback contract

**Files:**
- Modify: `tests/test_wb_repricer_bff.py`
- Modify: `app/repricer_sync.py`

**Interfaces:**
- Produces: `fetch_external_spp_prices(..., progress_callback: Callable[[dict[str, Any]], None] | None = None)`

- [ ] Write a failing test asserting 201 IDs create request sizes 100, 100, and 1 and callback completion reaches 201.
- [ ] Run the focused pytest and confirm failure against the current 50-item behavior.
- [ ] Change the batch constant to 100 and invoke the callback after each completed batch.
- [ ] Run the focused pytest and confirm it passes.

### Task 2: Sync step progress and heartbeat

**Files:**
- Modify: `tests/test_wb_repricer_bff.py`
- Modify: `app/repricer_sync.py`

**Interfaces:**
- Produces additive step fields: `progressPercent`, `progressCurrent`, `progressTotal`, `phase`, `message`, `request`.

- [ ] Write failing tests for goods heartbeat updates and source start/completion progress.
- [ ] Run focused tests and confirm the missing metadata failures.
- [ ] Add a progress update helper and wire SPP callbacks plus all source transitions into it.
- [ ] Run focused repricer tests and confirm they pass.

### Task 3: Expandable frontend details

**Files:**
- Modify: `D:/ogni-frontend/frontend/src/features/wb-repricer/liveParityData.ts`
- Modify: `D:/ogni-frontend/frontend/src/features/vella-parity/VellaHtmlParityPage.tsx`
- Modify: the stylesheet owning `products-sync-*` rules found during implementation.

**Interfaces:**
- Consumes optional backend step progress fields from Task 2.
- Produces an expandable localized per-source progress panel.

- [ ] Extend TypeScript sync-step types with optional progress metadata.
- [ ] Render all requested sources in backend order, including pending sources absent from `steps`.
- [ ] Add accessible expand/collapse control, per-source progress bars, messages, safe request labels, and errors.
- [ ] Run frontend type-checking and focused tests.

### Task 4: Regression verification

**Files:**
- Verify only.

- [ ] Run backend repricer sync/BFF tests.
- [ ] Run frontend type-checking and relevant tests.
- [ ] Inspect diffs for unrelated changes and secret exposure.
