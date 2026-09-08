# Satorna Canonical Period/Finance Slice

> Execute test-first. Keep legacy UI on its existing contract; this slice is shadow-only until parity gates pass.

**Goal:** Introduce one Moscow-period model and immutable, tenant/account-scoped WB finance snapshots that can be read through `/api/v2` without calling WB.

**Initial production baseline:** release label `b749fe1`, Git `13cba53`, Alembic `20260901_0046`. The exact running application overlay is captured locally by commit `ed80c0f`. No GitHub dependency is used.

**Observed root cause:** numeric preset keys such as `finance_7` return early in `_load_period_source_cache` before the existing covering-range lookup. Production has non-empty `finance_2026-08-26_2026-09-01`, while numeric SKU snapshots for the same range contain zero finance totals.

## Scope

- `app/platform/period.py`: inclusive calendar dates in `Europe/Moscow`, converted once to `[start_at, end_exclusive_at)`.
- `app/platform/finance/`: deterministic WB row normalization, immutable operation versions, immutable snapshot membership, exact signed kopecks, report type and correction timestamps.
- `GET /api/v2/wb/finance`: account-scoped, cache-only rows and summary from the same snapshot.
- Shadow ingestion from both existing background finance fetch paths.
- `VELLA_FINANCE_SHADOW_INGEST_ENABLED=false` rollout guard; the cache-only reader remains usable while periodic writes are disabled.
- Shared legacy covering-cache bug fix.
- Alembic `20260901_0047` with composite tenant/account foreign keys and forced RLS.

Out of scope: frontend switch, ABC/P&L formulas, repricer changes, legacy deletion, a second cache layer, and synthetic reconstruction of missing raw WB evidence.

## Test-first tasks

1. Add failing Period tests for Moscow UTC boundaries, preset/custom equivalence, inclusive end, partial current day, future and validation.
2. Add failing normalizer tests for `reportType 1/2`, sale/return signs, `rrdId` identity, documented fallback fingerprint, exact Decimal-to-kopeck conversion, correction timestamp and snapshot checksum.
3. Add failing persistence tests for retry idempotency, changed payload versions, snapshot membership, tenant/account isolation and exact frozen reconciliation:
   `602842752 + 32694699 + 120800 = 635658251` kopecks.
4. Add failing API tests for permission/account scope, period metadata, explicit `ready|partial|future|empty|missing` states, pagination, row/summary equality and absence of WB calls.
5. Add a failing legacy regression proving a numeric preset reaches a covering date-range cache.
6. Add a failing migration test for tables, composite foreign keys, checks, indexes and forced RLS.
7. Implement only enough production code to make those tests pass; reuse existing auth, DB session, account/catalog models and source fetch paths.

## Data model

- `wb_finance_sync_runs`: immutable source snapshot metadata and checksum; exact duplicate snapshots are reused.
- `wb_finance_operations`: immutable content-addressed versions. `operation_id` includes tenant, account, source identity and payload checksum.
- `wb_finance_sync_run_operations`: immutable snapshot membership.

Alembic `0049` adds parent-linked delta membership, so unchanged operations are not copied into every revision. Alembic `0052` adds a tenant-scoped per-SKU projection for exact-period reads. Each projection and its readiness flag publish in the same transaction; sub-period reads retain operation-level filtering.

## Verification and rollout

1. Focused unit/API/migration tests, then the relevant backend suite and compile check.
2. Alembic upgrade/downgrade/upgrade on an empty PostgreSQL database and upgrade on a disposable production clone.
3. Frozen aggregate gate with zero monetary tolerance. The historic `1,208.00 RUB` adjustment has no retained raw `rrdId`; keep that evidence explicitly derived and do not claim the raw-operation integration gate is complete.
4. Live org2 shadow sync, compare legacy and canonical totals and operation IDs, verify 1/7/14/30/custom period states and p95 read latency.
5. Deploy the shadow reader after migrations, isolation and parity pass; keep the writer disabled unless its performance gate also passes. Keep release `b749fe1` as rollback target; do not switch frontend routes.

## Production canary evidence

- Alembic `0047` passed production-schema upgrade/downgrade/upgrade and a restore from the pre-migration scoped backup.
- Org `2`, account `2`, `2026-08-17…2026-08-23`: `62,465` operations; `61,389` main and `1,076` redemptions; unknown and late-correction rows `0`.
- Canonical and legacy live totals match exactly at `635,537,451` kopecks. The frozen total remains `635,658,251`; the missing `120,800`-kopeck correction has no retained raw identity.
- Cache-only read benchmark over 25 requests: p50 `212.5 ms`, p95 `298.9 ms`, max `302.53 ms` (`≤500 ms` gate passes).
- First membership materialization took about 15 minutes. A PostgreSQL COPY probe showed the composite FK checks remain the bottleneck, so the periodic shadow writer stays disabled pending a delta-membership design; no frontend route is switched.

