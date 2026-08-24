# Avito Return Inventory Matching Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Persist Avito `on_return` items as reusable return inventory and enrich Avito order items with reuse suggestions.

**Architecture:** Add a focused Avito returns domain module and DB table, keep the current Avito orders endpoint as the reader-facing API, and add Celery sync tasks that periodically populate the inventory. Matching runs in-process against active return candidates and appends `reuseSuggestion`/`returnMatches` to each order item.

**Tech Stack:** FastAPI, Pydantic v2, SQLAlchemy 2, Alembic, Celery, pytest, React/TypeScript frontend.

## Global Constraints

- A return candidate becomes reusable immediately when Avito exposes `status == "on_return"` or non-empty `returnStatus`.
- Do not require physical warehouse acceptance in this version.
- Do not implement QR-code generation, courier tables, reservation, or inventory decrement.
- Preserve existing Avito orders and listings API behavior as fallback.
- Use TDD: write and run failing tests before production code.

---

### Task 1: Return Candidate Models And Matching

**Files:**
- Modify: `app/avito/orders.py`
- Create: `app/avito/returns.py`
- Test: `tests/test_avito_returns.py`

**Interfaces:**
- Consumes: `AvitoOrderRow`, `AvitoOrderItem` from `app.avito.orders`
- Produces: `AvitoReturnCandidate`
- Produces: `AvitoReturnMatch`
- Produces: `extract_return_candidates(rows: list[AvitoOrderRow]) -> list[AvitoReturnCandidate]`
- Produces: `match_return_candidates(item: AvitoOrderItem, *, order: AvitoOrderRow, candidates: list[AvitoReturnCandidate], limit: int = 3) -> list[AvitoReturnMatch]`
- Produces item fields: `returnMatches: list[AvitoReturnMatch]`, `reuseSuggestion: AvitoReturnMatch | None`

- [ ] **Step 1: Write failing extraction and exact-match tests**

```python
from app.avito.orders import AvitoOrderItem, AvitoOrderRow
from app.avito.returns import extract_return_candidates, match_return_candidates


def test_extracts_on_return_items_as_reusable_candidates():
    rows = [
        AvitoOrderRow(
            orderId="ret_1",
            marketplaceId="7001",
            accountId="acc_1",
            accountName="Bless T",
            status="on_return",
            returnStatus="started",
            updatedAt="2026-08-07T09:00:00+00:00",
            items=[
                AvitoOrderItem(
                    itemId="item_1",
                    title="Футболка белая Принт 42",
                    sellerArticle="FBBT_42",
                    size="M",
                    color="белая",
                    quantity=1,
                )
            ],
        )
    ]

    candidates = extract_return_candidates(rows)

    assert len(candidates) == 1
    assert candidates[0].returnOrderId == "ret_1"
    assert candidates[0].sellerArticle == "FBBT_42"
    assert candidates[0].size == "M"
    assert candidates[0].color == "белая"
    assert candidates[0].quantity == 1
    assert candidates[0].status == "on_return"


def test_matches_return_candidate_by_article_size_and_color():
    order = AvitoOrderRow(
        orderId="new_1",
        status="ready_to_ship",
        items=[AvitoOrderItem(title="Футболка белая Принт 42", sellerArticle="FBBT_42", size="M", color="белый")],
    )
    candidates = extract_return_candidates(
        [
            AvitoOrderRow(
                orderId="ret_1",
                marketplaceId="7001",
                status="on_return",
                items=[AvitoOrderItem(itemId="item_1", title="Футболка белая Принт 42", sellerArticle="FBBT_42", size="M", color="white")],
            )
        ]
    )

    matches = match_return_candidates(order.items[0], order=order, candidates=candidates)

    assert matches[0].returnOrderId == "ret_1"
    assert matches[0].score == 100
    assert matches[0].reason == "article_size_color"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_avito_returns.py::test_extracts_on_return_items_as_reusable_candidates tests/test_avito_returns.py::test_matches_return_candidate_by_article_size_and_color -v`

Expected: FAIL because `app.avito.returns` does not exist or matching functions are missing.

- [ ] **Step 3: Implement minimal models and exact matching**

