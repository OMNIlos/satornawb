# WB 19.05 backend contract handoff

**Статус:** ready for backend review
**Source of truth:** `contracts/openapi/v1.yaml`
**Generated from:** Zod schemas in `frontend/src/features/wb-reports/schemas.ts`, `frontend/src/features/wb-repricer/schemas.ts`, `frontend/src/features/wb-contracts/sourceState.ts`
**Related:** `docs/api-contracts/wb-19-05-contract-delta.md`, `docs/handoffs/wb-19-05-implementation-roadmap.md`, `docs/handoffs/wb-backend-sprint-a-tickets.md`, `docs/handoffs/wb-backend-sprint-a-stub-pack.md`

**Local smoke validation:** `npm run smoke-openapi` passed; `datamodel-codegen` generated Pydantic v2 models from `contracts/openapi/v1.yaml` and `py_compile` passed.

**Runtime reference package:** `backend_contracts/vella_wb_19_05/` contains a copy-ready FastAPI/Pydantic stub package for Sprint A. It mirrors the 19.05 invariants below and has pytest coverage for negative cases.
**Backend skeleton:** `backend/` now mounts the package as a real FastAPI Sprint A app with `/health` and 19.05 stub endpoints.

## Что это закрывает

Этот пакет фиксирует runtime boundary для уточнений встречи 19.05. Он не переносит HTML Vella в React и не делает новые экраны. Видимый production shell остается `frontend/public/vella-production.html`; React/Zod слой сейчас нужен как typed contract boundary для backend.

Backend должен повторить эти инварианты в FastAPI/Pydantic и вернуть такие же состояния для реальных или пока заблокированных источников.

## Endpoints в OpenAPI

| Endpoint | Operation ID | Назначение |
|---|---|---|
| `GET /api/v1/wb-reports/pnl` | `wbReportsGetPnl` | P&L с состояниями `operative/preliminary/final/blocked`. |
| `GET /api/v1/wb-reports/ads/performance` | `wbReportsGetAdsPerformance` | Нормализованная реклама с attribution policy. |
| `GET /api/v1/wb-reports/rnp` | `wbReportsGetRnp` | РНП + реклама за тот же период. |
| `GET /api/v1/wb-reports/abc` | `wbReportsGetAbc` | ABC с `filteredSummary` по текущему набору фильтров. |
| `GET /api/v1/wb-repricer/sku/{articleId}/price-guard` | `wbRepricerGetPriceGuard` | SPP-aware guard/freeze state перед применением цены. |

## Backend generation commands

До отдельного contracts repo backend может брать artifact из этого проекта:

```bash
cd "/Users/dima/Downloads/Projects/SAAS для Огней/frontend"
npm run smoke-openapi
```

`smoke-openapi` проверяет, что artifact генерируется, все paths остаются под `/api/v1/*`, а `servers[0].url=/`. Это важно: если одновременно поставить `servers=/api/v1` и paths `/api/v1/...`, часть codegen-клиентов соберет URL вида `/api/v1/api/v1/...`.

Затем в backend repo:

```bash
datamodel-codegen \
  --input contracts/openapi/v1.yaml \
  --input-file-type openapi \
  --output app/contracts/vella_wb_19_05.py \
  --output-model-type pydantic_v2.BaseModel \
  --target-python-version 3.11
```

Smoke check:

```bash
python -m py_compile app/contracts/vella_wb_19_05.py
```

Для Sprint A можно также использовать переносимый reference package из этого repo:

```bash
PYTHONPATH=backend_contracts uvx --with pydantic --with fastapi --with httpx --with pytest pytest backend_contracts/tests
python3 -m py_compile backend_contracts/vella_wb_19_05/*.py
```

Он не заменяет backend repo, но фиксирует ожидаемые Pydantic validators, stub builders и FastAPI router до переноса.

Локальный backend skeleton проверяется так:

```bash
PYTHONPATH=backend:backend_contracts uvx --with pydantic --with fastapi --with httpx --with pytest pytest backend/tests backend_contracts/tests
python3 -m py_compile backend/app/*.py backend/app/routers/*.py backend/app/discovery/*.py backend/app/wb_api/*.py
```

Current executable discovery remains fake-client only: read-prices and task-history probes can confirm or reject fields, but they cannot call WB write endpoints and cannot set `canApply=true`.

