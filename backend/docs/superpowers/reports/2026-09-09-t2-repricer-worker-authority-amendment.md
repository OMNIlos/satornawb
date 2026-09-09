# T2 → T1: bounded repricer worker-authority amendment

Status: dependency request, **not an accepted worker permission policy or activation**.
Local evidence only. Existing Orders-only proposal cannot authorize a price mutation.
Accepted approvals schema: `dbf8d31d9fc0b9035b9c8a84727e70713956afe0` /0066.
Dormant scoped participant and committed user commands:
`bd3bb60a0baadc8d7683c8efd8bf4eff444c9643`.

## Existing boundaries and missing authority

`UserApprovalCommands.create_intent/claim/reject/block` owns a root transaction,
requires an authenticated `UserSessionPrincipal`, exact WB account binding and
service-fixed `price:send`. It returns after physical commit. T1 confirmed this
composition; it is not worker authority and exposes no worker/provider commands.

`ApprovalTransaction.reserve_attempt/mark_dispatch/record_attempt_outcome` currently
participates in a caller-owned transaction only. Values are uncommitted, its
membership check is not authentication, and its worker audit classification does
not authenticate a worker. No current router, job or provider uses this participant.

T1 must supply a reviewed trusted worker/job authority bound to durable job identity
and scope. A queue-provided membership ID, a frozen `AuthenticatedApprovalActor`,
or fabricating `UserSessionPrincipal` from historical IDs is insufficient.
The queue carries internal org/account/job IDs only, no credentials or permission list.

## Exact binding required at domain entrypoints

Common binding: internal positive INT4 `organization_id`, `marketplace_account_id`,
logical exact TEXT `approval_id`, immutable `action_key` and `request_checksum`.
Resolve by the full scope, never by UUID alone. `approval_row_id` is a physical UUID4
locator, not a replacement for the logical identity or account ownership.
The provider target is WB plus the exact expected external account identity and
accepted credential ID/generation/schema version, not whichever account is current.

| Entrypoint | Additional frozen predicates | Authority required |
| --- | --- | --- |
| User create/claim/reject/block | canonical request bytes for create; `expected_version` for transition; authenticated initiating membership | Current user/session/account checks, fixed `price:send`; implemented user boundary only |
| Future scheduled create/claim | same immutable request and expected approval version; durable originating job and initiator evidence | Accepted initiator-capable worker authority, current permission/account checks; no implicit system bypass |
| `reserve_attempt` | applying approval, claim version and claimant; one lifetime attempt UUID4 and its action/checksum | Initiator-capable job authority before reservation; return alone never authorizes send |
| `mark_dispatch` | exact attempt UUID4, reserved status, attempt version0, approval applying/claim version, claimant and deterministic dispatch key | Initiator-capable job authority plus exact usable WB credential binding before marker; caller commits marker before I/O |
| `record_attempt_outcome` | exact attempt UUID4, dispatch key/action/checksum, expected approval and attempt versions, allowlisted outcome, upload ID/result when applied | Separate state-closing authority bound to the already owned durable job/attempt; not new send authority |
| Future reconciliation | same owned attempt identity and upload ID if known; dispatched/ambiguous observation; no resend | State-closing authority for local facts; separately authorized valid credential for provider-history GET |

Versions are exact integers (approval/claim versions are PostgreSQL NUMERIC, not
silently narrowed floats/BIGINT). `dispatch_key` is already frozen by the pure
domain from org/account/approval/action/attempt identity; worker envelope must
bind the same value, not introduce a competing action key. Replays must compare
the immutable payload as well as the key. Expected versions come from durable rows
or a verified command, not “latest version” substitution after conflict.

## Revocation and uncertainty: safety floor, not invented roles

Initiation must fail closed after session/permission/account/credential revocation
or a changed expected binding. An old job cannot refresh itself into unrelated
authority or choose a newer credential merely to continue sending.

| Point of revocation/crash | Safe effect boundary | State-closing requirement for T1 design |
| --- | --- | --- |
| Before intent | No intent/send under denied authority | No action to recover |
| Intent committed, before marker | No provider POST after denied authority | A verified worker may record known local non-dispatch failure only under separately accepted closing authority; otherwise leave blocked recovery, not fabricate authority |
| Marker committed, before/around POST | Marker is not reusable send permission; revoked authority must not initiate a fresh POST | If non-dispatch cannot be proved, classify ambiguous; no automatic resend |
| Provider may have accepted, before local outcome commit | Never convert uncertainty to known rejection | Persist safe ambiguous observation using owned state-closing authority; preserve any known upload ID as permitted by the canonical outcome contract |
| Result committed, before ACK / duplicate delivery | Closed approval/attempt prevents another POST | Read/ACK the existing result under scoped worker authority; do not reopen/reclaim |
| Credential revoked while reconciliation needed | Do not use revoked credentials or borrow another tenant/account | Local ambiguity can remain; provider-history read waits for explicitly authorized matching-account read authority |

Revocation must stop *new external effects*, not erase already observed provider
facts. T1's accepted design needs to distinguish these two authorities so recovery
does not impersonate a revoked user. This document requests that distinction; it
does not grant a service role, extend a session, approve any TTL/lease duration or
define a retry policy. Until accepted, all worker entrypoints remain unwired.

`ambiguous` is terminal in the current domain and0066. Reconciliation may append
evidence but **cannot** silently call the existing API to turn ambiguous into applied
or create another attempt. Any future reconciliation state extension requires a
separately reviewed domain/schema change; proof of provider nonacceptance is not
inferred from timeout, absent upload ID or empty history page.

## Minimum shared contract requested, and proof gates

1. Trusted resolver result identifies its action class (initiate vs close vs read),
   exact durable job, org/account and preserved initiator evidence. Action sets are
   service-fixed, not selected by the queue. Define the owner of durable job-to-
   approval/attempt binding and whether0066 audit needs a composite job reference.
2. Transaction-bound initiation validation composes accepted lock ordering
   user → membership → session → account → credential → domain without recreating
   a live user session. State-closing validation uses its reviewed authority,
   not a blanket skip of permission checks.
3. State what authenticated executor may close after initiator revocation and how
   job cancellation, credential generation changes and duplicate delivery are
   distinguished. No guessed service-account ID, permission, TTL or expiry default.
4. Tests: crossorg; two accounts; forged/reused job/attempt/action/dispatch IDs;
   changed payload under key; initiator revoke before/after marker; expired or
   changed credential; duplicate delivery; outcome after revoke; failed commit;
   crash after possible acceptance. Zero-row CAS causes zero fake provider calls.

External exactly-once is not promised: the local marker is a conservative durable
fence, not a provider idempotency guarantee. Final authority check cannot eliminate
the distributed revocation/POST gap; cancellation semantics at that boundary need
an explicit accepted contract. No scheduler, real provider request, schema, config,
frontend or current repricer change is part of this amendment.
