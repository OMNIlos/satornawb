# SATORNA: инвентаризация ABC/P&L перед canonical projection

Дата discovery: 2026-09-03

Исследованная база: `1c9dd5a` (`codex/satorna-period-finance`)

Статус: discovery only; реализация, tests, schema, migrations, handoff и production не изменялись

## 1. Вывод

Минимальная правильная база для следующего backend slice уже существует: `GET /api/v2/wb/reports/abc-pnl`. Этот путь строго изолирован по tenant/account, читает immutable canonical finance projection, сохраняет signed finance facts и unattributed-строку, выбирает COGS и economics на каждый Moscow business date и не вызывает WB из HTTP (`app/routers/wb_reports_v2.py:147`, `app/modules/wb_reports/abc_pnl.py:411`).

Он пока не является финальным ABC/P&L:

- множество строк finance-led, а не union всех продуктовых источников;
- advertising и loyalty не канонизированы;
- `netProfitKopecks`, `profitClass` и `abcCode` намеренно `null`;
- source freshness не имеет отдельного состояния `stale`;
- top-level identity не содержит rules/source revisions;
- текущий размер ответа не измерен.

Рекомендованный следующий bounded slice — расширить существующий v2 contract только доказанным canonical advertising subtotal и union `finance ∪ advertising`, оставить финальную прибыль и profit-класс за loyalty blocker. Новый endpoint, универсальный reporting engine, новый response cache, group-by/export/UI и распределение 1С-расходов в этот slice не нужны.

Legacy Sprint D/BFF нельзя использовать как canonical основу. Он полезен как карта источников и consumer compatibility, но зависит от repricer snapshots/module globals, смешивает `missing` с `0`, распределяет unattributed finance пропорционально SKU и имеет несовместимую с v2 модель доступа.

## 2. Границы и доказательства

Discovery выполнен только по локальным документам, коду, тестам, fixtures и сохранённому production evidence. GitHub, production, WB API и новые live snapshots не использовались.

Термины в отчёте:

- **canonical v2** — `app/platform/finance/*`, `app/platform/catalog/*`, `app/platform/economics/*` и `app/modules/wb_reports/abc_pnl.py`;
- **legacy direct** — `/api/v1/wb-reports/{pnl,abc}` и `app/wb_reports_sprint_d.py`;
- **legacy generic/BFF** — `/api/wb/reports/{report_id}`, его report cache и Celery builders;
- **local live evidence** — ранее зафиксированный факт наблюдения, а не вечная константа источника.

Авторитетный handoff фиксирует текущую формулу `wb-abc-pnl-economics-v1`, незакрытые ads/loyalty и требование не восстанавливать отсутствующую корректировку (`/Users/ilagulakin/Desktop/Work/OgniWB/SATORNA_ARCHITECTURE_HANDOFF.md:76`, `:102`, `:120`). Старый production audit датирован 2026-08-26 и используется только как исторический baseline (`/Users/ilagulakin/Desktop/Work/OgniWB/.worktrees/backend-wb-abc-production/docs/wb-abc-production-audit-2026-08-26.md:1`).

## 3. Current-flow map

### 3.1. Canonical v2 read path

```text
GET /api/v2/wb/reports/abc-pnl
→ get_finance_actor + finance:read + tenant/account membership scope
→ Period.resolve (inclusive Moscow dates, max 90 days)
→ WbAbcPnlService.get_page
→ FinanceService.get_pnl_source
→ exact/covering canonical finance snapshot in PostgreSQL
→ exact SKU P&L rollup | daily rollup | immutable operation fallback
→ CatalogService.resolve_wb_product_skus
→ CostsService.get_costs_for_points + EconomicsService.get_policies_for_points
→ signed settlement/economics formula
→ Pydantic response + full-result summary + page slice
```

Опорные узлы:

- route, параметры, access и period resolution: `app/routers/wb_reports_v2.py:147-183`;
- org/account access: `app/platform/finance/access.py:17-66`;
- Moscow inclusive period → UTC half-open interval и temporal state: `app/platform/period.py:16-71`;
- orchestration: `app/modules/wb_reports/abc_pnl.py:411-554`;
- snapshot selection и P&L read strategy: `app/platform/finance/service.py:1350-1373`, `:1454-1524`;
- response mapping и identity metadata: `app/routers/wb_reports_v2.py:30-144`;
- response schema: `app/modules/wb_reports/schemas.py:11-98`.

В этом flow нет application response cache, repricer globals или WB adapter. HTTP читает только локальную canonical DB projection. Это подтверждено тестовым guard, который заставляет тест падать при попытке вызвать WB (`tests/test_abc_pnl_v2.py:204-239`).

### 3.2. Canonical finance write path

```text
Celery repricer sync / manual repricer source refresh
→ repricer_bff.fetch_finance_report_aggregates
→ WB /api/finance/v1/sales-reports/detailed pagination
→ raw rows + legacy aggregates
→ shadow_ingest_legacy_finance_payload (до удаления raw rows)
→ FinanceService.ingest_snapshot
→ immutable operations + snapshot membership delta
→ SKU, SKU-P&L и daily-SKU-P&L rollups
→ atomic materialized flags/commit
→ legacy source cache сохраняется уже без raw rows
```

- scheduler producer: `app/repricer_sync.py:1397-1419`;
- manual/router producer: `app/routers/wb_repricer_bff.py:1453-1483`;
- WB adapter, pagination и dedupe: `app/repricer_bff.py:3430-3516`;
- shadow bridge prerequisites and whitelist: `app/platform/finance/service.py:1587-1660`;
- immutable ingest/materialization: `app/platform/finance/service.py:1179-1348`;
- operation, membership and rollup grains: `app/platform/finance/orm.py:27-343`;
- legacy cache removes raw `rows`: `app/repricer_cache/store.py:735-789`.

`/api/v2/wb/reports/abc-pnl` не имеет отдельного Celery builder. Его producer — canonical finance shadow ingest внутри существующих sync flows. Если `finance_shadow_ingest_enabled` выключен, организация не в whitelist, raw rows уже удалены или у org не ровно один WB account, v2 projection не обновится (`app/platform/finance/service.py:1593-1628`, `:1650-1659`).

### 3.3. Legacy direct Sprint D

