# Avito Failure Surface Handoff

**IMPLEMENTED / UNVERIFIED.** Four-path temporary delegation from T1. No tests,
test authoring, import, compile, lint, review, DB, Redis, provider, credential,
network, production or activation actions were performed. This is not a claim
that all Avito diagnostic surfaces are sanitized.

## Changes

- `app/avito/returns_tasks.py`: existing decorated task name, signature, retry
  count and dispatch remain. Its body delegates to a private implementation under
  one outer failure boundary, covering settings/credential lookup, client calls,
  upsert and status persistence. Failure attempts to save the fixed string
  avito_returns_sync_failed with the existing failed state and retryable=True.
  Failure of that status save is contained. A fixed RuntimeError is raised outside
  both exception handlers, so Celery still receives a failed task, not a synthetic
  successful/skipped result, without original chained exception content.
- Blocked task errors retain object/null shape, closed known codes, boolean retry
  flag and known blockers, but replace arbitrary source messages. Completed and
  blocked diagnostics retain only fixed endpoint, bounded integral HTTP status and
  counts, plus fixed error/null reason. URL, request parameters, provider key names
  and unexpected diagnostic members are not returned or cached by this boundary.
  Successful business upsert/count/date/status payloads are otherwise unchanged.
- `app/routers/avito_orders.py`: return inventory enrichment failure retains
  unavailable status and zero counts with fixed avito_return_inventory_unavailable.
  Browser filter fallback retains rows/source/status but emits fixed
  avito_orders_filter_unavailable instead of exception text. Existing HTTPException
  handling and scope/auth/route/cache behavior are unchanged.
- `app/routers/avito_overview.py`: caught exception conversion returns closed
  code/message rather than dynamic class/text. The existing rate-limit classifier
  is retained internally to preserve cooldown/stale selection; only its boolean
  result escapes. Retryable remains True. A broken exception formatter falls back
  to generic unavailable, rather than throwing another diagnostic error.

## Explicit Residual Risks

The actual local Orders client still logs diagnostic request URL/parameters before
these return-task boundaries and can build transport errors from raw exception
text. It was outside the delegated files and was not changed. Other overview
branches directly forwarding typed client errors and historical cached errors
were not part of the delegated `_section_error` span. Thus this patch cannot claim
global secret-safe logging or sanitization of all successful/cached HTTP responses.
T1 retains source-client/shared diagnostic and credential cutover ownership.

Legacy returns tasks still enumerate organizations (including the existing empty
list fallback), use organization-level credentials/cache/storage and scheduler
identity, and do not implement canonical permission-filtered account selection.
Those business and security migrations are not silently performed here. Normal
Avito return matching is preserved; it is not the removed standalone KIZ matcher.

No historical JSON/cache records were rewritten or erased. Existing operational
defaults, schedules, retry declarations, task arguments and browser stale labels
are preserved. Changing exception class/message is intentional failure-surface
compatibility, not evidence of successful task execution.

## Final Canary Cases Pending

Central verification must inject synthetic secret canaries at initial settings,
credential access, provider read, return upsert, success/blocked status write and
failed-status write. Assert failure remains failure, persisted error and serialized
Celery exception contain only fixed content, and no cause/context retains the raw
exception. Exercise unknown diagnostic keys/URLs/body keys, oversized or boolean
counts/status, known blocked codes/retry flags, and unchanged successful business
DTOs. Check return inventory and browser fallback rows/types, HTTPException path,
overview rate-limit cooldown/stale branch and broken exception formatting.
Run existing return matching/task/router regression at the final coordinated gate.

Rollback is a bounded revert of this commit's four paths; it would restore the
unsafe diagnostic behavior and should not be used to recover deleted data because
no persisted user data was changed by this source package.
