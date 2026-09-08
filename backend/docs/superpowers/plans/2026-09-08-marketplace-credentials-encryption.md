# Marketplace Credentials Encryption Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Перенести WB, Avito и extension credentials в account-owned защищённое хранение без plaintext writer и без утечки через runtime surfaces.

**Architecture:** Provider credentials шифруются application-layer AES-256-GCM и принадлежат `MarketplaceAccount`; versioned master keys монтируются с host read-only только в API и нужные workers. Extension bearer хранится как account-scoped one-way verifier. Миграция additive и проходит encrypted-only write, dual-read/backfill, verify, encrypted-only switch и отдельный cleanup.

**Tech Stack:** Python 3.11 container/runtime, FastAPI, SQLAlchemy 2, PostgreSQL 16 forced RLS, Alembic, Celery/Redis, `cryptography` AESGCM, Docker Compose.

**Spec:** `backend/docs/superpowers/specs/2026-09-08-marketplace-credentials-encryption-design.md`

## Global Constraints

- Не читать, печатать, экспортировать или логировать реальные credential values; fixtures только синтетические.
- Не писать собственную cryptography и не использовать auth/session secret как encryption key.
- Master key не хранится в DB, repo, image, environment, logs или application backups.
- Writer encrypted-only с первой совместимой версии; invalid encrypted row никогда не вызывает plaintext fallback.
- Celery args/results, logs, errors, audit, API и generic caches не содержат secrets/ciphertext/verifiers.
- Production/GitHub/external services не используются при реализации до отдельного разрешённого rollout.
- Исходный architecture design отсутствует; owner gate из spec обязателен до implementation approval.

## File map

- Create `backend/app/security/marketplace_credentials.py`: crypto types, AAD/payload codecs, keyring loader, redacted secret values.
- Create `backend/app/platform/integrations/credential_store.py`: account-scoped put/resolve/revoke/reencrypt boundary.
- Create `backend/app/platform/integrations/ingestion_tokens.py`: scoped extension-token issue/verify/revoke.
- Modify `backend/app/platform/integrations/orm.py`: encrypted credential и ingestion-token ORM rows.
- Create `backend/alembic/versions/20260908_0061_marketplace_credentials.py`: additive tables, constraints, forced RLS, explicit grants.
- Modify cabinet/WB/Avito adapters and routers: account IDs, encrypted writes/reads, safe permissions/errors.
- Modify Celery/background call sites: only IDs in queued arguments and safe results.
- Create `backend/scripts/backfill_marketplace_credentials.py`: one-shot idempotent mapped backfill and verification modes.
- Modify Compose/ops templates: read-only key mounts for explicit services and separate backfill role/runbook; no key material.
- Add focused crypto, persistence, RLS, API, task-leakage, migration and rollback tests.

---

### Task 1: Pure crypto contract and secret-safe types

**Files:**
- Create: `backend/app/security/__init__.py`
- Create: `backend/app/security/marketplace_credentials.py`
- Test: `backend/tests/test_marketplace_credential_crypto.py`
- Modify: `backend/pyproject.toml`

**Interfaces:**
- Produces: `CredentialIdentity`, `EncryptedCredential`, `DecryptedCredential`, `CredentialKeyring`, `encrypt_credential(...)`, `decrypt_credential(...)`, typed non-secret exceptions.
- Consumes: 32-byte keys supplied by a mapping `key_version -> bytes`; no global settings lookup inside the pure functions.

- [ ] **Step 1: Write failing crypto-contract tests**

Cover round-trip for all three payload schemas; exact 12-byte nonce and 16-byte tag semantics; changed algorithm/keyVersion/credential ID/generation/organization/account/provider/kind/payload version/expiry; mutated nonce/ciphertext/tag; unknown versions; invalid lengths/UTF-8/schema/size; and redacted `repr`, `str`, exception text. Patch the nonce source in the test to prove the same plaintext produces different ciphertext with distinct nonces.

