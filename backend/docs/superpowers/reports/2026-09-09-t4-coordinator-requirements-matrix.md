# T4 — requirement → commit → evidence → remaining work

## Current checkpoint: frontend response isolation; Review historical binding open

Latest test-only Stock/Week checkpoint: actual React page proves four scoped
loading→empty/error→session-expired cases with one intercepted GET, no mock rows
or additional API calls. Replaced only two obsolete progress-component source
bans. Focused9PASS; full356PASS/17FAIL/0pending versus350/19, exact two source
failures closed and zero new failed IDs. Initial 1s readiness timeout reproduced
under load, corrected to bounded15s; final focused and broad runs pass new cases.
TypeScript/diff0; independent critic found no important defects. Runtime, HTML,
schema and flags unchanged. Report: frontend/docs/superpowers/reports/
2026-09-09-t4-stock-week-state-tests.md. Remaining17failures unwaived.
T1 candidate Review-run-binding design fully compared against1a3d344/45e2ccb;
domain direction accepted directly to T1, not DDL readiness or activation.

T1-requested Review binding purecodec READY: historical_binding.py frozenexact
descriptor +sortedASCIIJSONencoder +mandatorychecksum strictdecoder,6literal
Unicode/control/null-emptyvectors matched byindependentNodeencoder/hash andcritic.
61focusedPASS/283adjacentpurePASS0.48s/no skips, networkdenied, Ruff/compile/diff0.
Report2026-09-09-t4-review-binding-codec-handoff.md. ExactreadySHA sentdirectlyT1
forSQLparity, notrootper-slice. NoSQL/servicewiring; pureNULacceptance is notVARCHAR
admission; immutablehistory andpublicread/operationalactivation gates remainOPEN.

Latest test-only strategy-scope follow-up to c114a18: obsolete dependencyliteral
replaced byactualReactinactivepage APIassertion, precisein-memorymutation detects
unexpected GET/strategies/catalog. Finalfull350PASS/19FAIL/0pending versus349/20,
oneperformance sourcecaseclosed/nonewIDs; TypeScript/diff0, independentcriticPASS.
No runtimechanges; doesnotproveallproductrouteperformance. Localreport same
2026-09-09-t4-repricer-stats-route-test.md, remaining19failuresunwaived.

Latest frontend test-only checkpoint: actual VellaHtmlParityPage route/effects/
generatedHTML browser test replaces2obsolete source-string assertions, retaining
all otherguards. RealinitialGET/scopedperiodGET/authnullrow+KPIclearing verified.
In-memory route/eventguard mutations bothfail for intendedbehavior. Finalfull
349PASS/20FAIL/0pending versus345/21: one sourcecase closed, nonewfailedIDs.
Includes final Orderswhitespacefix tests. Finaltsc/diff0, independentcriticPASS;
no runtime/sourceHTML/generated changes. Reportfrontend/docs/superpowers/reports/
2026-09-09-t4-repricer-stats-route-test.md. Twentyfailures remainunwaived.

Dormant Orders wire preparation868728e:
canonicalOrders.ts strict typeddecoder and URLbuilder, nofetch/UIactivation/print
inference. T3da7e017 wire unchanged throughab272ee, directlyconfirmed. ActualT3
Pydantic JSON golden matches; independentcritic found2P2s, actual4RED fixed precise
microseconds/WBmandatoryevidence. Additional Python/JSwhitespace mismatch2RED fixed
without identitynormalization, critic independentlymatched Python Unicodewhitespace.
Finalfocused115PASS(59Orders+56ABC), broadpre-whitespacefix345PASS/21samefailedIDs/0pending
versus288/21. TypeScript/build passed pre-finaltextboundary; finaltsc exits0 as well.
No activatedclient or queue; sharedregistration/historybinding/queryregistry/rollout
and Productioncapabilities remain gates. Fullreport frontend/docs/superpowers/reports/
2026-09-09-t4-orders-wire-adapter.md. No root per-slice message requested.