```text
GET /api/v1/wb-reports/pnl | /api/v1/wb-reports/abc
→ settings:read; finance:read превращается в finance_allowed flag
→ build_pnl_report | build_abc_report
→ exact/covering repricer source-cache snapshots
→ repricer runtime/algorithm settings + goods/content cache
→ legacy formula
→ direct P&L response cache | direct ABC response
```

- endpoints: `app/routers/wb_reports_sprint_d.py:37-80`, `:169-210`;
- P&L cache/read/build: `app/wb_reports_sprint_d.py:559-654`, `:901-1158`, `:1292-1340`;
- ABC snapshot builder: `app/wb_reports_sprint_d.py:1837-2231`, `:2263-2284`;
- legacy union: `app/wb_reports_sprint_d.py:1906-1916`;
- runtime settings dependency: `app/wb_reports_sprint_d.py:919-936`, `:1902-1904`.

Read path не обращается к WB: при cache miss он возвращает blocked/empty report. Источники наполняются отдельным repricer sync.

### 3.4. Legacy generic BFF и background build

```text
GET /api/wb/reports/{abc|pnl}
→ settings:read + finance_allowed flag
→ exact generic report-cache lookup
→ cached payload or empty background state
→ (для cold ABC) Sprint D builder, затем repricer-list fallback
→ rules decoration
→ response

POST .../{report_id}/jobs | .../refresh-sources-job
→ reports.build_report_for_org | reports.refresh_report_sources_for_org
→ cached sources only | WB source refresh then build
→ Sprint D ABC/P&L builder
→ rules decoration
→ generic report payload cache + job cache
```

- generic GET and cache branches: `app/routers/wb_reports_bff.py:4593-4696`;
- cold ABC and repricer fallback: `app/routers/wb_reports_bff.py:4741-4814`, `:2626-2651`;
- P&L mapper and attached 1C payload: `app/routers/wb_reports_bff.py:2854-2887`;
- job/refresh/status endpoints: `app/routers/wb_reports_bff.py:4845-4964`;
- refresh and cache-only builders: `app/repricer_tasks.py:199-514`;
- scheduled snapshot materialization: `app/repricer_tasks.py:1312-1470`, `:1544-1571`, `:1621-1762`;
- beat schedule: `app/infra/celery_app.py:36-39`.

`reports.refresh_report_sources_for_org` — единственный report task из этой пары, который сам инициирует WB refresh; `reports.build_report_for_org` строит только из cache (`app/repricer_tasks.py:199-285`, `:288-514`). Discovery эти tasks не запускал.

## 4. Поверхности API и producers

| Surface | Роль | Access/current behavior | Cache/source |
|---|---|---|---|
| `GET /api/v2/wb/reports/abc-pnl` | canonical ABC/P&L base | строго `finance:read`, org/account scope | canonical DB; без response cache и WB (`app/routers/wb_reports_v2.py:147-189`) |
| `GET /api/v1/wb-reports/pnl` | legacy direct P&L | требует только `settings:read`; `finance:read` — flag | Sprint D P&L cache (`app/routers/wb_reports_sprint_d.py:37-80`) |
| `GET /api/v1/wb-reports/abc` | legacy direct ABC | требует только `settings:read`; finance может быть restricted внутри payload | repricer snapshots (`app/routers/wb_reports_sprint_d.py:169-210`) |
| `GET /api/v1/wb-export/current-view` | legacy current-view export consumer | `settings:read`, finance flag | runtime export builder (`app/routers/wb_reports_sprint_d.py:284-317`) |
| `GET /api/wb/reports/{report_id}` | generic `abc`/`pnl` consumer | `settings:read`, finance flag | generic DB payload cache (`app/routers/wb_reports_bff.py:4593-4696`) |
| `GET /api/wb/reports/{report_id}/latest-cache` | inspect latest `abc`/`pnl` result | generic report auth | latest compatible payload (`app/routers/wb_reports_bff.py:4288-4408`) |
| `POST /api/wb/reports/{report_id}/jobs` | async build request | generic report auth | Celery job/cache (`app/routers/wb_reports_bff.py:4845-4904`) |
| `POST /api/wb/reports/{report_id}/refresh-sources-job` | WB refresh + build | generic report auth | source refresh task (`app/routers/wb_reports_bff.py:4907-4941`) |
| `GET /api/wb/reports/{report_id}/jobs` | build state | generic report auth | job cache (`app/routers/wb_reports_bff.py:4944-4964`) |
| `GET/POST /api/wb/reports/export/{report_id}` | generic export/read request | export/report auth | row estimator invokes ABC/P&L builders (`app/routers/wb_reports_bff.py:4449-4543`, `:2600-2622`) |
| `GET /api/wb/reports/export/jobs/{export_id}` | export job state | export auth | export store (`app/routers/wb_reports_bff.py:4546-4564`) |
| rules GET/history/preview | affects generic row decoration and ABC cache identity | organization rules access | active version/profile (`app/routers/wb_reports_bff.py:4108-4209`) |

Background producers:

| Task | Что производит | WB network |
|---|---|---|
| `reports.refresh_report_sources_for_org` | period finance/ads/funnel/etc., затем report payload | да (`app/repricer_tasks.py:199-285`) |
| `reports.build_report_for_org` | generic ABC/P&L payload из уже готовых caches | нет (`app/repricer_tasks.py:288-514`) |
| `repricer.materialize_report_snapshot_extra_window` | дополнительное cache-only окно | нет (`app/repricer_tasks.py:1544-1571`) |
| `repricer.materialize_report_snapshots_for_org/all_orgs` | 1/7/14/30 report snapshots | нет, только существующий source cache (`app/repricer_tasks.py:1621-1762`) |
| `repricer.sync_wb_data_for_org`, onboarding/nightly и all-org wrappers | source caches; finance shadow ingest; затем snapshots | да (`app/repricer_tasks.py:2034-2433`) |

## 5. Canonical source, grain и mapping

