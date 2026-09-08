# Architecture integration acceptance

User scope: finish all assigned T1–T4 work, independently check and correct it,
audit omissions, then publish the verified result to `OMNIlos/satornawb:filipp`.
Publication is conditional on correctness. This checklist does not authorize
production rollout, real provider actions, or replacement of missing evidence.

## Execution

1. Accept immutable ready commits from each owner; verify prerequisites before
   releasing dependent repository/API work. Do not merge active working files.
2. Implement and verify each independent domain slice without waiting for
   unrelated external policy or source gaps.
3. Integrate owner commits on the existing `filipp` lineage, resolve overlaps,
   and repeat tests against the combined tree.
4. Independently review the complete requirement matrix and critical races.
5. Fetch `filipp` again, preserve intervening changes, rerun affected checks,
   and push normally only after acceptance. Verify the remote commit.

## Required acceptance evidence

| Area | Owner | Gate |
| --- | --- | --- |
| Credentials/context | T1 | Account-owned HTTP/worker binding, IDs-only queues, revoke/commit fencing, fail-closed credential resolution |
| Platform operation | T1 | Safe rotation/backfill/restore, migration bootstrap, runtime grants, installed packages, CI and bounded health checks |
| Repricer persistence | T2/T1 | Durable approval/attempt/audit, atomic CAS, two-session contention, dispatch/crash/replay matrix, no memory fallback |
| Settings/calculation | T2 | Versioned domain rows and immutable inputs, concurrent update preservation, exact-kopek characterization, single writer |
| Prices/stocks | T2 | Account/grain isolation, complete manifests, atomic publication, revisions/replay and partial-run preservation |
| Financial evidence | T2 | Proven KTR/source policy and explicit financial decisions; unapproved or missing evidence remains null with a blocker |
| Orders | T3/T1 | Actual schema/RLS, immutable observations, complete publication, revoke fencing, stable authorized snapshot pagination |
| Fulfillment | T3 | Proven source identity/readiness/deadlines; Statistics observations do not establish fulfillment eligibility |
| Production | T3/T1 | Work-item quantities, authenticated CAS/idempotency/audit, versioned grouping, immutable historical sheets |
| Production renderers | T3 | Separate required XLSX/A4/sticker parity, frozen inputs, checksums, restart/concurrency and authorized downloads |
| Reviews | T4/T1 | Persisted facts/policy/drafts/approvals, account isolation, atomic heads/audit, durable dispatch and ambiguous recovery |
| Notifications | T4/T1 | Transactional events/outbox, membership receipts/preferences, read-only GET, verified external delivery contracts |
| Frontend | T4 | Real typed API consumers, scoped queries, validation/error/409 UX, exclusive route ownership and feature gates |
| Release | All/root | Full backend/frontend suites, natural exit, typecheck/build, migration/restore and integrated concurrency checks |

## Evidence rules

- Owner test reports and independent verification are recorded separately with
  exact commit, command, outcome and limitations.
- A protocol, schema, serializer or fake-renderer test alone does not establish
  a working repository, mounted API, production delivery or artifact parity.
- Baseline failures require classification and correction where in scope;
  passing a selected subset is not the full release gate.
- Missing source code and financial decisions remain explicit unresolved gates.
  Do not reconstruct historical parity or choose business rules silently.
- Local test infrastructure uses disposable synthetic databases and fixtures;
  it must not inspect operational records or execute real marketplace actions.

## Initial independent evidence

- T1 `94381860a34632783fd1f75ab5aa51083f749597`: documented safe subset
  independently reproduced on a detached tree with network denied: 265 passed,
  six existing warnings, natural exit 0. This excludes actual PostgreSQL gates.
- T3 `f013dec2c0c17ba71e8905d334d41e829049d8c6` including serializer and
  strict decoder predecessors: 234 passed, two dependency warnings, Ruff passed
  on a detached tree. No blocking finding in the bounded independent review.
  Persistence/publication and HTTP renderer-error mapping remain separate work.

No whole-architecture acceptance or GitHub publication is claimed here.

## Scope correction and prerequisite verification

T3 relayed a newer direct user instruction excluding KIZ and the standalone
matcher from the requested product. Remove their isolated additions and exposed
placeholders only after checking dependencies; preserve core WB/Avito workflows,
Catalog resolution and Avito return matching. Historical evidence, backups and
operational data are not cleanup targets. Production itself remains in scope.

Orders schema `f9c7401d946063465e0576a689eb247c368eed73` independently passed
101 tests on fresh disposable PostgreSQL databases with restricted runtime roles,
including migration, RLS, contention, ACL and rollback checks (145.64 seconds,
natural exit 0). Network was denied except the local Unix PostgreSQL socket.
Independent DDL/ACL/Catalog review found no blocker. This releases the schema
prerequisite to T3; application authorization/publication and actual repository
and API acceptance are still required. Formatting-only lint followup is pending.