Frontend311458a prevents stale Repricer first/page2 success/error from changing
newer results after reload/disposal. Follow-up5256f77 clears stale KPI/deltas/filter
summary during loading/error/logout. Actual browser RED→GREEN, final6focusedPASS;
full288PASS/21samefailedIDs/0pending (previous282/21 before both slices), TypeScript
and Vitebuild0, independentcriticPASS. Reports2026-09-09-t4-repricer-stats-response-isolation.md
and2026-09-09-t4-repricer-stats-aggregate-clearing.md are under frontend/docs/superpowers/reports.
Synthetic actualbridge tests, not wholeReact/auth lifecycle or production proof.
Root requested local-matrix checkpoints only, no per-slice integration/messages.

T3 accepted dormant read wire866d1a1 + bigint-string correctionda7e017:
GET/api/v2/orders, snapshot_id and row_version decimal strings. T4 independently
ran10pure wiretests. Typed frontend preparation may proceed without activation;
public integration remains dependent on approved immutable sourcebinding service
and single-owner rollout. No invented filtering/capability/print semantics.

Historical binding request/witness1a3d344 supersedes any broader read readiness:
actual1PGcase3.08s demonstrates oldbody after completedaccountrebind under freshguard.
This is an OPEN defect, not safe-read PASS. T1 receives perrunimmutable binding and
unbound/mixed/currenthead rules; publicreads and operationalactivation blocked until
accepted persistence+consumer verification. SharedHTTP errors are error.code in
app/main.py, not standalone detail.code; T1 owns real registration/envelope tests.

Latest bounded result: canonical-only HTTP router/service/raw WB adapter ready for
T1 default-off registration, NOT activation. Coordinator superseded unsafe legacy
dualconsumer for this path: no legacy write/read/cache use. Actual signed auth,
pairedcredential/scope/revoke/replay/rollback/outage and rawlossless source acceptance;
final900PASS2warnings49.16s/no skips, scopedRuffcompile/diff0, independentcriticPASS.
See2026-09-09-t4-canonical-review-http-handoff.md for exact wire/errors/limits.
Public canonical reads, dualconsumer legacy isolation and later stages stay open.

Selector434ff5f accepted/cherry-picked9981e72,94PASS2warnings2.81s/newRuffcompile/diff0.
All flag defaults remain off. New actual wiring gate: legacy feedback storage and
reads have no org/account owner; adding arbitrary account DTO dualwrites is unsafe.
Coordinator received exact source evidence and bounded compatibility/scoping decision
request. No HTTP edit; older pending-selector statements below are superseded.

Fixture follow-up supersedes the blocker immediately below: acceptedT1 34b5f62
cherry-picked79f83b9; actual mixed collection with Review ORM and all original files
plus fixture regressions passes349tests27.69s and349tests31.46s in reverse order,
no skips/naturalexit0.20setup errors closed for this gate, not a full backend claim.
No unaccepted approvals ancestry imported; Review selector remains pending/off.

Physical guard8338ef7 now accepted from T1 and merged2dc09de; static integration
criticPASS. Expanded334-test acceptance is blocked by20credential SQLite setup
errors (314passed): global metadata includes Review JSONB after collection. Minimal
same-test alonePASS/importedReviewERROR reproduced and sent to T1 fixture owner.
Not waived; full mixed run must be repeated after fix. Review selector still pending.

Latest bounded acceptance: 19 new actual PostgreSQL shadow cases; combined641PASS
48.76s, no skips, Ruff/compile/diff0, independent scoped criticPASS. Details in
2026-09-09-t4-review-shadow-composition.md. Same received WB DTO composition, paired
credential authority, committed reservation and both real session-revocation lock
orders are now covered. Actual manual HTTP wiring, T1 physical guard follow-up and
Review-specific default-off selector remain gates; scheduler and Avito stay unwired.
This supersedes the older statements below that composition/race tests are missing,
not the broader stage-completion requirements.

All eight original stages remain in scope. A pure contract, fixture or dormant
repository is not an activated service. No production/deploy/push/live provider,
send, print/export action or rollout activation in this continuation.

