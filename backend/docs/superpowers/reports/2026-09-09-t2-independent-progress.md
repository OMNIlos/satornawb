# T2 — independent progress / dependency handoff

## CURRENT — original requirements, local readiness and owners

Updated 2026-09-09 after root process-audit direction. This is the **only current
requirement status table**. Everything under HISTORY below is dated evidence, not
current readiness. Counts prove only named tests, never completion of a stage.

Scope amendment from user via root,2026-09-09: shared WB/Avito Production assembly
and printing is **DEFERRED, not DONE** (workitems/assignments/batches/schedule,
assembly sheets/XLSX/PDF/labels/print archive/delivery receipt). T3 owns its exact
deferred readiness/dependency inventory; T2 neither resumes its implementation nor
searches missing renderer/calendar sources. Preserve already committed code/schema
and required compatibility regression, but Production completion is not a gate for
remaining-scope acceptance/integration/push. Orders ingestion/storage/read/API/source
progression and all T2 repricer/settings/economics/sources requirements remain active.
KIZ/matcher stays excluded. Activation/provider/flag restrictions and heavy queue
are unchanged. Existing0069 compatibility may be tested without resuming P1–P4 work.

`implemented` = code exists at the stated SHA; `released` = bounded owner handoff;
`consumer-accepted` = downstream owner actually accepted that exact contract;
`final-integrated` = common candidate verified by root. The latter is **not yet
established for T2**. Production activation is NOT AUTHORIZED, separately from local
implementation/testing; no provider calls, flag changes, deploy or push in T2.

| Requirement | Actual implementation / released input SHA | Verified evidence and acceptance | Remaining / exact owner |
| --- | --- | --- | --- |
| 1 Writers, identity bridge, repository contract | `769f3cf44742622824233eefe8f81d4e360f8484`, `ccaed3410e32c50b3604f02e5b1171fd7243ce49`, `45f94a39627ebe2916903e9e5e0930844f3daaf5` | Inventory/explicit identity bridge/scoped contract implemented; T1 approval0066 consumed by merge `1464fcdfaab15b053678dd4f6d0337d958dab7f7`; valid action keys unchanged | T2 current writers still disconnected; account/membership bridge is not authorization or writer cutover |
| 2 Durable approvals | `bd3bb60a0baadc8d7683c8efd8bf4eff444c9643`, legacy import `9c7e5baa6dc3b3b2f113671b03db6c301942b1e7` | Actual PG participant + committed user-session create/claim/reject/block; recorded93PG cases include CAS/races/scope/restart/rollback/import; locally accepted0066 only | T2 full Protocol/worker-authorized outcome service and current-flow integration incomplete; T1 accepted worker authority/schema needed, then T2 service acceptance |
| 3 Jobs, attempts, receipt, crash recovery | Participant at `bd3bb60`; job-domain request `3c99f1eddb4750faa2be0ce79806c2d6f26cbc7e`; raw receipt codec `43e2cab31707192f2a30ab9b00ca7e56c6b11c4d` | Durable attempt/marker/outcome primitives tested;95synthetic receipt cases. Job/receipt domain inputs released to T1, not DDL or worker-service READY | T1 exact jobs/receipt DDL + trusted worker/closing resolver; T2 actual dispatch/reconciliation/crash matrix through fake-provider service, duplicate delivery proof, one action owner. No external exactly-once claim |
| 4 Normalized settings / removal of globals | Override codec `bfc6c0eb156ef5b6a1d0a5b14066a6c7bb0ad01a`, vectors `a6b9fd1975d509911abc9da666bc0049e49228ce`, characterization `f3c61d7704813790245ec73096c753ee5dd93915`; shared permissions consumed by `5294fdb0860092b20c1fcc9c71b781b8666518a3` |78override cases; T1 independently reconstructed6vectors and accepted bytes as DDL prerequisite.102legacy calculation cases;81pure shared-export+codec cases. Permissions released and consumer-accepted; no durable state/service acceptance | T1 selected override-only versions/heads/separate audit design; exact DDL/ACL release pending. T2 scoped PG repository + authenticated service next. Org settings/assignments/liquidation/context rows and mapping versions remain T1/T2 work; one-writer fence/cutover NOT done |
| 5 Price snapshots / stock snapshots / daily / typed reads | Price `4e14e21ce79ebda29144d17db0b4a798f4bd2ec4`, stock `f7a5d62548d86f39c588c531c143936f0af8e55a`, chronology fix `901c1796e9a0ab04c0a4c7256e19bcce64dbaef1`; DDL request `907ec7b46ea5b6427385c7e80a204cb80f4adcad` | Immutable typed adapters/manifests/grain/presence and UTC chronology implemented;104scoped parser cases. Not actual publication or historical stock persistence | T1 source DDL; T2 atomic publication/current-head CAS, stock daily revisions and typed DB reads, fake collection/restart tests. FBS exact identity contract and source freshness policy unresolved; today's stock is not historical evidence |
| 6 KTR and source revision policy | `94b540f592a0fed3a29ce476fdb3dbd7ce58a604`; stock evidence request `0edde8bcc735999eaec0361620af47eee0b2c8a0`, codec/vectors `0c8fca9c5f8bdf62e630398cb1bd663acfb2cee0` | SourceDiff classification and stock count-only bytes implemented;69pure codec/diff cases. T1 accepted8vectors as prerequisite, not SQL/auth/publication proof; exact requests delivered | Owner source evidence: KTR artifact/effective bands + local/all-orders grain; T1 evidence DDL/auth, T2 complete diff+parent-linked daily correction service. Finance rrd/fingerprint limitation preserved; scheduler off |
| 7 Final profitability | Decision package `94b540f592a0fed3a29ce476fdb3dbd7ce58a604` | Synthetic alternatives delivered; no financial rule selected, no final-profit implementation/acceptance claimed | Financial owner approval + complete source evidence, then T2 canonical service/golden tests. netProfitKopecks/profitClass/abcCode remain null; no guessed allocation/account/backdate/rrdId/hash adjustment |
| 8 Test debt, rollback and common integration | Current code candidate `f3c61d7704813790245ec73096c753ee5dd93915`; scoped fixes/commands below | Named unit and owned-disposable PG evidence only; inherited lint deltas disclosed. T4 independently reran102characterization cases with OS network deny. No full backend/combined platform acceptance | Root one common integration milestone after T1 platform release; T2 consumer regression on accepted dependencies, remaining assigned failures and rollback verification. No further abstractions/characterization without a concrete service need |

