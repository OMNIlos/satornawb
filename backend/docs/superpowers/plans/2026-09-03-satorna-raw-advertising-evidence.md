# Satorna Raw Advertising Evidence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Persist account-scoped raw WB advertising hierarchy, campaign metadata and UPD lines as immutable canonical evidence without changing any report consumer.

**Architecture:** Reuse the deployed `wb_advertising_sync_runs` and `wb_advertising_facts` envelope, extending facts with explicit grain/scope/app semantics and adding only campaign-snapshot and spend-document child tables. A pure normalizer consumes a complete in-memory bundle produced through the existing typed WB adapter; an explicit CLI publishes the bundle atomically only when every planned read succeeds. Scheduled dual-write, persisted cursor resume, funnel storage and consumer cutover are separate slices.

**Tech Stack:** Python 3.12, SQLAlchemy 2, Alembic, PostgreSQL 16 RLS, SQLite unit tests, pytest, existing typed WB API client.

**Spec:** `docs/superpowers/specs/2026-09-03-wb-funnel-advertising-canonical-design.md`

## Global Constraints

- Work only in linked worktree `codex/satorna-canonical-funnel-ads-raw`; never stage `var/vella_repricer_runtime_state.json` or `.venv`.
- Do not use GitHub.
- Keep legacy caches, report GET paths, ABC/P&L/RNP readers and scheduler behavior unchanged.
- Use the existing `RateLimitedWbApiClient`; `fullstats` is at most 50 campaign IDs and 31 inclusive days per request, UPD at most 31 days.
- Validate all requested dates through canonical `Period` (`Europe/Moscow`, inclusive, 1–90 days).
- Never log or persist WB tokens. The committed fixture contains only synthetic IDs, names, dates and monetary values.
- Convert RUB with `Decimal(str(value))` and `ROUND_HALF_UP`; never use binary float arithmetic for kopecks.
- Preserve missing metrics as `NULL` and explicit zero as zero.
- Publish no canonical run unless every manifest request succeeded and normalized hierarchy checks pass.
- Enable and force PostgreSQL RLS on every new table with tenant `USING` and `WITH CHECK` policies.
- Production remained on revision `205c11b` until all local, clone-migration and rollback gates passed; the completed release is `d6ad0b0`.
- Manual bounded replay is the v1 recovery mechanism. Add persisted chunk resume only with scheduled dual-write, when a failed replay would otherwise breach the freshness SLA.

---

## File Map

- Create `tests/fixtures/wb_advertising_raw_sanitized.json`: synthetic raw-shape oracle derived from the verified live field structure.
- Create `app/platform/advertising/raw.py`: pure parsing, identity, reconciliation and snapshot checksums.
- Create `app/wb_api/raw_advertising.py`: read-only request plan and completeness manifest using the existing client.
- Create `app/platform/advertising/raw_backfill.py`: explicit organization-scoped CLI orchestration; no scheduler registration.
- Create `alembic/versions/20260903_0058_raw_advertising_evidence.py`: backward-compatible table extension and two tenant child tables.
- Create `tests/test_advertising_raw_normalization.py`: fixture-driven pure normalizer tests.
- Create `tests/test_advertising_raw_fetch.py`: request-plan/completeness tests against a fake typed client.
- Create `tests/test_advertising_raw_service.py`: atomic ingest, idempotency, revision and tenant tests.
- Modify `app/platform/advertising/orm.py`: map new columns and child tables.
- Modify `app/platform/advertising/service.py`: publish normalized raw evidence while keeping legacy ingest/P&L selection intact.
- Modify `tests/test_advertising_migration.py`: assert 0058 lineage, columns, composite FKs and forced RLS.
- Modify `SATORNA_ARCHITECTURE_HANDOFF.md` outside the backend Git worktree after rollout evidence is final.

---

### Task 1: Freeze the Raw Contract and Build the Pure Normalizer

**Files:**
- Create: `tests/fixtures/wb_advertising_raw_sanitized.json`
- Create: `tests/test_advertising_raw_normalization.py`
- Create: `app/platform/advertising/raw.py`

**Interfaces:**
- Consumes: `app.platform.period.Period` and a plain `dict[str, Any]` bundle with `promotion`, `adverts`, `fullstats`, `upd` and `manifest` keys.
- Produces: `normalize_raw_advertising(period: Period, bundle: dict[str, Any]) -> RawAdvertisingEvidence`.
- Produces immutable dataclasses `RawAdvertisingFact`, `RawAdvertisingCampaign`, `RawAdvertisingSpendDocument`, and `RawAdvertisingEvidence`.

- [x] **Step 1: Add one synthetic fixture matching the observed raw shape**

Use one day, two campaigns, two platform leaves for the same SKU, campaign-only metrics, and two UPD lines sharing one `updNum`. The additive values must satisfy campaign → day → app → `nms` equality and fullstats total = UPD total = 200 kopecks.

