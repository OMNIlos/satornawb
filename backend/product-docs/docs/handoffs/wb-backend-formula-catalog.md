# WB Backend Formula Catalog

Дата: 2026-05-25
Статус: Sprint A formula catalog.
Scope: WB first / INDEEPA replacement.

## 1. Formula status

- `confirmed` - формула и business meaning уже зафиксированы.
- `needs_client` - нужна Мария/Максим.
- `needs_api_discovery` - формула понятна, но не подтверждены source fields.
- `draft` - можно использовать для stubs/dry-run, нельзя считать final production truth.
- `disabled` - не реализовывать в v1.

## 2. Price and margin formulas

| formula | inputs | output/units | rule | rounding | owner/status | used by | blockers |
|---|---|---|---|---|---|---|---|
| Price after СПП | `priceBeforeSppKopecks`, `sppPct` | kopecks | `priceBeforeSppKopecks * (1 - sppPct / 100)` if WB does not provide final value | integer kopecks, round half up after percent conversion | Backend discovery / `needs_api_discovery` | repricer table, SKU drawer, margin, P_min/P_max | WB-06 |
| Price before СПП from after СПП | `priceAfterSppKopecks`, `sppPct` | kopecks | `priceAfterSppKopecks / (1 - sppPct / 100)` | integer kopecks, round up for minimum-safe bounds | Backend discovery / `needs_api_discovery` | manual price edit, price bounds | WB-06 |
| Unit margin rub | `priceAfterSpp`, commission, logistics, storage, COGS, tax | kopecks | `priceAfterSpp - commission - logistics - storage - COGS - tax` | integer kopecks | Максим + backend / `needs_api_discovery` | repricer, P&L, ABC, plan-fact | WB-06, WB-03 |
| Unit margin percent | `unitMarginKopecks`, `priceAfterSppKopecks` | percent | `unitMarginKopecks / priceAfterSppKopecks * 100` | 1 decimal in UI; store decimal | Максим + backend / `needs_api_discovery` | repricer, P&L, ABC | WB-03 |
| P_min validation | selected price plane, СПП, COGS, target margin, promo/min_price | valid/blocked reason | convert to after-SPP plane, compare with breakeven/min target and WB min_price guard | compare in kopecks | Дмитрий/backend / `needs_api_discovery` | price draft, import, liquidation | WB-06, WB-22, WB-23 |
| P_max validation | selected price plane, СПП, strategy cap, OOS cap | valid/blocked reason | convert to after-SPP plane, enforce strategy/global caps | compare in kopecks | Мария/backend / `confirmed` | strategy dry-run, manual draft | WB-15 |

## 3. Strategy formulas

| formula | inputs | output/units | rule | rounding | owner/status | used by | blockers |
|---|---|---|---|---|---|---|---|
| Strategy 4599 baskets/orders | baskets trend, orders trend, current price, caps | recommended price delta percent | Maria 2x2 matrix: baskets/orders up/down -> +3/+1/-1/-3 percent, then guards/caps | price rounded to kopecks/rubles according to price API rule | Мария confirmed principle, backend source pending / `needs_api_discovery` | repricer dry-run, price draft | WB-03, WB-23 |
| Strategy 4600 revenue dynamics | revenue/sales trend, settings mode | recommended delta | mode is required in settings per strategy version: `percent_only` or `percent_rub_floor` | mode-specific | Мария / `needs_api_discovery` | repricer strategies | WB-03 |
| Night mode | schedule, current price, median target, price guards | scheduled draft/apply | off-by-default; run in chosen night window only after approval/audit | same as price API | Мария / `needs_client` | repricer strategies | WB-25 |
| Strategy 4445 СПП/turnover | СПП, turnover, stock, business thresholds | none in v1 | no production formula until Maria confirms; keep `disabled/discovery_required` | none | Мария / `disabled` | source registry only | WB-25 |

## 4. Ads and RNP formulas

| formula | inputs | output/units | rule | rounding | owner/status | used by | blockers |
|---|---|---|---|---|---|---|---|
| CTR | clicks, impressions | percent | `clicks / impressions * 100` | 2 decimals | Backend / `needs_api_discovery` | ads, RNP | WB-02 |
| ATCR | carts, card views or clicks | percent | denominator must be confirmed by Maria: `carts / cardViews` or `carts / clicks` | 2 decimals | Мария / `needs_client` | RNP |  |
| Orders conversion from clicks | orders, clicks | percent | `orders / clicks * 100` | 2 decimals | Backend / `draft` | RNP |  |
| Orders conversion from carts | orders, carts | percent | `orders / carts * 100` | 2 decimals | Backend / `draft` | RNP |  |
| CPC | ad spend, clicks | kopecks/click | `adSpendKopecks / clicks` | integer kopecks | Backend / `needs_api_discovery` | ads, RNP | WB-02 |
| CPO | ad spend, orders | kopecks/order | `adSpendKopecks / orders` | integer kopecks | Backend / `needs_api_discovery` | ads, RNP | WB-02 |
| ДРР | ad spend, attributed sales | percent | `adSpendKopecks / salesKopecks * 100` | 1 decimal | Мария + backend / `confirmed` | ads review candidates, P&L context | WB-02, WB-20 |
| ROI | attributed revenue, ad spend | ratio/percent | `ROI = (revenueKopecks - adSpendKopecks) / adSpendKopecks * 100` (sales-based) | 1 decimal | Мария + Максим / `confirmed` | RNP, P&L | WB-02 |
| Ads review stop candidate | observation days, ДРР, spend, OOS, new SKU, promo/liquidation, attribution | recommendation enum | draft: days >= 21, ДРР >= 25%, spend >= 150000 kopecks, no guards, attribution exact/campaign_sku | n/a | Мария / `needs_client` | ads review queue | WB-20 |

