# T4 canonical-only WB Review HTTP handoff

## Scope and registration request

Coordinator explicitly approved canonical-only explicit-account sync. It must not
feed the global legacy Review store. This supersedes dual-consumer shadow for this
path only; legacy isolation and trusted legacy-source binding remain separate gaps.

T1 registration input: `app.reviews.canonical_router.router`, containing
`POST /api/v2/reviews/wb/sync`. The router is NOT registered in the shared app by T4.
Only synthetic test apps include it. Request to T1 is default-off registration,
not operational activation. Existing legacy routes/tasks/frontend remain unchanged.

Prerequisites consumed: physical guard8338ef7 via2dc09de; lossless0065 via74bde41,
decoder/writerdab11ec/0ce0517; fixture34b5f62 via79f83b9; selector434ff5f via9981e72.
No competing schema/config change or pending approvals migration was imported.

## Wire contract

`ReviewCanonicalSyncRequest`: snake_case, extra fields forbidden. Required:
marketplace_account_id strict positive INT4, request_id UUID, is_answered strict bool.
Optional nm_id is a positive JS-safe integer; take1..5000 defaults100; skip0..INT4_MAX
defaults0; order dateAsc/dateDesc defaultsdateDesc; optional nonnegative date_from/
date_to Unix seconds bounded at year9999, ordered when both provided. One explicit
answered/unanswered stream and one page per HTTP request; no implicit loop or
cross-stream aggregation. No scenario, secret, actor, permission or legacy payload.

`ReviewCanonicalSyncResponse`: sync_run_id UUID string, manifest_checksum lowercase
SHA256, observed_count integer, completeness always partial. It contains no Review
body, provider payload, credential reference or secret. It is not a printable/send
capability or a public canonical Review read response.

Errors use `detail.code`:

- 401 REVIEW_SYNC_AUTHENTICATION_REQUIRED (real existing bearer/session resolver).
- 403 REVIEW_SYNC_DENIED (live permission/scope, session or authority change).
- 409 REVIEW_SYNC_DISABLED, REVIEW_SYNC_CONFLICT, REVIEW_SYNC_CREDENTIAL_UNAVAILABLE.
- 400 REVIEW_SYNC_INVALID (including invalid received canonical source fields).
- 502 REVIEW_SYNC_PROVIDER_UNAVAILABLE (provider failure or malformed page envelope).
- 503 REVIEW_SYNC_STORAGE_UNAVAILABLE or REVIEW_SYNC_CONFIGURATION_INVALID.

FastAPI body-validation422 remains the standard framework contract. Fixed error
codes do not echo provider errors, SQL, credentials or bearer strings. Dependencies
also translate engine/config acquisition failures. Shared auth may update session
last_seen_at; canonical-only does not mean zero authentication/control-plane writes.

## Ownership, transactions and source evidence

Pure exact-pair selector is checked independently of authorization; defaultFalse,
empty allowlist. A fresh Engine-owned root discovers exact WB account/membership,
then shared guard checks live reviews:write, session and selected-account access
before credential resolution/provider fetch. Metadata discovery alone is not a grant.

Paired credential resolver supplies the actual nonempty WB token and binding.
Frozen preflight external-account/ref is compared with that paired binding; the
next guarded reservation revalidates its exact authority. Reservation commits before
provider I/O; no publication lock is held during fetch. Publication uses a separate
guarded root and returns only after commit. Revocation after fetch blocks publication.
No fabricated worker actor, user-token fallback or legacy `_run_db`/memory fallback.

Request source key is `http:` plus canonical request UUID. Checksum binds the explicit
account and all page selectors, excluding the request UUID itself. Changed request
under the same key conflicts before fetch. Identical retries may fetch again; exact
received evidence replays without duplicate facts, changed evidence conflicts.
This is idempotent persistence, NOT exactly-once provider reads or automatic retry.

New `canonical_wb_fetch.py` uses one shared rate-limited client request with the exact
paired token override. It requires `data.feedbacks` to be a list, rejects malformed
elements/pages rather than silently skipping, and keeps raw scalar values in a
redacted canonical DTO (`wb-feedbacks-api-v1`). Canonical normalization validates
them before fact writes. Null/empty/whitespace/NUL text is preserved; opaque IDs are
not stripped (invalid padded IDs are rejected by the existing canonical contract).
Missing/malformed source timestamp is rejected, never replaced by current time.
Answer-text presence must agree with the requested stream; mismatches fail closed.
No send eligibility is inferred. Legacy WB adapter remains byte-for-byte unchanged.

Coverage is conservatively partial even for an empty page. No provider completeness,
terminal pagination, tombstone or date-window semantics are inferred from page size.
Failed fetch/publication leaves its committed reservation running. Failed-run
finalization, process-restart recovery and ambiguous physical-COMMIT recovery remain
unimplemented; an injected pre-COMMIT error proves only its tested rollback case.

## Verification ledger

Initial missing HTTP3RED→3PGPASS. Actual completed account rebind after preflight
produced200 instead403:1RED→frozen expected-binding fix. Independent critic found
legacy normalization would lose raw evidence; separate adapter7RED→7PASS and actual
raw FakeWbApiClient→HTTP→PostgreSQL cases cover null/empty/whitespace/NUL/sourceversion
and invalid dates. Intermediate test corrections aligned padded-ID expectations with
the existing reject-not-strip contract and read evidence from actual repository/SQL
fields rather than nonexistent snapshot attributes.

Real signed bearer authentication, missing/tampered bearer, default-off, denied
account before credential/fetch, live permission/scope, session/credential revocation
during fetch, publication commit injection, request replay/conflict, malformed
request and OpenAPI schema are exercised. Canonical success with legacy memory/DB
access forbidden and runtime SQL capture without rv_review_* proves this path avoids
the global store. Engine-config1RED500→503 and credential-outage1RED409→503 are fixed.

Pre-final expanded suite:897PASS2warnings49.13s. Final combined run including the
three additional HTTP cases and final error mapping: **900 passed, 2 warnings in
49.16s**, no skips, natural exit0. This is the selected28-file Review/credential/
guard/selector/adjacent set, not the full backend suite. Scoped Ruff/compile/diff0.
Independent final static criticPASS: prior P1 lossless and preflight defects closed,
no new important findings. The critic did not independently rerun the900tests.
All runs use scrubbed environment, Unix-only sandbox and fresh owned disposable
PostgreSQL databases/runtime roles with cleanup checks. Provider boundary is fake;
no actual WB, Avito, LLM, production, Redis, print/export or delivery action occurs.

Remaining stages include account-owned policy/draft/send/notification services and
their DDL, canonical public reads/frontend integration, legacy isolation/retirement,
full integration baseline and separately authorized canary. No architecture-complete
or production-readiness claim follows from this bounded HTTP slice.
