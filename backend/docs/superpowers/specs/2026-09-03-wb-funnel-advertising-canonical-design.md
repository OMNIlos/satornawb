# Canonical WB funnel and advertising facts: discovery and minimum design

**Date:** 2026-09-03
**Status:** advertising and funnel evidence amended after read-only live probes; raw storage slices approved
**Scope:** WB facts required by ABC, P&L and RNP

## 1. Decision

The minimum canonical slice is six tables:

1. `wb_funnel_sync_runs` — immutable run envelope and raw-response manifest.
2. `wb_funnel_daily` — one source observation per Moscow business day and WB `nmId`.
3. `wb_advertising_sync_runs` — immutable advertising run envelope and raw-response manifest.
4. `wb_advertising_campaign_snapshots` — campaign identity, source metadata and explicit SKU membership observed in the run.
5. `wb_advertising_facts` — hierarchical `fullstats` observations at campaign and source-SKU scope.
6. `wb_advertising_spend_documents` — UPD spend documents, kept separately from `fullstats` attribution.

This slice deliberately does **not** add a universal event model, an order-lifecycle table, a persisted attribution table, a campaign-membership table, or a new source cache. Existing canonical `Period`, `marketplace_accounts`, `marketplace_products` and finance facts remain authoritative in their domains.

The core rules are:

- `openCount` is a funnel transition/card open. It is neither advertising `clicks` nor advertising `views`.
- Funnel `buyoutCount` is an operational funnel stage. It is not a finance `redemptions` report type.
- Funnel order/buyout amounts are not finance revenue.
- A `fullstats` row containing `nmId` is confirmed source-SKU attribution. Campaign membership without a metric-bearing `nmId` is not attribution.
- Campaign totals, source-SKU children and UPD spend are parallel confirmed observations. They are reconciled, never summed together as one additive grain.
- Missing source fields stay `NULL`; they are not converted to zero.
- A partial run is evidence, not a canonical snapshot. Consumers continue on the prior published run as `stale`, or return a blocker if none exists.

## 2. Evidence boundary

The discovery used local files only. No WB, GitHub, production, cache or database calls were made.

Read and applied:

- `SATORNA_ARCHITECTURE_HANDOFF.md`;
- `SATORNA_SPEC_AUDIT.md`;
- `docs/superpowers/specs/2026-08-26-satorna-platform-rebuild-architecture-design.md` from the local canonical worktree;
- current adapters, tasks, caches, report builders, migrations, tests and fixtures under `app/`, `alembic/` and `tests/`;
- canonical period/finance implementation in the local `codex/satorna-period-finance` worktree.

The legacy inventory is based on backend commit `748888f`. The canonical ownership, `Period` and immutable SyncRun pattern were checked at local commit `1c9dd5a`, which contains the handoff baseline plus later local hardening. The unrelated modified runtime-state file in that worktree was not read as architecture evidence and was not touched.

### 2.1 Advertising evidence amendment (2026-09-03)

