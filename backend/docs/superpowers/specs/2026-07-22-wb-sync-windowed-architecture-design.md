# WB Sync Windowed Architecture Design

## Goals

Move cold WB data loading out of report and repricer reads. Existing report and repricer endpoints keep their public contracts and formulas, but they read from local WB source caches. WB API fetching happens in explicit sync jobs: staged onboarding, short periodic refreshes, and nightly reconciliation.

## Architecture

Add a sync planner that describes profiles instead of letting every caller choose an ad hoc full period. Profiles define source list, period window, cadence, and whether expensive daily detail is allowed.

Initial onboarding runs in stages:

- `onboarding-7d`: current products, stock snapshot, period stats, finance, ads, and Sales Funnel aggregates for the last 7 days.
- `onboarding-30d`: same analytical sources for the last 30 days.
- `backfill-180d`: historical analytical sources in background; daily Sales Funnel detail remains separate.

Steady-state refreshes are short:

- hourly operational sync: orders/sales for the last 2 days.
- Sales Funnel sync every 2 hours: today and yesterday as aggregates.
- stock and ads sync every 3 hours: stock snapshot plus ads for the last 3 days.
- finance sync every 6 hours: last 7 days.
- nightly reconciliation: last 30 days, still cache-first for reads and allowed to run long outside user interaction.

Daily baskets detail is no longer part of ordinary WB sync. It uses the existing `/api/v1/wb-repricer/baskets/detail/start` background job or a future nightly detail profile.

WB token save does not validate by calling WB synchronously. In real WB mode it enqueues the onboarding worker, which performs staged sync in the background.

Nightly reconciliation is dispatched through Celery beat via a lightweight all-org task. The per-org nightly task checks the last `nightly-30d-reconcile` history event and skips if the daily cadence is not due.

Background report workers pre-sync their exact requested ranges before building stock, ads, RNP, and digest payloads. Stock and digest background jobs now build their shared reports snapshot from `stocks`, `period_stats_*`, and `finance_*` caches instead of calling the live WB runtime snapshot builder. A later phase should replace the remaining live builders used by ads/RNP/ABC/WoW/export/alerts paths with cache-only adapters.

## Compatibility

The existing `refresh_wb_data_sources` API remains callable with the same arguments. It gains optional profile metadata and a safe default: `baskets` sync stores period aggregates first and marks daily detail as deferred unless explicitly requested.

Report jobs and repricer pages continue to call existing cache readers and formula builders. When a requested exact range is not cached, jobs may queue a sync profile, but HTTP reads must not directly fetch WB heavy sources.

## Observability

Sync status exposes `syncProfile`, `windowKind`, `estimatedSeconds`, `estimatedRequests`, and per-step duration fields. The frontend can show onboarding/backfill progress without changing report payload shapes.

The repricer page reads the same sync status endpoint and renders a sync plan with onboarding, periodic, and nightly profiles. Each profile exposes current state, cadence, last run, next run, requested sources, and estimates, while the active run keeps the existing per-source progress bars.

## Verification

Tests cover planner windows and duration estimates, default baskets sync avoiding daily detail, opt-in baskets detail for deep jobs, and scheduler/manual sync passing profile metadata without changing legacy endpoint responses.
