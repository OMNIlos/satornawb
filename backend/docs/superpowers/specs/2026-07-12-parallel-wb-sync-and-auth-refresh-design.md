# Parallel WB Sync and Auth Refresh Design

## Goals

Run independent WB sync sources with at most four concurrent workers while preserving goods-dependent calculations. Keep production browser sessions renewable across cross-site frontend/API deployment and stop infinite 401 loops when renewal is impossible.

## Parallel sync

Create all requested source steps in deterministic order. Run `goods`, `content`, `promotions`, `stocks`, `period-stats`, and `ads` in one `ThreadPoolExecutor(max_workers=4)`. When goods completes, allow `finance` and `baskets` to run through the same executor; when goods was not requested, they may use the existing cache immediately.

One re-entrant lock protects step mutation, status mutation, snapshot creation, and status persistence. Status exposes `activeSources`; `currentSource` remains as a backward-compatible first active source. A source failure produces an error step but does not cancel other sources.

## Auth refresh

Production cross-site refresh cookies use `SameSite=None`, `Secure`, `HttpOnly`, and path `/`. Credentialed CORS must include the exact frontend origin via configuration. A terminal refresh 401 clears the expired access token and emits the existing cleared event, stopping repeated background refresh attempts.

Concurrent requests in one tab remain deduplicated. The backend accepts a just-rotated previous refresh token for a short grace period so simultaneous refreshes from separate tabs do not revoke the browser session.

## Verification

Backend tests prove peak sync concurrency is at most four, independent work overlaps, finance/baskets wait for goods, status snapshots retain concurrent steps, source errors remain partial, cookie attributes are production-safe, and refresh rotation grace works. Frontend tests prove a terminal refresh 401 clears stored auth while normal refresh still retries successfully.