| Stage | Delivered evidence | Still required before stage completion |
|---|---|---|
| 1. ABC/P&L | 7cd1fd9/028168b/81ee4b9 typed default-off adapter; 8d68560 actual SSR auth regression. Original focused75 and build/typecheck passed; later focused auth65. Null/formula semantics unchanged. | Backend freshness policy and separately authorized hosted canary/E2E; no release approval. |
| 2. Review Facts/shadow | Exact T1 56b5fa5/0063 integrated64f256f, fixture/style followups825326d/5f1f539; eaf15c6 dormant ORM/repository. Fresh314PASS (35 repository +48 schema +231 adjacent), real disposable PostgreSQL/runtime role, cleanup verified. Account lock/RC, replay manifest, CAS, immutable source history, late-run ambiguity. | Real shared publication/auth guard, same-fetch shadow service hook, actual account revocation/publication race and restart integration; public read API. Repository is not authorization and no route is wired. |
| 3. Policies/drafts/approval | 98d1331 pure decisions; 8f4a6c4/b17638f exact head/audit proposals; 4b349ec/92ba34c serializers; 5d4ac9a golden vectors; 316eaf8 local audit encoder/golden,157 combinedPASS incl51 audit,58 serializer,40 decision,8 golden tests. Independent critic PASS after impossible head transition fix. | T1 accepted local DDL, durable repositories/head CAS, fake generation service, authenticated actions, atomic audit and database races/restart. Encoding alone is not durable audit. |
| 4. Send/recovery | e4818e3 recovery, b17638f exact attempt/lease/result matrix, canonical send payload serializer. Existing35 recovery +8 provider lifecycle cases included in adjacent checks. | Durable command/idempotency/attempt/marker/evidence/audit/enqueue repositories, real credential and worker authority, fake-provider crash/restart integration. Live send remains prohibited. |
| 5. Notifications | 98d1331 safe projection; 9284fe0 read-only existing preferences;31 projection/21 SQLite tests (not RLS proof). | Event/receipt persistence, visible-ID mark-all and fresh actor checks, transactional producer/outbox, cache isolation and delivery storage. External delivery also needs verified destination/receipt/policy contract. |
| 6. Other frontend consumers | Frontend ownership retained; approved ABC only. Safe marking cleanup1d0700d/6171d72/02cbd9a/0ff9941/8d4a5b9 preserves historical status/problem filter/barcode fallback and core WB/Avito matching; shared snapshot regenerated by existing pipeline. | Approved authenticated T2/T3 HTTP/capability contracts then adapters/state/race/409 UI and single-writer cutover. Do not invent endpoints from repository proposals. Production parity/legacy owner retirement not established. |
| 7. Rollout/retirement | e4818e3 canary/rollback runbook; default-off, build-time redeploy requirement and separate write-action authority retained. | Approved budgets/window/artifact and explicit canary authority; legacy retirement only after actual parity and writer rollback. |
| 8. Debt/final handoff | Actual-rendering/browser fixes;5d92b78 expense-help,0aec110 runtime-source guard with RED/GREEN and mutation. Fresh full frontend279PASS/24FAIL/0pending versus278/25: zero new IDs, one resolved. Typecheck0, full npm build0 (large-chunk/plugin-time warnings); generator hash unchanged, timestamp-only incidental diff restored. Critic PASS. | Remaining24 failures, integration/full backend baseline, complete ready-set review; current checkpoint is not final architecture handoff. |

Latest verification superseding the counts in the stage rows above:

- Reviews268ea1d: valid Unicode/NUL identities preserved, invalid surrogate keys
  rejected with typed safe errors before SQL on write and read. Fresh405 combined
  backend tests pass (real disposable PostgreSQL plus adjacent contracts), no skips;
  scoped Ruff/compile/diff0. Local audit remains an encoder, not durable storage.
- Frontend4fd9156 actual ABC bridge empty/error/auth behavior, ff7038a Avito schedule
  cancel browser case,9099f32 RNP period/session scoped runtime fix with actual RED.
  Full282PASS/21FAIL/0pending, zero new failure IDs versus282/22. TypeScript and Vite
  build exit0; existing chunk/plugin warnings. All21 failures remain unwaived.
- T1 explicitly confirmed reading exact5d4ac9a,316eaf8,a836560,268ea1d. The unified
  eight-pair lossless design405033a and implementation plan1d8d493 were read fully;
  actual0065 migration and T4 decoder/repository acceptance are not yet available.
