# Manual WB Source Backfill Design

## Goal

Allow an operator to backfill only the missing WB sources for a selected period from the repricer UI without resetting or restarting the full cold onboarding flow.

The immediate recovery case is loading `baskets` with daily detail for the 30-day onboarding window after an aggregate-only baskets cache was saved.

## Current State

The repricer products toolbar already has:

- A cold full sync button that starts `POST /api/v1/wb-repricer/sync/run` with `mode: "onboarding"`.
- A manual sync path on the same endpoint with `mode: "manual"`, `sources`, `periodDays`, `dateFrom`, and `dateTo`.
- A visible sync status panel that polls `/api/v1/wb-repricer/sync/status`.

The gap is that manual sync always sends `baskets_include_daily_detail=False` on the backend, so it cannot repair a missing daily baskets cache.

## UX

Add a `Manual backfill` action in the WB data toolbar near the cold sync controls.

Clicking it opens a focused modal:

- Period preset: current selected period, 7 days, 30 days, 180 days, or custom dates.
- Source checkboxes: goods, content, stocks, period-stats, finance, ads, baskets.
- When `baskets` is selected, show `Daily baskets detail`.
- `Daily baskets detail` defaults to enabled for current, 7-day, and 30-day periods; it defaults to disabled for 180 days.

The modal should make the selected operation explicit, for example: `Корзины · 30 дней · дневная детализация`.

## Backend API

Extend `RepricerSyncRunRequest` with:

```json
{
  "basketsDailyDetail": true
}
```

Manual mode should pass this flag to:

- `begin_wb_sync(..., baskets_daily_detail=...)`
- `_refresh_wb_data_sources_and_flush(..., baskets_include_daily_detail=...)`

The default remains `false` to preserve current regular manual sync behavior.

## Data Flow

1. User opens manual backfill modal.
2. Frontend posts to `/api/v1/wb-repricer/sync/run` with `mode: "manual"`, the chosen period, sources, and `basketsDailyDetail`.
3. Backend queues/runs the existing manual WB sync path.
4. Existing status polling displays progress.
5. When sync finishes, the products table reloads, cache coverage is invalidated, and report islands are asked to refresh.

## Error Handling

- If another WB sync is running, show the existing `409 WB_SYNC_RUNNING` message and open sync details.
- If no access token is present, show the existing authorization warning.
- If `basketsDailyDetail` is true but baskets is not selected, backend should ignore the flag.
- The full cold sync button remains unchanged.

## Testing

Keep tests narrow:

- Backend request model/manual endpoint test that `basketsDailyDetail=true` reaches `refresh_wb_data_sources`.
- Frontend API helper test that posts `basketsDailyDetail`.
- Minimal UI behavior can be covered by typecheck/build if component-level tests are too heavy.
