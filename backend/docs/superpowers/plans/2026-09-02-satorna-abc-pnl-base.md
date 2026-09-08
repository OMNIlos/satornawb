# Satorna Canonical ABC/P&L Base Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expose one tenant/account/period-scoped, cache-only `/api/v2` ABC/P&L base that reconciles immutable WB finance settlement components with dated canonical SKU costs without treating unavailable inputs as zero.

**Architecture:** A new rollback-compatible per-snapshot P&L rollup stores the finance components that the existing revenue rollup intentionally omitted. `FinanceService` owns snapshot selection and immutable fact aggregation; `WbAbcPnlService` joins those facts to canonical catalog mappings and cost versions by Moscow business day. Full net profit and the second ABC letter stay `null` with explicit blockers until advertising, versioned economics and loyalty facts become canonical.

**Tech Stack:** Python 3.14, FastAPI, Pydantic v2, SQLAlchemy 2, Alembic, PostgreSQL 16, pytest.

**Spec:** `../../../../frontend-wb-abc-production/docs/superpowers/specs/2026-08-26-satorna-platform-rebuild-architecture-design.md`, especially §§1, 2, 3.3–3.5, 4.1, 5, 6.2, 7 and 11; continuation checkpoint: `/Users/ilagulakin/Desktop/Work/OgniWB/SATORNA_ARCHITECTURE_HANDOFF.md`.

## Global Constraints

- Preserve the dirty `var/vella_repricer_runtime_state.json`; stage no unrelated file or hunk.
- Do not use GitHub. Deploy only the reviewed local immutable artifact through the dedicated `satorna-api` SSH alias.
- HTTP reads never call WB, mutate a snapshot, or use legacy repricer/report caches.
- Money remains signed integer kopecks; missing, assumed and configured costs remain distinct.
- All tenant tables use `organization_id`, account-scoped rows also use `marketplace_account_id`, and PostgreSQL `ENABLE + FORCE RLS` is mandatory.
- User periods are inclusive Moscow dates resolved once through `Period`; timestamps stay UTC.
- Summary values are sums of the same complete row set returned by the projection before pagination.
- The historic missing `120,800`-kopeck correction is never synthesized.
- Funnel, ads, stocks, prices, KTR, versioned taxes/other expenses, loyalty ingestion and frontend switching are outside this bounded slice.
- The pre-existing empty-chain failure at migration `20260717_0019` and the captured `105` legacy test failures are reported, not attributed to this slice.

---

### Task 1: Add a rollback-compatible immutable P&L rollup

**Files:**

- Modify: `app/platform/finance/orm.py`
- Modify: `app/platform/finance/service.py`
- Create: `alembic/versions/20260902_0053_finance_pnl_rollups.py`
- Modify: `ops/runtime-db-role.sql`
- Modify: `tests/test_finance_migration.py`
- Modify: `tests/test_runtime_database_role.py`
- Create: `tests/test_finance_pnl_rollup.py`

**Interfaces:**

- Produces `WbFinanceSyncRunSkuPnlRollupRow` and `WbFinanceSyncRunRow.is_pnl_rollup_materialized`.
- Produces `FinancePnlFact` and `FinancePnlSource` dataclasses.
- Produces `FinanceService.get_pnl_source(marketplace_account_id: int, period: Period) -> FinancePnlSource`.
- Produces `FinanceService.backfill_pnl_rollups(marketplace_account_id: int) -> int`.

- [x] **Step 1: Write the failing migration and ORM tests**

  Assert revision `20260902_0053` follows `20260902_0052`, creates `wb_finance_sync_run_sku_pnl_rollups`, adds `is_pnl_rollup_materialized`, enables and forces RLS, and includes the table in the runtime-role security check. Assert the table primary key is `(organization_id, marketplace_account_id, sync_run_id, nm_id)` and its run foreign key contains all three ownership columns.

- [x] **Step 2: Run the migration tests and verify RED**

  Run:

  ```bash
  .venv/bin/python -m pytest -q tests/test_finance_migration.py tests/test_runtime_database_role.py
  ```

  Expected: failure because migration `0053`, the ORM table and runtime-role entry do not exist.

