# Sprint A tickets: WB backend discovery/foundation

Дата: 2026-05-21
Scope: WB first / INDEEPA replacement
Основа: `docs/handoffs/wb-backend-dev-package.md`
Meeting delta: `docs/api-contracts/wb-19-05-contract-delta.md`
Data handoff: `docs/handoffs/wb-backend-data-handoff-index.md`
Source registry seed: `docs/handoffs/wb-backend-source-registry.md`
Formula catalog: `docs/handoffs/wb-backend-formula-catalog.md`
Dependency map: `docs/handoffs/wb-backend-reuse-dependency-map.md`
First stub pack: `docs/handoffs/wb-backend-sprint-a-stub-pack.md`
Demo request: `docs/handoffs/wb-backend-sprint-a-demo-request.md`

## Sprint A goal

Создать backend foundation для WB-модуля и сделать неизвестные источники явными. После Sprint A можно безопасно переходить к price engine, потому что account/token, source registry, settings, permissions, audit, adapter envelope и sync jobs уже имеют понятные contracts.

## Definition of Done для всего Sprint A

- Backend repo поднимается локально одной командой из README.
- Есть FastAPI app, healthcheck, config, Postgres, Alembic, Redis, Celery/Celery Beat baseline.
- Миграции создают таблицы account/token health, source registry, settings versions, permissions, audit, sync jobs.
- Seed/test data создает одну WB account, несколько SKU и blocker registry entries.
- API stubs возвращают typed `ready`, `blocked`, `unknown`, `stale`, `error` states.
- Не реализован реальный price apply.
- Каждый unresolved production source связан с blocker ID из `docs/open-questions-current.md`.
- Registry rows from `docs/handoffs/wb-backend-source-registry.md` are seeded or represented as loadable config with status, fallback, freshness/confidence and blocker IDs.
- Formula entries from `docs/handoffs/wb-backend-formula-catalog.md` are mapped to formula IDs/version placeholders for dependent metrics/actions.
- Dependency blockers from `docs/handoffs/wb-backend-reuse-dependency-map.md` are enforced for price apply, finance finalization and SKU-level ads allocation.
- Contract delta 19.05 разобран: P&L, Ads/РНП, ABC filtered summary, SPP guard, plan-fact brand dimension и AI reviews approval помечены как `ready for schema`, `needs source discovery` или `client question`.
- Tests покрывают migrations, schema validation, permission checks, adapter envelope and blocked states.

## Ticket A0: repo skeleton

Owner: backend
Effort: 4-8h
Depends on: repo created

Task:

- Создать отдельный backend repo.
- Настроить Python 3.11+, FastAPI, Pydantic v2, pytest, ruff/formatter, mypy или pyright по выбору команды.
- Добавить `README.md` с local setup, test commands, env vars, contract location.
- Добавить `/health` endpoint.

Done:

- `pytest` проходит.
- `/health` возвращает ok locally.
- README позволяет новому разработчику поднять app без устных пояснений.

## Ticket A1: infrastructure baseline

Owner: backend
Effort: 4-8h
Depends on: A0

Task:

- Подключить PostgreSQL.
- Настроить Alembic.
- Подключить Redis.
- Настроить Celery app and Celery Beat baseline.
- Добавить docker compose или другой approved local runtime.

Done:

- Local app connects to Postgres/Redis.
- Alembic can create and rollback an empty baseline migration.
- Celery worker starts and can execute a test task.
- Beat starts with no production jobs enabled.

## Ticket A2: common API contracts

Owner: backend + frontend contract review
Effort: 4-8h
Depends on: A0

Task:

- Зафиксировать common API envelope: error, pagination, dates, money, internal/external IDs.
- Подготовить место для generated Pydantic models from OpenAPI.
- Добавить contract README in backend repo: source is Zod/OpenAPI, no handwritten drift.
- Добавить tests for money/date/error envelope validation.

Done:

- Common response/error models exist.
- Money is integer kopecks.
- Dates serialize as ISO UTC.
- Internal IDs are UUID.
- Existing frontend draft contracts are listed as pending backend review.

## Ticket A3: WB account and token health

Owner: backend
Effort: 6-10h
Depends on: A1, WB token access if available

Task:

- Создать models/tables for WB account, token metadata, scopes/capabilities, auth status.
- Подготовить safe discovery service for token health.
- Если live token еще нет, вернуть `unknown/missing_access` with blocker.
- Не хранить raw token в logs or API responses.

Done:

