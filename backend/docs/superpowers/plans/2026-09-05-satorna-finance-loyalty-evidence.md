# Canonical WB Finance Loyalty Evidence

**Goal:** retain the three direct WB loyalty money fields in canonical finance snapshots without switching any report consumer.

## Boundary

- Preserve `cashbackAmount`, `cashbackDiscount`, and `cashbackCommissionChange` separately as signed integer kopecks. The existing snake-case aliases are accepted at the same trust boundary.
- Missing, `null`, and empty source values remain unknown; an explicit source zero remains zero. Boolean values are rejected.
- Net loyalty cost is `cashback amount + cashback commission change - cashback discount`. Percentage and identifier fields are not monetized.
- Existing `wb-finance-v1` snapshots remain immutable and unknown for loyalty. New observations use `wb-finance-v2`.
- No endpoint, frontend, advertising authority, final profit classification, scheduler, or new dependency is included.

## Implementation and verification

- Commit `09afcc2` adds migration `20260905_0060`, the three nullable columns on operations and both P&L projections, finance normalization, checksum participation, and completeness-preserving exact/custom-period aggregation.
- The downgrade disables forced RLS on all three tables before testing for any non-null evidence, restores enabled/forced RLS before dropping empty columns, and refuses to discard populated evidence, including explicit zero.
- A real PostgreSQL rehearsal with a non-`BYPASSRLS` owner proved that forced RLS hides an explicit-zero row before the fix, the fixed populated downgrade is blocked, rollback restores RLS, and an empty downgrade/upgrade succeeds.
- Focused finance/ABC tests pass (`66 passed`). The full backend suite is `662 passed / 105 known legacy failures / 26 warnings` in `266.93 s`; the JUnit failure-ID set is exact with no added, missing, or error IDs. Ruff, compileall, one Alembic head, whitespace, and Git object checks pass.
- Independent review after the RLS and lint fixes reports zero Critical, Important, or Minor findings. CodeRabbit was unavailable because its CLI was not authenticated; no CodeRabbit approval is claimed.

## Production rollout — 2026-09-05

- Release `/var/tmp/satorna-loyalty-finance-09afcc2` runs image `sha256:22416c20e8b3f01ff89686c6bea05babab464ab381a9e19868beedd498155c24` for migrate, API, both workers, and beat. Archive `/var/tmp/satorna-loyalty-finance-09afcc2.tar` has SHA-256 `1b1cbb1bc524a0d2c8d0c52ed5a31afdb2d110658d88e035b9b323d56ceac84e`.
- Migration `0059 -> 0060` succeeded. All nine columns are nullable `BIGINT`; all three affected tables retain enabled/forced RLS. Public health, liveness, readiness, two Celery pongs, image parity, zero restarts/OOM events, and fresh critical-log checks pass.
- Organization-2 canary for closed day `2026-08-31` published finance run `327ee61d-daa4-4ea9-9c9c-9779e2b8d183`, checksum `e18e98db9ebc92b65e4efb16e35f60ad2fefa465a56f9c5db1df5ad0e20ba226`, with `9,240` operations and complete aggregate/daily projections.
- All `9,240` operations have known loyalty components. Seven reimbursement rows total `14,000` kopecks; withheld amount and participation charge total zero, so net loyalty cost is `-14,000` kopecks. Operation-to-aggregate and operation-to-daily mismatches are both zero.
- Immediate replay reused the same run and checksum, advanced only `lastObservedAt`, and created no operation or identity duplicates. Existing eight v1 runs were unchanged, as were legacy advertising counts.
- Scheduled raw advertising/funnel collection remains disabled with an empty allowlist. No report or frontend consumer was switched.

## Backup and rollback

- Backup `/var/backups/satorna-loyalty-finance-pre-09afcc2-20260905T195718Z` is mode `0700`; protected files are mode `0600`. The scoped finance dump, full schema, globals, environment, rollback image/source, checksums, and dump restore-list pass.
- Rollback tags `ogni-elfs-{api,worker,canonical-shadow-worker,beat,migrate}:rollback-6d55722-pre-09afcc2` point to image `sha256:564d08a04137cf8d9b54ca5843c648f4cfbd9a40934a1240b379cce541c440c7` and prior release `/var/tmp/satorna-wb-binding-6d55722`.
- The prior image is schema-compatible with `0060`. Downgrade `0060 -> 0059` is deliberately unavailable once any loyalty evidence exists; normal rollback therefore changes application images only.

## Next gate

Add a completeness-aware loyalty projection to the ABC/P&L read model using only selected v2 finance evidence. Keep v1 loyalty unknown, keep final net profit/classification blocked by advertising authority, and do not switch the frontend until a separate consumer canary passes.
