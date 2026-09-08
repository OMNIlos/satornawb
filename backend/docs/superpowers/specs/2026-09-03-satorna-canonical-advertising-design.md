# Satorna Canonical WB Advertising Design

**Date:** 2026-09-03  
**Status:** approved by the existing platform architecture handoff and the autonomous-continuation directive

## Goal

Persist the advertising amounts already fetched by the WB sync as immutable,
tenant/account-owned evidence and use only a proven exact-period subtotal in the
canonical ABC/P&L. This slice does not close loyalty, derive final net profit, or
change the frontend.

## Observed production boundary

Production has one connected WB account: organization `2`, marketplace account
`2`. The legacy advertising storage is not canonical:

- `wb_ads_report_cache` has `300` mutable organization-only period rows;
- `wb_ads_fullstats_daily_rows` has `2,641,006` rows from `1,288` observations,
  including repeated snapshots, no account ownership, and `2,274,224` rows with
  no campaign id;
- `wb_ads_spend_documents` has `32,828` rows but only `3,109` distinct legacy
  document/campaign/amount identities;
- none of these tables has forced RLS or atomic snapshot publication.

The active sync already obtains two advertising sources with different
semantics:

1. `finance_promotion`: settlement deductions whose `bonusTypeName` contains
   `WB Продвижение`. This is authoritative for P&L when its signed total is
   non-zero. Raw rows may have no `nmId`; such spend is not allocated.
2. `ads_fullstats`: operational campaign statistics collapsed by the legacy
   sync. Production-shaped replay proves that the current recursive parser can
   visit both campaign-day and top-level SKU branches and double spend. These
   snapshots are retained as `derived_legacy` diagnostics and are never a P&L
   source.

For retained `2026-08-17..2026-08-23` evidence, finance promotion totals
`981,000` kopecks while fullstats totals `111,076` kopecks. They must not be
added or treated as interchangeable. Fullstats aggregate, daily and declared
totals each equal `111,076` exactly. The retained finance cache no longer has
raw rows, so its `981,000`-kopeck backfill is one explicit aggregate-only,
unattributed fact; the old heuristic SKU distribution is rejected.

## Chosen approach

Add two tables and one application service. Each source-period observation is
an immutable sync run. Its facts are inserted while the run is unpublished;
the run becomes visible only after fact count and signed source total reconcile
with zero tolerance. A repeated identical checksum updates only
`last_observed_at` and inserts no facts.

This is preferred over expanding the current WB call graph or retrofitting the
legacy caches. It reuses the existing scheduler, `Period`, marketplace account
ownership and transaction-local tenant context. No generic event framework,
new queue, application response cache or dependency is introduced.

## Canonical model

### `wb_advertising_sync_runs`

- `sync_run_id` UUID text primary key;
- `organization_id`, `marketplace_account_id` with a composite account FK;
- `source_kind`: `finance_promotion | ads_fullstats`;
- inclusive `date_from`, `date_to` in `Europe/Moscow`;
- `source_reference`, `snapshot_checksum`, `formula_version`;
- signed `source_total_spend_kopecks`, `fact_count`;
- `evidence_status`: `raw | aggregate_only | derived_legacy`;
- `is_materialized`, `captured_at`, `last_observed_at`, `created_at`.

The unique observation key is organization, account, source kind, period and
snapshot checksum. Covering-period fallback is intentionally absent: ABC/P&L
uses an exact source snapshot or reports it missing.

### `wb_advertising_facts`

- deterministic `advertising_fact_id` primary key;
- composite tenant/account/run ownership FK;
- `source_identity` and `payload_checksum`;
- nullable Moscow `business_date`, `campaign_id`, and `nm_id`;
- `attribution_level`: `exact_sku | campaign_sku | campaign_only | unknown`;
- signed `spend_kopecks`; non-negative impressions, clicks, cart adds, order
  count and order revenue where the source supplies them.