- Account/token health endpoint returns structured state.
- Missing token/scopes are first-class states, not 500.
- Audit records token health check without secret leakage.
- Tests cover ok, missing token, missing scope, expired/unknown states.

## Ticket A4: adapter result envelope

Owner: backend
Effort: 4-6h
Depends on: A2

Task:

- Реализовать shared `AdapterResult<T>` equivalent in Python.
- Статусы: `success`, `partial`, `empty`, `stale`, `not_authorized`, `missing_capability`, `blocked_by_guard`, `rate_limited`, `external_error`, `unknown_error`.
- Добавить freshness: source, fetched_at, stale_after, is_stale, confidence.
- Добавить evidence refs and next valid actions.

Done:

- Envelope reusable by WB adapters and services.
- Unit tests cover status serialization and error cases.
- Route stubs can return blocked/stale without throwing generic exceptions.

## Ticket A5: source registry

Owner: backend
Effort: 8-12h
Depends on: A1, A4

Task:

- Создать registry for production metrics/actions:
  screen, metric, source, external field, formula, refresh frequency, fallback, freshness, confidence, blocker ID.
- Use `docs/handoffs/wb-backend-source-registry.md` as the initial seed, not only the blocker list.
- Preserve formula/status references so rows can point to `docs/handoffs/wb-backend-formula-catalog.md`.
- Seed blockers from current WB list:
  WB-01, WB-02, WB-03, WB-04, WB-06, WB-11, WB-12, WB-13, WB-14A, WB-17, WB-18, WB-19A, WB-22, WB-23.
- API endpoint to list registry and filter by module/status.

Done:

- Registry can represent `confirmed`, `blocked`, `unknown`, `manual_fallback`, `disabled`.
- Every seeded blocker links to `docs/open-questions-current.md` ID.
- Tests ensure production metric cannot be marked ready without source/fallback/freshness.
- Tests ensure price-critical rows cannot unblock price apply while СПП, price apply status or source freshness remain blocked.

## Ticket A6: typed settings model

Owner: backend
Effort: 8-12h
Depends on: A1, A2

Task:

- Create typed settings model for INDEEPA/WB repricer parameters.
- Support enum/range validation.
- Add settings versioning, diff and status: draft, pending approval, active, archived.
- Do not implement strategy execution yet.

Done:

- Settings can be created/updated as draft.
- Invalid ranges/enums fail validation.
- Diff between versions is available.
- Activation requires permission/approval placeholder, even if approval UI is not implemented yet.

## Ticket A7: permissions baseline

Owner: backend
Effort: 4-8h
Depends on: A1

Task:

- Implement roles:
  `viewer`, `settings_editor`, `price_sender`, `finance_viewer`, `admin`.
- Add permission checks for settings write, price send placeholder, finance read/export placeholder, admin token actions.
- No full auth provider required if not selected yet; use local/test actor injection for Sprint A.

Done:

- Protected routes can return no-access state.
- Finance data placeholder is blocked without `finance_viewer`.
- Price send placeholder is blocked without `price_sender` and approval.
- Tests cover role matrix.

## Ticket A8: audit primitive

Owner: backend
Effort: 6-10h
Depends on: A1, A7

Task:

- Create audit event table/model.
- Required fields: actor, role, action, object type/id, before/after, reason, approval ref, source/evidence refs, created_at.
- Add helper/service to record audit for settings changes, token health checks, blocked action attempts.

Done:

- Audit event is immutable through normal API.
- Settings draft/update creates audit event.
- Blocked risky action creates audit event.
- Tests cover audit creation and required fields.

## Ticket A9: sync job state

Owner: backend
Effort: 6-10h
Depends on: A1, A4, A5

Task:

- Create sync job model/table.
- Fields: job type, source, period, status, last success, last error, retry count, next run, staleAfter, linked source registry entry.
- Add one no-op Celery task that updates job state.
- Do not schedule real WB polling yet.

Done:

- Job can move queued -> running -> success/failure.
- Failed job records structured error.
- Source registry can reflect stale/last error state.
- Tests cover retry count and stale state.

## Ticket A10: Sprint A API stubs

Owner: backend
Effort: 8-12h
Depends on: A3-A9

Task:

- Add contract-shaped stubs for first frontend/backend integration:
  account health, source registry, settings draft/version list, audit list, sync jobs.
- For unresolved WB data, return typed blocked/unknown states with blocker IDs.
- No real price apply endpoint beyond a blocked placeholder.

Done:

- API stubs match common envelope.
- unresolved source returns blocker ID and next valid action.
- price apply placeholder always returns blocked until Sprint B gates are met.
- tests cover happy stub and blocked states.

