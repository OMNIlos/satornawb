# WB Backend Data Handoff Index

Дата: 2026-05-25
Статус: рабочий entrypoint для Sprint A source mapping.
Scope: WB first / INDEEPA replacement. Авито и production-заказы вне текущего cut.

## 1. Назначение пакета

Этот пакет закрывает слой, которого не хватало между PRD и backend implementation: карту данных WB-сервиса. Backend-разработчик должен видеть не только список экранов и endpoint stubs, а полную связку:

```text
screen -> metric/action -> source -> external field -> formula -> refresh -> fallback -> freshness -> confidence -> blocker
```

Без строки в source registry production-метрика не считается готовой к Sprint B/C/D. API должен возвращать `blocked`, `unknown`, `stale`, `partial` или `manual_fallback`, а не декоративные значения.

## 2. Читать по порядку

| Файл | Зачем |
|---|---|
| `docs/handoffs/wb-backend-source-registry.md` | Главная рабочая таблица source mapping для Sprint A. |
| `docs/handoffs/wb-backend-formula-catalog.md` | Формулы, inputs, outputs, units, owner и статус подтверждения. |
| `docs/handoffs/wb-backend-reuse-dependency-map.md` | Где данные переиспользуются и какие зависимости блокируют actions. |
| `docs/client-questions-wb-data-handoff-2026-05-25.md` | Короткий клиентский список вопросов к Марии и Максиму. |
| `docs/handoffs/wb-backend-checklist-delta-source-registry.md` | Delta к существующему backend checklist: gate перед Sprint B. |

Этот пакет дополняет, а не заменяет:

- `docs/handoffs/wb-backend-dev-package.md`;
- `docs/handoffs/wb-backend-sprint-a-tickets.md`;
- `docs/open-questions-current.md`;
- `docs/wb-reports-data-contract-2026-05-08.md`;
- `docs/api-contracts/wb-19-05-contract-delta.md`.

## 3. Sprint A outcome

К концу Sprint A backend должен показать:

- source registry в БД или seedable config;
- API для чтения registry и blocker status;
- stubs, где unresolved источники возвращают blocker IDs;
- связку registry с sync jobs, adapter envelope, audit и permissions;
- список client/API discovery gaps перед Sprint B.

## 4. Hard gates

Sprint B price engine не стартует, пока не закрыты или явно заблокированы:

- `WB-06`: закрыт 27.05.2026 (источник подтвержден через `POST /api/v2/list/goods/filter`, fallback формула зафиксирована);
- `WB-22`: price apply endpoint/status/row errors;
- критичные `WB-23`: freshness/confidence/blocking rules для price apply;
- SKU/COGS/commission/logistics inputs для margin and P_min/P_max.

Sprint D NRP-lite не стартует как production finance, пока не закрыты:

- `WB-02`: WB Ads attribution source;
- `WB-11`: ROI/ДРР/маржа formulas;
- `WB-12`: storage/OPEX allocation;
- `WB-13`: tax/VAT base and percentages;
- `WB-24`: finance visibility/export permissions.

## 5. Output format expected from backend

Every production metric/action should expose:

- `sourceStatus`: `confirmed`, `blocked`, `unknown`, `manual_fallback`, `stale`, `partial`, `disabled`;
- `blockerIds`: array of IDs from `docs/open-questions-current.md`;
- `freshness`: source name, fetchedAt, staleAfter, isStale, confidence;
- `fallback`: UI/data behavior when source is missing or stale;
- `evidenceRefs`: source registry row, sync job, sanitized external raw reference, or client confirmation.

## 6. Explicitly out of this cut

- Авито;
- production order queue;
- КИЗ implementation;
- direct 1C integration;
- Ozon/cross-marketplace;
- full INDEEPA rule-builder parity;
- WB auto-actions management through API.
