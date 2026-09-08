# Satorna Canonical WB Advertising Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Persist immutable WB advertising evidence and subtract only the selected exact-period advertising subtotal in canonical ABC/P&L while loyalty keeps final profit blocked.

**Architecture:** Add one small advertising platform service over two forced-RLS tables. Existing WB sync writes legacy cache first and then shadow-ingests finance-promotion and fullstats payloads; exact-period P&L reads use only non-zero settlement promotion spend. Collapsed fullstats remain `derived_legacy` diagnostics because production-shaped replay proves their parser can double spend.

**Tech Stack:** Python 3.14, SQLAlchemy 2, PostgreSQL 16, Alembic, FastAPI/Pydantic v2, pytest.

**Spec:** `docs/superpowers/specs/2026-09-03-satorna-canonical-advertising-design.md`

## Global Constraints

- Do not call WB from HTTP reads, backfill, migration, tests or deployment gates.
- Do not allocate campaign-only, unknown, weak or aggregate-only spend to SKU.
- Do not promote `derived_legacy` fullstats into P&L.
- Money is signed integer kopecks; periods are inclusive Moscow dates via the existing `Period`.
- Preserve account ownership, transaction-local tenant context and forced PostgreSQL RLS.
- Do not add a scheduler, dependency, response cache, generic event model or frontend change.
- `netProfitKopecks`, `profitClass` and `abcCode` remain `null` until canonical loyalty exists.
- Preserve the exact 105 baseline failure IDs and all user-owned worktree changes.

---

### Task 1: Immutable tenant/account advertising schema

**Status:** completed in `91b1ca8`.

**Files:**
- Create: `app/platform/advertising/__init__.py`
- Create: `app/platform/advertising/orm.py`
- Create: `alembic/versions/20260903_0056_external_stamp.py`
- Create: `alembic/versions/20260903_0057_canonical_advertising.py`
- Modify: `alembic/env.py`
- Create: `tests/test_advertising_migration.py`

**Interfaces:**
- Produces: `WbAdvertisingSyncRunRow`, `WbAdvertisingFactRow`.
- Consumes: `marketplace_accounts(organization_id, marketplace_account_id)` and `app.organization_id` tenant GUC.

- [ ] **Step 1: Write failing migration/metadata tests**

```python
def test_advertising_migration_creates_forced_rls_tables(monkeypatch):
    created, statements = [], []
    monkeypatch.setattr(op, "create_table", lambda name, *_a, **_k: created.append(name))
    monkeypatch.setattr(op, "create_index", lambda *_a, **_k: None)
    monkeypatch.setattr(op, "execute", lambda value: statements.append(str(value)))
    migration = runpy.run_path(str(MIGRATION))
    migration["upgrade"]()
    assert migration["down_revision"] == "20260902_0055"
    assert set(created) == {"wb_advertising_sync_runs", "wb_advertising_facts"}
    for table in created:
        assert f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY" in statements

def test_advertising_fact_fk_contains_tenant_account_and_run():
    table = Base.metadata.tables["wb_advertising_facts"]
    assert ("organization_id", "marketplace_account_id", "sync_run_id") in {
        tuple(element.parent.name for element in constraint.elements)
        for constraint in table.foreign_key_constraints
    }
```

- [ ] **Step 2: Run the tests and verify RED**

Run: `.venv/bin/python -m pytest -q tests/test_advertising_migration.py`
Expected: fail because migration/module/tables do not exist.

- [ ] **Step 3: Implement the two ORM tables and migration**

Use exact check values from the spec and an atomic publication flag:

```python
class WbAdvertisingSyncRunRow(Base):
    __tablename__ = "wb_advertising_sync_runs"
    sync_run_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    organization_id: Mapped[int] = mapped_column(Integer, nullable=False)
    marketplace_account_id: Mapped[int] = mapped_column(Integer, nullable=False)
    source_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    date_from: Mapped[date] = mapped_column(Date, nullable=False)
    date_to: Mapped[date] = mapped_column(Date, nullable=False)
    source_reference: Mapped[str] = mapped_column(String(255), nullable=False)
    snapshot_checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    formula_version: Mapped[str] = mapped_column(String(32), nullable=False)
    source_total_spend_kopecks: Mapped[int] = mapped_column(BigInteger, nullable=False)
    fact_count: Mapped[int] = mapped_column(Integer, nullable=False)
    evidence_status: Mapped[str] = mapped_column(String(32), nullable=False)
    is_materialized: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
```

