# Task 5: Frontend Stale and Source Cache Miss UX Report

## Status

DONE_WITH_CONCERNS

## Scope Delivered

- Updated `D:\ogni-frontend\frontend\src\features\vella-parity\VellaHtmlParityPage.tsx`.
- Added `D:\ogni-frontend\frontend\src\features\vella-parity\reportSourceCacheMiss.test.ts`.
- Did not modify backend files.

## Implementation

- Exported `reportHasSourceCacheMiss(report: unknown)` and `reportSourceCacheMissMessage(report: unknown)` with the required Russian copy and `missingSources` rendering.
- Source cache misses now remain ready report states for RNP, P&L, expenses, ads, stock, and week-over-week instead of becoming frontend errors or long loading states.
- Existing ready reports are retained while the RNP, P&L, expenses, ads, and stock loaders refresh.
- Added source-cache-miss titles to all six report source strips without changing report layouts.
- Week-over-week returns the cache-miss report as ready before it can schedule/start the background report job.

## TDD Evidence

1. Created the focused Vitest contract test first.
2. Ran `npm test -- --run src/features/vella-parity/reportSourceCacheMiss.test.ts` before implementation.
3. Confirmed the expected RED failure: `reportHasSourceCacheMiss is not a function`.
4. Implemented the exported helpers and consumer state/title handling.
5. Reran the focused test successfully.

## Verification

- `npm test -- --run src/features/vella-parity/reportSourceCacheMiss.test.ts`: PASS, 1 file and 2 tests.
- `npx tsc -b --noEmit`: PASS.
- `git diff --check`: PASS before commit.

## Commit

- `e13ca3e feat: show report source cache miss state`

## Concerns

- The focused test verifies the public helper contract only. No existing component/API fixture was available for exercising each report island against a real `source_cache_miss` response end to end.
- Existing report-job request behavior was preserved except for the week-over-week cache-miss early return; this task intentionally did not redesign background-job triggering.

## Review Fix: Missing Metrics

### Root Cause

Source-cache-miss reports intentionally enter the ready state. The RNP, expenses, ads, and week-over-week cards then aggregated their empty row arrays, converting unavailable source data into numeric zeroes.

### Fix

- Added exported `reportSourceCacheMissMetricValue(report, fallback)` to return `нет данных` when the report has `cache.status = "source_cache_miss"`.
- Added explicit unavailable metric card branches for RNP, expenses, ads KPI cards, ads summary cards, and week-over-week signals.
- Preserved the ready state, report layout, and all six source-strip cache-miss messages.
- No cache-miss metric card now derives a displayed zero, percent, SKU count, campaign count, click count, document count, or WoW total from empty source-cache-miss rows.

### TDD Evidence

1. Extended the focused test with source-cache-miss numeric fallbacks (`0%` and `0 SKU`).
2. Confirmed the expected RED failure: `reportSourceCacheMissMetricValue is not a function`.
3. Implemented the pure display guard and the four metric-surface branches.

### Verification

- `npm test -- --run src/features/vella-parity/reportSourceCacheMiss.test.ts`: PASS, 1 file and 3 tests.
- `npx tsc -b --noEmit`: PASS.
- `git diff --check`: PASS before commit.

### Commit

- `e2bbbfe fix: avoid zero metrics on source cache miss`

## Re-review Fix: P&L Missing Metrics

### Root Cause

P&L source-cache-miss reports are ready with empty rows. The workbench and cost panel summed those rows, while the status grid rendered `rows.length`, producing visible zero metrics.

### Fix

- Added source-cache-miss branches to the P&L workbench KPI flow, status grid, and operational-cost panel.
- Replaced P&L zero currency, zero row count, and zero cost displays with `нет данных` or an explicit source-cache-miss state.
- Kept the P&L report ready and preserved its layout and source-strip message.
- Extended the focused helper test with `0 ₽` and `Строки: 0` fallbacks.

### Verification

- `npm test -- --run src/features/vella-parity/reportSourceCacheMiss.test.ts`: PASS, 1 file and 3 tests.
- `npx tsc -b --noEmit`: PASS.
- `git diff --check`: PASS before commit.

### Commit

- `179d922 fix: show unavailable pnl cache miss metrics`

## Final Frontend Review Fix

### Fix

- RNP and expenses retain an already-ready report during empty background-refresh responses.
- P&L, expenses, ads, and stock source-cache-miss metadata now renders unavailable text rather than fabricated zero row/article counts.
- Added focused static-render coverage for the four affected source strips.

### Verification

- `npm test -- --run src/features/vella-parity/reportSourceCacheMiss.test.ts`: PASS, 1 file and 4 tests.
- `npx tsc -b --noEmit`: PASS.
- `git diff --check`: PASS.

### Commit

- `9e7371e fix: retain reports during empty refresh`