| Данные | Physical/canonical grain | Правило |
|---|---|---|
| Finance operation | `(organization_id, marketplace_account_id, operation_id)` | `source_identity=rrd:<rrdId>`; без положительного `rrdId` — fingerprint нормализованной операции. Конфликт одинаковой source identity с разным checksum запрещён (`app/platform/finance/service.py:352-427`, `app/platform/finance/orm.py:116-188`) |
| Finance snapshot | `(org, account, dateFrom, dateTo, snapshotChecksum)` | immutable membership delta к parent snapshot; только materialized snapshot видим читателю (`app/platform/finance/orm.py:27-113`, `app/platform/finance/service.py:1232-1348`) |
| Period SKU P&L | `(org, account, syncRunId, nmId)` | `nmId=0` — storage sentinel, декодируется в `null`; все signed components суммируются (`app/platform/finance/orm.py:261-300`, `app/platform/finance/service.py:948-1020`) |
| Daily SKU P&L | `(org, account, syncRunId, businessDate, nmId)` | источник point-in-time COGS/economics (`app/platform/finance/orm.py:303-343`) |
| Catalog SKU | `(org, catalogSkuId/code)` | внутренняя товарная сущность (`app/platform/catalog/orm.py:13-39`) |
| WB product | `(org, account, external_product_id=nmId)` | account-scoped product identity (`app/platform/catalog/orm.py:42-74`) |
| Marketplace offer | `(org, marketplaceProduct, externalOfferKey) → catalogSkuId?` | nullable link к CatalogSku (`app/platform/catalog/orm.py:77-116`) |
| Cost | `(org, catalogSkuId, effectiveFrom, version)` | amount в копейках + value/evidence state (`app/platform/economics/costs.py:109-119`, `:297-350`) |
| Economics | org policy version + optional `(org, catalogSkuId)` override version | override field-by-field поверх org policy на instant (`app/platform/economics/policies.py:592-759`) |
| Advertising (legacy only) | WB campaign/source row → агрегат `nmId` | canonical таблицы/revision для ABC/P&L отсутствуют; legacy cache используется в `app/wb_reports_sprint_d.py:1858-1860` |
| Loyalty (legacy only) | WB finance row → `nmId` aggregate | есть в repricer aggregate, отсутствует в canonical finance operation/P&L schema (`app/wb_reports_sprint_d.py:192-199`, `app/platform/finance/orm.py:176-185`) |
| 1C cash flow | `(org, period, cash-flow rows)` | generic P&L прикладывает report-level `cashFlow`, но не включает его в SKU net-profit (`app/routers/wb_reports_bff.py:2854-2887`) |

Mapping `nmId → product → offer → CatalogSku` считается безопасным только при ровно одном ненулевом `catalogSkuId`. Ноль связей даёт missing mapping, больше одной — ambiguous; угадывания по `vendorCode`, garment/type или первому offer нет (`app/platform/catalog/service.py:178-227`).

## 6. Signed finance normalization

Canonical money сначала переводится в копейки через `Decimal` + `ROUND_HALF_UP`; нечисловое и non-finite значение отвергается, а отсутствующее поле нормализуется в `0` (`app/platform/finance/service.py:217-233`). Затем:

| Компонент | Source / знак | Canonical result |
|---|---|---|
| Units | `quantity`, только doc types «Продажа»/«Возврат» | sale `+q`, return `-q` (`app/platform/finance/service.py:287-295`) |
| Revenue | `retailAmount` | sale positive, return negative |
| Commission | `ppvzSalesCommission` fallback aliases | умножается на document sign (`app/platform/finance/service.py:296-302`) |
| Acquiring | `acquiringFee` | умножается на document sign (`app/platform/finance/service.py:303`) |
| Logistics | `deliveryService`/aliases | source-signed amount, дополнительный document sign не применяется (`app/platform/finance/service.py:340-342`) |
| Storage | `paidStorage`/aliases | source-signed (`app/platform/finance/service.py:343-345`) |
| Acceptance | `paidAcceptance`/alias | source-signed (`app/platform/finance/service.py:346`) |
| Penalty | `penalty` | source-signed; positive later expense, negative compensation (`app/platform/finance/service.py:347`, `app/modules/wb_reports/abc_pnl.py:295-302`) |
| Deduction | `deduction` | source-signed; positive expense, negative compensation. Строка `bonusTypeName~WB продвижение` обнуляется, чтобы не дублировать advertising (`app/platform/finance/service.py:304-308`) |
| Additional payment | `paymentSchedule - additionalPayment` | positive compensation; negative finance-other-expense (`app/platform/finance/service.py:309-310`, `app/modules/wb_reports/abc_pnl.py:297-302`) |
| Report type | `1/main`, `2/redemptions`, иначе unknown | late correction выносится из main/redemptions в отдельный bucket (`app/platform/finance/service.py:261-263`, `:321-335`, `:906-930`) |
| Business date | `saleDt`, иначе `rrDate`, в Europe/Moscow | может быть `null`, что блокирует dated COGS/economics для соответствующего факта (`app/platform/finance/service.py:311-317`) |

P&L aggregation сохраняет:

- `revenueKopecks` как signed net revenue;
- `salesRevenueKopecks` как сумму revenue строк с positive units;
- `returnsRevenueKopecks` как положительную величину `-revenue` строк с negative units;
- `salesUnits`, `returnsUnits` как неотрицательные magnitudes и `netUnits` как signed total;
- main, redemptions, late correction и unknown как взаимоисключающие revenue buckets (`app/platform/finance/service.py:885-946`).

Поздняя операция определяется явным `isLateCorrection` либо `rrDate` после `period.dateTo`. Это классификация реально полученной raw operation; код не создаёт отсутствующую операцию (`app/platform/finance/service.py:321-335`).

## 7. Canonical формулы

Для одной строки обозначим signed finance fact как `F`.

```text
penaltyExpense   = max(0, F.penalty)
deductionExpense = max(0, F.deduction)
financeOther     = max(0, -F.additionalPayment)
compensation     = max(0, F.additionalPayment)
                 + max(0, -F.penalty)
                 + max(0, -F.deduction)

financeExpenses  = commission + logistics + storage + acceptance
                 + penaltyExpense + deductionExpense + financeOther
                 + acquiring - compensation

settlementProfit = signedRevenue - COGS - financeExpenses
profitBeforeAdsAndLoyalty
                 = settlementProfit - tax - otherExpenses
```

Реализация: `app/modules/wb_reports/abc_pnl.py:282-362`.

### 7.1. COGS

