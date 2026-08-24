# Baskets Detail Job Design

## Goal

Keep the regular WB sync fast by loading only period-level basket aggregates, while loading per-day basket detail on demand for the date range applied by the user.

## Fast sync

The baskets source calls `fetch_baskets_aggregates(..., include_daily=False)`. It reports heartbeat after every SKU batch with processed and total SKU counts. The resulting cache remains the authoritative period aggregate used by the product table, strategies, and warmup release.

## Detail job

Dedicated endpoints start and inspect a basket-detail background run for one organization and exact date range. A run has a stable run ID, state, date range, request counters, current day, current SKU batch, percentage, message, timestamps, and error. Completed detail is stored in the matching `baskets_<period-suffix>` cache under `dailyAggregates` without replacing its aggregate totals.

A fresh completed cache for the exact range is returned without starting duplicate upstream work. Only one detail run per organization executes at once; a new range receives a new run ID after the previous run finishes.

## Frontend

Applying a product date range starts or reuses the detail job, then polls status. A visible loader shows `requestsCompleted/requestsTotal`, percentage, current day, and current SKU batch. On completion the product/report data reloads. Changing the selected range stops polling the previous run and follows the new run.

## Failure behavior

Each upstream request updates heartbeat before and after execution. WB errors finish the detail run as failed and remain visible in the loader. The regular aggregate basket cache and regular WB sync are not invalidated by a detail failure.