Create `app/avito/returns.py` with Pydantic models, normalization helpers, `extract_return_candidates`, and `match_return_candidates`. Add `AvitoReturnMatch` import or local forward-safe model wiring in `app/avito/orders.py`, then add `returnMatches` and `reuseSuggestion` fields to `AvitoOrderItem`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_avito_returns.py::test_extracts_on_return_items_as_reusable_candidates tests/test_avito_returns.py::test_matches_return_candidate_by_article_size_and_color -v`

Expected: PASS.

- [ ] **Step 5: Add conflict and title-fallback tests**

```python
def test_does_not_match_when_size_or_color_conflicts():
    order = AvitoOrderRow(orderId="new_1", status="ready_to_ship", items=[AvitoOrderItem(title="Худи", sellerArticle="HCBT_17", size="L", color="черный")])
    candidates = extract_return_candidates([
        AvitoOrderRow(orderId="ret_1", status="on_return", items=[AvitoOrderItem(title="Худи", sellerArticle="HCBT_17", size="XL", color="черный")]),
        AvitoOrderRow(orderId="ret_2", status="on_return", items=[AvitoOrderItem(title="Худи", sellerArticle="HCBT_17", size="L", color="белый")]),
    ])

    assert match_return_candidates(order.items[0], order=order, candidates=candidates) == []


def test_matches_by_title_size_color_when_article_missing():
    order = AvitoOrderRow(orderId="new_1", status="ready_to_ship", items=[AvitoOrderItem(title="Лонгслив Vintage Stars", size="S", color="графит")])
    candidates = extract_return_candidates([
        AvitoOrderRow(orderId="ret_1", status="on_return", items=[AvitoOrderItem(title="лонгслив vintage stars", size="S", color="graphite")]),
    ])

    matches = match_return_candidates(order.items[0], order=order, candidates=candidates)

    assert matches[0].score == 90
    assert matches[0].reason == "title_size_color"
```

- [ ] **Step 6: Run all return model tests**

Run: `pytest tests/test_avito_returns.py -v`

Expected: PASS.

### Task 2: Database Persistence For Return Inventory

**Files:**
- Create: `app/avito/returns_orm.py`
- Create: `app/avito/returns_store.py`
- Create: `alembic/versions/20260807_0022_avito_return_items.py`
- Modify: `pyproject.toml`
- Test: `tests/test_avito_returns.py`

**Interfaces:**
- Consumes: `AvitoReturnCandidate`
- Produces: `upsert_return_candidates(organization_id: int, candidates: list[AvitoReturnCandidate]) -> dict[str, int]`
- Produces: `list_active_return_candidates(organization_id: int, limit: int = 500) -> list[AvitoReturnCandidate]`

- [ ] **Step 1: Write failing store tests with monkeypatched in-memory DB or temp SQLite if existing infra permits**

Add tests that call `upsert_return_candidates` twice with the same candidate and assert the active candidate list has one row with updated quantity/last payload.

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_avito_returns.py::test_upserts_return_candidates_without_duplicates -v`

Expected: FAIL because store/ORM are missing.

- [ ] **Step 3: Implement ORM, store, and migration**

Add `AvitoReturnItemRow` with columns from the design. Use a non-null `identity_key` string built from `account_id|order_id|item_id_or_title_size_color` and a unique constraint on `organization_id, identity_key` to avoid nullable unique issues. Update `pyproject.toml` package list only if setuptools package discovery needs explicit `app.avito`.

- [ ] **Step 4: Run store test**

Run: `pytest tests/test_avito_returns.py::test_upserts_return_candidates_without_duplicates -v`

Expected: PASS.

### Task 3: Orders Endpoint Enrichment

**Files:**
- Modify: `app/routers/avito_orders.py`
- Test: `tests/test_avito_orders.py`

**Interfaces:**
- Consumes: `list_active_return_candidates`
- Consumes: `match_return_candidates`
- Produces: enriched order items with `returnMatches` and `reuseSuggestion`
- Produces: `source.returnInventory`

- [ ] **Step 1: Write failing API enrichment test**

Add a test that monkeypatches `list_active_return_candidates` to return one matching candidate and asserts `/api/v1/avito/orders` includes `rows[0].items[0].reuseSuggestion.reason == "article_size_color"`.

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_avito_orders.py::test_avito_orders_endpoint_adds_return_reuse_suggestion -v`

Expected: FAIL because the endpoint does not call return matching.

- [ ] **Step 3: Implement enrichment helper**

Add `_enrich_orders_with_return_matches(rows: list[AvitoOrderRow], organization_id: int) -> dict[str, Any]` in `app/routers/avito_orders.py`. Call it after existing browser/listing color enrichment and before `_response_payload` serializes rows. Add `returnInventory` metadata to `source`.

- [ ] **Step 4: Run targeted API test**

Run: `pytest tests/test_avito_orders.py::test_avito_orders_endpoint_adds_return_reuse_suggestion -v`

Expected: PASS.

### Task 4: Celery Sync Tasks And Schedule

**Files:**
- Modify: `app/config.py`
- Modify: `app/infra/celery_app.py`
- Create: `app/avito/returns_tasks.py`
- Test: `tests/test_avito_returns.py`

**Interfaces:**
- Consumes: `get_organization_avito_credentials_secret`
- Consumes: `resolve_user_avito_access_token`
- Consumes: `build_avito_orders_client`
- Produces task: `avito.sync_returns_for_org`
- Produces task: `avito.sync_returns_all_orgs`
- Produces settings: `avito_returns_sync_enabled`, `avito_returns_sync_interval_minutes`, `avito_returns_period_days`

- [ ] **Step 1: Write failing task test**

Add a test that monkeypatches credentials/token/client and asserts `sync_returns_for_org.run(1, force=True)` upserts only `on_return` rows.

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_avito_returns.py::test_sync_returns_for_org_fetches_on_return_orders_and_persists_candidates -v`

