# Backend checklist: INDEEPA WB replacement

Дата: 2026-05-21
Основа: PRD-пакет `docs/specs/indeepa-wb-replacement/` и entrypoint `docs/handoffs/wb-backend-dev-package.md`.

## Цель

Backend должен обеспечить production-контур WB replacement: источники данных, расчет цен, настройки, стратегии, guards, apply jobs, audit, NRP-lite и Excel pipelines.

Backend стартует в отдельном FastAPI repo. Этот проект остается source-of-truth для PRD, frontend/mock API, design contract и contract workflow. Первый рабочий срез - Sprint A discovery/foundation; price engine начинается только после source/guard gates.

## Общие backend-инварианты

- Route handlers не вызывают WB API напрямую: все внешние операции идут через typed adapters.
- Любая production-метрика имеет запись в `source registry` или blocker ID из `docs/open-questions-current.md`.
- Любое рискованное действие идет через `draft -> preview/diff -> approval -> commit -> audit`.
- Деньги в API и БД хранятся в копейках integer; даты - ISO UTC.
- Внутренние ID - UUID v4; WB external IDs хранятся отдельно.
- Stale/partial critical source блокирует auto-apply и возвращает понятный blocked state.
- Raw external payloads не возвращаются в UI/model context; хранить sanitized refs для диагностики.

## Sprint A: source mapping + account/token + settings model

- Завести `source registry`: экран, метрика, источник, поле, формула, частота, fallback, freshness, confidence.
- Использовать `docs/handoffs/wb-backend-data-handoff-index.md` как entrypoint по карте данных.
- Seed source registry from `docs/handoffs/wb-backend-source-registry.md`.
- Link formulas/statuses from `docs/handoffs/wb-backend-formula-catalog.md`.
- Enforce shared dependency blockers from `docs/handoffs/wb-backend-reuse-dependency-map.md`.
- Подтвердить WB account health: token status, expiry, scopes, missing capabilities.
- Реализовать typed settings model для 17 параметров INDEEPA, включая отдельные enum/range-типы.
- Добавить settings versioning, diff, approval state и audit event.
- Подготовить backend permission checks: `viewer`, `settings_editor`, `price_sender`, `finance_viewer`, `admin`.
- Завести adapter result envelope: status, data, warnings, error, freshness, evidenceRefs, nextValidActions.
- Завести sync job state: job type, source, period, last success, last error, retry count, next run, staleAfter.
- Завести audit primitive: actor, role, action, object type/id, before/after, reason, approval ref, source/evidence refs.
- Подготовить blocked/unknown responses для неподтвержденных источников вместо production-заглушек.

Sprint A done:

- миграции под account/token health, source registry, settings versions, permissions, audit, sync jobs;
- local seed/test data для одной WB account и нескольких SKU;
- API stubs возвращают typed ready/blocked/stale states;
- blockers WB-01, WB-03, WB-22, WB-23 заведены в registry как blockers, если еще не подтверждены (`WB-06` resolved 2026-05-27, `WB-02` resolved 2026-06-01).
- Sprint B gate from `docs/handoffs/wb-backend-checklist-delta-source-registry.md` is explicitly marked pass/fail.

## Sprint B: repricer core + price guards + apply jobs

- Нормализовать SKU, цены до/после СПП, COGS, комиссии, логистику, хранение, налоги и P_min/P_max.
- Реализовать price draft: ручное изменение цены без отправки в WB.
- Реализовать price guards: P_min/P_max, per-update 6%, per-day 20%, min_price/promo, negative margin block.
- Реализовать input guards: СПП, остатки, COGS, логистика, выкуп, промо, source stale.
- Реализовать WB price apply job: draft -> approved -> queued -> sent -> accepted/failed.
- Логировать apply result, WB errors, retry/backoff и stop-required states.
- Разделить price recommendation, manual draft, approval request и external WB commit.
- Хранить formula version и source snapshot для каждого расчета цены.
- Не применять цену, если WB-22 или критичный WB-23 source остается unknown/stale.

