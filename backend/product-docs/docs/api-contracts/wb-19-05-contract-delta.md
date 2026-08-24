# WB contract delta после созвона 19.05

**Источник:** `Встречи/19.05/meeting-protocol-backlog-2026-05-19.md`
**Связано:** `docs/handoffs/wb-19-05-action-backlog.md`, `docs/handoffs/wb-19-05-vella-gap-check.md`, `docs/open-questions-current.md`
**Статус:** draft для Zod/OpenAPI. Это не финальный контракт и не доказательство доступности WB-источников.
**Runtime:** frontend mock/repository boundary подключен через Zod sidecar validation; backend должен повторить те же инварианты в Pydantic/FastAPI.

**Frontend draft schemas:**

- `frontend/src/features/wb-contracts/sourceState.ts`
- `frontend/src/features/wb-reports/schemas.ts`
- `frontend/src/features/wb-repricer/schemas.ts` (`PriceGuardResponseSchema`)

**Backend reference:** `backend_contracts/vella_wb_19_05/` mirrors these invariants as Pydantic models, stub builders and a FastAPI router for Sprint A handoff. It is a transfer package, not a production backend.

## Зачем этот файл

Созвон 19.05 уточнил не новые экраны, а contract gaps. Перед backend-реализацией нужно зафиксировать, какие ответы API обязаны уметь показывать `blocked`, `partial`, `stale` и `confidence`, вместо того чтобы возвращать декоративный mock.

Этот delta закрывает только 19.05:

- P&L mapping и финансовый источник;
- реклама и РНП;
- агрегаты ABC по текущему фильтру;
- SPP-aware guard/freeze в репрайсере;
- brand dimension для plan-fact, если клиент подтвердит;
- approval gate для AI reviews.

## Общие типы

Все новые report/action endpoints должны использовать общие поля источника и надежности.

| Поле | Тип | Обязательно | Смысл |
|---|---|---:|---|
| `sourceStatus` | `fresh | partial | stale | blocked | unknown` | Да | Можно ли использовать данные для production-расчета. |
| `confidence` | `high | medium | low | blocked` | Да | Насколько надежна метрика или строка. |
| `blockerIds` | `string[]` | Да | Ссылки на `docs/open-questions-current.md`, если источник не закрыт. |
| `sourceEvidence` | `SourceEvidence[]` | Да | Какие источники/выгрузки/API участвовали в расчете. |
| `calculatedAt` | ISO UTC datetime | Да | Когда расчет выполнен. |
| `period` | `{dateFrom,dateTo}` | Да | Период отчета в ISO date. |

`SourceEvidence`:

| Поле | Тип | Смысл |
|---|---|---|
| `sourceId` | string | Внутренний ID источника из source registry. |
| `sourceType` | `wb_api | wb_excel | manual | derived | mock` | Откуда пришли данные. |
| `sourceName` | string | Человекочитаемое имя источника. |
| `lastSyncedAt` | ISO UTC datetime/null | Последняя синхронизация. |
| `freshnessTtlMinutes` | integer/null | TTL свежести. |
| `fieldsUsed` | string[] | Поля/колонки, которые реально использовались. |

Правило: если `sourceStatus` = `blocked` или `unknown`, endpoint не должен отдавать видимость финального production-расчета. Он возвращает typed blocker state и список недостающих источников.

## 1. P&L report

**Backlog:** `M19-PNL-01` - `M19-PNL-04`
**Blockers:** `WB-03`, `WB-12`, `WB-13`, `WB-23`

Draft endpoint:

```text
GET /api/v1/wb-reports/pnl?dateFrom=YYYY-MM-DD&dateTo=YYYY-MM-DD&source=operational|financial&groupBy=sku|brand|manager|category|status
```

Response fields:

| Поле | Тип | Смысл |
|---|---|---|
| `reportState` | `operative | preliminary | final | blocked` | Финальный P&L недоступен без подтвержденных расходов/налогов. |
| `totals` | `PnlTotals` | Свод по периоду. |
| `rows` | `PnlRow[]` | Разрез по `groupBy`. |
| `fieldMapping` | `PnlFieldMapping[]` | Метрика -> источник -> поле -> формула -> fallback. |
| `manualCosts` | `ManualCost[]` | Налоги, хранение, общие расходы, если вводятся руками. |
| `dayAllocation` | `DayAllocationSummary` | Как продажи/расходы разложены по дням. |
| `sourceEvidence` | `SourceEvidence[]` | Источники расчета. |
| `blockerIds` | `string[]` | Открытые вопросы. |

Минимальный `PnlRow`:

| Поле | Тип |
|---|---|
| `rowId` | string |
| `label` | string |
| `brandId` | string/null |
| `managerId` | string/null |
| `skuId` | string/null |
| `revenueKopecks` | integer/null |
| `cogsKopecks` | integer/null |
| `commissionKopecks` | integer/null |
| `logisticsKopecks` | integer/null |
| `storageKopecks` | integer/null |
| `adSpendKopecks` | integer/null |
| `taxKopecks` | integer/null |
| `overheadKopecks` | integer/null |
| `netProfitKopecks` | integer/null |
| `marginPct` | number/null |
| `sourceStatus` | common enum |
| `confidence` | common enum |

Acceptance для контракта:

- каждая P&L-метрика имеет `fieldMapping`;
- финальный state запрещен, если верхний или вложенный source-state содержит blockers: totals, rows, field mapping, manual costs, day allocation;
- day-level allocation явно описывает дату продажи/отчета/расхода;
- слабая рекламная атрибуция не маскируется как точная SKU-прибыль.

## 2. Ads normalized layer

**Backlog:** `M19-ADS-01`, `M19-ADS-02`
**Blockers:** `WB-02`, `WB-03`, `WB-23`

Draft endpoint:

```text
GET /api/v1/wb-reports/ads/performance?dateFrom=YYYY-MM-DD&dateTo=YYYY-MM-DD&groupBy=sku|campaign|brand|manager
```

Response fields:

| Поле | Тип | Смысл |
|---|---|---|
| `totals` | `AdsTotals` | Spend, показы, клики, корзины, заказы, DRR, ROMI/ROI. |
| `rows` | `AdsPerformanceRow[]` | Нормализованные строки рекламы. |
| `attributionPolicy` | `AdsAttributionPolicy` | Как spend связан с SKU/кампанией. |
| `sourceEvidence` | `SourceEvidence[]` | Endpoint/export/XLSX. |
| `blockerIds` | string[] | Обычно `WB-02`, пока источник не доказан. |

`AdsPerformanceRow`:

| Поле | Тип |
|---|---|
| `rowId` | string |
| `campaignId` | string/null |
| `skuId` | string/null |
| `brandId` | string/null |
| `managerId` | string/null |
| `adSpendKopecks` | integer/null |
| `impressions` | integer/null |
| `clicks` | integer/null |
| `cartAdds` | integer/null |
| `ordersCount` | integer/null |
| `ordersKopecks` | integer/null |
| `drrPct` | number/null |
| `romiPct` | number/null |
| `roiPct` | number/null |
| `attributionLevel` | `exact_sku | campaign_sku | campaign_only | unknown` |
| `confidence` | common enum |

Правило: `campaign_only` нельзя автоматически раскладывать в SKU P&L как точную прибыль. UI может показывать его как campaign-level или partial.

## 3. РНП report

**Backlog:** `M19-RNP-01`, `M19-RNP-02`
**Blockers:** `WB-02`, `WB-11`, `WB-23`

Draft endpoint:

```text
GET /api/v1/wb-reports/rnp?dateFrom=YYYY-MM-DD&dateTo=YYYY-MM-DD&groupBy=sku|brand|manager|status
```

Response must include:

| Поле | Тип | Смысл |
|---|---|---|
| `rows` | `RnpRow[]` | РНП по выбранному разрезу. |
| `adSpendKopecks` | integer/null | Реклама за тот же период. |
| `drrPct` | number/null | Формула должна быть согласована с Марией/Максимом. |
| `formulaNotes` | string[] | Какие базы использованы для ДРР/ROI/маржи. |
| `adsSourceStatus` | common enum | Отдельный статус рекламного источника. |

Acceptance:

- период рекламы совпадает с периодом РНП;
- если `WB-11` не закрыт, `drrPct` может быть `null`, а endpoint возвращает blocker;
- если `WB-02` не закрыт, строки не должны выглядеть как точная SKU-атрибуция.

## 4. ABC filtered summary

**Backlog:** `M19-ABC-01` - `M19-ABC-03`
**Blockers:** `WB-09`, `WB-19`, `WB-19A`

Draft endpoint:

```text
GET /api/v1/wb-reports/abc?dateFrom=YYYY-MM-DD&dateTo=YYYY-MM-DD&filters=...
```

Response must include `filteredSummary`:

| Поле | Тип | Смысл |
|---|---|---|
| `filterHash` | string | Хэш текущего набора фильтров. |
| `skuCount` | integer | Количество SKU в выбранном наборе. |
| `locomotiveCount` | integer/null | Количество локомотивов, если фильтр/статус применим. |
| `ordersCount` | integer/null | Количество заказов. |
| `ordersKopecks` | integer/null | Заказы/продажи в рублях по согласованной базе. |
| `profitKopecks` | integer/null | Чистая прибыль. |
| `marginPct` | number/null | Маржа выбранного набора. |
| `adSpendKopecks` | integer/null | Реклама по выбранному набору, если источник надежен. |
| `sourceStatus` | common enum | Статус расчета. |
| `confidence` | common enum | Надежность summary. |

Acceptance:

- `filteredSummary` пересчитывается при изменении фильтров;
- summary не должен быть статичным mock-card;
- если реклама недоступна, только `adSpendKopecks`/рекламные метрики становятся partial/blocked, а не весь ABC.

