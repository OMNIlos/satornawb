# WB Backend Dev Package: INDEEPA replacement

Дата: 2026-05-21
Статус: entrypoint для backend-разработчика перед Sprint A.
Scope: только WB first / INDEEPA replacement. Авито и производство заказов не входят в первый backend cut.

## 1. Цель передачи

Backend должен подготовить production-контур замены INDEEPA по WB: данные, настройки, guards, расчеты, фоновые jobs, audit, NRP-lite и Excel pipelines. Первый инженерный шаг - не price engine, а Sprint A discovery/foundation, потому что критичные источники WB, СПП, Ads, freshness и price apply behavior еще должны быть подтверждены.

Дефолт по организации: backend живет в отдельном repo на FastAPI, а этот проект остается source-of-truth для PRD, frontend, mock API, design contract и contract workflow.

## 2. Read first

| Файл | Зачем читать |
|---|---|
| `docs/specs/indeepa-wb-replacement/README.md` | Навигация по PRD-пакету WB replacement. |
| `docs/specs/indeepa-wb-replacement/00-master-prd.md` | Границы v1, hardening, full parity и change request. |
| `docs/specs/indeepa-wb-replacement/11-readiness-matrix.md` | Какие PRD идут в какие sprint cut и какие blockers держат старт. |
| `docs/handoffs/wb-backend-data-handoff-index.md` | Новый entrypoint по карте данных: source registry, formula catalog, dependencies, client questions и Sprint B gate. |
| `docs/handoffs/wb-backend-source-registry.md` | Рабочая таблица `экран -> метрика -> источник -> поле -> формула -> fallback -> freshness -> blocker`; обязательна для Sprint A. |
| `docs/handoffs/wb-backend-formula-catalog.md` | Формулы, inputs/outputs, owner, статус подтверждения и downstream usage. |
| `docs/handoffs/wb-backend-reuse-dependency-map.md` | Какие данные переиспользуются между репрайсером, отчетами, P&L, РнП, stock и risky actions. |
| `docs/handoffs/indeepa-wb-backend-checklist.md` | Инженерный checklist Sprint A-E. |
| `docs/handoffs/wb-backend-checklist-delta-source-registry.md` | Delta к checklist: source registry gate перед Sprint B/C/D. |
| `docs/handoffs/wb-backend-sprint-a-stub-pack.md` | Конкретный first-stub pack: endpoints, blocker seed, negative tests для первых 2-3 дней FastAPI. |
| `docs/handoffs/wb-backend-sprint-a-demo-request.md` | Что показать на первом Sprint A demo: команды, URL, JSON-инварианты и fail criteria. |
| `docs/open-questions-current.md` | Актуальные `BLOCKER / CONFIRM / LATER`; старые open questions не брать в работу. |
| `docs/api-contracts/README.md` | Contract workflow `Zod -> OpenAPI -> Pydantic` и backend-start правила. |
| `docs/constraints.md` | Жесткие ограничения WB/Авито/производства, которые нельзя обходить обещаниями. |
| `docs/architecture/agent-harness-standard.md` | Обязателен для WB автоответов и AI/agent действий. |
| `docs/evals/ai-agent-evals.md` | Eval gates для автоответов, AI-рекомендаций, risky actions. |

Historical audits, screenshots, `outputs/` and archived research are evidence, not implementation entrypoints. Open them only when a PRD or blocker links to them directly.

## 3. Repo and stack decision

Backend repo: separate repository.

Baseline stack:

- Python 3.11+;
- FastAPI;
- PostgreSQL;
- Redis;
- Celery + Celery Beat;
- Alembic migrations;
- typed external adapters for WB APIs;
- generated Pydantic v2 models from OpenAPI contracts where frontend/backend API is already contracted.

This repo remains:

- PRD and scope source;
- frontend/mock API source;
- Vella design-system and visual contract source;
- contract source until a shared `contracts/` repo exists;
- handoff and UAT package source.

## 4. Backend boundaries

External WB API calls must go through typed adapters. Route handlers and domain services must not call WB directly.

Minimum adapter envelope:

```ts
type AdapterResult<T> = {
  status:
    | "success"
    | "partial"
    | "empty"
    | "stale"
    | "not_authorized"
    | "missing_capability"
    | "blocked_by_guard"
    | "rate_limited"
    | "external_error"
    | "unknown_error";
  data?: T;
  warnings: Array<{ code: string; message: string }>;
  error?: {
    code: string;
    message: string;
    retryable: boolean;
    retryAfterSeconds?: number;
    rawRef?: string;
  };
  freshness: {
    source: string;
    fetchedAt: string;
    staleAfter?: string;
    isStale: boolean;
    confidence: "high" | "medium" | "low" | "unknown";
  };
  evidenceRefs: string[];
  nextValidActions: string[];
};
```