```text
COGS(nmId, period) = Σday netUnits(nmId, day)
                           × cost(catalogSkuId, endOfMoscowBusinessDay)
```

`endOfMoscowBusinessDay` переводится в UTC; cost point lookup берёт последнюю версию с `effectiveFrom <= instant` (`app/modules/wb_reports/abc_pnl.py:117-122`, `:155-193`, `app/platform/economics/costs.py:297-350`). Signed `netUnits` означает, что возвраты могут обращать COGS, а не только уменьшать его до нуля.

Текущий edge case: если daily list пуста, `_cost_result` без проверки period fact возвращает COGS `0/configured` (`app/modules/wb_reports/abc_pnl.py:164-165`). Поэтому finance fact с ненулевыми units, но без `business_date`, может получить ложный нулевой COGS. Economics защищён отдельной daily-coverage сверкой (`app/modules/wb_reports/abc_pnl.py:204-215`), COGS — пока нет. Следующий slice должен требовать `Σ daily netUnits == fact.netUnits`; только доказанный нулевой fact может вернуть COGS `0`.

### 7.2. Tax и other expenses

Daily basis содержит signed revenue и positive sales units. Для каждого непрерывно одинакового набора policy amounts:

```text
tax   = roundHalfEven(groupSignedRevenue × taxBasisPoints / 10_000)
other = roundHalfEven(groupSignedRevenue × otherBasisPoints / 10_000)
        + groupSalesUnits × otherExpensePerSaleKopecks
```

Итог — сумма policy groups. Это не округление каждой raw operation и не применение period-end policy ко всему периоду (`app/modules/wb_reports/abc_pnl.py:195-279`). Basis-point rounding signed half-even определён в `app/modules/wb_reports/abc_pnl.py:130-136`; он намеренно отличается от source-money `ROUND_HALF_UP`.

### 7.3. ABC

Текущий v2 сортирует attributed facts по `revenue desc, netUnits desc, nmId asc`, затем присваивает `A` первым 20% строк, `B` следующим 30%, `C` остальным. Это ранжирование по количеству SKU, не cumulative revenue share (`app/modules/wb_reports/abc_pnl.py:125-127`, `:480-490`). Unattributed row в ранжирование не входит.

`profitClass`, `abcCode` и `netProfitKopecks` всегда `null`; глобальные blockers — `WB_PNL_ADS_NOT_CANONICAL` и `WB_PNL_LOYALTY_NOT_CANONICAL` (`app/modules/wb_reports/abc_pnl.py:23-27`, `app/modules/wb_reports/schemas.py:45-49`). Поэтому любой непустой v2 result сейчас `partial` (`app/modules/wb_reports/abc_pnl.py:533-550`).

### 7.4. Rules versions

Canonical v2 не читает active report rules. Его sales thresholds зашиты в formula version, и `rulesVersion` в response отсутствует.

Legacy generic path загружает active org profile из DB, затем memory/default fallback; default version равен `1`, активация создаёт immutable `version+1` (`app/report_rules/store.py:55-83`, `:102-159`). Конфигурация ABC принудительно нормализуется к `FIXED_ABC`, а rules evaluator декорирует строки bands/actions (`app/report_rules/service.py:27-48`, `:94-149`). Generic ABC economics hash включает profile id/version/config (`app/routers/wb_reports_bff.py:3371-3402`).

Решение для canonical contract должно быть одним из двух: считать ranking полностью фиксированной частью `formulaVersion` либо действительно применять active rules и публиковать `rulesVersion`. Неявное смешение запрещено.

## 8. Union-SKU и unattributed semantics

Canonical v2 строит строки только из `FinancePnlSource.facts`; catalog-only, funnel-only, ads-only, prices-only и stock-only SKU отсутствуют (`app/modules/wb_reports/abc_pnl.py:424-426`, `:449-493`). Следовательно, это finance-led base, а не целевой union projection.

Legacy ABC, напротив, делает union положительных `nmId` из finance, baskets/funnel, period stats, ads, stock и current goods (`app/wb_reports_sprint_d.py:1906-1916`). Но он:

- отбрасывает `nmId <= 0`;
- использует `vendorCode`/runtime settings вместо canonical CatalogSku mapping;
- преобразует отсутствующие/невалидные числа в `0` (`app/wb_reports_sprint_d.py:222-256`);
- формирует финальную прибыль из источников с различной identity/freshness.

Legacy WB adapter собирает finance rows без `nmId` отдельно и распределяет их между SKU пропорционально seller revenue (`app/repricer_bff.py:419-460`, `:3518-3525`, `:3707`). Это изменяет provenance и запрещено для canonical projection.

Canonical v2 сохраняет все finance facts, включая ровно одну агрегированную строку `nmId=null`; summary включает её деньги/операции, а `skuCount` — нет (`app/modules/wb_reports/abc_pnl.py:365-409`, `:492-550`). COGS/economics для неё `null` с явными blockers. Такой подход должен остаться: unattributed никогда не распределяется без подтверждённой allocation policy.

## 9. `null`, `0`, states и access

| Семантика | Canonical v2 | Legacy |
|---|---|---|
| `0` | derived layer использует ноль для доказанного empty basis, configured cost `0` разрешён. Но raw finance adapter также превращает отсутствующее денежное поле в `0`, а COGS сейчас возвращает `0` при пустом daily list: provenance нуля закрыт не полностью (`app/platform/finance/service.py:217-233`, `app/modules/wb_reports/abc_pnl.py:164-165`) | parser превращает `None`, bool, invalid string и unknown type в `0` (`app/wb_reports_sprint_d.py:222-256`) |
| `null` | значение нельзя безопасно вычислить: missing/ambiguous mapping, missing dated value, daily coverage mismatch, unattributed product, final ads/loyalty fields | часть отсутствий `null`, часть уже потеряна как `0` |
| `missing` | нет covering snapshot или нет cost/economics/mapping point | часто cache miss/blocker, но числовые поля могут остаться zero-filled |
| `assumed` | numeric value разрешено показать, но blocker сохраняется; не равно configured | runtime default/fallback часто неразличим с configured |
| `blocked` | выражен blocker IDs и зависимые поля `null`; source state vocabulary отдельно | report-level status/blockers, неоднородно по builders |
| `restricted` | весь route запрещается HTTP 403 при отсутствии `finance:read`; это не числовое состояние | finance flag скрывает только отдельные поля |