`WbAdvertisingFactRow` contains deterministic id, tenant/account/run, source
identity/checksum, nullable date/campaign/product, attribution, signed spend and
optional non-negative counters. Add a covering read index and composite unique
observation key. Import ORM metadata in `alembic/env.py`. Apply `ENABLE`,
`FORCE`, and the established tenant policy to both tables.

- [ ] **Step 4: Run focused tests and compile**

Run: `.venv/bin/python -m pytest -q tests/test_advertising_migration.py && .venv/bin/python -m compileall -q app/platform/advertising alembic/versions/20260903_005*.py`
Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add app/platform/advertising/__init__.py app/platform/advertising/orm.py \
  alembic/env.py alembic/versions/20260903_0056_external_stamp.py \
  alembic/versions/20260903_0057_canonical_advertising.py \
  tests/test_advertising_migration.py
git commit -m "feat: add canonical advertising ledger"
```

### Task 2: Normalization, idempotency and exact source selection

**Status:** completed in `9d64e99`, with derived-fullstats safety corrected in `2c7f15e`.

**Files:**
- Create: `app/platform/advertising/service.py`
- Create: `tests/test_advertising_service.py`

**Interfaces:**
- Produces: `AdvertisingService.ingest_payload(...) -> AdvertisingSnapshot`.
- Produces: `AdvertisingService.get_pnl_source(account_id, period) -> AdvertisingPnlSource`.
- Produces: `normalize_finance_promotion(...)`, `normalize_fullstats(...)` pure functions.
- Consumes: Task 1 ORM rows, `Period`, `set_tenant_context`.

- [ ] **Step 1: Write failing normalization and service tests**

Cover signed corrections, missing `nmId`, fullstats daily/aggregate/declared total
equality, mismatch rejection, source precedence, exact-period-only selection,
atomic visibility and repeat ingestion:

```python
def test_finance_promotion_keeps_signed_unattributed_row():
    facts, total = normalize_finance_promotion(
        PERIOD,
        {"rows": [{"rrdId": 7, "bonusTypeName": "WB Продвижение", "deduction": "-12.34", "rrDate": "2026-08-23"}]},
    )
    assert total == -1234
    assert facts[0].nm_id is None
    assert facts[0].attribution_level == "unknown"

def test_repeated_snapshot_only_updates_observation(session):
    service = AdvertisingService(session, 1)
    first = service.ingest_payload(31, PERIOD, "ads_fullstats", FULLSTATS, source_reference="ads_fixture", observed_at=T0)
    second = service.ingest_payload(31, PERIOD, "ads_fullstats", FULLSTATS, source_reference="ads_fixture", observed_at=T1)
    assert first.sync_run_id == second.sync_run_id
    assert session.scalar(select(func.count()).select_from(WbAdvertisingFactRow)) == first.fact_count

def test_finance_nonzero_precedes_fullstats_without_addition(session):
    source = AdvertisingService(session, 1).get_pnl_source(31, PERIOD)
    assert source.source_kind == "finance_promotion"
    assert source.total_spend_kopecks == 981_000
```

- [ ] **Step 2: Run tests and verify RED**

Run: `.venv/bin/python -m pytest -q tests/test_advertising_service.py`
Expected: import/behavior failures.

- [ ] **Step 3: Implement minimal pure normalization**

Canonical JSON serialization uses sorted keys and compact separators. A fact id
hashes tenant, account, source kind, period, snapshot checksum, source identity
and payload checksum. Finance source identity prefers `rrdId`, otherwise a
stable row fingerprint. Fullstats identity is `date|nmId`; missing daily dates,
non-dict rows, booleans as numbers and total mismatches raise
`AdvertisingNormalizationError`.

```python
@dataclass(frozen=True, slots=True)
class AdvertisingPnlSource:
    state: Literal["ready", "partial", "future", "empty", "missing"]
    snapshot: AdvertisingSnapshot | None
    source_kind: str | None
    evidence_status: str | None
    spend_by_nm: dict[int, int]
    total_spend_kopecks: int | None
    unattributed_spend_kopecks: int | None
