# Canonical WB Sales Funnel Daily Evidence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Persist account-scoped, immutable daily WB Sales Funnel evidence from the current `products/history` source without changing any report consumer.

**Architecture:** Fetch at most seven recent days in deterministic 20-SKU batches, normalize only source-proven daily metrics, and publish a complete snapshot atomically into two forced-RLS tables. A failed request never writes a run; an exact replay reuses the published run; a changed replay links to its prior run.

**Tech Stack:** Python 3.11, SQLAlchemy 2, Alembic, PostgreSQL, pytest, existing WB adapter/rate limiter.

**Spec:** `docs/superpowers/specs/2026-09-03-wb-funnel-advertising-canonical-design.md`

## Global constraints

- Preserve `var/vella_repricer_runtime_state.json`, `.venv`, and unrelated worktrees.
- Do not use GitHub. Do not modify the dirty production checkout.
- Scope is raw daily funnel evidence only: no scheduler, HTTP endpoint, report read switch, advertising join, loyalty, or legacy-cache rewrite.
- Source is `POST /api/analytics/v3/sales-funnel/products/history`; one request contains 1–20 sorted unique `nmIds` and a period of at most seven inclusive days.
- Store no impressions, cancellations, ratios, titles, brands, or inferred zero rows: the current official schema and the 2026-09-04 live probe did not expose them.
- Missing field/row remains missing; explicit zero remains zero. Money uses `Decimal`, never binary-float arithmetic.
- Fetch completes before the publication transaction. Therefore committed runs are published by definition; no staging/status abstraction is needed in v1.
- Reuse canonical `Period`, ownership FKs, tenant context, WB client/rate limiter, and the advertising raw publication pattern.

### Task 1: Freeze the proven source contract

**Files:**

- Modify: `docs/superpowers/specs/2026-09-03-wb-funnel-advertising-canonical-design.md`
- Create: `tests/fixtures/wb_funnel_history_daily_sanitized.json`

**Step 1: Amend the design from evidence**

Record these resolved decisions:

- daily source is `/api/analytics/v3/sales-funnel/products/history`, not repeated one-day `/products` period calls;
- current response is the exact `{"data": [...]}` wrapper; the normalizer may also accept the official bare-list example;
- request limit is 20 `nmIds`, selected period is at most the last seven days, aggregation is `day`;
- `openCount` means product-card transitions/opens, not impressions;
- v1 metrics are `openCount`, `cartCount`, `orderCount`, `orderSum`, `buyoutCount`, `buyoutSum`, `addToWishlistCount`, plus row currency;
- omitted fields and omitted rows are missing observations, never zero;
- cancellation/return accounting remains a future CSV/finance concern because the live daily payload exposes no cancellation fields.

Remove impressions and cancellations from the funnel v1 schema/test matrix. Keep advertising decisions unchanged.

**Step 2: Add one synthetic fixture**

Create a sanitized two-product/two-day bundle with no production identifiers or values. Include explicit zero, one omitted optional metric, one RUB currency, the source period, successful pages, and a complete manifest. Do not persist the live payload.

**Step 3: Validate documentation and fixture**

Run:

```bash
.venv/bin/python -m json.tool tests/fixtures/wb_funnel_history_daily_sanitized.json >/dev/null
rg -n "impression_count|cancel_count|cancel_amount|one-day.*products" docs/superpowers/specs/2026-09-03-wb-funnel-advertising-canonical-design.md
git diff --check
```

Expected: JSON is valid; remaining matches refer only to rejected legacy semantics or advertising; diff check passes.

**Step 4: Commit**

```bash
git add docs/superpowers/plans/2026-09-04-satorna-funnel-daily-evidence.md docs/superpowers/specs/2026-09-03-wb-funnel-advertising-canonical-design.md tests/fixtures/wb_funnel_history_daily_sanitized.json
git commit -m "docs: freeze canonical funnel history contract"
```

### Task 2: Normalize daily funnel evidence

**Files:**

- Create: `app/platform/funnel/__init__.py`
- Create: `app/platform/funnel/raw.py`
- Create: `tests/test_funnel_raw_normalization.py`

**Step 1: Write failing tests**

Cover only the trust-boundary invariants:

- fixture produces one fact per returned `(business_date, nmId)` with RUB amounts in kopecks;
- explicit zero survives while an omitted field remains `None`;
- official bare-list and live `{"data": [...]}` shapes normalize identically;
- exact duplicate identity collapses; conflicting duplicate raises `FunnelNormalizationError`;
- invalid/out-of-period dates, non-positive/bool `nmId`, negative metrics, fractional counts, invalid currency, malformed manifest, secret-like manifest keys, and imprecise money raise without leaking values;
- snapshot checksum ignores WB request IDs but changes with metric, coverage, or request-plan changes.