- [x] **Step 3: Add the minimal schema**

  Store only immutable finance facts needed by P&L:

  ```text
  operation_count
  revenue_kopecks
  sales_revenue_kopecks
  returns_revenue_kopecks
  main_revenue_kopecks
  redemptions_revenue_kopecks
  late_correction_revenue_kopecks
  unknown_revenue_kopecks
  sales_units / returns_units / net_units
  commission_kopecks / logistics_kopecks / storage_kopecks
  acceptance_kopecks / penalty_kopecks / deduction_kopecks
  additional_payment_kopecks / acquiring_kopecks
  ```

  Keep the new readiness flag defaulted to `false`. Old release `73fa984` must be able to run against schema `0053`; it ignores the new table and cannot publish a false-ready P&L projection.

- [x] **Step 4: Run the migration tests and verify GREEN**

  Run the Step 2 command. Expected: pass.

- [x] **Step 5: Write failing rollup behavior tests**

  Use real SQLite tables and raw WB-shaped operations. Hand-check these expectations:

  ```text
  sale revenue 100000, return revenue 20000 => net revenue 80000
  sale units 2, return units 1 => net units 1
  signed commission 10000 - 2000 => 8000
  signed acquiring 1500 - 300 => 1200
  paymentSchedule 2500 - additionalPayment 10000 => -7500
  ```

  Assert exact-period reads use the new materialized table, custom sub-periods aggregate immutable operations, an unattributed fact is retained as `nm_id=None`, retry is idempotent, and a rollup failure leaves the previous published projection visible.

- [x] **Step 6: Run the rollup test and verify RED**

  Run:

  ```bash
  .venv/bin/python -m pytest -q tests/test_finance_pnl_rollup.py
  ```

  Expected: import or attribute failure for the missing P&L source API.

- [x] **Step 7: Implement the minimal P&L source**

  Reuse the existing snapshot resolver and effective-membership query. Materialize the new rollup in the same transaction that publishes a new snapshot; for an already published snapshot, publish only the new P&L table and readiness flag atomically. `backfill_pnl_rollups` commits each snapshot separately so one failure cannot hide completed projections.

- [x] **Step 8: Run focused finance tests and verify GREEN**

  Run:

  ```bash
  .venv/bin/python -m pytest -q tests/test_finance_pnl_rollup.py tests/test_finance_service.py tests/test_finance_v2.py tests/test_finance_migration.py tests/test_runtime_database_role.py
  ```

  Expected: all pass.

- [x] **Step 9: Commit Task 1 only**

  ```bash
  git add app/platform/finance/orm.py app/platform/finance/service.py alembic/versions/20260902_0053_finance_pnl_rollups.py ops/runtime-db-role.sql tests/test_finance_migration.py tests/test_runtime_database_role.py tests/test_finance_pnl_rollup.py
  git commit -m "feat: materialize canonical finance pnl rollups"
  ```

### Task 2: Resolve canonical product identity and dated costs in one bounded read

**Files:**

- Modify: `app/platform/catalog/service.py`
- Modify: `app/platform/economics/costs.py`
- Create: `tests/test_abc_pnl_costs.py`

**Interfaces:**

- Produces `CatalogService.resolve_wb_product_skus(marketplace_account_id: int, nm_ids: list[int]) -> tuple[dict[int, int], set[int]]`; the set contains products with multiple distinct mapped SKU identities.
- Produces `CostsService.get_costs_on_dates(catalog_sku_ids: list[int], at: list[datetime]) -> dict[tuple[int, datetime], CostValue]`.
- Produces `CostsService.revision() -> int` as the organization-scoped maximum `cost_version_id`, or `0` for an empty ledger.

- [x] **Step 1: Write failing identity and cost-resolution tests**

  Assert exact account/tenant scoping, one mapped SKU, ambiguous multiple mappings, missing mapping, configured zero, assumed cost, missing cost, a cost change between two Moscow days, and a stable revision literal. Expected values must be explicit integers and states.

- [x] **Step 2: Run the test and verify RED**

  Run:

  ```bash
  .venv/bin/python -m pytest -q tests/test_abc_pnl_costs.py
  ```

  Expected: attribute failures for the three missing service methods.

- [x] **Step 3: Implement one-query cost history resolution**

  Fetch all applicable versions for the requested SKU set through the latest requested instant, ordered by `(catalog_sku_id, effective_from, created_at, cost_version_id)`. Walk the sorted dates in memory and return `CostValue(..., value_state="missing")` when no version is effective. Do not issue one query per SKU or per day.

