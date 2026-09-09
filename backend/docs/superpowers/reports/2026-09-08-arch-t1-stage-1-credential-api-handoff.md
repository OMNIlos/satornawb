# Satorna Architecture Wave: Terminal 1 Stage 1 handoff

Date: 2026-09-08. Base: `c88a474695569af905b294906ba604d61f3de62f`.
Branch: `codex/arch-t1-platform`.

This slice adds the authenticated account-owned API boundary over the existing
Wave 1 crypto, persistence, forced-RLS and credential-store contracts. It does
not switch a provider consumer, implement a legacy fallback, mount a keyring,
run a backfill, enable a flag or change deployment.

## Baseline and lineage

- Git started clean at the exact requested base.
- Alembic has one head: `20260908_0061`.
- The four Wave 1 contracts are present: marketplace credentials,
  `PriceApprovalSnapshot`, `ExternalOrderIdentity` and `ExternalReviewIdentity`.
- `20260717_0019` uses `ADD COLUMN IF NOT EXISTS`, validates the resulting
  schema, and does not remove the `ai_prompt` column on its own downgrade.
- The repository's release/contract entry points remain
  `backend/ops/release_gate.py`, `backend/contracts/openapi/v1.yaml` and
  `backend/product-docs/contracts/openapi/v1.yaml`. This slice does not
  regenerate either OpenAPI artifact because no frontend consumer is switched.
- The inherited full-backend baseline is `883 passed / 105 failed`; its exact
  failure IDs were unchanged from the preceding integration run. Those known
  failures and the post-summary shutdown hang remain release-infrastructure
  debt, not an allowlist to expand.
- On this slice, the final full JUnit contains 999 tests: `894 passed / 105
  failed / 0 errors / 0 skipped` in 297.468 seconds. The 105 failure IDs match
  `ops/legacy-test-failures.txt` exactly (`added=0`, `missing=0`). Pytest again
  hung in its known background-thread shutdown after writing the summary and
  JUnit; only that exact test process was stopped with SIGINT.

## Shared-file ownership manifest

| Surface | Owner for this architecture wave |
|---|---|
| `backend/alembic/**`, shared configuration, router/task registration, runtime grants, Docker/CI/dependencies, common handoff and final integration branch | Terminal 1 |
| `backend/app/repricer_tasks.py` and repricer domain implementation | Terminal 2 |
| `backend/app/avito/orders.py` and Avito order-domain implementation | Terminal 3 |
| `backend/app/review_tasks.py`, frontend and serverless | Terminal 4 |
| `backend/app/routers/avito_orders.py` during credential/token cutover | Terminal 1 |

Terminals 2–4 submit committed schema requests to Terminal 1. Each request must
state tables, columns/types, foreign keys, unique/check/index requirements, RLS,
backfill semantics and downgrade guards. Terminal 1 serializes migration
revisions; domain owners do not edit shared migrations concurrently.

2026-09-09 scoped delegation amendment, explicitly authorized by the integration
coordinator to unblock parallel source implementation (not Stage1 verification):

- T2 temporarily owned ONLY the paired-fetch core/dedicated executor callable in
  `backend/app/platform/integrations/credential_store.py` and new
  `2026-09-09-t1-executor-credential-resolver-handoff.md`. Delivered
  `00961055428365f83d7dd05bd07f46786709c975`, imported unchanged with provenance as
  `b70f2d2afdd545005b59b65d7a40c66595b4bfcd`; ownership returned T1.
- T4 temporarily owned ONLY the additive verified OAuth method in
  `backend/app/avito/auth.py`, new `backend/app/avito/credential_exchange.py` and
  new `2026-09-09-t4-avito-account-oauth-adapter-handoff.md`. Delivered
  `d1fd534f53b879f1e741d39b13c6ce76fdad5e2f`, imported unchanged with provenance as
  `564515291612520e3ba5d585e870a37355c90e0b`; ownership returned T1. Existing legacy
  methods and consumers are unchanged.
- T2 temporarily owned ONLY safe error/diagnostic fields in
  `backend/app/avito/chats.py`, `backend/app/avito/stats.py` and its dedicated
  `2026-09-09-t2-avito-safe-diagnostics-handoff.md`. Delivered
  `1213202030039af60aa63e111e2f1de43d9b7e06`, imported unchanged as
  `dad6b661efd5844f68d6085c93e6b2662f4fbc32`; ownership returned T1. Business
  payloads/pagination remain separate from redacted diagnostics; no blanket
  claim that every non-HTTP Avito action error is now covered.
