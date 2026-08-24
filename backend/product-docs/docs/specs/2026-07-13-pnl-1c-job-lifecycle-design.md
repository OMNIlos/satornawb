# P&L / 1C Job Lifecycle Design

## Goal

Make a P&L date change immediately visible to 1C and keep the P&L background job open until 1C operating expenses are available.

## Lifecycle

1. `POST /api/wb/reports/pnl/jobs` creates or reuses the cash-flow request in Postgres before dispatching Celery.
2. The P&L Celery task reads the cash-flow state first. For `pending` or `processing`, it stores `waiting_1c` and retries later without building or completing P&L.
3. 1C atomically claims a pending or stale-processing row with a database row lock.
4. 1C posts the result into the same database row shared by API and worker.
5. A later Celery retry sees `ready`, builds P&L once, embeds cash-flow data, and marks the report completed.

## Storage and compatibility

Postgres is the production source of truth. The existing JSON implementation remains a fallback for local/test environments where the database is unavailable, preserving current endpoint compatibility. A unique `(organization_id, period_from, period_to)` constraint makes creation idempotent, and a status/creation index supports polling.

## UI

The frontend recognizes `waiting_1c` as a non-terminal job state, continues polling every 2.5 seconds, and explicitly says that it is waiting for operating expenses from 1C.

## Verification

Backend API tests cover immediate creation and the 1C round trip. Task tests cover waiting without starting the expensive P&L build. Frontend unit tests cover `waiting_1c`. Browser/headless tests are excluded.
