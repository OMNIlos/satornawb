# WB Backend Reuse And Dependency Map

Дата: 2026-05-25
Статус: backend handoff map for Sprint A/B gates.
Scope: WB first / INDEEPA replacement.

## 1. Shared data domains

| Domain | Produced by | Reused by | Blocks if missing/stale |
|---|---|---|---|
| WB account/token health | auth/token discovery | every WB adapter, sync job, account settings | all live WB sync; source registry remains `unknown/missing_access` |
| SKU directory | WB product/card source + internal enrichment | repricer, reports, ABC, P&L, ads attribution, exports | production row identity, brand scope, manager filters |
| COGS | Excel import/manual SKU card | margin, P_min/P_max, P&L, ABC profit, price guards | margin-dependent auto price apply |
| СПП | WB source or approved fallback | price planes, margin, P_min/P_max, strategy dry-run, apply guards | external price apply and confident margin |
| Commission/logistics/storage/tax | WB reports + finance rules | margin, P&L, ABC profit, plan-fact | final finance, final margin, profit ABC |
| Demand metrics | WB reports/analytics | strategies 4599/4600, RNP, ABC, digest, week-over-week | strategy auto-drafts and demand recommendations |
| Ads attribution | WB Ads source/export/manual mapping | RNP, ads recommendations, P&L ad allocation, ABC context | SKU ad P&L and SKU stop candidates |
| Stock snapshots | WB stocks report + daily job | stock report, week-over-week, OOS guards, ads guard, repricer | OOS context, stock decision, stale-source guards |
| Source freshness/confidence | source registry + sync jobs | every report and risky action | auto-apply, final finance, recommendation confidence |
| Audit/permissions | platform foundation | settings, price apply, finance export, reviews | risky actions and financial visibility |

## 2. Core dependency chains

### Price apply chain

```text
SKU directory
  -> current price before/after СПП
  -> СПП source/fallback
  -> COGS + commission + logistics + storage + tax
  -> margin + P_min/P_max
  -> strategy/manual/import price draft
  -> guards: per-update, per-day, min_price/promo, stale critical sources
  -> approval
  -> WB price apply job
  -> row-level status/errors
  -> audit
```

Hard blockers:

- `WB-06` СПП;
- `WB-22` price apply/status/errors;
- `WB-23` freshness/confidence;
- finance inputs for final margin if the action depends on final margin.

### RNP and ads chain

```text
WB Ads campaigns/spend
  -> attribution: exact_sku / campaign_sku / campaign_only
  -> funnel: impressions, clicks/views, baskets, orders, sales
  -> ДРР/ROI/review candidate
  -> RNP table and ads report
  -> optional SKU drawer context
  -> optional P&L ad allocation only for acceptable attribution
```

Rules:

- `campaign_only` must not be allocated into SKU P&L.
- `campaign_only` must not create SKU stop recommendation.
- v1 creates review candidates only; no auto-stop.

### P&L and ABC chain

```text
SKU directory + sales/orders
  -> revenue
  -> COGS
  -> commission/logistics/storage/tax/OPEX
  -> unit and period P&L
  -> ABC profit letter
  -> product status/rating
  -> liquidation context and repricer filters
```

Rules:

- P&L can be `operative` or `preliminary` before Maxim confirms tax/storage/OPEX.
- `final` P&L is blocked by `WB-12`, `WB-13`, and finance permissions.
- Managers without `finance_viewer` get no-access states, not leaked values.

### Stock and week-over-week chain

```text
WB stocks report
  -> daily stock snapshots
  -> availableUnits = wbStockUnits + fromClientUnits
  -> wasOutOfStock / stockAvailability7d / coverage
  -> week-over-week OOS explanation
  -> ads and repricer guards
  -> stock decision after KTR/localization formula
```

Rules:

- Do not infer historical OOS from current WB stock.
- Do not add `toClientUnits` to availability.
- Before enough snapshots exist, return partial/coverage state.

### Liquidation chain

```text
product status + turnover + stock + baskets/orders + ads + margin
  -> candidate reasons
  -> manager approval
  -> liquidation price draft series
  -> same price guards and WB apply job as repricer
```

Rules:

- No automated liquidation before Maria confirms candidate criteria and AND/OR logic.
- Negative margin requires explicit approval and audit reason.

## 3. Screen dependency matrix

| Screen | Reads | Writes/actions | Shared dependencies | Primary blockers |
|---|---|---|---|---|
| `/wb/repricer` | SKU, prices, СПП, economics, demand, stock, ads context | manual draft, strategy dry-run, apply request | SKU directory, COGS, СПП, source freshness, audit, permissions | WB-06, WB-22, WB-23 |
| `/wb/repricer/settings` | settings versions, strategy configs | draft settings, approve/activate | permissions, audit, formula versions | WB-14, WB-25 |
| `/wb/repricer/liquidation` | product status, stock, demand, ads, margin | candidate approval, liquidation price draft | repricer guards, audit, P&L | WB-04, WB-06, WB-22 |
| `/wb/reports` | report aggregates, plan-fact, source state | export | brand scope, P&L, permissions | WB-03, WB-12, WB-13, WB-24 |
| `/wb/reports/abc` | sales/profit ranks, statuses | export/filter | P&L, SKU directory, product status | WB-09, WB-12, WB-13, WB-19 |
| `/wb/reports/pnl` | revenue, costs, storage, tax, ads | export/manual inputs if allowed | finance permissions, source registry | WB-11, WB-12, WB-13, WB-24 |
| `/wb/reports/ads` | campaigns, spend, attribution, sales | review candidates only | Ads source, SKU directory, OOS guard | WB-02, WB-11, WB-20 |
| `/wb/reports/rnp` | funnel, ads, demand, SKU context | comments/review candidates | Ads attribution, demand reports, audit/comments | WB-02, WB-03, WB-11 |
| `/wb/reports/stock` | stock snapshots, KTR/localization | review candidates only | local orders, stock fields, daily snapshots | WB-01, WB-17, WB-18 |
| `/wb/reports/week-over-week` | daily stock snapshots, sales/orders/baskets | export | snapshot job, demand reports | WB-18, WB-23 |
| `/wb/reviews` | WB feedbacks, brand rules | draft, approve, send later | AI harness, prompt caching, audit, permissions | WB-16 |
| `/wb/export` | current view data | XLSX export | permissions, source metadata | WB-23, WB-24 |

## 4. Fallback policy by dependency type

| Dependency type | Acceptable fallback | External action allowed? |
|---|---|---|
| Missing report metric | `нет данных` / `partial_data` | no automation based on missing metric |
| Missing COGS | `не задано` | no margin-dependent price apply |
| Missing СПП | `blocked_by_source_mapping` | no price apply |
| Stale critical source | last successful snapshot with stale warning | no auto-apply; manual review only if approved |
| Weak ads attribution | `campaign_only` | no SKU P&L allocation and no SKU stop candidate |
| Missing finance formulas | `operative`/`preliminary` | no final finance export/claim |
| Missing stock snapshot coverage | partial coverage state | no final OOS/stock decision |
| Missing permissions | no-access state | no leaked field values or exports |

## 5. Backend acceptance checks

- A route that returns a metric must be able to point to registry row IDs.
- A route that returns a recommendation must include formula version and source state.
- A route that exposes money or finance export must pass permission checks.
- A route that creates an external side effect must have preview, approval, commit result and audit.
- Any blocked dependency must be visible in API as data, not hidden in logs.