Canonical source states: `future`, `missing`, `empty`, `ready`, `partial` (`app/modules/wb_reports/schemas.py:80-88`). Finance source способен вернуть `ready`, но ABC/P&L переводит любой непустой результат в `partial`, пока присутствуют global blockers (`app/platform/finance/service.py:1454-1524`, `app/modules/wb_reports/abc_pnl.py:538-540`).

Cost/economics value states — `configured | assumed | missing`, evidence — `dated | undated | period_end_fallback` (`app/modules/wb_reports/schemas.py:37-44`). `restricted` существует в общем economics API schema, но не является row state v2 ABC/P&L (`app/platform/economics/schemas.py:10`).

Access mismatch требует отдельного cutover решения:

- v2 требует `finance:read` и account membership (`app/routers/wb_reports_v2.py:158-159`);
- direct/generic legacy требует лишь `settings:read` и передаёт `finance_allowed` в builder (`app/routers/wb_reports_sprint_d.py:45-62`, `app/routers/wb_reports_bff.py:4603-4613`);
- legacy P&L при `finance_allowed=false` скрывает только `overheadKopecks`, но продолжает отдавать revenue, commission, tax, ads и уже рассчитанный net profit (`app/wb_reports_sprint_d.py:1019-1042`, `:1121-1150`);
- generic report-cache identity не включает finance permission, поэтому cached payload нельзя считать actor-safe (`app/routers/wb_reports_bff.py:3405-3421`, `:4674-4695`).

Это подтверждённый code-level disclosure risk внутри организации. До retirement/feature-flag legacy routes нельзя объявлять canonical access semantics закрытой.

## 10. Cache, revisions и invalidation

| Слой | Key/identity | TTL/freshness | Invalidation/проблема |
|---|---|---|---|
| Canonical v2 response | отсутствует | отсутствует | пересчёт из DB на каждый запрос; текущий latency gate проходит без app cache |
| Canonical finance snapshot | org + account + period + snapshot checksum + `wb-finance-v1` | `lastObservedAt`, но нет TTL/`stale` state | exact period preferred, затем newest covering snapshot (`app/platform/finance/service.py:1350-1373`) |
| v2 formula identity | `wb-abc-pnl-economics-v1`, snapshot metadata, `costLedgerRevision`, `economicsRevision` | request-time | cost/economics пересчитываются; нет `sourceRevision`/`rulesVersion` (`app/routers/wb_reports_v2.py:115-141`) |
| Repricer source cache | DB `(organization_id, source_key)`; finance basis `retailAmount/v3` | DB rows физически не expire; consumers применяют age rules | exact key upsert; raw finance rows удаляются; Redis exact keys удаляются (`app/repricer_cache/store.py:19-27`, `:735-789`) |
| Repricer Redis front | org/source key only для allowlist | 45 s | finance/report payloads обычно не допускаются в Redis (`app/repricer_cache/store.py:17`, `:132-196`) |
| Direct legacy P&L | hash `v3|dates|group|requestedState|finance|nofinance` | fresh 24h; stale 24h | stale branch недостижим, потому TTL равны; key не содержит source/cost/economics/rules revision (`app/wb_reports_sprint_d.py:52-54`, `:559-654`) |
| Generic ABC | `v16 + economicsHash + org + dates + group + source` | logical 24h | economics hash включает runtime settings/history/rules, но не source snapshot revision (`app/routers/wb_reports_bff.py:3362-3416`, `:3467-3540`) |
| Generic P&L | `reports_payload_pnl_dates_group_source` | logical 24h | org изолирован DB row, но key не содержит permission, formula/source/economics/rules revision (`app/routers/wb_reports_bff.py:3405-3416`) |
| Generic job | report/dates/group; source suffix только для P&L | stale job guards 30s/15m | не является result identity (`app/routers/wb_reports_bff.py:3357-3363`, `:3419-3421`) |
| Report rules | org active profile id/version/config | без TTL | DB → module memory → default fallback (`app/report_rules/store.py:20`, `:69-83`) |

Новый v2 response cache не нужен до измеренного нарушения SLO. Если он всё же потребуется, минимальная identity обязана включать:

```text
org + account + period + formulaVersion + rulesVersion
+ costRevision + economicsRevision + eachSourceRevision
+ stable sort/filter/page/column projection
```

Revision mismatch должен делать cache miss; wildcard deletion не должна быть единственным механизмом корректности.

## 11. Прямые зависимости от repricer state

Canonical v2 read path от них свободен. Legacy пути зависят от:

- module-level dictionaries и cache TTL constants в `app/repricer_bff.py:900-913`;
- DB → file → memory fallback для runtime/algorithm state (`app/repricer_persistence/store.py:27-30`, `:128-199`);
- hydration module globals перед request/list fallback и snapshot materialization (`app/routers/wb_reports_bff.py:2626-2651`, `app/repricer_tasks.py:1656-1743`);
- flush module globals назад в runtime state, включая реконструированную COGS history (`app/repricer_persistence/store.py:446-492`);
- current algorithm settings, SKU overrides, garment defaults и active rules в legacy economics hash (`app/routers/wb_reports_bff.py:3371-3402`).

Это process-local mutable state с file fallback `var/vella_repricer_runtime_state.json`; параллельные org requests/tasks требуют корректной hydration discipline. Переносить эту модель в canonical slice нельзя.

## 12. Legacy formula differences

Legacy ABC helper вычитает COGS, commission, logistics, storage, acceptance, penalty, deduction, finance-other, acquiring, loyalty, ads, tax и other expenses, затем прибавляет compensation (`app/wb_reports_sprint_d.py:169-219`). В отличие от v2:

- P&L использует `max(0, salesUnits-returnsUnits)` и current runtime COGS, а не day-specific cost ledger (`app/wb_reports_sprint_d.py:945-976`);
- ABC использует daily COGS helper, но может fallback к period end и runtime history (`app/wb_reports_sprint_d.py:787-837`);
- missing ads даёт `0` spend и `partial`, а не `null` dependent profit (`app/wb_reports_sprint_d.py:964-976`, `:1013-1018`);
- active promotion deduction может считаться authoritative ads spend, тогда как canonical normalizer только исключает её из deduction и нигде не сохраняет как advertising (`app/wb_reports_sprint_d.py:1085-1101`, `app/platform/finance/service.py:304-308`);
- final two-letter ABC ранжирует и sales, и уже рассчитанную net profit (`app/wb_reports_sprint_d.py:2129-2136`);
- 1C `cashFlow` прикладывается к generic P&L, но формула строк/total не меняется (`app/routers/wb_reports_bff.py:2854-2887`).

Одновременное подключение finance promotion deduction и Ads API без authority/dedup rule создаст double count. Это главный источник, который надо решить до advertising slice.

## 13. Frozen fixture, local live evidence и gaps

### 13.1. Frozen fixture

`tests/fixtures/wb_abc_2026_08_17_23.json:1-20` фиксирует:

```text
main                 602,842,752 kopecks
redemptions           32,694,699 kopecks
late correction          120,800 kopecks
frozen total         635,658,251 kopecks
```

Но сама fixture говорит `lateCorrectionEvidence=derived_live_snapshot_delta` и `rawLateCorrectionIdentityAvailable=false` (`tests/fixtures/wb_abc_2026_08_17_23.json:17-18`). Unit helper затем синтезирует три illustrative rows и присваивает корректировке выдуманный `rrdId=3` (`tests/test_finance_service.py:80-91`). Этот тест доказывает арифметику/bucket exclusivity, но не закрывает raw-operation evidence gate.

`tests/test_abc_pnl_v2.py:148-165` также содержит обычную продажу на 1,208.00 RUB; она не является восстановленной late correction.

Запрещено переносить любой из этих synthetic IDs в canonical data или считать fixture текущим WB truth.

### 13.2. Time-bounded local production evidence

По handoff, без повторного live запроса:

- исторический период 2026-08-17…2026-08-23: 62,465 операций, 929 attributed SKU, 635,537,451 коп. (`SATORNA_ARCHITECTURE_HANDOFF.md:83`);
- предыдущий 7d snapshot 2026-08-27…2026-09-02: 48,529 операций, 848 SKU, 634,901,083 коп. (`SATORNA_ARCHITECTURE_HANDOFF.md:84`);
- 30d 2026-08-04…2026-09-02: 271,211 операций, 1,228 SKU, 2,983,463,860 коп. (`SATORNA_ARCHITECTURE_HANDOFF.md:85`);
- в каждом измеренном окне сохранялась одна unattributed sentinel row; dated-economics coverage различается по исторической глубине (`SATORNA_ARCHITECTURE_HANDOFF.md:95`).

Текущий повторный источник уже не содержит 120,800 коп. и raw `rrdId` не сохранён (`SATORNA_ARCHITECTURE_HANDOFF.md:102`). Поэтому существуют два разных acceptance объекта:

1. **frozen regression** — воспроизводимость сохранённого evidence bundle при наличии всех raw identities;
2. **current source reconciliation** — точное равенство текущему immutable snapshot на момент наблюдения.

Ни один нельзя заменять другим; historic live number не является вечной константой.

### 13.3. Необъяснённые/незакрытые gaps

- Нет raw identity для исторических 120,800 коп.; frozen raw-operation gate открыт.
- Нет canonical advertising ledger/revision и решения об authority между promotion deduction и Ads API.
- Нет canonical loyalty source, grain, sign и revision.
- Нет политики SKU allocation для 1C operating expenses; существующий generic path только прикладывает payload.
- Нет полного target union в v2.
- Нет explicit `stale` state/TTL для canonical source snapshot; `lastObservedAt` доступен, но policy отсутствует.
- Нет source/rules revision в top-level v2 identity.
- Нет COGS daily-coverage guard: ненулевой fact без `business_date` может выглядеть как configured zero COGS.
- Отсутствующее raw finance money field нормализуется в zero; required/optional field completeness отдельно не публикуется.
- Нет измерения serialized/compressed v2 response size.
- Нет решения о lifecycle legacy routes/caches и несовместимом access contract.

## 14. Performance и response size

Current canonical v2 authenticated p50/p95, 25 запросов, quiet window:

| Окно | p50 | p95 |
|---|---:|---:|
| 7d | 152.55 ms | 343.83 ms |
| 30d | 394.28 ms | 445.30 ms |
| custom | 151.70 ms | 332.04 ms |

Все значения ниже gate `p95 ≤ 500 ms` без application cache (`SATORNA_ARCHITECTURE_HANDOFF.md:96`). Canonical finance projection DB-only baseline был 7d `7.01/9.08 ms`, 30d `8.22/10.31 ms`; route — `20.92/23.92 ms` и `25.36/27.92 ms` (`SATORNA_ARCHITECTURE_HANDOFF.md:89`). Разница объяснима дополнительными catalog/cost/economics lookups и row formula.

Upstream sync не входит в request SLO: зафиксированный 30d fetch занял 151.578 s, delta ingest 399.629 s (`SATORNA_ARCHITECTURE_HANDOFF.md:85`).

Для legacy v16 полный ответ на 3,339 строк составлял 6,558,954 bytes uncompressed, exact-cache HTTP p50/p95 — 481.50/637.56 ms (`SATORNA_SPEC_AUDIT.md:264-272`; local audit `:143-144`). Это исторический baseline другого контракта, а не размер v2.

Current v2 bounded `limit=100`, maximum `500` (`app/routers/wb_reports_v2.py:151-156`), но byte size ни для default page, ни для maximum page не сохранён. Следующий canary должен измерять response bytes after serialization и transfer bytes with actual compression; до этого нельзя заявлять size gate.

## 15. Blockers и риски

