# WB Reviews Backend Design

Status: approved for implementation on 2026-07-17.

## Goal

Make `/wb/reviews` backend-ready without live publishing to Wildberries: fetch and cache WB feedbacks, generate OpenAI-backed reply drafts, keep risky replies behind approval, and expose configurable sync settings for the frontend.

## External Contracts

Wildberries Feedbacks API uses `https://feedbacks-api.wildberries.ru`.

- `GET /api/v1/feedbacks` fetches feedbacks with pagination and sorting.
- `GET /api/v1/feedback` fetches one feedback by ID.
- `POST /api/v1/feedbacks/answer` replies to a feedback, but this project must not call it yet.
- `PATCH /api/v1/feedbacks/answer` edits a feedback answer, but this project must not call it yet.
- Current documented category limits per seller account: Personal and Service tokens allow 3 requests/second with 333 ms interval and burst 6; Base token allows 5 requests/hour with 12 minute interval and burst 1.

OpenAI reply generation uses the Responses API with structured JSON output. The backend must work without an API key by falling back to deterministic template drafts and marking the generation source accordingly.

## Backend Behavior

The module remains draft-first. Generated responses are either safe drafts or approval-required drafts. No endpoint sends a reply to WB unless live send is explicitly implemented in a future change; the current send route returns a blocked or dry-run status and never performs a WB mutation.

Feedback sync writes normalized rows plus raw WB payloads to Postgres. If the database is unavailable in local/test mode, the existing memory fallback remains available and must fail fast instead of hanging on a long TCP timeout.

Sync settings are organization-scoped in the API surface. The current project has one active organization in most flows, but schemas and storage must include `organization_id` so the module is not boxed into a global singleton. Settings include enabled/disabled, interval minutes, token type, unanswered-only, pagination size, and date window.

## API Surface

Existing endpoints stay:

- `GET /api/v1/wb-reviews/settings`
- template, stop-topic, moderation-rule CRUD
- `POST /api/v1/wb-reviews/sync`
- `GET /api/v1/wb-reviews/feedbacks`
- `GET /api/v1/wb-reviews/feedbacks/{feedbackId}`
- `POST /api/v1/wb-reviews/drafts/generate`
- draft read, prompt trace, approve, reject, send, send-job read
- `GET /api/v1/wb-reviews/{reviewId}/approval`

New endpoints:

- `GET /api/v1/wb-reviews/sync-settings`
- `PUT /api/v1/wb-reviews/sync-settings`
- `GET /api/v1/wb-reviews/sync-status`

The frontend can use these endpoints to render the current sync interval and allow the user to update it.

## Data Model

Add Alembic migration for existing `rv_review_*` tables and new:

- `rv_review_sync_settings`
- `rv_review_sync_runs`

Settings store one row per organization. Runs store the latest manual/scheduler sync status, counts, timestamps, trigger, and safe error messages.

## OpenAI Draft Generation

Add a small adapter package under `app/reviews/openai_client.py`.

The adapter returns a typed result:

- `replyText`
- `riskLevel`
- `requiresApproval`
- `reasons`
- `matchedStopTopics`
- `model`
- `generationSource`

Generation prompt layout keeps stable instructions and brand rules first, with the current feedback text and product data last for prompt-cache friendliness.

## Scheduler

Add Celery tasks:

- `reviews.sync_for_org`
- `reviews.sync_all_orgs`

The scheduler reads saved settings and skips when disabled or interval is not due. The current frontend can also trigger manual sync via API.

## Safety

Live WB answer mutation is intentionally out of scope. The backend may construct the request path and log a blocked send job, but it must not call `POST /api/v1/feedbacks/answer` or `PATCH /api/v1/feedbacks/answer`.

Low rating, stop topics, already answered feedbacks, legal/compensation/defect wording, and empty text require manual review or block sending.

## Verification

Implementation must be test-first:

- API tests for sync settings/status.
- Service tests for minimum interval by token type.
- Runtime tests for WB response parsing and answer send disabled.
- OpenAI adapter tests with mocked HTTP client and fallback.
- Migration metadata test for `rv_review_*` tables.