- T2 temporarily owned ONLY the ordinary put/revoke/status/resolve transaction
  core in `backend/app/platform/integrations/credential_store.py` and
  `2026-09-09-t1-credential-transaction-core-handoff.md`. Source chain
  `874782ddeed534e4f4bfd9024037853fb5197ac4`,
  `e2d51a5c9482733eb4e50a0dd47addb010280440`,
  `fb2ae0ec686aa59a2c8e69dc3fdf96dca753ee42` imported unchanged respectively as
  `944c6ed31362471fd9c7b93adc09d8dc5bd3c36b`,
  `827620abaa5b83ad169391611db5684c277a1917`,
  `742c83f690272344427de7f02d2fcfca756e8689`; ownership returned T1. The final
  follow-up preserves public post-query expiry-clock ordering. Private helpers
  are transaction participants, not authentication; paired fetch/executor/rekey
  and existing public signatures were outside this delegation.
- T4 now temporarily owns ONLY the existing canonical credential-management
  composition under committed plan `2026-09-09-credential-management-commit-fence.md`,
  with exact prerequisite `b21f2166886ade7637b1b9594b5b28c1e38d3e80`: new
  `backend/app/platform/integrations/credential_management.py`, fixed management
  root support only in `publication_guard.py`, only the three canonical exact-account
  credential routes/helpers/imports in `backend/app/routers/cabinet.py`, and new
  `2026-09-09-t1-credential-management-handoff.md`. T1 will not edit these four
  paths until the bounded source package returns. Store, schema, grants, config,
  legacy routes and domain consumers are excluded. T1's daily stock/evidence
  schema package touches only a new migration, runtime grants and its own handoff.
  This temporary assignment implements the explicit independent-work redistribution
  request; it does not transfer standing shared-auth ownership or acceptance.

All these source packages are IMPLEMENTED / UNVERIFIED under the user's source-first
sequence. No new tests/review/compile/import/PG gates, operational role/flag/key or
provider actions were performed for these imports. This does not broaden domain
owners' standing rights over store writers, schema, shared guard/config/grants,
routers, other Avito consumers or deployment. T1 retains serialized shared schema
and authority; the separate coordinator owns final integration/admission.

## Account-owned credential API

The registered path is:

```text
/api/v1/cabinet/marketplace-accounts/{marketplaceAccountId}/credentials/{provider}/{credentialKind}
```

- `GET` returns only `marketplaceAccountId`, `status` and lifecycle timestamps.
- `PUT` creates or replaces an encrypted credential and returns the same
  redacted status contract.
- `DELETE` revokes the active credential; `reasonCode` is constrained by the
  store allowlist.
- Every operation requires an authenticated actor, effective
  `integrations:write`, an active organization membership whose current role
  or explicit permissions still grant `integrations:write`, and access to the
  exact account. This closes the stale access-token downgrade window.
  Organization, account and canonical provider are checked in the database
  under tenant context.
- User-managed kinds are exactly `wb/wb_api` (`wbToken`) and
  `avito/avito_oauth_client` (`clientId`, `clientSecret`). The derived
  `avito_oauth_access` kind is not writable or observable through this API.
- WB writes call the existing seller-info identity verifier. The verified
  seller UUID must equal the canonical account external ID, and that ID is
  checked again under the account-row lock before persistence.
- Avito writes require the explicit path account. No account is inferred from
  a title, client ID, organization account count, insertion time or “latest”
  credential.
- New writes are encrypted-only. Legacy plaintext rows are not read, written,
  cleared or updated by these operations.
- Keyring readiness is checked before WB seller-info verification, so a
  disabled or misconfigured encrypted store cannot send an unusable credential
  to the provider.
- Active status is authenticated by a real decrypt. Corrupt ciphertext,
  expiry, a missing key/keyring or database failure returns a typed safe error;
  it never calls a legacy reader. Revoked rows remain redacted metadata.
- Pydantic secret types, root-level rejection of unknown credential-body keys
  and the global validation-error sanitizer keep request values, unknown keys
  and validator context out of 422 responses. Credential API responses exclude
  credential UUID and generation. Audit events use the credential UUID as
  `object_id` and include safe `generation` metadata alongside credential kind,
  account ID, operation, provider and result code. Neither surface contains
  secret payloads, ciphertext, nonce, verifier, raw exception text or key inventory.