Expected: FAIL because task module is missing.

- [ ] **Step 3: Implement tasks and settings**

Add settings defaults: enabled `True`, interval `15`, period days `30`. Register the task module in `app/infra/celery_app.py` and add a beat schedule entry named `avito-sync-returns` when enabled.

- [ ] **Step 4: Run task test and celery import smoke**

Run: `pytest tests/test_avito_returns.py::test_sync_returns_for_org_fetches_on_return_orders_and_persists_candidates -v`

Run: `python -c "from app.infra.celery_app import celery_app; print('avito.sync_returns_all_orgs' in celery_app.tasks)"`

Expected: test PASS and command prints `True`.

### Task 5: Frontend Suggestion Copy

**Files:**
- Modify: `C:/Users/porka/OneDrive/Рабочий стол/folders/кодерские архивы/ogni-react-frontend/frontend/public/vella-production.html`
- Modify: `C:/Users/porka/OneDrive/Рабочий стол/folders/кодерские архивы/ogni-react-frontend/frontend/src/features/vella-static/vella-source.test.ts`

**Interfaces:**
- Consumes: backend `item.reuseSuggestion`
- Produces visible copy: `В возврате есть такой же товар`

- [ ] **Step 1: Find the Avito orders table renderer**

Run: `rg -n "ordersPickingRows|orders-avito|QR/Barcode Авито|Наименование" frontend/public/vella-production.html frontend/src/features/vella-static/vella-source.test.ts`

- [ ] **Step 2: Write failing static source test**

Add an assertion that the relevant orders section contains `В возврате есть такой же товар` and reads `reuseSuggestion`.

- [ ] **Step 3: Run test to verify it fails**

Run from frontend repo: `npm test -- frontend/src/features/vella-static/vella-source.test.ts -t "orders"`

Expected: FAIL because copy/field is absent.

- [ ] **Step 4: Implement copy in the orders item renderer**

Render a compact badge near the item title when `item.reuseSuggestion` exists. Include size/color/article evidence in existing dense table/drawer style.

- [ ] **Step 5: Run frontend static test**

Run from frontend repo: `npm test -- frontend/src/features/vella-static/vella-source.test.ts -t "orders"`

Expected: PASS.

### Task 6: Final Verification

**Files:**
- All backend and frontend files touched above.

**Interfaces:**
- Produces verified feature.

- [ ] **Step 1: Run backend targeted tests**

Run: `pytest tests/test_avito_returns.py tests/test_avito_orders.py -v`

- [ ] **Step 2: Run frontend targeted tests**

Run from frontend repo: `npm test -- frontend/src/features/vella-static/vella-source.test.ts -t "orders"`

- [ ] **Step 3: Check changed files**

Run backend: `git status --short`

Run frontend: `git status --short`

- [ ] **Step 4: Commit backend changes**

Run backend: `git add app tests alembic docs pyproject.toml && git commit -m "feat: add avito return inventory matching"`

- [ ] **Step 5: Commit frontend changes**

Run frontend: `git add frontend/public/vella-production.html frontend/src/features/vella-static/vella-source.test.ts && git commit -m "feat: show avito return reuse suggestions"`

## Self-Review

Spec coverage: the plan covers return extraction, persistence, matching, API enrichment, periodic sync, frontend copy, and verification. Out-of-scope QR/reservation/warehouse acceptance remain excluded.

Placeholder scan: no TBD/TODO/fill-in-later wording remains in task steps.

Type consistency: `AvitoReturnCandidate`, `AvitoReturnMatch`, `extract_return_candidates`, `match_return_candidates`, `upsert_return_candidates`, and `list_active_return_candidates` are introduced before use.
