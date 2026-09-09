# T3 Orders / Production: requirement tracking

Branch `codex/arch-t3-operations`; исходная база `c88a474`.
Общая очередь не активирована. Legacy writers/prototype сохранены.

## Scope override пользователя, 2026-09-09

КИЗ/Честный знак и отдельный recovered matcher исключены из продукта по прямому
указанию пользователя. Isolated matcher harness/report удалены: runtime imports
или consumers отсутствуют. PHP runtime tests не запускались. Исторические строки
ниже про КИЗ/source recovery описывают прежний scope и больше не являются gates.
Avito return matching, Catalog resolution, WB/Avito order identities, XLSX и
обычная печать не относятся к удаляемому КИЗ subsystem и сохранены.
Backend app scan не обнаружил kiz/chz/КИЗ/Честный знак runtime references.
Frontend placeholders требуют отдельной правки владельца T4; координатор уведомлён.
Backup/user data и исторические Git commits не удалялись.

| Этап / requirement | Реализованные commits / проверки | Remaining / blocker |
|---|---|---|
| 1 Discovery / parity / schema request | `4323821` Stage1; `3a30b16` offline/XLSX; `f4d6d55` returns/XLSX edge characterization | Полного production prototype нет; только частичные исходники. КИЗ/matcher исключены, не blocker |
| 2 Identity / normalized ingestion | Pure contract/manifest/serialization; `51e0b3c` account-serialized exact replay; `a197a65` parent CAS; `03a30b8` item CAS; T1 actual0064 merged `2d9a400`, consumer+DDL106PASS | Atomic manifest/status/coverage/run publication and source-progression composition unfinished; T1 shared auth guard/revocation races pending |
| 3 Catalog / read API | Item-scoped read models, exact decoder; `cd5c277` immutable snapshot repository, `32d5af5` parent fence; same-org cross-account Product FK negative | Repository resolution, live permissions/signed cursors/API wiring pending; persisted snapshot is not an authorized HTTP endpoint |
| 4 Production work items / commands | `1afd5a2` pure assignment preconditions; DB09-DB13 specification | Production schema/receipts/audit отсутствуют в Orders candidate; нужны отдельный binding и T1 DDL; concurrency proof NOT_RUN |
| 5 Batches / groups / frozen sheets | Только discovery/parity requirements | Полный legacy schedule/grouping source не восстановлен; Orders read snapshot не равен Production sheet |
| 6 XLSX | Renderer characterization: inline text, leading zeros, Cyrillic, quantities, 1000 rows; `f013dec` rejects XML-invalid controls | Frozen sheet adapter/артефакт persistence требуют Production contract |
| 6 A4 PDF | Source gap описан | Нет полного renderer/fixtures, не реконструировать по screenshots; multipage/48+ rows NOT_RUN |
| 6 Stickers 120x75 / 58x40 | Source gap documented; no substitute renderer invented | Нужны исходники обычных WB/Avito renderers; selected unit identity/barcode/quantity parity NOT_RUN. КИЗ/matcher не требуются |
| 7 Archive / delivery | Requirements and safety boundaries preserved; КИЗ excluded | Immutable historical artifact and delivery receipt/ambiguity require source+Production schema prerequisites |
| 8 Cutover / retirement | Proposed T4 wire/error handoff `f4d6d55`, no activation | Нет полной parity/reconciliation/writer fence/rollback proof; prototype не удалён; switch запрещён |

## Strict storage decoder slice

`deserialize_observation` и `deserialize_read_row` в `app/orders/serialization.py`:
exact envelope/version, exact nested fields, strict scalars/arrays, canonical UTC
timestamp encoding, reconstruction через existing validated frozen models.
Отвергает unknown version, bool/float/string version, extra/missing fields, forged
source line key/account/status mapping, invalid resolution и mismatched read item.
Нет fallback на current Catalog или provider. JSONB object input, не JSON text
parser: duplicate JSON keys должны отвергаться до JSONB, если будет внешний JSON
ingress. Этот decoder не подключён к API и не устанавливает authority SQL FK.

Формат v1 связан с существующими mapping versions. При будущем изменении mapper
нужен явный versioned decoder/mapping registry; нельзя silently remap historical
status или переименовать v1 fields. Повреждённая история требует reconciliation,
не скрытого repair. Права проверяет будущий repository на каждой странице.

TDD RED: отсутствующий `deserialize_observation`, pytest exit2. GREEN: 27 decoder
cases; combined scoped offline regression **232 passed, 2 прежних dependency
warnings**, exit0. Ruff проходит. Compileall/diff проверяются перед commit.
Self-review: проверены schema versions, nested domain validation, отсутствие
mutation входного JSON и mutable Catalog/network imports. Full backend baseline,
DB/CAS/RLS/renderer visual parity НЕ заявляются.

