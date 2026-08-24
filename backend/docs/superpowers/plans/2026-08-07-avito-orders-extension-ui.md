# Avito Orders Extension UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Redesign the Avito extension popup and `/avito/orders` empty/data states.

**Architecture:** Keep the extension as static HTML/CSS/JS with tabs controlled by `popup.js`. Keep frontend changes scoped to `VellaHtmlParityPage.tsx` and route-level parity tests.

**Tech Stack:** Chrome MV3 extension, vanilla JS, React/TypeScript Vella parity page, Vitest.

## Global Constraints

- Do not expose technical logs on default screens.
- Keep Avito collection settings available under Settings.
- Show the frontend onboarding only when extension data is absent.
- Commit every completed repo change.

---

### Task 1: Extension Popup

**Files:**
- Modify: `avito-orders-extension/src/popup.html`
- Modify: `avito-orders-extension/src/popup.css`
- Modify: `avito-orders-extension/src/popup.js`
- Test: `avito-orders-extension/tests/popup-ui.test.mjs`

**Interfaces:**
- Consumes: existing `chrome.storage.sync`, `chrome.runtime.sendMessage`.
- Produces: `data-screen="collect|settings"` UI state and logs rendered only in diagnostics.

- [ ] Write tests for default collect screen and settings logs placement.
- [ ] Run `node --test tests/popup-ui.test.mjs` and confirm failure.
- [ ] Implement screen tabs, grouped settings, and refined visual styles.
- [ ] Run popup tests and `npm run build`.

### Task 2: Avito In-Page Overlay

**Files:**
- Modify: `avito-orders-extension/src/content.js`
- Test: covered by `npm run build` syntax and existing collector tests.

**Interfaces:**
- Consumes: existing collector stats.
- Produces: less technical overlay copy.

- [ ] Replace technical overlay labels with operator-facing text.
- [ ] Keep detailed errors in logs.
- [ ] Run `npm run build`.

### Task 3: Frontend Orders Page

**Files:**
- Modify: `ogni-react-frontend/frontend/src/features/vella-parity/VellaHtmlParityPage.tsx`
- Test: `ogni-react-frontend/frontend/src/features/vella-parity/avitoLiveIntegration.test.ts`

**Interfaces:**
- Consumes: `browserSnapshot`, `rows`, `extensionTokenStatus`.
- Produces: onboarding-only view when no extension rows exist; production view without KPI strip when rows exist.

- [ ] Add tests that removed KPI labels and browser diagnostics are absent.
- [ ] Run focused frontend test and confirm failure.
- [ ] Remove KPI strip, hide collector note on data view, add onboarding-only branch.
- [ ] Run focused frontend test and available type/build checks.