| Приоритет | Blocker/risk | Последствие | Gate/решение |
|---|---|---|---|
| P0 | Legacy access/cache не actor-safe по `finance:read` | finance fields/net profit доступны settings-only actor; cached payload не partitioned по permission | закрыть/feature-flag legacy financial routes либо enforce strict finance access до cutover |
| P0 | Frozen correction без raw identity | невозможно доказать immutable operation reconciliation на 635,658,251 | отдельный evidence gate; никогда не синтезировать 120,800 |
| P1 | Ads не canonical | `profitBeforeAdsAndLoyalty` — последний доказанный subtotal; final fields null | выбрать authority, grain, dedup и source revision |
| P1 | Loyalty не canonical | final net profit/profit rank/ABC code недоказуемы | определить source, sign, business date, attribution и revision |
| P1 | V2 finance-led, не union | ads/catalog/funnel/stock-only SKU теряются | bounded ads slice: `finance ∪ ads`; full union — отдельный gate |
| P1 | Promotion deduction исключён из canonical deduction, но не сохранён как ads | возможная потеря expense либо double count при подключении Ads API | explicit authority/dedup tests |
| P1 | Canonical source без stale policy | закрытый период может измениться в WB, а старый snapshot выглядеть ready | freshness policy + source state/revision |
| P1 | COGS не сверяет daily coverage с period net units | fact без business date может получить ложный configured zero | exact daily-units equality; mismatch → `null` + blocker |
| P2 | Raw finance missing field → zero | source omission неотличим от доказанного zero | определить required fields/coverage diagnostics для каждой component |
| P2 | 1C report-level only | “P&L with 1C expenses” не соответствует SKU formula | оставить unallocated/report-level до принятия allocation policy |
| P2 | Generic/direct TTL/revision drift | stale result и несовместимые consumer ожидания | не переносить cache; retirement test либо отдельный legacy fix |
| P2 | V2 response size неизвестен | нельзя подтвердить network/memory budget | измерить default/max page в canary |

## 16. Минимальный canonical contract

### 16.1. Endpoint и inputs

Переиспользовать:

```http
GET /api/v2/wb/reports/abc-pnl
```

Inputs следующего slice:

- actor organization — только из auth context;
- обязательный `marketplaceAccountId` с tenant/account membership check;
- либо `periodDays=1..90`, либо полная пара `dateFrom/dateTo`, inclusive Europe/Moscow;
- `limit=1..500`, `offset>=0`;
- фиксированный stable sort `revenue desc, затем attributed при равной revenue, затем nmId asc`.

Не добавлять пока `groupBy`, произвольные filters, column projection, export или второй endpoint. Sort/filter надо версионировать и включать в cache identity только когда появится подтверждённый consumer.

### 16.2. Row grain и union

Одна строка на `(org, account, period, nmId)` плюс не более одной явной `nmId=null` unattributed finance row.

Для следующего ads slice:

```text
row ids = finance nmIds ∪ canonical advertising nmIds ∪ {unattributed if present}
```

Full cutover gate позже расширяет union до требуемых catalog/funnel/prices/stock sources. Ads-only expansion нельзя называть полным target union.

### 16.3. Outputs

Сохранить текущие signed finance fields, COGS/economics states и subtotal. Добавить только при наличии canonical ads source:

- `adSpendKopecks: int | null`;
- `advertisingValueState/evidenceStatus` либо единый source state в meta;
- `profitBeforeLoyaltyKopecks = profitBeforeAdsAndLoyaltyKopecks - adSpendKopecks` при полной row attribution;
- explicit blocker для unattributed ad spend.

До canonical loyalty:

- `netProfitKopecks=null`;
- `profitClass=null`;
- `abcCode=null`;
- `WB_PNL_LOYALTY_NOT_CANONICAL` остаётся.

1C operating expenses остаются отдельным report-level subtotal/state и не распределяются по SKU без утверждённой policy.

### 16.4. Summary и pagination

- `summary` считается по полному union до `offset/limit`;
- `total` включает unattributed row;
- `skuCount` считает только attributed `nmId`;
- если хотя бы одна строка не имеет безопасного COGS/economics/ads subtotal, соответствующий aggregate и все downstream profit aggregates остаются `null`, а не суммируют только calculable subset;
- classes считаются по полному attributed set до pagination;
- tie-break deterministic и покрыт тестом.

### 16.5. Source states

Минимальный vocabulary:

- `ready` — полный immutable source coverage и все обязательные revisions;
- `partial` — текущий день либо хотя бы один downstream blocker;
- `missing` — обязательного source snapshot нет;
- `empty` — доказанный snapshot есть, операций/строк нет;
- `future` — период полностью в будущем;
- `stale` — snapshot вышел за утверждённую freshness policy;
- `restricted` — не payload state, а HTTP 403.

На уровне значения сохранить `configured | assumed | missing`; `assumed` всегда сопровождается blocker, `0` не используется как substitute для missing.

### 16.6. Version identity

Meta должна однозначно описывать результат:

```text
formulaVersion
rulesVersion | fixedRulesVersion
finance: syncRunId + snapshotChecksum + formulaVersion + lastObservedAt
advertising: sourceRevision + observedAt + attributionVersion
costLedgerRevision
economicsRevision
period/timezone
```

`sourceRevision` должен быть immutable identity, а не только timestamp. Пока rules фиксированы в коде, достаточно отдельного `fixedRulesVersion` внутри formula contract; нельзя публиковать active legacy rules version, если v2 его не применял.

### 16.7. Cache policy

Оставить без application response cache, пока p95 проходит. При измеренной необходимости добавить bounded page cache с полной identity из §10 и revision-based miss. Canonical DB rollups уже являются projection, поэтому ещё один универсальный caching layer сейчас не обоснован.

## 17. Boundary следующего bounded slice

### Входит

- существующий v2 route/service/schema;
- адаптер к уже доказанному canonical/cached advertising source без WB из HTTP;
- immutable advertising revision/evidence;
- union `finance ∪ ads` и explicit unattributed ads;
- ad subtotal и `profitBeforeLoyalty`;
- source state/identity;
- access, exact-money, pagination/summary и p95/size gates.

### Не входит

- loyalty и final `netProfit/profitClass/abcCode`;
- 1C SKU allocation;
- catalog/funnel/prices/stock full union;
- generic group-by/filter/export/UI;
- новый report/rules/cache framework;
- перенос repricer globals или file fallback;
- изменение legacy routes без отдельного security/retirement decision;
- WB calls, новый live snapshot или восстановление 120,800 коп.

## 18. Acceptance gates

