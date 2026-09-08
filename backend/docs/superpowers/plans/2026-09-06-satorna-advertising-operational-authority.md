# Satorna Advertising Operational Authority Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make exact, complete raw WB fullstats the operational advertising authority consumed by canonical ABC/P&L without mixing settlement evidence.

**Architecture:** Reuse `AdvertisingService.get_raw_reconciliation()` as the single evidence reader, derive one internally consistent spend total and attribution result in `get_pnl_source()`, and let ABC/P&L consume that result fail-closed. Keep final net/classification null behind a distinct blocker; add no persistence or collection path.

**Tech Stack:** Python 3.12, SQLAlchemy 2, FastAPI/Pydantic 2, pytest, PostgreSQL RLS-compatible service patterns.

**Spec:** `docs/superpowers/specs/2026-09-06-satorna-advertising-operational-authority-design.md`

## Global Constraints

- Use only an exact materialized `ads_fullstats/raw` snapshot with a complete request manifest.
- Never select, add or allocate `finance_promotion`, UPD or `derived_legacy` evidence into operational spend.
- Permit at most one kopeck of negative campaign residual; larger or missing spend fails closed.
- Treat complete empty raw evidence as authoritative zero.
- Publish row advertising/profit only when mapped spend equals the effective total.
- Keep `netProfitKopecks`, `profitClass` and `abcCode` null and explain them with `WB_PNL_CLASSIFICATION_NOT_CANONICAL` only after all upstream row inputs are complete.
- Add no migration, dependency, endpoint, configuration, scheduler, queue, cache or frontend change.
- Preserve `var/vella_repricer_runtime_state.json`, `.venv` and all unrelated user changes.
- Do not use GitHub.

## File map

- Modify `app/platform/advertising/service.py`: own raw authority selection, effective total, attribution and advertising blockers.
- Modify `app/modules/wb_reports/abc_pnl.py`: consume the service result, change formula version and add the classification gate.
- Modify `app/modules/wb_reports/schemas.py`: accept only the new formula version in the response schema.
- Modify `tests/test_advertising_raw_service.py`: prove raw money authority, rounding, mapping, empty and fail-closed behavior.
- Modify `tests/test_advertising_service.py`: prove finance and derived evidence are no longer operational fallbacks.
- Modify `tests/test_abc_pnl_service.py`: prove row/summary arithmetic and null propagation.
- Modify `tests/test_abc_pnl_v2.py`: prove the authenticated cache-only wire contract.
- Update this plan and root `SATORNA_ARCHITECTURE_HANDOFF.md` only after verified rollout.

---

### Task 1: Raw fullstats P&L source

**Files:**
- Modify: `tests/test_advertising_raw_service.py`
- Modify: `tests/test_advertising_service.py`
- Modify: `app/platform/advertising/service.py`

**Interfaces:**
- Consumes: `AdvertisingService.get_raw_reconciliation(marketplace_account_id: int, period: Period) -> AdvertisingRawReconciliation`.
- Produces: `AdvertisingPnlSource.blocker_ids: tuple[str, ...]` and `AdvertisingService.get_pnl_source(marketplace_account_id: int, period: Period) -> AdvertisingPnlSource` backed only by exact raw fullstats.

- [x] **Step 1: Add failing service tests**

Add a test-local catalog mapping for fixture `nmId=2001`, ingest the sanitized raw bundle, and assert the existing campaign/source residual becomes the P&L result:

```python
source = service.get_pnl_source(31, PERIOD)
assert source.state == "ready"
assert source.source_kind == "ads_fullstats"
assert source.evidence_status == "raw"
assert source.total_spend_kopecks == 200
assert source.spend_by_nm == {2001: 150}
assert source.unattributed_spend_kopecks == 50
assert source.blocker_ids == ("WB_PNL_ADVERTISING_UNATTRIBUTED",)
```

In the same test, persist a later non-zero `finance_promotion` observation and
assert the raw result is unchanged. Add focused cases for:

```python
# campaign 199, source detail 150, residual 50 -> effective total 200
assert tolerated.total_spend_kopecks == 200

# exact empty raw bundle
assert empty.state == "empty"
assert empty.total_spend_kopecks == 0
assert empty.unattributed_spend_kopecks == 0

# missing/ambiguous mapping carrying spend
assert unmapped.total_spend_kopecks == 200
assert unmapped.spend_by_nm == {}
assert unmapped.unattributed_spend_kopecks == 200
assert "WB_ADS_PRODUCT_MAPPING_MISSING" in unmapped.blocker_ids

# corrupted/missing spend hierarchy
assert invalid.state == "partial"
assert invalid.total_spend_kopecks is None
assert invalid.spend_by_nm == {}
```

Update the legacy-source tests so finance-only and derived-fullstats-only exact
periods both return `missing`, regardless of observation order.

- [x] **Step 2: Run RED tests**

Run:

```bash
.venv/bin/python -m pytest -q \
  tests/test_advertising_raw_service.py \
  tests/test_advertising_service.py
```

Expected: the new authority assertions fail because `get_pnl_source()` still
selects non-zero finance evidence and `AdvertisingPnlSource` lacks blockers.

- [x] **Step 3: Implement the minimum authority logic**

Append a defaulted field so existing constructors remain compatible:

```python
@dataclass(frozen=True, slots=True)
class AdvertisingPnlSource:
    state: AdvertisingSourceState
    period: Period
    snapshot: AdvertisingSnapshot | None
    source_kind: AdvertisingSourceKind | None
    evidence_status: str | None
    spend_by_nm: dict[int, int]
    total_spend_kopecks: int | None
    unattributed_spend_kopecks: int | None
    blocker_ids: tuple[str, ...] = ()
```

Remove the unconditional `WB_ADS_ACCOUNTING_AUTHORITY_UNRESOLVED` diagnostic
from `get_raw_reconciliation()`. Rewrite `get_pnl_source()` to call that method
and follow this exact decision order:

```python
reconciliation = self.get_raw_reconciliation(marketplace_account_id, period)
if reconciliation.snapshot is None:
    return AdvertisingPnlSource(
        state=reconciliation.state,
        period=period,
        snapshot=None,
        source_kind=None,
        evidence_status=None,
        spend_by_nm={},
        total_spend_kopecks=None,
        unattributed_spend_kopecks=None,
        blocker_ids=(
            ()
            if reconciliation.state == "future"
            else ("WB_PNL_ADS_NOT_CANONICAL",)
        ),
    )
if reconciliation.state == "partial":
    return AdvertisingPnlSource(
        state="partial",
        period=period,
        snapshot=reconciliation.snapshot,
        source_kind="ads_fullstats",
        evidence_status="raw",
        spend_by_nm={},
        total_spend_kopecks=None,
        unattributed_spend_kopecks=None,
        blocker_ids=("WB_PNL_ADS_NOT_CANONICAL",),
    )
source_missing = any(
    totals is None or totals.spend_kopecks is None
    for totals in (reconciliation.campaign, reconciliation.source_sku)
)
hierarchy_invalid = (
    reconciliation.campaign_only is None
    or reconciliation.campaign_only.spend_kopecks is None
)
if source_missing or hierarchy_invalid:
    blocker = (
        "WB_ADS_SOURCE_METRIC_INCOMPLETE"
        if source_missing
        else "WB_ADS_HIERARCHY_RECONCILIATION_FAILED"
    )
    return AdvertisingPnlSource(
        state="partial",
        period=period,
        snapshot=reconciliation.snapshot,
        source_kind="ads_fullstats",
        evidence_status="raw",
        spend_by_nm={},
        total_spend_kopecks=None,
        unattributed_spend_kopecks=None,
        blocker_ids=(blocker,),
    )

total = source_sku_spend + campaign_only_spend
spend_by_nm = {
    nm_id: int(metrics.spend_kopecks)
    for nm_id, metrics in reconciliation.source_sku_by_nm.items()
    if nm_id in reconciliation.mapped_catalog_sku_by_nm
}
unattributed = total - sum(spend_by_nm.values())
```

