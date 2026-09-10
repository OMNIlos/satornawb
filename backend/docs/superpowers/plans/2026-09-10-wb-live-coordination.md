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
| T1 | Notification preference runtime/0081, then history staging/publication and manual Review SQL amendment | Retry/import-path fixes integrated; sole DDL owner |
| T2 | Price HTTP adapter and override factory delivered; remaining source/runtime composition | No blind retries or invented finance/authority policy; durable shared quota still required |
| T3 | Complete Orders read/filter contract for UI, then Production commands/CAS | Preserve separate marketplace status rules and all legacy print/export behavior |
| T4 | Local Reviews drawer and first manual draft; Notifications UI integrated | Existing real source/policy required; no fake generation or provider send |
| ROOT | Shared entrypoints, native startup, assembled verification and merges | Heavy slot free after T1 preference gate; allocate explicitly, no simultaneous runs |

Imports: final native-cursor/URL fix `fba66f6` -> `d603aa7`; worker cursor
regression `edf9cd` -> `8b9ddf8`. Explicit partial-source retry and clean launcher
import fixes are integrated through `a854ecc`, independently reviewed.
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

### Historical integration checkpoint (2026-09-10, HEAD 814a69d)

Notification list/receipt client and UI are integrated (`8f88f7a`, `a926728`,
`7f2dea7`); shared default-off API registration `3e911c0` has five focused
entrypoint tests passing (2.24s, two dependency deprecation warnings).
Schema0081 `5a4ee23` is imported, not applied to a persistent database. T1's
preference service/config/legacy-writer fence package is still pending import;
the preferences screen is therefore not an accepted end-to-end workflow yet.

First manual Review backend `cb8496a` and local drawer `814a69d` are imported.
Manual mode is initial draft only, requires an actual current policy/source,
and remains dependent on T1's additive SQL encoder amendment. No database or
full Reviews acceptance is claimed from pure tests. Helper owns only domain
code; T1 remains sole DDL owner.

History streaming source is integrated through `d48afb3`, independently reviewed.
Its staged pages are provisional until guarded EOF; published source evidence
is not the canonical Orders queue. Explicit dateFrom is mandatory. With no
active job, history initialization may also create the normal content/prices
sources and must disclose them; adding history to an active job leaves siblings
unchanged. No inferred date window or implicit cursor reset.

Dedicated local initdb remains blocked by host shared-memory allocation. The
existing PostgreSQL alternative was rejected after read-only checks found
generic trust authentication. No existing database/role, HBA, kernel setting,
IPC segment or server was modified; no persistent service or live WB key is
active. Disposable synthetic test databases are not approval to store real
credentials on that shared server.

### Historical integration checkpoint (2026-09-10, HEAD 7c93728)

- Notification preferences/config and registration are now composed through
  `74dcfb7`; 30 focused entrypoint/HTTP tests passed. The final local API role
  exercised list/read/dismiss and two recipients plus preferences: one actual
  PostgreSQL test passed in 17.90s, owned DB/roles cleanup asserted. Independent
  bounded Notifications review passed. This is not bearer/live acceptance.
- First manual Review SQL0083 `7c93728` is imported after history0082. T1's
  15-case gate covered canonical bytes, initial revision, replay/edit/approval,
  revocations, downgrade and retained SQL identities. Root's independent SQL
  review is pending; local workflow and streamed64KiB HTTP boundary were reviewed.
- Shared WB/Avito account discovery `9db095a` + registration `7e76b4c` and Orders
  UI `772069c` are integrated and independently reviewed. Metadata has its own
  default-off flag, not the WB collector flag. Root's 15 entrypoint/HTTP tests
  passed; T2's 10 actual PG cases passed. Orders remains a limited saved view.
- SKU context/config `a2714d8` and read composition `9ecb4a9` are integrated,
  with 29 focused HTTP tests and independent review passing. Write admission
  remains permanently false until an actual verified legacy-writer cutover.
- History0082 `1a4954d` and runtime `6b563d4` are integrated and independently
  reviewed. T1's four unique PostgreSQL cases include the real streaming worker
  and non-bypass-owner downgrade refusal. Staged source evidence is NOT current
  canonical Orders projection. A separate explicit sync:run projection intent
  is the approved direction; the original read subscription is not write authority.