### Canonical SKU policy — one compatibility record

Root explicitly approved: independent get/history require fixed `settings:read`;
replace and exact-command replay require **both** `settings:read` + `settings:write`
before reading receipt or acquiring domain locks. A write-only custom principal is
now denied by the new canonical API, even if a legacy write path would allow it.
This is intentional compatibility impact, not inferred historical behavior. Existing
profiles/aliases, profile+explicit-grant union, operational grants and legacy routes
remain unchanged. No price:send/team:write fallback or client-selected permission.
Fresh authenticated user/session/membership/exact account scope and final commit
revalidation apply to each call/replay; idempotency key grants no authority.
T1 released exact shared constants at `47ca9513244ea29f21aba47527cbd8807d31caed`;
T2 consumed via cherry-pick-x `5294fdb0860092b20c1fcc9c71b781b8666518a3`.
Context-only conflict resolved by adding only the two SKU sets: T2 did not yet have
adjacent Production constants, which were neither imported nor deleted by this slice.
Actual pure exports+override codec **81PASS0.07s**, compileall/diff0. This confirms
the exports, not authenticated service or DB authorization; those remain required.
Required service matrix: read-only/write-only/both/neither, cross-account, revoke
after wait, denied mutation and receipt non-disclosure. No repeat policy approval needed.

Verified access-only consumer slice (not a repository/service release):
`app/modules/wb_repricing_override_access.py` and `tests/test_wb_override_access.py`
use the actual released permission exports, existing publication guard and existing
Catalog offer rows. Separate read and replace entry points; mapping SHARE locks
follow auth/account locks and persist through the caller-owned root. Actual final
**19 PASS / 5.59s / natural exit0** on accepted0066 with non-owner runtime and OS
network-deny sandbox, including observed mapping/revocation waits. Scoped Ruff,
compileall and diff-check exit0. Exact temporary DB
orders_test_df4ce14e8bad420794bf40e270aedd59 and role
repricer_runtime_f0c44acef0814f2f9153aabfb978d300 cleanup absence verified.
Existing libpq /dev/null passfile warnings retained. Read-only critic found no
defects in the domain-error fix; PostgreSQL concurrency proof is this actual run.