```json
{
  "period": {"dateFrom": "2026-09-01", "dateTo": "2026-09-01"},
  "promotion": {
    "adverts": [
      {"type": 8, "status": 9, "count": 1, "advert_list": [{"advertId": 1001, "changeTime": "2026-09-01T09:00:00+03:00"}]},
      {"type": 8, "status": 11, "count": 1, "advert_list": [{"advertId": 1002, "changeTime": "2026-09-01T09:05:00+03:00"}]}
    ],
    "all": 2
  },
  "adverts": {
    "adverts": [
      {
        "id": 1001,
        "status": 9,
        "bid_type": "manual",
        "currency": "RUB",
        "settings": {"name": "campaign-a", "payment_type": "cpm", "placements": {}},
        "timestamps": {"created": "2026-08-01T09:00:00+03:00", "started": "2026-08-02T09:00:00+03:00", "updated": "2026-09-01T09:00:00+03:00", "deleted": null},
        "restrictions": {"can_change_nms": true},
        "nm_settings": [{"nm_id": 2001, "bids_kopecks": {}, "subject": {}}]
      },
      {
        "id": 1002,
        "status": 11,
        "bid_type": "manual",
        "currency": "RUB",
        "settings": {"name": "campaign-b", "payment_type": "cpm", "placements": {}},
        "timestamps": {"created": "2026-08-01T09:00:00+03:00", "started": null, "updated": "2026-09-01T09:05:00+03:00", "deleted": null},
        "restrictions": {"can_change_nms": true},
        "nm_settings": []
      }
    ]
  },
  "fullstats": [
    {
      "dateFrom": "2026-09-01",
      "dateTo": "2026-09-01",
      "campaignIds": [1001, 1002],
      "payload": [
        {
          "advertId": 1001,
          "views": 15,
          "clicks": 3,
          "ctr": 20.0,
          "cpc": 0.5,
          "sum": 1.5,
          "atbs": 1,
          "orders": 1,
          "cr": 33.33,
          "shks": 1,
          "sum_price": 5,
          "canceled": 1,
          "currency": "RUB",
          "days": [
            {
              "date": "2026-09-01T00:00:00Z",
              "views": 15,
              "clicks": 3,
              "ctr": 20.0,
              "cpc": 0.5,
              "sum": 1.5,
              "atbs": 1,
              "orders": 1,
              "cr": 33.33,
              "shks": 1,
              "sum_price": 5,
              "canceled": 1,
              "apps": [
                {"appType": 1, "views": 10, "clicks": 2, "ctr": 20.0, "cpc": 0.55, "sum": 1.1, "atbs": 1, "orders": 1, "cr": 50.0, "shks": 1, "sum_price": 5, "canceled": 0, "nms": [{"name": "product-a", "nmId": 2001, "views": 10, "clicks": 2, "ctr": 20.0, "cpc": 0.55, "sum": 1.1, "atbs": 1, "orders": 1, "cr": 50.0, "shks": 1, "sum_price": 5, "canceled": 0}]},
                {"appType": 32, "views": 5, "clicks": 1, "ctr": 20.0, "cpc": 0.4, "sum": 0.4, "atbs": 0, "orders": 0, "cr": 0, "shks": 0, "sum_price": 0, "canceled": 1, "nms": [{"name": "product-a", "nmId": 2001, "views": 5, "clicks": 1, "ctr": 20.0, "cpc": 0.4, "sum": 0.4, "atbs": 0, "orders": 0, "cr": 0, "shks": 0, "sum_price": 0, "canceled": 1}]}
              ]
            }
          ],
          "boosterStats": []
        },
        {
          "advertId": 1002,
          "views": 4,
          "clicks": 0,
          "ctr": 0,
          "cpc": 0,
          "sum": 0.5,
          "atbs": 0,
          "orders": 0,
          "cr": 0,
          "shks": 0,
          "sum_price": 0,
          "canceled": 0,
          "currency": "RUB",
          "days": [{"date": "2026-09-01T00:00:00Z", "views": 4, "clicks": 0, "ctr": 0, "cpc": 0, "sum": 0.5, "atbs": 0, "orders": 0, "cr": 0, "shks": 0, "sum_price": 0, "canceled": 0, "apps": []}],
          "boosterStats": []
        }
      ]
    }
  ],
  "upd": [
    {
      "dateFrom": "2026-09-01",
      "dateTo": "2026-09-01",
      "payload": [
        {"updNum": 7001, "updTime": "2026-09-01T12:00:00+03:00", "updSum": 1.5, "advertId": 1001, "campName": "campaign-a", "advertType": 8, "paymentType": "cpm", "advertStatus": 9, "currency": "RUB"},
        {"updNum": 7001, "updTime": "2026-09-01T12:05:00+03:00", "updSum": 0.5, "advertId": 1002, "campName": "campaign-b", "advertType": 8, "paymentType": "cpm", "advertStatus": 11, "currency": "RUB"}
      ]
    }
  ],
  "manifest": [
    {"endpoint": "GET /adv/v1/promotion/count", "ok": true, "statusCode": 200, "request": {}},
    {"endpoint": "GET /api/advert/v2/adverts", "ok": true, "statusCode": 200, "request": {"statuses": "7,9,11"}},
    {"endpoint": "GET /adv/v1/upd", "ok": true, "statusCode": 200, "request": {"from": "2026-09-01", "to": "2026-09-01"}},
    {"endpoint": "GET /adv/v3/fullstats", "ok": true, "statusCode": 200, "request": {"ids": "1001,1002", "beginDate": "2026-09-01", "endDate": "2026-09-01"}}
  ]
}
```

- [x] **Step 2: Write failing normalizer tests**

Name the breaks before the bodies: recursively summing headers would inflate 200 kopecks; dropping `appType` would collapse two leaves; `or`-based parsing would turn explicit zero into missing; using `updNum` alone would collapse two real lines.

