# WB Backend Sprint A Foundation Plan

Дата: 2026-05-26  
Статус: рабочий план запуска Sprint A foundation для backend.

## 1) Цель Sprint A

Собрать честный backend foundation для WB first без имитации production-готовности:

- поднятая инфраструктура;
- общий контрактный слой и типизированные состояния;
- source registry + blocker register;
- permissions + audit + sync jobs;
- contract-shaped stubs с `blocked/unknown/stale/partial`.

Sprint A не включает реальный `price apply` в WB.

## 2) Scope и ограничения

In scope:

- WB first / INDEEPA replacement foundation;
- discovery-safe adapters;
- gates для дальнейших Sprint B/C/D.

Out of scope для Sprint A:

- real WB price mutations;
- финальный P&L как источник финансовой истины;
- full INDEEPA parity;
- Avito/production-orders.

## 3) Артефакты, которые обязательны к чтению

1. `docs/handoffs/wb-backend-programmer-brief.md`
2. `docs/handoffs/wb-backend-dev-package.md`
3. `docs/handoffs/wb-backend-data-handoff-index.md`
4. `docs/handoffs/wb-backend-source-registry.md`
5. `docs/handoffs/wb-backend-formula-catalog.md`
6. `docs/handoffs/wb-backend-reuse-dependency-map.md`
7. `docs/open-questions-current.md`
8. `docs/api-contracts/README.md`
9. `docs/handoffs/wb-backend-sprint-a-stub-pack.md`
10. `docs/handoffs/wb-backend-sprint-a-demo-request.md`

## 4) Рабочий план по фазам

### Phase A0: Baseline среды и репозитория

Цель:

- единый воспроизводимый local setup;
- тесты проходят;
- есть понятная точка входа для любого нового разработчика.

Шаги:

1. Поднять `.venv`.
2. Установить runtime + test зависимости.
3. Прогнать `pytest tests backend_contracts/tests`.
4. Проверить `/health`.
5. Зафиксировать команды в README.

Definition of Done:

- setup и tests повторяются на чистой машине;
- нет устных "магических" шагов.

### Phase A1: Infrastructure Foundation

Цель:

- минимальный production-like каркас данных и фоновых задач.

Шаги:

1. Подключить PostgreSQL и модель конфигурации.
2. Подключить Alembic и сделать baseline migration.
3. Подключить Redis.
4. Подключить Celery/Celery Beat (без production polling jobs).

Definition of Done:

- app стартует с Postgres/Redis;
- миграции вверх/вниз рабочие;
- test Celery task выполняется.

### Phase A2: Common Contracts и Envelope

Цель:

- единые структуры ответа/ошибок/пагинации/денег/дат;
- строгий workflow `Zod -> OpenAPI -> generated models`.

Шаги:

1. Зафиксировать error envelope и pagination envelope.
2. Зафиксировать `money=integer kopecks`, `dates=ISO UTC`.
3. Ввести shared adapter result model со статусами.
4. Добавить тесты сериализации/валидации envelope.

Definition of Done:

- роуты отдают согласованные typed states;
- новые endpoint'ы не создают форматный drift.

### Phase A3: Source Registry + Blockers as First-Class

Цель:

- production-метрики описаны как data lineage, а не как "магия в коде".

Шаги:

1. Реализовать хранение/seed source registry.
2. Подтянуть blocker IDs из `open-questions-current`.
3. Добавить API выдачи registry и фильтрации.
4. Привязать formula IDs и freshness/confidence.

Definition of Done:

- каждая критичная метрика имеет source/fallback/freshness/blocker;
- нет "ready" без подтвержденного источника.

### Phase A4: Settings/Permissions/Audit/Sync Jobs

Цель:

- безопасный контур изменений и наблюдаемости.

Шаги:

1. Typed settings model + range/enum validation.
2. Versioning/diff/status (`draft/pending/active/archived`).
3. Role baseline: `viewer/settings_editor/price_sender/finance_viewer/admin`.
4. Audit primitive: actor/action/object/before/after/reason/evidence refs.
5. Sync jobs state model и no-op scheduler flow.

Definition of Done:

- изменение настроек и blocked actions логируются в audit;
- no-access сценарии типизированы и тестируются.

### Phase A5: Sprint A Stubs и Demo Readiness

Цель:

- отдать фронту интеграционный API, который честно отражает blockers.

Шаги:

1. Проверить/доработать stubs для:
   - account health;
   - source registry;
   - reports (`P&L`, `Ads`, `RNP`, `ABC`);
   - price guard;
   - reviews approval gate.
2. Для unresolved источников возвращать `blocked/unknown/partial`.
3. Подготовить demo-пакет и негативные сценарии.

Definition of Done:

- demo показывает foundation, а не fake production;
- `price apply` остаётся blocked placeholder.

## 5) Порядок исполнения задач (critical path)

1. A0 baseline env and tests
2. A1 infra
3. A2 contracts/envelopes
4. A3 source registry
5. A4 settings/permissions/audit/sync jobs
6. A5 stubs + demo

Параллелить можно после A1/A2, но source registry должен оставаться главным gate для risky actions.

## 6) Sprint A контрольные точки по неделям

Week 1:

- A0 завершен;
- infrastructure skeleton готов;
- common contracts зафиксированы.

Week 2:

- source registry + blockers работают через API;
- settings + permissions + audit протянуты end-to-end.

Week 3:

- sync jobs state и stubs завершены;
- demo package собран;
- список Sprint B gates согласован.

## 7) Риски и ранняя эскалация

Эскалировать сразу:

- не подтвержден endpoint/status/row errors для apply (`WB-22`);
- не определены freshness/confidence blocking rules (`WB-23`);
- давление на реализацию real apply до закрытия guards/audit.

## 8) Sprint B gate (что нужно закрыть до старта)

Минимум:

1. `WB-22` - apply endpoint + status + row errors.
2. `WB-23` - freshness/confidence rules для критичных источников.

Без этих пунктов Sprint B price engine не стартует.

## 9) Progress log

- 2026-05-26: Phase A2 baseline implemented in code:
  - common error envelope;
  - common pagination envelope;
  - money as integer kopecks and UTC-aware datetime validation;
  - shared adapter result model with typed statuses;
  - contract validation tests added and passing.
- 2026-05-26: Phase A3 baseline implemented in code:
  - `source_registry_entries`, `source_registry_blockers`, `source_registry_formulas` tables + Alembic migration;
  - seed parsing from `open-questions-current.md`, `wb-backend-source-registry.md`, `wb-backend-formula-catalog.md`;
  - source registry API with filtering/pagination and formula/blocker catalogs;
  - validation rule: `confirmed` rows must carry source/formula/fallback/freshness lineage fields.
- 2026-05-26: Phase A4 baseline implemented in code:
  - typed repricer settings model with range/enum validation;
  - settings versioning lifecycle (`draft/pending/active/archived`) + diff endpoint;
  - role baseline (`viewer`, `settings_editor`, `price_sender`, `finance_viewer`, `admin`) with permission checks;
  - audit primitive for settings/sync/blocked actions;
  - sync jobs model + no-op run and no-op scheduler tick endpoints.
- 2026-05-26: Phase A5 baseline implemented in code:
  - added `GET /api/v1/wb/account/health` stub with `ok/missing_token/missing_scope/expired` scenarios;
  - kept source/report/repricer/reviews stubs in typed `blocked/unknown/partial` states for unresolved sources;
  - added demo-compatible `GET /api/v1/source-registry?module=wb` view for blocker registry;
  - added A5 demo-negative tests (`pnl/ads/rnp/price-guard`) and prepared demo package doc.
- 2026-05-26: Sprint A closure delta implemented:
  - added DB tables for WB account/token health snapshots (`wb_accounts`, `wb_account_capabilities`, `wb_account_missing_scopes`, `wb_token_health_checks`) + Alembic migration `20260526_0004`;
  - `GET /api/v1/wb/account/health` now persists health snapshots and writes audit event `wb.token_health.check` without token secrets in payloads;
  - added OpenAPI-generated Pydantic layer at `app/contracts/vella_wb_19_05_generated.py` and test coverage to keep generated-contract workflow explicit.
- 2026-05-27: `WB-06` source confirmed:
  - primary source: `POST /api/v2/list/goods/filter` (Prices & Discounts API);
  - fields: `clubDiscount`, `sizes[].discountedPrice`, `sizes[].clubDiscountedPrice`;
  - fallback formula: `(discountedPrice - clubDiscountedPrice) / discountedPrice * 100`.
