# WB-03 Matrix: Frontend Reports vs Backend Contracts

Дата: 2026-06-01  
Статус: рабочая матрица для закрытия `WB-03` (endpoint/field mapping по отчетам WB).

## Источники

- Frontend contract/types: `../ogni-frontend/frontend/src/features/wb-reports/types.ts`
- Frontend API calls: `../ogni-frontend/frontend/src/features/wb-reports/api.ts`
- Frontend mocked HTTP routes: `../ogni-frontend/frontend/src/mocks/handlers.ts`
- Backend runtime routes: `app/routers/wb_reports_sprint_d.py`
- Backend response models: `backend_contracts/vella_wb_19_05/models.py`
- Backend runtime payload builders: `app/wb_reports_sprint_d.py`

## Короткий итог

- Frontend ожидает BFF-слой `/api/wb/reports/*` с unified shape `ReportResponse`/`DigestResponse`.
- Backend теперь отдает:
  - доменные Sprint-D ручки `/api/v1/wb-reports/*`;
  - BFF-ручки `/api/wb/reports/*` для фронт-интеграции.
- В WB adapter/runtime добавлены источники `orders/sales/reportDetailByPeriod/sales-reports-list/warehouse_remains/penalties/acceptance/paid_storage`.
- `commission/logistics` для production-final P&L теперь считаются из `reportDetailByPeriod` и сверяются через `sales-reports/list`.
- Главный residual risk: live semantic validation полей `sale_percent` и `dlv_prc`, плюс накопление собственной history таблицы для stock WoW.

## Endpoint Matrix

| Frontend endpoint (ожидает) | Зачем экрану | Backend сейчас | Статус | Что нужно для закрытия WB-03 |
|---|---|---|---|---|
| `GET /api/wb/reports/digest?preset&from&to` | Главный дайджест (`kpis`, `planFactRows`, `freshness`, `alerts`, `charts`, `problemRows`, `quickLinks`) | Есть BFF digest endpoint | Implemented | Уточнить content/формулы при UAT |
| `GET /api/wb/reports/:reportId` (`abc/rnp/pnl/ads/stock/week-over-week`) | Унифицированный экран отчета | Есть BFF report endpoint + stock/week-over-week | Implemented | Расширять глубину полей по мере подтверждения WB source mapping |
| `GET /api/wb/reports/pnl?...&source=operational|financial` | P&L с переключением источника | Есть BFF mapping `operational/financial` -> Sprint-D modes | Implemented | Нужна только live semantic validation финальных полей WB |
| `GET /api/wb/reports/alerts` | Алерты в дайджест/таблицы | Есть BFF alerts endpoint | Implemented | Доработать rule taxonomy при UAT |
| `GET /api/wb/reports/export/:reportId` | Экспорт конкретного отчета | Есть BFF export endpoint | Implemented | Подключить реальный export job |

## Field Coverage Matrix (по вкладкам отчетов)

| Report tab | Что ждет frontend | Что есть в backend | Покрытие |
|---|---|---|---|
| `digest` | `DigestResponse` (`planFactRows`, `freshness`, `alerts`, `charts`, `problemRows`) | Есть BFF агрегатор | Partial |
| `abc` | Большая SKU-таблица с `columns[]/rows[]`, composite полями (`ordersComposite`, `salesComposite`) | BFF shape есть, глубина полей пока ограничена runtime summary | Partial |
| `rnp` | Табличный `ReportResponse` + `comments[]`, `auditEvents[]`, динамики по воронке | BFF shape есть; comments/audit пока пустые placeholders | Partial |
| `pnl` | Табличный `ReportResponse`, `financialConfirmationStatus`, `warning`, `sourceType/freshnessState` | BFF mapping добавлен; финансы идут из realization details + finance reconciliation | Partial |
| `ads` | Campaign-first rows: `campaignName/type`, `orders/sales` как composite, `recommendation*` | BFF mapping добавлен поверх Ads attribution runtime | Partial |
| `stock` | `warehouseName`, `clusterName`, `availableUnits`, `ktrIndex`, `localizationPct`, `decision` | Есть BFF stock endpoint на базе `warehouse_remains` с enrichment из analytics snapshot | Partial |
| `week-over-week` | `orders/sales/baskets/margin/profit` composite + `wasOutOfStock`, `stockAvailability7d` | Есть BFF week-over-week endpoint; stock history требует внутренних daily snapshots | Partial |
| `alerts` | Список `ReportAlert[]` | Есть BFF alerts endpoint | Partial |
| `export/:reportId` | `ExportResponse { fileName, rows, emptySourceNote? }` | Есть BFF export endpoint | Partial |

## Parameter/Enum Mismatch

| Frontend | Backend | Действие |
|---|---|---|
| `preset=1d/7d/14d/30d/custom` | `dateFrom/dateTo` | Добавить слой преобразования preset -> dateFrom/dateTo |
| `groupBy` не включает `campaign` | Backend `ReportGroupBy` включает `campaign` | Оставить backend superset, но валидировать frontend subset |
| P&L `source=operational|financial` | P&L `source=operative|preliminary|final` | Ввести alias mapping и явное поведение для `financial` |

## Минимальный план закрытия WB-03

1. Ввести BFF-роутер `/api/wb/reports/*` как alias-слой поверх существующих `/api/v1/wb-reports/*`.
2. Добавить недостающие surfaces: `digest`, `stock`, `week-over-week`, `alerts`, `export/:reportId`.
3. Стабилизировать один frontend-friendly response shape для report tabs (`meta/headline/filters/kpis/chart/columns/rows`).
4. Зафиксировать mapping `frontend field -> backend source/formula/fallback` в `wb-backend-source-registry.md`.
5. Добавить contract-тесты: frontend expected JSON shape vs backend responses.

## Граница ответственности

- Backend business endpoints обязательны для production.
- Discovery endpoints остаются внутренним инструментом проверки источников и не заменяют бизнес-ручки.