- [ ] **Step 2: Run the failing test**

Run: `cd backend && pytest -q tests/test_marketplace_credential_crypto.py`

Expected: FAIL because the security module and dependency do not exist.

- [ ] **Step 3: Add the reviewed dependency and exact interfaces**

Add an owner-approved bounded `cryptography` dependency compatible with Python 3.11 and record the resolved lock/image version. Add `app.security` to package configuration. Implement AESGCM only through that library. Encode AAD with unambiguous length-prefixes in the exact spec order. Enforce an allowlist of `(provider, kind, payload_schema_version)`, strict key/nonce/ciphertext sizes and fail-closed typed error codes. The keyring loader accepts a directory and version names but never logs file content or path on an error exposed to API clients.

- [ ] **Step 4: Run focused tests and secret scan**

Run: `cd backend && pytest -q tests/test_marketplace_credential_crypto.py`

Expected: PASS.

Run a test that captures logging and exception serialization with unique synthetic canaries; expected count outside the test input fixture: zero.

- [ ] **Step 5: Commit**

Commit only the module, dependency metadata and focused tests with message `feat: add marketplace credential crypto contract`.

### Task 2: Add account-owned persistence and forced RLS

**Files:**
- Modify: `backend/app/platform/integrations/orm.py`
- Create: `backend/alembic/versions/20260908_0061_marketplace_credentials.py`
- Modify: `backend/ops/runtime-db-role.sql`
- Test: `backend/tests/test_marketplace_credential_migration.py`
- Test: `backend/tests/test_marketplace_credential_rls.py`

**Interfaces:**
- Produces: `MarketplaceAccountCredentialRow`, `MarketplaceAccountIngestionTokenRow` with the exact schema/constraints from the spec.
- Consumes: existing `(organization_id, marketplace_account_id)` account unique key; extends it to include provider for a composite FK.

- [ ] **Step 1: Write failing metadata and PostgreSQL RLS tests**

Assert every required column/check/index, one-active-per-kind partial unique, composite tenant/account/provider FK, access-token expiry rule, forced RLS, cross-tenant denials and no-context denials. Assert migrate/beat have no key mount/decrypt capability; if owner approves split DB logins, additionally assert beat cannot select the credential table.

- [ ] **Step 2: Run tests against a disposable PostgreSQL database**

Run: `cd backend && pytest -q tests/test_marketplace_credential_migration.py tests/test_marketplace_credential_rls.py`

Expected: FAIL because models/tables/policies are absent.

- [ ] **Step 3: Implement additive schema only**

Create both tables without altering/deleting legacy plaintext. Add constraints exactly as the spec, enable and force RLS. With the current shared runtime login, accept tenant-scoped ciphertext visibility but separate key mounts; if owner approves split logins, revoke inherited broad grants and add explicit API/worker grants. The downgrade may remove new empty/additive objects but must never recreate or populate plaintext data after cleanup in a later revision.

- [ ] **Step 4: Verify migration cycle**

Run upgrade on empty DB and production-shaped disposable clone, downgrade this additive revision, then upgrade again. Run the tests from Step 2.

Expected: all commands exit 0; tenant/account/provider mismatch is rejected by PostgreSQL.

- [ ] **Step 5: Commit**

Commit models, additive migration, role template and tests with message `feat: add account-owned credential storage`.

### Task 3: Implement the only credential store boundary

**Files:**
- Create: `backend/app/platform/integrations/credential_store.py`
- Modify: `backend/app/config.py`
- Test: `backend/tests/test_marketplace_credential_store.py`

**Interfaces:**
- Produces: `put_marketplace_credential(identity, kind, plaintext)`, `resolve_marketplace_credential(identity, kind)`, `revoke_marketplace_credential(identity, kind, reason_code)`, `reencrypt_credential(credential_id, expected_generation, target_key_version)`.
- Consumes: Task 1 crypto contract and Task 2 rows. Returns redacted values/metadata, never ORM ciphertext objects through router boundaries.

