# Runtime report route contract implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the four runtime WB report GET operations have the same real handler in dispatch and OpenAPI, without changing domain handlers or standalone reference contracts.

**Architecture:** `app.main` already mounts real `wb_reports_sprint_d` before the reference adapter. `wb_19_05` then mounts four duplicate stubs: runtime dispatch selects the first real route, but OpenAPI describes the last stub and loses PNL's `source` parameter. Exclude only those superseded reference GET routes from the adapter's local copied routes. Do not suppress warnings or invent operation IDs to conceal duplicate operations.

**Tech Stack:** Existing FastAPI/APIRouter, pytest/httpx; no dependencies, DB or service needed.

**Spec:** Binding local decision in this document, derived from actual `app/main.py`, `app/routers/wb_19_05.py`, real `wb_reports_sprint_d.py` and `backend_contracts/vella_wb_19_05/router.py`. Those sources must be read before edits. No separate spec is necessary for this bounded diagnosed registration fix.

## Global constraints

- T1 worktree `/Users/bratishka/Downloads/satornawb-main/.worktrees/arch-t1-platform` only; no external network/providers/Redis/production/.env/real credentials, push/deploy or host changes.
- No domain report math/data/provider adapter edits, no frontend/serverless/static generated contract changes. The standalone `vella_wb_19_05.router` and its source registry/repricer/reviews routes remain intact.
- Tests use own backend/.venv and scrubbed environment under network/secret-file-denying sandbox. Import/generate OpenAPI without production startup/lifespan. HTTP checks use synthetic in-process stubs and no background services.
- Keep the real runtime handler/permissions/query parameters unchanged. No broad stub retirement or activation. Duplicate findings outside these exact four paths return to controller, not automatic route removal.

## Task 1: Exclude four superseded GET stubs from runtime adapter

**Files:**
- Modify `backend/app/routers/wb_19_05.py` only reference inclusion boundary.
- Create `backend/tests/test_runtime_report_route_contract.py`.
- Create `backend/docs/superpowers/reports/2026-09-09-t1-runtime-report-route-handoff.md`.

**Consumes:** real first-match FastAPI registrations and standalone reference router; no business service contract changes.

**Produces:** exactly one GET registration in runtime app for each of:

```python
SUPERSEDED_REPORT_PATHS = frozenset({
    "/api/v1/wb-reports/pnl",
    "/api/v1/wb-reports/ads/performance",
    "/api/v1/wb-reports/rnp",
    "/api/v1/wb-reports/abc",
})
```

- [ ] Step1 write RED: full runtime app routes have one operation for each exact path/GET, endpoint is real module's corresponding function, OpenAPI PNL contains `source` with preliminary default and actual accepted enum, all actual date/group/filter parameters unchanged. Compare expected parameter schema to standalone app containing only real report router, not handwritten duplicate schemas. Capture original four duplicate warning IDs as defect evidence, not accepted warnings.

```python
for path in SUPERSEDED_REPORT_PATHS:
    matches = [route for route in app.routes
               if getattr(route, "path", None) == path
               and "GET" in (getattr(route, "methods", None) or ())]
    assert len(matches) == 1
    assert matches[0].endpoint.__module__ == "app.routers.wb_reports_sprint_d"
assert app.openapi()["paths"]["/api/v1/wb-reports/pnl"]["get"]["parameters"] == real_only_schema["paths"]["/api/v1/wb-reports/pnl"]["get"]["parameters"]
```

- [ ] Step2 run expected assertion RED before implementation. Implement filtering only the runtime adapter's copied GET-only routes after `include_router(reference_router)`; preserve source router object/list and all other local/reference routes. Use exact path+method matching. Do not remove future POST methods by path-only filtering, mutate shared reference routes, change main ordering or clear unrelated OpenAPI cache as a fix.

```python
router.include_router(reference_router)
router.routes[:] = [route for route in router.routes
    if not (getattr(route, "path", None) in SUPERSEDED_REPORT_PATHS
            and getattr(route, "methods", None) == {"GET"})]
```

Constants may use private naming to avoid public API expansion; no route helper abstraction needed. The test must fail if future mixed-method registration restores a duplicate GET; such a change requires explicit review rather than silently deleting the other method.

- [ ] Step3 GREEN plus synthetic in-process HTTP checks. Directly stub the real report module's actor/permission/data boundaries: unauthorized request remains denied before report data access; authorized request reaches the same real handler with provided source/date values. Never invoke seller APIs, file/default business stores or startup jobs. Instantiate TestClient without application lifespan if needed and close naturally. Independently mount original reference router into a fresh app and verify all seven original paths/handlers remain, including the four reference report stubs. Verify adapter's source-registry endpoints and non-report reference operations unchanged.

```sh
.venv/bin/python -m pytest -q tests/test_runtime_report_route_contract.py
.venv/bin/python -m compileall -q app/routers/wb_19_05.py tests/test_runtime_report_route_contract.py
git diff --check
```

Run relevant existing report API/contract tests selected by file discovery once; preserve any preexisting failures as exact baseline evidence, no skips or fixture weakening. Scoped Ruff may use approved lint-only `/tmp/satorna-backend-verify-20260908/bin/python -m ruff check`; never use it as application runtime.

- [ ] Step4 self-review, bounded commit `fix: align runtime report routes with OpenAPI`, exact commands/exit codes/RED→GREEN handoff, independent task review. This closes only duplicate runtime registration, not complete generated frontend contract parity or full suite baseline.

## Preflight

Single task touches only runtime composition and its tests/report. Real handlers and standalone contracts are read-only dependencies. Unique runtime operation and untouched standalone reference router assertions jointly prevent overbroad deletion. Local source count currently seven reference routes; test source-preservation should compare the exact pre-import route inventory rather than freeze seven forever. No secret/network/production action is required.