- Production service `70acd18` adds guarded create/read/manual assignment and
  passed independent source review. T3's 16 unique PG cases and six new pure
  cases passed. It is dormant: no HTTP, local API grant acceptance, calendar,
  batches, print/export, or prototype retirement is claimed.
- Synthetic Chromium component proof `a4b5fe5` extended by OrdersUI passed on
  owner worktree. Root built the integrated frontend with canonical flags true:
  direct Vite build passed in 6.17s; existing large-chunk warnings remain. This
  is not styled parity or live-data acceptance; no snapshot generator was run.
- Scoped CI `3cc3a0d` is source/static-validated only, not executed on GitHub.
  It explicitly does not replace full release/debt/restore/rollback gates.

Work at that checkpoint: T1 sole schema/guard owner prepares durable shared price quota then
explicit Orders projection authority; T2 migrates a bounded Avito statistics
consumer without org cache/plaintext fallback; T3 prepares bounded staged-source
decoding and projection semantics; T4 adds explicit history initialization UI.
All external mutation flags remain off. Missing real WB input, dedicated local
infrastructure acceptance, final finance decisions and complete Production
renderer/calendar parity remain separate blockers, not completed tasks.

### Historical integration checkpoint (2026-09-10, HEAD 478c15a)

- Shared price quota schema0084 `d9adb37` and service `ae4df5d` are integrated
  and independently reviewed. Owner proof: 31 pure / 12 PostgreSQL tests;
  ROOT repeated the pure contract: 31 passed in 0.53s. Database-time account
  serialization, monotonic cooldown and hostile default-ACL/reapply denial are
  covered. This is admission infrastructure, not price-send authority. Actual
  adapter admission currently follows dispatch; T2 must move preparation before
  the marker with a one-use bound operation and no second quota charge. A crash
  may waste quota capacity; no durable exactly-once admission claim is made.
- Shared WB/Avito Notifications account discovery `80952a8` is integrated,
  independently reviewed and owner-tested (58 focused/client/browser cases).
  Cleanup fix `fbda7c0` has 17 focused client tests plus TypeScript passing.
  Neither Notifications nor Orders derives action permission from metadata.
  Explicit WB history initialization `ae29ccb` is also reviewed and integrated.
- Manual Review SQL0083 and pure history bridge `80b26e3` have passed bounded
  independent review. Final local API role tests `742b30f` (Reviews) and
  `22c8409` (SKU read-only) expose narrower missing grants; T1 owns their
  RED-to-GREEN fixes. Broad fixture roles are not final API acceptance.
- Avito encrypted-account statistics `5399e46` and default-off exact-pair
  composition `478c15a` are integrated. Owner proof: 43 offline / 19 PostgreSQL
  cases; ROOT entrypoint/HTTP/transport run: 48 passed in 2.42s. Independent
  review found a daily-null aggregation defect despite those tests; T2 is
  fixing it before acceptance. Final local API-role proof and validated config
  are still pending. No legacy statistics cutover, source persistence/cache,
  OAuth refresh or live provider acceptance is claimed. Future frontend load
  must be explicit, not triggered by every date-field change.
- Scoped CI `8807d30` includes quota, history decoder and new typed frontend
  consumers; YAML parsed locally. GitHub Actions has not been executed.
- T1/T3 projection direction is frozen: a separate current `sync:run` intent,
  immutable completed-history selection, typed 1000-row chunks and atomic
  receipt/progress. Historical and current credential identity/generation/
  incarnation must match. Explicit trusted policy and deadline dependencies
  are mandatory; no runtime values/TTL are invented. Partial observations do
  not establish fulfillment readiness or permit Production activation.

Active implementation is T1 minimal grants/authority, T2 Avito correction and
pre-dispatch price composition, T3 Production HTTP factory while awaiting the
exact projection handle, and T4 typed explicit-load Avito client. All new gates
remain off; the dedicated local infrastructure and actual WB-key blockers above
are unchanged. This checkpoint is not complete architecture/release acceptance.

### Current integration checkpoint (2026-09-10, HEAD 97fc255)

