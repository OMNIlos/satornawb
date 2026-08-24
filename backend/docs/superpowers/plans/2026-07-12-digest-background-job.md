# Digest Background Job Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Serve WB digest data from cache while a Celery task computes each requested date range in the background.

**Architecture:** Persist per-range job state and finished digest payloads in the existing source-cache store. A Celery task performs the present expensive digest collection. Read, refresh, and status endpoints remain fast; the parity page starts a task and polls it without chunking the range.

**Tech Stack:** FastAPI, Celery, existing source-cache store, pytest, React/TypeScript.

## Global Constraints

- No WB network calls on `GET /api/wb/reports/digest`.
- Status and cache keys are organization- and exact-range-scoped.
- A running range must be deduplicated.
- A range change must only update the UI for the newly selected range.

---

### Task 1: Backend digest cache and job lifecycle

**Files:**
- Modify: `app/routers/wb_reports_bff.py`
- Modify: `app/repricer_tasks.py`
- Test: `tests/test_wb_reports_bff.py`
- Test: `tests/test_repricer_tasks.py`

**Interfaces:**
- Produces `GET /api/wb/reports/digest`, `POST /api/wb/reports/digest/refresh`, and `GET /api/wb/reports/digest/status`.
- Produces Celery task `reports.build_digest_for_org(organization_id, date_from_iso, date_to_iso, finance_allowed, wb_token)`.

- [ ] **Step 1: Write failing backend tests**

```python
def test_digest_read_returns_cached_payload_without_building_sources(monkeypatch):
    monkeypatch.setattr(module, "get_source_cache", lambda *_args, **_kwargs: {"digest": {"meta": {"id": "digest"}}})
    monkeypatch.setattr(module, "build_wb_reports_sources_snapshot", lambda **_kwargs: pytest.fail("must not call WB"))
    response = api.get("/api/wb/reports/digest", headers=auth_headers(api, "viewer"))
    assert response.status_code == 200
    assert response.json()["cache"]["status"] == "exact"

def test_digest_refresh_reuses_running_job(monkeypatch):
    monkeypatch.setattr(module, "get_source_cache", lambda *_args, **_kwargs: {"state": "running", "taskId": "task-1"})
    response = api.post("/api/wb/reports/digest/refresh", headers=auth_headers(api, "viewer"))
    assert response.json()["taskId"] == "task-1"
    assert response.json()["reused"] is True
```

- [ ] **Step 2: Run tests to verify RED**

Run: `pytest -q tests/test_wb_reports_bff.py -k "digest_read_returns_cached or digest_refresh_reuses"`

Expected: FAIL because cache-only response and refresh endpoint do not exist.

- [ ] **Step 3: Implement minimal lifecycle**

```python
def _digest_job_cache_key(date_from: date, date_to: date) -> str:
    return f"reports_digest_job_{date_from.isoformat()}_{date_to.isoformat()}"

@router.post("/api/wb/reports/digest/refresh")
def refresh_reports_digest(...):
    # return existing queued/running record, otherwise persist queued record and .delay task

@router.get("/api/wb/reports/digest/status")
def get_reports_digest_status(...):
    # return exact job record or idle state
```

The Celery task marks `running`, builds the existing snapshots, saves the digest, marks `completed`, and marks `failed` with `str(exc)[:500]` on exception.

- [ ] **Step 4: Run backend tests to verify GREEN**

Run: `pytest -q tests/test_wb_reports_bff.py tests/test_repricer_tasks.py`

Expected: PASS.

### Task 2: Digest parity page background-job client

**Files:**
- Modify: `D:/ogni-frontend/frontend/src/features/vella-parity/VellaHtmlParityPage.tsx`
- Test: `D:/ogni-frontend/frontend/src/features/vella-parity/VellaHtmlParityPage.test.tsx` or the existing frontend test suite.

**Interfaces:**
- Consumes digest response field `cache` and `digestJob` and the refresh/status endpoints from Task 1.
- Produces an updating/fallback status in the Digest API debug panel and reloads completed data.

- [ ] **Step 1: Write failing frontend test**

```ts
it('loads cached digest, requests background refresh, and reloads on completion', async () => {
  // mock GET digest -> cache fallback, POST refresh -> running, GET status -> completed
  // assert fallback data renders and a final GET digest is made after completion
})
```

- [ ] **Step 2: Run frontend test to verify RED**

Run: `npm test -- VellaHtmlParityPage`

Expected: FAIL because the page still runs direct, chunked digest requests.

- [ ] **Step 3: Implement the job bridge**

```ts
const digest = await apiRequest<DigestResponse>(path, { headers })
await apiRequest<DigestJob>(`${pathBase}/refresh?...`, { method: 'POST', headers })
// poll `${pathBase}/status?...` every 3s; reload only if requestKey still matches
```

Remove `chunkDateRanges`, the per-chunk 600-second controller, and merging from the digest loading path. Render `digestJob.state` and `cache.status` as `Обновляется` / `Последние готовые данные`.

- [ ] **Step 4: Run frontend test/build to verify GREEN**

Run: `npm test -- VellaHtmlParityPage` and `npm run build`

Expected: PASS.

### Task 3: End-to-end regression verification

**Files:**
- Modify: `tests/test_wb_reports_bff.py` only if a missing regression assertion is discovered.

- [ ] **Step 1: Verify backend API contract**

Run: `pytest -q tests/test_wb_reports_bff.py tests/test_repricer_tasks.py tests/test_infra_baseline.py`

Expected: PASS.

- [ ] **Step 2: Verify frontend types and production build**

Run: `npm run build`

Expected: exit code 0.

- [ ] **Step 3: Commit implementation**

```bash
git add app/repricer_tasks.py app/routers/wb_reports_bff.py tests/test_wb_reports_bff.py tests/test_repricer_tasks.py
git commit -m "feat: build wb digest in background"
git -C D:/ogni-frontend add frontend/src/features/vella-parity/VellaHtmlParityPage.tsx
git -C D:/ogni-frontend commit -m "feat: poll wb digest background job"
```