```python
def test_raw_hierarchy_preserves_scope_app_and_exact_totals(raw_bundle):
    evidence = normalize_raw_advertising(PERIOD, raw_bundle)
    assert evidence.source_total_spend_kopecks == 200
    assert evidence.document_total_spend_kopecks == 200
    assert len(evidence.spend_documents) == 2
    leaves = [fact for fact in evidence.facts if fact.fact_scope == "source_sku"]
    assert [(fact.app_type, fact.spend_kopecks) for fact in leaves] == [(1, 110), (32, 40)]
    assert leaves[1].clicks == 1
    assert leaves[1].cart_adds == 0
    assert leaves[1].cancel_count == 1


def test_raw_exact_duplicate_collapses_but_conflict_blocks(raw_bundle):
    duplicate = copy.deepcopy(raw_bundle["upd"][0]["payload"][0])
    raw_bundle["upd"][0]["payload"].append(duplicate)
    assert len(normalize_raw_advertising(PERIOD, raw_bundle).spend_documents) == 2
    raw_bundle["upd"][0]["payload"][-1]["updSum"] = 9
    with pytest.raises(AdvertisingNormalizationError, match="conflicting"):
        normalize_raw_advertising(PERIOD, raw_bundle)


def test_raw_child_totals_cannot_exceed_parent(raw_bundle):
    raw_bundle["fullstats"][0]["payload"][0]["days"][0]["apps"][0]["nms"][0]["sum"] = 9
    with pytest.raises(AdvertisingNormalizationError, match="hierarchy"):
        normalize_raw_advertising(PERIOD, raw_bundle)
```

- [x] **Step 3: Run the tests and verify RED**

Run: `.venv/bin/python -m pytest -q tests/test_advertising_raw_normalization.py`

Expected: collection fails with `ModuleNotFoundError: app.platform.advertising.raw`.

- [x] **Step 4: Implement the minimum pure model and normalizer**

Use explicit nullable metrics and composite source identities. The public model is:

```python
FactGrain = Literal["day", "period"]
FactScope = Literal["campaign", "source_sku"]


@dataclass(frozen=True, slots=True)
class RawAdvertisingFact:
    source_identity: str
    payload_checksum: str
    grain: FactGrain
    date_from: date
    date_to: date
    business_date: date | None
    campaign_id: int
    fact_scope: FactScope
    app_type: int | None
    nm_id: int | None
    currency: str | None
    spend_kopecks: int | None
    impressions: int | None
    clicks: int | None
    cart_adds: int | None
    order_count: int | None
    order_revenue_kopecks: int | None
    cancel_count: int | None


@dataclass(frozen=True, slots=True)
class RawAdvertisingCampaign:
    source_identity: str
    payload_checksum: str
    campaign_id: int
    name: str | None
    campaign_type: int | None
    status: int | None
    payment_type: str | None
    bid_type: str | None
    member_nm_ids: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class RawAdvertisingSpendDocument:
    source_identity: str
    payload_checksum: str
    upd_num: str
    upd_time: datetime
    business_date: date
    campaign_id: int
    campaign_name: str | None
    campaign_type: int | None
    payment_type: str | None
    campaign_status: int | None
    currency: str | None
    spend_kopecks: int


@dataclass(frozen=True, slots=True)
class RawAdvertisingEvidence:
    facts: tuple[RawAdvertisingFact, ...]
    campaigns: tuple[RawAdvertisingCampaign, ...]
    spend_documents: tuple[RawAdvertisingSpendDocument, ...]
    source_total_spend_kopecks: int
    document_total_spend_kopecks: int
    raw_manifest_checksum: str
    snapshot_checksum: str
```

Implementation rules:

```python
def normalize_raw_advertising(period: Period, bundle: dict[str, Any]) -> RawAdvertisingEvidence:
    _validate_bundle_period(period, bundle)
    _require_complete_manifest(bundle.get("manifest"))
    campaigns = _normalize_campaigns(bundle.get("promotion"), bundle.get("adverts"))
    facts = _normalize_fullstats(period, bundle.get("fullstats"))
    documents = _normalize_upd(period, bundle.get("upd"))
    manifest_checksum = _hash(_canonical_manifest(bundle))
    return _evidence(facts, campaigns, documents, manifest_checksum)
```

- Parse `Z` as `+00:00`, reject naive fullstats/UPD timestamps, then derive `astimezone(MOSCOW).date()`.
- Create one period campaign fact per returned campaign header, one day campaign fact per `days[]`, and one day `source_sku` fact per `apps[].nms[]` leaf.
- Include `appType` in source-SKU identity; never recurse through arbitrary nodes and never ingest a top-level app branch when `days` exists.
- Reject a top-level app branch without dated `days` in v1 with `AdvertisingNormalizationError("unsupported period-only fullstats")`.
- Compare every present additive child metric with its parent; child sum may be lower. WB source-level rounding may put money children at most `0.01 RUB` above their parent; integer metrics remain exact and any larger delta fails closed.
- Require positive `advertId`, `nmId`, `appType`; require at least one source metric to be present.
- Hash identities and payloads with sorted compact JSON. Exact duplicates collapse; the same identity with a different checksum raises a conflict.
- Require UPD `updNum`, positive `advertId`, aware `updTime`; identity is `upd-v1|updNum|advertId|normalized UTC updTime`.
- Do not require fullstats and UPD totals to equal; they remain parallel observations until the consumer policy is approved.

- [x] **Step 5: Verify GREEN and mutation coverage**

Run: `.venv/bin/python -m pytest -q tests/test_advertising_raw_normalization.py tests/test_advertising_service.py`

Expected: all selected tests pass. Mentally verify that removing `appType` from identity, changing the composite UPD identity, using `row.get(key) or 0`, or allowing child > parent breaks at least one test.

- [x] **Step 6: Commit Task 1**

