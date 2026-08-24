# 00 START HERE

Короткая карта проекта для нового человека или AI-агента.

## 1. Что это за repo

Это product/source-of-truth repo по Vella для "Огней":

- ТЗ и scope;
- PRD/specs;
- handoff для backend/frontend/UAT;
- frontend implementation and visual contract;
- API contracts and mock contracts;
- research/evidence from calls, screenshots, audits;
- open questions and blocker register.

Production backend должен жить отдельно: `ogni-vella-backend`.

## 2. Текущий фокус

WB first / INDEEPA replacement:

- WB repricer;
- WB reports / NRP-lite;
- P&L, РнП, ABC, stock, week-over-week;
- liquidation;
- WB review autoreplies draft-first.

Авито и production-заказы идут вторым этапом, если задача явно не говорит обратное.

## 3. Entry points by role

| Роль | Читать |
|---|---|
| Backend developer | `docs/handoffs/wb-backend-programmer-brief.md` |
| Backend developer, data mapping | `docs/handoffs/wb-backend-data-handoff-index.md` |
| Frontend developer | `frontend/README.md`, `docs/design-system/vella-source-of-truth.md` |
| PM/Фил | `docs/client-summary-indeepa-wb-replacement-2026-05-19.md`, `sprint-backlog.md` |
| Client questions | `docs/client-questions-wb-data-handoff-2026-05-25.md` |
| AI agent | `AGENTS.md`, then this file, then task-specific handoff/spec |

## 4. Current source-of-truth stack

| Layer | Source |
|---|---|
| Project rules | `AGENTS.md` |
| Current blockers | `docs/open-questions-current.md` |
| WB approved TZ | `ТЗ/TZ-WB.md` |
| Avito approved TZ | `ТЗ/TZ-Avito.md` |
| WB backend handoff | `docs/handoffs/wb-backend-dev-package.md` |
| WB data mapping | `docs/handoffs/wb-backend-source-registry.md` |
| WB formulas | `docs/handoffs/wb-backend-formula-catalog.md` |
| WB dependency map | `docs/handoffs/wb-backend-reuse-dependency-map.md` |
| API contracts | `docs/api-contracts/`, `contracts/openapi/v1.yaml` |
| Frontend design source | `frontend/public/vella-production.html` |

## 5. Folder map

See full map: `docs/PROJECT_STRUCTURE.md`.

## 6. Working rule

If a metric/action is not mapped to source/formula/fallback/freshness/blocker, it is not production-ready. Backend should return typed blocked/unknown/stale/partial states instead of pretending the data is ready.
