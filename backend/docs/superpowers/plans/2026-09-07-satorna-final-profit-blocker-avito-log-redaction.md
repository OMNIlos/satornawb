# Satorna final-profit boundary and Avito log-redaction plan

> Status: complete. Executed in the existing isolated worktree
> `backend-satorna-canonical-advertising`; preserve its runtime-state change and
> `.venv` symlink.

**Goal:** Prove whether canonical final net profit and profit ABC can be
implemented without invented business rules, then ship the smallest safe
evidence-backed slice when they cannot.

**Decision:** Keep `netProfitKopecks`, `profitClass` and `abcCode` null. The
canonical row currently ends at `profitAfterLoyaltyKopecks`; it does not consume
1C operational expenses, and no approved SKU allocation or final-profit rule
exists. The next bounded slice removes Avito order response bodies from logs
while retaining status, request metadata and order count diagnostics.

## Evidence boundary

- `product-docs/README.md` explicitly excludes final P&L without Maxim's
  formulas.
- The unit-P&L PRD allows unallocated expenses to remain unallocated or use an
  approved revenue/orders/stocks rule; that choice and final source remain
  open.
- The formula catalog confirms only the sales ABC thresholds. Profit ABC still
  needs final profit inputs; the source registry remains `needs_client`.
- Production schema `20260905_0060` contains 503 completed organization-2 1C
  jobs and 4,016 operational-expense rows across 347 jobs. The table has no
  marketplace-account key and PostgreSQL RLS is disabled. Applying these rows
  to SKU profit would require an unapproved allocation and tenant/account
  boundary.
- Legacy ABC ranks row positions and has no authoritative tie, zero or negative
  profit policy. It is evidence of old behavior, not a final business contract.
- `app/avito/orders.py` puts the entire Avito response into `bodyPreview` and
  logs it on every fetch. Production worker logs contained 86
  `[AVITO_ORDERS_BODY]` lines in the inspected 24-hour window.

## Task 1: Lock the final-profit blocker

- [x] Trace canonical finance, economics, advertising, loyalty and summary
  arithmetic end to end.
- [x] Check product contracts, formula catalogs, open questions and legacy
  behavior for thresholds, ties, zero/negative profit and page independence.
- [x] Verify the omitted 1C expense domain against production using a read-only
  transaction.
- [x] Leave final fields null and retain
  `WB_PNL_CLASSIFICATION_NOT_CANONICAL`; do not add a speculative formula.

## Task 2: Remove the Avito log sink with TDD

**Files:**

- Modify: `tests/test_avito_orders.py`
- Modify: `app/avito/orders.py`

- [x] Add one end-to-end `caplog` regression proving a synthetic buyer name,
  phone/address and nested payload value reach the current log sink.
- [x] Run that test alone and record RED.
- [x] Remove the raw body from diagnostics and delete the body-log statement at
  the shared live-client boundary. This also prevents Celery task-success logs
  from serializing the copied diagnostics. Keep response parsing, typed errors,
  status, URL/params, key names, count and reason behavior unchanged.
- [x] Re-run both security regressions and every non-baseline test in the Avito
  orders module: `2 passed`; then `13 passed, 2 deselected`. The two deselected
  failures reproduce independently and are exact entries in the 105-test
  legacy baseline.

## Task 3: Review and local release gates

- [x] Review every direct `fetch_orders` caller and all remaining Avito order
  log statements for a surviving response-body path or behavior regression.
- [x] Run focused Avito tests, Ruff, compileall and `git diff --check`.
- [x] Run the canonical finance/advertising gate (`110` tests) to prove the
  blocked formula path was not changed.
- [x] Run one isolated full backend suite with JUnit: `678 passed / 105 failed`
  in `273.38 s`; exact equality with `ops/legacy-test-failures.txt`, with no
  added, missing or error IDs.
- [x] Require one Alembic head, valid Git objects and only the preserved dirty
  runtime-state and `.venv` entries outside this slice.

## Task 4: Immutable production rollout

- [x] Commit the tested source before packaging. Capture current production
  source, image digest, schema, health, process state, scheduler flags, dirty
  checkout count and environment checksum.
- [x] Create a checksum-protected backup and rollback tags before switching any
  service. Do not build from or modify `/var/www/ogni-elfs`.
- [x] Build one image from a committed source archive and deploy that digest to
  migrate, API, default worker, canonical worker and beat.