```

- [ ] **Step 4: Implement atomic idempotent ingestion and exact selection**

Call `set_tenant_context` once in service preparation. Insert a run with
`is_materialized=False`, bulk-add facts, flush, compare count/signed total, then
publish. On an existing checksum, update only `last_observed_at`. Readers filter
`is_materialized=True`, exact dates and account. A non-zero finance run wins;
otherwise the P&L source is missing. Fullstats remain diagnostic and the two
totals are never summed.

- [ ] **Step 5: Run focused tests and commit**

Run: `.venv/bin/python -m pytest -q tests/test_advertising_migration.py tests/test_advertising_service.py`
Expected: pass.

```bash
git add app/platform/advertising/service.py tests/test_advertising_service.py
git commit -m "feat: normalize canonical advertising snapshots"
```

### Task 3: Shadow ingestion through the existing WB sync

**Status:** completed in `123d268`.

**Files:**
- Modify: `app/config.py`
- Modify: `app/repricer_sync.py`
- Modify: `docker-compose.yml`
- Create: `tests/test_advertising_shadow_bridge.py`
- Modify: `tests/test_infra_baseline.py`
- Modify: `tests/test_wb_repricer_bff.py`

**Interfaces:**
- Produces: `shadow_ingest_legacy_advertising_payload(organization_id, payload, source_kind, observed_at=None) -> dict`.
- Consumes: `VELLA_ADVERTISING_SHADOW_INGEST_ENABLED` and `VELLA_ADVERTISING_SHADOW_INGEST_ORGANIZATION_IDS`.

- [ ] **Step 1: Write failing bridge/config tests**

```python
def test_shadow_bridge_requires_enabled_org(monkeypatch):
    monkeypatch.setattr(service, "get_settings", lambda: SimpleNamespace(
        advertising_shadow_ingest_enabled=True,
        advertising_shadow_ingest_organization_ids=(2,),
    ))
    assert shadow_ingest_legacy_advertising_payload(1, {}, source_kind="ads_fullstats") == {"state": "disabled"}

def test_wb_sync_writes_ads_cache_before_advertising_shadow(monkeypatch):
    import app.repricer_sync as sync

    calls = []
    payload = {
        "aggregates": {},
        "dailyAggregates": {},
        "count": 0,
        "campaignCount": 0,
        "dateFrom": "2026-08-17",
        "dateTo": "2026-08-23",
        "totalSpendKopecks": 0,
    }
    monkeypatch.setattr(sync, "fetch_ads_spend_aggregates", lambda *_a, **_k: payload)
    monkeypatch.setattr(
        sync,
        "save_source_cache",
        lambda _organization_id, key, value, **_kwargs: calls.append(("legacy", key)) or value,
    )
    monkeypatch.setattr(
        sync,
        "shadow_ingest_legacy_advertising_payload",
        lambda *_a, **_k: calls.append(("canonical", "ads_fullstats")) or {"state": "ready"},
    )

    sync.refresh_wb_data_sources(
        organization_id=1,
        wb_token="token",
        date_from=date(2026, 8, 17),
        date_to=date(2026, 8, 23),
        execute_lock=False,
        sources=["ads"],
        _parallelize=False,
    )

    assert [kind for kind, _value in calls] == ["legacy", "canonical"]
```

- [ ] **Step 2: Run tests and verify RED**

Run: `.venv/bin/python -m pytest -q tests/test_advertising_shadow_bridge.py tests/test_infra_baseline.py tests/test_wb_repricer_bff.py -k 'advertising_shadow or writes_ads_cache'`
Expected: missing settings/function and ordering failures.

- [ ] **Step 3: Implement guarded bridge and sync calls**

Resolve exactly one WB account in a fresh session under tenant context. Return
only stable state/error codes; log exceptions without payloads. Call the bridge
after the finance and ads legacy cache writes. Include canonical snapshot
metadata in step diagnostics, not in source payload. Add disabled-by-default
environment variables to API, worker and beat compose sections.

- [ ] **Step 4: Run sync/config regression and commit**

Run: `.venv/bin/python -m pytest -q tests/test_advertising_shadow_bridge.py tests/test_infra_baseline.py tests/test_wb_repricer_bff.py tests/test_finance_shadow_bridge.py tests/test_repricer_tasks.py -k 'shadow or writes_ads_cache or finance_shadow'`
Expected: pass; unrelated baseline failures remain deselected.

```bash
git add app/config.py app/repricer_sync.py docker-compose.yml \
  tests/test_advertising_shadow_bridge.py tests/test_infra_baseline.py \
  tests/test_wb_repricer_bff.py
