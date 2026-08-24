# Avito v1 Implementation Handoff

Дата: 2026-05-19  
Статус: handoff для backend/frontend/QA перед AV-A.

## 1. Read first

| File | Why |
|---|---|
| `docs/specs/avito-v1/README.md` | Navigation across the full Avito package. |
| `docs/specs/avito-v1/02-master-prd.md` | Scope, IA, roles, shared states, risky action policy. |
| `docs/specs/avito-v1/10-api-discovery-register.md` | Current API status and blockers. |
| `docs/specs/avito-v1/11-avito-adapter-contract.md` | Backend adapter ports, errors, jobs, audit. |
| `docs/specs/avito-v1/12-api-discovery-uat-checklist.md` | Safe live-account verification plan. |
| `docs/specs/avito-v1/13-implementation-backlog.md` | Sprint slicing AV-A..AV-I. |
| `docs/specs/avito-v1/14-frontend-screen-spec.md` | Frontend route-by-route handoff. |
| `docs/specs/avito-v1/15-data-model-and-internal-api.md` | Internal entities and `/api/avito/*` draft. |

## 2. Implementation order

Do not start screen feature work before AV-A/AV-B foundation is clear.

1. AV-A: safe API UAT on one account.
2. Adapter base: auth, errors, rate limits, freshness, capability matrix.
3. Accounts/readiness UI.
4. Read-only data surfaces: listings, stats, chats, reviews, orders, wallets.
5. Draft-only surfaces: listing drafts, bot replies, review replies, photo drafts.
6. Approval previews for risky actions.
7. External write commits only after explicit capability proof and approval flow.

## 3. Backend handoff

Build around adapter boundaries:

- no direct Avito calls from route handlers;
- all Avito reads return `AvitoAdapterResult<T>`;
- all risky writes split into `prepare*` and `commitApproved*`;
- every source has `sourceFetchedAt`, `staleAfter`, `isStale`;
- every unsupported feature returns capability blocker, not generic 500;
- raw payload refs are sanitized and access-controlled.

Backend deliverables for AV-A/AV-B:

- token/auth model;
- encrypted credential storage;
- account profile read;
- capability matrix table and service;
- sync job table;
- adapter error mapping;
- audit event primitive;
- sanitized payload note template.

## 4. Frontend handoff

Use production Vella design only:

- `frontend/public/vella-production.html`;
- `docs/design-system/vella-source-of-truth.md`;
- existing shell/sidebar/topbar/table/drawer/chip/button/modal patterns.

Do not create a new Avito dashboard visual style.

Frontend deliverables for AV-B:

- `/avito/overview` scaffold;
- `/avito/accounts` table;
- capability drawer;
- sync/freshness states;
- role/no-access states;
- disabled buttons with reasons/tooltips;
- partial/stale banners.

## 5. QA handoff

Required QA gates:

- no message sent during discovery;
- no review reply sent/deleted;
- no XML/autoload uploaded to real account;
- no listing changed/deactivated;
- no payment/top-up executed;
- no tariff/integration/token/team access changed;
- no delivery status mutation;
- raw payloads sanitized.

Visual QA before accepting each screen:

- default state;
- filters/dropdowns;
- drawer;
- modal/approval preview;
- empty;
- partial;
- stale;
- no-access;
- disabled risky action;
- mobile simplified state where route supports mobile.

## 6. Non-negotiable product rules

- XML publish is blocked unless full-feed validation passes and approval exists.
- `stop`/full-close XML hazard is blocked by default.
- Wallet v1 starts as monitoring/alerts/manual task, not real auto-top-up.
- Return QR automation is not promised until endpoint/workflow is proven.
- Bot/reviews/photo AI are draft-first.
- External send/publish/pay/delete cannot be combined with generation/calculation in one action.
- Chrome extension is fallback/P2, not primary order source unless native API fails.

## 7. First engineering tickets from this handoff

| Ticket | Owner | Output |
|---|---|---|
| AV-A1 API UAT runbook execution | Backend/discovery | Sanitized results for API-01..27. |
| AV-A3 Adapter base skeleton | Backend | `AvitoAdapterResult`, errors, auth, retry, rawRef. |
| AV-A4 Capability matrix persistence | Backend | Account capability states. |
| AV-B1/B2 Accounts UI scaffold | Frontend | Overview/accounts using Vella shell. |
| AV-B4 Capability drawer | Frontend | Blockers and next valid actions. |
| QA-AV-01 Dangerous action self-check | QA | Signed safe-audit checklist. |

## 8. What to escalate immediately

- Avito account cannot expose API keys/scopes under current tariff.
- Messenger works only under a tariff not budgeted for 10-15 accounts.
- Autoload report/listing registry cannot be read.
- Stats do not include views/contacts/favorites.
- Orders are unavailable through native API.
- Balance endpoint is unavailable.
- Return QR fetch is only possible through a mutating app workflow.
- Any implementation pressure to enable external write before approval/audit exists.
