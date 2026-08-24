# API Contracts

> Единый слой правды между фронтом и backend-разработчиком. Первоисточник — TypeScript/Zod.

**Версия:** 1.0 · **Стек:** Zod → OpenAPI → Pydantic (подробнее [tooling.md](./tooling.md))

---

## Зачем это

Frontend и backend должны идти через общий контракт. Без этого:
- Типы дублируются вручную → расходятся
- Ошибки проявляются в интеграции, не в разработке
- Pending decisions по данным невидимы (что обязательно, что опционально, формат дат)

С контрактами:
- **Zod-схема** определяет структуру запросов/ответов на стороне фронта
- **OpenAPI YAML** — промежуточный формат, понятный обоим стекам
- **Pydantic** генерируется из OpenAPI — backend не переписывает модели вручную, а получает их из контракта

Один источник правды → изменение контракта идёт через PR в общий репо `contracts/`.

---

## Backend start: WB first

Первый backend cut для передачи разработчику - WB first / INDEEPA replacement. Backend живет в отдельном FastAPI repo; этот проект остается source-of-truth для PRD, frontend, mock API and contract workflow.

Baseline backend stack:

- Python 3.11+;
- FastAPI;
- PostgreSQL;
- Redis;
- Celery + Celery Beat;
- Alembic;
- Pydantic v2 models generated from OpenAPI;
- typed adapters for all external WB API calls.

Backend repo должен подтягивать contracts одним из двух способов:

1. До отдельного `contracts/` repo: брать OpenAPI YAML, exported from this project, as versioned artifact.
2. После создания `contracts/` repo: pull `contracts/openapi/v1.yaml` and run backend generation in CI.

Backend не должен вручную переписывать Pydantic models from screenshots/mock handlers. Если нужного контракта нет, сначала добавляем/обновляем Zod schema and OpenAPI, затем backend implements.

### Existing WB frontend contract inventory

| Surface | Current source | Backend status |
|---|---|---|
| SKU settings, comments, audit, changelog schemas | `frontend/src/features/wb-repricer/schemas.ts` | Draft Zod source; ready for OpenAPI export after backend review. |
| Manual price and bulk action schemas | `frontend/src/features/wb-repricer/schemas.ts` | Needs approval/guard flow review before production. |
| `/api/v1/wb-repricer/sku` | `frontend/src/mocks/handlers.ts` | Mock endpoint; backend must connect to real SKU/source registry. |
| `/api/v1/wb-repricer/sku/:articleId/settings` | `frontend/src/mocks/handlers.ts` | Draft contract; add settings versioning, approval and audit semantics. |
| `/api/v1/wb-repricer/dashboard` | `frontend/src/mocks/handlers.ts` | Needs source mapping before production. |
| `/api/v1/wb-repricer/templates` | `frontend/src/mocks/handlers.ts` | Draft settings/preset surface; align with typed settings model. |
| `/api/v1/wb-repricer/liquidation*` | `frontend/src/mocks/handlers.ts` | Needs WB-04 criteria and approval/audit flow. |
| `/api/v1/wb-repricer/algorithm` | `frontend/src/mocks/handlers.ts` | Draft only; align with typed strategy model. |
| `/api/v1/wb-repricer/promotions*` | `frontend/src/mocks/handlers.ts` | Needs WB source proof; do not promise WB auto-actions API. |
| `/api/v1/wb-repricer/changelog` | `frontend/src/mocks/handlers.ts` | Draft audit/read model; align with apply jobs. |

### Sprint A minimum contracts

Create or confirm contracts before Sprint B:

- account/token health;
- source registry and source freshness/confidence;
- settings model and settings version diff;
- permission/no-access state;
- audit event primitive;
- adapter/sync job state;
- blocked/unknown/stale responses for unresolved WB blockers.

Each production metric/action must have either source/formula/fallback/freshness or explicit blocker ID from `docs/open-questions-current.md`.

Meeting delta 19.05 is tracked separately in [wb-19-05-contract-delta.md](./wb-19-05-contract-delta.md). Treat it as a draft input for Zod/OpenAPI until backend review confirms source availability.

Current backend handoff package:

- OpenAPI artifact: `contracts/openapi/v1.yaml`
- Frontend export script: `frontend/scripts/export-openapi.ts`
- Frontend smoke script: `frontend/scripts/smoke-openapi.mjs` (`npm run smoke-openapi`)
- Backend review brief: [wb-19-05-backend-contract-handoff.md](../handoffs/wb-19-05-backend-contract-handoff.md)

---

## Процесс

### 1. Новый endpoint или изменение существующего