git commit -m "feat: shadow ingest WB advertising evidence"
```

### Task 4: Retained-evidence backfill

**Status:** completed in `cdf8b13`.

**Files:**
- Create: `app/platform/advertising/backfill.py`
- Create: `tests/test_advertising_backfill.py`

**Interfaces:**
- Produces: `backfill_advertising(organization_id, period) -> AdvertisingBackfillResult`.
- CLI: `python -m app.platform.advertising.backfill --organization-id N --date-from YYYY-MM-DD --date-to YYYY-MM-DD`.
- Consumes: exact `finance_<from>_<to>` and `ads_<from>_<to>` legacy cache rows only.

- [ ] **Step 1: Write failing backfill tests**

```python
def test_backfill_uses_retained_totals_without_allocating_finance(session):
    result = backfill_advertising(1, PERIOD, session=session)
    assert result.finance_total_kopecks == 981_000
    finance_run_id = session.scalar(
        select(WbAdvertisingSyncRunRow.sync_run_id).where(
            WbAdvertisingSyncRunRow.source_kind == "finance_promotion"
        )
    )
    facts = session.scalars(
        select(WbAdvertisingFactRow).where(
            WbAdvertisingFactRow.sync_run_id == finance_run_id
        )
    ).all()
    assert [(fact.nm_id, fact.spend_kopecks) for fact in facts] == [(None, 981_000)]

def test_backfill_is_idempotent(session):
    assert backfill_advertising(1, PERIOD, session=session).inserted_runs == 2
    assert backfill_advertising(1, PERIOD, session=session).inserted_runs == 0
```

- [ ] **Step 2: Run tests and verify RED**

Run: `.venv/bin/python -m pytest -q tests/test_advertising_backfill.py`
Expected: module/function missing.

- [ ] **Step 3: Implement exact-key backfill and JSON CLI output**

Reject absent/ambiguous WB accounts and missing/malformed exact caches. Fullstats
uses its retained daily rows. Finance without raw rows becomes exactly one
`aggregate_only` unknown fact equal to the retained aggregate total. Never read
`wb_ads_fullstats_daily_rows` or `wb_ads_spend_documents` for this release.

- [ ] **Step 4: Run focused tests and commit**

Run: `.venv/bin/python -m pytest -q tests/test_advertising_service.py tests/test_advertising_backfill.py`
Expected: pass.

```bash
git add app/platform/advertising/backfill.py tests/test_advertising_backfill.py
git commit -m "feat: backfill retained advertising evidence"
```

### Task 5: Canonical advertising subtotal in ABC/P&L

**Status:** completed in `a9cc582`; production release `205c11b`.

**Files:**
- Modify: `app/modules/wb_reports/abc_pnl.py`
- Modify: `app/modules/wb_reports/schemas.py`
- Modify: `app/routers/wb_reports_v2.py`
- Modify: `tests/test_abc_pnl_service.py`
- Modify: `tests/test_abc_pnl_v2.py`

**Interfaces:**
- Consumes: `AdvertisingService.get_pnl_source(...)`.
- Produces formula `wb-abc-pnl-advertising-v1` and the exact response fields from the spec.

- [ ] **Step 1: Write failing contract/formula tests**

```python
def test_exact_finance_promotion_subtracts_ads_and_keeps_loyalty_blocked(api):
    payload = api.get(PATH, params=PARAMS, headers=HEADERS).json()
    assert payload["items"][0]["advertisingSpendKopecks"] == 12_300
    assert payload["items"][0]["profitBeforeLoyaltyKopecks"] == 74_212
    assert payload["summary"]["unattributedAdvertisingSpendKopecks"] == 0
    assert payload["meta"]["formulaVersion"] == "wb-abc-pnl-advertising-v1"
    assert payload["meta"]["blockerIds"] == ["WB_PNL_LOYALTY_NOT_CANONICAL"]
    assert payload["items"][0]["netProfitKopecks"] is None