```bash
git add app/platform/advertising/raw.py tests/fixtures/wb_advertising_raw_sanitized.json tests/test_advertising_raw_normalization.py
git commit -m "feat: normalize raw WB advertising evidence"
```

---

### Task 2: Extend the Canonical Schema Without Rewriting Existing Evidence

**Files:**
- Create: `alembic/versions/20260903_0058_raw_advertising_evidence.py`
- Modify: `app/platform/advertising/orm.py`
- Modify: `tests/test_advertising_migration.py`

**Interfaces:**
- Consumes: existing 0057 `wb_advertising_sync_runs` and `wb_advertising_facts` rows.
- Produces: columns needed by `RawAdvertisingFact`, `WbAdvertisingCampaignSnapshotRow`, and `WbAdvertisingSpendDocumentRow`.

- [x] **Step 1: Write failing migration/model tests**

The breaks are missing tenant/account/run FKs, nullable legacy backfill fields, or a policy omitted from either new table.

```python
RAW_MIGRATION = ROOT / "alembic" / "versions" / "20260903_0058_raw_advertising_evidence.py"
RAW_TABLES = {"wb_advertising_campaign_snapshots", "wb_advertising_spend_documents"}


def test_raw_advertising_migration_extends_0057_and_forces_rls(monkeypatch):
    created, statements = [], []
    monkeypatch.setattr(op, "create_table", lambda name, *_a, **_k: created.append(name))
    monkeypatch.setattr(op, "add_column", lambda *_a, **_k: None)
    monkeypatch.setattr(op, "alter_column", lambda *_a, **_k: None)
    monkeypatch.setattr(op, "create_index", lambda *_a, **_k: None)
    monkeypatch.setattr(op, "create_foreign_key", lambda *_a, **_k: None)
    monkeypatch.setattr(op, "create_check_constraint", lambda *_a, **_k: None)
    monkeypatch.setattr(op, "drop_constraint", lambda *_a, **_k: None)
    monkeypatch.setattr(op, "execute", lambda statement: statements.append(str(statement)))
    migration = runpy.run_path(str(RAW_MIGRATION))
    migration["upgrade"]()
    assert migration["revision"] == "20260903_0058"
    assert migration["down_revision"] == "20260903_0057"
    assert set(created) == RAW_TABLES
    for table in RAW_TABLES:
        assert f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY" in statements
        assert f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY" in statements


def test_raw_advertising_models_have_explicit_grain_and_composite_children():
    fact = Base.metadata.tables["wb_advertising_facts"]
    assert {"grain", "date_from", "date_to", "fact_scope", "app_type", "currency", "cancel_count"} <= set(fact.c)
    for name in RAW_TABLES:
        table = Base.metadata.tables[name]
        assert ("organization_id", "marketplace_account_id", "sync_run_id") in {
            tuple(element.parent.name for element in constraint.elements)
            for constraint in table.foreign_key_constraints
        }
```

- [x] **Step 2: Run migration tests and verify RED**

Run: `.venv/bin/python -m pytest -q tests/test_advertising_migration.py`

Expected: failure because revision 0058 and the mapped columns/tables do not exist.

- [x] **Step 3: Implement migration 0058**

Add these run columns with legacy-safe defaults:

```python
op.add_column(RUN_TABLE, sa.Column("parent_sync_run_id", sa.String(36), nullable=True))
op.add_column(RUN_TABLE, sa.Column("raw_manifest_checksum", sa.String(64), nullable=True))
op.add_column(RUN_TABLE, sa.Column("campaign_count", sa.Integer(), nullable=False, server_default="0"))
op.add_column(RUN_TABLE, sa.Column("spend_document_count", sa.Integer(), nullable=False, server_default="0"))
op.add_column(RUN_TABLE, sa.Column("document_total_spend_kopecks", sa.BigInteger(), nullable=True))
```

Add fact columns nullable, backfill from the owning 0057 run, then make the first four non-null:

```sql
UPDATE wb_advertising_facts AS fact
SET grain = CASE WHEN fact.business_date IS NULL THEN 'period' ELSE 'day' END,
    date_from = COALESCE(fact.business_date, run.date_from),
    date_to = COALESCE(fact.business_date, run.date_to),
    fact_scope = CASE
        WHEN fact.nm_id IS NOT NULL THEN 'source_sku'
        WHEN fact.campaign_id IS NOT NULL THEN 'campaign'
        ELSE 'account'
    END
FROM wb_advertising_sync_runs AS run
WHERE run.organization_id = fact.organization_id
  AND run.marketplace_account_id = fact.marketplace_account_id
  AND run.sync_run_id = fact.sync_run_id
```

Columns are `grain String(16)`, `date_from Date`, `date_to Date`, `fact_scope String(16)`, nullable `app_type Integer`, nullable `currency String(8)`, and nullable `cancel_count BigInteger`. Alter `spend_kopecks` to nullable because an observed raw row may omit `sum` while containing another metric.

Before replacing the old observation uniqueness, run a PostgreSQL `DO` guard that raises if any existing `(organization_id, marketplace_account_id, sync_run_id, source_identity)` group has more than one row. Replace it with unique run + source identity. Add checks for:

```sql
grain IN ('day', 'period')
AND date_from <= date_to
AND (grain <> 'day' OR date_from = date_to)
AND fact_scope IN ('account', 'campaign', 'source_sku')
AND (
  (fact_scope = 'account' AND campaign_id IS NULL AND nm_id IS NULL)
  OR (fact_scope = 'campaign' AND campaign_id IS NOT NULL AND nm_id IS NULL)
  OR (fact_scope = 'source_sku' AND nm_id IS NOT NULL)
)
```