```sh
python -m pytest -p tests.orders_offline_plugin -q tests/test_orders_decoding.py \
  tests/test_orders_serialization.py tests/test_orders_contract.py \
  tests/test_orders_stage1_characterization.py tests/test_orders_xlsx_characterization.py \
  tests/test_orders_offline_guard.py tests/test_avito_orders.py tests/test_avito_returns.py \
  tests/test_orders_ingestion.py tests/test_orders_read_contracts.py \
  tests/test_orders_avito_adapter_characterization.py tests/test_orders_returns_characterization.py
python -m ruff check app/orders/serialization.py tests/test_orders_decoding.py
python -m compileall -q app/orders/serialization.py tests/test_orders_decoding.py
```

SQL candidate не является installed migration. Ни application DB, ни Redis,
provider, production, реальные print/export, deploy или push не использовались.
## XLSX invalid-character rule change

Отдельное явное изменение legacy behavior в `app/avito/orders_picking_xlsx.py`:
`_cell` отклоняет запрещённые XML 1.0 codepoints до создания ZIP: NUL/недопустимые
controls, surrogate range, U+FFFE/U+FFFF. Разрешённые tab/LF/CR и Unicode ranges
не очищаются и не нормализуются. ValueError содержит постоянное сообщение без
исходного текста. Это не новый renderer и не schema work.

TDD: 4 RED failures (XML parse errors/Unicode encoding error вместо predictable
rejection), затем GREEN. Старые characterization assertions повреждённого XML
заменены на acceptance безопасного отказа; исторический отчёт `f4d6d55` остаётся
доказательством предыдущего поведения. Количества/layout/headers/inline formulas
не менялись. HTTP error envelope не меняется здесь: T1 router owner должен
согласовать отображение renderer ValueError перед UI activation. Без такого
binding запрос может завершиться generic 500, но не успешным corrupt XLSX.
Rollback возможен отдельным revert этого fix; он вернёт известный corrupt-output
риск, поэтому не рекомендуется как способ продолжить печать malformed данных.
Все проверки только synthetic in-memory rendering, без physical print/export.
Combined offline regression после изменения: **234 passed, 2 прежних warnings**,
exit0. Ruff/compileall проверены для renderer и characterization file. Полный
visual XLSX/Excel layout acceptance не заявляется.

После exact T1 ready commit приоритет переключается на Orders persistence.

## Orders evidence repository / accepted dependency

Merged exact verified T1 schema `f9c7401d946063465e0576a689eb247c368eed73`
with its prerequisite lineage, no merge conflicts or manual shared-file edits.
Active0062 dependency accepted by root; не запускалась против application DB.

`app/orders/evidence_repository.py` now implements transaction-participating
order-level fact storage via parameterized SQLAlchemy Session queries. It checks
scope and current tenant context, locks run FOR UPDATE, rejects terminal/source
binding drift, creates scoped order identity, stores immutable normalized evidence
with semantic replay check, and links receipt to run membership. Same run/different
evidence is rejected. New run replay returns original persisted observation receipt.
No commit, provider, secret access, authorization helper, snapshot publication,
item projection, cancellation inference or route registration in this repository.
Caller must roll back on errors and hold fresh auth/account locks.

TDD RED missing repository import, then5 actual PostgreSQL tests PASS: rollback,
terminal/source drift, same-run changed fact/scope rejection, cross-run replay,
two simultaneous sessions/Barrier yielding one immutable fact. Fresh random
disposable DB and runtime NOSUPERUSER/NOBYPASSRLS role; reused T1 bounded fixture
with deliberately broad DML grants (tests trigger defense, not exact final ACL).
Network denied by sandbox except local Unix PG socket. Fixture verified DB/role
cleanup. No working DB table read, only maintenance metadata/create/drop own DB.
Ruff/compileall passed; DB08/revocation and full publication remain NOT_RUN.

Root fixed trusted service permission decision: user-initiated publish requires
`sync:run`; persisted reads require `cabinet:read` and live scope. These are service
constants, never request strings. Existing membership+profile union retained;
worker denied. Guard implementation is T1-owned, still awaited for service wiring.

Production schema dependency separately committed `8a8722f`:3relations with CAS,
successful receipt and immutable assignment audit; does not require renderer source.

## Sealed snapshot repository

`app/orders/snapshot_repository.py`: caller-transaction freeze/read over0062.
Before INSERT header, freeze validates complete read model and binds each row to
stored observation, account-qualified item identity, quantity, current version and
resolution. Deterministic account/external-order/source-line order; projection SHARE
locks held through caller commit. Header plus all payload rows inserted in same tx;
existing deferred DDL seals positions/count. No commits or own sessions.