## Ticket A11: contract export plan

Owner: frontend/backend
Effort: 4-6h
Depends on: A2

Task:

- Review current draft sources:
  `frontend/src/features/wb-repricer/schemas.ts` and `frontend/src/mocks/handlers.ts`.
- Review `docs/api-contracts/wb-19-05-contract-delta.md` and split each section into:
  `ready for Zod`, `needs backend discovery`, `client question`, `out of Sprint A`.
- Mark each surface as `ready`, `needs backend review`, or `replace in Sprint A`.
- Decide how OpenAPI artifact will be passed before separate `contracts/` repo exists.

Done:

- Backend repo README links to the chosen OpenAPI artifact/process.
- Contract gaps are listed before Sprint B.
- 19.05 contract delta has an owner and next action for each section.
- No backend model is hand-written where a generated model is expected.

## Ticket A11.1: 19.05 source-state stubs

Owner: backend + frontend contract review
Effort: 4-8h
Depends on: A4, A5, A11
Implementation pack: `docs/handoffs/wb-backend-sprint-a-stub-pack.md`

Task:

- Add blocked/partial stub responses for the 19.05 report/action surfaces:
  P&L, Ads performance, РНП, ABC filtered summary, SPP price guard, plan-fact brand dimension, AI reviews approval gate.
- Do not implement real formulas yet.
- Each stub must expose source status, confidence and blocker IDs from `docs/open-questions-current.md`.

Done:

- P&L final state is blocked until WB-12/WB-13 are confirmed.
- Ads/РНП return partial/blocked states until WB-02/WB-11 are confirmed.
- ABC includes a contract-shaped `filteredSummary` with source status.
- SPP guard returns `canApply=false` while WB-22/WB-23 are unresolved (even with confirmed WB-06 source).
- Plan-fact brand dimension is disabled or unknown until WB-14A is confirmed.
- AI reviews expose approval state and cannot auto-send low-rating replies.

## Ticket A12: Sprint A demo package

Owner: backend
Effort: 2-4h
Depends on: A0-A11.1
Acceptance pack: `docs/handoffs/wb-backend-sprint-a-demo-request.md`

Task:

- Prepare demo notes:
  how to run, what endpoints exist, which blockers are represented, what is intentionally not implemented.
- Include sample API responses for ready/blocked/stale/error.
- Include next-step recommendation for Sprint B.

Done:

- Demo proves foundation without pretending production readiness.
- Stakeholders can see why price engine is gated.
- Next Sprint B blockers are explicit: WB-22, WB-23 (`WB-06` resolved 27.05.2026).

## Critical path

```text
A0 repo skeleton
  -> A1 infra baseline
  -> A2 common contracts
  -> A3 account/token health
  -> A4 adapter envelope
  -> A5 source registry
  -> A6 settings model
  -> A7 permissions
  -> A8 audit
  -> A9 sync jobs
  -> A10 API stubs
  -> A11 contract export plan
  -> A11.1 19.05 source-state stubs
  -> A12 demo package
```

A3-A9 can be partially parallel after A1/A2 if the write scopes are separated.

## Sprint A risks

| Risk | Impact | Mitigation |
|---|---|---|
| WB token/scopes are unavailable | Blocks live discovery | Implement unknown/missing_access states and identify access owner. |
| Contract repo is not created | Backend/frontend drift | Use versioned OpenAPI artifact from this project temporarily. |
| Developer starts price engine too early | Wrong assumptions around СПП/apply/status | Keep price apply as blocked placeholder until Sprint B gates. |
| Mock endpoints are treated as production truth | Wrong data model | Treat frontend mocks as draft contracts only; source registry wins. |
| Financial visibility is unclear | P&L leaks or wrong final states | Gate finance by `finance_viewer`; final P&L disabled until WB-12/WB-13. |
| 19.05 UI surfaces are mistaken for backend readiness | P&L/Ads/РНП/SPP appear done while sources are unresolved | Use source-state stubs and blocker IDs from `wb-19-05-contract-delta.md`. |

## Sprint B entry gates

Sprint B starts only when:

- settings model is frozen enough for guard defaults;
- source registry contains confirmed or blocked entries for critical price inputs;
- WB-06 SPP source/fallback is resolved (confirmed on 27.05.2026);
- WB-22 price apply/status/errors are mapped;
- WB-23 freshness/confidence rules exist for critical sources;
- approval/audit primitives are working.
- 19.05 surfaces have reviewed contracts or explicit blocked/client-question states.