Create the self-parent FK/check/index on runs. Create both child tables with a composite FK to `(organization_id, marketplace_account_id, sync_run_id)`, unique run + source identity, query indexes, and the exact columns represented by the Task 1 campaign/document dataclasses. Enable and force RLS with the same tenant expression as 0057.

Downgrade must first raise if any run has `formula_version = 'wb-advertising-raw-v1'`; otherwise drop child tables, indexes/FKs/checks, restore the 0057 uniqueness/metric constraint and non-null `spend_kopecks`, then drop added columns.

- [x] **Step 4: Map the migration in ORM**

Keep current class names and add:

```python
class WbAdvertisingCampaignSnapshotRow(Base):
    __tablename__ = "wb_advertising_campaign_snapshots"


class WbAdvertisingSpendDocumentRow(Base):
    __tablename__ = "wb_advertising_spend_documents"
```

Use `JSON` for sorted `member_nm_ids`, timezone-aware `DateTime` for UPD time, `BigInteger` for external IDs/money/counts, and the same composite FKs and checks as the migration. Existing raw/legacy models must still create cleanly under SQLite with foreign keys enabled.

- [x] **Step 5: Verify schema tests and existing canonical tests**

Run: `.venv/bin/python -m pytest -q tests/test_advertising_migration.py tests/test_advertising_service.py tests/test_advertising_backfill.py tests/test_advertising_shadow_bridge.py tests/test_infra_baseline.py`

Expected: all selected tests pass.

- [x] **Step 6: Commit Task 2**

```bash
git add alembic/versions/20260903_0058_raw_advertising_evidence.py app/platform/advertising/orm.py tests/test_advertising_migration.py
git commit -m "feat: store raw advertising evidence"
```

---

### Task 3: Publish Raw Evidence Atomically and Idempotently

**Files:**
- Modify: `app/platform/advertising/service.py`
- Create: `tests/test_advertising_raw_service.py`

**Interfaces:**
- Consumes: `normalize_raw_advertising(period, bundle)` and Task 2 ORM rows.
- Produces: `AdvertisingService.ingest_raw_payload(marketplace_account_id: int, period: Period, bundle: dict[str, Any], *, source_reference: str, observed_at: datetime | None = None) -> AdvertisingSnapshot`.

- [x] **Step 1: Write the failing atomic/idempotent service test**

The breaks are publishing partial data, summing campaign and SKU scopes together, duplicating an exact replay, or losing revision lineage.

```python
def test_raw_ingest_is_atomic_idempotent_and_parent_linked(session, raw_bundle):
    service = AdvertisingService(session, 1, now=lambda: NOW)
    first = service.ingest_raw_payload(31, PERIOD, raw_bundle, source_reference="wb_api:probe")
    replay = service.ingest_raw_payload(31, PERIOD, raw_bundle, source_reference="wb_api:probe", observed_at=LATER)
    assert replay.sync_run_id == first.sync_run_id
    assert session.scalar(select(func.count()).select_from(WbAdvertisingFactRow)) == 6
    assert session.scalar(select(func.count()).select_from(WbAdvertisingCampaignSnapshotRow)) == 2
    assert session.scalar(select(func.count()).select_from(WbAdvertisingSpendDocumentRow)) == 2

    changed = copy.deepcopy(raw_bundle)
    changed["fullstats"][0]["payload"][1]["sum"] = 0.6
    changed["fullstats"][0]["payload"][1]["days"][0]["sum"] = 0.6
    second = service.ingest_raw_payload(31, PERIOD, changed, source_reference="wb_api:probe", observed_at=LATER)
    row = session.get(WbAdvertisingSyncRunRow, second.sync_run_id)
    assert row.parent_sync_run_id == first.sync_run_id
```

Add a separate test where a manifest row has `ok=False`: `ingest_raw_payload` must raise and all four canonical table counts remain unchanged. Add a two-tenant test with identical external IDs proving composite FKs do not collide.

- [x] **Step 2: Run service tests and verify RED**

Run: `.venv/bin/python -m pytest -q tests/test_advertising_raw_service.py`

Expected: `AdvertisingService` has no `ingest_raw_payload` method.

- [x] **Step 3: Implement the raw publish path**

Normalize before opening mutations. Reuse `_account`, `_utc`, `_snapshot`, tenant context and existing exact-snapshot lookup. The new method must:

```python
evidence = normalize_raw_advertising(period, bundle)
existing = self.session.scalar(
    select(WbAdvertisingSyncRunRow).where(
        WbAdvertisingSyncRunRow.organization_id == self.organization_id,
        WbAdvertisingSyncRunRow.marketplace_account_id == marketplace_account_id,
        WbAdvertisingSyncRunRow.source_kind == "ads_fullstats",
        WbAdvertisingSyncRunRow.date_from == period.date_from,
        WbAdvertisingSyncRunRow.date_to == period.date_to,
        WbAdvertisingSyncRunRow.snapshot_checksum == evidence.snapshot_checksum,
        WbAdvertisingSyncRunRow.is_materialized.is_(True),
    )
)
```

- On replay, update only `last_observed_at` and return the same run.
- On change, select the latest published raw exact-period run as `parent_sync_run_id`.
- Insert the run as `formula_version='wb-advertising-raw-v1'`, `evidence_status='raw'`, `is_materialized=False`, with fact/campaign/document counts and both source totals.
- Flush the run before child rows.
- Insert facts, campaign snapshots and spend documents from immutable dataclasses.
- Verify stored counts and verify only `fact_scope='campaign' AND grain='period'` sums to `source_total_spend_kopecks`; never sum every hierarchy level.
- Set `is_materialized=True` only after all checks, then commit once. Roll back the entire run and children on any exception.