Only missing/ambiguous IDs whose aggregated spend is non-zero create mapping
blockers. Append `WB_PNL_ADVERTISING_UNATTRIBUTED` when `unattributed != 0`.
Return `empty` only for reconciliation state `empty`; otherwise return `ready`.
Do not gate money on UPD or non-spend metric diagnostics.

- [x] **Step 4: Run GREEN service tests**

Run the Step 2 command. Expected: all selected tests pass.

- [x] **Step 5: Commit Task 1**

```bash
git add app/platform/advertising/service.py \
  tests/test_advertising_raw_service.py tests/test_advertising_service.py
git commit -m "feat: make raw fullstats advertising authority"
```

---

### Task 2: ABC/P&L fail-closed consumer

**Files:**
- Modify: `tests/test_abc_pnl_service.py`
- Modify: `app/modules/wb_reports/abc_pnl.py`

**Interfaces:**
- Consumes: `AdvertisingPnlSource.blocker_ids`, `state`, `spend_by_nm`, effective `total_spend_kopecks` and `unattributed_spend_kopecks` from Task 1.
- Produces: formula `wb-abc-pnl-fullstats-loyalty-v1`, row/summary operational spend, and `WB_PNL_CLASSIFICATION_NOT_CANONICAL` after complete upstream calculation.

- [x] **Step 1: Replace finance fixtures with exact raw fixtures and add RED assertions**

Build the exact test-local raw bundle from the checked-in sanitized fixture;
this avoids a second representation of the WB envelope while making the test
period and amount explicit:

```python
def abc_raw_bundle(nm_id: int, spend_rubles: float = 123.0) -> dict[str, object]:
    bundle = json.loads(
        (Path(__file__).parent / "fixtures/wb_advertising_raw_sanitized.json")
        .read_text()
    )
    date_from, date_to, business_day = "2026-08-17", "2026-08-23", "2026-08-20"
    bundle["period"] = {"dateFrom": date_from, "dateTo": date_to}
    response = bundle["fullstats"][0]
    response.update(dateFrom=date_from, dateTo=date_to, campaignIds=[1001])
    response["payload"] = response["payload"][:1]
    campaign = response["payload"][0]
    campaign["sum"] = spend_rubles
    campaign["days"] = campaign["days"][:1]
    day = campaign["days"][0]
    day.update(date=f"{business_day}T00:00:00Z", sum=spend_rubles)
    day["apps"] = day["apps"][:1]
    app = day["apps"][0]
    app["sum"] = spend_rubles
    app["nms"] = app["nms"][:1]
    app["nms"][0].update(nmId=nm_id, sum=spend_rubles)
    for page in bundle["upd"]:
        page.update(dateFrom=date_from, dateTo=date_to)
    for item in bundle["manifest"]:
        request = item.get("request", {})
        for key in ("from", "beginDate"):
            if key in request:
                request[key] = date_from
        for key in ("to", "endDate"):
            if key in request:
                request[key] = date_to
        if "ids" in request:
            request["ids"] = "1001"
    return bundle
```

Ingest it through `ingest_raw_payload()` and assert:

```python
assert page.formula_version == "wb-abc-pnl-fullstats-loyalty-v1"
assert row.advertising_spend_kopecks == 12_300
assert row.profit_before_loyalty_kopecks == 10_200
assert row.profit_after_loyalty_kopecks == 9_900
assert page.advertising_snapshot.evidence_status == "raw"
assert page.blocker_ids == ("WB_PNL_CLASSIFICATION_NOT_CANONICAL",)
```

Also add one raw snapshot with campaign-only or unmapped spend and assert:

```python
assert page.summary.advertising_spend_kopecks == 12_350
assert page.summary.unattributed_advertising_spend_kopecks == 50
assert row.advertising_spend_kopecks is None
assert row.profit_before_loyalty_kopecks is None
assert row.profit_after_loyalty_kopecks is None
assert "WB_PNL_ADVERTISING_UNATTRIBUTED" in page.blocker_ids
```