Historical RED steps for this slice (superseded by final19PASS above):
Missing-module collection RED verified; scoped Ruff/compile0. First admitted actual
PG gate stopped with **14 PASS / 1 FAIL, 3.40s, natural exit1**: shared guard safely
normalized the unsupported domain mapping code to publication_persistence_failed.
Fixed locally with a separate fixed-message OverrideMappingUnresolvedError, leaving
the shared guard/allowlist unchanged. Exact owned DB orders_test_a941c45710c94013a90988060802ad43 and role
repricer_runtime_c2c7919ec28545cfb91e6bb2e7b4ba1d cleanup absence verified; no pending
cleanup. This is no substitute for the pending
override repository/receipt/CAS/audit implementation and is excluded from frozen
integration candidate f3c61d7. No new schema or general-purpose repository added.
Second admitted gate: **18 PASS / 1 FAIL, 9.97s, natural exit1**; mapping blocker
regression passed. The membership-race observer incorrectly matched FOR UPDATE,
where the accepted guard uses with_for_update(read=True), i.e. FOR SHARE. Corrected
that observer only; no timeout or guard change. Exact temporary DB
orders_test_5729daa46d174241b2f6c65cd2538fb0 and role
repricer_runtime_dadeca7a32b64e75929cdfe5e512b7e9 cleanup absence verified.
Independent follow-up: all six invalid-authority cases now explicitly observe zero
Catalog queries, not merely an eventual exception. Future service ordering is BOTH
live authorization -> exact scoped receipt lookup -> current mapping lock only for
a new revision. The combined replace helper is not a replay entry point; historical
replay must not require a surviving current mapping. This boundary was sent to T1.

### Stable consumer candidate for the common milestone

Immutable T2 code candidate: `f3c61d7704813790245ec73096c753ee5dd93915` on
`codex/arch-t2-economics`, base `c88a474695569af905b294906ba604d61f3de62f`.
Exact accepted0066 prerequisite: `dbf8d31d9fc0b9035b9c8a84727e70713956afe0`,
merged with its platform/guard ancestry by `1464fcdfaab15b053678dd4f6d0337d958dab7f7`.
This includes the0066 consumer and released pure source prerequisites; no speculative
imports of upcoming override constants/tables. Accepted compatibility currently means
0066 plus its merged guard prerequisites, **not** the later combined platform.
Root may use this candidate after T1 platform release for one shared migration/import/
contract/consumer gate; root owns integration and authorized push. T2 will update the
candidate when an actual new accepted repository/service dependency is consumed,
not for each test/docs commit. Stage2/3/4/5 remain incomplete after this milestone.
Read-only `git diff --exit-code 9c7e5ba f3c61d7` confirms the participant/user-command
modules and all three PG acceptance test files byte-unchanged; merge-base verifies
0066 ancestry, both exit0. These are snapshot checks, not a new platform test run.
Next work priority is actual worker/outcome/jobs/receipt and normalized override/source
repositories/services using exact released T1 contracts, not extra generic codecs.

## HISTORY — prior snapshots and per-slice evidence (not current status)

## T1 SQL encoder golden-vector dependency

`tests/fixtures/wb_repricing_sql_golden_vectors_v1.json`: eight synthetic vectors
generated by exact45f94a3 domain serializers (those three modules are byte-unchanged
at this delivery). Actual API is `CanonicalApplyRequest`, not a function named
build_price_apply_request. Each vector stores typed input scope/request, UUID4,
canonical request ASCII text/byte count, request checksum, action/dispatch keys and
pure provider-body bytes as ASCII text. No provider request was sent.

Coverage: explicit optional NULL; all optional IDs/minimum populated; Cyrillic;
decomposed/precomposed combining text independently; supplementary emoji;
quote/backslash/slash; permitted interior approval controls including DEL; business
integers above BIGINT. Org/account/catalog remain positive internal INTEGER-range IDs.
All requests fit4096 bytes (218..335). Fixture itself is ASCII JSON: load outer JSON
once, then encode `canonical_request_ascii` as ASCII; do not JSON-encode it again.
Use exact integer JSON decoder (Python json.loads); JS Number would lose big integers.
SQL encoder should compare to these literal bytes/hashes, not regenerate expected
results through SQL under test. Fixture is never regenerated automatically in tests.

RED fixture missing →GREEN parity regression; kernel/repository/dispatch adjacent
228PASS. Existing negative Unicode corpus remains in test_wb_repricing_postgres_text.py.
This supplies parity vectors requested by T1 design7e9085c, not DDL acceptance.