Read fetches ONLY snapshot header/rows (no mutable Catalog/projection joins), checks
exact query checksum/account scope, expiry when present, position bounds, payload
versions and scoped row metadata. Returns frozen rows, high-water mark, published
time, validated account coverage/aggregate and numeric next_position. Position is
repository-only, NOT an authenticated/signed HTTP cursor or enduring permission.
No default retention lifetime invented; service activation must decide cursor policy.
Empty account scope is rejected for storage; service returns empty without header.

TDD RED missing module and separate missing coverage result assertion; GREEN3
snapshot PostgreSQL tests (historical read after current mutation, stale freeze,
query/account mismatch). Combined evidence+snapshot8PASS14.18s, fresh disposable
DBs/runtime roles; cleanup verified. Ruff/compileall exit0. Tests use T1 Unix-only
sandbox profile and bounded fixtures. Full concurrent snapshot-vs-projection race,
projection writer/CAS, authguard/DB08, API/cursor and retained-snapshot expiry gates
remain incomplete. No claim that this is already GET/api/v2/orders.

Guard design reviewed exact `1406686de74b52e1d7c92c3d9975d55b778c0cc6`:
metadata locks/atomic credential binding/session lock/final commit validation agree
with caller-owned repository transactions. Do not call a resolver with a separate
session under these locks. Guard is still a design dependency, not installed here.
Self-review retained coverage in read output and checks frozen payload against DB
identity/version rather than trusting only JSONB object shape. Projection/observation
source authority remains service responsibility; snapshot storage cannot prove it.

### Parent projection composition amendment

Root requested parent-only status/version race. Actual two-session RED reproduced
stale ready freeze after cancellation while item version stayed1. freeze now requires
`parent_versions: dict[ExternalOrderIdentity,int]` for exactly its scoped orders;
under existing parent SHARE lock compares version plus raw/canonical status and
mapping state/version with selected evidence. No observed_at ordering or version
guessing. Snapshot assembler must capture these parent versions alongside source
selection; changed parent forces conflict/retry. Historic committed snapshots stay
immutable; their read never compares against current parent.
Two real connection PIDs, Barrier/Event, parent-only cancellation and version-only
change both rejected. Combined snapshot/evidence10PASS8.89s, disposablecleanup
verified. Ruff import-order corrected before commit. This closes the stale-parent
storage gate, not yet authoritative source/high-watermark selection in service.
Known0062 long-key B-tree defect remains separate T1 amendment prerequisite; no
arbitrary cap or hash-as-identity introduced in domain.

## Parent projection CAS primitive

`app/orders/projection_repository.py` set_parent(run_id,observation_id,expected_version)
uses the caller transaction/tenant context, staging-run FOR UPDATE, exact scoped
membership, stored observation decoder/checksum/source binding and SQL
`UPDATE ... WHERE org/account/order/version ... RETURNING version`.
Updates raw/canonical/mapping fields, effective source time and last-seen run;
no observed_at ordering, no provider/raw body, no own commit or session.

This is a repository primitive, NOT a source progression decision: trusted service
must classify replay/out-of-order/reconciliation before calling it, authorize under
T1 guard and atomically commit all publication effects. Calling this primitive for
an arbitrary older fact would be misuse; it does not claim automatic lifecycle
monotonicity. No route calls it. Item projections/status-history/coverage/final-run
publication remain separate unfinished service work.

TDD RED missing module ->3PGGREEN including two real sessions competing for one
parent version (one winner/one conflict); combined evidence/snapshot/CAS13PASS16.22s.
Added caller-rollback regression: focused4PGPASS5.34s. Fresh random disposable DB,
runtime role and cleanup verified, Unix-only sandbox. Ruff/compileall exit0.
Self-review checked exact scoped joins and that incoming request cannot override
stored status. Full auth/revocation/source-progression/long-key gates not claimed.

## Exact-key repository preparation

T1 approved design `87ef04884e5636dbed704ee3f54f2e95fb9959a7` removes raw TEXT
arbiters in forthcoming0064. Evidence append now rejects RR/SERIALIZABLE, locks
the scoped account before run/domain locks, then performs fresh C-collated exact
order/evidence lookup and insert-if-absent. Semantic replay verification and
bounded membership ON CONFLICT remain; no hash identity or length cap.

RED: two isolation cases DID NOT RAISE on old code. GREEN: eight evidence tests,
including two actual sessions with pg_blocking_pids proving account-lock wait;
the waiter establishes a snapshot before blocking and sees the winner's newly
committed exact fact. Final evidence/parent/snapshot regression17PASS9.67s on0062,
own disposable DB/role cleanup verified. Ruff (backend cwd) and compileall exit0.
Manual critic: account lock is serialization, not authorization; caller still
needs T1 shared guard before entering, and must not hold domain locks first.
Actual0064 migration/long-key gate remains NOT_RUN until T1 delivers its exact SHA.
No schema, shared auth, routes, providers, production or frontend changed.