- [x] **Step 4: Implement strict WB product mapping**

  Join canonical products and offers for the authenticated organization/account. Map an `nmId` only when all non-null offers resolve to exactly one `catalog_sku_id`; mark multiple distinct identities ambiguous and never guess from title or article text.

- [x] **Step 5: Run the focused test and verify GREEN**

  Run the Step 2 command. Expected: pass.

- [x] **Step 6: Commit Task 2 only**

  ```bash
  git add app/platform/catalog/service.py app/platform/economics/costs.py tests/test_abc_pnl_costs.py
  git commit -m "feat: resolve dated costs for wb pnl"
  ```

### Task 3: Build the canonical ABC/P&L base projection

**Files:**

- Create: `app/modules/__init__.py`
- Create: `app/modules/wb_reports/__init__.py`
- Create: `app/modules/wb_reports/abc_pnl.py`
- Create: `tests/test_abc_pnl_service.py`

**Interfaces:**

- Consumes `FinanceService.get_pnl_source`, `CatalogService.resolve_wb_product_skus`, `CostsService.get_costs_on_dates` and `CostsService.revision`.
- Produces `WbAbcPnlService.get_page(marketplace_account_id: int, period: Period, limit: int, offset: int) -> AbcPnlPage`.
- Formula version is exactly `wb-abc-pnl-base-v1`.

- [x] **Step 1: Write failing formula and state tests**

  Use a real in-memory database. Freeze the legacy settlement formula with literals:

  ```text
  revenue                                      80000
  dated COGS: 2*20000 - 1*25000              15000
  commission + logistics + storage +
  acceptance + penalty + deduction +
  finance-other + acquiring - compensation   31700
  settlement profit                           33300
  ```

  Assert an assumed cost computes the same amount but adds `WB_PNL_COST_ASSUMED`; missing daily coverage produces `cogsKopecks=null` and `settlementProfitKopecks=null`; ambiguous mapping is never costed; summary settlement profit becomes `null` if any contributing row is incomplete; unattributed finance remains a row; pagination does not change summary; sales letters use the frozen top-20%/next-30%/remaining rank rule.

- [x] **Step 2: Run the service test and verify RED**

  Run:

  ```bash
  .venv/bin/python -m pytest -q tests/test_abc_pnl_service.py
  ```

  Expected: import failure for `app.modules.wb_reports.abc_pnl`.

- [x] **Step 3: Implement the minimal projection**

  Calculate daily COGS from daily net finance units and the cost effective at the end of that Moscow business day. Preserve signed returns. Aggregate finance expenses exactly once:

  ```text
  financeOther = max(0, -additionalPaymentSigned)
  compensation = max(0, additionalPaymentSigned)
               + max(0, -penaltySigned)
               + max(0, -deductionSigned)
  financeExpenses = commission + logistics + storage + acceptance
                  + max(0, penaltySigned) + max(0, deductionSigned)
                  + financeOther + acquiring - compensation
  settlementProfit = revenue - cogs - financeExpenses
  ```

  Return `netProfitKopecks=null`, `profitClass=null` and `abcCode=null`. Add global blockers `WB_PNL_ADS_NOT_CANONICAL`, `WB_PNL_ECONOMICS_NOT_CANONICAL` and `WB_PNL_LOYALTY_NOT_CANONICAL`; this prevents the base from being misrepresented as final P&L.

- [x] **Step 4: Run the service test and verify GREEN**

  Run the Step 2 command. Expected: pass.

- [x] **Step 5: Commit Task 3 only**

  ```bash
  git add app/modules/__init__.py app/modules/wb_reports/__init__.py app/modules/wb_reports/abc_pnl.py tests/test_abc_pnl_service.py
  git commit -m "feat: add canonical abc pnl base projection"
  ```

### Task 4: Expose a typed, cache-only `/api/v2` contract

**Files:**

- Create: `app/platform/finance/access.py`
- Modify: `app/routers/finance_v2.py`
- Create: `app/modules/wb_reports/schemas.py`
- Create: `app/routers/wb_reports_v2.py`
- Modify: `app/main.py`
- Create: `tests/test_abc_pnl_v2.py`

**Interfaces:**