Branch `codex/arch-t2-economics`, base `c88a474695569af905b294906ba604d61f3de62f`.
Worktree `satornawb-main/.worktrees/arch-t2-economics`. No push/deploy/production,
provider requests, working DB/Redis/state, schema/config/shared wiring/flags changes
in these slices. Existing pure approval ownership/action keys preserved. Tests use
synthetic values; cost/economics legacy tests use ephemeral in-memory SQLite, **not**
a substitute for PostgreSQL approval acceptance. Offline plugin fence is Python-level,
not an OS/native networking sandbox. No native PostgreSQL calls in this delivery.

## Exact ready commits since root's 6ee8485

| Commit | Scope / evidence |
| --- | --- |
| `4e14e21ce79ebda29144d17db0b4a798f4bd2ec4` | Seller-price raw parser/immutable pages/complete manifest; initial54 tests; corrected below |
| `45f94a39627ebe2916903e9e5e0930844f3daaf5` | Kernel/repository/dispatch reject PostgreSQL-unrepresentable text;72 new tests,227 adjacent; updated approval schema request |
| `907ec7b46ea5b6427385c7e80a204cb80f4adcad` | Two independently reviewed exact bounded DDL requests: normalized state4A and prices/stocks/daily5 |
| `c11d07b3d623c5e534bac84166714377d3312a3f` | Safe DecimalException decode boundary;2RED→56parser+16root syntheticPASS |
| `02591f3c249fbb32082e802b27ca7a058fff83e6` | Pure scoped CollectionRequest canonical bytes/checksum;29 tests |
| `f7a5d62548d86f39c588c531c143936f0af8e55a` | WB warehouse stock parser/grain/complete manifests/receipt-daily eligibility;42 tests |

Exact changed files per commit: `git show --stat --name-status <full SHA>`. New modules:
`app/modules/wb_price_snapshots.py`, `wb_source_requests.py`, `wb_stock_snapshots.py`;
new tests respectively `test_wb_canonical_price_parser.py`,
`test_wb_source_collection_request.py`, `test_wb_stock_snapshots.py`, plus approval
`test_wb_repricing_postgres_text.py`. Approval change touches only pure kernel,
repository Protocol/identity bridge and dispatch domain; no actual writer connection.

## Historical requirement snapshot — superseded by CURRENT above

| Stage | Completed evidence | Still required / actual dependency |
| --- | --- | --- |
| 1 writer inventory / identity / contract | 769f3cf + ccaed341 +45f94a; composite scope, exclusive marker, safe UUID/text, unchanged valid hashes; accepted T1 approvals0066 dbf8d31 merged by1464fcd | No UUID-only repository; current writers still disconnected |
| 2 durable approvals | Actual scoped PostgreSQL transaction participant plus committed user-session create/claim/reject/block; real runtime-role tests, two-session CAS, replay, rollback, restart, crossorg/account, immutable terminals; owner-only synthetic legacy import preserving full snapshot | Full repository Protocol not complete: worker-authorized outcome service still pending; no current-flow cutover |
| 3 jobs/crash | Pure matrix plus durable reserve/dispatch marker/outcome participant, observed PostgreSQL dispatch lock race and one synthetic effect | Accepted worker/job authority PENDING per T1; no worker impersonation, scheduler/provider wiring or reconciliation activation. No external exactly-once claim |
| 4 globals/settings | 80 legacy characterization cases; exact normalized4A schema request907ec7b; pure four-strategy AssignmentChange canonical command bytes/checksum | T1 rows/heads/audit, concrete repository/context wiring and one-writer fence; additional strategies/context mapping must be typed before cutover |
| 5 prices/stocks/daily | Price and warehouse stock adapters,request hashes,immutable complete manifest assembly,missing/null/zero,all sizes,receipt-date gate; targeted legacy source fixes | T1 separate source DDL, DB publication/read services, current-head CAS and daily revision persistence; Catalog mapping/source freshness policy, FBS skus/chrtIds contract unresolved |
| 6 KTR/source revisions | SourceDiff classifications + synthetic closed-day revision evidence tests (94b540f/ee7bd6e) | Verified local/all orders grain, reference effective ranges/gaps/overlap evidence; unknown remains null, scheduler off |
| 7 final profit | Decision package94b540f with numerical alternatives | Explicit financial owner approval and complete source evidence. No invented OPEX allocation/backdate/rrdId/checksum change; netProfitKopecks/profitClass/abcCode remain null |
| 8 test debt / handoff | Targeted source/cache/RNP/economics regressions repaired; new scoped group below | Not full backend parity and not DB durability; no weakened guards/removed tests |