## 5. Repricer SPP guard/freeze

**Backlog:** `M19-REP-01` - `M19-REP-04`
**Blockers:** `WB-06`, `WB-14`, `WB-22`, `WB-23`

Draft endpoint:

```text
GET /api/v1/wb-repricer/sku/{articleId}/price-guard
```

Response fields:

| Поле | Тип | Смысл |
|---|---|---|
| `articleId` | string | WB/internal article. |
| `currentPriceKopecks` | integer/null | Текущая цена продавца. |
| `buyerPriceKopecks` | integer/null | Цена покупателя после SPP, если вычислима. |
| `sppSnapshot` | `SppSnapshot/null` | Состояние SPP. |
| `recommendedSellerPriceKopecks` | integer/null | Рекомендация с учетом SPP. |
| `lastKnownGoodPriceKopecks` | integer/null | Последняя безопасная цена. |
| `canApply` | boolean | Можно ли отправлять цену. |
| `blockedReason` | string/null | Причина блокировки. |
| `freezeState` | `none | frozen | requires_review | source_blocked` | Guard-состояние. |
| `guardTriggers` | `GuardTrigger[]` | Какие скачки обнаружены. |
| `sourceEvidence` | `SourceEvidence[]` | Откуда взяты цена, SPP, остатки, COGS. |
| `blockerIds` | string[] | Открытые blockers. |

`GuardTrigger`:

| Поле | Тип |
|---|---|
| `type` | `stock_jump | spp_jump | cogs_jump | seller_price_jump | source_stale` |
| `severity` | `info | warning | blocker` |
| `observedValue` | number/string/null |
| `previousValue` | number/string/null |
| `threshold` | number/string/null |
| `message` | string |

Acceptance:

- если источник SPP неизвестен, `canApply=false` для SPP-aware apply;
- если `canApply=true`, `freezeState=none`, `blockedReason=null`, `blockerIds=[]`, нет blocker triggers и SPP snapshot fresh без blockers;
- frontend не вычисляет freeze сам, только отображает состояние backend;
- рублевый шаг стратегии должен быть частью typed settings, а не отдельной UI-логикой.

## 6. Plan-fact brand dimension

**Backlog:** `M19-PLAN-02`, `WB-14A`
**Статус:** включать только после подтверждения Марии/Максима.

Draft endpoint:

```text
GET /api/v1/wb-reports/plan-fact?dateFrom=YYYY-MM-DD&dateTo=YYYY-MM-DD&dimension=company|manager|brand
```

Contract change:

| Сейчас | Нужно, если brand подтвержден |
|---|---|
| `owner: company | manager` | `dimension: company | manager | brand` |
| brand только как filter/groupBy | brand может быть владельцем плановой строки |
| нет явной связки brand -> manager | нужна связка `brandId`, `managerId`, `responsibilityPct/null` |

Acceptance:

- не создавать отдельный отчет `план-факт по брендам`;
- сохранить единый plan-fact endpoint;
- если brand plan не подтвержден, endpoint остается company/manager.

## 7. AI reviews approval gate

**Backlog:** `M19-AI-01`, `M19-AI-02`
**Связано:** `docs/architecture/agent-harness-standard.md`, `docs/evals/ai-agent-evals.md`

Draft contract requirements:

| Поле/действие | Требование |
|---|---|
| `rating` < 4 | Только draft, external send blocked until approval. |
| `draftId` | Обязателен для audit and approval. |
| `approvalState` | `not_required | required | approved | rejected | expired`. |
| `approvalActorId` / `approvedAt` | Обязательны для `approved`. |
| `externalSendAllowed` | `true` только после прохождения approval/permission gate. |
| `sendState` | `draft_only | ready_to_send | sent | blocked`. |
| `brandVoiceId` | Обязателен, если используются разные тоны брендов. |
| `promptTraceId` | Обязателен для AI audit. |
| `cacheMetrics` | Логировать cached tokens/hit rate where applicable. |
| `send` action | Только через permission + approval gate. |

Acceptance:

- auto-send для низких оценок невозможен contract-level без `approved`, approval evidence и `externalSendAllowed=true`;
- draft можно пересоздать, отредактировать и отклонить;
- audit хранит акторов: AI draft, manager approval, external send.

## Что не входит в этот delta

- Полный OpenAPI YAML.
- Реальная проверка WB endpoints.
- Pydantic model generation.
- UI implementation.
- Service Token package как API contract: это project ops/docs blocker, а не endpoint Vella.

## Следующий конкретный шаг

1. Сгенерировать OpenAPI artifact из Zod schemas.
2. Отдать backend-разработчику на review по реализуемости и WB API ограничениям.
3. Повторить runtime invariants в Pydantic/FastAPI.
4. После review обновить `docs/api-contracts/README.md` inventory: draft -> reviewed.
