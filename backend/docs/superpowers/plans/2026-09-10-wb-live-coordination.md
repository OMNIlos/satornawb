# WB live path — shared coordination

Base: filipp `966dcc5ba64697b52f596a0abd755323c23e36e2`.
User scope: attachment 5b6a9f7b-0dde-4dd3-b7f4-83a288517901, read in full.
Coordinator: current task 01a08045-7a78-72d2-ad9a-34a2bc76f519.
Integration: codex/wb-live-integration, architecture-integration-filipp worktree.

## Ownership and delivery

| Owner | Exclusive areas |
|---|---|
| T1 | Alembic/schema/indexes/grants; account/credential connection, durable sync intent repository and HTTP; config/db/cabinet; local infrastructure and launcher |
| T2 | WB sync execution, provider reads, paging/checkpoints/retries, read-only periodic job discovery; existing repricer_sync/tasks as needed, new wb_live worker/provider modules |
| T3 | Account-scoped read HTTP/query services and DTOs, screen/source mapping, query/index requests to T1 |
| T4 (coordinator locally) | frontend only, settings connection and existing data screens/typed consumers |
| Coordinator | this file, integration, backend main/bootstrap/router registration and shared task entrypoint registration |

Separate branches based on base above. Completed commits only for handoff. Never modify another owner's paths without explicit transfer. T1 owns all DDL, T2/T3 request it. No migrations in other packages. Report only completed package, contract change or blocker. No CodeRabbit. No full audit or repeated full suite; complete packages first, focused acceptance afterward; heavy checks serial.

## Frozen cross-package contracts

Preserve existing account-scoped GET/PUT credential route:
`/api/v1/cabinet/marketplace-accounts/{id}/credentials/wb/wb_api`, PUT `{wbToken}`, existing DataEnvelope/MarketplaceCredentialStatusView; never return secret. Separate verified/saved credential from sync state. T1 resolves existing account discovery/create needs without organization-global fallback. Authenticated session and fresh account permission remain authoritative.

New missing sync route family (T1): `/api/v2/wb/accounts/{id}/sync` POST (empty JSON, explicit idempotency header) and GET (latest persisted state). Return `{data:{marketplaceAccountId,jobId,state,sources,updatedAt}}`; jobId UUID string or null on never-started GET; state idle/queued/running/partial/completed/failed; sources list `{source,state,processed,updatedAt,errorCode}` with nonnegative committed count, nullable UTC timestamps and safe nullable error code. No fabricated percentage/total. HTTP 403 denied, 409 conflicting action, 503 unavailable; saved key remains distinguishable from enqueue failure. Exact replay resolves same intent. T1 supplies final DTO and worker repository signatures before dependent integration; additive details must be recorded here.

Durable intent: organization + account + credential binding + source/window + idempotency identity, no plaintext in broker. PostgreSQL is authoritative; Redis is delivery, not commit evidence. One active equivalent source/window, leased recovery, bounded attempts/backoff; persist batch/checkpoint atomically, repeat-safe unique identities. Recheck current account/credential binding before provider access/publication. No locks held during HTTP. T1/T2 agree existing table reuse and concrete repository signature directly; preserve publication guards.

First useful screen: existing WB SKU/goods table; first batch goods/content/current prices as supported by current provider consumers. T3 owns `/api/v2/wb/accounts/{id}/products` bounded server read and exact existing-column DTO; page size default 50/max 200, stable deterministic cursor, allowlisted sort/filter, no per-row queries. Return data items + nextCursor + source readiness (empty/partial/ready/error); never infer complete from zero rows. T3 sends exact wire fixture to T4 and schema/index needs to T1. Preserve existing canonical ABC/P&L route and null final-profit semantics; never replace unavailable canonical fields with guessed financial values. Extend only screens supported by actual loaded sources and explicitly list remaining ones.

Frontend scopes requests/cache by session + organization + account + period/filter, aborts/invalidates stale work, deduplicates in-flight GET, bounded status polling paused when hidden/unmounted. No automatic repeat of uncertain writes, no demo/error-as-empty fallback. Only one active credential write path after verified replacement.

## Dependencies and acceptance

All owners start from these contracts now; mocks only in development/tests. T1 publishes storage/API; T2 publishes bounded source runner; T3 publishes queries; T4 consumes agreed wire. Integrate immutable commits then run one bounded end-to-end path with persistent local services. No existing remote production modifications or broad environment/service discovery. Local app setup may use dedicated persistent local resources; never repurpose another database or enable external price/message mutations. Live WB token must be supplied securely through UI by user; do not retrieve secrets from history/logs or display them. Missing token is a live acceptance blocker, not permission to fabricate data.

Measure first useful page, source throughput, main query timings, peak memory and browser response bytes; distinguish fixture measurements from live WB. Validate persistence across controlled restart of our own services. One launch command and local address required. Package 2 (notifications/settings/schedule and existing external-operation adapters/recovery) starts only after coordinator confirms real-data path; no automatic external mutation during connection check.

## Known gaps / current state

- Confirmed source: frontend settings writes legacy /cabinet/wb-token; cabinet enqueue catches Exception and returns silently; canonical credential route already exists but does not enqueue.
- Runtime fake-mode, PostgreSQL/Redis/worker availability and real-mode memory fallback require targeted T1 verification, not assumptions from prior reports.
- Persistent job/provider/read composition is not yet verified. No live credential accepted in this task yet.
- Foundation tests are historical evidence, not acceptance of this new operational path.