No claim that whole T2 scope or the complete repository/service protocol is ready.
Accepted T1 approval schema0066 `dbf8d31d9fc0b9035b9c8a84727e70713956afe0`
and its reviewed platform prerequisites were merged without conflicts by
`1464fcdfaab15b053678dd4f6d0337d958dab7f7`. State4A and source requests remain
independent dependencies, not queued behind complete repricer.

## Verification

From this worktree `backend`, runtime:
`/Users/bratishka/Downloads/satornawb-main/.worktrees/wave1-integration/backend/.venv/bin/python`.

```sh
python -m pytest -q -p tests.repricer_offline_plugin \
 tests/test_wb_stock_snapshots.py tests/test_wb_repricing_postgres_text.py \
 tests/test_wb_source_collection_request.py tests/test_wb_canonical_price_parser.py \
 tests/test_wb_price_size_preservation.py tests/test_wb_repricing_dispatch_contract.py \
 tests/test_wb_repricing_repository_contract.py tests/test_wb_repricing_approval_domain.py \
 tests/test_wb_repricing_price_inputs.py tests/test_wb_source_revision.py \
 tests/test_wb_source_grain_contract.py tests/test_wb_stock_page_validation.py \
 tests/test_wb_price_units.py tests/test_repricer_calculation_characterization.py \
 tests/test_economics_internal_identity.py tests/test_economics_policies.py \
 tests/test_abc_pnl_costs.py tests/test_rnp_runtime.py \
 tests/test_rnp_source_period_isolation.py tests/test_repricer_bff_cache_contract.py \
 tests/test_repricer_cache_store.py
```

Ruff runtime `/tmp/satorna-backend-verify-20260908/bin/python -m ruff check` and
`python -m compileall -q`: kernel/repository/dispatch/price_snapshots/source_requests/
stock_snapshots modules plus four new/updated tests listed above; both exit0.
`git diff --check`, staged diff checks exit0. Scoped test results recorded below;
counts are not added to infer a broader suite. Fresh combined command above:
**662 passed in2.24s, exit0**, no pytest warnings. Earlier independently scoped source
group556PASS and economics/cache group106PASS were also run separately;662 is an
actual combined run, not only arithmetic. Historical full-suite delta remains unproved.

Independent critique closed text UUID exception leakage, unsupported FBS transport,
schema nullability/audit/paused-slot ambiguities, collection integer serialization,
stock owner range and daily datetime overflow. Every code defect gained a failing
test before correction. Stock final three findings rechecked locally by fresh tests.

## Accepted approvals persistence slice

Owned code: `app/modules/wb_repricing_postgres.py`,
`app/modules/wb_repricing_commands.py`; tests:
`tests/test_wb_repricing_postgres_repository.py`,
`tests/test_wb_repricing_approval_commands.py`. Existing pure kernel, current
repricer, migrations/config/shared wiring are unchanged by this T2 slice.

`ApprovalTransaction` is explicitly an **uncommitted** scoped transaction
participant, not authentication and not send permission. `UserApprovalCommands`
owns its clean Engine-bound root and returns after physical commit only. The latter
uses accepted live PublicationGuard with fixed `price:send`, authenticated membership
derived from its principal, exact account binding and no request-selected permission.
It exposes no reserve/dispatch/outcome or worker API. Guard-through-commit behavior
also depends on accepted T1 guard tests, not solely the tests added here.

RED: missing participant module/API (collection exit2); missing attempt-ID boundary
6 failing cases, missing durable attempt2 failures (exit1). GREEN: corrected required
canonical UUID4 and absent-row conflict. User service RED: absent module (exit2).
Fresh combined real PostgreSQL run: **75 passed in12.77s, exit0**. The runtime role
is nonowner/NOBYPASSRLS, actual migrations run into disposable databases; fixture
verified exact database and role cleanup. Explicit null pgpass produces benign
libpq `/dev/null is not a plain file` warnings; no real credential files read.