Sprint B implementation status (2026-05-28):

- `POST /api/v1/wb-repricer/recommendation` нормализует SKU/economics + хранит `formulaVersion`/`sourceSnapshot`.
- `POST /api/v1/wb-repricer/drafts` создает manual draft без WB commit.
- `POST /api/v1/wb-repricer/drafts/{draftId}/approve` фиксирует approval ref/actor.
- `POST /api/v1/wb-repricer/drafts/{draftId}/apply` выполняет только approved draft с guard check и audit.
- `GET /api/v1/wb-repricer/jobs/{jobId}` и `POST /api/v1/wb-repricer/jobs/{jobId}/retry` покрывают job status + retry/backoff + stop-required.
- Legacy direct endpoint `/api/v1/wb-repricer/actions/price-apply` блокирует direct commit (`409`), чтобы нельзя было обойти draft/approval/guards.

Sprint B done:

- ни один endpoint не отправляет цену без approval и guards;
- row-level result по отправке цены сохраняется в apply job/audit;
- UI может отличить draft, queued, sent, accepted, failed, blocked и needs attention.

## Sprint C: typed strategies + dry-run

- Реализовать `baskets_orders_4599`: +3/+1/-1/-3%, cap, guards, explanation.
- Реализовать `revenue_dynamics_4600` только после выбора режима: percent-only или percent/rub floor.
- Реализовать `night_price_mode` off-by-default с явным schedule и audit.
- Завести `spp_turnover_4445` только как `disabled/discovery_required`, пока Мария не подтвердит правила.
- Для каждой стратегии хранить formula version, source dependencies, dry-run result и blocked guard reasons.
- Поддержать assignment стратегии на уровень артикула (SKU / `vendorCode`) по логике INDEEPA.
- Сделать dry-run endpoint/report перед включением стратегии в production.
- Ночной режим не включает auto-commit без отдельного approval/schedule audit.

Sprint C implementation status (2026-05-28):

- `GET /api/v1/wb-repricer/strategies/catalog` и `GET /api/v1/wb-repricer/strategies/{strategyId}/versions` отдают typed catalog + version history.
- `POST /api/v1/wb-repricer/strategies/{strategyId}/versions` версионирует стратегию с `formulaVersion`, `sourceDependencies`, `blockedReasons` и audit event.
- `POST /api/v1/wb-repricer/strategies/{strategyId}/dry-run` и `GET /api/v1/wb-repricer/strategies/{strategyId}/dry-runs` дают explainable dry-run report/history.
- `GET|PUT /api/v1/wb-repricer/night-schedule` держит `night_price_mode` off-by-default, schedule с явным `approvalRef`, и отдельный audit trail.
- `POST /api/v1/wb-repricer/strategy-assignments` разрешает assignment на `sku` и сохраняет audit; non-SKU scope блокируется политикой `SCOPE_SKU_ONLY_V1`.
- `spp_turnover_4445` остается `discovery_required`; dry-run не может создать production draft.

Sprint C done:

- 4599 и 4600 дают explainable dry-run на тестовых SKU;
- 4445 не может создать production draft;
- strategy changes версионируются и видны в audit.

## Sprint D: NRP-lite

- P&L: operative/preliminary/final states, COGS, комиссии, логистика, хранение, налоги, реклама, общие расходы.
- РнП: campaign attribution type `exact_sku`, `campaign_sku`, `campaign_only`; weak attribution не распределять в SKU P&L.
- План-факт: company/manager plan, fact, deviation, completion %, forecast, minimum per day.
- Рейтинг SKU: groups, score reasons, links to SKU/repricer/liquidation.
- No-access states для financial data и audit.
- Финансовые поля gated by `finance_viewer`; export тоже проверяет permission.
- Final P&L запрещен, пока WB-24 не подтвержден (финдоступы).
- Ads/P&L metrics обязаны ссылаться на source registry и attribution confidence.

