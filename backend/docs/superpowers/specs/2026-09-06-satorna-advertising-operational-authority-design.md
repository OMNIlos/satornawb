# Satorna Advertising Operational Authority Design

**Date:** 2026-09-06
**Status:** approved in chat; ready for implementation planning

## Decision

Canonical ABC/P&L uses exact-period raw WB fullstats as the authority for
operational advertising expense by activity date. Finance promotion deductions
and UPD documents remain settlement evidence used for reconciliation; they are
never added to, substituted for, or allocated into the operational expense.

This deliberately defines an accrual/operational view, not a cash-settlement
view. WB describes fullstats as campaign statistics and UPD as factual campaign
cost documents in its [Promotion API](https://dev.wildberries.ru/openapi/promotion).

## Goal

Replace the current finance-promotion P&L selection with the already persisted,
account-scoped raw fullstats hierarchy. Publish advertising and pre-loyalty
profit only when exact evidence and SKU attribution are complete. Preserve
unknown values as unknown and keep final profit classification outside this
slice.

## Existing components to reuse

- `AdvertisingService.get_raw_reconciliation()` already selects the latest
  materialized `ads_fullstats/raw` run for one exact organization, marketplace
  account and period.
- The raw run already contains campaign-period facts, source-SKU facts, request
  completeness, immutable checksums, UPD documents and forced-RLS ownership.
- Existing reconciliation calculates campaign-only residuals, enforces exact
  integer hierarchies, permits only a one-kopeck money discrepancy and resolves
  WB `nmId` values through `CatalogService`.
- `AdvertisingPnlSource` and `WbAbcPnlService` already form the cache-only
  boundary consumed by `/api/v2/wb/reports/abc-pnl`.

No new table, migration, endpoint, dependency, configuration, scheduler task,
queue, cache or frontend contract is required.

## Authority contract

An operational advertising total is authoritative only when all of the
following hold:

1. The requested period is not future or currently open.
2. A materialized `ads_fullstats` run with `evidence_status=raw` exists for the
   exact period and account.
3. `expected_request_count == completed_request_count`.
4. Campaign-period and source-SKU spend values are present.
5. Every campaign spend hierarchy reconciles within one kopeck.

Row attribution is complete only when, in addition, every source `nmId`
carrying spend maps to exactly one canonical catalog SKU for the same
organization and marketplace account and no campaign-only residual remains.

A complete raw run with no facts and no documents is authoritative zero and
returns `state=empty`. Covering-window fallback, period stitching and derived
legacy fullstats are forbidden.

Engagement fields such as impressions, clicks, carts and orders remain
diagnostic. Their absence or hierarchy mismatch does not invalidate a fully
reconciled spend hierarchy. UPD absence or mismatch also does not invalidate
operational spend because UPD belongs to the settlement view.

## Money and attribution flow

For each campaign interval:

```text
source spend = sum(source-SKU spend)
difference   = campaign spend - source spend
```

- `difference >= 0`: campaign-only residual equals `difference`.
- `difference == -1 kopeck`: accept proven WB rounding, use residual `0`, and
  retain `WB_ADS_HIERARCHY_TOLERANCE_APPLIED`.
- `difference < -1 kopeck`: reject the source for P&L with
  `WB_ADS_HIERARCHY_RECONCILIATION_FAILED`.

The effective operational total is:

```text
sum(source-SKU spend) + sum(non-negative campaign-only residual)
```

Consequently, if source detail exceeds campaign totals by the permitted single
kopeck, the effective total follows the detail. The observed production case
`campaign=2,282`, `source-SKU=2,283` therefore publishes `2,283` kopecks with an
explicit rounding diagnostic. This preserves the invariant:

```text
sum(row advertising spend) + unattributed advertising spend
    == summary advertising spend
```

`spend_by_nm` contains only source-SKU spend with an unambiguous catalog
mapping. `unattributed_spend_kopecks` is the effective total minus mapped
source-SKU spend, so it includes campaign-only residual and spend with missing
or ambiguous catalog mapping. It is never distributed across campaign members.
No penny allocator or heuristic fallback is introduced.

P&L validity is decided from the spend fields themselves, not from the generic
set of reconciliation diagnostics. This keeps a clicks or impressions mismatch
diagnostic without accidentally invalidating an otherwise valid spend total.

## Failure behavior

`AdvertisingPnlSource` owns advertising-specific blockers so ABC/P&L does not
reimplement reconciliation rules.

| Condition | Source result | Consumer behavior |
| --- | --- | --- |
| Future period | `future`, no snapshot | Advertising and dependent profit remain `null` |
| Open period | `partial`, no authoritative values | Advertising and dependent profit remain `null` |
| Exact raw evidence missing/incomplete | `missing` or `partial` | `WB_PNL_ADS_NOT_CANONICAL` |
| Spend missing or hierarchy exceeds tolerance | `partial`, evidence retained | No row advertising/profit publication; reconciliation blocker propagated |
| Missing or ambiguous product mapping | Money source `ready`, attribution incomplete | Summary total/unattributed are known; every row advertising/profit field remains `null` |
| Valid source with campaign-only residual | Money source `ready`, attribution incomplete | Summary total/unattributed are known; every row advertising/profit field remains `null` |
| Valid, fully attributed source | `ready` | Row and summary advertising/profit may be calculated |
| Complete empty source | `empty` | Confirmed advertising zero |

Raw reconciliation stops emitting
`WB_ADS_ACCOUNTING_AUTHORITY_UNRESOLVED`: this decision resolves that shadow
blocker. Settlement diagnostics such as `WB_ADS_DOCUMENT_SCOPE_UNKNOWN` remain
visible but do not block the operational source.

## ABC/P&L contract

The authenticated, account-scoped and paginated endpoint remains cache-only.
Its formula version becomes `wb-abc-pnl-fullstats-loyalty-v1`; advertising meta
reports `source=ads_fullstats`, the raw evidence status and snapshot checksum.

The current `finance_promotion` evidence remains queryable in canonical storage
but is no longer selected by `get_pnl_source()`. A non-zero finance-promotion
subtotal cannot override or supplement raw fullstats. This intentionally means
that a period containing only settlement evidence returns advertising missing
in the operational report.

When advertising is fully attributed and finance, costs, economics and loyalty
are complete:

- row and summary `advertisingSpendKopecks` are populated;
- `profitBeforeLoyaltyKopecks` and `profitAfterLoyaltyKopecks` are populated;
- `netProfitKopecks`, `profitClass` and `abcCode` remain `null`;
- `WB_PNL_CLASSIFICATION_NOT_CANONICAL` explicitly explains those final nulls,
  so the page remains `partial`.

Final profit naming and classification rules are a separate business decision
and the next independent architecture slice. The former advertising-authority
blocker must not be reused to represent that missing decision.

## Verification

Implementation begins with failing tests and covers:

- exact raw selection and rejection of wider, derived, unpublished and partial
  snapshots;
- complete empty snapshot as confirmed zero;
- exact reconciliation, one-kopeck acceptance and greater-than-one-kopeck
  rejection;
- effective-total invariant for both ordinary and tolerated hierarchies;
- campaign-only residual without allocation;
- missing and ambiguous catalog mappings;
- engagement and UPD diagnostics not blocking valid spend;
- finance promotion and UPD never selected or summed;
- formula, evidence metadata and explicit classification blocker;
- cross-tenant isolation and no external WB call from the report path.

The release gate is the existing targeted advertising/ABC suite, compile and
diff checks, the exact known full-suite failure set, then an immutable-image
production rollout. A closed-day organization-2 canary must prove source kind,
checksum, row/summary arithmetic, blockers, p95 below `500 ms`, healthy API and
workers, zero restarts and unchanged scheduler disablement. Rollback uses the
previous image and source archive; this slice has no schema rollback.

## Explicitly excluded

- cash-settlement P&L or reconciliation thresholds between fullstats and UPD;
- heuristic SKU allocation, historical reconstruction or covering-period
  fallback;
- changes to collectors, raw publication, scheduler cadence or account locks;
- final net-profit formula, profit classes and ABC classification;
- frontend cutover, legacy cache cleanup or unrelated baseline repairs.