Reproduction from backend (same interpreter as above): scrub environment with
`env -i PATH=/usr/local/bin:/usr/bin:/bin PGPASSFILE=/dev/null PGSERVICEFILE=/dev/null
NETRC=/dev/null PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 ORDERS_TEST_USE_LOCAL_CLUSTER=1`,
then `/usr/bin/sandbox-exec -f ../.superpowers/t2-repository-offline.sb python
-m pytest -q -s tests/test_wb_repricing_postgres_repository.py
tests/test_wb_repricing_approval_commands.py --tb=short`.
The local untracked test-only sandbox profile allows default, denies network,
then allows outbound Unix socket `/private/tmp/.s.PGSQL.5432` only, and denies
reads matching `(^|/)\.env($|\.)` or `(^|/)(\.pgpass|\.netrc)$`.
This is not an application/config change. No provider TCP access or production DB.

Fresh unchanged pure approval/identity/dispatch/Postgres-text/golden-vector group:
**228 passed in0.19s, exit0**. Ruff, compileall and diff checks are scoped to the four
owned Python files. Independent critic's missing-ID blocker fixed/rechecked;
final read-only review found no further blockers. Full backend baseline delta and
privileged backfill preservation are not claimed by these results.

Worker-authority amendment committed `a4de0b8a653857779391bb054ac06cde7d0ac184`
and sent directly to T1. Known upload ID with ambiguous requires a separate durable
receipt/evidence boundary: current domain/0066 prohibit upload ID on ambiguous.
Worker/provider/scheduler remain dormant pending that accepted contract.

### Independent synthetic backfill continuation

`LegacyApprovalImportTransaction` is a separate owner-only caller-committed surface;
runtime role denied before import. Explicit positive internal catalog/member IDs
must exactly match snapshot identities; unresolved legacy strings remain blocked.
No files read, rekeying, inferred IDs, repaired hashes or historical time changes.
All seven statuses, long logical ID, NUMERIC values above BIGINT, original timestamps,
replay/conflicting payload and transaction rollback are tested. Current old rows
are still immutable/non-dispatchable by0066; this is not a real data backfill run.

RED: absent importer API, collection exit2. Fresh combined three-file PG group
(repository, user commands, `tests/test_wb_repricing_legacy_import.py`):
**93 passed in11.94s, exit0**, exact three disposable databases/runtime roles cleaned.
Importer has18 cases. Scoped Ruff/compileall exit0. Independent critic found no
importer blockers; worker receipt limitation clarified in the existing amendment.
The historical note above about missing backfill proof is superseded only for these
synthetic cases, not a production migration/backfill or full backend baseline.

### Independent Stage4A assignment command codec

`app/modules/wb_repricing_assignments.py` +
`tests/test_wb_repricing_assignment_command.py` fix the full assignment command
encoding documented in the existing settings-state schema request. Strict internal
INT4 scope/member, UUID4 command, exact decimal version, four supported strategies,
explicit clear/null, interval compatibility and immutable aware UTC instant. Unknown
strategy/config is not defaulted. No registry/global reads, formula changes, clock,
repository or current-state mutation. A checksum is neither auth nor proof of DB CAS.

RED missing module exit2 →56 pure cases pass. Fresh combined codec+unchanged old
calculation characterization: **136 passed in1.05s, exit0** under offline plugin.
Scoped Ruff/compile/diff exit0; independent read-only critic found no codec issues.
This fixes assignment bytes only, not settings/overrides/liquidation serializers.

T1 additionally requested exact receipt schema evidence; the separate
`2026-09-09-t2-provider-upload-receipt-schema-request.md` traces available WB22/WB23
fields, lossy `_as_int`, mixed HTTP/task status, incomplete details pagination and
receipt-vs-applied semantics. No provider jobs run. Receipt DDL, strict initial-ID
adapter projection and worker/job reference remain pending; audit vocabulary and
finite separate-clock semantics are explicit, no guessed retention/permission/TTL.

### Dormant decoded upload-ID projection

After T1 accepted470d410 as domain input (not schema READY), added
`app/modules/wb_repricing_upload_receipt.py` with47 synthetic offline tests in
`tests/test_wb_repricing_upload_receipt.py`. Original decoded POST response only;
no float/bool truncation, invalid alias fallback, unknown transport or raw error
reflection. It returns only ID, never applied state or retained response payload.
No current adapter/client or provider execution is connected.

RED missing module exit2; nested explicit error2FAIL exit1 → corrected GREEN.
Fresh projection+assignment+dispatch group **165 passed in0.52s, exit0**; scoped
Ruff/compile/diff0. Independent critic47PASS and no material findings. Pure helper
does not establish raw JSON duplicate-key validation, trusted transport provenance,
job authority, committed dispatch proof or receipt persistence; those remain gates.

