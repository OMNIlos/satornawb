# Satorna Dated Economics Implementation Plan

> **Execution:** use `superpowers:executing-plans` and
> `superpowers:test-driven-development`; keep each task independently revertible.

**Goal:** Make `taxPct`, `otherExpensePricePct` and
`otherExpensePerSaleKopecks` append-only, dated canonical inputs and expose their
reconciled subtotal in the canonical ABC/P&L report without claiming final net
profit.

**Architecture:** PostgreSQL owns organization defaults and optional SKU
overrides. A policy is resolved at the end of each Moscow business day as SKU
override → organization default. Finance supplies immutable daily revenue and
gross-sale bases; economics supplies integer basis points and kopecks. Missing
coverage stays `null`; observed legacy snapshots remain `assumed`. Advertising
and loyalty keep `netProfitKopecks`, profit class and final ABC code blocked.

**Production evidence:** immutable backups prove organization `2` economics at
`2026-08-19T12:37:54Z` and `2026-08-28T11:17:46Z`. All `3,054` economics-bearing
SKU overrides existed in both snapshots. `3,053` were unchanged; only
`Фсbt_3107` changed tax from `6%` to `7.5%`. The organization default changed
from `6% / 5% / 0` to `7.5% / 0% / 0`. Current values match the 28/29 August
snapshot hash. No earlier evidence is claimed.

## Constraints

- Preserve `var/vella_repricer_runtime_state.json`; do not stage or deploy it.
- Do not use GitHub.
- Store percentages as integer basis points and money as integer kopecks.
- Keep HTTP report reads cache-only and WB-free.
- Use inclusive Moscow `Period`; evaluate policy at Moscow day end.
- Keep legacy formula semantics: gross sales units for per-sale overhead and
  signed seller revenue for percentage overhead/tax. Round percentage amounts
  exactly like Python integer `round` (half-even), once per unchanged policy
  bucket so a constant policy preserves period-level legacy rounding.
- Never backdate current settings beyond immutable evidence. Missing daily or
  identity coverage returns `null` and a blocker.
- No advertising, loyalty, frontend cutover or final profit classification in
  this slice.

## Task 1: Append-only economics ledger (`0055`)

**Files:** `app/platform/economics/orm.py`,
`app/platform/economics/policies.py`,
`alembic/versions/20260902_0055_dated_economics.py`,
`ops/runtime-db-role.sql`, migration/runtime-role tests, and
`tests/test_economics_policies.py`.

- [x] Write RED tests for two forced-RLS tables,
  `organization_economics_versions` and
  `catalog_economics_override_versions`, following `0054`.
- [x] Add tenant/composite foreign keys, append-only source identities,
  supersession links, range checks and resolve indexes.
- [x] Implement idempotent organization/override writes, point-only resolution,
  partial override fallback, explicit `configured|assumed|missing`, evidence
  propagation and a tenant-scoped monotonic revision.
- [x] Verify dated changes, clears, missing defaults, cross-tenant isolation and
  source-reference conflicts; commit the task alone.

## Task 2: Expose daily economics bases from canonical finance

**Files:** `app/platform/finance/service.py` and
`tests/test_finance_pnl_rollup.py`.

- [x] Add a failing exact/custom test for daily signed revenue and gross sales
  units sourced from the already-deployed `0054` daily rollup.
- [x] Add the smallest read-only `FinancePnlDailyBasis` projection; do not add a
  table or rematerialize finance.
- [x] Keep existing daily COGS units and snapshot semantics unchanged; commit.

## Task 3: Integrate economics into canonical ABC/P&L

**Files:** `app/modules/wb_reports/abc_pnl.py`,
`app/modules/wb_reports/schemas.py`, `app/routers/wb_reports_v2.py`,
`tests/test_abc_pnl_service.py`, and `tests/test_abc_pnl_v2.py`.

- [x] Write RED tests with literal tax/overhead amounts, a mid-period policy
  change, half-even rounding, missing identity/daily/policy coverage, assumed
  evidence and pagination-independent summaries.