`campaign_only`, `unknown`, weak `campaign_sku`, missing `nmId`, and retained
aggregate-only finance spend are never distributed to products. Both tables
have `ENABLE` and `FORCE ROW LEVEL SECURITY` with the established
`app.organization_id` policy.

## Ingestion and precedence

The existing sync remains the only producer:

```text
WB fetch
  -> legacy cache write
  -> canonical shadow ingest for the same in-memory payload
  -> exact reconciliation
  -> atomic materialization
```

The bridge is enabled only for configured organization ids. It resolves
exactly one connected WB marketplace account; zero or multiple accounts return
an explicit non-ready result and write nothing. A failure after the legacy
write is repairable by retry because checksum ingestion is idempotent.

For finance payloads, raw promotion rows are normalized without using the
legacy global-cost allocator. Signed deduction corrections are retained. For
legacy backfill, only the exact source total is retained and marked
`aggregate_only`. Fullstats ingestion checks that the collapsed payload is
internally self-consistent, but that does not upgrade it to raw evidence.

P&L source selection for one exact period is deterministic:

1. non-zero materialized `finance_promotion` run;
2. otherwise `missing` (`future` for a future period).

No values from the two sources are added together.

## ABC/P&L contract

The existing `/api/v2/wb/reports/abc-pnl` stays authenticated, account scoped,
paginated and cache-only. Formula version becomes
`wb-abc-pnl-advertising-v1`. It adds:

- row: `advertisingSpendKopecks`, `profitBeforeLoyaltyKopecks`;
- summary: `advertisingSpendKopecks`,
  `unattributedAdvertisingSpendKopecks`, `profitBeforeLoyaltyKopecks`;
- meta: selected advertising source, checksum and evidence status.

An exact attributed finance-promotion absence for a finance SKU is `0`, not missing.
Advertising-only exact SKU facts join the report union with zero finance
amounts. If authoritative spend is unattributed, the summary subtracts the
proven total but row profit remains `null`. If advertising is missing, all new
profit values remain `null` and a source blocker is present.

This bounded ledger is the safe P&L-promotion slice, not the final advertising
domain. Raw campaign/funnel facts and UPD reconciliation follow the six-table
design in `2026-09-03-wb-funnel-advertising-canonical-design.md`.

`netProfitKopecks`, `profitClass` and `abcCode` remain `null`; only
`WB_PNL_LOYALTY_NOT_CANONICAL` remains global after an advertising source is
ready. Cost/economics blockers continue to propagate unchanged.

## Backfill and rollout

Backfill is explicit by organization and exact date range. The first production
backfill is limited to retained organization `2`, account `2`,
`2026-08-17..2026-08-23`; it performs no WB calls and does not rewrite legacy
data. A second identical run must insert zero rows.

Production discovery found `alembic_version=20260903_0056` while the deployed
image ends at `0055` and no advertising tables exist. Revision `0056` is
therefore reserved as a compatibility no-op; the advertising schema is `0057`.
This advances both the externally stamped production schema and clean databases
without rewriting production history.

Release gates:

- migration contract, composite ownership and forced-RLS tests;
- normalization tests for signed finance promotion, missing product identity,
  fullstats daily reconciliation and repeated ingestion;
- cross-tenant read/write probes under `satorna_runtime`;
- exact source-total and ABC summary parity with zero tolerance;
- unchanged legacy failure-id set and contract checks;
- authenticated ABC/P&L p95 at most `500 ms`;
- scoped backup, production-schema migration rehearsal, one-image canary,
  health/Celery/zero-restart checks and immediate rollback tags.

## Explicitly excluded

- additional WB API calls or campaign enrichment;
- treating collapsed legacy fullstats as canonical P&L evidence;
- heuristic allocation of campaign/aggregate spend;
- loyalty/cashback canonicalization and final profit classification;
- frontend cutover, legacy-cache deletion, generic reporting infrastructure;
- fixes for the pre-existing empty-chain `0019` defect or the 105 legacy test
  failures.