Keep finance-only evidence in a regression case and assert it cannot populate
operational advertising. Keep final net/profit/ABC fields null.

- [x] **Step 2: Run RED ABC service tests**

Run:

```bash
.venv/bin/python -m pytest -q tests/test_abc_pnl_service.py
```

Expected: source, formula and blocker assertions fail under the old consumer.

- [x] **Step 3: Implement the minimal consumer change**

Set:

```python
FORMULA_VERSION = "wb-abc-pnl-fullstats-loyalty-v1"
```

Define advertising completeness from the Task 1 result, not merely snapshot
presence:

```python
advertising_complete = (
    advertising.state in {"ready", "empty"}
    and advertising.total_spend_kopecks is not None
    and advertising.unattributed_spend_kopecks == 0
    and not advertising.blocker_ids
)
source_blockers = (*advertising.blocker_ids,)
```

Append the loyalty blocker exactly as today. Continue passing `None` as each
row's advertising spend unless `advertising_complete`. After rows are built,
append `WB_PNL_CLASSIFICATION_NOT_CANONICAL` only when the non-empty page has no
upstream row blocker and every row has `profit_after_loyalty_kopecks` present.
Leave `net_profit_kopecks`, `profit_class` and `abc_code` unchanged as `None`.

- [x] **Step 4: Run GREEN ABC service tests**

Run the Step 2 command. Expected: all tests pass.

- [x] **Step 5: Commit Task 2**

```bash
git add app/modules/wb_reports/abc_pnl.py tests/test_abc_pnl_service.py
git commit -m "feat: consume operational advertising in abc pnl"
```

---

### Task 3: API contract

**Files:**
- Modify: `tests/test_abc_pnl_v2.py`
- Modify: `app/modules/wb_reports/schemas.py`

**Interfaces:**
- Consumes: Task 2 `AbcPnlPage` formula and blocker semantics.
- Produces: validated JSON with `formulaVersion=wb-abc-pnl-fullstats-loyalty-v1` and `advertisingSource=ads_fullstats`.

- [x] **Step 1: Add the RED wire-contract assertions**

Add this complete test-local helper in the API module:

```python
def abc_raw_bundle(nm_id: int, spend_rubles: float = 123.0) -> dict[str, object]:
    bundle = json.loads(
        (Path(__file__).parent / "fixtures/wb_advertising_raw_sanitized.json")
        .read_text()
    )
    date_from, date_to, business_day = "2026-08-17", "2026-08-23", "2026-08-20"
    bundle["period"] = {"dateFrom": date_from, "dateTo": date_to}
    response = bundle["fullstats"][0]
    response.update(dateFrom=date_from, dateTo=date_to, campaignIds=[1001])
    response["payload"] = response["payload"][:1]
    campaign = response["payload"][0]
    campaign["sum"] = spend_rubles
    campaign["days"] = campaign["days"][:1]
    day = campaign["days"][0]
    day.update(date=f"{business_day}T00:00:00Z", sum=spend_rubles)
    day["apps"] = day["apps"][:1]
    app = day["apps"][0]
    app["sum"] = spend_rubles
    app["nms"] = app["nms"][:1]
    app["nms"][0].update(nmId=nm_id, sum=spend_rubles)
    for page in bundle["upd"]:
        page.update(dateFrom=date_from, dateTo=date_to)
    for item in bundle["manifest"]:
        request = item.get("request", {})
        for key in ("from", "beginDate"):
            if key in request:
                request[key] = date_from
        for key in ("to", "endDate"):
            if key in request:
                request[key] = date_to
        if "ids" in request:
            request["ids"] = "1001"
    return bundle
```

Replace the API fixture's finance-promotion ingest with the complete raw bundle
for `nmId=453200669`, and keep the monkeypatch that makes any WB HTTP read fail.
Assert:

```python
assert payload["meta"]["formulaVersion"] == "wb-abc-pnl-fullstats-loyalty-v1"
assert payload["meta"]["advertisingSource"] == "ads_fullstats"
assert payload["meta"]["advertisingEvidenceStatus"] == "raw"
assert payload["meta"]["blockerIds"] == [
    "WB_PNL_CLASSIFICATION_NOT_CANONICAL"
]
```

Retain the existing response arithmetic, authentication, account-scope and
period-validation assertions.

- [x] **Step 2: Run RED API tests**

Run:

```bash
.venv/bin/python -m pytest -q tests/test_abc_pnl_v2.py
```

Expected: response-model validation fails until the schema literal changes.

- [x] **Step 3: Update only the formula literal**

```python
formulaVersion: Literal["wb-abc-pnl-fullstats-loyalty-v1"]
```

No router mapping or endpoint change is needed because the existing source and
evidence literals already include `ads_fullstats` and `raw`.

- [x] **Step 4: Run GREEN API tests**

Run the Step 2 command. Expected: all tests pass without an external WB call.

- [x] **Step 5: Commit Task 3**

```bash
git add app/modules/wb_reports/schemas.py tests/test_abc_pnl_v2.py
git commit -m "test: lock operational advertising api contract"
```

---

### Task 4: Review and local release gates

**Files:**
- Modify only files required by verified review findings.

**Interfaces:**
- Consumes: Tasks 1-3 commits.
- Produces: review-clean immutable candidate with no new backend failure ID.

- [x] **Step 1: Run focused/static gates**

```bash
.venv/bin/python -m pytest -q \
  tests/test_advertising_raw_normalization.py \
  tests/test_advertising_raw_service.py \
  tests/test_advertising_service.py \
  tests/test_abc_pnl_service.py \
  tests/test_abc_pnl_v2.py \
  tests/test_common_contracts.py \
  tests/test_openapi_generated_models.py
.venv/bin/python -m compileall -q app tests alembic
.venv/bin/ruff check --no-cache \
  app/platform/advertising/service.py \
  app/modules/wb_reports/abc_pnl.py \
  app/modules/wb_reports/schemas.py \
  tests/test_advertising_raw_service.py \
  tests/test_advertising_service.py \
  tests/test_abc_pnl_service.py tests/test_abc_pnl_v2.py
git diff --check
```

Expected: all focused/static commands pass.

- [x] **Step 2: Review the complete implementation diff**

Review from `4f7c669` to `HEAD` for tenant/account scope, exact-period selection,
unknown-to-zero coercion, double counting, negative residuals, incomplete
manifest visibility, and accidental production/network writes. Fix only proven
issues and rerun the focused gate.

- [x] **Step 3: Run one isolated full backend suite**

Use an isolated `VELLA_REPRICER_STATE_FILE`, emit JUnit XML, and compare
`ops.release_gate.junit_failure_ids()` with
`ops/legacy-test-failures.txt`. Expected: `added=[]`, `errors=[]`; the known
failure set remains exact, while additional passing tests increase the pass
count.

- [x] **Step 4: Verify repository integrity**

```bash
test "$(.venv/bin/alembic heads | wc -l | tr -d ' ')" = "1"
git show --check --stat HEAD
git fsck --no-reflogs
git status --short
```

Expected: one Alembic head, clean committed implementation, only preserved
runtime-state and `.venv` entries, and no Git corruption.

---

### Task 5: Production rollout and handoff

**Files:**
- Modify: `docs/superpowers/plans/2026-09-06-satorna-advertising-operational-authority.md`
- Modify outside backend Git: `SATORNA_ARCHITECTURE_HANDOFF.md`

**Interfaces:**
- Consumes: immutable candidate from Task 4 and the established release/rollback procedure.
- Produces: one-image production release, closed-day evidence and an exact next safe slice.

- [x] **Step 1: Capture pre-deploy state and rollback assets**