## Item projection primitive

`OrdersProjectionRepository.set_item(run,observation,line,resolution,expected_version)`
uses the same decoded scoped order-level membership as parent CAS. Shared account
lock precedes run/item locks under RC. None means insert only if absent; explicit
version requires CAS. Stored line identity/quantity/effective time cannot be
overridden by request. Repeated listings retain distinct explicit occurrence keys.
Identity drift fails; no physical deletion or inferred absent-item cancellation.
Catalog IDs remain references with account-scoped Product/Offer FKs; resolution is
an explicit trusted caller decision, not title matching. No readiness field written.

RED2 missing set_item -> GREEN; final parent/item/evidence/snapshot21PASS9.03s,
including two actual sessions/PIDs competing for item version (one winner, one
conflict), quantity3->5, repeated lines, missing line, rollback, and same-org other
account Product rejection. Cleanup verified, Ruff/compileall/diff exit0.
Manual critic: not an operator assignment endpoint; manual override commands still
require Production CAS/idempotency/audit service. No-op replay, out-of-order source
selection and atomic status/coverage/run publication remain service obligations.
Long-key acceptance still waits exact0064 and its PG gate; no original0062 changes.

## Actual0064 consumer acceptance

Exact T1 implementation `0dbb85d8ccda4d528b4fc9b37d539a6e664cbabf` and test correction
`d44c971148ab1e5d185adcc079c8d2ab9aced813` merged with prerequisite lineage in
`2d9a40059f39ecf2b1b2d4f7123d8ff749e2126c`, no conflicts or manual shared-file edits.
The earlier long-key NOT_RUN entries above are historical; this gate is now PASS.

All three repository suites now use actual0064 pinned disposable fixtures. New
consumer tests retain >4096-byte synthetic order/adapter/line values exactly,
replay without changed IDs, create a new observation for changed evidence, keep
same external ID in two accounts distinct, and roll back order/item/evidence
together. The existing physical account-wait test now runs with short and long
keys; both sessions have established snapshots before the waiter is released.
A separate latest-head fixture applies the actual runtime role script and verifies
narrow Orders privileges before evidence replay and parent/item projection calls.
No latest-head assertion is baked into the historical0064 fixture.

Fresh combined command (same sanitized Unix-only prefix documented above):
`python -m pytest -q -s --tb=short tests/test_orders_exact_repositories.py tests/test_orders_evidence_repository.py tests/test_orders_projection_repository.py tests/test_orders_snapshot_repository.py tests/test_orders_exact_text_migration.py`
Result: **106 passed in37.92s**, exit0, no skips; 26 consumer cases plus80 migration
cases. All own disposable DB/role cleanup assertions passed. Ruff over app/orders
and four consumer files, compileall, diff check and git fsck --no-dangling exit0.
Self-review read actual171-line migration and checked account-before-domain locks,
C-comparison predicates, bounded membership arbiter and scope preservation.
This closes the0064 repository compatibility dependency, NOT publication/auth,
complete source coverage, worker authority, Production parity or application activation.

## Guarded persisted read service

Consumed T1 paired-fetch `7bfb631d30426dd39a4f4dae7aab4754155b6a62`, guard0900f8e
and mandatory finalizer fix `4860c53df7e12543c7f8afb7569ada773bea37d3` by clean merge.
`read_orders_snapshot` owns a fresh root transaction on the supplied unused Session,
uses fixed cabinet:read and no credential authority, delegates to immutable snapshot
read, then returns only after revalidation and guarded Session commit succeeds.
Does not commit a caller's existing transaction. Physical SQLAlchemy COMMIT errors
are sanitized. Principal must come from authenticated session/canonical membership;
the passed principal object is not authentication. Exact account bindings and live
scope are checked on every page. Current T1 guard requires connected accounts;
no active marketplace credential is required to read stored facts.

RED missing module; fresh GREEN34PASS15.94s: eight read-service cases plus26
repository cases. Covers no-credential read, Session reuse, membership/permission/
scope/logout revocation between pages, final-commit mutation rejection/rollback,
and actual two-session logout lock wait (distinct PIDs, pg_blocking_pids observed).
Own disposable cleanup verified, Ruff/compileall exit0. Self-review corrected the
snapshot ID annotation to int and confirmed result cannot escape before commit.
Not an HTTP route/signed cursor/authentication adapter; no provider/business-state
write, worker authority, current queue activation or Production parity claimed.