Update legacy `_ingest` to populate `grain`, `date_from`, `date_to`, and `fact_scope` for its 0057 facts. Do not alter its checksum, evidence status, selector precedence or P&L behavior.

- [x] **Step 4: Verify GREEN and legacy invariants**

Run: `.venv/bin/python -m pytest -q tests/test_advertising_raw_service.py tests/test_advertising_service.py tests/test_advertising_backfill.py tests/test_advertising_shadow_bridge.py tests/test_abc_pnl_service.py`

Expected: all selected tests pass; existing P&L still selects only non-zero `finance_promotion` and never adds raw/fullstats totals.

- [x] **Step 5: Commit Task 3**

```bash
git add app/platform/advertising/service.py tests/test_advertising_raw_service.py
git commit -m "feat: publish raw advertising snapshots"
```

---

### Task 4: Fetch a Complete Raw Bundle Through the Existing Adapter

**Files:**
- Create: `app/wb_api/raw_advertising.py`
- Create: `tests/test_advertising_raw_fetch.py`

**Interfaces:**
- Consumes: `Period`, `RateLimitedWbApiClient`, `WbApiRequest`, `build_wb_ads_client`.
- Produces: `fetch_raw_advertising(period: Period, *, wb_token: str, scenario: str = "complete") -> RawAdvertisingFetch`.

```python
@dataclass(frozen=True, slots=True)
class RawAdvertisingFetch:
    state: Literal["ready", "partial"]
    bundle: dict[str, Any]
    expected_requests: int
    completed_requests: int
    failure_codes: tuple[str, ...]
```

- [x] **Step 1: Write failing request-plan tests**

The breaks are requesting unsupported statuses, sending more than 50 IDs, producing overlapping 31-day windows, or calling the service with a failed page.

```python
def test_raw_fetch_batches_campaigns_and_windows(monkeypatch):
    campaign_ids = list(range(1000, 1051))
    fake = QueryAwareAdsClient(campaign_ids=campaign_ids)
    monkeypatch.setattr(raw_module, "build_wb_ads_client", lambda *_a, **_k: fake)
    result = fetch_raw_advertising(Period(date(2026, 6, 2), date(2026, 7, 4)), wb_token="token")
    assert result.state == "ready"
    fullstats = [request for request in fake.requests if request.path == "/adv/v3/fullstats"]
    assert len(fullstats) == 4
    assert [len(request.query["ids"].split(",")) for request in fullstats] == [50, 50, 1, 1]
    assert {(request.query["beginDate"], request.query["endDate"]) for request in fullstats} == {
        ("2026-06-02", "2026-07-02"),
        ("2026-07-03", "2026-07-04"),
    }


def test_raw_fetch_marks_any_failed_request_partial(monkeypatch):
    fake = QueryAwareAdsClient(campaign_ids=[1001], failing_path="/adv/v3/fullstats")
    monkeypatch.setattr(raw_module, "build_wb_ads_client", lambda *_a, **_k: fake)
    result = fetch_raw_advertising(PERIOD, wb_token="token")
    assert result.state == "partial"
    assert result.completed_requests < result.expected_requests
    assert result.failure_codes == ("rate_limited",)
```

- [x] **Step 2: Run fetch tests and verify RED**

Run: `.venv/bin/python -m pytest -q tests/test_advertising_raw_fetch.py`

Expected: collection fails because `app.wb_api.raw_advertising` is absent.

- [x] **Step 3: Implement the deterministic read plan**

Request in this order:

1. `GET /adv/v1/promotion/count`.
2. One `GET /adv/v1/upd` per non-overlapping 31-day window.
3. `GET /api/advert/v2/adverts?statuses=7,9,11`.
4. One `GET /adv/v3/fullstats` per union-ID chunk × date window.

Campaign IDs are the union of promotion groups in statuses `{7, 9, 11}` and positive `advertId` values in successful UPD pages. Each manifest item contains endpoint, request query, status code, `ok`, WB request ID and a checksum of the response data; error messages and tokens are excluded.

Use one attempt per request. A non-2xx response records its stable adapter error code and yields `state='partial'`; it is never split, skipped or published. The existing limiter performs the required waits. An empty, fully successful cabinet yields a ready empty bundle.

```python
def fetch_raw_advertising(period: Period, *, wb_token: str, scenario: str = "complete") -> RawAdvertisingFetch:
    if not wb_token.strip():
        raise ValueError("WB token is required")
    client = RateLimitedWbApiClient(
        inner=build_wb_ads_client(scenario=scenario, token_override=wb_token)
    )
    return _execute_plan(client, period)
```

- [x] **Step 4: Verify GREEN and existing adapter behavior**

Run: `.venv/bin/python -m pytest -q tests/test_advertising_raw_fetch.py tests/test_wb_ads_runtime.py tests/test_wb_rate_limiter.py tests/test_wb_real_client.py`

Expected: all selected tests pass without sleeping because fake clients use injected no-op waits.

- [x] **Step 5: Commit Task 4**

```bash
git add app/wb_api/raw_advertising.py tests/test_advertising_raw_fetch.py
git commit -m "feat: fetch complete raw advertising bundles"
```

---

### Task 5: Add an Explicit Shadow Backfill Command

**Files:**
- Create: `app/platform/advertising/raw_backfill.py`
- Modify: `tests/test_advertising_raw_service.py`