Sprint D implementation status (2026-05-29):

- `GET /api/v1/wb-reports/pnl` поддерживает `source=operative|preliminary|final`; `final` возвращает blocked state до закрытия `WB-24`.
- `GET /api/v1/wb-reports/ads/performance` возвращает attribution policy (`exact_sku`, `campaign_sku`, `campaign_only`) и confidence; weak attribution не считается SKU P&L truth.
- `GET /api/v1/wb-reports/rnp` отдает funnel + confirmed DRR/ROI formulas; source blockers остаются только по ads/source/access.
- `GET /api/v1/wb-reports/abc` отдает filtered summary с динамическим `filterHash` и source/confidence metadata.
- `GET /api/v1/wb-reports/plan-fact` реализован для `dimension=company|manager|brand`: plan/fact/deviation/completion/forecast/min per day.
- `GET /api/v1/wb-reports/sku-rating` возвращает rating groups, explainable reasons и links к SKU/repricer/liquidation.
- `GET /api/v1/wb-export/current-view` проверяет `finance_viewer` и возвращает `ready|no_access` без утечки финансовых данных.
- Для ролей без `finance:read` финансовые поля redacted (`no_access` state), а audit фиксирует факт запроса/блокировки.

Sprint D done:

- P&L может быть `operative`, `preliminary` или `final`, но final недоступен без подтвержденных финдоступов (`WB-24`);
- weak ads attribution не размазывается по SKU;
- no-access states не раскрывают финансовые значения.

## Sprint E: Excel + big table pipelines

- Async import jobs: upload, mapping, validation, preview, approval, apply.
- Import types v1: prices, COGS, operating expenses, plan values.
- Export current view with filters, period, columns, source freshness metadata.
- Row-level validation: valid rows, blocked rows, partial apply.
- Audit original import file metadata, actor, approval and affected rows.
- XLSX import не применяет изменения сразу: сначала preview, validation, diff and approval.
- Export сохраняет параметры фильтра, период, columns, source freshness/confidence.
- Большие таблицы должны поддерживать async jobs and pagination/streaming, а не блокирующий request.

Sprint E done:

- partial import сохраняет valid/blocked rows separately;
- original file metadata and hash are auditable;
- financial export respects `finance_viewer`.

## WB autoreplies / AI harness

- MVP autonomy: Level 2 draft-only.
- External send only after approval tied to exact draft/review/account.
- Follow `docs/architecture/agent-harness-standard.md` and `docs/evals/ai-agent-evals.md`.
- Prompt caching must keep stable prefix first: tools, system rules, brand/TZ/rules; volatile review/tool results last.
- Log prompt bundle version, tool bundle version, cached tokens where provider supports it, approval state and final tool result.
- Fail production if reply is sent without approval or model claims success without tool confirmation.

## Do not implement yet

- WB auto-actions management through API; API does not exist, use `minPrice` protection only.
- `spp_turnover_4445` production logic without confirmed Maria rules.
- Final P&L without Максим's tax/storage/overhead formulas.
- Auto-send WB review replies before approval UX, eval pack, audit and prompt caching telemetry.
- Any WB price apply without backend guards and audit.
- Full custom rule-builder / full INDEEPA parity unless separately approved as change request.

## Acceptance

- Ни один price apply не обходит backend guards.
- Все production метрики имеют source mapping или явный blocker.
- Все price-critical метрики имеют fallback/freshness/confidence или явно блокируют Sprint B.
- Все production формулы имеют owner/status/version placeholder before they feed recommendations or finance.
- Все risky actions имеют actor, diff/preview, approval или block reason.
- `4445` не может создать production price draft без подтвержденных правил.
- Финансовые поля не доступны без `finance_viewer`.
- Backend developer can start Sprint A from `docs/handoffs/wb-backend-dev-package.md` without reading historical/archive docs first.
- Separate backend repo pulls/receives OpenAPI contracts and generates Pydantic models without manual schema rewrites.