- [x] Require migration exit `0`; health/live/ready `200`; both workers pong;
  empty active/reserved/scheduled queues; zero restarts/OOM; scheduler still
  disabled; and zero post-boundary strict error matches.
- [x] Trigger/read the existing Avito worker path without logging payload data,
  and verify post-boundary logs contain no `[AVITO_ORDERS_BODY]` marker while
  count/status diagnostics remain.
- [x] Re-run the finance-membership/account-scoped closed-day ABC/P&L service
  and response-schema canary in a PostgreSQL read-only transaction. This avoids
  the otherwise unavoidable auth-session `last_seen_at` write while proving
  null final fields, exact blockers, arithmetic, pagination and p95 <= 500 ms.

## Task 5: Record and hand off

- [x] Append exact commits, image/archive/backup checksums, health, log and
  canary evidence here.
- [x] Update `SATORNA_ARCHITECTURE_HANDOFF.md` with the final-profit blocker,
  deployed security slice, production drift and next safe boundary.
- [x] Commit only owned documentation; do not push to GitHub.

## Completion evidence — 2026-09-07

- Runtime commit is `b96e602`. The first security test reproduced the complete
  synthetic buyer/phone/address payload in `[AVITO_ORDERS_BODY]`; a second RED
  proved that copied `bodyPreview` diagnostics would still reach Celery task
  success logs. Removing those two source lines made both paths green while
  retaining typed parsing and safe status/count diagnostics.
- Focused direct-consumer tests are `21 passed, 2 deselected`; both deselected
  failures reproduce independently and are listed in the legacy baseline. The
  canonical finance/advertising gate is `110 passed`. Ruff, full compileall,
  one Alembic head, whitespace and Git object checks pass.
- One fresh isolated full backend run produced `678 passed / 105 failed / 26
  warnings` in `273.38 s`. All `105` failure IDs exactly match
  `ops/legacy-test-failures.txt`; added, missing and error sets are empty.
- Production runs committed archive
  `/var/tmp/satorna-avito-log-redaction-b96e602.tar.gz`, SHA-256
  `bb0949dd22a6be35bd2b7d2d2a95e7f1a163bb11a77f8088f961d52aa02bfac8`,
  and one image
  `sha256:0aad3379406afd344b1ede23859350752f40efe9a2e8d19a988f8431f4040fa1`
  for migrate, API, both workers and beat. Migration exits `0`; schema remains
  `20260905_0060`.
- Internal and public health/live/ready are all `200`; two workers pong and
  active/reserved/scheduled queues are empty. Live processes have zero
  restarts/OOM events and strict post-boundary log matches. Canonical collection
  remains disabled with an empty allowlist; environment SHA-256 remains
  `18b8293c1ae5dfb24e64c7a0a0fa1afd2132ccec2f08396bcd22c124ef55ca3c`.
- A read-only synthetic fetch inside the production worker emitted status `200`
  and count `1`; `[AVITO_ORDERS_BODY]` and every synthetic PII marker were
  absent. Natural identity-level sync was not forced because it would call the
  external API and write routine return state.
- The transaction-read-only `2026-09-02` canary returned 457 rows, formula
  `wb-abc-pnl-fullstats-loyalty-v1`, source/evidence `ads_fullstats/raw`, and
  advertising arithmetic `2,283 = 2,283 + 0` kopecks. Every final field is
  null; the classification blocker is correctly withheld while exact upstream
  blockers are `WB_PNL_COST_ASSUMED`, `WB_PNL_COST_EVIDENCE_UNDATED` and
  `WB_PNL_ECONOMICS_ASSUMED`. Pagination is stable; 25 reads measured
  p50/p95/max `72.88/90.19/147.62 ms`.
- Backup
  `/var/backups/satorna-avito-log-redaction-pre-b96e602-20260907T191612Z` is
  mode `0700` with 31 files total; all 30 non-manifest checksum entries pass,
  the protected schema dump has a valid restore list, and pre/post database
  evidence is identical. Rollback tags
  `ogni-elfs-{api,worker,canonical-shadow-worker,beat,migrate}:rollback-a247504-pre-b96e602`
  point to
  `sha256:a247504bcb3db354f77fa5b11e5bbdf73127852abf912ecc400eab9dad41339a`;
  rollback is image-only because both releases use schema `0060`.