**Interfaces:**
- Consumes: organization secret lookup, one connected WB account, `fetch_raw_advertising`, and `AdvertisingService.ingest_raw_payload`.
- Produces: `backfill_raw_advertising(organization_id: int, period: Period, *, wb_token: str | None = None, session: Session | None = None) -> dict[str, Any]` and `python -m app.platform.advertising.raw_backfill`.

- [x] **Step 1: Write failing orchestration tests**

The breaks are writing a partial fetch, choosing between multiple connected WB accounts, or emitting raw data/secrets in CLI output.

```python
def test_raw_backfill_never_publishes_partial_fetch(session, monkeypatch):
    monkeypatch.setattr(backfill_module, "fetch_raw_advertising", lambda *_a, **_k: RawAdvertisingFetch("partial", {}, 4, 3, ("rate_limited",)))
    result = backfill_raw_advertising(1, PERIOD, wb_token="secret", session=session)
    assert result == {"state": "partial", "expectedRequests": 4, "completedRequests": 3, "failureCodes": ["rate_limited"]}
    assert session.scalar(select(func.count()).select_from(WbAdvertisingSyncRunRow)) == 0
```

Add a ready-path test asserting the returned keys are only state, run/checksum, counts, both totals and request counts. Add account-missing and account-ambiguous tests.

- [x] **Step 2: Run the orchestration test and verify RED**

Run: `.venv/bin/python -m pytest -q tests/test_advertising_raw_service.py -k backfill`

Expected: import or symbol failure for `raw_backfill`.

- [x] **Step 3: Implement minimal CLI orchestration**

Resolve a supplied token first, otherwise `get_organization_wb_token_secret(organization_id)`. Validate exactly one connected `marketplace='wb'` account under tenant context. Fetch first; call the service only when `state == 'ready'`.

```python
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Backfill raw canonical WB advertising")
    parser.add_argument("--organization-id", type=int, required=True)
    parser.add_argument("--date-from", type=date.fromisoformat, required=True)
    parser.add_argument("--date-to", type=date.fromisoformat, required=True)
    args = parser.parse_args(argv)
    result = backfill_raw_advertising(
        args.organization_id,
        Period(args.date_from, args.date_to),
    )
    print(json.dumps(result, sort_keys=True))
    return 0 if result["state"] == "ready" else 1
```

Do not register a Celery task, scheduler source, route or config flag in this slice.

- [x] **Step 4: Verify GREEN and secret-safe output**

Run: `.venv/bin/python -m pytest -q tests/test_advertising_raw_service.py`

Run: `.venv/bin/python -m app.platform.advertising.raw_backfill --help`

Expected: tests pass; help exits 0; no token/raw-payload field exists in result models.

- [x] **Step 5: Commit Task 5**

```bash
git add app/platform/advertising/raw_backfill.py tests/test_advertising_raw_service.py
git commit -m "feat: add raw advertising shadow backfill"
```

---

### Task 6: Verify the Slice and Rehearse Migration/Rollback

**Files:**
- Modify only files required by failures proven during this task.

**Interfaces:**
- Consumes: Tasks 1–5.
- Produces: a release candidate with exact regression and migration evidence.

- [x] **Step 1: Run static and targeted checks**

```bash
.venv/bin/python -m compileall -q app tests
.venv/bin/python -m pytest -q \
  tests/test_advertising_raw_normalization.py \
  tests/test_advertising_raw_fetch.py \
  tests/test_advertising_raw_service.py \
  tests/test_advertising_migration.py \
  tests/test_advertising_service.py \
  tests/test_advertising_backfill.py \
  tests/test_advertising_shadow_bridge.py \
  tests/test_abc_pnl_service.py \
  tests/test_wb_ads_runtime.py
git diff --check
```

Expected: all selected tests pass and no whitespace errors exist.

- [x] **Step 2: Run the exact full baseline comparison**

```bash
.venv/bin/python -m pytest -q --tb=no tests backend_contracts/tests
```

Expected: every new test passes and the legacy failure-ID set is exactly the known 105 baseline failures; no collection error and no new failure ID is allowed.

- [x] **Step 3: Rehearse 0057 → 0058 → 0057 → 0058 on a production clone**

Create an isolated PostgreSQL clone from the scoped production schema/rows. Verify before upgrade that current counts/checksums match the source. Then:

```bash
alembic upgrade 20260903_0058
alembic downgrade 20260903_0057
alembic upgrade 20260903_0058
```

Assert existing run/fact counts and sums are unchanged, legacy facts received deterministic grain/date/scope, the two new tables are empty, all four advertising tables have RLS enabled+forced, and tenant policies have both `USING` and `WITH CHECK`.

- [x] **Step 4: Perform a diff-focused self-review**

Review every changed caller and mutation path. Specifically verify no report reader selects raw fullstats, no request can exceed WB limits, no manifest error can reach `ingest_raw_payload`, all external IDs are account-scoped, and raw source totals never sum campaign + SKU scopes.

- [x] **Step 5: Commit only proven review fixes**

```bash
git add app/platform/advertising/raw.py app/platform/advertising/orm.py app/platform/advertising/service.py app/platform/advertising/raw_backfill.py app/wb_api/raw_advertising.py alembic/versions/20260903_0058_raw_advertising_evidence.py tests/test_advertising_raw_normalization.py tests/test_advertising_raw_fetch.py tests/test_advertising_raw_service.py tests/test_advertising_migration.py
git commit -m "fix: harden raw advertising evidence"
```

Skip this commit when review finds no required change.

---

### Task 7: Deploy the Inactive Path, Run a Tenant Canary, and Update Handoff

