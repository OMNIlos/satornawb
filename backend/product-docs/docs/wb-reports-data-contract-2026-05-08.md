# WB Reports Data Contract — 2026-05-08

Источник: созвон с Марией `Встречи/Созвон по Отчётам 8.05/` и backlog `reports-backlog-2026-05-08.md`.

Цель документа: зафиксировать frontend/backend контракт v1. Это не финальная схема БД и не обещание доступности всех полей WB API.

## Общие правила

- Единый период управляет всеми KPI, таблицами, графиками и export.
- Brand scope управляет всеми KPI, таблицами, графиками и export так же, как период. Если `brandIds` не передан, backend считает все бренды; если передан один или несколько id, фильтр применяется до агрегации, а не после неё на фронте.
- Excel export остаётся в v1; PDF/share не входят в обязательный v1.
- Прямая 1С-интеграция вне v1.
- Пользовательский термин в UI: `Себестоимость`; внутреннее имя поля не показывается пользователю.
- P&L не показывает внутренние статусы согласования. Если значения нет, UI использует нейтральные состояния ячеек: `нет данных`, `не задано`, `ручной ввод`.
- ABC-пороги фиксированы: `A=20%`, `B=30%`, `C=50%`; UI не даёт менять эти проценты в v1.

## Metric Mapping Contract

Каждая метрика отчёта описывается одной строкой контракта:

| screen | metric | source | field | formula | fallback |
|---|---|---|---|---|---|
| `/wb/reports` | Маржинальная прибыль | reports aggregation | `marginProfitKopecks` | сумма по brand scope и периоду | `нет данных` |
| `/wb/reports/rnp` | Воронка SKU | RNP aggregation | `impressions/clicks/baskets/orders/sales` | значения периода + динамика к выбранному сравнению | `нет данных` по отсутствующим этапам |
| `/wb/reports/abc` | Себестоимость | cost import / manual SKU card | `costKopecks` | себестоимость единицы × продажи | `не задано` |
| `/wb/reports/pnl` | Налоговая база | WB sales/orders report | `buyerRevenueKopecks` | выручка покупателя до комиссии и логистики | `ручной ввод` |
| `/wb/reports/ads` | ДРР | WB Ads + sales attribution | `adSpendKopecks/salesKopecks` | расход рекламы ÷ продажи | `нет данных` |
| `/wb/reports/stock` | Доступно | stock snapshot | `availableUnits` | `wbStockUnits + fromClientUnits` | последний дневной snapshot |
| `/wb/reports/week-over-week` | Был OOS | daily stock snapshots | `wasOutOfStock` | `availableUnits <= 0` в выбранный день | `нет данных` |

## Acceptance surfaces: 10 отчетов WB

Отдельная route не обязательна для каждого названия, если отчет закрыт проверяемым блоком внутри Vella reports. Для QA важно фиксировать, где именно проверяется каждый тип:

| Требование из ТЗ | Проверяемая поверхность v1 | Комментарий |
|---|---|---|
| Сводный дайджест | `/wb/reports` | Главная аналитическая витрина с KPI и переходами в детализацию. |
| Продажи | `/wb/reports`, `/wb/reports/abc`, `/wb/reports/week-over-week` | Проверять рубли, штуки и динамику по периоду. |
| Заказы | `/wb/reports`, `/wb/reports/abc`, `/wb/reports/week-over-week` | Отчетный блок заказов не равен production `/orders`; это аналитика по заказам. |
| Остатки | `/wb/reports/stock` | Остатки WB, доступность, склады/кластеры и решения по stock. |
| Возвраты | `/wb/reports/pnl` | Финансовый учет возвратов/штрафов как строка P&L; отдельная Avito QR-returns route не входит в WB reports acceptance. |
| P&L | `/wb/reports/pnl` | Финансовый отчет без внутренних статусов согласования в UI; пустые поля показываются нейтральными состояниями. |
| Рентабельность / ABC | `/wb/reports/abc` | SKU-level рентабельность, ABC и управленческие статусы. |
| Реклама | `/wb/reports/ads` | Campaign/SKU attribution, ДРР, ROI и рекомендации. |
| Позиции / РНП | `/wb/reports/rnp` | Рабочая поверхность для карточки SKU, воронки, позиций и причин внимания. |
| Неделя-к-неделе | `/wb/reports/week-over-week` | Сравнение недель, динамики и OOS context. |

## Digest

Frontend expects:

| Field | Meaning | Source | Status |
|---|---|---|---|
| `brandScope` / query `brandIds[]` | Все бренды, один бренд или несколько брендов | SKU/product directory | Backend-stage |
| `planFactRows[]` | Компания + Анна + Ирина + Светлана | План от клиента + факт маржинальной прибыли | Needs source |
| `kpis[]` | Заказы, продажи, прибыль, маржа, корзины, реклама | Aggregated reports layer | Mock-ready |
| `charts[]` | План/факт и чистая прибыль | Aggregated reports layer | Mock-ready |
| `quickLinks[]` | Переходы в ABC, РНП, рекламу, остатки | Static frontend | Ready |