## Final rollout evidence

- Production initially had `9` active legacy users and `0` canonical memberships because `0046` created `iam_memberships` without its specified `lk_users` backfill. Test-first commit `65b2d85` adds one shared lifecycle synchronizer and Alembic `0048`; production now has `9/9`, with zero missing or mismatched roles, permissions, active flags or scopes.
- Candidate image `sha256:93ae196157df1832b4fbafc5c9f7e74d7e1119e426768abafa3de3da6a6150f7`, label `65b2d85`, passed a restored-anchor PostgreSQL clone `0047→0048→0047→0048` and an authenticated route smoke before production migration.
- Final focused suite: `31 passed`; compile and diff checks pass. Full backend suite: `406 passed / 105 failed` in `264.71 s`; the 105 failures are the unchanged captured-production baseline set.
- API, worker and beat run the same candidate image. API health is `200`, Alembic is `20260902_0048`, Celery returns `pong`, restart counts are zero, and worker shadow ingestion resolves to `false`.
- Final production cache-only benchmark over 25 authenticated route calls: p50 `197.89 ms`, p95 `231.78 ms`, max `273.03 ms`; every response reconciled `62,465` operations to `635,537,451` kopecks.
- Pre-`0048` backup: `/var/backups/satorna-period-finance-pre-0048-20260902T0744Z/`; anchor checksum `c06b8860cf33e92f74ecb0b3281fbafb1d983fda02bc8d45527413f3342b7164`, schema checksum `d9d4c885a616cf7c45941174d611733b4d51de02aeca4a524d5dbd68aca4af4d`.
- Rollback tags `ogni-elfs-{api,worker,beat}:rollback-81258cb` point to `sha256:d5ae5181768d1ef48d208acb668183c3d56d8a15441818c18188a747454f00e5`; the earlier `rollback-b749fe1` tags remain intact.
- Historical gates at this point were the missing raw `120,800`-kopeck correction, 15-minute changed-snapshot membership materialization, and production's superuser DB runtime role. The refresh-hardening rollout below closes the latter two without changing frontend routes.

## Refresh-hardening rollout evidence

- Commits `dfd6060`, `f31f2bf`, `41cfb4d`, `59f4238`, `f277e4d`, `38606cc` and `73fa984` add atomic delta snapshots, indexed/append-only resolution, exact-period selection, the non-superuser runtime boundary and per-SKU rollups. Concurrent production migrations `0050` and `0051` were retained byte-for-byte; finance rollups are `0052`.
- The org `2` writer is enabled alone. A real current 7-day refresh reused `48,529` operations exactly. A changed 30-day canary fetched `271,211` operations in `151.578 s` and ingested them in `399.629 s`, while repeated health probes remained successful and no lock waits appeared.
- Production has three published snapshots and zero incomplete or unmaterialized rollups. Backfill reconciled every rollup row against the legacy operation query with zero tolerance: `62,465 / 635,537,451`, `48,529 / 634,901,083`, and `271,211 / 2,983,463,860` operations/kopecks.
- API, worker and beat use runtime role `satorna_runtime`, which is not superuser, owner, role/database creator, replication role or `BYPASSRLS`. Migrations run separately with the owner URL. Forced RLS, no-context/org1/org2 probes, a rolled-back two-session visibility probe and a cross-tenant write probe pass.
- Exact-period rollups reduce authenticated production route latency to p50/p95 `20.92/23.92 ms` for 7 days and `25.36/27.92 ms` for 30 days. The 30-day rollup scan itself executes in `0.786 ms` with shared-buffer hits only.
- Release `73fa984`, image `sha256:bd9c3f11a37a910ac3580a9bff7b1a5f475fa88521626f135244246f3cd221a1`, is deployed to migrate/API/worker/beat with zero restarts; Alembic is `20260902_0052`, health is `200`, and Celery returns `pong`.
- Final focused checks pass. Full backend result is `415 passed / 105 failed` in `271.63 s`; the same 105 failures are the captured legacy baseline.
- Pre-rollup backup: `/var/backups/satorna-finance-rollup-pre-0052-20260902T110306Z/`. Rollback tags `ogni-elfs-{api,worker,beat,migrate}:rollback-0b8366d-pre-73fa984` preserve the previous image.
- Still open: the source-missing historic `120,800`-kopeck correction, the pre-existing empty-chain `0019` defect, the 105 legacy failures, and frontend migration. No synthetic finance row was introduced.