def test_aggregate_only_finance_spend_changes_summary_not_rows(api):
    payload = api.get(PATH, params=PARAMS, headers=HEADERS).json()
    assert payload["summary"]["advertisingSpendKopecks"] == 981_000
    assert payload["summary"]["unattributedAdvertisingSpendKopecks"] == 981_000
    assert payload["items"][0]["advertisingSpendKopecks"] is None
    assert payload["items"][0]["profitBeforeLoyaltyKopecks"] is None
```

Also test missing/future sources, an ads-only exact SKU union row, account scope,
pagination, `null` versus zero and that HTTP cannot call WB.

- [ ] **Step 2: Run tests and verify RED**

Run: `.venv/bin/python -m pytest -q tests/test_abc_pnl_v2.py tests/test_abc_pnl_service.py`
Expected: response fields/formula behavior missing.

- [ ] **Step 3: Extend the service projection minimally**

Load finance and advertising once. Add zero-valued finance facts only for exact
advertising `nmId`s absent from finance. For attributed source rows, subtract
per-SKU spend; an exact missing SKU is zero. For unattributed authoritative
spend, keep row advertising/profit null and subtract the proven total only in
the summary. Preserve all cost/economics blockers and add source-specific
blockers only when needed.

- [ ] **Step 4: Extend typed API serialization**

Add the row, summary and meta fields exactly as named in the spec. Advertising
meta fields are nullable when no snapshot exists. Keep the final three fields
typed as literal `None`.

- [ ] **Step 5: Run ABC/contract tests and commit**

Run: `.venv/bin/python -m pytest -q tests/test_abc_pnl_v2.py tests/test_abc_pnl_service.py tests/test_abc_pnl_costs.py backend_contracts/tests`
Expected: pass.

```bash
git add app/modules/wb_reports/abc_pnl.py app/modules/wb_reports/schemas.py \
  app/routers/wb_reports_v2.py tests/test_abc_pnl_service.py \
  tests/test_abc_pnl_v2.py
git commit -m "feat: include canonical advertising in ABC P&L"
```

### Task 6: Release verification, canary and production rollout

**Status:** completed; production release `205c11b` / Alembic `0057`.

**Files:**
- Modify: `docs/superpowers/plans/2026-09-03-satorna-canonical-advertising.md`
- Modify outside Git after successful rollout: `/Users/ilagulakin/Desktop/Work/OgniWB/SATORNA_ARCHITECTURE_HANDOFF.md`

**Interfaces:**
- Consumes all previous tasks.
- Produces reproducible release evidence and rollback identifiers.

- [x] **Step 1: Run local static, focused and full regression gates**

```bash
.venv/bin/python -m compileall -q app tests backend_contracts/vella_wb_19_05
.venv/bin/python -m pytest -q \
  tests/test_advertising_migration.py tests/test_advertising_service.py \
  tests/test_advertising_shadow_bridge.py tests/test_advertising_backfill.py \
  tests/test_abc_pnl_v2.py tests/test_abc_pnl_service.py \
  tests/test_abc_pnl_costs.py
