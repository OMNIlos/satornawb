# Live Week-over-Week Report

## Goal

Make `/wb/reports/week-over-week` use the existing WB report sources and the existing background-report job pattern while preserving the current visual layout exactly.

## Backend

- Add `week-over-week` to the background report allowlist.
- Reuse the existing report job cache key, report payload cache key, Celery task, and job polling endpoints.
- Build two equal date ranges: requested range and the immediately preceding range of the same length.
- Reuse existing orders, sales, ads, product, and stock sources; do not add a new WB integration.
- Return the current physical values and percent deltas for price, orders, sales, baskets, margin, and profit.
- Return `wasOutOfStock` and `stockAvailability7d` from the internal stock snapshot history, with an explicit history source/state when coverage is incomplete.
- Preserve stale cached data while a refresh is queued/running and expose safe failure state through `reportJob`.
- Keep `POST /api/wb/reports/week-over-week/jobs` and `GET /api/wb/reports/week-over-week/jobs` compatible with the existing report job API.

## Frontend

- Keep the current WoW layout, labels, classes, and column order.
- Replace hardcoded signal cards, mock rows, and legacy `renderSecondaryReports` binding with the live report response.
- Start/reuse the WoW background job, fetch the cached response, and poll while it is queued/running.
- Render loading, stale/updating, partial/no-history, and error states without inventing numeric values.
- Keep the existing filters and export action, applying them to backend rows and the existing export endpoint.

## Data rules

- `deltaPct = (current - previous) / abs(previous) * 100`; when the previous value is unavailable or zero, return `null` and render an unavailable delta.
- Profit and margin use the existing backend-derived report values; they must not be replaced by seller revenue.
- Price remains a recommendation/context field; no SPP assumption or automatic price application is introduced.
- Missing historical stock days are marked as incomplete/backfilled and are not presented as captured WB history.

## Verification

- Backend tests cover date-range pairing, metric deltas, cache-only GET, job deduplication, task completion/error state, and WoW response shape.
- Frontend tests cover live fetch/job polling, removal of mock values, real-row rendering, and filter behavior.
- Run focused backend pytest, frontend unit tests/typecheck, and a rendered route smoke check if the local frontend workflow is available.