- T1 fetch-only authority7bfb631 handoff read: paired credential/binding is not
  publication authorization. Full shared guard remains pending; neither this API
  nor the proposed0065 are claimed installed in this worktree.

The earlier pending-guard statement is superseded: exact T1 guard4860c53 and paired
fetch7bfb631 lineage are now merged83ef4a4. T4 root-transaction compatibility30f1f15
passes253 tests (new9+repository35+schema48+sharedguard161), Ruff/compile/diff0 and
independent review. Repository uses explicit command_savepoints=False under guard;
caller must roll back the full root on every error. No current service is wired.
This closes guard/repository compatibility, not authenticated same-fetch shadow
composition, audit or a Review-specific two-session revocation acceptance gate.
Actual0065c68cd31 subsequently controller-approved and merged74bde41. Decoder-first
dab11ec and writer0ce0517 close lossless representation acceptance: fresh622PASS38.86s
(461Review/adjacent+161guard), no skips, Ruff/compile/diff0, independent reviewPASS.
All8pairs preserve NUL/Unicode/null-empty and semantic hashes; mixed legacy identity
is not rewritten; actual guard publication/rollback covers NUL keys. DeepJSON
RecursionError safe handling was reproduced and fixed during decoder review.
Rollback requires decoder-capable dab11ec+expanded0065, never oldTEXT-only/downgrade.
Next same-fetch shadow composition remains separate. T1 was directly requested a
Review-specific default-off org/account policy; collector flags are not reused.
No SQL migrations or shared auth are authored by T4. Next independent task:
remaining evidence-backed frontend test debt; durable wiring waits for real guard/DDL.

Current native PostgreSQL access is no longer blocked by the historical ENOMEM:
coordinator authorized Unix-only fresh disposable tests; no existing application DB
or host service changes. eaf15c6 report contains exact commands/cleanup and limitations.
Source-text NUL mismatch is now reproduced316eaf8: normalizer accepts it,0063 TEXT
storage rejects it;1 realPG test proves safe rollback plus plain-text control, not
lossless parity. T1 notified for forward schema decision; no stripping or schema edit.

## Historical snapshot at 9284fe0 — retained as history, not current readiness

Snapshot на `9284fe0`, worktree clean. Координатор: задача
`01a082e2-4420-70a3-b4f4-2c4ad061e587`; начальная передача подтверждена tool.
Stage completion оценивается по исходному заданию T4, не числу pure modules/documents.
GitHub push/integration выполняет координатор после общего gate.

| Требование | Commit / артефакт | Проверка | Незавершённое |
|---|---|---|---|
| 1. Canonical ABC/P&L frontend | 7cd1fd9,028168b,81ee4b9 | focused75; typecheck/build0; immutable base193pass29fail →261pass29fail, exact same failure IDs | Hosted canary/browser E2E, missing backend freshness policy; no release approval |
| 2. Review Facts + shadow | 4a7d669 request, accepted T1 d38e923; existing canonical_contract.py | existing normalization38 cases в текущем combined173 | DDL, canonical_orm/repository, same-fetch shadow hook, actual PG replay/manifest/watermark/source-order/CAS/RLS/outage/restart |
| 3. Policy/draft/approval | 98d1331 pure decision, 8f4a6c4+b17638f exact payload/head/audit proposals | 40 decision tests + lifecycle subset; revoked/stale/scope/checksum predicates | Canonical serializers, immutable rows/head publication CAS, fake generation service, authenticated actions, atomic audit, PG races/restart |
| 4. Send/recovery | e4818e3 pure recovery; b17638f exact lease/result/evidence/audit | 35 recovery tests, current-read boundary/live lease/ambiguity; 8 provider lifecycle | Durable idempotency, exclusive attempt/marker, worker enqueue and credential resolution, actual provider-fake crash/restart/CAS; no live send |
| 5. Notifications | 98d1331 safe projection; 9284fe0 read-only preferences | 31 projection +21 SQLite preferences tests | Immutable events, per-member receipt/upsert/visible-ID mark-all, atomic outbox, recipient/cache isolation, delivery storage/attempts, verified destination/receipt contracts |
| 6. Other frontend consumers | Существующий ABC adapter; новые domain endpoints ещё не approved | Stage1/bd6139f проверены; другие capability cutovers не заявляются | T1 credential/token policy; T2 repricer/finance/sources HTTP schemas; T3 Orders/Production HTTP commands/read/export/receipt contracts; adapters/UI/default-off flags после parity |
| 7. Rollout/retirement | e4818e3 frontend canary-rollback-runbook | read-only critic, explicit NO-GO, build-time rollback and old tabs | Approved release budgets/window/artifacts, отдельно разрешённый canary; legacy retirement только после actual parity |
| 8. Test debt/handoff | bd6139f clock fix, все bounded handoffs | fresh frontend261/29 →264/28, exact0new1resolved, skips0; typecheck0 | Остальные28 frontend failures, integration full suite/baseline, real generator pipeline по контракту, final ready set |