- [ ] **Step 1: Write failing store tests**

Cover exact account lookup, active row uniqueness, atomic rotation, revoked/expired handling, invalid-tag no-fallback, generation CAS, fresh-nonce re-encryption, concurrent update rejection and safe audit fields. Assert startup fails when encrypted mode is enabled but current key is missing/malformed/unreadable.

- [ ] **Step 2: Run focused tests**

Run: `cd backend && pytest -q tests/test_marketplace_credential_store.py`

Expected: FAIL because store/config interfaces are absent.

- [ ] **Step 3: Implement transactional store**

Keep key loading outside ORM and migration code. Select account and credential under tenant context; validate provider twice (query + crypto identity). Put encrypts before persistence and audit writes allowlisted metadata only. Re-encrypt locks the row, decrypts/validates, encrypts with fresh nonce, decrypt-verifies, then compares `generation` in the update.

- [ ] **Step 4: Run store, crypto and RLS tests**

Run: `cd backend && pytest -q tests/test_marketplace_credential_crypto.py tests/test_marketplace_credential_store.py tests/test_marketplace_credential_rls.py`

Expected: PASS.

- [ ] **Step 5: Commit**

Commit store/config/tests with message `feat: add account-scoped credential resolver`.

### Task 4: Switch credential APIs and provider adapters to account ownership

**Files:**
- Modify: `backend/app/routers/cabinet.py`
- Modify: `backend/app/cabinet/schemas.py`
- Modify: `backend/app/platform/integrations/wb_credentials.py`
- Modify: `backend/app/avito/auth.py`
- Modify: `backend/app/routers/avito_orders.py`
- Modify: all provider-client call sites returned by `rg -n 'get_organization_avito_credentials_secret|resolve_bound_wb_credential|wb_token' backend/app`
- Test: `backend/tests/test_marketplace_credential_api.py`
- Modify: existing WB/Avito adapter tests.

**Interfaces:**
- Produces: credential create/rotate APIs requiring `integrations:write` and account ID; provider adapters resolve by exact account.
- Consumes: Task 3 store. Legacy read remains only behind explicit compatibility mode when no encrypted row exists.

- [ ] **Step 1: Write failing permission, ownership and dual-read tests**

Assert read-only actors cannot write credentials; responses/errors contain no secret/ciphertext/key metadata; cross-account/provider access fails; encrypted row wins; missing encrypted row falls back only with flag; corrupt encrypted row never falls back. Preserve WB seller-info identity verification before activation. Require explicit Avito account identity mapping.

- [ ] **Step 2: Run the focused API/adapter tests**

Run: `cd backend && pytest -q tests/test_marketplace_credential_api.py tests/test_wb_credential_binding.py tests/test_avito_orders.py`

Expected: FAIL on old user/org-owned behavior.

- [ ] **Step 3: Route all writes and reads through the store**

Make writers encrypted-only. Change resolver inputs to exact account identity. Remove ambiguous org-latest selection from new paths. Convert crypto/provider exceptions to the safe codes in the spec, with no `str(exc)` in API/audit/cache output. Keep legacy models/readers unchanged only for migration fallback.

- [ ] **Step 4: Run focused tests and inspect OpenAPI**

Run the Step 2 suite. Generate OpenAPI locally and assert response schemas/examples contain no credential value, ciphertext, nonce, verifier or key inventory.

Expected: PASS and no forbidden fields.

- [ ] **Step 5: Commit**

Commit API/adapter changes and tests with message `feat: use encrypted marketplace credentials`.

### Task 5: Remove secrets from asynchronous and diagnostic surfaces