Internal API baseline:

- REST under `/api/v1/*`;
- ISO 8601 UTC dates only;
- money in kopecks integer;
- UUID v4 for internal IDs, external WB IDs stored separately;
- typed error envelope: `{ "error": { "code": "...", "message": "...", "details": {} } }`;
- pagination: `limit/offset` plus `items/total`;
- risky actions use `draft -> preview/diff -> approval -> commit -> audit`.

## 5. Sprint A: first backend cut

Sprint A can start after three gates:

- WB account/token access is available for safe discovery.
- Current PRD-pack is accepted as implementation baseline.
- `docs/open-questions-current.md` is acknowledged as the active blocker register.

Sprint A deliverables:

- WB account/token health model: token status, scopes, expiry, missing capabilities.
- Source registry: screen, metric, source, field, formula, refresh frequency, fallback, freshness, confidence, blocker ID.
- Seed and expose the registry rows from `docs/handoffs/wb-backend-source-registry.md`, including status and blocker IDs.
- Link formula IDs/statuses from `docs/handoffs/wb-backend-formula-catalog.md` to dependent metrics/actions.
- Use `docs/handoffs/wb-backend-reuse-dependency-map.md` to block downstream risky actions when shared inputs are unknown/stale.
- Typed settings model for 17 INDEEPA parameters with enum/range validation.
- Settings versioning with diff, approval state and audit event.
- Permission checks for `viewer`, `settings_editor`, `price_sender`, `finance_viewer`, `admin`.
- Adapter skeleton and structured adapter result envelope.
- Sync job table/state for polling, last success, last error, retry/backoff.
- Audit primitive with actor, action, object, before/after, reason, approval ref and evidence refs.
- 19.05 first stubs from `docs/handoffs/wb-backend-sprint-a-stub-pack.md`: P&L, Ads, РНП, ABC and SPP guard return contract-shaped blocked/partial states.
- Sprint A demo follows `docs/handoffs/wb-backend-sprint-a-demo-request.md`: health, registry seed, five stubs, negative tests and explicit non-production states.

Sprint A is accepted when a developer can show a local backend skeleton, migrations, seed/test data for account/settings/source registry, and contract-shaped API stubs that return blocked/unknown states instead of pretending production data is ready.

Sprint B does not start until the source registry gate in `docs/handoffs/wb-backend-checklist-delta-source-registry.md` is resolved for price-critical rows: СПП, price planes, COGS/economics, P_min/P_max, freshness/confidence and WB price apply/status.

## 6. v1 / hardening / out

v1 replacement minimum:

- WB repricer on real data with SKU table, drawer, margin calculation, price drafts and apply jobs.
- Typed settings model and strategies `4599`, `4600`, night mode; `4445` only as `discovery_required` until Мария confirms rules.
- Price guards: P_min/P_max, per-update/per-day, promo/min_price, negative margin block.
- Input guards: СПП, остатки, COGS, логистика, выкуп, промо, source stale.
- Roles, audit trail, source freshness, Excel import/export.
- NRP-lite: Unit P&L, plan-fact, РнП funnel, SKU rating.

Production hardening:

- richer retry/backoff and status polling;
- formula and strategy versioning;
- larger table/export pipelines;
- integration monitoring dashboard;
- fuller source confidence and stale-data diagnostics.

Out / change request:

- full INDEEPA rule-builder parity;
- Ozon/cross-marketplace;
- competitor following;
- direct 1C integration;
- PDF/share reports as required v1;
- black-box clone of `Indeepa.Index`.

## 7. Do not implement yet

- WB auto-actions management through API. API управления автоакциями нет; only `minPrice` protection.
- `spp_turnover_4445` as production strategy before Мария confirms rules.
- Final P&L and final plan-fact without Максим's storage, tax and overhead allocation formulas.
- Auto-send WB review replies. Start draft-first with approval, evals, trace and prompt caching telemetry.
- Any WB price apply that bypasses backend guards, approval and audit.
- Any price action based on stale/partial critical sources without explicit blocked state.
- Broad custom rule-engine as INDEEPA parity unless separately approved as change request.

## 8. Current blockers for backend

Start with these WB blockers from `docs/open-questions-current.md`:

| ID | Backend impact |
|---|---|
| WB-01 | Local orders source for localization index. |
| WB-02 | WB Ads per-SKU/per-period source and attribution. |
| WB-03 | Endpoint/field mapping for all WB reports. |
| WB-04 | Liquidation criteria and AND/OR rules. |
| WB-06 | Reliable SPP source and fallback. Resolved 27.05.2026 via `POST /api/v2/list/goods/filter`. |
| WB-17 | Warehouse decision formula. |
| WB-18 | Available stock and `к клиенту` / `от клиента` fields. |
| WB-22 | WB price apply endpoint, status polling, row errors and retry/backoff. |
| WB-23 | Source freshness/confidence registry rules. |

Confirm before hard production implementation:

| ID | Backend impact |
|---|---|
| WB-11 | ROI/ДРР/margin formulas in РнП. |
| WB-12 | Storage and overhead allocation. |
| WB-13 | Tax/VAT base and percentages. |
| WB-14 | Strategy application level. |
| WB-16 | Brand rules and stop-topics for WB autoreplies. |
| WB-19 | INDEEPA product status thresholds. |
| WB-24 | Financial permissions and export visibility. |
| WB-25 | 4442/4445 strategy rules and v1/P2 boundary. |

## 9. Contract inventory

Existing frontend/mock surfaces are useful as draft contracts, not final backend truth.

| Surface | Current source | Status for backend |
|---|---|---|
| SKU list/settings/comment/audit schemas | `frontend/src/features/wb-repricer/schemas.ts` | Ready as draft Zod source; needs OpenAPI export and backend review. |
| Changelog schemas | `frontend/src/features/wb-repricer/schemas.ts` | Ready as draft Zod source; needs apply-job alignment. |
| Manual/bulk action request schemas | `frontend/src/features/wb-repricer/schemas.ts` | Needs backend review for approval and guard flow. |
| `/api/v1/wb-repricer/sku` | `frontend/src/mocks/handlers.ts` | Mock endpoint; backend must connect to real SKU/source registry. |
| `/api/v1/wb-repricer/sku/:articleId/settings` | `frontend/src/mocks/handlers.ts` | Draft contract; add versioning, approval and audit semantics. |
| `/api/v1/wb-repricer/dashboard` | `frontend/src/mocks/handlers.ts` | Needs backend review; source mapping required. |
| `/api/v1/wb-repricer/templates` | `frontend/src/mocks/handlers.ts` | Draft settings/preset surface; align with typed settings model. |
| `/api/v1/wb-repricer/liquidation*` | `frontend/src/mocks/handlers.ts` | Needs blocker WB-04 and approval/audit semantics. |
| `/api/v1/wb-repricer/algorithm` | `frontend/src/mocks/handlers.ts` | Draft only; align with Sprint C strategy model. |
| `/api/v1/wb-repricer/promotions*` | `frontend/src/mocks/handlers.ts` | Needs WB promotions/source proof; no auto-actions API promise. |
| `/api/v1/wb-repricer/changelog` | `frontend/src/mocks/handlers.ts` | Draft audit/read model; align with apply jobs. |

## 10. AI/reviews rule

WB autoreplies are an agent/LLM feature and must follow `docs/architecture/agent-harness-standard.md`.

Default MVP:

- autonomy Level 2: draft-only;
- model drafts and classifies, backend/harness validates and records;
- external send requires approval tied to a specific preview;
- prompt layout must be cache-friendly: stable tools/system/brand rules first, volatile review/order/tool results last;
- eval pack from `docs/evals/ai-agent-evals.md` is required before production.

Fail conditions:

- reply sent without approval;
- model claims send/apply success without tool confirmation;
- external review text overrides project/TZ instructions;
- sensitive buyer/seller data leaks into generated output or trace.

## 11. Escalate immediately

- WB token cannot expose required categories/scopes.
- WB Ads data is unavailable or cannot support `exact_sku / campaign_sku / campaign_only` attribution.
- SPP source is absent or unstable and no fallback is accepted.
- Price apply cannot return row-level result/status.
- Anyone asks to send prices before guards/audit exist.
- Anyone asks to mark final financial truth before Максим confirms formulas.
- Scope pressure appears to include full INDEEPA parity or custom rule-builder in v1.

## 12. Handoff acceptance

The package is ready for backend start when:

- this file is the only entrypoint sent to the developer;
- `docs/handoffs/indeepa-wb-backend-checklist.md` is accepted as Sprint A-E checklist;
- separate backend repo decision is acknowledged;
- WB account/token access owner is named;
- blocker register is current;
- contract workflow is accepted: Zod/OpenAPI first, Pydantic generation in backend repo;
- risky-action policy is accepted: no external price/review side effects without preview, approval, commit result and audit.