Latest scoped combined T4: **173 passed, exit0**, zero external-action attempts under
Python audit hooks. 21 SQLite tests доказывают query/projection, не PostgreSQL RLS.
Полный backend suite для T4 continuation не запускался; исторические baseline failures
не автоматически утверждённый release allowlist. Frontend runtime после Stage1 не менялся.

## Exact requests координатору и владельцам

### T1 — prerequisites в порядке возможности

1. Принятый Review Facts DDL по `4a7d669`, actual revision от единственной head, scoped
   FKs/RLS/runtime privileges и committed test handoff. T4 после проверки пишет
   `app/reviews/canonical_orm.py` + repository, не competing T1 domain ORM.
2. Review local policy/draft/decision/head DDL по `8f4a6c4` и `b17638f`.
   b17638f уточняет head initialization, distinct head/draft versions и per-event audit;
   независимый critic прошёл, acceptance T1 ещё не подтверждено.
3. Send command/attempt/evidence + domain audit/enqueue atomic persistence по тем же
   matrices. No provider/production policy defaults. Shared transaction-local context,
   grants и physical outbox принадлежат T1; T4 получает готовый интерфейс/DDL.
4. Account-scoped notification events/receipts DDL можно выпускать независимо от Telegram.
   Explicit visible-ID mark-all, integer membership, composite owner FKs. Preferences
   остаются в lk_user_preferences; read-only adapter9284fe0 уже готов. Writer требует
   T1 extension existing owner's version/CAS, не новой preferences table.
5. External Telegram позже: verified versioned destination binding, scoped provider
   receipt, immutable delivery policy relation/ref. Org-wide events отдельно требуют
   platform registry. Missing policy/binding блокирует активацию, не in-app storage.
6. Disposable PostgreSQL environment: T1 report9438186 сообщает bootstrap ENOMEM.
   T4 не меняет sysctl/shared memory/чужие процессы. Координатор определяет разрешённую
   remediation/isolated runtime; новый PG запуск только после безопасной готовности.

### T2

Нужны committed approved HTTP schemas/routes/permissions/capabilities для repricer,
finance/sources: exact read pagination/snapshot/error contracts и command expected_version/
idempotency/409 semantics. Observed HEAD ee7bd6e; незакоммиченный reserve/dispatch amendment
не импортирован. Pure repository proposal не служит источником придуманных HTTP endpoints.

### T3

Нужны committed approved Orders/Production HTTP read/commands + status mapping, print/download/
delivery/backend receipt distinctions и parity evidence. Observed HEAD2f1724a. T1 currently
интегрирует Orders candidate; незакоммиченная0062 не imported и не названа ready. Legacy
serverless snapshot writer отключается только при agreed single-owner cutover/rollback.

## Готовые bounded commits и следующий шаг

Текущий ready для review набор — T4 история от c88a474 до9284fe0, включая docs; это не
разрешение общего merge и не stop/ready declaration всей задачи. После каждого следующего
slice координатор получает exact commit/tests/gaps. Независимый следующий шаг — canonical
serializers для уже описанных policy/generation/send bytes, чтобы repository повторно
использовал проверенную реализацию. Это не заменит DDL/DB/HTTP acceptance.
