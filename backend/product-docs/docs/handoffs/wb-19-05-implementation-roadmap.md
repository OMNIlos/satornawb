# Implementation roadmap по итогам 19.05

**Источник:** `Встречи/19.05/meeting-protocol-backlog-2026-05-19.md`
**Backlog:** `docs/handoffs/wb-19-05-action-backlog.md`
**Contract draft:** `docs/api-contracts/wb-19-05-contract-delta.md`
**Backend contract handoff:** `docs/handoffs/wb-19-05-backend-contract-handoff.md`
**Цель:** реализовать уточнения 19.05 в Vella/WB без имитации production-готовности там, где WB/API/клиентские формулы еще не подтверждены.

## Общая логика

19.05 не добавил новый большой модуль. Реализация должна идти так:

1. Сначала backend foundation, source registry и blocked/partial states.
2. Затем безопасный repricer/SPP guard, потому что price apply самый рискованный.
3. Затем отчеты P&L/Ads/РНП/ABC на реальных или явно заблокированных источниках.
4. Затем frontend-доводка Vella поверх контрактов.
5. AI reviews и Service Token идут отдельными параллельными треками, но с жесткими gates.

## Этапы

| Этап | Название | Цель | Выход | Можно начинать |
|---:|---|---|---|---|
| 0 | Client/ops decisions | Закрыть вопросы, которые backend не угадает | Ответы по P&L расходам, Ads, SPP, Service Token timing | Сразу |
| 1 | Backend foundation | Сделать каркас и source-state модель | Sprint A backend, source registry, blocked stubs | Сразу |
| 2 | Contract hardening | Превратить draft 19.05 в Zod/OpenAPI | Reviewed contracts для P&L/Ads/РНП/ABC/SPP/reviews | После начала этапа 1 |
| 3 | Repricer/SPP safety | Реализовать guardrails до отправки цен | SPP-aware guard, freeze-state, apply blocked/ready states | После этапов 1-2 |
| 4 | Reports data layer | Реализовать P&L/Ads/РНП/ABC как данные | API reports with confidence/source evidence | После этапов 1-2, частично параллельно с 3 |
| 5 | Frontend Vella patch | Подключить UI к контрактам без новых больших экранов | Filtered summary, states, рублевый шаг, blockers UI | После готовности contract stubs |
| 6 | AI reviews approval | Production-safe отзывы | Draft -> approval -> send, audit, brand voice | После agent harness/contracts |
| 7 | UAT + Service Token readiness | Подготовить запуск и SaaS-переход | UAT pack, Service Token package, release gates | Параллельно с 1-6 |

## Этап 0: Client/ops decisions

**Владелец:** Фил + Дмитрий + Мария/Максим
**Срок:** параллельно с backend Sprint A
**Зачем:** без этих ответов backend обязан возвращать `blocked`, а не считать финальные метрики.

| Задача | Источник | Done |
|---|---|---|
| Подтвердить P&L расходы: налоги, хранение, общие расходы, allocation | `M19-PNL-04`, `WB-12`, `WB-13` | Есть таблица правил: статья -> период -> база распределения -> кто вводит/подтверждает. |
| Выбрать источник финансового отчета: API, Excel import или гибрид | `M19-PNL-03`, `WB-03` | Для financial source выбран основной путь и fallback. |
| Подтвердить Ads source и допустимую атрибуцию | `M19-ADS-01`, `WB-02` | Есть endpoint/export/XLSX, поля, доступы, лимиты, правило `exact_sku/campaign_sku/campaign_only`. |
| Подтвердить набор агрегатов по локомотивам | `M19-ABC-03`, `WB-19A` | Мария подтверждает первый набор: count, заказы/выручка, прибыль, маржа, реклама if available. |
| Подтвердить SPP source/fallback и пороги freeze | `M19-REP-01`, `M19-REP-02`, `WB-06` | Есть источник/формула SPP или решение держать SPP-aware apply blocked. |
| Выбрать момент подачи на WB Service Token | `M19-TOKEN-03`, `WB-26` | Решено: заранее или после core WB UAT; есть owner и календарь. |

## Этап 1: Backend foundation

**Владелец:** backend
**Основа:** `docs/handoffs/wb-backend-sprint-a-tickets.md`
**Смысл:** без этого нельзя безопасно реализовывать ни P&L, ни price apply.

Минимальный scope:

- FastAPI repo skeleton.
- PostgreSQL, Redis, Celery/Celery Beat.
- account/token health.
- source registry.
- adapter envelope.
- settings versions.
- permissions.
- audit.
- sync job state.
- API stubs with `ready/blocked/unknown/stale/error`.

Done:

- unresolved источники возвращают blocker IDs из `docs/open-questions-current.md`;
- price apply только blocked placeholder;
- P&L final blocked до `WB-12/WB-13`;
- Ads/РНП partial/blocked до `WB-02/WB-11`;
- SPP guard `canApply=false` до `WB-06/WB-22/WB-23`.

## Этап 2: Contract hardening

**Владелец:** frontend + backend contract review
**Основа:** `docs/api-contracts/wb-19-05-contract-delta.md`

| Contract slice | Что сделать | Gate |
|---|---|---|
| Common source state | Zod/OpenAPI для `sourceStatus`, `confidence`, `SourceEvidence`, `blockerIds` | Backend подтверждает, что это удобно маппится в Pydantic. |
| P&L | `GET /api/v1/wb-reports/pnl` | Есть `reportState` и field mapping. |
| Ads | `GET /api/v1/wb-reports/ads/performance` | Есть attribution policy и confidence. |
| РНП | `GET /api/v1/wb-reports/rnp` | ДРР может быть null/blocked до формулы. |
| ABC | `filteredSummary` в ABC response | Summary пересчитывается по фильтрам. |
| SPP guard | `GET /api/v1/wb-repricer/sku/{articleId}/price-guard` | Frontend не считает freeze сам. |
| Plan-fact brand | `dimension=brand`, только если подтверждено | Не плодим отдельный отчет. |
| AI reviews | approval state + audit fields | Низкие оценки нельзя отправить без approval. |

Done:

- Zod schemas готовы или явно помечены `needs source discovery`;
- frontend mock/repository boundary валидирует P&L/Ads/РНП/ABC через 19.05 Zod sidecars;
- SPP guard mock endpoint возвращает typed blocked state до закрытия `WB-06/WB-22/WB-23`;
- OpenAPI artifact сгенерирован в `contracts/openapi/v1.yaml`;
- backend handoff оформлен в `docs/handoffs/wb-19-05-backend-contract-handoff.md`;
- переносимый Pydantic/FastAPI reference package добавлен в `backend_contracts/vella_wb_19_05/` с pytest negative cases;
- локальный Sprint A backend skeleton добавлен в `backend/`: `/health`, source registry, P&L/Ads/РНП/ABC/SPP/reviews stubs через FastAPI response models;
- SPP/price apply discovery endpoints добавлены: `/api/v1/wb-discovery/repricer/source-map` и `/api/v1/wb-discovery/repricer/readiness`;
- read-only adapter probes добавлены через fake WB client: `/api/v1/wb-discovery/repricer/probes/read-prices` и `/api/v1/wb-discovery/repricer/probes/task-history`;
- следующий backend шаг - подключить реальные read-only WB adapter calls к этим probe contracts после token validation, не добавляя write/apply до audit gates.

## Этап 3: Repricer/SPP safety

**Владелец:** backend first, frontend after contract
**Приоритет:** P0
**Почему раньше отчетов:** ошибка price apply дороже, чем недоделанный отчет.

Tasks:

| Задача | Owner | Depends on | Done |
|---|---|---|---|
| Реализовать source-backed price guard | backend | Этап 1-2 | `canApply`, `blockedReason`, `freezeState`, `guardTriggers`. |
| Проверить/подключить SPP source или fallback | backend | `WB-06` | SPP-aware apply либо работает, либо честно blocked. |
| Добавить SPP-aware recommendation | backend | SPP source | Видно влияние на buyer price. |
| Добавить рублевый шаг стратегии в typed settings | backend + frontend | `WB-14` | Рублевый и процентный шаг валидируются. |
| Подключить UI states в Vella | frontend | backend stubs | UI показывает blocked/frozen/requires_review без frontend-only логики. |

Не делать:

- не отправлять реальные цены до guard/audit/approval;
- не переносить кастомный rule-engine INDEEPA;
- не делать SPP расчет только на клиенте.

Sprint A default уже зафиксирован в reference package: `canApply=false`, `freezeState=source_blocked`, blockers `WB-06/WB-22/WB-23`. Это можно менять только после backend source discovery и audit/apply gates.

Adapter-probe default: даже если fake read-prices подтверждает `discountedPrice/clubDiscount`, `priceGuardPreview.canApply=false`, потому что `WB-22/WB-23` остаются unresolved. Missing SPP fields возвращают `WB-06` и `freezeState=source_blocked`.

## Этап 4: Reports data layer

**Владелец:** backend + frontend contract review
**Приоритет:** P0/P1
**Смысл:** P&L/Ads/РНП/ABC должны стать данными, а не экранными моками.

### 4.1 P&L

Done:

- есть field mapping для выручки, COGS, комиссий, логистики, хранения, рекламы, налогов, overhead, net profit;
- есть day-level allocation;
- `operative/preliminary/final/blocked`;
- final недоступен без правил Максима.

### 4.2 Ads/РНП

Done:

- Ads layer отдает spend, показы, клики, корзины, заказы, ДРР, ROMI/ROI;
- атрибуция не ниже `campaign_sku` для SKU-level выводов;
- `campaign_only` не попадает в SKU P&L как точная прибыль;
- РНП показывает рекламу за тот же период.

### 4.3 ABC/локомотивы

Done:

- API отдает `filteredSummary`;
- summary пересчитывается от фильтров;
- локомотивы имеют count, продажи/выручку, прибыль, маржу;
- рекламные поля partial/blocked, если Ads source не закрыт.

## Этап 5: Frontend Vella patch

**Владелец:** frontend
**Основа:** `frontend/public/vella-production.html` как design/source shell
**Правило:** не делать новый большой экран; доработать существующие surfaces.

Tasks:

| Surface | Что реализовать | Depends on |
|---|---|---|
| P&L | source states, field mapping visibility, blocked final state | P&L contract/stub |
| Ads/РНП | confidence, partial/blocked attribution, period-aligned spend | Ads/РНП contract/stub |
| ABC | sticky/верхний `filteredSummary` | ABC contract/stub |
| Repricer | SPP guard/freeze state, рублевый шаг | SPP guard/settings contract |
| Plan-fact | brand dimension only if confirmed | `WB-14A` |
| Reviews | approval state, no auto-send for low ratings | AI reviews contract |

Done:

- UI не показывает неподтвержденные данные как final;
- все risky actions имеют intermediate state;
- tooltips объясняют blocked/partial states коротко;
- HTML shell и React implementation не расходятся по смыслу.

## Этап 6: AI reviews approval

**Владелец:** backend + frontend + AI
**Основа:** `docs/architecture/agent-harness-standard.md`, `docs/evals/ai-agent-evals.md`

Tasks:

- draft generation with brand voice;
- approval gate for rating < 4;
- edit/regenerate/reject;
- audit trail: AI draft, manager approval, external send;
- prompt caching layout;
- eval pack: prompt injection, approval bypass, false success, tone errors.

Done:

- низкая оценка не может уйти автоматически;
- каждый send имеет approval/audit;
- brand voice не смешивает мемный стиль там, где он рискован.

## Этап 7: UAT + Service Token readiness

**Владелец:** Фил + Дмитрий + backend
**Идет параллельно:** с этапов 1-6

Service Token package:

- сайт/лендинг сервиса;
- описание сервиса;
- поддержка/контакты;
- privacy/security материалы;
- security files, если требуются WB;
- onboarding: Personal Token только для single-client пилота, Service Token для SaaS.

UAT package:

- список сценариев: price guard, blocked SPP, P&L blocked/final, Ads partial, ABC filtered summary, AI approval;
- тестовые SKU/периоды;
- ожидаемые source states;
- список открытых blockers.

Done:

- понятно, что можно пилотировать на Personal Token;
- понятно, что нужно для SaaS-перехода;
- нет внешнего обещания production SaaS без Service Token.

## Критический путь

```text
Этап 0 Client decisions
        |
Этап 1 Backend foundation
        |
Этап 2 Contracts
        |
        +--> Этап 3 Repricer/SPP safety
        |
        +--> Этап 4 Reports data layer
                    |
                    +--> Этап 5 Frontend Vella patch

Этап 6 AI reviews approval идет после agent/contracts, частично параллельно.
Этап 7 Service Token readiness идет параллельно, но блокирует SaaS-вывод.
```

## Что делаем первым

1. Открываем kickoff-пакет: `docs/handoffs/wb-19-05-phase-0-1-kickoff.md`.
2. Backend начинает Sprint A из `docs/handoffs/wb-backend-sprint-a-tickets.md`.
3. Фил собирает ответы по `WB-02`, `WB-06`, `WB-11`, `WB-12`, `WB-13`, `WB-14A`, `WB-19A`, `WB-26`.
4. Backend берет `contracts/openapi/v1.yaml` и `docs/handoffs/wb-19-05-backend-contract-handoff.md` на Pydantic/FastAPI review.
5. После stubs frontend подключает Vella states в HTML shell, но не рисует новый reporting product.

## Не делаем

- Full INDEEPA rule-engine.
- Full NRP BI parity.
- Campaign detail parity INDEEPA.
- Реальный price apply до SPP/source/apply status/audit.
- Final P&L без Максима.
- Auto-send негативных отзывов.
- Service Token как UI-фичу.