## Инварианты, которые нельзя потерять в backend

### Common source state

- `sourceStatus=blocked|unknown` требует хотя бы один `blockerIds[]`.
- `sourceStatus=blocked` требует `confidence=blocked`.
- `sourceEvidence[]` должен ссылаться на реальные элементы source registry; `mock` допустим только для dev/staging stubs.
- `calculatedAt` всегда UTC datetime, `period.dateFrom/dateTo` всегда ISO date.

### P&L

- `reportState=final` разрешен только если верхний `sourceStatus=fresh`, `blockerIds=[]`, totals/rows/manualCosts/dayAllocation/fieldMapping не несут blockers.
- `financial` source до закрытия `WB-12/WB-13/WB-23` возвращает не `final`, а `preliminary` или `blocked`.
- Каждая метрика P&L должна иметь `fieldMapping`: источник, поле, формула, fallback и blockers.
- Слабая рекламная атрибуция не должна превращаться в точную SKU-прибыль.

### Ads

- `campaign_only` и `unknown` нельзя разрешать в SKU-level attribution policy.
- Если отчет сгруппирован по SKU, строки не могут иметь `attributionLevel=campaign_only|unknown`.
- `campaign_only|unknown` не может иметь `confidence=high`.
- `sourceStatus=blocked|unknown` для рекламы должен ссылаться на `WB-02`.

### РНП

- Если `drrPct=null`, ответ должен ссылаться на `WB-11`.
- Если `adsSourceStatus=blocked|unknown`, ответ должен ссылаться на `WB-02`.
- Период рекламы должен совпадать с периодом РНП.

### ABC

- `filteredSummary` пересчитывается от текущих фильтров/groupBy, а не возвращает статичную карточку.
- Если рекламный источник не закрыт, блокируются/понижаются только рекламные поля summary, а не весь ABC.
- `filteredSummary.sourceStatus=blocked|unknown` требует blockers на уровне ответа.

### SPP price guard

- Пока источник SPP/price apply не подтвержден, default response: `canApply=false`, `freezeState=source_blocked`, blockers `WB-06/WB-22/WB-23`.
- `canApply=true` несовместим с `blockedReason`, `blockerIds[]`, `freezeState!=none`, blocker triggers и stale/blocked SPP snapshot.
- Frontend только отображает guard state; backend является source of truth для freeze/apply.

## Что backend возвращает в Sprint A stubs

Sprint A не обязан иметь реальные WB данные, но должен вернуть contract-shaped stubs:

| Slice | Stub state |
|---|---|
| P&L financial | `preliminary` или `blocked`, blockers `WB-12/WB-13/WB-23`. |
| Ads | `partial` или `blocked`, blocker `WB-02`, без SKU exactness при `campaign_only`. |
| РНП | `partial` или `blocked`, blockers `WB-02/WB-11`. |
| ABC | свежие non-ad aggregates where possible, ad fields partial/blocked. |
| SPP guard | `canApply=false`, `source_blocked`, blockers `WB-06/WB-22/WB-23`. |

## Review checklist для backend

- [ ] Pydantic models генерируются из `contracts/openapi/v1.yaml` без ручных правок.
- [ ] FastAPI response models используют сгенерированные модели или совместимые Pydantic wrappers.
- [ ] Source registry содержит blockers `WB-02`, `WB-03`, `WB-06`, `WB-11`, `WB-12`, `WB-13`, `WB-14A`, `WB-19A`, `WB-22`, `WB-23`.
- [ ] Contract tests покрывают negative cases: P&L final with blockers, SKU ads with campaign-only attribution, RNP blocked ads without `WB-02`, price guard `canApply=true` with blockers.
- [ ] Backend не реализует кастомный INDEEPA rule-engine и не отправляет реальные цены до SPP/source/apply/audit gates.
- [ ] Reference package перенесен в backend repo или явно заменен совместимыми Pydantic/FastAPI моделями с теми же tests.

## После backend review

1. Если генерация Pydantic или FastAPI response validation выявит неудобную форму схемы, правим Zod и заново экспортируем OpenAPI.
2. После подтверждения backend меняем статус `docs/api-contracts/wb-19-05-contract-delta.md` с draft на reviewed for implementation.
3. Только после backend stubs подключаем следующие Vella states в HTML shell.
