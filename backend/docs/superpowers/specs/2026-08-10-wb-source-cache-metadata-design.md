# WB source cache metadata

## Problem

`wb_repricer_source_cache.payload` is stored as PostgreSQL `JSON` and moved to
TOAST for large WB snapshots. Range readiness checks currently cast every
matching payload to `jsonb` and enumerate `dailyAggregates`. The API and Celery
worker can run this query concurrently, causing the same compressed documents
to be expanded several times. Production evidence showed multi-gigabyte
PostgreSQL backends, high CPU use, and an OOM kill.

## Design

Store the fields needed for cache discovery directly on
`wb_repricer_source_cache`:

- `range_date_from` and `range_date_to`;
- `daily_detail_status` and the associated error/timestamp fields;
- `daily_detail_requests_completed` and `daily_detail_requests_total`;
- `daily_aggregate_dates`, containing only date strings.

`save_source_cache` derives these fields from the in-memory payload before the
payload is serialized. Range listing reads only the metadata columns and never
touches `payload`. An index on organization, source key, and fetch time supports
the prefix-and-recency lookup.

## Existing rows

The migration adds nullable columns and the index but does not parse or rewrite
existing payloads. This avoids expanding all existing TOAST data during deploy.
For legacy rows, range dates are parsed from ranged source keys where possible.
Legacy rows without daily-date metadata are treated conservatively as not fully
ready and are refreshed by the existing sync flow. Saving the refreshed cache
populates metadata normally.

## Concurrency

Both API and worker may request readiness at the same time, but the new query is
small and bounded because it reads metadata only. Existing job reuse remains the
guard against duplicate WB collection jobs; this change removes the database
memory amplification from readiness polling.

## Verification

A focused store test verifies that metadata is derived during save and that the
range-list query does not reference or cast `payload`. Migration upgrade and
downgrade are checked through the repository's existing Alembic conventions.
