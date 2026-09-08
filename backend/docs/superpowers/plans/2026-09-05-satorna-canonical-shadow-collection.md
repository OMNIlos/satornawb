# Scheduled Canonical Evidence Shadow

**Goal:** run raw WB advertising and Sales Funnel collection on a bounded daily schedule without changing any report consumer.

## Boundary

- The feature is disabled by default and restricted to an explicit organization allowlist. It collects only the last closed Moscow business day.
- A connected WB account must reference an active tenant-owned token as `lk_user_wb_tokens:<token_id>`. Missing, malformed, cross-tenant, rotated, or reassigned bindings fail closed.
- Advertising and funnel backfills validate the same account, reference, and secret before fetch and again under row locks immediately before atomic publication.
- Partial or failed domain results run both domains, release the Redis organization lock, and retry twice at 30-minute intervals. Results and exceptions never expose credentials.
- `vella.canonical-shadow` has a dedicated concurrency-1 worker. The normal worker explicitly consumes only `vella.default`.
- No migration, endpoint, legacy-cache write, report read switch, advertising-authority decision, loyalty model, or frontend change is included.

## Verification and rollout — 2026-09-05

- Scheduling commits are `953d235` and `59de372`; authoritative credential binding is `6d55722`. The latter uses the existing official WB seller-info endpoint, stores `lk_user_wb_tokens:<token_id>` only after the returned cabinet identity equals the connected account identity, and revalidates ownership before publication. No token or seller secret is logged or returned.
- Final local gate at deployed code: targeted `48 passed`; full backend `655 passed / 105 known legacy failures / 26 warnings`, with the same exact failure-ID set. Compileall, one Alembic head (`20260904_0059`), whitespace and Git object checks pass.
- Production release `/var/tmp/satorna-wb-binding-6d55722` runs image `sha256:564d08a04137cf8d9b54ca5843c648f4cfbd9a40934a1240b379cce541c440c7` for API, default worker, canonical worker, beat, and migrate. Archive `/var/tmp/satorna-wb-binding-6d55722.tar` has SHA-256 `4f04eb847ad407425b3bf343071efd1e4a2a160218e78d13fa4bc5c690c56e86`; migrate exited `0` at `0059`.
- Backup `/var/backups/satorna-wb-binding-pre-6d55722-20260905T124807Z` passes its checksums. Immediate rollback tags `ogni-elfs-{api,worker,canonical-shadow-worker,beat,migrate}:rollback-59de372-pre-6d55722` point to image `sha256:ef14abcf3e74c2f5314c7b389f775bedb5347773f06b23cb1a5da7c97e76c085` and release `/var/tmp/satorna-schedule-59de372`.
- The official identity response matched organization `2`'s connected account, the explicit credential reference was stored, and collection was temporarily enabled only for organization `2`. No consumer was switched.
- The first closed-day task for `2026-09-04` completed `ready`. Advertising published run `58d01ea5-62d5-4d3f-960e-8135b42dea32`, snapshot `3ad4be55ae2dbca3c19d3e2bc3ecbe5846d6fa6654890b53cb28285861ae94cb`, `124` facts, `636` campaigns, `0` spend documents and `16/16` requests. Funnel published run `e8699b06-a6d0-486d-addd-baae828239e6`, snapshot `0e535f0eac7415f74cbd515892d7f25030a822ec4e33e3396cbda28cf5a34acf`, `3,303` facts and `167/167` requests.
- One controlled replay, task `8c6a7691-3d72-4fc3-8d49-5a0e824d73f2`, completed `SUCCESS/ready`. Advertising reused the exact run/checksum and advanced `lastObservedAt`. WB revised the closed-day funnel source during the `3 h 49 m` observation interval: the request/identity sets stayed identical, while exactly six facts changed (`openCount +4`, `buyoutCount +3`, `buyoutSum +606,400` kopecks). The service correctly retained a parent-linked revision `ca4be26d-da8f-4b96-bea6-36c2e92c64f5`, snapshot `1cdeb20be451ab5f15930795ab0586887bda5b662afa1c022a49650ea9dbd3ae`, with the same `3,303` facts and `167/167` coverage.
- Because the activation gate required an unchanged live replay, the fail-safe disabled scheduled collection and cleared its allowlist immediately after the explained source revision. Backup `/var/backups/satorna-canonical-shadow-disable-20260905T180000Z` retains the enabled environment (`aac568b9a683c07f6f5ea2ffcbe492870bdd35e6cdf1165abf9a010db9a82c14`); live disabled `.env` is `18b8293c1ae5dfb24e64c7a0a0fa1afd2132ccec2f08396bcd22c124ef55ca3c` and mode `0600`.
- Post-disable checks pass: no tenant and organization `1` see zero canonical rows; organization `2` sees one advertising run and two immutable funnel revisions. Child source-identity duplicates are `0`; legacy advertising tables remain exactly `314 / 2,656,964 / 32,828` rows. Public readiness is `200`, both workers return `pong`, all application containers use one image with zero restarts/OOM events, and the canonical worker has zero fresh critical log matches.

## Next gate

Keep scheduled collection disabled while the immutable canary evidence is retained. A future activation must define live-revision acceptance as an exact identity-level diff, not assume WB keeps a closed day byte-stable; consumer cutover remains separately blocked by advertising authority and canonical loyalty evidence.