Digest must not show the large WB funnel block. Funnel belongs in RNP/details.

## ABC / статусы

Rows keep existing SKU-level fields and additionally expose:

| Field | Meaning | Status |
|---|---|---|
| `ordersComposite` | `units + kopecks + deltaPct` | Ready |
| `salesComposite` | `units + kopecks + deltaPct` | Ready |
| `logisticsCostPct` + `logisticsDeltaPct` | Current logistics % and delta | Needs formula validation |
| `commissionCostPct` + `commissionDeltaPct` | Current commission % and delta | Needs final field mapping |
| `storageCostPct` + `storageDeltaPct` | Current storage % and delta | Needs final field mapping |
| status profit cards | profit by `локомотив/новинка/средний/неликвид/ликвидация` | Needs INDEEPA criteria |

## RNP

Rows extend SKU data with:

| Field | Meaning | Status |
|---|---|---|
| `activeRule` | Current repricer strategy/rule for SKU | Needs repricer link |
| `impressionsDeltaPct`, `clicksDeltaPct`, `basketsDeltaPct`, `ordersComposite`, `salesComposite`, `adSpendDeltaPct` | Dynamics next to funnel/ads metrics | Needs snapshots |
| `comments[]` | SKU comments: date, author, text | Needs auth/actor model |
| `auditEvents[]` | Separate system and manager events | Needs event model |

## P&L

| Field | Meaning | Status |
|---|---|---|
| `taxBaseKopecks` | Buyer revenue before WB commission/logistics | Open formula inputs |
| `cogsKopecks` | Себестоимость for sold units | Needs import/source |
| `dataState` | `ok`, `no_data`, `not_set`, `manual_input` for neutral cell states | Ready |

Open with Maxim: tax percent, turnover thresholds, OPEX allocation, whether OPEX is SKU/category/period/global.

Tax base remains buyer revenue before WB commission and logistics. Final percentages and thresholds stay an open contract question, not a visible UI label.

## Ads

Campaign-first row:

| Field | Meaning | Status |
|---|---|---|
| `campaignId`, `campaignName`, `campaignType` | Main row identity | Needs WB Ads mapping |
| `manager`, `sku`, `nmId` | Filters/drill-down | Needs campaign-SKU relation |
| `attributionLevel` | `exact_sku`, `campaign_sku`, `campaign_only` | Ready as frontend/backend contract |
| `attributionSource` | `wb_ads_nm`, `campaign_product_list`, `campaign_name_match`, `manual_mapping`, `unknown` | Ready as frontend/backend contract |
| `attributionConfidencePct` | Confidence score shown in UI | Ready as frontend/backend contract |
| `observationDays` | Days included in the recommendation window | Ready |
| `impressions`, `clicks`, `ctrPct`, `baskets` | Funnel | Needs API/export |
| `orders`, `sales` | `units + kopecks + deltaPct` | Needs attribution rules |
| `adSpendKopecks`, `drrPct` | Spend and DRR | Needs final formula |
| `minSpendMet`, `hasOosInPeriod`, `isNewSku`, `isPromoOrLiquidation` | Guard flags for recommendations | Ready |
| `recommendation`, `recommendationReason`, `recommendationStatus=review_candidate` | Do not auto-stop; create a manager review candidate | Ready |

### Ads Attribution And Stop Rule

V1 recommendation: do not auto-disable WB ads. The system should produce a visible review queue:

- `keep`: DRR and funnel are within allowed range.
- `review`: high DRR or weak attribution, but one of the guards blocks a stop recommendation.
- `review_stop_candidate`: candidate for manager approval, not an automatic stop.

Attribution levels:

- `exact_sku`: WB Ads source provides `nmId`/SKU-level relation. This can be used for SKU P&L and stop recommendations.
- `campaign_sku`: campaign has a product list or manual campaign→SKU mapping. This can be used for recommendations, but UI must show lower confidence.
- `campaign_only`: campaign cannot be reliably split by SKU. Show campaign-level spend and DRR only; do not allocate to SKU P&L and do not recommend stop by SKU.

Draft stop rule:

```text
recommendation = review_stop_candidate only if:
  observationDays >= 21
  and drrPct >= 25
  and adSpendKopecks >= 150000
  and hasOosInPeriod == false
  and isNewSku == false
  and isPromoOrLiquidation == false
  and attributionLevel in ['exact_sku', 'campaign_sku']
```

If any guard fails, use `review` with a concrete `recommendationReason`. This keeps Maria's "3 weeks + high DRR" logic, while protecting launches, OOS periods, promos/liquidation and weak attribution.

## Price Bounds Contract

Repricer and reports share the same price-bound model so P_min/P_max is not ambiguous around СПП:

| Field | Meaning |
|---|---|
| `basis` | `before_spp` or `after_spp`; user edits only the selected basis. |
| `enteredMinKopecks`, `enteredMaxKopecks` | Values entered by the user in the selected basis. |
| `derivedMinKopecks`, `derivedMaxKopecks` | Readonly values derived into the opposite basis using current SKU СПП. |
| `sppPct` | СПП used for deriving the opposite basis. |
| `validation` | `ok`, `below_breakeven`, `min_gt_max`, `above_rrp`, `missing_cost`. |
| `auditReason` | Human-readable reason for manual changes, used in audit log. |

Margin is always calculated from the price after СПП. Promo/night actions use the same `23:00–06:00 МСК` night window as the night median strategy.

## Stock

Warehouse row:

| Field | Meaning | Status |
|---|---|---|
| `warehouseName`, `clusterName` | `SKU x склад WB x кластер` | Needs WB endpoint validation |
| `wbStockUnits` | Physical WB stock | Needs endpoint validation |
| `fromClientUnits` | Incoming to WB; added to availability | Needs field validation |
| `toClientUnits` | Going to buyer; not added to availability | Needs field validation |
| `availableUnits` | `wbStockUnits + fromClientUnits` | Business rule from 8.05 |
| `ktrIndex`, `localizationPct`, `logisticsPerUnitKopecks` | Warehouse economics | Needs Maria/backend discovery |
| `decisionStatus=review_candidate` | Do not finalize stock recommendation before formula | Ready |

Use `POST /api/analytics/v1/stocks-report/wb-warehouses` for discovery path because the old stock GET is being shut down.

## Week-over-week

| Field | Meaning | Status |
|---|---|---|
| `orders`, `sales`, `baskets`, `marginPct`, `profit` | Physical value + percent dynamic | Ready |
| `wasOutOfStock` | Whether SKU was OOS during period | Ready from daily stock snapshots |
| `stockAvailability7d` | 7 booleans for mini-histogram | Ready from daily stock snapshots |
| `stockOutDays` | Count of days with `availableUnits <= 0` in selected 7-day window | Ready from daily stock snapshots |
| `stockSnapshotCoveragePct` | Share of selected days covered by our snapshot history | Ready from daily stock snapshots |
| chart toggles | prices, margin, profit, sales, orders, baskets | Frontend-ready |

WB does not provide reliable historical stock retroactively for this UI. We need our own daily snapshots.

### Daily Stock Snapshots Backend Contract

Purpose: week-over-week must explain whether sales dropped because the product was unavailable, not because the current WB stock is low/high. Current WB stock is not enough; we need our own daily history.

Recommended table: `wb_stock_daily_snapshots`.

| Column | Type | Meaning |
|---|---|---|
| `id` | uuid/bigserial | Primary key |
| `snapshot_date` | date | Business date of the snapshot |
| `tenant_id` | uuid | SaaS tenant/account |
| `brand_id` | uuid/null | Optional brand scope |
| `sku` | text | Internal article, for example `FBBT_42` |
| `nm_id` | bigint | WB nomenclature id |
| `warehouse_id` | bigint/null | WB warehouse id when available |
| `warehouse_name` | text | WB warehouse name |
| `cluster_name` | text/null | Local cluster mapping |
| `wb_stock_units` | integer | Physical WB stock |
| `from_client_units` | integer | Return flow back to WB; included into available stock |
| `to_client_units` | integer | Delivery flow to buyer; shown separately, not included |
| `available_units` | integer | `wb_stock_units + from_client_units` |
| `was_out_of_stock` | boolean | `available_units <= 0` |
| `source` | text | Expected `wb_stocks_report` |
| `source_updated_at` | timestamptz/null | Timestamp reported by source, if any |
| `created_at` | timestamptz | Insert time |

Recommended unique key:

```sql
unique (tenant_id, snapshot_date, nm_id, warehouse_id)
```

If WB does not provide stable `warehouse_id`, use `(tenant_id, snapshot_date, nm_id, warehouse_name)` as a temporary unique key and migrate once ids are available.

Collection job:

- Run once daily after the operational WB sync, target time `08:00` local account time.
- Upsert same-day rows, never rewrite previous dates except explicit backfill/recovery.
- Store row per `SKU x WB warehouse`.
- Compute `available_units` and `was_out_of_stock` at ingestion time.
- Preserve `source_updated_at` and sync status for diagnostics.

Week-over-week aggregation:

- For each SKU and day, aggregate all warehouse rows.
- `day_available = sum(available_units) > 0`.
- `stockAvailability7d = last 7 day_available values`.
- `wasOutOfStock = any(day_available === false)`.
- `stockOutDays = count(day_available === false)`.
- `stockSnapshotCoveragePct = days_with_snapshot / selected_days * 100`.

Fallback rules:

- Before seven snapshots exist, show grey/partial state and coverage below 100%.
- Do not infer historical OOS from current WB stock.
- Do not use `to_client_units` in availability.