- Final local API Review grants `4f22de9` and SKU read-only grants `2ab1f31`
  are integrated. ROOT's assembled Review, SKU and encrypted Avito statistics
  tests passed together: **3 passed in 10.29s**, with actual limited API logins,
  synthetic owner seeds and allocator cleanup. Reviews cannot enqueue/send;
  SKU reads require no current mapping or write permission. Avito statistics
  reuses existing credential-read rights and performs no SQL mutation.
- Avito daily-completeness correction `4841499` is independently accepted:
  incomplete/null days cannot become a complete total. Explicit zero and null
  totals remain distinct. Config `b29b3ce` supplies strict default-off exact-pair
  rollout; own route does not depend on WB collection or metadata flags.
- ROOT's exact migration ancestry, Avito entrypoint and config checks passed:
  **24 passed in 1.84s**. `f3b06c3` fixes the old test that incorrectly required
  0083 to remain the newest migration forever: exactly one head, 0083 ancestry
  and its exact 0082 parent remain required. An initial broad `-k head` selector
  also selected one PG fixture, whose native initdb failed before starting a
  server; its allocated directory was empty. The corrected exact-node check
  was run independently. No existing server or database was changed by that
  setup failure.
- Typed Avito client `97fc255` has 40 owner tests and TypeScript passing.
  Canonical UI is still being implemented behind its own default-off flag;
  it will load only after explicit submission, never on every date edit.
- The shared role proof is not live/bearer acceptance, nor full migration or
  release acceptance. Existing lint debt remains: unchanged SIM117 in the
  manual-schema test and unchanged config import ordering were reproduced in
  pre-patch sources. No blanket lint waiver or all-green claim is made.

The heavy PostgreSQL slot is now T1's exact six-case general WB runtime ACL
gate. Migration0085 is reserved exclusively for T1's history projection authority.
T2 prepared-price composition, T3 Production HTTP and T4 explicit-load UI
continue independently. No runtime policy values, production actions or legacy
retirement are introduced by these approvals.

### Superseding integration checkpoint (2026-09-10, HEAD c98f020)

- Prepared price admission `202ad12` precedes the durable dispatch marker.
  ROOT verified the actual quota service plus prepared worker: **3 passed in
  8.30s**, including durable Retry-After and lost quota-commit acknowledgment.
  This is synthetic transport proof, not live activation or provider exactly-once.
- Saved Orders views now have two-table read-only local API grants `c04c609`:
  ROOT's unchanged final-role test went from RED to **1 passed in 3.69s**.
- Explicit-load Avito statistics UI `0802ac9` is integrated behind its own
  default-off flag. ROOT TypeScript and direct build passed. Native ephemeral
  Vite binding `f697013` fixed an actual parallel-browser port collision:
  two browser files / **3 tests passed in 6.87s**, with listener cleanup verified.
- Pure history projection contracts `4387c63` and dormant trusted credential
  registrar `e7a6513` are independently reviewed. They do not establish actual
  0085 SQL authority, maintenance provisioning, source transfer or rotation.
- Production command client `c98f020` passed independent source review and ROOT
  **50 tests in 703ms**, plus TypeScript. It is client-only, not mounted UI.
  Commands are single-dispatch and require explicit readback; unknown creation
  without a returned ID stays blocked because no safe lookup endpoint exists.
- Actual Production HTTP-to-service final API-role test `c1ae0e2` is RED:
  **1 failed in 8.73s**, creation returned 503 rather than 200. Synthetic DB and
  three roles were removed and absence verified. T1 owns cause diagnosis and
  any narrowly justified local role changes; broad grants are not authorized.
- CI adds already verified Orders/quota, dormant Production HTTP/client,
  registrar, pure projection and parallel Avito browser checks. YAML is locally
  parsed; no GitHub Actions execution or full release proof is claimed. The RED
  Production final-role test is deliberately not yet advertised as a CI gate.
- ROOT then ran the complete eleven-file scoped frontend command with two
  workers: **222 passed in 11.49s**, including both Chromium fixtures; all five
  owned listeners closed. The four newly added pure backend files passed
  together: **95 passed in 1.13s**, with two existing dependency warnings.
  A safe diagnostic repeat of the Production role gate confirmed SQLSTATE
  **42501** on `marketplace_order_items` (1 failed in 3.74s); it printed neither
  SQL nor parameters and verified temporary database/role cleanup.