Worker dependency ownership clarified after critique: resolver belongs to T1, but
T2 can propose domain job rows/lifecycle independently. The worker amendment now
contains exact proposed `wb_repricing_jobs` UUID4 binding, composite approval/origin
references and creation audit. Lifecycle remains derived from0066, not a second
mutable state machine. Receipt gets a proposed concrete scoped job FK. Existing
ORM/memory/Orders proposal are not misrepresented as accepted price-worker authority;
trusted executor/closing resolver remains T1-owned and pending. No production or
shared schema changes and no fabricated worker principal.

### Independent raw receipt JSON boundary

`extract_post_upload_id_from_bytes` now accepts original immutable UTF-8 bytes,
requires an explicit trusted response-byte budget, rejects duplicate/escaped-equal
keys and malformed/non-finite JSON, and preserves integer lexemes beyond BIGINT
and Python's decimal-string digit limit. Decimal/exponent tokens never become IDs.
Only canonical ID is returned; no raw payload/checksum is retained. The decoded
entrypoint remains available but cannot establish raw JSON uniqueness by itself.

RED missing raw API exit2 → **95 combined raw+decoded cases PASS in0.06s, exit0**
(48 new raw cases). Independent critic reran95PASS; scoped Ruff/compile/diff0.
The existing transport does not call this helper: trusted POST provenance, job
authority, marker-commit proof and receipt DB publication remain separate gates.
T4's available/blocked matrix was sent before implementation, not used as a stopping
point; no frontend or active T1 schema/resolver work was duplicated.

### Independent full-row SKU override command codec

Added dormant `wb_repricing_overrides.py` and61 synthetic tests. Full immutable
nullable row, strict internal ownership/member IDs, UUID4 command, expected version,
lossless money/Decimal canonical bytes and SHA-256. No new percentage bounds or
cross-field formula rules; existing formula guards are unchanged. Explicit trusted
byte budget rejects compact exponent expansion. No current override registry read
or write, no persistence/auth claims and no dependency on unaccepted schema.

RED missing module: collection exit2. GREEN focused56PASS; five extra decimal
position cases added. Fresh combined override/assignment/decoded+raw receipt run:
**212 passed in0.88s, exit0** under offline plugin. Scoped Ruff (two mechanical
test literal fixes), compileall and diff checks exit0. Independent critic reran
the original56 cases, exit0, and found no defects. Existing schema request records
the exact codec boundary; Stage4 persistence, immutable calculation context and
one-writer fence remain unimplemented gates, not implied by these tests.

Follow-up contract pinning: fixed v1 all-NULL golden checksum, all14 override
fields individually participate in the hash, and AST import allowlist prevents
accidental runtime/client dependencies. Fresh combined group **228PASS in0.16s**;
override suite now77 cases. Ruff from `backend` exits0. A root-cwd Ruff invocation
reported I001 because import-root inference differs; the documented backend-cwd
invocation passes without source changes. This is a scoped check, not whole-repo lint.

### Real independent input-guard defect: DST elapsed TTL

Strict-boundary review found a real defect in dormant `wb_repricing_price_inputs`:
adding TTL/comparing datetimes in the same timezone used wall-clock semantics.
Synthetic New York fall-back accepted an expired observation as fresh and accepted
a future fold as current; spring-forward expired a still-fresh observation early.
RED **3FAIL32PASS**, exit1. Root cause fixed by normalizing comparison instants to
UTC before elapsed-second TTL arithmetic, while retaining original observation.
UTC overflow fails closed; timezone/freshness policies and TTL values are not invented.

Six regressions (DST3, UTC boundary2, provenance/equivalent offset1). Independent
critic **38PASS**, no findings. Fresh combined price-input/stock/price-parser/source-
revision/unchanged legacy calculation group **245PASS54.76s**, exit0. Compileall and
diff0. Ruff exit1 has exactly the same5 diagnostics as pre-change HEAD: TRY004,
I001, UP017, C408x2; new test lines use UTC and introduce no additional diagnostics.
This is not a full-backend baseline claim. No current repricer wiring or formula edits.
Rollback is a code-only revert of this bounded fix; no data/schema/backfill exists
for this dormant guard. Activating it still requires accepted canonical inputs and
the existing approval/economics/one-writer gates.

### T1-requested stock evidence codec and literal SQL vectors