**Files:**
- Modify: `backend/app/repricer_tasks.py`
- Modify: `backend/app/avito/returns_tasks.py`
- Modify: `backend/app/canonical_shadow_tasks.py`
- Modify: `backend/app/review_tasks.py`
- Modify: task dispatch call sites under `backend/app/routers/`
- Modify: provider HTTP clients that expose raw exception text/headers.
- Test: `backend/tests/test_marketplace_credential_leakage.py`

**Interfaces:**
- Produces: tasks whose arguments are tenant/account IDs plus nonsensitive business parameters; allowlisted error/result objects.
- Consumes: Task 3 resolver inside the worker immediately before provider use.

- [ ] **Step 1: Write failing canary leakage tests**

Use unique synthetic values and capture Celery signatures, retry kwargs, result payloads, logs, audit rows, HTTP errors and source-cache writes on success, provider failure and decrypt failure. Assert no raw value, encoded value, ciphertext or verifier appears. Assert task registration signatures have no `wb_token`, client secret or access token parameter.

- [ ] **Step 2: Run focused tests**

Run: `cd backend && pytest -q tests/test_marketplace_credential_leakage.py`

Expected: FAIL on existing secret-capable signatures and raw exception persistence.

- [ ] **Step 3: Replace secret transport and free-form errors**

Pass only account IDs; resolve in worker scope; clear references after provider call where practical. Replace `str(exc)` persistence with typed codes and allowlisted diagnostics. Ensure HTTP client logging never includes Authorization/request bodies. Treat logging filters only as an extra safeguard.

- [ ] **Step 4: Run leakage tests and broker/result inspection**

Run the Step 1 test in eager and real local Redis/Celery modes. Inspect captured broker/result payloads programmatically for all canaries.

Expected: PASS; zero canary occurrences outside the test fixture input.

- [ ] **Step 5: Commit**

Commit async/diagnostic changes and tests with message `security: remove credentials from async surfaces`.

### Task 6: Replace the org-wide extension token

**Files:**
- Create: `backend/app/platform/integrations/ingestion_tokens.py`
- Modify: `backend/app/routers/avito_orders.py`
- Modify: `frontend/api/v1/avito/orders/browser-snapshot.ts`
- Test: `backend/tests/test_avito_extension_token_scope.py`

**Interfaces:**
- Produces: issue-once, verify, revoke and status operations for exact Avito account and scope `avito.browser_snapshot.write`.
- Consumes: Task 2 ingestion-token row. Stores only SHA-256 verifier for a random token with at least 256 bits entropy.

- [ ] **Step 1: Write failing scope/lifecycle tests**

Cover self-locating organization locator + random public ID + random secret, tenant-context exact lookup under forced RLS, uniform invalid-token responses, one-time reveal, constant-time verifier comparison, exact account, expiry, revoke/rotate, cross-account rejection, write-only route scope, account-scoped snapshot key, pre-lookup IP abuse limit, post-verification per-token rate limit and body-size gates. Assert invalid IDs do not create unbounded cache keys, request body cannot override account, extension bearer cannot GET returns-sync or update settings, and bearer is absent from logs/errors/cache.

- [ ] **Step 2: Run focused tests**

Run: `cd backend && pytest -q tests/test_avito_extension_token_scope.py`

Expected: FAIL because current token is organization-scoped in generic cache.

- [ ] **Step 3: Implement scoped verifier and route contract**

Require explicit `marketplaceAccountId` only at authenticated issue. Ingest derives account exclusively from the verified self-locating token and rejects/ignores no caller-supplied account override. Persist verifier in the dedicated forced-RLS table, reveal raw token only in the successful issue response, enforce owner-selected TTL/rate/body policy, and remove extension authorization from returns-sync GET. Keep old token verification only during a short revoke/reissue window; never copy its hash into an account row.

- [ ] **Step 4: Run tests and frontend request smoke**

Run backend focused tests, then `cd frontend && npm run typecheck && npm run test && npm run build`. Exercise a local synthetic extension request and assert only the selected account snapshot changes.