## 5. ABC, rating and product status

| formula | inputs | output/units | rule | rounding | owner/status | used by | blockers |
|---|---|---|---|---|---|---|---|
| ABC sales letter | period sales by SKU | A/B/C | A = top 20%, B = next 30%, C = bottom 50% | rank by selected period | Confirmed in data contract / `confirmed` | ABC report, filters | WB-09 |
| ABC profit letter | period profit by SKU | A/B/C | A = top 20%, B = next 30%, C = bottom 50% | rank by selected period | Needs final profit inputs / `needs_api_discovery` | ABC report, filters | WB-03 |
| Product status | sales, profit, stock, age, INDEEPA/Vella thresholds | status enum | thresholds for locomotive/new/weak/unprofitable/liquidation not final | n/a | Мария / `needs_client` | ABC, RNP, liquidation, repricer filters | WB-19 |
| Filtered locomotive aggregates | filtered SKU set | count/sales/profit/margin etc. | first aggregate set after 19.05 needs confirmation | standard report rounding | Мария / `needs_client` | ABC summary | WB-19A |

## 6. Stock formulas

| formula | inputs | output/units | rule | rounding | owner/status | used by | blockers |
|---|---|---|---|---|---|---|---|
| Available units | `wbStockUnits`, `fromClientUnits`, `toClientUnits` | units | `wbStockUnits + fromClientUnits`; do not add `toClientUnits` | integer units | Business rule from 8.05, fields pending / `needs_api_discovery` | stock, week-over-week, guards | WB-18 |
| Was OOS | available units | boolean | `availableUnits <= 0` | n/a | `confirmed` after snapshot source | week-over-week, ads guard, repricer guard | WB-18 |
| 7d stock histogram | daily availability by SKU | 7 booleans | aggregate all warehouses per SKU/day; available if sum available > 0 | n/a | `confirmed` after snapshots | week-over-week | WB-18, WB-23 |
| Snapshot coverage | days with snapshot, selected days | percent | `days_with_snapshot / selected_days * 100` | 0 decimals | `confirmed` | week-over-week fallback | WB-23 |
| Localization percent | local orders, all orders | percent | `localOrders / allOrders * 100` | 1 decimal | Мария table received, source pending / `needs_api_discovery` | stock, KTR, logistics | WB-01 |
| KTR index | localization percent, Maria range table | index/percent | lookup by localization range | table-specific | Мария/source pending / `needs_client` | stock economics, logistics | WB-01, WB-17 |
| Stock decision | available units, KTR/localization, orders/day, cluster/SKU | `норма`/`держать`/`дозагрузить` | final formula required | n/a | Мария / `needs_client` | stock report, repricer guards | WB-17 |

## 7. P&L and plan-fact formulas

| formula | inputs | output/units | rule | rounding | owner/status | used by | blockers |
|---|---|---|---|---|---|---|---|
| Buyer revenue tax base | WB sales/orders revenue | kopecks | buyer revenue before WB commission and logistics | integer kopecks | Максим/backend / `needs_api_discovery` | P&L tax, margin | WB-03 |
| Storage allocation | storage period expense | kopecks/period | separate expense line from WB source; no SKU/manager allocation in v1 | integer kopecks | Максим / `confirmed` | P&L, margin, ABC |  |
| OPEX allocation | total OPEX, manual period value | kopecks | manual period expense input; no SKU/manager allocation in v1 | integer kopecks | Максим / `manual_fallback` | P&L, plan-fact |  |
| Plan-fact deviation | plan, fact | kopecks and percent | `fact - plan`; percent = `fact / plan * 100` | kopecks + 1 decimal | backend + client plan source / `needs_client` | digest, plan-fact | WB-14A, WB-24 |
| Forecast minimum per day | remaining plan, days left | kopecks/day | `(plan - fact) / remainingDays` where plan/fact available | integer kopecks | backend / `draft` | plan-fact | WB-14A |

## 8. Liquidation formulas

| formula | inputs | output/units | rule | rounding | owner/status | used by | blockers |
|---|---|---|---|---|---|---|---|
| Liquidation candidate | turnover, stock, baskets, orders, ads spend, margin, product status | candidate/reason | criteria and AND/OR logic required from Maria | n/a | Мария / `needs_client` | liquidation report, repricer | WB-04 |
| Liquidation price decrease | current price, min allowed margin, schedule, approval | price draft series | smooth decrease every 24h only after approval; negative margin only by explicit rule | same as price API | Мария/Максим / `needs_client` | liquidation flow | WB-04, WB-06, WB-22 |

## 9. Backend rules

- Store formula version on every calculated recommendation, draft and report aggregate.
- Store source snapshot/evidence refs for every price recommendation and finance aggregate.
- If any critical input is `stale`, `partial`, `unknown` or `blocked`, downstream formula must expose the weakest state.
- UI labels can be simplified, but API must preserve formula/source status.