- Produces `GET /api/v2/wb/reports/abc-pnl` with `marketplaceAccountId`, `periodDays`, `dateFrom`, `dateTo`, `limit` and `offset` query parameters.
- Reuses one shared `finance:read` and membership account-scope guard; organization is never accepted from query/body.
- Returns typed rows, full-set summary, pagination, source snapshot, period, formula version, cost-ledger revision, blockers and timestamp.

- [x] **Step 1: Write failing route tests**

  Assert unauthenticated `401`, missing permission `403`, out-of-scope account `403`, cross-tenant account `404`, invalid period `422`, OpenAPI registration, row/summary reconciliation, explicit `partial` state and all three global blockers. Monkeypatch the WB fetch function to raise if called and assert the request still succeeds.

- [x] **Step 2: Run the route test and verify RED**

  Run:

  ```bash
  .venv/bin/python -m pytest -q tests/test_abc_pnl_v2.py
  ```

  Expected: `404` because the route is not registered.

- [x] **Step 3: Extract the existing finance access guard without changing behavior**

  Move the actor dependency, `finance:read` check and canonical membership account-scope check from `finance_v2.py` to `app/platform/finance/access.py`. Re-export/import the same dependency object so existing `dependency_overrides[get_finance_actor]` tests continue to work. Do not create router-to-router calls.

- [x] **Step 4: Implement schemas and route**

  Resolve `Period` once with the same error envelope as `/api/v2/wb/finance`, call `WbAbcPnlService`, and serialize only Pydantic response models. No legacy cache or WB adapter import is allowed in the service or route.

- [x] **Step 5: Run route and existing finance tests and verify GREEN**

  Run:

  ```bash
  .venv/bin/python -m pytest -q tests/test_abc_pnl_v2.py tests/test_finance_v2.py tests/test_period.py
  ```

  Expected: all pass.

- [x] **Step 6: Commit Task 4 only**

  ```bash
  git add app/platform/finance/access.py app/routers/finance_v2.py app/modules/wb_reports/schemas.py app/routers/wb_reports_v2.py app/main.py tests/test_abc_pnl_v2.py
  git commit -m "feat: expose canonical abc pnl api"
  ```

### Task 5: Close the production latency gate with daily materialization

The first authenticated production shadow read on `0053` measured about `481 ms`
for 7 days, `1.4 s` for 30 days and `981 ms` for a custom sub-period. Profiling
isolated repeated operation-membership aggregation as the dominant cost; the
release therefore remains incomplete until the same immutable snapshot publishes
daily P&L components.

**Files:**

- Create: `alembic/versions/20260902_0054_finance_daily_pnl_rollups.py`
- Modify: `app/platform/finance/orm.py`
- Modify: `app/platform/finance/service.py`
- Modify: `app/platform/economics/costs.py`
- Modify: `app/modules/wb_reports/abc_pnl.py`
- Modify: `ops/runtime-db-role.sql`
- Modify: focused finance, migration, cost and runtime-role tests

- [x] Add a failing test for point-only dated-cost resolution.
- [x] Add failing migration, forced-RLS, exact/custom daily-read, atomic-publish
  and resumable-backfill tests.
- [x] Materialize per-snapshot, per-day, per-SKU finance components atomically.
- [x] Aggregate custom periods from daily facts and resolve costs only for actual
  `(catalog_sku_id, Moscow business day)` points.
- [x] Rehearse `0053→0054→0053→0054`, backfill production through
  `satorna_runtime`, repeat zero-tolerance parity and require p95 `≤500 ms`.

### Task 6: Verify, rehearse, canary and deploy

**Files:**

- Modify: `docs/superpowers/plans/2026-09-02-satorna-abc-pnl-base.md`
- Modify: `/Users/ilagulakin/Desktop/Work/OgniWB/SATORNA_ARCHITECTURE_HANDOFF.md`

**Interfaces:**

- Consumes the final tested code and production release `73fa984` / Alembic `0052`.
- Produces migration, RLS, parity, latency, backup, image, deployment and rollback evidence.

- [x] **Step 1: Run focused and static verification**

  ```bash
  .venv/bin/python -m pytest -q tests/test_period.py tests/test_finance_normalization.py tests/test_finance_service.py tests/test_finance_pnl_rollup.py tests/test_finance_v2.py tests/test_finance_migration.py tests/test_runtime_database_role.py tests/test_abc_pnl_costs.py tests/test_abc_pnl_service.py tests/test_abc_pnl_v2.py
  .venv/bin/python -m compileall -q app tests alembic
  git diff --check
  ```

