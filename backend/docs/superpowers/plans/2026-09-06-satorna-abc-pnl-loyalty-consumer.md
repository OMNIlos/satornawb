# Canonical ABC/P&L loyalty consumer

## Boundary

- `WbAbcPnlService` reads loyalty only from the selected canonical
  `wb-finance-v2` projection. V1 snapshots and incomplete components remain
  unknown; no legacy-zero fallback exists.
- Rows and summary expose the three direct WB loyalty amounts, net loyalty
  cost, and profit after loyalty. Net loyalty cost is amount plus commission
  change minus discount.
- Final net profit, profit class, and ABC code remain `NULL` while advertising
  accounting authority is unresolved or any earlier evidence is incomplete.
- The HTTP path remains permission/account scoped and cache-only. No migration,
  scheduler, frontend, or application cache was added.

## Implementation and local verification

- Runtime implementation is commit `1173b2d`; coverage hardening is `6edfb82`.
  The latter changes tests only, so the runtime tree is identical to the tree
  that passed the complete backend failure-set comparison.
- The final focused service/route gate is `21 passed`. The wider ABC,
  advertising, finance, contract, and security profile is `174 passed`; the
  contract subset is `20 passed`. Ruff, compileall, one Alembic head, and Git
  diff checks pass.
- The complete backend run at the runtime-identical implementation is
  `666 passed / 105 failed`; the 105 identifiers exactly match the known legacy
  baseline, with no added, missing, or error identifiers.
- The independent review found no Critical or Important issue. Two minor
  finality coverage gaps were closed by `6edfb82`.
- The repository-wide frontend gate remains `195 passed / 29 failed`. Those
  failures predate this backend slice and are not claimed as passing.

## Parallel work integrated

- Legacy-failure triage from prompt 09 is squashed into `1a7354f`. Its clean,
  isolated full run reproduces exactly the 105 legacy failure identifiers.
- Finance observability from prompt 11 is integrated as `25bbc7e` and
  `016ead2`. Its SQL is read-only and its effective snapshot-chain membership
  matches `FinanceService`.
- These documentation/operations artifacts are present in the immutable
  release source. The Dockerfile intentionally does not copy `docs/` or `ops/`
  into the runtime image.
- No prompt-10 worktree or commit was available at release time, so no prompt-10
  change is included or claimed.

## Production rollout — 2026-09-06

- Immutable source `/var/tmp/satorna-abc-pnl-loyalty-1a7354f` was built from
  Git revision `1a7354f`. Archive
  `/var/tmp/satorna-abc-pnl-loyalty-1a7354f.tar` is mode `0600` with SHA-256
  `fa588aedbaf91c6dddb95057e9d2e5eb5e24931fdce321b9883bfc47ce2d7dc3`.
  The archive excludes `.venv` and `var/vella_repricer_runtime_state.json`.
- Migrate, API, default worker, canonical worker, and beat use the same image
  `sha256:5155436ff49a8a4ffe0e62489780afb0865bf9d2a61ae2f135b67259b8f75230`.
  Migrate exited `0` with the schema unchanged at `20260905_0060`; live
  containers are running with zero restarts and OOM events.
- `/health`, `/health/live`, and `/health/ready` return `200`; both Celery
  workers return `pong`, and active/reserved/scheduled counts are zero.
  Strict post-rollout error/traceback matches are zero.
- Production `.env` checksum remains
  `18b8293c1ae5dfb24e64c7a0a0fa1afd2132ccec2f08396bcd22c124ef55ca3c`.
  Scheduled canonical collection remains disabled with an empty allowlist.
  The intentionally dirty `/var/www/ogni-elfs` remains at `13cba53` with the
  same 72 status entries.

## Production canary

- A transaction-read-only service canary for organization/account `2`, closed
  day `2026-08-31`, selected v2 run
  `327ee61d-daa4-4ea9-9c9c-9779e2b8d183` and returned 494 rows.
- Formula is `wb-abc-pnl-loyalty-v1`. Summary loyalty components are
  `0 / 14,000 / 0` kopecks and net loyalty cost is `-14,000` kopecks. All 494
  rows have known loyalty evidence; `WB_PNL_LOYALTY_NOT_CANONICAL` is absent.
- Advertising remains unavailable for that exact day, so profit after loyalty,
  final net profit, profit class, and ABC code remain null. The advertising and
  existing economics/cost coverage blockers remain explicit.
- Twenty-five fresh cache-only service reads, including Pydantic response
  validation, measured p50/p95/max `72.50/157.54/179.80 ms`, below the
  `500 ms` gate.
- The first pre-count backup command omitted interactive stdin for `psql` and
  produced an empty file. It is explicitly marked invalid; exact pre/post count
  parity is not claimed. A corrected post-rollout snapshot records head `0060`
  and current counts. Independent maximum `created_at`/`last_observed_at`
  checks prove all finance, advertising, and funnel canonical writes predate
  the rollout boundary `2026-09-06T12:35:59Z`.

## Backup and rollback

- Backup
  `/var/backups/satorna-abc-pnl-loyalty-pre-1a7354f-20260906T123559Z` is mode
  `0700`; its environment, prior immutable source, image/container metadata,
  scheduler state, corrected database evidence, and manifest pass
  `sha256sum -c`.
- Rollback tags
  `ogni-elfs-{api,worker,canonical-shadow-worker,beat,migrate}:rollback-09afcc2-pre-1a7354f`
  point to
  `sha256:22416c20e8b3f01ff89686c6bea05babab464ab381a9e19868beedd498155c24`
  and prior source `/var/tmp/satorna-loyalty-finance-09afcc2`.
- The rollback is image-only. Both versions use schema `0060`; no database
  downgrade is required or permitted for populated loyalty evidence.

## Next gate

Resolve advertising accounting authority against retained raw evidence before
letting ABC/P&L consume attributed advertising or derive final net profit and
classification. Keep the change cache-only and fail closed whenever total,
identity, or completeness reconciliation is not exact.