.venv/bin/python -m pytest -q backend_contracts/tests
.venv/bin/python -m pytest -q tests backend_contracts/tests
```

Compare full failure node IDs exactly with the 105-ID baseline; any added,
missing or collection-error ID blocks release. Run `git diff --check` and the
repository's touched-file lint command.

- [x] **Step 2: Rehearse migration on a production-schema clone**

Create only a uniquely named task database/container from the production
schema, upgrade `0056 -> 0057`, downgrade `0057 -> 0056`, upgrade again, and
prove a single Alembic head. Production was externally stamped `0056` without
a corresponding migration or advertising tables, so `0056` is an explicit
compatibility no-op and the real schema is `0057`. Preserve the documented
empty-chain `0019` exception without relabeling it.

- [x] **Step 3: Create scoped backup and staged canary**

Back up schema plus legacy source rows for organization `2` and record
checksums/restore-list evidence. Build one immutable image from the committed
tree, excluding `.venv` and `var/vella_repricer_runtime_state.json`; use it for
migrate, API, worker and beat. Do not broad-prune the 99%-full server.

- [x] **Step 4: Backfill and prove data gates**

Run the explicit `2026-08-17..2026-08-23` backfill through
`satorna_runtime`, rerun it for idempotency, prove source totals `981000` and
`111076`, forced RLS/no-tenant/cross-tenant isolation, account ownership and
zero-tolerance ABC summary selection.

- [x] **Step 5: Measure and deploy only if every gate passes**

Measure authenticated 7/30/custom ABC/P&L 25 times in an uncontaminated window;
p95 must be at most `500 ms`. Create exact immediate rollback image tags, roll
all app processes to one digest, then verify migration head, external
`/health/live`, `/health/ready`, Celery pong, queue state and restart counts.

- [x] **Step 6: Record evidence and commit docs**

Update this plan's checkboxes/evidence and the root handoff with deployed SHA,
digest, backup, rollback, counts, parity, latency, remaining blockers and the
next bounded slice. Commit only the plan inside Git; do not stage the runtime
state or `.venv` symlink and do not use GitHub.

## Production release evidence

- The final code revision is `205c11b`. The immutable image digest is
  `sha256:ecb931743658334812b7c16c04f7f45c472f33a6370f0eda9151283171f7e3bb`;
  migrate exited `0`, while API, worker and beat run that same digest with
  revision label `205c11b`, zero restarts and no error lines in the first
  ten-minute release window.
- Production was already externally stamped `20260903_0056` without a matching
  migration file or advertising tables. Commit `6eff4f8` preserves that stamp
  as an explicit compatibility no-op and advances the real advertising schema
  to `20260903_0057`. A production-schema clone passed
  `0056 -> 0057 -> 0056 -> 0057`, including forced RLS and both tenant policies.
- Scoped backup
  `/var/backups/satorna-advertising-pre-0057-20260903T133707Z` contains the
  schema, anchor rows and the two exact retained source payloads. Every listed
  SHA-256 and gzip check passes. The pre-shadow production environment copy is
  mode `0600`; the live environment differs from it only in the two advertising
  shadow keys.
- The first PostgreSQL backfill canary exposed missing ORM flush ordering
  between a new run and its facts. The transaction rolled back fully, leaving
  `0/0` rows. Enabling SQLite foreign keys reproduced the same failure; the
  minimal parent flush in `205c11b` fixes it. The final full command
  `pytest -q --tb=no tests backend_contracts/tests` reports `520 passed`, the
  exact unchanged `105` legacy failures and `26` warnings in `273.54 s`.
  `compileall`, `git diff --check` and `git show --check` pass.
- Backfill `2026-08-17..2026-08-23` inserted two runs on its first execution and
  zero on its second. Finance promotion is one `aggregate_only` unknown fact
  totalling `981000` kopecks. Fullstats is `730` `derived_legacy` facts totalling
  `111076` kopecks. P&L selects only finance, reports all `981000` as
  unattributed and never adds or selects derived fullstats.
- Both tables have enabled and forced RLS with `ALL` tenant policies. The runtime
  role sees `0` runs with no tenant, `0` as organization `1`, and both runs as
  organization `2`; an organization-1 insert for organization `2` fails with
  SQLSTATE `42501`. The shadow bridge is enabled only for organization `2`:
  organization `1` returns `disabled`, while an idempotent organization-2 replay
  remains `730` facts and `111076` kopecks.
- Authenticated retained-period ABC/P&L returns formula
  `wb-abc-pnl-advertising-v1`, source `finance_promotion`, evidence
  `aggregate_only`, and spend/unattributed `981000/981000`; final net profit
  remains null behind explicit attribution, loyalty, cost and economics gates.
  Production p95 over 25 authenticated requests is `266.86 ms` retained,
  `337.98 ms` 7-day, `435.03 ms` 30-day and `334.62 ms` custom. A post-shadow
  retained rerun is p50/p95/max `119.34/294.57/295.75 ms`.
- External `/health/live`, `/health/ready` and legacy `/health` pass; readiness
  reports PostgreSQL, Redis, Celery broker and result backend `ok`. Celery
  returns `pong`; active, reserved and scheduled queues are empty. Worker/beat
  remain intentionally `not_monitored` until a canonical heartbeat exists.
- Immediate rollback tags
  `ogni-elfs-{api,worker,beat,migrate}:rollback-259977f-pre-205c11b` point to
  `sha256:1daef9da8d491f3483de5b23ff58268dff19ecec6fd0245b1db717fca18e57df`.
  The active compose source is retained at
  `/var/tmp/satorna-advertising-205c11b`; only the unused intermediate `6eff4f8`
  release directory and tags were removed. No GitHub operation was used, and
  user-owned runtime state plus the `.venv` symlink stayed outside commits and
  images.