T1 is implementing genuine 0085 projection authority; T3 implements its actual
participant, with no fake handle. T2 continues the encrypted-account Avito
Orders status preview, not a full queue or legacy replacement. Production
batches, calendar, print/export parity, credential maintenance/store lifecycle,
runtime business-policy decisions and full release acceptance remain unfinished.
No real provider request, secret retrieval, production operation or push occurred.

### Superseding integration checkpoint (2026-09-10, HEAD 06cba90)

- Production grants `3b49771` are independently reviewed and the unchanged
  final API-role workflow is now GREEN: **1 passed in 9.94s**. Narrow lock
  privileges are not source-publication rights. The catalog timestamp column
  remains explicitly classified as mutable timestamp DML, not immutable.
- Recovery GET `ee80042` finds committed work by account + original order item
  + exact source version, using current Production read authority and source
  coherence. No audit/write/retry is performed. Owner HTTP44 and service PG6
  pass; an initial native-initdb setup error was resolved only by the already
  authorized synthetic owned-database fixture, not host changes. ROOT extended
  final API-role workflow `52cd067` also checks recovery before/after assignment:
  **1 passed in 5.11s**. Temporary database/role cleanup was verified.
- Client `ea435de` exposes explicit `readbackUnknownCreate()` with no caller
  IDs, accepts only the original captured scope and source version, and retains
  its write fence on failed readback. ROOT **68 passed in 989ms** and TypeScript
  passed. The suspected trailing-newline ID defect was disproved by tests;
  `36a909d` adds regression coverage only, not a bug fix.
- Encrypted Avito Orders status preview `497c9d0` / `ae30760` and client
  `9ce84da` are independently reviewed. Owner service PG15 passed; ROOT pure
  preview + recovery HTTP **57 passed in 1.96s**, client **70 passed in 1.07s**.
  Present null/conflicting account aliases and unsupported top-level aliases
  fail closed; absent provider account evidence is explicitly credential-scoped.
  Unknown statuses/timestamps stay unknown; no quantity/price/total is inferred.
- Config `c8e01ca` and bootstrap `06cba90` register this preview only under its
  own default-off flag and strict organization/account allowlist. ROOT TDD was
  4 failed / 1 passed before implementation, then combined source/entrypoint
  checks **54 passed in 2.53s** and config/entrypoint **41 passed in 2.83s**.
  Actual final API-role test `a84324b` passed **1 in 5.87s**, including fresh
  revoked-session denial and no service DML. No live/bearer/provider proof,
  canonical queue publication, frontend mounting or legacy replacement claimed.

T1/T3 are implementing the explicitly approved per-run history decision witness
over immutable parent memberships. The database must derive its pre-state and
outcome, reject caller-authored/reordered proof, and prevent parent advancement
before proof capture. Reused historical singleton observations cannot become
initial projections; legacy behavior is unchanged. Eight codec vectors have
bounded owner evidence (6 passed first run, 2 passed after a fixture-only chunk
split); full 0085 authority/runtime is still unaccepted. T2/T4 independently
implement encrypted-account Avito Reviews metadata preview, without text/PII,
drafting, sends, source-publication authority or automatic effects.

### Superseding checkpoint (2026-09-10, HEAD 8a623f9)

Avito Reviews metadata backend `2ea2e59` and client `a6fe0e1` are independently
reviewed. ROOT pure67 passed in 0.78s; frontend55 passed in 419ms and TypeScript
passed. Actual limited API-role test `b293c0b` passed 1 in 4.81s with cleanup,
including foreign-account/revoked-permission denial and no service DML.
Negative mathematical zero is normalized without float conversion, retaining
decimal scale; rating/count nulls are not fabricated defaults. Content, buyer
names, images and answer actions are deliberately absent from this preview.

Own default-off config `2b640fc` and bootstrap `8a623f9` preserve empty exact-pair
allowlists and all legacy paths. ROOT entrypoint TDD: 4 failed / 1 passed before
implementation; combined config/source/three preview entrypoints: 100 passed in
2.49s afterward. New bootstrap/tests Ruff and diff checks passed. This is not
full Reviews parity: old UI depends on text, answer text, account-scoped state
and correctly separated canonical action authority. T2 inspects the existing
canonical adapter/publication contract for the next real read-parity slice;
another unrelated metadata preview was not started.

Independent review found two additional unaccepted T1 projection concerns:

- Participant/domain exceptions escaped the closed error boundary. T1 is
  applying and testing closed errors without retained exception contexts.
- Capturing pre-state at membership INSERT cannot detect an earlier parent
  UPDATE before history-run insertion. A staging-run predicate alone is not
  sufficient. The genuine runtime must capture/lock a private baseline before
  invoking its participant and validate it at the final fence. Standalone SQL
  proof additionally requires a protected projection-writer boundary; T1 must
  propose a dedicated role/helper without changing legacy writer authority.
  No GUC assertion or transaction-ID heuristic substitutes for this proof.

The 0085 decision gate remains unaccepted: syntax error was isolated and fixed;
the subsequent genuine-service setup exposed missing fixture history SELECT
rights. Only fixture reads were approved, not live/API privilege expansion.
T1 reruns the same three cases, not an implicitly expanded suite.

The generated Production snapshot is already lazy. T4's separate approved
frontend optimization targets the whole parity-page module at the App route
boundary; it may reduce non-parity route startup only. It must not be described
as a Production-only or universal WB speedup, regenerate data, or change prints.

### Superseding checkpoint (2026-09-10, HEAD 599251b)

App parity lazy boundary `f035544` passed independent review and ROOT browser/
history checks (16 passed in 9.16s), TypeScript and direct Vite build (3.83s).
Manifest verified entry 1,032,432 bytes, lazy parity 1,353,237 bytes, lazy
snapshot 1,561,404 bytes; static entry closure contains only index.html.
This reduces unrelated-route startup, not total parity/WB download. Recovery is
an explicit document reload; no automatic retry and no prototype regeneration.

Pure Avito canonical decoder `599251b` passed independent review and ROOT
81 tests in 0.47s, scoped Ruff. It preserves the existing canonical contract;
answer body/id/status are not versioned by that model. This is not an Avito
publication guard or full Reviews parity. T2 next determines the exact reusable
source-publication authority; no send/preview permission may substitute for it.
CI includes both canonical decoder/contract and App lazy browser regressions.

T1 reported genuine decision 3 passed and a separate 5-case gate passed (empty
upgrade/downgrade, malformed decision evidence, closed callback exceptions).
These do not approve complete 0085. The new genuine unsealed-publication test
failed as intended: 1 failed in 4.44s, commit did not reject the missing seal.
Owned database/three roles were cleaned and the PG slot released. T1 implements
private baseline/sealed final commit plus the dormant protected-writer boundary.
Narrow UPDATE(order_id) is permitted solely for row locks, provided actual
tests prove every direct parent mutation, including no-op, is rejected. No
operational provisioning, provider actions, rollout or legacy removal occurred.

### Superseding checkpoint (2026-09-10, HEAD e9db267)

Received-page Avito canonical publisher `e9db267` (T2 source `5a02706`) passed
independent review and ROOT bounded pure230 (0.63s), actual PostgreSQL17 (4.46s)
and scoped Ruff. Disposable database/role absence was explicitly verified.
The genuine original reviews:write principal, exact credential and incarnation
are revalidated; pending ORM/listener reordering fail closed; receipt follows
physical commit. Existing WB bodies remain unchanged. Fixture-only PURE4 grants
are not operational/final API-role grants. Fetch orchestration, list/answer
parity, final-role wiring and activation remain separate work.

T1 owner evidence: dedicated-role gate1 passed in 5.18s; empty 0085 roundtrip
passed. Actual T3 nonempty publication initially failed at the deferred decision
witness; safe diagnostic confirmed P0001 and the exact witness. Only child
evidence fix `c9d064b` was added, then the same genuine test passed in 5.95s.
Child payload/checksum/time/item binding, receipt and progress were inspected
after commit. This addresses the missing-child defect, not whole history replay.
T1 schema/ops/runtime checkpoint is not yet imported into ROOT: final review
found the new-operation status read also needs pinned entry/final role checks.
No production changes, operational grants, provider actions or rollout occurred.

### Schema-first integration (2026-09-10, HEAD 678a407)

Schema `5a6832a` and dormant role artifact `678a407` passed independent source
review. ROOT reran the exact empty 0085 roundtrip and physical restricted-role
gate together: 2 passed in 9.72s, both owned databases/three roles removed and
absence verified. Scoped Ruff passed. CI now includes these bounded gates.
No operational role was provisioned and no history runtime was activated.

