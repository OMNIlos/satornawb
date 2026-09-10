# T2 → T1: bounded operational orders history storage

Status: implementation request, not persistence acceptance. T1 owns DDL,
repository and authority. T2 owns transport/orchestration. Root owns registration
and the combined PostgreSQL gate. No real provider execution is authorized.

## Existing committed adapter and facts

`b5aa69d136d49d48f4d78f167e0e0481161330f9`:
`backend/app/wb_live/statistics_orders.py` and
`backend/tests/test_wb_live_statistics_orders.py` (35 focused tests passed).

Reuse `app.orders.ingestion.OrderObservation`,
`app.orders.serialization.serialize_observation` / `observation_checksum`,
existing order evidence/projection services and exact account ownership.
Do not create a parallel order domain or feed an entire history into
`OrderManifest`: that interface materializes all observations.

Source identity: `wb-statistics-supplier-orders`. Existing live sources
`content` / `prices` remain unchanged. This source is preliminary operational
history, not all orders, fulfillment readiness, settlement or final profit.

Official rules checked 2026-09-10:
<https://dev.wildberries.ru/docs/openapi/reports> (supplier/orders).
GET `/api/v1/supplier/orders`, query `dateFrom=<exact native value>&flag=0`.
No invented `dateTo`, offset, limit or timestamp increment. Only EMPTY is
terminal; roughly 80,000 rows is not a terminal condition. Cursor moves to the
last native `lastChangeDate`, inclusively. Same/nonadvancing cursor is a visible
blocker, never a guessed skip. Retention is 90 days; unpaid orders may be absent.
Unknown/base token interval is 10,800 seconds; no worker sleeps or JWT entitlement
inference. All source calls, including crash retries, share a persisted quota.

## Exact adapter output

`iter_orders_page(chunks, organization_id, marketplace_account_id, date_from,
observed_at)` emits:

- `HistoryOrderRow(observation: OrderObservation, nm_id: int,
  barcode: str | None, source_row_checksum: str)`.
- Exactly one final `OrdersPageEnd(next_date_from: str, terminal: bool,
  row_count: int, raw_checksum: str, request_checksum: str)` after valid array
  closure AND transport EOF. Every hash is lowercase SHA-256 hex.

Rows preceding the end marker are provisional. Adapter exceptions or abandoned
iteration do not authorize publication. Native srid is the account-scoped order
and one-unit identity. nmId is a product, not a size. No synthetic SKU identity.
Unknown noncancelled status stays unmapped. Year0001 cancellation sentinel is
not cancellation evidence. Source-naive time means Moscow; exact wire cursor
is retained separately from normalized timestamps.

`source_row_checksum` binds original JSON object bytes. It is provenance, not
entity identity. Canonical observation checksum excludes `observed_at`; reuse
it for semantic replay. Changes only in formatting must not create new orders.
Retain the raw checksum separately; never rewrite checksums to force equality.

## Proposed repository protocol — confirm names before integration

Accepted T1/root amendment: **only methods 1–3 are implemented in this package**.
`begin_history_page` returns a string UUID. Method 3 atomically marks the staged
page as published source evidence and advances source cursor; this is NOT
canonical Orders queue publication. T3 owns the bounded canonical projector
from committed pages. Methods 4–5 below describe that deferred projection concern,
not calls T2 makes or prerequisites for the next provider page. No whole-page
ORM upsert is authorized. History initialization requires an explicit validated
account-owned `dateFrom`; no automatic now-minus90-days start policy.

Use existing guarded `BatchLease` / `JobLocator` and `WbLiveError` safe codes.
All calls are exact org/account/job/run/lease scoped; no UUID-only lookup.

1. `begin_history_page(lease, *, request_checksum) -> page_id: str`.
   Requires a fetch-phase lease; binds its exact dateFrom, actor/authority,
   account incarnation and credential generation. An abandoned unsealed attempt
   is superseded, not resumed from an invented HTTP byte/row offset.
2. `stage_history_rows(lease, *, page_id, first_ordinal, rows) -> bool`.
   Ordinals start at zero. Immutable tuple, at most 1,000 typed rows per call.
   Validate all ownership, domain values and closed serialization before insert.
   Same ordinal + same semantic/source hashes replays; differing data conflicts.
   Each local transaction ends before requesting more provider bytes.
3. `commit_history_page(lease, *, page_id, end, next_due_at) -> bool`.
   Seal EOF only after exact staged count/contiguity, stored request hash,
   cursor progression and renewed publication-authority checks. Bound raw digest
   and terminal claim to this page. If canonical projection requires multiple
   batches, seal durably as ready-to-project; do not claim source completion yet.
4. `history_page_for_publication(lease) -> page_id | None`.
   Select a previously sealed page before scheduling another fetch. Projection
   may continue without another provider request or consuming provider quota.
5. `publish_history_batch(lease, *, page_id, limit=1000, next_due_at)
   -> HistoryPublicationProgress` (T1-owned frozen metadata type).
   Required fields: `page_done: bool`, `published_rows: int` (this call).
   Guard + append canonical facts + advance bounded projection ordinal in one
   transaction. Only final publication advances native source checkpoint and
   releases the page for the next fetch. Empty sealed pages finish without rows.

If T1 can prove a bounded set-based EOF publication using existing services,
steps 4–5 can collapse into step 3; do not implement an 80k-row ORM loop while
holding account authorization locks. T1 must explicitly freeze this choice.

Existing `claim_batch`, `defer_batch`, `fail_batch`, `due_jobs` remain owners of
admission, retries and scheduling. Claim must distinguish fetch from projection
work without exposing credentials. T2 task locators contain three IDs only.
Lease120s and task hard bound100s currently apply; no implicit lease extension.
Projection calls use only short transactions and never hold a provider stream.

## Storage guarantees / schema request

- Page rows carry internal org/account composite foreign keys, job/run/page
  scope, request checksum, input cursor, EOF receipt and lifecycle state.
- Staging identity is page + ordinal; unique native srid within a page.
  Cross-page inclusive-boundary replay uses account/source/srid + semantic
  observation checksum; different source revisions remain evidence, not duplicates.
- Append-only receipts/audit bind lease, authority and published range; FORCE
  RLS and explicit worker grants. No raw token/provider exception or full raw
  provider payload is stored. Existing normalized observation schema is reused.
- Incomplete staging is never visible as published history. Published earlier
  pages may be visible with explicit partial/source coverage, never full-run ready.
- DB failure is explicit; no file/memory fallback. No deletion based on omission.
- Persist progress: fetching/staged/sealed/projecting/published counts and
  safe error, next_due, last confirmed native cursor. UI/read ownership stays T3.
- Bounds: chunks64KiB, JSON row128KiB, native response128MiB, 100k rows hard
  safety cap (over-limit is an explicit error, not truncation). Do not accumulate
  complete pages or history in application memory. Canonical batches <=1000.

## Acceptance and crash gates

Fixture-only T2 transport/orchestration first. Root-controlled actual PG gate:
two claimers; wrong org/account; revoked authority; credential replacement;
duplicate chunk; conflicting ordinal; inclusive page-boundary replay;
same-cursor blocker; DB rollback; restart after stage before EOF; after EOF
before projection; after projection chunk before ACK; after final publication
before ACK. Every path proves no additional fetch while a sealed page awaits
projection and no cursor advance from an unsealed page. External read retries
are quota-controlled; this does not authorize any price or messaging write.