The main safe API codes are `NO_ACCESS`, `MEMBERSHIP_INACTIVE`,
`ACCOUNT_SCOPE_DENIED`, `MARKETPLACE_ACCOUNT_NOT_FOUND`,
`MARKETPLACE_ACCOUNT_PROVIDER_MISMATCH`, `CREDENTIAL_KIND_UNSUPPORTED`,
`CREDENTIAL_PAYLOAD_INVALID`, `WB_CREDENTIAL_IDENTITY_INVALID`,
`WB_SELLER_IDENTITY_MISMATCH`, `credential_missing`, `credential_expired`,
`credential_auth_failed`, `credential_configuration_invalid`,
`credential_key_unavailable`, `credential_payload_invalid`,
`credential_contract_invalid`, `credential_account_not_found`,
`credential_account_identity_mismatch`, `credential_concurrent_update`,
`credential_reason_invalid` and `credential_persistence_failed`. Callers must
branch on the code and must not surface caught exception text.

## Resolver contract for Terminals 2–4

Import only the boundary types/functions:

```python
from app.platform.integrations.credential_store import (
    CredentialStoreError,
    MarketplaceAccountCredentialOwner,
    resolve_marketplace_credential,
)
from app.security.marketplace_credentials import CredentialCryptoError
```

Construct the owner from already-authorized canonical IDs:

```python
owner = MarketplaceAccountCredentialOwner(
    organization_id=organization_id,
    marketplace_account_id=marketplace_account_id,
    provider=provider,
)
credential = resolve_marketplace_credential(owner, credential_kind)
```

Kinds and decrypted payload shapes are fixed:

| Provider/kind | Payload fields | Intended owner |
|---|---|---|
| `wb/wb_api` | `token` | exact canonical WB account |
| `avito/avito_oauth_client` | `clientId`, `clientSecret` | exact canonical Avito account |
| `avito/avito_oauth_access` | `accessToken`, `expiresAt` | exact canonical Avito account; derived worker credential only |

Worker requirements for later consumer slices:

1. Celery arguments, retries and result values carry organization/account/job
   IDs only—never a credential, decrypted payload or bearer.
2. Establish tenant context and authorize the exact canonical account before
   resolution. Resolve immediately before the provider call.
3. Keep `DecryptedCredential` wrapped. Call `reveal()` only at the adapter
   boundary and do not attach its result to logs, errors, audit, caches, task
   metadata or API responses.
4. Treat all `CredentialStoreError` and `CredentialCryptoError` codes as
   fail-closed. Corrupt, expired or revoked credentials, storage errors and
   unavailable keys must not enter a plaintext/default/memory fallback.
5. Do not instantiate ORM credential rows in domain code and do not select a
   credential by user, organization-only query, title, account count, newest
   timestamp or `credential_ref` convention.

No explicit migration-mode fallback exists in this slice. A later compatible
legacy reader, if approved, must be centralized behind this boundary, run only
when no encrypted row exists, and never run after an encrypted-row error.

## Rollout state and blockers

- All existing WB/Avito consumers and legacy cabinet endpoints retain their
  prior behavior. No consumer uses the new writer or resolver yet.
- `VELLA_MARKETPLACE_CREDENTIALS_ENABLED` remains default-off. No key directory,
  key version or key material was added to Git or deployment configuration.
- No Alembic revision or runtime grant is needed for this API-only slice; the
  existing `0061` forced-RLS schema is unchanged.
- Before Stage 2, the infrastructure owner must approve production extension
  token TTL, abuse/rate limits, extension request-body limit and mixed-version
  Celery queue drain policy. No values are invented here.
- Before any rollout, the infrastructure owner must provide the external
  read-only key mount and minimum role placement described by the approved
  encryption design. API/required workers may receive it; beat/migrate must not.
- Backfill mapping evidence, old/new key overlap, production rotation, cleanup
  and all real provider canaries remain separate, explicitly authorized stages.

GitHub, production databases/Redis, real credentials and external review
services were not used. During an early regression command, an existing Avito
orders test unexpectedly attempted one read-only `accounts/self` request with a
synthetic bearer and received HTTP 403; it sent no message or price mutation.
Subsequent regression commands use a scrubbed environment, fake provider modes
and loopback-only HTTP proxies.