**Files:**
- Modify: `SATORNA_ARCHITECTURE_HANDOFF.md` outside backend Git after evidence is collected.

**Interfaces:**
- Consumes: verified release candidate and production SSH alias `satorna-api`.
- Produces: revision 0058 deployed, one bounded org-2 raw canary, tested idempotency/RLS/rollback, and an updated architecture percentage.

- [x] **Step 1: Create recoverable production backup and rollback tags**

Back up exact 0057 advertising tables, Alembic version, production env and source files changed by this release into a timestamped directory under `/var/backups`. Record SHA-256 checksums. Tag the current API/worker/beat/migrate images with explicit pre-release rollback tags; verify their common digest and revision label.

- [x] **Step 2: Build and start one immutable release**

Transfer only committed source via an isolated release directory, build API/worker/beat/migrate images with the new commit label, run migrate to 0058, then replace services. Do not overlay the dirty production checkout and do not prune unrelated images.

- [x] **Step 3: Verify platform health before the canary**

Check image digests/labels, Alembic 0058, external `/health/live`, `/health/ready`, legacy `/health`, Celery pong, restart counts and fresh API/worker/beat logs. Any failed gate triggers the documented image/schema rollback.

- [x] **Step 4: Run a one-day org-2 raw canary twice**

```bash
docker exec vella-api python -m app.platform.advertising.raw_backfill \
  --organization-id 2 \
  --date-from 2026-09-02 \
  --date-to 2026-09-02
```

The first run must return `ready` and persist one raw run; the second must return the same run ID with identical child counts and a later observation time. If the full cabinet requires more than one WB rate-limit window, allow the typed limiter to complete; do not reduce campaign coverage.

- [x] **Step 5: Verify DB invariants and tenant isolation**

Assert raw run counts match all three child counts, period-campaign spend equals the stored fullstats total, UPD lines sum to the separately stored document total, composite UPD identities are unique per run, and no exact payload is duplicated. Under no tenant and org 1, org-2 rows must read as zero; an org-1 cross-tenant insert must fail with SQLSTATE `42501` and persist nothing.

- [x] **Step 6: Recheck unchanged consumers and performance**

Call authenticated retained/custom/7-day/30-day ABC/P&L endpoints and confirm formula/source/blockers match the pre-release contract. Measure at least 25 retained calls; p95 must remain at or below 500 ms. Confirm raw runs are absent from the selected P&L source.

- [x] **Step 7: Update handoff and commit rollout evidence**

Record commit/digest, Alembic 0058, backup path, rollback tags, canary run/count/checksum invariants, RLS result, health/performance, full-suite baseline comparison, current branch, next slice and an evidence-based completion percentage. Keep the root handoff outside backend Git; commit any backend plan status update separately.

## Rollout evidence — 2026-09-04

- Final immutable release `d6ad0b0` is deployed from `/var/tmp/satorna-raw-advertising-d6ad0b0`; API, worker, beat and migrate share image `sha256:009a8fd34bb5a451b77f436bcfef80d2978a438cecdaea95a60cccf091dc2cb6`. Migrate exited `0`, production is at `20260903_0058`, health endpoints return `200`, Celery returns `pong`, queues are empty and restart counts are zero.
- Backup `/var/backups/satorna-raw-advertising-pre-0058-20260903T220731Z/` and every listed release archive pass `sha256sum -c`; sensitive files and release archives are mode `0600`. Immediate rollback `rollback-81a22ed-pre-d6ad0b0` points to `sha256:6cf785e01e92575c75d723ba96df5e3f301eac9cfadd54131eb004b28034325a`; `rollback-f5dddb0-pre-81a22ed` remains available at `sha256:ef4c658d22ce5093309369e7a0fe58d165f545be98324dd204f338e6c65f3258`.
- The final one-day org-2 canary and replay both returned run `bbce1497-feb1-4497-b270-6bd50762ca15`, snapshot `cf233b3101fbe0ce277212d57856ca6e0ce82bdd04781902c6a4a3fdaac1bc9f`, manifest `16/16`, `138` facts, `636` campaign snapshots, `0` spend documents and `2,282` source kopecks. Replay advanced `last_observed_at` from the captured observation without creating a new run; per-run identity duplicates are `0/0/0` and the manifest contains no secret-like key.
- Two earlier canary observations produced distinct snapshots solely because source discovery order changed the 50-ID request partitions. They are preserved as append-only diagnostic audit. `d6ad0b0` sorts the `636`-ID union before producing deterministic `12×50 + 36` batches; the paired regression checks both request chunks and snapshot checksum.
- Production proved the only hierarchy excess was exactly `0.01 RUB` for a money `sum`. The normalizer allows that source-level money tolerance only; both money fields reject `0.0101` and all integer metrics remain exact.
- Runtime-role RLS probe: no tenant and org `1` see `0/0/0/0`; cross-tenant insert fails with SQLSTATE `42501` and persists nothing. All four tables have enabled/forced RLS with tenant `ALL` policies.
- ABC/P&L remains cache-only and unchanged: retained evidence is `finance_promotion/aggregate_only`, spend/unattributed is `981,000/981,000`, and raw evidence is not selected. Production p95 over 25 requests per case is `254.96 ms` retained, `23.75 ms` 7-day, `19.87 ms` 30-day and `101.40 ms` custom, all below `500 ms`.
- Final verification is `591 passed / 105 known baseline failures / 0 errors / 26 warnings` in `265.89 s`; the failure-ID comparison is exact, raw-advertising targeted tests are `115 passed`, compileall, one-head, whitespace and Git object checks pass.