Expected: all checks pass.

- [ ] **Step 5: Commit**

Commit token boundary, routes/frontend contract and tests with message `security: scope extension ingestion tokens`.

### Task 7: Build restricted idempotent backfill and verification command

**Files:**
- Create: `backend/scripts/backfill_marketplace_credentials.py`
- Create: `backend/ops/marketplace-credential-backfill-role.sql`
- Test: `backend/tests/test_marketplace_credential_backfill.py`
- Create: `backend/docs/runbooks/marketplace-credential-migration.md`

**Interfaces:**
- Produces CLI modes `inventory`, `backfill`, `verify`, `report`; inputs are an owner-reviewed mapping file containing IDs only.
- Consumes: Tasks 2–4 storage/resolver. Output is counts, IDs, status codes and timestamps only.

- [ ] **Step 1: Write failing backfill tests**

Create synthetic WB/Avito legacy rows and explicit mappings. Test per-row lock/encrypt/read-back/decrypt/schema/exact-equality before commit, interruption/restart idempotency, ambiguous mapping refusal, newer-generation protection, partial failure isolation and no secret/digest/ciphertext output. Assert legacy Avito cached access tokens are not copied: only after client-credential decrypt plus successful synthetic OAuth exchange is a fresh access token encrypted and the legacy cache eligible for deletion.

- [ ] **Step 2: Run focused tests**

Run: `cd backend && pytest -q tests/test_marketplace_credential_backfill.py`

Expected: FAIL because CLI/role do not exist.

- [ ] **Step 3: Implement the one-shot runner and least-privilege role**

The schema migrator never runs data backfill. The dedicated role gets only required legacy `SELECT` and encrypted-table operations; runner requires keyring only for `backfill`/`verify`, refuses implicit user→account cardinality, and emits no values/hashes. Document supervised grant, mount, run, verification and immediate revoke steps without secret-bearing shell examples.

- [ ] **Step 4: Verify on a disposable production-shaped clone**

Run inventory, interrupted backfill, resume, verify and report. Assert expected=mapped=encrypted=decrypt_verified, unresolved=0, no canary leakage, then revoke role and prove a subsequent query is denied.

Expected: all gates pass; no production connection is used.

- [ ] **Step 5: Commit**

Commit runner, role, tests and runbook with message `feat: add credential migration backfill`.

### Task 8: Add deployment key mounts and decide DB-role separation

**Files:**
- Modify: `backend/docker-compose.yml`
- Modify: `backend/app/config.py`
- Modify: `backend/ops/runtime-db-role.sql` or split role templates.
- Modify: `backend/Dockerfile` to run application services as a dedicated non-root user that belongs to the approved key-reader group.
- Test: `backend/tests/test_marketplace_credential_deployment.py`
- Modify: `backend/docs/runbooks/marketplace-credential-migration.md`

**Interfaces:**
- Produces: keyring read-only in API/required workers, absent from migrate/beat; non-secret current-version config; documented host/offline custody.
- Consumes: owner decisions for custodian, paths, permissions, service list and recovery.

- [ ] **Step 1: Write failing rendered-Compose and permission tests**

Assert no key value/environment interpolation, read-only mount only on approved services, no mount on migrate/beat, non-root service process, startup fail-closed and the owner-selected DB-login model. Assert files in the image/repo do not contain key material.

- [ ] **Step 2: Run focused deployment tests**

Run: `cd backend && pytest -q tests/test_marketplace_credential_deployment.py`

Expected: FAIL because mounts/config/service role split are absent.

- [ ] **Step 3: Add templates, never key material**

Mount the owner-approved host directory read-only. Pass only current version and mount path as nonsensitive configuration. Ensure container user can read keys without making files world-readable. Keep schema migrate separate; create API/worker/beat DB logins if approved. Beat never receives a key mount; credential-table access is also removed when split logins are approved.

- [ ] **Step 4: Render and inspect locally**