Run:

```bash
.venv/bin/pytest -q tests/test_funnel_raw_normalization.py
```

Expected: RED because `app.platform.funnel.raw` does not exist.

**Step 2: Implement the smallest pure model**

In `raw.py`, add:

```python
class FunnelNormalizationError(ValueError): ...

@dataclass(frozen=True, slots=True)
class RawFunnelDailyFact:
    source_identity: str
    payload_checksum: str
    business_date: date
    nm_id: int
    currency: str | None
    open_count: int | None
    cart_count: int | None
    order_count: int | None
    order_amount_kopecks: int | None
    buyout_count: int | None
    buyout_amount_kopecks: int | None
    add_to_wishlist_count: int | None

@dataclass(frozen=True, slots=True)
class RawFunnelEvidence:
    facts: tuple[RawFunnelDailyFact, ...]
    raw_manifest: list[dict[str, Any]]
    raw_manifest_checksum: str
    snapshot_checksum: str

def normalize_raw_funnel(period: Period, bundle: dict[str, Any]) -> RawFunnelEvidence: ...
```

Use source identity `funnel-history-v1|YYYY-MM-DD|nmId`. Hash canonical sorted JSON. Validate complete successful manifests and every returned row, but do not invent facts for requested IDs/dates absent from the response.

**Step 3: Run GREEN**

```bash
.venv/bin/pytest -q tests/test_funnel_raw_normalization.py
.venv/bin/python -m compileall -q app/platform/funnel
git diff --check
```

**Step 4: Commit**

```bash
git add app/platform/funnel tests/test_funnel_raw_normalization.py
git commit -m "feat: normalize canonical funnel history"
```

### Task 3: Add tenant-safe append-only storage

**Files:**

- Create: `app/platform/funnel/orm.py`
- Modify: `alembic/env.py`
- Create: `alembic/versions/20260904_0059_canonical_funnel_daily.py`
- Create: `tests/test_funnel_migration.py`

**Step 1: Write failing schema tests**

Assert:

- exactly two tables: `wb_funnel_sync_runs`, `wb_funnel_daily`;
- run has account composite FK, account-scoped parent FK, exact-snapshot uniqueness, period/count/coverage checks, and query/parent indexes;
- fact has account+run composite FK, run-scoped identity uniqueness, positive `nm_id`, non-negative nullable metrics, and at least one source metric non-null;
- both tables enable and force RLS with one tenant `USING`/`WITH CHECK` policy;
- downgrade is guarded when funnel evidence exists, then drops only these two tables;
- Alembic has one head, `20260904_0059` after `20260903_0058`.

Run:

```bash
.venv/bin/pytest -q tests/test_funnel_migration.py
```

Expected: RED because migration/models are absent.

**Step 2: Implement ORM and migration**

`WbFunnelSyncRunRow` stores ownership, optional parent, period, source reference, snapshot/raw-manifest checksums, raw manifest, expected/completed request counts, normalizer version, fact count, captured/last-observed/created timestamps.

`WbFunnelDailyRow` stores ownership/run, identity/checksum, date, `nm_id`, currency and only the seven v1 metrics. A publication transaction inserts the run and facts together; no status/staging table is added.

Import `app.platform.funnel.orm` in `alembic/env.py`.

**Step 3: Run GREEN**

```bash
.venv/bin/pytest -q tests/test_funnel_migration.py
.venv/bin/alembic heads
.venv/bin/python -m compileall -q app/platform/funnel alembic/versions/20260904_0059_canonical_funnel_daily.py
git diff --check
```

**Step 4: Commit**

```bash
git add app/platform/funnel/orm.py alembic/env.py alembic/versions/20260904_0059_canonical_funnel_daily.py tests/test_funnel_migration.py
git commit -m "feat: store canonical funnel daily evidence"
```

### Task 4: Fetch deterministic complete evidence

**Files:**

- Create: `app/wb_api/raw_funnel.py`
- Create: `tests/test_funnel_raw_fetch.py`

**Step 1: Write failing adapter tests**

Assert:

- 21 IDs create two POST requests of 20 and 1, in sorted deterministic order;
- request body contains only `selectedPeriod`, `nmIds`, `skipDeletedNm=false`, `aggregationLevel=day`;
- input duplicates collapse; bool/non-positive IDs and periods over seven days fail before I/O;
- response accepts exact bare list or exact `{"data": list}` only;
- 429 uses the existing bounded retry helper;
- any exhausted/error/malformed chunk yields `state="partial"`, keeps audit manifest/error code, and cannot masquerade as completed;
- reversing input order produces identical bundle request order and normalized snapshot checksum;
- manifest stores response checksum and WB request ID, never a token.

Run:

```bash
.venv/bin/pytest -q tests/test_funnel_raw_fetch.py
```

Expected: RED because `app.wb_api.raw_funnel` does not exist.

**Step 2: Implement fetch**

Add `RawFunnelFetch`, `RawFunnelFetchError`, `fetch_raw_funnel(period, nm_ids, *, wb_token, scenario="complete")`, and a testable `_execute_plan(client, period, nm_ids)`. Reuse `RateLimitedWbApiClient`, `build_wb_analytics_client`, `WbApiRequest`, and the existing bounded 429 retry helper. Never log payloads or credentials.

**Step 3: Run GREEN**

```bash
.venv/bin/pytest -q tests/test_funnel_raw_fetch.py tests/test_funnel_raw_normalization.py
.venv/bin/python -m compileall -q app/wb_api/raw_funnel.py
git diff --check
```

**Step 4: Commit**

```bash
git add app/wb_api/raw_funnel.py tests/test_funnel_raw_fetch.py
git commit -m "feat: fetch canonical funnel history"
```

### Task 5: Publish atomically and idempotently

**Files:**

- Create: `app/platform/funnel/service.py`
- Create: `tests/test_funnel_raw_service.py`

**Step 1: Write failing service tests**

Cover:

- connected WB account must belong to the organization;
- run and all facts commit atomically; an injected child insert failure leaves zero rows;
- exact replay returns the original run ID/count, monotonically advances `last_observed_at`, and creates no facts;
- changed metric creates one child run while preserving the prior snapshot;
- identical external IDs across two organizations/accounts never collide;
- PostgreSQL account/domain advisory lock occurs after ownership validation and before run lookup;
- malformed or partial evidence makes no writes;
- persisted manifest contains no secret-like keys.

Run:

```bash
.venv/bin/pytest -q tests/test_funnel_raw_service.py
```

Expected: RED because `FunnelService` is absent.

**Step 2: Implement publication**

Add `FunnelSnapshot`, `FunnelAccountNotFound`, and `FunnelService.ingest_raw_payload(...)`. Follow the proven advertising raw transaction order, but insert only a run and daily facts. Hash physical row IDs from organization/account/run/source identity. On any exception, rollback and re-raise.

**Step 3: Run GREEN**

```bash
.venv/bin/pytest -q tests/test_funnel_raw_service.py tests/test_funnel_raw_normalization.py
.venv/bin/python -m compileall -q app/platform/funnel/service.py
git diff --check
```

**Step 4: Commit**

```bash
git add app/platform/funnel/service.py tests/test_funnel_raw_service.py
git commit -m "feat: publish canonical funnel snapshots"
```

### Task 6: Add an explicit manual backfill boundary

**Files:**

- Create: `app/platform/funnel/raw_backfill.py`
- Modify: `tests/test_funnel_raw_service.py`

**Step 1: Write failing orchestration tests**

Assert that backfill:

- validates positive organization and an idle injected session before token resolution;
- requires exactly one connected WB account and at least one account-owned numeric catalog product;
- resolves token without emitting it;
- fetches outside the publication transaction and revalidates the same account afterward;
- returns partial counts/codes without calling the service;
- publishes ready evidence only and prints a secret-free JSON result;
- batches all account-owned `nmId`s through the fetch layer without changing legacy caches.

Run:

```bash
.venv/bin/pytest -q tests/test_funnel_raw_service.py
```

Expected: RED on missing backfill boundary.

**Step 2: Implement CLI**

Mirror the small raw-advertising backfill shape with arguments `--organization-id`, `--date-from`, `--date-to`. Product lookup is account-scoped and numeric IDs are sorted/deduplicated. Do not add a scheduler or API route.

**Step 3: Run GREEN**

```bash
.venv/bin/pytest -q tests/test_funnel_raw_service.py tests/test_funnel_raw_fetch.py tests/test_funnel_raw_normalization.py tests/test_funnel_migration.py
.venv/bin/python -m compileall -q app/platform/funnel app/wb_api/raw_funnel.py
git diff --check
```

**Step 4: Commit**

```bash
git add app/platform/funnel/raw_backfill.py tests/test_funnel_raw_service.py
git commit -m "feat: backfill canonical funnel evidence"
```

