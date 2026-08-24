# Avito Orders Extension Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a Chrome MV3 browser collector for Avito orders and merge collected photos, sizes, colors, and articles into the existing Avito orders table and picking XLSX.

**Architecture:** Keep the backend as the data hub. Add a browser snapshot model and endpoint, merge browser data into API rows before returning JSON and before generating XLSX, and create a static extension project at `../avito-orders-extension`.

**Tech Stack:** FastAPI, Pydantic, existing source cache, React/TypeScript frontend, Chrome Manifest V3 static JavaScript extension.

## Global Constraints

- Keep the current Avito Orders API flow as fallback.
- Do not use Next.js for the extension.
- Do not load remote JavaScript in the extension.
- Prefer Avito stable DOM selectors and text fallbacks over hashed classes.
- Keep verification light and targeted.

---

### Task 1: Backend Snapshot Ingestion And Merge

**Files:**
- Modify: `app/avito/orders.py`
- Modify: `app/routers/avito_orders.py`
- Test: `tests/test_avito_orders.py`

**Interfaces:**
- Produces: `AvitoOrdersBrowserSnapshot`, `AvitoOrdersBrowserOrder`, `AvitoOrdersBrowserItem`
- Produces: `merge_browser_snapshot_orders(rows: list[AvitoOrderRow], snapshot: AvitoOrdersBrowserSnapshot | None) -> None`
- Produces endpoint: `POST /api/v1/avito/orders/browser-snapshot`

- [ ] Write failing tests for accepting a browser snapshot and merging `imageUrl`, `size`, `color`, `sellerArticle`.
- [ ] Run targeted backend tests and confirm they fail because endpoint/merge is missing.
- [ ] Implement models, merge helper, cache key, endpoint, and response/XLSX merge calls.
- [ ] Run targeted backend tests and confirm they pass.

### Task 2: Extension Static Project

**Files:**
- Create: `../avito-orders-extension/manifest.json`
- Create: `../avito-orders-extension/src/content.js`
- Create: `../avito-orders-extension/src/background.js`
- Create: `../avito-orders-extension/src/popup.html`
- Create: `../avito-orders-extension/src/popup.js`
- Create: `../avito-orders-extension/src/popup.css`
- Create: `../avito-orders-extension/README.md`

**Interfaces:**
- Consumes: `POST /api/v1/avito/orders/browser-snapshot`
- Produces message: `{ type: "AVITO_ORDERS_COLLECTED", payload: { capturedAt, pageUrl, orders } }`

- [ ] Create a no-build MV3 extension with Avito content script, background poster, and popup settings.
- [ ] Implement DOM extraction using selector candidate helpers.
- [ ] Implement deterministic parsing for color, size, article, image, order id, track number, buyer, delivery, and item URL.
- [ ] Add README with local install steps.

### Task 3: Frontend Integration Copy And Download Behavior

**Files:**
- Modify: `../ogni-react-frontend/frontend/src/features/vella-parity/VellaHtmlParityPage.tsx`
- Modify: `../ogni-react-frontend/frontend/src/features/vella-parity/avitoOrdersXlsx.ts`

**Interfaces:**
- Consumes: backend source metadata `source.browserSnapshot`

- [ ] Add user-facing status copy on `/avito/orders` explaining that browser collector data will enrich picking lists when available.
- [ ] Keep existing XLSX button path unchanged, because backend merge handles enriched data.
- [ ] Run light frontend type/test check for Avito orders files if available.

### Task 4: Commit And Verification

**Files:**
- Backend, frontend, and extension files from Tasks 1-3.

- [ ] Run targeted backend tests for Avito orders.
- [ ] Run targeted frontend tests for Avito XLSX/link behavior if not too slow.
- [ ] Check git status in backend, frontend, and extension.
- [ ] Commit backend changes.
- [ ] Commit frontend changes.
- [ ] Commit extension changes if it is a git repo; otherwise leave it as a new sibling folder and report that it is outside git.