Implemented the existing0edde8b §3 row/diff/proposal wire contract, no new policy
or abstraction outside that request. New `wb_stock_evidence_codec.py`, focused
test and eight literal vectors (`wb_stock_evidence_golden_v1.json`), with full inputs,
ASCII bytes/count/hash. Native identity separated from count-only payload; missing/
null/zero, BIGINT, lexical sorting, all delta categories, Unicode/escaping covered.
Proposal derives hashes/counts, rejects duplicate/empty evidence and invalid owners.
Explicit encoding budget is caller-supplied, not invented permission/retention policy.

RED missing module exit2 →40 focusedPASS0.05s, including actual fixture parity.
Read-only critic found fixture-test gap during work (closed by non-regenerating test)
and preallocation order (fixed). No critic test processes during T1 resource slot.
No PostgreSQL/integration/browser/build/fullsuite run; scoped lightweight verification
only. Complete-run/evidence auth/parent-linked CAS/daily eligibility remain separate
unproved gates. Existing source hashes/compare_runs/formulas/flags untouched.
Final lightweight codec+existing SourceDiff run **69PASS0.07s**, exit0; scoped
Ruff/compileall/diff checks exit0. No accepted SQL parity or DB gate implied.

### Source page chronology: same-zone DST regression

Independent strict-boundary review found the same wall-clock comparison issue in
both canonical price/warehouse-stock run assemblers. RED6FAIL0.08s: each rejected
valid increasing fall-back instants, accepted reversed actual instants, and accepted
a UTC-unrepresentable receipt. Fixed only comparison locals to UTC, safe domain
overflow rejection; original pages/times/raw checksums/manifest algorithm unchanged.
Added `tests/test_wb_source_page_chronology.py`, preserving page object identity and
comparing manifest checksum against an equivalent UTC representation.

Fresh lightweight new chronology+existing price/stock parser group **104PASS0.10s**,
exit0; scoped Ruff/compileall/diff0. Read-only critic no findings, no test process.
No heavy slot used, no actual source request, schema or current publication/wiring.
Rollback is a code-only revert, no migrated facts. New schema dependencies requested
directly from T1; uncommitted0069 Production work is unrelated, not consumed as a
repricer/source READY handoff. Continue independent work while awaiting exact acceptance.

### Next schema selection: SKU overrides / dedicated parity vectors

T1 selected bounded SKU overrides only from existingbfc6c0 request, not whole4A;
this can unblock a scoped transaction participant without worker authority or
source/context wiring. T2 provided exact request/codec/pinned-test SHAs, explicitly
not claiming a dedicated fixture existed at that point. Then supplied the requested
six literal vectors in `wb_repricing_override_golden_v1.json` covering fullowner,
14fields, NULL/false/zero, signed/fraction Decimal normalization,2**80 money/version,
longprecision, modes andINT4 boundaries. Existing encoder byte-unchanged.

Actual missing-fixture RED1FAIL77deselected → focused **78PASS0.07s**, exit0; test
loads pinned expected bytes/hash/count and never regenerates.8192 syntheticbudget,
no operational policy. Native NUMERIC limits and separate settings-write/live mapping
auth must remain explicit; these vectors are SQL parity inputs, not SQL proof.
Scoped Ruff/compileall/diff exit0; read-only critic no findings, no extra test process.

### Independent override-to-calculation characterization gap

Added22 test-only cases to existing `test_repricer_calculation_characterization.py`:
explicit pMin/alias/zero inheritance, fixed costs/pick-pack/expense precedence,
nonpositive denominator fallback, pMax/RRP/margin priority, minutes/hours/global
interval fallback and input/global immutability. Original repricer code is unchanged.
These pin actual legacy behavior, not approved financial rules or new API defaults.

One synthetic precision boundary is explicit: `2**53+1` passes direct pMin exactly,
but the existing COGS path crosses float and produces one kopeck less. This must not
be hidden by future integer storage/codec exactness claims. No business formula or
checksum is adjusted to repair it in a state-migration slice; no real data involved.

Fresh focused **22PASS0.57s,80deselected**, naturalexit0; no claim the entire102case
file ran at this revision. Compileall/diff0. Ruff exit1 same3 inherited diagnostics
as pre-change HEAD (I001,C408,UP017), no new diagnostics. Fixture blocks network,
approval/apply/storage entry points and restores monkeypatched globals. No PG,
browser/build/fullsuite gate or heavy-slot reservation. Test-only rollback removes
the new cases; no runtime/schema/data rollback needed.
Final single-module unit run **102PASS0.62s**, naturalexit0 (old80+new22 actually
run together). Read-only critic found no defects, did not start test processes.