The new-operation status path still awaits T1's runtime fix/integration:
its genuine owner-factory substitution test failed causally (incorrectly allowed
read), not at setup. Used-history downgrade refusal, full replay, late role
drift and final API-reader grants remain separate gates. T3 owns only a new
genuine used-history downgrade regression; it must preserve stored evidence.

### Runtime integration checkpoint (2026-09-10, HEAD d64d442)

Bounded raw Avito fetch/orchestration `118f789` passed independent review and
ROOT pure272 (0.85s), PostgreSQL13 (4.04s), Ruff and owned cleanup. Same original
binding/incarnation is captured before resolution and checked across closed
roots; one GET runs outside transactions. Timeouts are per-operation plus
elapsed checks, not a hard 30-second deadline. No provider call/activation.

History runtime `e02b62e`, T3 participant `f3a5cdf`, child fix `1413419` and
genuine regression files `1b87866`/`d64d442` are integrated after source review.
ROOT pure187 passed in 0.74s. ROOT actual3 passed in 12.08s: genuine child
publication, used-data downgrade refusal with 13 unchanged scoped table hashes,
and required per-run decision columns. Owned databases/roles were removed with
explicit absence checks. An earlier accidental pure invocation included a PG
test and failed at sandbox socket setup; a mistyped sandbox path also prevented
one launch. Neither is a source regression or passing gate; corrected commands
above completed normally.

T1 owner status2 and late-ACL/unsupported-path5 gates passed after causal REDs.
ROOT found an additional contract mismatch during full source review: an already
existing empty identity (version1, no current run/evidence) is eligible for initial
projection under the agreed contract, but the private baseline comparison rejects
it. T1 owns the narrow comparator fix; T3 owns its genuine regression and then
same-fixture replay/EOF checks. No schema or legacy-rule weakening is authorized.
An independent test-only helper prepares the final wb_live_api Avito writer gate;
T1 retains exact grants ownership. These outstanding gates are not completion.

### Saved history read checkpoint (2026-09-10, HEAD 6bf8676)

The existing-empty-identity comparator fix `5aac361` and genuine history replay
tests are integrated. ROOT reran the complete four-case history file on
`a21b5ee`: 4 passed in 9.08s, exit 0. This proves a fresh projection-job replay,
empty EOF, initial projection onto a pre-existing empty identity and changed
cancellation reconciliation without overwriting current state. The changed-run
fixture now uses the genuine manual initializer and exact source cooldown;
production selection and authority rules were not weakened. An older test
session's result was unavailable and is not counted as additional evidence.

Final API Avito source grants `5c2f1d6` closed the diagnosed SQLSTATE 42501:
ROOT's unchanged final API source-sync test passed (1 in 4.01s). No send, auth,
observation-update, delete or additional sequence rights were added.

Genuine history-to-saved-view test `6bf8676` passed independent read-only review
and ROOT PostgreSQL (1 passed in 4.71s, exit 0). It calls the real history
participant and guarded owner-side freeze, then discovers and reads the saved
view through the final API role. Selected-account restriction, session revocation
and denied snapshot writes are asserted. Both fresh fixture runs completed their
owned database/role cleanup assertions. This does NOT prove a final snapshot
publisher runtime identity, HTTP wiring, complete history coverage or UI parity.
CI now includes both history test files and the final API Avito sync regression;
the hosted workflow itself has not been run.

ROOT also reran the existing `test_orders_job_publication.py` against the current
migration head: 11 passed in 6.05s, exit 0 and owned cleanup assertions passed.
This covers the bounded pre-existing publication path, not the entire backend
suite. Scoped Ruff and `git diff --check` passed.

T3 owns the next bounded read-only inventory of the existing snapshot publisher
and explicit history-to-saved-queue wiring. API reads must not acquire publisher
grants. No production, provider requests, real keys, operational provisioning,
rollout, printing, exports or remote pushes occurred.

## Historical deferral (superseded where explicitly resumed above)

Production/printing/KIZ/standalone matcher; new financial formulas/redesign; all 70 historical failures except an actual current-path blocker; broad fault matrix and backup-restore program. Package 2 waits for the real-data first-path acceptance rather than silently proceeding on fixtures.