The advertising half was subsequently checked against the official [WB Promotion API contract](https://dev.wildberries.ru/openapi/promotion) and a read-only production probe through the existing typed adapter. The probe used one tenant, at most 10 campaign IDs for hierarchy inspection, and a 31-day UPD window. It emitted only field names, types, counts and equality/uniqueness predicates; tokens, campaign/SKU IDs, names and monetary values were not emitted or persisted.

Confirmed corrections to the initial local-only design:

- current `fullstats` leaves are under `days[].apps[].nms[]`, not `nm[]`; all observed day strings were aware UTC-midnight timestamps;
- `canceled` is present at campaign, day, app and `nms` levels;
- every observed campaign/day/app hierarchy reconciled exactly for the additive metrics;
- current `/api/advert/v2/adverts` returns `{adverts: [...]}` with campaign `id`, nested `settings`, `timestamps` and `nm_settings[].nm_id`;
- `updNum` is not a document-row identity: one live day returned 78 distinct rows sharing one `updNum`, and a 31-day sample returned 1,575 rows but only six `updNum` values;
- `(updNum, advertId, updTime)` was unique for all 1,575 sampled rows, with no exact duplicate payloads; it is the v1 account-scoped logical identity, while the remaining fields form the payload checksum;
- no negative or zero `updSum` was observed, which is insufficient evidence to forbid signed corrections.

These observations narrowed the first implementation to advertising raw storage and normalizers. Funnel tables and all consumer cutovers remained separate slices.

### 2.2 Funnel evidence amendment (2026-09-04)

The funnel half was checked against the official [WB Analytics API contract](https://dev.wildberries.ru/en/openapi/analytics) and one read-only production request through the existing typed adapter. The request covered two recent days and 20 account-owned products. It emitted only field names, types, counts and coverage predicates; tokens, product IDs, names and metric values were not emitted or persisted.

Confirmed corrections to the initial local-only design:

- canonical daily evidence comes from `POST /api/analytics/v3/sales-funnel/products/history`, not repeated one-day calls to the period aggregate `/products`;
- a request accepts 1–20 `nmIds`, at most seven recent inclusive days and `aggregationLevel='day'`; the account limit is three requests per minute with a 20-second interval;
- the live adapter response was the exact `{data: [...]}` wrapper; the official response example is a bare list, so v1 accepts only those two exact shapes;
- every sampled product had one row for each requested day, with no duplicate `(nmId, date)` identity;
- the returned base fields were `openCount`, `cartCount`, `orderCount`, `orderSum`, `buyoutCount`, `buyoutSum` and `addToWishlistCount`, plus product-level currency;
- all sampled base values were integers, including explicit zeros; no impression, cancellation or return field was present;
- an omitted field or product/date row remains a missing observation. The implementation does not infer zero from source silence.

This evidence approves only recent raw daily funnel storage and a manual backfill boundary. It does not approve a scheduler, report consumer switch, organic-traffic subtraction or long-range CSV ingestion.

## 3. Domain vocabulary

| Canonical term | Confirmed source meaning | Must not be substituted with |
|---|---|---|
| `funnel_open_count` | `selected.openCount` from Sales Funnel; current UI often labels it as card transitions/clicks | ad clicks or impressions |
| `funnel_cart_count` | `selected.cartCount` | ad `atbs` |
| `funnel_order_count` / `funnel_order_amount_kopecks` | operational orders and order amount from Sales Funnel | sales, buyouts or finance revenue |
| `funnel_buyout_count` / `funnel_buyout_amount_kopecks` | operational buyout stage from Sales Funnel | canonical finance sale/redemption |
| `funnel_add_to_wishlist_count` | `addToWishlistCount` from Sales Funnel history | baskets, orders or an inferred engagement count |
| `ad_impression_count` | `views` from advertising `fullstats` | funnel views/opens |
| `ad_click_count` | `clicks` from advertising `fullstats` | funnel `openCount` |
| `ad_order_count` / `ad_order_amount_kopecks` | source-attributed advertising orders and `sum_price` | total funnel orders or finance revenue |
| `ad_spend_kopecks` | `sum` from `fullstats`, or `updSum` in a separate UPD fact | finance deduction without reconciliation |
| `finance_return` | canonical finance operation with return semantics | funnel cancellation |

## 4. Source matrix

### 4.1 Funnel and lifecycle-adjacent sources

| Flow | Endpoint and current adapter | Source grain and identity | Period, pagination and retry | Current persistence/state | Canonical decision and blockers |
|---|---|---|---|---|---|
| Funnel period aggregate | `POST /api/analytics/v3/sales-funnel/products`; `app/repricer_bff.py::fetch_baskets_aggregates` | Selected period × `nmId`; no external row ID. Stable logical identity is account + selected period + `nmId`. | App accepts 1–90 inclusive dates. Full-catalog path uses `limit=1000`, `offset`; explicit `nmIds` are batched by 1000 and stop after one response per batch. Analytics policy is 3/min with ~22 s interval. Adapter retries up to 5; `Retry-After > 180 s` becomes deferred. | Mutable org-only key `baskets_{N}` or `baskets_{YYYY-MM-DD}_{YYYY-MM-DD}`. Aggregate refresh can preserve old daily detail. Each write refreshes `fetchedAt`. | Keep the period aggregate only as raw/reconciliation evidence. It cannot be decomposed into daily facts. `nmId` duplicates with identical payload collapse; conflicting duplicates block the run. Missing rows are not inferred as zero activity. |
| Funnel daily | `POST /api/analytics/v3/sales-funnel/products/history`; canonical raw adapter is introduced separately from legacy `fetch_baskets_daily_detail` | Returned `history[].date` × `product.nmId`; canonical identity is account + source date + `nmId`. | One request covers at most seven inclusive recent days and 20 sorted unique `nmIds`; no pagination. Analytics policy is 3/min with a 20-second interval. | Legacy daily detail remains inside mutable `dailyAggregates`; canonical evidence is not read by legacy consumers in this slice. | Sole input to `wb_funnel_daily`. Publish only when every planned SKU batch returns a valid successful response. Missing response rows remain absent facts rather than inferred zeros. |
| Opens/transitions, baskets, orders, buyouts and wishlist adds | `products/history` returns base metrics directly under each `history[]` row; product identity is `product.nmId` and currency is beside `history`. | Day × `nmId`. | Same as funnel daily source. | Legacy period normalizers coerce several absent fields to zero and overwrite duplicate `nmId`; percentages/deltas are cached alongside base measures. | Persist only the seven source-proven nullable base measures. Do not persist ratios, comparisons, product metadata, impressions or cancellations. |
| Funnel cancellations/returns | Described operationally by WB but absent from the current `products/history` JSON schema and live response. Long-range `DETAIL_HISTORY_REPORT` CSV documents cancellation columns separately. | Not proven for this JSON source. | Outside the recent JSON slice. | Legacy code anticipates aliases that the sampled response did not expose. | Do not add speculative JSON columns or fall back to supplier/finance returns. Design a separate CSV evidence slice when long-range/cancellation facts are required. |
| Supplier orders and cancellations | `GET /api/v1/supplier/orders`; `fetch_period_stats_aggregates`, `_collect_period_statistics_timeseries`, `app/wb_api/reports_sources_runtime.py` | Order-like row. Current identity preference: `srid`, `odid`, `rid`; then a composite using order UID/gNumber, `nmId`, barcode/size/date/price. | Only `dateFrom` is sent; code filters an end date locally. No pagination. Statistics policy is 1/min; legacy retry up to 4 with 61 s spacing and 180 s cap. | `period_stats_*` mutable org-only cache. A cancellation is detected by boolean aliases or a non-placeholder cancel date, but assigned to the row's original order date. | Do not add it to this slice. Keep as diagnostic/parity evidence until order/cancel business date, stable identity and correction semantics are proved. It must not overwrite Sales Funnel orders. |
| Supplier sales and returns | `GET /api/v1/supplier/sales`; same adapters | Sale/return row, with `saleID`, `srid`, `isReturn` visible in current evidence. | Same dateFrom-only and 1/min behavior. | Current period aggregation has no sale-row dedup and computes revenue from `finishedPrice`, then `forPay`, then `priceWithDisc`. | Do not canonicalize here and do not use as P&L revenue. Canonical finance remains authoritative for sales/returns. This endpoint is diagnostic until its own order domain is designed. |
| Finance sale/return/redemption | Existing canonical finance adapter and `wb_finance_*` facts | Immutable finance operation identity (`rrdId`/source identity) and SyncRun membership | Canonical Moscow `Period`; outside this slice | Canonical PostgreSQL facts and rollups | Reuse, do not change. ABC/P&L sales, returns and revenue come from finance. “Redemptions” remains a finance report type, not a funnel metric. |

There is a second Sales Funnel implementation in `app/wb_api/rnp_runtime.py::_fetch_sales_funnel_rows` and direct SKU time-series loaders in `app/repricer_bff.py`. They differ in `skipDeletedNm`, ordering, retry and normalization. They are not a second canonical source; rollout must route their consumers to the canonical read model.

### 4.2 Advertising sources

| Flow | Endpoint and current adapter | Source grain and identity | Period, batching and retry | Current persistence/state | Canonical decision and blockers |
|---|---|---|---|---|---|
| Campaign discovery | `GET /adv/v1/promotion/count`; `_campaign_ids_from_promotion` and legacy `_ads_campaign_ids_from_payload` | Account × `advertId`; status/type are observations, not identity | No pagination in current adapter. Ads-meta policy is 5/s. Rich adapter retries 429 up to 3. | Legacy sync keeps only campaign count and later discards campaign ID from SKU aggregates. Rich report merges metadata in memory. | Campaign identity is account-scoped `advertId`. Discover the union of promotion IDs and UPD campaign IDs. A missing metadata row must not discard metric/spend facts. Legacy status filtering `{7,9,11}` is not sufficient for historical periods. |
| Campaign metadata and membership | `GET /api/advert/v2/adverts`; `_request_adverts_payload`, `_campaign_meta_from_adverts`, `_sku_membership_from_adverts` | Account × campaign `id`; current membership is `nm_settings[].nm_id` at capture time | Campaign IDs batched by 50 when filtered; ads-meta 5/s; rich retry up to 3 on 429 | Current history tables are org-only. Status/budget uniqueness uses `fetched_at`, so repeated refreshes create new rows. | Store a run-scoped campaign snapshot and sorted membership IDs. Membership proves association only; it never carries spend/orders and never upgrades campaign-only metrics to SKU attribution. |
| Advertising metrics | `GET /adv/v3/fullstats`; legacy `fetch_ads_spend_aggregates`; rich `build_ads_attribution_snapshot` | Current hierarchy: requested subwindow × campaign header × `days[].date` × `apps[].appType` × `nms[].nmId`. No external row ID. | Max 50 campaign IDs/request and 31 inclusive days/window. Client policy: 3/min, 20 s. Legacy path enforces 23 s, up to 8 attempts and splits invalid 400/422 batches; rich path uses 20 s and up to 3 attempts. | Legacy `ads_*` cache collapses campaign/app into org + period + `nmId`. Rich cache is org + period + groupBy; history daily rows have no uniqueness. | Preserve campaign observations and source-SKU children with explicit scope and app type; consumers choose one hierarchy level. Dated nodes are daily. A legacy undated top-level branch is reconciliation-only when dated data exists and otherwise remains an unsupported partial case in the first raw-storage slice. Any skipped/failed campaign or window makes the run partial. |
| Advertising spend documents | `GET /adv/v1/upd`; `_normalize_upd_rows` | Account-scoped logical row identity is `(updNum, advertId, updTime)`; `updNum` alone identifies a multi-row document | Split into 31-day windows. Ads account-money policy is 1/s; rich retry up to 3 on 429. | Append-only org-only `wb_ads_spend_documents`, no uniqueness or account. Repeated report refresh duplicates documents. | Store separately at account + run + the composite logical identity; parse `updTime` with its offset and derive Moscow business date. Missing any identity component is a blocker. UPD can reconcile campaign/account spend but is never allocated to SKU. |
| Budget and cabinet balance | `GET /adv/v1/budget`, `GET /adv/v1/balance` | Current mutable snapshot, not historical spend | Budget 4/s per campaign; balance/account-money 1/s | Current report/history snapshots | Excluded from canonical ABC/P&L/RNP facts. Keep operational report behavior outside this slice. Add a dedicated snapshot only when a dated business requirement exists. |
| Search phrases | `GET /adv/v1/normquery/stats`; `fetch_ads_search_clusters` | Campaign × `nmId` × day × normalized query | Batches up to 100 IDs; policy 10/min | In-memory/report payload | Excluded: no current ABC/P&L/RNP fact requires it. |

## 5. Confirmed observations versus attribution

### 5.1 Confirmed facts

- A Sales Funnel metric is confirmed only at the period/day and `nmId` returned by WB.
- A `fullstats` campaign header is a confirmed campaign-level observation.
- A `fullstats` metric-bearing leaf with `nmId` is a confirmed source-SKU observation.
- `/api/advert/v2/adverts` membership is a confirmed campaign-to-`nmId` relationship at capture time.
- An UPD row with stable `(updNum, advertId, updTime)` is a confirmed spend-document line; `updNum` alone is a document grouping value.
- Canonical finance sales/returns/revenue remain confirmed finance facts.

### 5.2 Derived, never stored in the source fact tables

Use a versioned read-model formula, initially `wb-funnel-ads-derived-v1`, for:

- cart-to-order = `order_count / cart_count * 100`;
- funnel buyout rate = `buyout_count / order_count * 100`;
- ad CTR = `ad_click_count / ad_impression_count * 100`;
- ad ATCR = `ad_cart_count / ad_click_count * 100`;
- DRR-orders = source-SKU ad spend / funnel order amount;
- DRR-sales = source-SKU ad spend / canonical finance seller revenue;
- ad ROI/ROMI = `(ad_order_amount - ad_spend) / ad_spend * 100`;
- source-SKU attributed subtotal = sum of source-SKU facts only;
- campaign-only residual = campaign observation minus source-SKU subtotal, only when both cover the same campaign, metric and source interval;
- unknown spend = confirmed UPD/account spend that cannot be reconciled to a campaign observation;
- RNP “organic” estimates remain blocked until the compared funnel and advertising counters have proven matching semantics and windows.

Every ratio is `NULL` when its denominator is missing or non-positive. A residual is `NULL`, not zero, when either side is incomplete, period grains differ, or the subtraction is negative beyond an explicit reconciliation tolerance.

Attribution states exposed by the projection should be:

- `source_sku`: the metric-bearing source row contains `nmId` and period coverage is complete;
- `unmapped_product`: the source row contains `nmId`, but no account-scoped marketplace product is currently mapped;
- `campaign_only`: a campaign observation/residual has no source metric-bearing `nmId`;
- `unknown`: campaign or time ownership is not trustworthy enough for reconciliation.

The legacy label `campaign_sku` may remain temporarily at an API boundary, but it must not mean “campaign spend divided among members”. No proportional, equal-share, order-share or last-click allocation is part of this design.

## 6. Current consumers and target formulas

| Consumer | Current inputs/behavior | Canonical input and readiness rule |
|---|---|---|
| ABC | `app/wb_reports_sprint_d.py::_build_abc_report_from_snapshots` joins mutable finance, baskets and ads caches. Row set is finance ∪ baskets. Funnel `openCount` is shown as traffic clicks; CTR uses explicit funnel impressions when present; cart CR is orders/baskets. DRR uses ad spend over funnel order amount or finance revenue. Legacy net profit and ABC profit class treat missing ads as zero in several paths. | Row set becomes catalog ∪ canonical finance ∪ funnel ∪ source-SKU ads. Sales/returns/revenue come only from finance. Traffic metrics come only from funnel. Ad metrics come only from `source_sku`. Missing source remains null and adds a blocker; campaign-only/unknown spend is visible in diagnostics, not allocated. |
| Canonical ABC/P&L service | `app/modules/wb_reports/abc_pnl.py` currently exposes `profit_before_ads_and_loyalty_kopecks`; net profit, profit class and ABC code remain null under `WB_PNL_ADS_NOT_CANONICAL` and `WB_PNL_LOYALTY_NOT_CANONICAL`. | Remove only the ads blocker when the exact account/period has a published ads run, source-SKU spend coverage meets the agreed policy, and campaign/fullstats/UPD reconciliation passes. Loyalty remains blocking. Do not revive the legacy final-net-profit formula. |
| Legacy P&L | `_build_cached_pnl_report` prefers finance `adSpendKopecks` when `financeAdSpendAuthoritative`, otherwise SKU ads cache, and subtracts it from finance revenue with other costs. Cache presence may be treated as zero spend. | Finance revenue/cost basis stays canonical. Subtract a canonical ads subtotal once. A finance “WB Promotion” deduction, `fullstats.sum` and `updSum` are reconciled sources, not three additive expenses. Unallocated spend keeps SKU-level P&L incomplete. |
| RNP | `app/wb_api/rnp_runtime.py::_rnp_row_from_sources` joins org-only funnel/ads caches by `nmId`. It calculates ad CTR, ATCR, DRR, ROI, ACoO/TACoO and `max(0, funnel - ad)` organic estimates. Any present ads row can enable those estimates. | Require one account, one revision vector and complete matching intervals. Use only `source_sku` ad metrics. Campaign-only/unknown/unmapped amounts do not enter SKU formulas. Organic values remain explicitly derived estimates and become null on incomplete attribution or semantic mismatch. |
| Advertising report | Rich report can show campaign metadata, balances, UPD, daily rows and attribution labels; cached fallback can fabricate an `unattributed`/`FBBT_42` row. | Campaign view reads campaign-scope facts and UPD reconciliation; SKU view reads source-SKU facts. Show campaign-only and unknown buckets explicitly. Never create a synthetic product row. DRR/ROI are null on undefined denominators. |
| Digest / week-over-week / SKU detail / repricer | Digest may choose funnel buyout amount, supplier sales or finance summary by availability. Direct detail loaders call WB again. Repricer consumes baskets/orders and comparisons from mutable caches. | Route to a projection keyed by canonical run IDs. Keep finance and funnel measures named separately. Direct WB detail calls become cache/read-model reads after parity; repricer can continue to consume base funnel counts plus versioned deltas. |

## 7. Current cache and SyncRun gaps

### 7.1 Mutable cache behavior

- `wb_repricer_source_cache` is unique only on `(organization_id, source_key)`; it has no marketplace account.
- `ads_*` and `baskets_*` keys are mutable range blobs. A refresh overwrites the same key.
- `save_source_cache` stamps a new `fetchedAt` on every partial/progress write and silently falls back to an unstored payload on SQLAlchemy errors.
- Redis is a 45-second accelerator only for selected status keys, not the ranged source blobs.
- A covering range may be sliced from `dailyAggregates`, but revision identity and source checksum are absent.
- Ads readiness checks `dailyAggregatesDays`, not whether the days came from dated source nodes or whether all campaigns/windows reconciled.
- `wb_sync_status` is one mutable org-level run; it has no account scope, immutable source manifest or snapshot checksum.
- Current schedules are useful SLAs, not identities: recent funnel is normally 2 days / 120 minutes; recent ads 3 days / 180 minutes; nightly reconciliation is 30 days / 24 hours; onboarding loads 7 and 30 days.

### 7.2 Confirmed failure modes

1. `app/repricer_bff.py::_merge_ads_spend_aggregate_from_node` recursively visits both dated and top-level fixture branches. The built-in legacy fixture uses `nm[]` and repeats the same SKU values in both branches, so the first campaign's 1,800 RUB becomes 3,600 RUB in SKU aggregation. The live v3 payload uses `nms[]` and did not expose a top-level app branch in the sampled windows.
2. The same recursion treats undated top-level nodes as in range for every requested day, so period totals can be copied into every daily bucket.
3. `app/wb_api/ads_runtime.py::_collect_nm_rows` has the same recursive duplication for grouped SKU rows. Its metric buckets start at zero, so the later non-`None` completeness check can mark omitted fields as complete exact attribution.
4. The default advertising fixture itself provides the parity oracle: campaign headers total 195,000 kopecks; direct SKU children total 180,000; UPD totals 195,000; therefore the unallocated campaign subtotal is 15,000. Current recursive SKU paths do not preserve that invariant.
5. Legacy ads aggregates discard `advertId`, app and attribution grain. Rich history writes are append-only without a daily/document natural-key constraint.
6. Funnel normalization overwrites duplicate `nmId`, drops cancellation fields and converts several missing values to zero.
7. Supplier sales aggregation does not deduplicate `saleID`/`srid`; supplier cancellation is dated by the order row rather than a proven cancellation business date.
8. Process-local rate-limit clocks and locks do not coordinate multiple workers.

## 8. Identity, ownership and time rules

### 8.1 Ownership

Every run and fact carries `organization_id` and `marketplace_account_id` with the same composite foreign-key pattern already used by canonical finance. `advertId`, `nmId` and `updNum` are never globally unique.

Facts retain external `nm_id` even when catalog mapping is missing. They do not persist a mutable internal product ID; readers left-join `marketplace_products` on `(organization_id, marketplace_account_id, external_product_id)`. This preserves source evidence, prevents cross-account attachment and avoids rewriting immutable facts after catalog mapping changes.

### 8.2 Business time

- Validate report input through the existing canonical `Period`: inclusive local dates, `Europe/Moscow`, maximum 90 days, with the existing UTC half-open conversion where timestamps are required.
- Funnel `business_date` is the exact ISO date returned by `history[].date`, validated inside the requested inclusive period.
- Advertising `days[].date` is parsed as the returned aware timestamp and projected to its Moscow calendar date. The live sample used UTC-midnight timestamps; late revisions remain distinct immutable snapshots.
- An undated `fullstats` header or `apps` branch is stored with the exact request subwindow `date_from/date_to` and `grain='period'`; it is never spread over dates.
- `updTime` is parsed as an aware timestamp. `business_date` is its `Europe/Moscow` date. An unparseable time is raw-only and blocks spend completeness.
- `captured_at` and `last_observed_at` are UTC timestamps.

### 8.3 Source identity and checksums

Use canonical JSON serialization with sorted keys, explicit nulls and Decimal-based RUB-to-kopeck conversion. Do not use binary float for money.

| Table | Logical source identity before hashing | Payload checksum covers |
|---|---|---|
| `wb_funnel_daily` | `funnel-history-v1 · business_date · nmId` | nullable source-proven base metrics returned for that source row |
| campaign snapshot | `campaign-v1 · advertId` | normalized metadata, sorted membership and source-presence flags |
| campaign ads fact | `fullstats-v1 · grain · from · to · advertId · campaign` | campaign-level nullable metrics |
| source-SKU ads fact | `fullstats-v1 · grain · from · to · advertId · appType-or-null · nmId · source_sku` | leaf-level nullable metrics |
| spend-document line | `upd-v1 · updNum · advertId · updTime` | campaign fields, currency and signed spend |

`source_identity` is the SHA-256 of the account-scoped logical identity. `payload_checksum` excludes capture time. A duplicate identity with the same payload inside one run collapses; the same identity with a different payload inside one response/run is a blocking ambiguity.

The run `snapshot_checksum` is the SHA-256 of sorted `(entity kind, source_identity, payload_checksum)` triples plus the requested period, normalizer version and completeness manifest. It therefore changes when data, source coverage or normalization changes.

## 9. Schema sketch

This is a logical sketch, not migration-ready DDL.

### 9.1 `wb_funnel_sync_runs`

Required fields:

- `sync_run_id`, `organization_id`, `marketplace_account_id`, optional `parent_sync_run_id`;
- `date_from`, `date_to`, source reference;
- `normalizer_version`, `snapshot_checksum`;
- `raw_manifest`, `raw_manifest_checksum`;
- expected/completed request counts and fact count;
- `captured_at`, `last_observed_at`, `created_at`.

Required constraints/indexes:

- composite FK to the owning marketplace account;
- account-scoped parent FK and parent-not-self check;
- `date_from <= date_to`;
- unique `(organization_id, marketplace_account_id, sync_run_id)`;
- unique `(organization_id, marketplace_account_id, date_from, date_to, snapshot_checksum)`;
- covering index `(organization_id, marketplace_account_id, date_from, date_to, last_observed_at)`.

Funnel v1 fetches completely before opening the publication transaction. A committed run is therefore published by definition; no staging/status row is persisted. Failed and partial fetches return diagnostics to the caller and write nothing.

### 9.2 `wb_funnel_daily`

Required fields:

- ownership and `sync_run_id`;
- `business_date`, positive `nm_id`, `source_identity`, `payload_checksum`;
- nullable `open_count`, `cart_count`, `order_count`, `order_amount_kopecks`, `buyout_count`, `buyout_amount_kopecks`, `add_to_wishlist_count`.

Required constraints/indexes:

- account-scoped composite FK to the run;
- unique `(organization_id, marketplace_account_id, sync_run_id, source_identity)`;
- all present counts and funnel amounts are non-negative;
- at least one source metric is non-null;
- query index `(organization_id, marketplace_account_id, business_date, nm_id, sync_run_id)`.

Do not store ratios, comparison deltas, product title/brand, finance revenue or an inferred zero row.

### 9.3 `wb_advertising_sync_runs`

Use the funnel run envelope and constraints, with advertising-specific coverage metadata: discovered campaign IDs, completed campaign batches, completed 31-day windows, UPD coverage and endpoint-level status. Do not introduce a generic cross-domain run table solely to remove duplicated columns.

### 9.4 `wb_advertising_campaign_snapshots`

Required fields:

- ownership, run, positive `advert_id`, `source_identity`, `payload_checksum`;
- nullable source name/type/status/payment/change timestamp;
- sorted `member_nm_ids` JSON array and `membership_source='adverts'`.

Required constraints/indexes:

- account-scoped run FK;
- unique run + `source_identity`;
- index `(organization_id, marketplace_account_id, advert_id, sync_run_id)`.

No normalized membership table or GIN index is required until a measured query needs it. Membership remains non-metric evidence.

### 9.5 `wb_advertising_facts`

Required fields:

- ownership and run;
- `grain` (`day` or `period`), `date_from`, `date_to`;
- positive `advert_id`, `fact_scope` (`campaign` or `source_sku`);
- nullable `app_type`; `nm_id` required only for `source_sku`;
- `source_identity`, `payload_checksum`;
- nullable `impression_count`, `click_count`, `cart_count`, `order_count`, `order_amount_kopecks`, `spend_kopecks`.

Required constraints/indexes:

- account-scoped run FK;
- `date_from <= date_to`; `grain='day'` requires equal dates;
- campaign scope requires `nm_id IS NULL`; source-SKU scope requires positive `nm_id`;
- unique run + `source_identity`;
- all present `fullstats` metrics are non-negative and at least one is non-null;
- campaign query index `(organization_id, marketplace_account_id, date_from, date_to, advert_id, fact_scope, sync_run_id)`;
- SKU query index `(organization_id, marketplace_account_id, date_from, date_to, nm_id, fact_scope, sync_run_id)`.

Campaign and source-SKU rows intentionally coexist. Any additive query must filter exactly one `fact_scope`.

### 9.6 `wb_advertising_spend_documents`

Required fields:

- ownership and run;
- non-empty `upd_num`, aware `upd_time`, Moscow `business_date`;
- positive `advert_id` and nullable source campaign metadata;
- signed `spend_kopecks`, `source_identity`, `payload_checksum`.

Required constraints/indexes:

- account-scoped run FK;
- unique run + `source_identity`;
- index `(organization_id, marketplace_account_id, business_date, advert_id, sync_run_id)`;
- cross-run lookup index `(organization_id, marketplace_account_id, upd_num, advert_id, upd_time)`.

Spend is signed because the absence of negative values in one 31-day probe does not prove that corrections cannot occur. Missing `updNum`, `advertId` or `updTime`, or conflicting payload for the same composite line identity, is a DQ blocker, not a fallback fingerprint.

## 10. Idempotent SyncRun flow

1. Validate organization/account ownership and canonical `Period`; build a deterministic request plan.
2. Fetch through the existing adapter layer before opening the publication transaction. Record each response in the in-memory manifest with endpoint, request parameters, WB request ID when present, response checksum and success/error state.
3. Return partial diagnostics without database writes when any planned request fails or has an invalid payload.
4. Normalize complete responses with explicit nulls and Decimal money. Exact duplicates collapse; conflicting identities fail. For `fullstats`, preserve its existing hierarchy rules.
5. Verify coverage, ownership, identities, non-negative metrics, raw/normalized checksums and applicable hierarchy reconciliation.
6. Acquire one PostgreSQL account+domain lock and look up an exact account/period/checksum replay. Update only its monotonic `last_observed_at` and return its ID.
7. If changed, set `parent_sync_run_id` to the prior run for the same exact scope and atomically insert the new run with all facts.
9. Readers choose one latest published run that covers the requested period, preferring the smallest covering range then newest capture. Daily facts may be sliced. A period-grain ads fact may be used only for the exact matching source subwindow; it must not be sliced.
10. If no usable published run exists, return a blocker. Do not stitch overlapping mutable revisions in v1. Add stitching only after a concrete report requires it and parity tests define revision precedence.

Derived/report cache keys include organization, account, requested period, selected funnel/ads/finance run IDs and formula version. Redis remains a bounded accelerator; deleting it must not change results.

## 11. Data-quality gates

A run cannot publish when any applicable gate fails:

- account ownership or account-scoped product lookup is ambiguous;
- a requested funnel SKU chunk has no successful valid response;
- discovered advertising campaign/window failed or was silently skipped;
- duplicate source identity has conflicting payloads;
- source date/time cannot be interpreted under the defined rule;
- money cannot be converted exactly to kopecks;
- required raw manifest/checksum is absent;
- a metric is negative where the source contract is non-negative;
- dated/top-level advertising hierarchy would be counted twice;
- campaign totals are below source-SKU children beyond the agreed tolerance;
- UPD document identity/time is invalid;
- report tries to add campaign and source-SKU fact scopes;
- SKU P&L tries to allocate campaign-only/unknown spend;
- report treats missing fields, rows or source coverage as zero.

Non-blocking diagnostics, shown with counts and examples, include unmapped `nmId`, campaign metadata missing for a valid metric fact, campaign-to-SKU residual, source-provided percentage differing from the canonical formula, and late revision versus the parent run.

## 12. Parity fixtures and tests required before rollout

The existing `tests/fixtures/wb_abc_2026_08_17_23.json` proves report totals/checksums but does not contain raw finance identity rows, funnel payloads or ads hierarchy. It is insufficient for this slice and should remain unchanged.

Add frozen, sanitized raw-response fixtures during implementation:

| Fixture | Required assertion |
|---|---|
| Funnel recent history complete | Exact `nmId`/date rows preserve opens, baskets, orders, order amount, buyouts, buyout amount, wishlist adds and currency. |
| Funnel missing optional fields | A missing source field remains null while an explicit zero remains zero; an omitted product/date creates no fact. |
| Funnel SKU batching | 21 requested SKUs produce deterministic batches of 20 and 1 and yield each returned identity once. |
| Funnel duplicate exact/conflict | Exact duplicate collapses; conflicting duplicate blocks. |
| Funnel partial request | Exhausted 429, transport or malformed response returns partial diagnostics; no partial run becomes readable. |
| Funnel late revision | Same day/`nmId` with changed payload creates a child run; prior run remains reproducible. |
| Moscow boundaries | Inclusive local dates select the expected source days around UTC midnight. |
| Ads live hierarchy | Freeze a sanitized current shape with `days[].apps[].nms[]`, `canceled`, aware day timestamps and repeated `nmId` across app types. Preserve app scope and exact campaign/day/app/SKU reconciliation. |
| Ads legacy dual hierarchy | Keep the current fake shape containing both `days[].apps[].nm[]` and top-level `apps[].nm[]` as a regression oracle. Expect campaign spend 195,000, source-SKU spend 180,000, UPD spend 195,000 and campaign-only residual 15,000 kopecks—never 360,000. |
| Ads campaign-only | Header metrics with no metric-bearing SKU remain campaign-only even when membership lists SKUs. |
| Ads period-only | Undated top-level metrics are stored once at period grain and never repeated per day. |
| Ads missing versus zero | Omitted metrics stay null and cannot produce `source_sku` completeness; explicit zeros remain zeros. |
| Ads batching/windows | 51 campaigns and a period over 31 days produce complete, non-overlapping request coverage. |
| Ads partial campaign | One invalid/429 campaign makes the run partial and records the campaign ID; it is not silently omitted. |
| UPD identity | Multiple rows sharing `updNum` survive when `(updNum, advertId, updTime)` differs; exact composite repeats collapse; conflicting payload or a missing component blocks. |
| Hierarchy mismatch | Source-SKU subtotal greater than campaign total blocks attribution and reports diagnostics. |
| Two accounts | Identical `nmId`, `advertId` and `updNum` in two accounts never collide or cross-join. |
| Repeated SyncRun | Exact replay returns the original run ID and row counts; changed payload creates one parent-linked run. |
| Consumer formulas | Undefined denominators are null; campaign and source-SKU scopes cannot be accidentally summed; finance revenue is unchanged. |
| Canonical P&L gate | Ads readiness can remove only `WB_PNL_ADS_NOT_CANONICAL`; loyalty and any economics blocker remain. |

Minimum automated layers:

1. pure normalizer tests against raw fixtures;
2. PostgreSQL constraints, tenant isolation and repeated-run integration tests;
3. adapter request-plan tests for pagination, batching, windows and retry/defer;
4. projection parity tests for ABC, P&L and RNP using an explicit revision vector;
5. a regression test for the dual `fullstats` hierarchy before any consumer switch.

## 13. Rollout sequence

1. **Freeze evidence.** Obtain sanitized raw fixtures through an approved offline path and resolve the blocking questions below. Do not use generated report aggregates as the oracle.
2. **Land storage, pure normalizer and manual backfill.** Reuse canonical ownership/Period/finance SyncRun conventions. Do not change report readers or add a feature flag for an unread table.
3. **Add scheduled dual-write in a later slice.** Canonical writes must be account-scoped; legacy caches remain unchanged. Compare row counts, snapshot checksums and coverage. Never dual-write from a report GET.
4. **Shadow projections.** Build campaign, source-SKU, campaign-only and unknown subtotals. Compare current ABC/RNP fields but accept only intentional differences documented above, especially duplicate removal and null preservation.
5. **Switch the advertising report and RNP reads.** Remove direct WB/report-refresh persistence and fabricated fallback rows. Keep partial attribution explicit.
6. **Integrate ABC/P&L.** Use canonical finance revenue unchanged. Subtract ads once and remove the ads blocker only after exact-period reconciliation; leave loyalty/final-profit blockers intact.
7. **Retire legacy blobs.** Stop writing `ads_*`/`baskets_*` only after at least one full freshness window plus nightly reconciliation passes and rollback reads have been exercised. Drop legacy tables/caches in a later, separately approved change.

## 14. Open questions

Resolved sufficiently for funnel raw storage, but not consumer semantics:

1. The current daily JSON contract and live response expose no impressions or cancellations. V1 stores neither; `openCount` is a card transition/open, never an impression.
2. Subtracting advertising clicks from `openCount` is not approved because the semantics and attribution windows differ.
3. WB does not provide a contractual zero guarantee for omitted product/date rows. V1 records no fact for an omission and consumers must treat it as missing.

Resolved sufficiently for advertising raw storage, but not for consumer semantics:

4. Live `fullstats.days[].date` values were UTC-midnight timestamps. V1 parses them as aware instants and derives their Moscow calendar date; whether a closed source day can revise remains a late-revision concern, handled by immutable checksums.
5. `updNum` is demonstrably not row-unique. V1 uses account + `(updNum, advertId, updTime)` and keeps spend signed; conflicting repeats block publication.

Blocking before a consumer cutover:

6. For accounting spend, which source is authoritative by period: UPD, `fullstats.sum`, or a named finance deduction? What reconciliation tolerance and timing lag are accepted?
7. Can stopped/archived historical campaigns disappear from `promotion/count`; if so, what approved source enumerates them when neither current metadata nor UPD contains the ID?
8. May source-SKU `fullstats` spend be considered complete when its subtotal is below the campaign header, or must any residual block SKU P&L?
9. Which RNP “organic” differences remain useful when funnel and advertising counters have different semantics or attribution windows?
10. Should historical freshness follow the current nightly 24-hour cadence, or is a longer closed-period SLA accepted?

Non-blocking/YAGNI decisions:

- Normalize campaign membership into its own table only when membership queries become material or history comparison cannot be served from the campaign snapshot.
- Add cross-run range stitching only when a real report cannot request or find one covering published run.
- Add budget/balance/search-query facts only for a separately approved dated business use case.