Run Compose config with synthetic local paths and keys, service startup tests, file permission tests and repository secret scan. Delete disposable synthetic key material outside the repo afterward.

Expected: approved readers start; missing/malformed key fails closed; migrate/beat cannot read it.

- [ ] **Step 5: Commit**

Commit deployment templates/tests/runbook with message `ops: isolate marketplace credential keys`.

### Task 9: Exercise rotation, switch, cleanup and rollback gates

**Files:**
- Modify: `backend/scripts/backfill_marketplace_credentials.py`
- Create: `backend/alembic/versions/20260908_0062_marketplace_credentials_cleanup.py` only after observation gates pass and if `0062` is still the next free revision at implementation time; otherwise stop for revision coordination rather than silently renumbering.
- Modify: legacy cabinet stores/models/config call sites identified by `rg`.
- Test: `backend/tests/test_marketplace_credential_rotation.py`
- Test: `backend/tests/test_marketplace_credential_cleanup.py`
- Modify: `backend/docs/runbooks/marketplace-credential-migration.md`

**Interfaces:**
- Produces: controlled batch re-encryption, encrypted-only switch, irreversible-safe cleanup and encrypted-aware rollback procedure.
- Consumes: verified zero-fallback report, owner observation window and backup retention decisions.

- [ ] **Step 1: Write failing rotation/cleanup/rollback tests**

Cover dual keyring, new-writer version, `FOR UPDATE SKIP LOCKED`, fresh nonce, decrypt-before-CAS, concurrent generation conflict, zero-old-version gate, absence of plaintext columns/readers/env fallback, and rejection of a pre-encryption writer. Test recovery from encrypted backup with separately supplied old key.

- [ ] **Step 2: Run focused tests**

Run: `cd backend && pytest -q tests/test_marketplace_credential_rotation.py tests/test_marketplace_credential_cleanup.py`

Expected: FAIL until lifecycle tooling and cleanup are implemented.

- [ ] **Step 3: Implement rotation and encrypted-only switch first**

Deploy readers for old+new keys, set writer to new version, re-encrypt/verify/CAS in batches, and require zero active old-version rows plus consumer canaries. Switch off legacy fallback only after the agreed zero-fallback observation window. Do not delete legacy data in this step.

- [ ] **Step 4: Take encrypted backup, restore-rehearse, then cleanup**

On an authorized production change only: create encrypted backup, restore in isolation with separately supplied recovery key, verify all rows, then apply cleanup revision removing plaintext columns/legacy refs/cache entries and provider credential env fallback. Revoke backfill access and enforce retention purge. No downgrade repopulates plaintext.

- [ ] **Step 5: Run full release gates**

Run focused tests from every task; `cd backend && .venv/bin/python -m pytest -q`; `cd backend && .venv/bin/python -m compileall -q app tests alembic`; `cd frontend && npm run typecheck && npm run test && npm run build`; migration upgrade/downgrade/upgrade on disposable DB; RLS probes; canary leakage scan; encrypted backup restore; and account-specific provider canaries.

Expected: zero new failures; every spec go/no-go passes. Existing unrelated baseline failures, if any, are recorded exactly and require owner acceptance rather than being described as pass.

- [ ] **Step 6: Commit**

Commit rotation/cleanup/tests/runbook with message `security: complete credential plaintext cleanup`.

## Execution order and review gates

Tasks 1–3 establish the cryptographic/persistence boundary; Task 4 moves synchronous consumers; Tasks 5 and 6 close side channels and extension scope; Tasks 7 and 8 create controlled migration operations; Task 9 alone may switch and remove legacy storage. Each task requires security review before the next. Task 9 cleanup is forbidden until every owner decision and go/no-go in the spec is resolved.

Recommended execution is a dedicated isolated worktree with review after each task. This docs-only commit does not authorize implementation, key generation, schema change, environment change, backup access or production rollout.