### Accepted implementation details

- T1 verified native PostgreSQL and Redis tools available; Docker CLI absent. Use dedicated persistent native resources, not existing application databases.
- T1 account discovery: GET `/api/v1/cabinet/marketplace-accounts?provider=wb` returns `{data:[{marketplaceAccountId,provider,externalAccountId,displayName,status}]}`. Connect: POST `/api/v1/cabinet/marketplace-accounts/connect/wb` with `{wbToken,displayName?}` returns `{data:{account:{same fields},credential:{existing MarketplaceCredentialStatusView}}}` after actual seller verification and encrypted persistence. Existing account credential PUT is replacement. Never derive account identity from the legacy `wb-primary` capability label.
- `Settings.wb_live_sync_enabled` / `VELLA_WB_LIVE_SYNC_ENABLED` default false. T2 implements `app.wb_live.tasks`: `wb_live.dispatch_pending`, `wb_live.run_batch(organization_id, marketplace_account_id, job_id)`. Coordinator registers a 30-second dispatcher tick and `vella.wb-live` routes; initial worker concurrency one. Legacy execution schedules remain off in launcher.
- First sources are `content` and `prices`; goods is their read projection, not a duplicate source fetch. History is subsequent work within package 1, not represented as already loaded.
- T2 inspected official browser documentation on 2026-09-10 at https://dev.wildberries.ru/docs/openapi/item-management. Content uses ascending updatedAt/nmID cursor, 100 cards/page. Price listing is GET `/api/v2/list/goods/filter`, limit 1000/offset, continuing until empty; POST is nmList lookup, not equivalent provenance. Existing 0077 POST evidence cannot be reused to label a GET. T1 owns any necessary codec/schema accommodation.
- Documented base price token limit is four/hour (900 seconds between calls); faster service profile requires explicit verified entitlement. Persist retry/due time and release worker instead of sleeping for 900 seconds. Content-only rows are partial, missing prices are null. Honor server throttle feedback. Static web fetches returned 498; fresh evidence is T2's official browser read, not stale search index.
- T3 product query: limit default50/max200; sort `nmId|vendorCode|title|brand`, direction asc/desc, literal `q`, exact `brand`, opaque cursor. Envelope data has integer marketplaceAccountId, items, nextCursor, readiness, sources and opaque readVersion. Items: string nmId, nullable vendorCode/title/brand/subjectId(string)/subjectName/photoUrl/contentUpdatedAt/pricesUpdatedAt, sizes and sizesTruncated. Size: string chrtId, nullable techSize, skus, skusTruncated, nullable decimal-string priceKopecks/discountedPriceKopecks. Bound first100 sizes and first100 barcodes each, flag truncation. Current-source table has no historical-period semantics. Signed cursor binds principal/account/query/source revision; one statement reads source revisions and rows at one MVCC snapshot. Changed publication returns409 `WB_PRODUCTS_CHANGED`; frontend resets pagination without a retry loop.

## Superseding user instruction — full original T1–T4 completion

The user explicitly resumed all unfinished original requirements after reading
attachment `42220e2b-3a63-4b43-a8e4-78334716fb3f`. This supersedes the earlier
package-2 implementation wait and Production deferral, not external-action
authorization. Independent implementation may proceed before a real WB key is
available; fixture proof must never be called live acceptance.

Current delivery ledger:

| Owner | Active bounded package | Acceptance / dependency |
|---|---|---|
| T1 | Explicit retry of failed source in partial WB job, then history staging/publication | Preserve replay, successful sibling and authority; sole DDL owner |
| T2 | Bounded historical orders pipeline, then existing repricer runtime wiring | T1 EOF/staging contract; no blind retries or invented finance policy |
| T3 | Complete Orders read/filter contract for UI, then Production commands/CAS | Preserve separate marketplace status rules and all legacy print/export behavior |
| T4 | Existing Notifications UI to persistent list/read contracts | Existing server DTO only; missing preferences write contract must be handed to T1 |
| ROOT | Shared entrypoints, native startup, assembled verification and merges | Heavy test slot held here; no simultaneous heavy owner runs |

Imports: final native-cursor/URL fix `fba66f6` -> `d603aa7`; worker cursor
regression `edf9cd` -> `8b9ddf8`. Explicit partial-source retry remains open.
T3 actual product bounds supersede the earlier paragraph: first **5** sizes;
barcodes omitted with explicit null/empty/truncated semantics, not 100 x 100.

Original requirements not yet accepted: all-consumer credential lifecycle and
Avito isolation, repricer runtime/settings/recovery, history/revision evidence,
Orders UI, Production parity/commands/batches/print/archive, complete Reviews and
Notifications flows, remaining canonical consumers, CI/debt/rollback acceptance.
Track them as implementation plus verification, never merely a merge checklist.
Existing authoritative business decisions are reused. Missing final-profit
policy is a decision blocker: retain null rather than invent a formula.
KIZ/standalone matcher and redesign remain excluded; no actual production,
price changes, message sends, printing or exports are authorized by this restart.

## Historical deferral (superseded where explicitly resumed above)

Production/printing/KIZ/standalone matcher; new financial formulas/redesign; all 70 historical failures except an actual current-path blocker; broad fault matrix and backup-restore program. Package 2 waits for the real-data first-path acceptance rather than silently proceeding on fixtures.