- [x] Add `taxKopecks`, `otherExpensesKopecks`,
  `profitBeforeAdsAndLoyaltyKopecks`, economics state/evidence and
  `economicsRevision`; advance formula version to
  `wb-abc-pnl-economics-v1`.
- [x] Remove only `WB_PNL_ECONOMICS_NOT_CANONICAL`. Keep ads/loyalty global
  blockers and all final profit/classification fields `null`.
- [x] Run focused route/service/finance tests; commit.

## Task 4: Preserve future settings changes and backfill proven evidence

**Files:** `app/platform/economics/policies.py`,
`app/routers/wb_repricer_bff.py`, and focused repricer/economics tests.

- [x] Reconcile only economics-bearing legacy PUT/import changes into canonical
  versions after the legacy write succeeds. A retry must repair a partial
  dual-write; unrelated repricer flushes must do no canonical work.
- [x] Backfill organization `2` from the two immutable backup observations as
  `assumed` dated snapshots. Record unmapped articles; do not invent dates.
- [x] Prove zero-tolerance calculation parity against those observations for
  exact 7d, 30d and a custom period; incomplete pre-evidence periods stay null.

## Task 5: Verify and deploy

- [x] Run focused tests, `compileall`, `git diff --check`, then the full suite;
  accept no failure outside the exact `105` baseline.
- [x] Rehearse `0054→0055→0054→0055` locally and on a disposable production
  schema clone; prove runtime grants, forced RLS and app startup.
- [x] Create and verify a scoped production backup; preserve immutable rollback
  image tags.
- [x] Deploy one digest to migrate/API/worker/beat, backfill through
  `satorna_runtime`, require health/pong/zero restarts and authenticated p95
  `≤500 ms` over 25 requests for each period.
- [x] Update `SATORNA_ARCHITECTURE_HANDOFF.md`; keep frontend unchanged.

## Completion evidence — 2026-09-03

- Production runs migration `20260902_0055` and application revision `259977f`
  on one image digest
  `sha256:1daef9da8d491f3483de5b23ff58268dff19ecec6fd0245b1db717fca18e57df`.
  API, worker and beat have zero restarts; liveness/readiness pass externally and
  Celery returns `pong` with empty active, reserved and scheduled queues.
- Backup `/var/backups/satorna-dated-economics-pre-0055-20260902T185811Z`
  and rollback tag
  `ogni-elfs-{api,worker,beat,migrate}:rollback-6959fc0-pre-259977f` are retained.
  The production-schema `0054→0055→0054→0055` rehearsal passed.
- Runtime role `satorna_runtime` has no superuser, create DB/role, replication or
  `BYPASSRLS` attributes. Both economics tables have RLS and FORCE RLS. No
  tenant, organization `1` and organization `3` see `0/0` rows; organization
  `2` sees `2/3052`, revision `3054`.
- Immutable parity evidence has zero monetary delta for every calculable row:
  7d `849/848` calculable with one source row lacking `business_date`; 30d
  `1229/518` calculable with `711` intentionally missing historical coverage;
  custom `2026-08-20…2026-08-26` `926/926`, tax `42,077,260` kopecks and other
  expenses `35,064,382` kopecks. Incomplete summaries remain `null`.
- Authenticated live p50/p95 over 25 requests are `152.55/343.83 ms` (7d),
  `394.28/445.30 ms` (30d) and `151.70/332.04 ms` (custom). All pass the
  `500 ms` p95 gate without an application cache. Runs overlapping legacy
  repricer pagination or the five-minute Celery burst were rejected as
  contaminated measurements rather than reported as release evidence.
- Final backend suite is `476 passed / 105 failed` in `264.25 s`; the failure
  identifiers exactly match the captured legacy baseline (`added=[]`,
  `missing=[]`, `errors=[]`). Contract suite is `20 passed`; compile, touched
  Ruff checks and `git diff --check` pass. The frontend was not changed.