Record source revision, dirty production tree without modifying it, current
image IDs for API/default worker/canonical worker/beat/migrate, Alembic head,
service health, scheduler flags, environment checksum and scoped canonical
table counts/max timestamps. Create checksum-protected source/DB backup and
rollback image tags before switching services.

- [x] **Step 2: Build and deploy one immutable source**

Archive the committed worktree excluding Git metadata, `.venv`, runtime state,
caches and secrets. Build one image from that archive and use the same digest
for migrate, API, both workers and beat. Do not deploy from or clean the dirty
production checkout.

- [x] **Step 3: Verify production health and a closed-day canary**

Require migration exit `0`, `/health`, `/health/live`, `/health/ready` all
`200`, both Celery workers responding, zero restarts/OOM, scheduler still
disabled, and no new strict error logs. Query an existing closed exact raw day
through the authenticated ABC/P&L endpoint and verify:

```text
advertisingSource = ads_fullstats
advertisingEvidenceStatus = raw
summary = row spend + unattributed spend
finance promotion and UPD are not added
formulaVersion = wb-abc-pnl-fullstats-loyalty-v1
classification blocker present only when upstream row profit is complete
p95 <= 500 ms
```

- [x] **Step 4: Record evidence and commit docs**

Append exact commits, image digest, archive/backup checksums, test counts,
health, canary arithmetic, latency and rollback identifiers to this plan.
Update the root handoff with the completed slice, revised completion estimate
and the next unresolved canonical business boundary. Commit only the tracked
plan update; preserve all unrelated files.

## Completion evidence — 2026-09-07

- Runtime commits are `592073d`, `5b48b23` and `8c84e1e`. Strict RED was
  observed at each boundary; the final focused service/API/contract gate is
  `110 passed`. Ruff, compileall, one Alembic head, whitespace and object
  integrity checks pass.
- One fresh isolated full backend run at `8c84e1e` produced `677 passed / 105
  failed / 15 warnings` in `294.77 s`. All `105` failure identifiers exactly
  match `ops/legacy-test-failures.txt`; added, missing and error sets are empty.
- Production runs immutable source
  `/var/tmp/satorna-ads-authority-8c84e1e`, archive SHA-256
  `69cac87e1b23819967d218dd4770e360dc2c5db0d020c460e6c15df9f63326a5`,
  and one image
  `sha256:a247504bcb3db354f77fa5b11e5bbdf73127852abf912ecc400eab9dad41339a`
  for migrate, API, both workers and beat. Migration exits `0`; the schema
  remains `20260905_0060`.
- Internal and public `/health`, `/health/live` and `/health/ready` are `200`.
  Both Celery workers return `pong`; active, reserved and scheduled queues are
  empty. Live services have zero restarts/OOM events, strict post-boundary log
  matches are zero, and canonical scheduled collection remains disabled with
  an empty allowlist.
- The transaction-read-only closed-day canary for organization/account `2` on
  `2026-09-02` returns formula `wb-abc-pnl-fullstats-loyalty-v1`, source/evidence
  `ads_fullstats/raw`, raw campaign total `2,282`, effective total `2,283`, row
  total `2,283` and unattributed `0` kopecks. The one-kopeck hierarchy tolerance
  is retained. Exact `2026-08-31` settlement evidence is not substituted as an
  operational source. Twenty-five validated cache-only reads measured
  p50/p95/max `82.46/147.84/161.37 ms`.
- Backup
  `/var/backups/satorna-ads-authority-pre-8c84e1e-20260906T210945Z` is mode
  `0700`; all 28 files pass `sha256sum -c`, the scoped PostgreSQL dump passes
  `pg_restore -l`, and advertising/funnel/catalog/account evidence is unchanged
  across the rollout. Rollback tags
  `ogni-elfs-{api,worker,canonical-shadow-worker,beat,migrate}:rollback-1a7354f-pre-8c84e1e`
  point to prior image
  `sha256:5155436ff49a8a4ffe0e62489780afb0865bf9d2a61ae2f135b67259b8f75230`;
  rollback is image-only because both releases use schema `0060`.