### Task 7: Verify, review, rehearse, and roll out

**Files:**

- Modify: `docs/superpowers/plans/2026-09-04-satorna-funnel-daily-evidence.md`
- Modify outside backend repository: `/Users/ilagulakin/Desktop/Work/OgniWB/SATORNA_ARCHITECTURE_HANDOFF.md`

**Step 1: Review the complete slice**

Inspect the full diff from `d72d0f5`, then run the configured code-review process. Fix every validated Critical/Important finding through RED → GREEN. Do not widen scope for unrelated legacy findings.

**Step 2: Run local gates once at final HEAD**

```bash
.venv/bin/python -m compileall -q app alembic/versions
.venv/bin/pytest -q tests/test_funnel_raw_normalization.py tests/test_funnel_raw_fetch.py tests/test_funnel_raw_service.py tests/test_funnel_migration.py
.venv/bin/alembic heads
git diff --check
git fsck --no-reflogs --full
```

Run the full suite once and compare JUnit failure identities with the checked-in 105-failure baseline. No added, missing, collection, or internal errors are allowed.

**Step 3: Rehearse PostgreSQL migration**

Restore a production-schema clone from a verified backup, upgrade `0058 -> 0059`, verify constraints/RLS/policies/indexes, run a sanitized publish/replay/change/rollback check, downgrade an empty clone, then upgrade again. Never downgrade production after evidence exists.

**Step 4: Prepare rollback before production mutation**

- Verify current immutable image/release and health.
- Create and checksum a fresh PostgreSQL backup.
- Build/tag an immutable image from the reviewed commit without GitHub.
- Record the prior image/release and exact rollback commands.
- Require at least 5 GB free; do not run broad Docker prune.

**Step 5: Deploy and canary**

Run `alembic upgrade head`, roll API/worker/beat to the same immutable image, and verify schema `20260904_0059`, container identity, `/health`, `/health/live`, `/health/ready`, Celery process health, and fresh error logs. Execute one recent two-day organization-scoped funnel backfill. Report only run/checksum prefix, request/fact counts, duplicate/conflict counts, and coverage—never raw IDs, payloads, or token.

**Step 6: Record evidence**

Append actual commands/results, release digest, backup/rollback pointers, production canary evidence, the disk-full worker incident, and the remaining architecture percentage to the plan and root handoff. Stop at a clean commit with only the two pre-existing preserved local paths dirty.

## Rollout evidence — 2026-09-04

- Reviewed implementation release: `4d3cbb1`; production image `sha256:b4f65e3f213bc112f927c70cd87cf45c83916e0a79aa9ab0212a11cd5c56ff9c`; migration head `20260904_0059`.
- PostgreSQL rehearsal passed `0058 -> 0059`, forced-RLS policy/constraint inspection, publish/replay/change and empty downgrade/upgrade. Populated downgrade is guarded.
- Local funnel gate passed; the full-suite failure-ID set remained exactly the checked-in `105`-failure baseline. CodeRabbit could not run because its CLI was not authenticated; no substitute CodeRabbit approval is claimed.
- Production organization-2 canary for `2026-09-02...2026-09-03` published run `4d21594d-8106-4a3c-bedd-e2b7a23efad5`, checksum `c7d2e942caab1905f7d352dc258b348593f350a9f19d5a7efd72b132b644f3c0`, `167/167` requests and `6,608` facts.
- Coverage is source-literal: `3,337` requested SKUs, `3,304` returned SKUs and `33` source omissions; no synthetic zero rows were created. Each day has `3,304` facts; identities and `(date, nm_id)` pairs are unique; returned SKUs outside the request are zero.
- Both funnel tables have enabled/forced RLS and one tenant `ALL` policy. No tenant and organization `1` read `0/0`; organization `2` reads `1/6,608`; a cross-tenant insert fails with SQLSTATE `42501` and persists nothing.
- Backup `/var/backups/satorna-funnel-pre-0059-20260904T093739Z` is mode `0700`; protected files are mode `0600`, and `sha256sum -c SHA256SUMS` passes. The prior `d6ad0b0` image remains tagged as `rollback-d6ad0b0-pre-4d3cbb1`.
- During rollout the existing worker was found stopped after an earlier disk-full event. The exact previous worker was restarted before the release; no broad prune or unrelated production mutation was performed. API, worker and beat then remained at restart count `0`.
- The final funnel release kept `/health`, `/health/live`, `/health/ready` at HTTP `200` and Celery at `pong`. Worker/beat readiness remains explicitly `not_monitored` until a shared heartbeat exists.