1. Frontend пишет Zod-схему в frontend-репо под нужный экран
2. Выделяет в отдельный файл в папке `contracts/` (зеркалит структуру модулей: `wb-repricer/`, `avito-listings/` и т.п.)
3. Запускает скрипт `npm run export-openapi` → генерирует OpenAPI YAML
4. Коммит в общий репо `contracts/` с PR
5. Backend-разработчик ревьюит, мерджит
6. На стороне бэка — скрипт `make gen-pydantic` → генерирует Pydantic модели из OpenAPI

### 2. Именование

- **Zod схема:** `WBRepricerUpdatePriceRequest`, `WBRepricerUpdatePriceResponse`
- **Endpoint paths:** `/api/v1/wb-repricer/prices` (REST conventions, всегда `/api/v1/` префикс)
- **Типы в OpenAPI (operationId):** `wbRepricerUpdatePrice`
- **Pydantic (auto-generated):** автоматически из OpenAPI, переименование не делаем

### 3. Версионирование

- `/api/v1/` — текущая версия
- Breaking changes → `/api/v2/`, старая версия сохраняется на время миграции (3 мес минимум)
- Non-breaking (добавление опциональных полей) — в той же версии
- Все изменения — через PR с описанием «breaking / non-breaking»

### 4. Общие соглашения

| Область | Правило |
|---|---|
| Даты | ISO 8601 UTC: `2026-04-22T14:30:00Z`. Никаких локальных таймзон в API |
| Валюта | Копейки как integer (не рубли с плавающей точкой): `45000` = 450.00 ₽ |
| ID | UUID v4 для внутренних, строки для внешних (WB article, Avito itemId) |
| Пагинация | `?limit=100&offset=0`, в ответе `{items: [...], total: 1234}` |
| Ошибки | `{error: {code: "WB_API_UNAVAILABLE", message: "...", details: {...}}}` |
| Enums | Всегда в константах schema, не в коде: `status: z.enum(['pending', 'in_progress', 'completed'])` |

---

## Структура папки contracts/

Создаётся в отдельном репо (TBD — общий contracts repo):

```
contracts/
  README.md                          (ссылка на этот файл)
  tooling.md                         (ссылка на tooling.md)
  schemas/
    wb-repricer/
      price-update.ts                (Zod schemas)
      sku-list.ts
    wb-reports/
      sales.ts
      inventory.ts
    avito-listings/
      listing-crud.ts
      xml-publish.ts
    orders/
      order.ts
      kiz-pool.ts
    common/
      pagination.ts
      errors.ts
      date-time.ts
  openapi/
    v1.yaml                          (auto-generated)
  scripts/
    export-openapi.ts                (Zod → OpenAPI YAML)
    generate-pydantic.sh             (OpenAPI → Pydantic на стороне бэка)
```

---

## Handoff между frontend и backend

### Правило: любая новая фича начинается с контракта

Frontend не пишет UI-запросы «на глазок». Сначала:
1. Обсудить с backend-разработчиком (коротко, в Slack или на синке): «Нужен endpoint X с полями Y, Z»
2. Frontend пишет Zod-схему
3. PR в contracts
4. Backend-разработчик ревьюит (смотрит на то, что сможет реализовать на бэке — ограничения WB API, индексы БД)
5. Мердж → оба параллельно идут делать реализацию

### Что backend ожидает от frontend

- Zod-схема компилируется без ошибок
- `npm run smoke-openapi` отрабатывает
- Добавлен описательный `operationId` и `description` в OpenAPI
- Указаны коды ответов: 200, 400, 401, 429, 500 (с типизированными телами ошибок)

### Что frontend ожидает от backend

- Pydantic генерируется без ручных правок
- Эндпоинт задеплоен в staging в течение N дней после мерджа контракта
- Реализация соответствует контракту (валидируется автотестами с Zod на фронте и Pydantic на бэке)

---

## Что НЕ делаем

- **GraphQL** — не делаем. Для B2B CRUD с ~50 эндпоинтами REST + контракты проще
- **tRPC** — не делаем. Требует Node.js на бэке, у нас Python
- **Ручные Pydantic модели** — не пишем. Только автогенерация из OpenAPI
- **TypeScript-only** контракты — нет. Нужен промежуточный OpenAPI, иначе Python не поймёт

---

## Ссылки

- [tooling.md](./tooling.md) — обоснование стека и команды
- [wb-19-05-backend-contract-handoff.md](../handoffs/wb-19-05-backend-contract-handoff.md) — что backend должен повторить в Pydantic/FastAPI по итогам 19.05
- Zod: https://zod.dev/
- OpenAPI 3.1: https://spec.openapis.org/oas/v3.1.0
- datamodel-code-generator: https://github.com/koxudaxi/datamodel-code-generator
