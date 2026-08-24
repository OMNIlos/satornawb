# Backend Checklist Delta: Source Registry Gate

Дата: 2026-05-25
Статус: delta к `docs/handoffs/indeepa-wb-backend-checklist.md` и `docs/handoffs/wb-backend-sprint-a-tickets.md`.
Scope: WB first / INDEEPA replacement.

## 1. Что меняется

Существующий backend handoff остается актуальным. Эта delta добавляет обязательный gate: перед Sprint B/C/D backend должен не просто поднять stubs, а заполнить source registry и formula catalog для production surfaces.

Новый обязательный пакет:

- `docs/handoffs/wb-backend-data-handoff-index.md`;
- `docs/handoffs/wb-backend-source-registry.md`;
- `docs/handoffs/wb-backend-formula-catalog.md`;
- `docs/handoffs/wb-backend-reuse-dependency-map.md`;
- `docs/client-questions-wb-data-handoff-2026-05-25.md`.

## 2. Sprint A delta

Add to Sprint A Definition of Done:

- source registry seed loaded for all rows in `wb-backend-source-registry.md`;
- every seeded row has status, fallback, freshness rule, confidence, and blocker IDs;
- formula catalog entries are represented as formula IDs or versioned constants in backend code/config;
- unresolved rows return typed API states, not mock values;
- blockers from `docs/open-questions-current.md` are linked to concrete screens/metrics;
- backend demo includes examples of `confirmed`, `needs_client`, `needs_api_discovery`, `manual_fallback`, and `blocked` rows.

## 3. Sprint B gate

Do not start production price engine until:

- `WB-06` is resolved (2026-05-27): confirmed source via `POST /api/v2/list/goods/filter` + fallback from `discountedPrice/clubDiscountedPrice`;
- `WB-22` has confirmed WB price apply endpoint, polling and row-level error behavior;
- `WB-23` critical freshness/confidence rules are implemented for price sources;
- COGS import/manual source is available;
- P_min/P_max formulas have test fixtures for before-SPP and after-SPP edit modes;
- price apply placeholder still blocks external send when any critical row is stale/partial/blocked.

Gate status:

- `PASS` as of 2026-05-28 for backend workflow surfaces (`recommendation -> draft -> approve -> apply job`).
- Direct commit endpoint is explicitly blocked unless flow goes through draft/approval guards.

Allowed before gate:

- local dry-run;
- API stubs;
- blocked placeholders;
- schema generation;
- UI integration against blocked/partial states.

## 4. Sprint C gate

Do not enable strategy-generated production drafts until:

- 4599 inputs have source mapping and enough historical coverage;
- 4600 mode is confirmed by Maria;
- strategy scope policy is enforced (v1: SKU-level assignment);
- 4445 remains `disabled/discovery_required` unless `WB-25` is resolved;
- strategy output stores formula version, source snapshot and guard reasons.

Gate status:

- `PASS` for typed strategy dry-run/audit API as of 2026-05-28.
- `PASS` for strategy assignment scope: `WB-14` confirmed as SKU-level (`vendorCode`) on 2026-05-28.

## 5. Sprint D gate

Do not mark NRP/P&L finance as final until:

- `WB-02` Ads source and attribution are proven;
- `WB-24` finance visibility/export permissions are implemented.

Before gate, return `operative`, `preliminary`, `manual_input`, `not_set` or `no_access` states.

## 6. Client question loop

Use `docs/client-questions-wb-data-handoff-2026-05-25.md` for the client-facing part. Do not send backend/internal blocker language to the client as-is.

After answers arrive:

1. Update `docs/open-questions-current.md`.
2. Update affected registry rows.
3. Update formula status/version.
4. Add fixtures or acceptance examples.
5. Only then move the relevant ticket out of `blocked`.

## 7. Acceptance checklist for backend handoff

- A new backend developer can open `wb-backend-data-handoff-index.md` and know where every source/formula question lives.
- Every WB screen has at least one registry row for its key metrics/actions.
- Every production formula has owner/status and downstream usage.
- Every blocker has a concrete affected surface.
- Sprint B is explicitly blocked by missing critical source mapping, not by vague "needs discovery" prose.