- [x] **Step 2: Run the full backend suite and compare the captured baseline**

  Run `.venv/bin/python -m pytest -q`. Accept no failure outside the exact known `105` baseline set; record counts and duration.

- [x] **Step 3: Rehearse migration and rollback on a disposable production-schema clone**

  Verify `0052 → 0053 → 0052 → 0053`, schema ownership, the new runtime grants and application startup. Do not claim the known broken empty chain passes.

- [x] **Step 4: Back up production before migration**

  Store scoped database dump, schema, globals, runtime compose/config checksums and release/image identifiers under a timestamped `/var/backups/satorna-abc-pnl-pre-0053-*` directory; verify checksums before proceeding.

- [x] **Step 5: Deploy migration and compatible immutable image**

  Tag the current API/worker/beat/migrate image for immediate rollback. Run the one-shot migrate service, deploy the same candidate digest to API/worker/beat/migrate, and require health, Celery pong and zero restarts.

- [x] **Step 6: Backfill and verify organization `2`**

  Through `satorna_runtime`, materialize all published account `2` P&L rollups. Assert published runs equal ready rollups, row totals match canonical finance to zero kopecks, no-context and organization `1` see zero organization `2` rows, and a cross-tenant write fails.

- [x] **Step 7: Run shadow parity and latency gates**

  For exact 7-day and 30-day snapshots plus one custom sub-period, compare every canonical finance component against operation-level aggregation and every dated COGS result against `catalog_cost_versions`. Record expected cost blockers before the first effective version; never substitute a later cost. Benchmark 25 authenticated requests and require p95 `≤ 500 ms`.

- [x] **Step 8: Update handoff and execution record**

  Record commits, migration, image digest, backup, rollback tags, focused/full results, parity, RLS, latency and all still-open blockers. Keep frontend unchanged.

## Self-review record

- Spec coverage: tenant/account scope, Period, cache-only reads, immutable facts, dated costs, null semantics, forced RLS, typed v2 contract, pagination, reconciliation, rollback and production gates are assigned above.
- Deliberate gaps: full `netProfitKopecks`, second ABC letter, funnel/ads/economics/loyalty/KTR and frontend rollout are explicit blockers/non-goals, not silent defaults.
- Type consistency: Task 3 consumes the exact four service interfaces produced by Tasks 1–2; Task 4 serializes only `AbcPnlPage` from Task 3.
- Placeholder scan: no unfinished implementation placeholder is part of the plan.

## Execution record — 2026-09-02

- Commits: `673d10b`, `a0db4b2`, `043fefe`, `0dca857`, `1fcd065`, `1ecf67f`.
- Focused verification: `48 passed`. Full suite: `438 passed / 105 failed`
  in `272.68 s`; the failure set is the exact captured legacy baseline.
- Both migration steps were rehearsed through upgrade, downgrade and re-upgrade
  on local and production-schema clones; runtime ownership, grants and startup
  passed. Production Alembic head is `20260902_0054`.
- Verified backups:
  `/var/backups/satorna-abc-pnl-pre-0053-20260902T170744Z` and
  `/var/backups/satorna-abc-pnl-pre-0054-20260902T172411Z`.
- Production image digest is
  `sha256:29a8e75a1bf9a6c0d8fe7e535f7243852eff5a2250e912e26954fbfd18e63db8`
  with revision `1ecf67f`; API, worker and beat use the same digest and have zero
  restarts. Immediate rollback tags point to the `0053`-compatible image.
- Organization `2`, account `2`: all `3/3` snapshots are P&L- and daily-ready;
  the projections contain `3,008` aggregate rows and `20,891` daily rows. Forced
  RLS returns zero rows without tenant context and for organization `1`, while a
  cross-tenant write is rejected.
- Zero-tolerance finance and dated-cost parity passed for exact 7-day, exact
  30-day and custom `2026-08-10…2026-08-16` periods. The 7-day summary has
  `174,913,000` kopecks COGS; 30-day/custom COGS correctly remain `null` because
  `840/519` rows respectively predate their first cost evidence.
- Authenticated production route benchmark over 25 requests per period:
  p50/p95 `142.7/330.2 ms` (7d), `343.1/400.3 ms` (30d), and
  `95.5/237.8 ms` (custom), all below the `500 ms` p95 gate.
