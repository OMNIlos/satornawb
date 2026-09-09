# T1 user/session publication guard handoff

Date: 2026-09-09. Task 2 on `codex/arch-t1-platform`; consumes paired fetch
`7bfb631d30426dd39a4f4dae7aab4754155b6a62`. No current consumer, writer, router,
schema, migration, permission profile or `infra/db.py` changes.

## Caller interface

All exports come from `app.platform.integrations.publication_guard`:

```python
UserSessionPrincipal(organization_id, user_id, membership_id, session_id)
ExpectedAccountBinding(marketplace_account_id, provider, external_account_id, credential_ref)
ExpectedCredential(marketplace_account_id, credential_id, kind, generation,
                   payload_schema_version, expires_at)
ExpectedIngestionToken(marketplace_account_id, token_id, scope, expires_at)
acquire_publication_guard(session, *, principal, required_permissions,
                          accounts, authorities) -> PublicationGuard
PublicationGuard.revalidate_before_write() -> datetime
```

Expectation classes are frozen, slotted and do not print their fields. IDs are
strict positive PostgreSQL INTEGER-compatible ints (generation is BIGINT), never
bool/coerced strings. User/session IDs are nonempty schema-bounded text, not UUIDs.
Credential/token UUIDs are UUID objects. Provider/kind/schema/expiry/ref metadata
are strict; `credential_ref=None` means exact NULL. Duplicate or contradictory
bindings fail closed; multiple distinct token UUIDs can be fenced for one account.

The trusted service captures principal from authenticated ActorContext plus the
exact canonical membership before fetch. The principal itself authenticates no
one. Permissions are nonempty frozensets from trusted service constants, never
client, HTTP or queue fields. Membership explicit permissions UNION the existing
`permissions_from_profile(membership.role)` decides access; stale ActorContext
permissions and the user's old profile cannot override live membership. Scope
supports all/selected/restricted; restricted account lists preserve positive int
and ASCII decimal-string IDs, including leading zeros. Malformed scope JSON denies.

Convert paired fetch `.binding` explicitly:

```python
binding = fetched.binding
identity = binding.credential_identity
account = ExpectedAccountBinding(
    binding.owner.marketplace_account_id, binding.owner.provider,
    binding.external_account_id, binding.credential_ref,
)
authority = ExpectedCredential(
    identity.marketplace_account_id, identity.credential_id,
    identity.credential_kind, identity.generation,
    identity.payload_schema_version, identity.expires_at,
)
# Provider work finishes before entering this transaction.
with Session(runtime_engine) as session, session.begin():
    guard = acquire_publication_guard(
        session, principal=principal, required_permissions=frozenset({"sync:run"}),
        accounts=(account,), authorities=(authority,),
    )
    lock_domain_run(session)
    guard.revalidate_before_write()
    write_domain_publication_and_audit(session)
    # Session.commit / context exit flushes and validates again automatically.
```

Every fetch credential/token must be declared by the consuming service. Empty
authorities expressly mean a trusted credential-independent operation, including
persisted `cabinet:read` or local `reviews:approve` work. The guard cannot infer an
unreported fetch. Orders must forbid omission on fetched publication paths and
use fixed `sync:run`; this is a caller obligation, not a new grants policy.
Guard idempotent replay returns and persisted cursor reads too: prior output is
not enduring authorization. Domain writes/audit must use this same root transaction.

## Transaction and error contract

Require a clean existing active root Session transaction on PostgreSQL READ
COMMITTED, no pending new/dirty/deleted objects, no SAVEPOINT, one guard per root.
The module creates no session, decrypts nothing and calls no resolver or provider.
Only explicit safe metadata columns are selected, avoiding stale identity-map data.

Locks are user SHARE, membership SHARE, login session SHARE, exact accounts UPDATE
ascending, exact credentials SHARE sorted(account, kind, UUID), tokens SHARE
sorted(account, UUID), then caller domain locks. Fresh user/org/activity,
membership/org/user/permission/scope, session/user/revoke/expiry and every exact
account and authority expectation are checked. No latest-row substitution.

Database `clock_timestamp()` is sampled after all lock waits. The Session-specific
`before_commit` hook checks context, explicitly flushes, then performs the complete
fresh metadata/context/time validation again. Omitted caller rechecks and mutations
flushed in the same transaction cannot bypass this final check. Failure poisons the
handle until caller rollback. Nested transaction attempts also poison the root.

Three constant callbacks are installed once per guarded Session. They hold no
captured Session/root state and never modify listeners during event dispatch.
Root completion/rollback invalidates the handle and clears active state; reused
Sessions/pool connections have no stale authorization and listeners do not grow.
Sessions that never acquire a guard receive no hooks. Both tenant marker and actual
PostgreSQL tenant/isolation settings are validated through commit.

`PublicationGuardError` exposes only `publication_context_invalid`,
`publication_access_denied`, `publication_binding_changed`,
`publication_authority_invalid`, `publication_expired`, or
`publication_persistence_failed`. Unknown codes normalize to the last code.
Acquisition, revalidation and final-flush SQLAlchemy failures are sanitized without
SQL/input/secret reflection. The caller still owns rollback and physical COMMIT
driver errors (outside the hook); do not reflect raw database exceptions in HTTP.

## Verification and limits

Missing-API RED was observed before implementation in both contract and real
PostgreSQL tests. Additional self-review RED reproduced malformed tenant markers,
leading-zero scope compatibility and multiple distinct same-account tokens; fixed
and rerun. Exact commands, counts and allocated-resource cleanup are in the local
task execution report `.superpowers/sdd/2026-09-09-publication-guard/task-2-report.md`.
Final focused plus paired-fetch/crypto/store/WB binding run: **245 passed in
14.00s**, exit 0. Three-file Ruff and compileall pass, exit 0.

PostgreSQL coverage includes both lock winner orders for user deactivation/org
change, membership revocation/permission/scope change, session revoke, account
disconnect/rebind/ref change, credential revoke/generation and token revoke.
Actual existing credential replace/revoke/reencrypt and ingestion rotate/revoke
writers run in both winner orders. Expiry is exercised during account, membership,
domain and final-flush lock waits, plus expiring Avito credentials and tokens.
Synthetic publication plus audit proofs commit together or leave zero rows;
deferred constraint failure also proves physical COMMIT rollback. Stale ORM,
exact UUID/generation/ref/expiry, permission union, tenant changes during flush,
listener reuse and credential-independent reads are covered.

Tests/app use only the worktree `backend/.venv`, scrubbed environment and the
existing OS sandbox denying IP networking and secret reads. Actual PostgreSQL is
only a fresh random disposable database/runtime role through the authorized local
Unix socket; migrations stop at 0061. Existing helper cleanup verifies exact absence.
The approved alternate Python is used for Ruff only. Existing PostgreSQL `/dev/null`
password-file warnings remain disclosed; output is not claimed pristine.

No production activation, provider/Redis/network work, current consumers, worker
or delegated-job principal, bearer-only authentication, access-token-expiry claim,
permission expansion, historical A→B→A binding epoch, whole application suite or
other writers' universal lock-order proof. Validation proves expiry at the final
database validation instant, not frozen wall-clock time until physical COMMIT.
Requested local preflight-critic was unavailable; an isolated self-review pass
covered spec/source/races/error/lifecycle checks. Controller independent review is
required before this handoff is accepted or wired by domain owners.
