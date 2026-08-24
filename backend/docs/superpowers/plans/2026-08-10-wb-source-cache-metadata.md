# WB Source Cache Metadata Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stop WB cache readiness checks from expanding large JSON payloads in PostgreSQL memory.

**Architecture:** Persist discovery metadata in nullable columns on the existing source-cache row. New writes populate the columns from the already-loaded Python payload, while reads use only metadata and derive legacy date ranges from ranged source keys.

**Tech Stack:** Python, SQLAlchemy 2, PostgreSQL 16, Alembic, pytest.

## Global Constraints

- Do not parse or rewrite existing payloads during migration.
- Do not read or cast `payload` in range-list queries.
- Keep legacy rows discoverable from their source keys.
- Add only focused tests for the changed store behavior.

---

### Task 1: Persist source-cache metadata

**Files:**
- Create: `alembic/versions/20260810_0017_source_cache_metadata.py`
- Modify: `app/repricer_cache/orm.py`
- Modify: `app/repricer_cache/store.py`
- Test: `tests/test_repricer_cache_store.py`

**Interfaces:**
- Consumes: `save_source_cache(organization_id: int, source_key: str, payload: dict[str, Any])`.
- Produces: `_source_cache_metadata(source_key: str, payload: dict[str, Any]) -> dict[str, Any]` and nullable ORM metadata fields.

- [x] Write a failing test showing metadata dates, status, counters, and daily dates are derived without changing the payload.
- [x] Run the focused test and confirm the missing helper/fields cause failure.
- [x] Add nullable columns and an organization/key/fetch-time index in an Alembic migration, without an `UPDATE` backfill.
- [x] Add matching ORM fields and populate them in both insert and update branches of `save_source_cache`.
- [x] Run the focused test and commit the task.

### Task 2: Make range discovery payload-free

**Files:**
- Modify: `app/repricer_cache/store.py`
- Test: `tests/test_repricer_cache_store.py`

**Interfaces:**
- Consumes: metadata columns from Task 1.
- Produces: unchanged `list_source_cache_ranges_by_prefix(...) -> list[dict[str, Any]]` response shape.

- [x] Write a failing test asserting the range query contains no `payload`, `jsonb`, or `jsonb_object_keys` access and parses legacy ranged source keys.
- [x] Run the focused test and confirm it fails against the existing SQL.
- [x] Select metadata columns only, parse legacy source-key dates, and conservatively leave missing daily-detail metadata incomplete.
- [x] Run the focused tests plus Alembic import validation.
- [x] Inspect the diff, run `git diff --check`, and commit the completed fix.
