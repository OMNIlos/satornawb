# WB Reviews Backend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a production-safe WB reviews backend that fetches and caches feedbacks, generates OpenAI-backed drafts, exposes configurable sync, and never sends live WB replies yet.

**Architecture:** Extend the existing `app.reviews` package rather than replacing it. Add focused storage schemas for sync settings/runs, a small OpenAI adapter with deterministic fallback, WB answer runtime methods kept disabled, and Celery tasks that reuse the same service functions as manual sync.

**Tech Stack:** FastAPI, Pydantic v2, SQLAlchemy 2, Alembic, Celery, httpx, pytest, OpenAI Responses API over HTTP.

## Global Constraints

- No live WB feedback answer mutation in this implementation.
- All generated replies remain drafts or approval-required drafts.
- WB Feedbacks API limits: Personal/Service 3 requests per second with 333 ms interval and burst 6; Base 5 requests per hour with 12 minute interval and burst 1.
- OpenAI must be optional; without `OPENAI_API_KEY`, deterministic template fallback is used.
- Use TDD: add a failing test before production code for each behavior.

---

### Task 1: Persistence And Packaging

**Files:**
- Modify: `pyproject.toml`
- Modify: `tests/test_infra_baseline.py`
- Create: `alembic/versions/20260717_0017_wb_reviews_runtime.py`
- Modify: `app/reviews/orm.py`

**Interfaces:**
- Produces SQLAlchemy tables `rv_review_templates`, `rv_review_stop_topics`, `rv_review_moderation_rules`, `rv_review_feedbacks`, `rv_review_drafts`, `rv_review_send_jobs`, `rv_review_prompt_traces`, `rv_review_sync_settings`, and `rv_review_sync_runs`.

- [ ] Add a failing metadata test for all review tables.
- [ ] Run `pytest -q tests/test_infra_baseline.py -k reviews` and confirm failure.
- [ ] Add ORM rows for sync settings/runs and package entries for `app.reviews`.
- [ ] Add Alembic migration with create/drop table definitions.
- [ ] Run the focused metadata test and confirm pass.

### Task 2: Sync Settings And Status API

**Files:**
- Modify: `app/reviews/schemas.py`
- Modify: `app/reviews/service.py`
- Modify: `app/routers/wb_reviews.py`
- Modify: `tests/test_wb_reviews.py`

**Interfaces:**
- Produces `ReviewSyncSettingsView`, `ReviewSyncSettingsUpdateRequest`, `ReviewSyncStatusView`.
- Produces service functions `get_sync_settings`, `update_sync_settings`, `get_sync_status`.
- Produces API routes `GET/PUT /api/v1/wb-reviews/sync-settings` and `GET /api/v1/wb-reviews/sync-status`.

- [ ] Add failing API tests for default settings, Base-token interval clamping, and status after no sync.
- [ ] Run focused tests and confirm failure.
- [ ] Implement schemas, DB/memory storage, and routes.
- [ ] Run focused tests and confirm pass.

### Task 3: WB Runtime Fetch/Answer Boundary

**Files:**
- Modify: `app/wb_api/feedbacks_runtime.py`
- Modify: `app/wb_api/client.py`
- Modify: `app/reviews/service.py`
- Modify: `tests/test_wb_reviews.py`

**Interfaces:**
- Produces `send_feedback_answer(feedback_id: str, text: str, *, scenario: str = "complete")`.
- Produces sync run persistence in `sync_feedbacks`.

- [ ] Add failing tests that WB feedback parser accepts documented payload shapes and that non-dry-run send is blocked without live mutation.
- [ ] Run focused tests and confirm failure.
- [ ] Implement parser broadening, safe blocked send result, and sync run status recording.
- [ ] Run focused tests and confirm pass.

### Task 4: OpenAI Draft Adapter

**Files:**
- Modify: `app/config.py`
- Create: `app/reviews/openai_client.py`
- Modify: `app/reviews/schemas.py`
- Modify: `app/reviews/service.py`
- Create: `tests/test_review_openai_client.py`
- Modify: `tests/test_wb_reviews.py`

**Interfaces:**
- Produces `generate_openai_review_reply(feedback, brand_voice_id, template, moderation, settings) -> ReviewAiGenerationResult`.
- `generate_draft` consumes this adapter and falls back to templates when OpenAI is unavailable.

- [ ] Add failing adapter tests for structured output parsing and no-key fallback.
- [ ] Add failing service test that safe ratings become draft-only rather than ready-to-send.
- [ ] Run focused tests and confirm failure.
- [ ] Implement config, adapter, service integration, prompt trace metadata, and draft-only send state.
- [ ] Run focused tests and confirm pass.

### Task 5: Scheduler Task

**Files:**
- Modify: `app/infra/celery_app.py`
- Modify: `app/repricer_tasks.py` or create `app/review_tasks.py`
- Modify: `app/main.py` if task import registration is needed
- Create: `tests/test_review_tasks.py`

**Interfaces:**
- Produces Celery tasks `reviews.sync_for_org` and `reviews.sync_all_orgs`.

- [ ] Add failing task tests for disabled settings, interval-not-due, and due sync.
- [ ] Run focused tests and confirm failure.
- [ ] Implement task functions and beat schedule entry.
- [ ] Run focused tests and confirm pass.

### Task 6: Verification

**Files:**
- No production files unless a failing verification reveals a bug.

- [ ] Run `pytest -q tests/test_wb_reviews.py tests/test_review_openai_client.py tests/test_review_tasks.py tests/test_infra_baseline.py`.
- [ ] Run `python -m py_compile app/reviews/*.py app/routers/wb_reviews.py app/wb_api/feedbacks_runtime.py`.
- [ ] Confirm no code path calls live WB answer endpoints when `dryRun` is false and feature is not implemented.
