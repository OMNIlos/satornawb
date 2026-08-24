# Digest background job design

## Goal

Make `/wb/reports` responsive by moving WB digest collection off the page request, while retaining the last completed digest during a refresh.

## Backend

The digest cache is keyed by organization and exact `dateFrom`/`dateTo`. `GET /api/wb/reports/digest` only reads that key and never calls WB. Its response contains either the exact cached digest or the latest completed digest for the organization, together with a `digestJob` status object.

`POST /api/wb/reports/digest/refresh` parses the requested range and queues a Celery task for that exact key. A queued or running task for the same organization and range is reused instead of duplicated. The task obtains the cabinet WB token, builds the existing source, ads, and plan-fact snapshots, saves the digest cache, and persists `queued`, `running`, `completed`, or `failed` status plus timestamps and a safe error message.

`GET /api/wb/reports/digest/status` returns the status for the exact requested range. All three endpoints retain the current report-read permission checks. The cache/status records live in the existing source-cache store, so no schema migration is required.

## Frontend

On entering the digest view and on every date-range change, the frontend first fetches the fast cache response, requests a refresh, then polls digest status. It displays the returned digest immediately. If it is a fallback from a different range, the UI labels it as the last available data and shows that the selected range is updating. On completion it reloads the exact digest; on failure it preserves the last result and shows the task error with a retry action.

The old sequential seven-day chunking and 600-second page-request timeout are removed for the digest flow. A range change creates or follows only the job for that new exact range; the former job can finish and populate its own cache without replacing the selected range in the UI.

## Tests

Backend tests cover cache-only reads, one queued job per range, task state transitions, error persistence, and fallback digest selection. Frontend tests cover refresh/poll behaviour and the visible updating/fallback state.
