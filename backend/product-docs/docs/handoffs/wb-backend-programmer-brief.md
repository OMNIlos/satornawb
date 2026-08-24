# Brief для backend-разработчика: WB / INDEEPA replacement

Дата: 2026-05-21
Кому: backend-разработчик WB-модуля
Статус: можно отправлять как первое сообщение перед стартом

## Контекст

Нужно подготовить backend для WB first / INDEEPA replacement в Vella. Это не Авито и не production-заказы. Первый этап - foundation/discovery, а не отправка цен.

Backend планируется в отдельном repo на FastAPI. Текущий проект остается source-of-truth для PRD, frontend, mock API, Vella design contract и API contracts.

## С чего начать

Открой сначала этот файл:

- `docs/handoffs/wb-backend-dev-package.md`

Потом по порядку:

1. `docs/specs/indeepa-wb-replacement/README.md`
2. `docs/specs/indeepa-wb-replacement/00-master-prd.md`
3. `docs/specs/indeepa-wb-replacement/11-readiness-matrix.md`
4. `docs/handoffs/wb-backend-data-handoff-index.md` - карта данных: sources, formulas, dependencies, questions and gates
5. `docs/handoffs/wb-backend-source-registry.md` - seed registry по экранам/метрикам/источникам/fallback/blockers
6. `docs/handoffs/wb-backend-formula-catalog.md` - formulas, owners, statuses and downstream usage
7. `docs/handoffs/wb-backend-reuse-dependency-map.md` - shared dependencies and action blockers
8. `docs/handoffs/indeepa-wb-backend-checklist.md`
9. `docs/handoffs/wb-19-05-action-backlog.md` - meeting delta 19.05: P&L mapping, ads/РНП, SPP safeguards, Service Token
10. `docs/handoffs/wb-19-05-implementation-roadmap.md` - этапы реализации уточнений 19.05
11. `docs/handoffs/wb-19-05-phase-0-1-kickoff.md` - что стартует сразу: клиентские вопросы + backend Sprint A
12. `docs/handoffs/wb-19-05-vella-gap-check.md` - что уже есть в Vella UI, а что требует backend contracts/source evidence
13. `docs/open-questions-current.md`
14. `docs/api-contracts/README.md`
15. `docs/api-contracts/wb-19-05-contract-delta.md` - draft полей/состояний для P&L, ads, РНП, ABC, SPP guard, plan-fact, AI reviews
16. `docs/handoffs/wb-19-05-backend-contract-handoff.md` - OpenAPI/Pydantic handoff и инварианты, которые backend должен повторить
17. `docs/handoffs/wb-backend-sprint-a-stub-pack.md` - первый FastAPI stub pack: endpoints, blocker seed, negative tests
18. `docs/handoffs/wb-backend-sprint-a-demo-request.md` - что показать на первом Sprint A demo и критерии приемки
19. `docs/constraints.md`

Если занимаешься WB автоответами или любым AI/agent действием, дополнительно читать:

- `docs/architecture/agent-harness-standard.md`
- `docs/evals/ai-agent-evals.md`

## Первый рабочий срез

Sprint A: discovery/foundation.

Цель Sprint A - создать backend основу и явно зафиксировать неизвестные источники, а не имитировать production. Если источник не подтвержден, endpoint должен возвращать typed `blocked`, `unknown` или `stale` state, а не декоративные данные.

Sprint A включает:

- FastAPI repo skeleton;
- PostgreSQL + Alembic;
- Redis + Celery/Celery Beat baseline;
- WB account/token health;
- source registry;
- formula catalog and dependency blockers from the data handoff package;
- typed settings model;
- permissions;
- audit primitive;
- adapter result envelope;
- sync job state;
- contract-shaped API stubs.

## Технологический baseline

- Python 3.11+
- FastAPI
- PostgreSQL
- Redis
- Celery + Celery Beat
- Alembic
- Pydantic v2
- REST `/api/v1/*`
- UUID v4 для внутренних ID
- деньги в копейках integer
- даты ISO 8601 UTC
- WB API только через typed adapters

## Contract workflow

Не писать Pydantic модели вручную по скриншотам или mock handlers.

Правильный поток:

```text
Zod schema -> OpenAPI -> generated Pydantic -> FastAPI implementation
```

Текущие draft sources:

- `frontend/src/features/wb-repricer/schemas.ts`
- `frontend/src/features/wb-reports/schemas.ts`
- `frontend/src/features/wb-contracts/sourceState.ts`
- `contracts/openapi/v1.yaml`
- `frontend/src/mocks/handlers.ts`
- `docs/api-contracts/README.md`
- `docs/handoffs/wb-19-05-backend-contract-handoff.md`
- `docs/handoffs/wb-backend-sprint-a-stub-pack.md`
- `docs/handoffs/wb-backend-sprint-a-demo-request.md`

Если нужного контракта нет, сначала обсуждаем и фиксируем schema/OpenAPI, потом реализуем backend.

## Нельзя делать на первом этапе

- Не начинать с price apply.
- Не отправлять цены в WB без backend guards, approval и audit.
- Не делать WB auto-actions management через API: API управления автоакциями нет, только `minPrice` protection.
- Не реализовывать `4445` как production strategy без подтвержденных правил Марии.
- Не считать P&L final без формул Максима по налогам, хранению и общим расходам.
- Не делать auto-send ответов на отзывы; только draft-first + approval + evals + trace.
- Не строить full INDEEPA rule-builder parity без отдельного change request.

## Главные blockers

Смотреть полный список в `docs/open-questions-current.md`. Для Sprint A критичны:

- WB-01 local orders source for localization index;
- WB-02 WB Ads per-SKU/per-period;
- WB-03 endpoint/field mapping по WB reports;
- WB-04 liquidation criteria;
- WB-06 SPP source and fallback;
- WB-17 warehouse decision formula;
- WB-18 available stock fields;
- WB-22 price apply/status/errors;
- WB-23 source freshness/confidence registry.

## Что должно быть на демо Sprint A

- Локально поднимается backend skeleton.
- Есть миграции и seed/test data для одной WB account и нескольких SKU.
- Есть модели/tables для account/token health, source registry, settings, permissions, audit, sync jobs.
- Adapter envelope возвращает structured success/blocked/stale/error states.
- API stubs не притворяются production: unresolved sources возвращают blocker IDs.
- Есть короткий README в backend repo: как поднять локально, как прогнать tests, где contracts.

## Как эскалировать

Сразу поднимать вопрос, если:

- WB token/scopes не дают нужный доступ;
- нет надежного источника СПП;
- WB Ads не поддерживает нужную атрибуцию;
- price apply не дает row-level status/errors;
- кто-то просит отправлять реальные цены до guards/audit;
- scope начинает расползаться в full INDEEPA parity или Авито.

## Главный принцип

Лучше честный `blocked_by_source_mapping` в API, чем красивый mock, который потом примут за готовый production backend.