| Gate | Критерий |
|---|---|
| HTTP purity | v2 read path не вызывает WB и не читает repricer globals |
| Access | без `finance:read` — 403; чужой account — 403/404; cached response не пересекает actor/org/account scope |
| Signed finance | sale/return/redemption/late/unknown и все expense/compensation buckets сходятся до 1 копейки |
| Raw identity | correction учитывается только при наличии реальной immutable operation identity/fingerprint; 120,800 не синтезируется |
| Formula | `financeExpenses`, settlement, dated COGS/economics и ads subtotal проверены independently reconstructed totals |
| Mapping | missing/ambiguous `nmId→CatalogSku` никогда не угадывает COGS/economics |
| Date | COGS/economics выбираются на конец каждого Moscow business date; `Σ daily netUnits == period fact.netUnits`; mid-period version changes покрыты |
| States | missing/assumed/unattributed/stale дают `null` + blocker; evidenced zero остаётся `0` |
| Union | ads-only и finance-only SKU присутствуют; unattributed row сохраняет summary totals |
| Pagination | summary/classes инвариантны от limit/offset; stable tie-break |
| Periods | 1/7/14/30/custom, current/future/empty/missing/stale |
| Identity | изменение finance/ads/cost/economics/rules revision меняет result identity/cache outcome |
| Performance | authenticated quiet-window p95 ≤ 500 ms на 7d/30d/custom, 25 запросов на окно |
| Size | зафиксированы uncompressed serialized bytes и compressed transfer bytes для default/max page |
| Regression | нет новых failure IDs сверх сохранённого full-suite baseline 105; focused canonical suite зелёный |

## 19. Тестовая матрица

| Область | Текущее доказательство | Gap / следующий тест |
|---|---|---|
| Money/sign normalization | `tests/test_finance_normalization.py:45-127` | добавить source-specific ads sign/dedup cases |
| Immutable snapshot/delta | `tests/test_finance_service.py:94-133`; `tests/test_finance_pnl_rollup.py:85-317` | frozen fixture не имеет raw late identity; не считать synthetic row evidence |
| Finance P&L components | `tests/test_finance_pnl_rollup.py:85-317` | independently reconstructed ads-inclusive subtotal |
| Dated COGS | `tests/test_abc_pnl_costs.py:146-296`; `tests/test_abc_pnl_service.py:155-227` | ads-only SKU без finance units должен иметь explicit COGS semantics |
| COGS daily coverage | отсутствует | ненулевой fact без business date и incomplete daily rollup должны давать `null` + blocker, не configured zero |
| Mapping ambiguity | `tests/test_abc_pnl_service.py:249-299` | union source mapping conflicts across accounts |
| Unattributed facts | `tests/test_abc_pnl_service.py:301-331` | unattributed advertising и no-allocation assertion |
| Pagination/classes | `tests/test_abc_pnl_service.py:333-425` | union/ties при page boundaries |
| Dated economics | `tests/test_abc_pnl_service.py:427-524`; `tests/test_economics_policies.py:37+` | partial ads coverage must null downstream summary |
| API purity/access | `tests/test_abc_pnl_v2.py:204-269` | actor-safe response-cache test, если cache когда-либо появится |
| Shadow bridge | `tests/test_finance_shadow_bridge.py:20+`; `tests/test_period_finance_legacy_bridge.py` | multiple-account explicit routing вместо silent skip — отдельный scope |
| Legacy P&L cache | targeted test `tests/test_sprint_d_reports.py::test_pnl_report_response_is_cached_for_two_hours` сейчас расходится с implementation | решить: вернуть 2h/24h или обновить retirement expectation; stale branch при 24h/24h недостижим |
| Performance/size | локально сохранённый route p95; legacy bytes baseline | измерить v2 bytes и ads-inclusive p95 в canary |

Fresh local focused run на исследованной базе:

```text
python -m pytest -q \
  tests/test_finance_normalization.py \
  tests/test_finance_pnl_rollup.py \
  tests/test_abc_pnl_costs.py \
  tests/test_abc_pnl_service.py \
  tests/test_abc_pnl_v2.py \
  tests/test_economics_policies.py \
  tests/test_finance_shadow_bridge.py \
  tests/test_period_finance_legacy_bridge.py

43 passed, 5 warnings in 2.51s
```

Targeted legacy cache test дал `1 failed`: fixture не содержит обязательные `revenueBasis=retailAmount`/`financeSchemaVersion=v3` и всё ещё ожидает TTL 7,200/86,400 s, тогда как implementation публикует 86,400/86,400 s (`app/wb_reports_sprint_d.py:52-54`). Отдельный локальный compatible-payload harness подтвердил один finance read и фактические TTL. Это существующий contract/test drift, не дефект canonical v2 и не исправлялся в discovery.

Последний авторитетный full backend baseline из handoff — `476 passed / 105 failed`; те же 105 legacy failures были зафиксированы без новых/missing/error IDs (`SATORNA_ARCHITECTURE_HANDOFF.md:97`). Full suite в read-only discovery повторно не запускался.

## 20. Решения, требующие подтверждения

1. Следующий slice действительно ограничен `finance ∪ advertising`, а полный catalog/funnel/prices/stock union остаётся отдельным этапом?
2. Что authoritative для advertising expense: finance promotion deduction, Ads API attribution или deterministic reconciliation двух источников?
3. Каков canonical loyalty source: поля, grain, sign, business date, attribution и revision?
4. 1C operating expenses остаются report-level/unallocated или должны распределяться; если да, по какой утверждённой базе?
5. Подтверждается ли правило: unattributed finance/ads показываются отдельной строкой и никогда не распределяются pro rata автоматически?
6. ABC thresholds — фиксированная часть formula version или active org report-rules profile? Нужен один вариант и его identity.
7. Каков response-size ceiling для default/max page и требуется ли compressed-transfer gate?
8. Какие legacy routes закрываются/feature-flagged при cutover и когда устраняется settings-only доступ к finance payload?
9. Release gate использует два независимых набора: frozen raw-evidence bundle и current-source snapshot, без требования вечного live равенства 635,658,251?

## 21. Рекомендация к старту реализации

Начинать с существующего `WbAbcPnlService`, не с legacy builders. До кода зафиксировать только три решения: advertising authority/dedup, ads union/unattributed semantics и version identity. После этого минимальный slice сводится к одному canonical source adapter, расширению текущей row/summary formula и одному набору acceptance checks; всё остальное остаётся за границей.
