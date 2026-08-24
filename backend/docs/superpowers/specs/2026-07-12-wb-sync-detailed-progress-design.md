# WB Sync Detailed Progress Design

## Goal

Speed up the external 41-SPP enrichment by restoring batches of 100 SKUs and expose live, human-readable progress for every source in the eight-stage WB sync.

## Backend contract

Each sync step may expose `progressPercent`, `progressCurrent`, `progressTotal`, `phase`, `message`, and `request`. These fields are additive and optional for backward compatibility. No token or complete nmID list may be persisted in status.

The goods step updates its heartbeat after a WB catalog page and after every 41-SPP batch. The SPP client accepts at most 100 unique nmIDs per request and waits ten seconds between requests. A progress callback receives completed and total item counts plus the current batch number.

Every other source publishes a start message and reaches 100 percent on success, skip, or error. Where an upstream API does not reveal its total work in advance, the UI presents phase progress rather than a fabricated row count.

## Frontend

The existing aggregate progress remains compact. A button below it expands a persistent detail panel containing all requested sources in order. Each row shows a localized source label, state, progress bar, percentage, message, safe request description, and error when present.

## Failure and stale behavior

Heartbeat writes are part of normal progress persistence. A failure to fetch SPP remains non-fatal for the goods cache, while an ordinary status persistence failure follows the existing sync failure behavior. Frequent heartbeat updates prevent an active goods step from being classified as stale.

## Verification

Backend tests cover 201 nmIDs splitting into 100, 100, and 1; callback progress; heartbeat persistence; and status fields. Frontend type-checking and focused tests cover normalization/rendering of detailed progress.
