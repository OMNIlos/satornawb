# Satorna architecture rebuild — handoff

Updated: 2026-09-07, Europe/Moscow.

## Objective

Continue replacing the fragmented Satorna backend/frontend with a modular monolith and canonical PostgreSQL model. Fix shared causes, preserve tenant isolation, and migrate one bounded vertical slice at a time with parity, latency, backup and rollback evidence.

## Read first

1. Every applicable `SYSTEM_PROMPT.md`, `AGENTS.md` and project README/documentation.
2. `frontend/docs/superpowers/specs/2026-08-26-satorna-platform-rebuild-architecture-design.md` or its matching worktree copy.
3. `frontend/docs/superpowers/plans/2026-08-28-satorna-slice-1-canonical-costs.md` or its matching worktree copy.
4. `backend/docs/superpowers/plans/2026-09-01-satorna-period-finance-slice.md` or its matching worktree copy.
5. `SATORNA_SPEC_AUDIT.md`, resolving every remark against code and production evidence.

Do not assume a clean worktree. Preserve all user changes and inspect every repository/worktree before editing. GitHub is neither required nor authorized.

## Live production state

- Backend target: SSH alias `satorna-api`, server `109.69.22.214`, directory `/var/www/ogni-elfs`.
- Use only the dedicated key configured by that alias. Do not use credentials or keys belonging to another platform.
- Deployed application revision: `b96e602`. Runtime commits `592073d`, `5b48b23` and `8c84e1e` make exact complete raw fullstats the operational advertising authority and expose it through canonical ABC/P&L; `b96e602` removes raw Avito order bodies from diagnostics and logs. Earlier prompt-09 legacy triage and prompt-11 finance observability artifacts remain integrated.
- Migrate, API, default worker, dedicated canonical worker and beat use image `sha256:0aad3379406afd344b1ede23859350752f40efe9a2e8d19a988f8431f4040fa1`; migrate exits `0`, API is healthy, both Celery queues return `pong`, and all four live application containers have zero restarts/OOM events. The active immutable compose source is `/var/tmp/satorna-avito-log-redaction-b96e602`.
- Production Alembic head is `20260905_0060`. `0060` adds nullable loyalty evidence to immutable finance operations and both P&L projections; `0059` retains funnel facts and `0058` the raw advertising envelope. The compatibility-only `0056`, `0057` ownership, and concurrent FoundHub migrations `0050_department_hierarchy` and `0051_sales_user_channels` remain preserved byte-for-byte; never remove or rewrite them.
- Legacy `/health` remains compatible. `/health/live` is process-only; `/health/ready` checks PostgreSQL, Redis, Celery broker and result backend under one-second deadline and hides dependency errors. Both pass locally and at `https://api.elfprint-system.ru`; Celery returns `pong`. Worker/beat heartbeat is explicitly `not_monitored` until a shared heartbeat exists.
- API, worker and beat use `satorna_runtime`. It is not superuser, database/role creator, replication role or `BYPASSRLS`; it cannot access `alembic_version`. Only the one-shot migrate service receives the owner URL.
- Canonical finance and legacy advertising shadow ingestion are enabled only for organization `2`. The production account has an explicit credential reference proven by the official WB seller-info response. Scheduled raw advertising/funnel collection was canaried and is currently disabled with an empty allowlist after WB legitimately revised six closed-day funnel facts during the delayed replay; explicit CLI paths remain available. Exact complete raw fullstats is now the operational advertising authority; settlement promotion and UPD remain separate evidence and are never added or substituted. HTTP reads remain cache-only.
- Frontend remains on its legacy finance routes. Live page: `https://satorna-wb.vercel.app/production/skus`.
- Production source is an intentionally dirty overlay. Never reset it. The active isolated backend worktree is `.worktrees/backend-satorna-canonical-advertising`, branch `codex/satorna-canonical-funnel-ads-raw`; its preserved user-owned changes are `var/vella_repricer_runtime_state.json` and the untracked `.venv` symlink, which must remain outside commits and deploys.
- The intentionally dirty production checkout remains at `13cba531003f` with `72` collapsed status entries (`93` with every untracked file); the rollout did not modify it. Root filesystem reports `98%` used with `6,101,572 KB` free. Remove only exact task-owned releases/images; never broad-prune production.

## Backups and rollback

- Pre-`0047`: `/var/backups/satorna-period-finance-pre-0047-20260901T1950Z/`.
- Pre-`0048`: `/var/backups/satorna-period-finance-pre-0048-20260902T0744Z/`.
- Pre-`0049`: `/var/backups/satorna-finance-refresh-pre-0049-20260902T092500Z/`.
- Pre-runtime-role: `/var/backups/satorna-runtime-role-pre-38606cc-20260902T095837Z/`.
- Pre-`0052`: `/var/backups/satorna-finance-rollup-pre-0052-20260902T110306Z/`; its `38 MB` finance dump, schema, globals, runtime config and source checksums pass `sha256sum -c`.
- Pre-`0053`: `/var/backups/satorna-abc-pnl-pre-0053-20260902T170744Z/`; dump and restore-list checks pass.
- Pre-`0054`: `/var/backups/satorna-abc-pnl-pre-0054-20260902T172411Z/`; dump and restore-list checks pass.
- Pre-`0055`: `/var/backups/satorna-dated-economics-pre-0055-20260902T185811Z/`; scoped dump/checksums and restore evidence pass.
- Pre-`0057`: `/var/backups/satorna-advertising-pre-0057-20260903T133707Z/`; schema, anchors and exact retained finance/ads sources pass all listed SHA-256 and gzip checks. `production.env.pre-shadow` is mode `0600`; live `.env` differs from it only in the two advertising shadow keys.
- Pre-`0058`: `/var/backups/satorna-raw-advertising-pre-0058-20260903T220731Z/`; scoped dumps, pre/post invariants, environment, rollback source and immutable release archives through `d6ad0b0` pass `sha256sum -c`. Sensitive files and release archives are mode `0600`; the directory is mode `0700`.
- Pre-`0059`: `/var/backups/satorna-funnel-pre-0059-20260904T093739Z/`; pre-`0059` schema/anchors/environment, funnel post-canary evidence, shadow evidence and exact release archives through `c9e5747` pass `sha256sum -c`. The directory is mode `0700`; protected files are mode `0600`.
- Pre-binding backup: `/var/backups/satorna-wb-binding-pre-6d55722-20260905T124807Z/`; scoped source, environment and database evidence pass their checksums. Release archive `/var/tmp/satorna-wb-binding-6d55722.tar` has SHA-256 `4f04eb847ad407425b3bf343071efd1e4a2a160218e78d13fa4bc5c690c56e86`.
- Pre-loyalty backup: `/var/backups/satorna-loyalty-finance-pre-09afcc2-20260905T195718Z/`; scoped finance dump, full schema, globals, environment, rollback image/source, checksums and dump restore-list pass. The directory is mode `0700`, protected files are mode `0600`, and the release archive `/var/tmp/satorna-loyalty-finance-09afcc2.tar` has SHA-256 `1b1cbb1bc524a0d2c8d0c52ed5a31afdb2d110658d88e035b9b323d56ceac84e`.
- Pre-loyalty-consumer backup: `/var/backups/satorna-abc-pnl-loyalty-pre-1a7354f-20260906T123559Z/`; environment, prior immutable source, image/container metadata, scheduler state and corrected database evidence pass `sha256sum -c`. The original pre-count file is explicitly invalid and no exact count-parity claim is made; timestamp evidence proves all canonical finance/advertising/funnel writes predate rollout. The release archive `/var/tmp/satorna-abc-pnl-loyalty-1a7354f.tar` has SHA-256 `fa588aedbaf91c6dddb95057e9d2e5eb5e24931fdce321b9883bfc47ce2d7dc3`.
- Pre-operational-advertising backup: `/var/backups/satorna-ads-authority-pre-8c84e1e-20260906T210945Z/`; all `28` checksum entries pass. The `69 MB` backup contains the protected environment, prior immutable source, full schema, scoped canonical PostgreSQL dump with a valid restore list, pre/post database and container evidence, canary output and strict log gate. Release archive `/var/tmp/satorna-ads-authority-8c84e1e.tar` is mode `0600` with SHA-256 `69cac87e1b23819967d218dd4770e360dc2c5db0d020c460e6c15df9f63326a5`.
- Pre-Avito-redaction backup: `/var/backups/satorna-avito-log-redaction-pre-b96e602-20260907T191612Z/`; directory mode is `0700`, it contains `31` files total, and all `30` non-manifest checksum entries pass. The schema dump has a valid restore list and pre/post read-only database evidence is identical. It contains the protected environment, prior immutable source, both image/container states, rollout logs and both canaries. Release archive `/var/tmp/satorna-avito-log-redaction-b96e602.tar.gz` has SHA-256 `bb0949dd22a6be35bd2b7d2d2a95e7f1a163bb11a77f8088f961d52aa02bfac8`.
- Scheduled-collection fail-safe backup: `/var/backups/satorna-canonical-shadow-disable-20260905T180000Z/`; directory mode is `0700`, the enabled environment is mode `0600`, checksum `aac568b9a683c07f6f5ea2ffcbe492870bdd35e6cdf1165abf9a010db9a82c14`, and `sha256sum -c` passes. The disabled live environment checksum is `18b8293c1ae5dfb24e64c7a0a0fa1afd2132ccec2f08396bcd22c124ef55ca3c`.
- Current immediate image rollback: `ogni-elfs-{api,worker,canonical-shadow-worker,beat,migrate}:rollback-a247504-pre-b96e602`, image `sha256:a247504bcb3db354f77fa5b11e5bbdf73127852abf912ecc400eab9dad41339a`; restore `/var/tmp/satorna-ads-authority-8c84e1e`. Both images use schema `0060`, so rollback is image-only.
- Previous operational-advertising rollback: `ogni-elfs-{api,worker,canonical-shadow-worker,beat,migrate}:rollback-1a7354f-pre-8c84e1e`, image `sha256:5155436ff49a8a4ffe0e62489780afb0865bf9d2a61ae2f135b67259b8f75230`; restore `/var/tmp/satorna-abc-pnl-loyalty-1a7354f`.
- Previous loyalty-consumer rollback: `ogni-elfs-{api,worker,canonical-shadow-worker,beat,migrate}:rollback-09afcc2-pre-1a7354f`, image `sha256:22416c20e8b3f01ff89686c6bea05babab464ab381a9e19868beedd498155c24`; restore `/var/tmp/satorna-loyalty-finance-09afcc2`.
- Previous immediate image rollback: `ogni-elfs-{api,worker,canonical-shadow-worker,beat,migrate}:rollback-6d55722-pre-09afcc2`, image `sha256:564d08a04137cf8d9b54ca5843c648f4cfbd9a40934a1240b379cce541c440c7`; restore `/var/tmp/satorna-wb-binding-6d55722`. The image is schema-compatible with `0060`; populated downgrade is deliberately guarded.
- Previous scheduled-boundary rollback: `ogni-elfs-{api,worker,canonical-shadow-worker,beat,migrate}:rollback-59de372-pre-6d55722`, image `sha256:ef14abcf3e74c2f5314c7b389f775bedb5347773f06b23cb1a5da7c97e76c085`; restore `/var/tmp/satorna-schedule-59de372`.
- Funnel rollback: `ogni-elfs-{api,worker,beat,migrate}:rollback-d6ad0b0-pre-4d3cbb1`, image `sha256:009a8fd34bb5a451b77f436bcfef80d2978a438cecdaea95a60cccf091dc2cb6`. Downgrade `0059 -> 0058` only after proving the funnel tables are empty; the populated downgrade is deliberately guarded.
- Current immediate image rollback: `ogni-elfs-{api,worker,beat,migrate}:rollback-81a22ed-pre-d6ad0b0`, image `sha256:6cf785e01e92575c75d723ba96df5e3f301eac9cfadd54131eb004b28034325a`, label `81a22ed`. The safer preceding rollback `rollback-f5dddb0-pre-81a22ed` remains at `sha256:ef4c658d22ce5093309369e7a0fe58d165f545be98324dd204f338e6c65f3258`; both are schema-compatible with `0058`.
- Current immediate image rollback: `ogni-elfs-{api,worker,beat,migrate}:rollback-259977f-pre-205c11b`, pointing to the `0055`-compatible image `sha256:1daef9da8d491f3483de5b23ff58268dff19ecec6fd0245b1db717fca18e57df`, label `259977f`. Roll back the four app images first; downgrade `0057→0056` only if the advertising tables must also be removed.
- Immediate image rollback: `ogni-elfs-{api,worker,beat,migrate}:rollback-6959fc0-pre-259977f`, pointing to the `0055`-compatible image `sha256:cf176a765548941e88b747776c0e7e36106199c22ce258bb6de75f6f46a64fb9`. The preceding `rollback-fc6dd95-pre-6959fc0` and earlier rollback tags remain intact.
- A code rollback to `6959fc0` is schema-compatible and only restores the previous ABC row-classification pass. Database downgrade `0055→0054` drops only the two dated-economics ledgers; older `0054→0053→0052` rollback semantics remain unchanged.

## Completed slice 1 — catalog and costs

- Six canonical tenant-owned tables, forced PostgreSQL RLS and append-only `CostsService`.
- `/api/v2/production/skus` and `/api/v2/wb/products` are authenticated and organization/account scoped.
- Organization `2`: `3,337` SKU/products/offers and `15,047` cost versions; current-cost parity is `3,337/3,337` with zero amount mismatches.
- Undated legacy costs are exposed as `assumed`; three orphan rows remain `needs_review`. Do not guess their SKU identity.
- Authenticated production list p50/p95 is `32.9/37.7 ms` over 25 requests.

## Completed slice 2 — canonical period and finance

- One inclusive `Europe/Moscow` period model converts dates once to `[start_at, end_exclusive_at)` and explicitly represents complete, current-partial and future periods.
- WB operations are immutable, content-addressed and tenant/account scoped. Money is signed `BIGINT` kopecks; source identity/fingerprint, report type, correction timestamp and snapshot membership are retained.
- `GET /api/v2/wb/finance` is permission/account scoped and cache-only. It returns a coherent snapshot, paginated SKU rows, reconciled summary and explicit `ready|partial|future|empty|missing` states.
- `0047` created canonical operations/runs/memberships; `0048` backfilled and lifecycle-synchronized `9/9` canonical identity memberships.
- `0049` stores changed snapshots as parent-linked membership deltas. Exact snapshot selection wins over newer covering windows; one-level append-only deltas avoid ranking and anti-joins.
- `0052` materializes per-SKU rollups. Projection rows and `is_rollup_materialized=true` publish atomically; an interrupted rollup leaves the previous snapshot visible. Exact periods use the projection, while custom sub-periods retain operation-level filtering.

## Completed slice 3 — canonical ABC/P&L base

- `0053` materializes all signed WB settlement components per snapshot/SKU; `0054` adds daily immutable P&L facts so custom periods no longer scan operation memberships.
- `GET /api/v2/wb/reports/abc-pnl` is typed, `finance:read`/membership/account scoped and cache-only. It reuses canonical `Period`, snapshot selection, catalog identity and dated costs; HTTP reads never call WB.
- Settlement profit is reproducible from finance facts and Moscow-day COGS. Missing/ambiguous mappings and missing historical costs remain `null`, not zero; assumed costs are explicit blockers.
- `netProfitKopecks`, the profit letter and final `abcCode` intentionally remain `null`. Slice 4 removed only `WB_PNL_ECONOMICS_NOT_CANONICAL`; advertising and loyalty blockers remain.
- Commits: `673d10b`, `a0db4b2`, `043fefe`, `0dca857`, `1fcd065`, `1ecf67f`. Execution plan and evidence: `docs/superpowers/plans/2026-09-02-satorna-abc-pnl-base.md` in the isolated backend worktree.

## Completed slice 4 — dated economics and release readiness

- `0055` adds append-only, tenant-owned `organization_economics_versions` and `catalog_economics_override_versions` with composite ownership constraints, source idempotency, effective timestamps and forced RLS.
- Organization defaults and optional SKU overrides resolve at each Moscow business-day end as override → organization. Percentages are integer basis points; percentage rounding is half-even per unchanged policy bucket; missing evidence remains `null`.
- Legacy economics-bearing writes reconcile into the canonical ledger after the legacy write succeeds and repair partial dual-writes on retry. Unrelated repricer writes do no canonical work.
- ABC/P&L formula `wb-abc-pnl-economics-v1` exposes dated tax, other expenses and profit before ads/loyalty with value/evidence states and `economicsRevision`. Final net profit/classification stays blocked only by advertising and loyalty.
- Organization `2` has `2` organization versions and `3,052` SKU override versions, revision `3,054`; the two immutable observations preserve the only evidenced policy change instead of backdating current settings.
- Performance work reuses ledger projections, avoids tracked ORM reads/repeated datetime normalization and tenant setup, and assigns sales classes in one pass. No application response cache was added.
- Health/readiness commit `fc6dd95` from the isolated agent worktree was inspected against its contract, cherry-picked and deployed with the economics slice. Dated-economics implementation/performance commits are `a915e09`, `d604ff3`, `e2fd71d`, `2681dca`, `ac88226`, `eeee3e1`, `83dbebe`, `6959fc0` and `259977f`.

## Completed slice 5 — canonical advertising subtotal

- `0057` adds append-only, tenant/account-owned `wb_advertising_sync_runs` and `wb_advertising_facts` with composite ownership, deterministic source identity/checksums, atomic publication, idempotent observations and forced PostgreSQL RLS. The compatibility-only `0056` preserves the externally stamped production history.
- Existing WB finance and ads sync paths keep the legacy cache write first, then shadow-ingest into the canonical boundary. The bridge is enabled only for organization `2`, returns stable diagnostics and cannot break the established sync when its shadow write fails.
- Settlement promotion is authoritative for the exact-period P&L subtotal. Retained finance evidence lacks raw rows, so its `981,000` kopecks remain one explicit `aggregate_only`/unknown fact and are never allocated heuristically to SKU.
- Legacy fullstats is retained as `derived_legacy` diagnostics only. A production-shaped replay proved the recursive legacy aggregation can turn `1,800` RUB into `3,600` RUB; ABC/P&L therefore never selects or adds its total.
- Formula `wb-abc-pnl-advertising-v1` exposes row advertising/profit-before-loyalty only where exact SKU evidence exists, and exposes authoritative aggregate spend plus unattributed spend in the summary. Final `netProfitKopecks`, profit class and `abcCode` remain null behind loyalty and any pre-existing cost/economics evidence gaps.
- A daily COGS coverage guard now rejects mismatched materialization instead of silently treating missing daily units as zero. The PostgreSQL-only parent/fact insert ordering defect found by the first canary is covered with SQLite foreign keys and fixed by one parent flush.
- Core commits are `91b1ca8`, `9d64e99`, `123d268`, `cdf8b13`, `2c7f15e`, `a9cc582`, `6eff4f8` and `205c11b`. Read-only discoveries from the parallel agents are integrated as `7caad9e`, `179448c` and `5b55f03`; they document ABC/P&L inventory, the future raw funnel/advertising boundary, and price/stock contradictions without changing production behavior.

## Completed slice 6 — raw advertising evidence

- `0058` keeps the existing advertising envelope append-only, adds explicit `day|period` grain and `campaign|source_sku` scope, and creates account-owned campaign-snapshot and UPD spend-document tables with composite ownership and forced RLS.
- The explicit org-scoped CLI fetches campaign discovery, current metadata, hierarchical `fullstats` and UPD through the existing typed/rate-limited client. It publishes atomically only when the complete manifest succeeds; partial responses, malformed wrappers, ownership changes and normalization failures remain fail-closed. No scheduler or HTTP consumer was added.
- Normalization preserves missing versus zero, `appType`, source-SKU identity, signed UPD corrections and separate hierarchy levels. Campaign-period `fullstats` spend and UPD documents are parallel evidence and are never summed. A production-only WB rounding delta proved a bounded source-level tolerance: `0.01 RUB` for `sum`/`sum_price`; integer metrics stay exact and `0.0101 RUB` fails.
- Raw response lists and campaign ID unions are canonicalized before checksum/chunking, while exact audit manifests retain WB request IDs. Logical snapshots ignore request IDs but retain real payload/coverage changes. Fullstats batches are deterministic `≤50` IDs; transient `429` is retried at most three times through the existing limiter.
- Core raw-slice commits are `995f926`, `c9608a4`, `ff5a37c`, `1845a41`, `0eb181d`, `677ce67`, `8a108b1`, `7056e09`, `0254de4`, `f5dddb0`, `81a22ed` and `d6ad0b0`; hardening/test commits between them remain in history. Rollout evidence is committed as `d72d0f5` in `docs/superpowers/plans/2026-09-03-satorna-raw-advertising-evidence.md`.

## Completed slice 7 — canonical Sales Funnel daily evidence

- `0059` adds only `wb_funnel_sync_runs` and `wb_funnel_daily`: append-only, account-scoped, atomically published and forced-RLS. Daily facts retain literal WB `products/history` observations; omitted rows/fields stay missing and are never converted to zero.
- Fetching is deterministic in sorted batches of at most `20` SKUs and periods of at most seven days. A failed/malformed chunk publishes nothing; exact replay reuses the run and a changed snapshot links to its parent.
- The explicit CLI resolves the connected account and account-owned catalog IDs before fetching, performs network I/O outside the publication transaction, and revalidates ownership before commit. No scheduler, HTTP route, legacy-cache rewrite or frontend change was added.
- Production canary, RLS, migration rehearsal and rollback evidence are recorded in `docs/superpowers/plans/2026-09-04-satorna-funnel-daily-evidence.md`. Core release commit is `4d3cbb1`.

## Completed slice 8 — advertising reconciliation shadow

- `AdvertisingService.get_raw_reconciliation` projects the latest complete exact-period raw run without new storage. Campaign, source-SKU, campaign-only residual and unmatched UPD evidence stay separate; no campaign residual is allocated to products.
- Missing metrics propagate as `null`, integer hierarchy reconciliation is exact, and only the proven one-kopeck money tolerance can clamp a negative residual. Both tolerance use and unresolved accounting authority are explicit diagnostics.
- Source `nm_id` values reuse canonical catalog resolution and expose mapped, unmapped and ambiguous identities. No consumer, endpoint, scheduler, P&L authority or loyalty gate changed.
- Implementation commits are `4eac307` and `c9e5747`; rollout evidence is `docs/superpowers/plans/2026-09-04-satorna-advertising-reconciliation-shadow.md`. The parallel dated-economics audit is integrated as `1666b20` and changes documentation only.

## Completed slice 9 — scheduled evidence boundary and credential canary

- Commits `953d235` and `59de372` add a daily last-closed-day dispatcher behind a disabled-by-default organization allowlist. Partial/failed domain results retry twice after both domains run; an organization Redis lock prevents overlap.
- `vella.canonical-shadow` has its own concurrency-1 worker, while the existing worker explicitly consumes only `vella.default`. No endpoint, migration, cache consumer, accounting authority, loyalty model or frontend changed.
- Scheduled collection requires `marketplace_accounts.credential_ref = lk_user_wb_tokens:<token_id>`. Account, tenant, active-user, reference and secret are verified before fetch and again under row locks immediately before publication; reassignment or rotation fails closed.
- Commit `6d55722` resolves the identity gap through the existing official WB seller-info endpoint. Organization `2` was bound only after the returned cabinet identity exactly matched its connected account; no identity was inferred from one-account/one-token cardinality.
- A closed-day scheduler canary and one controlled replay both completed `ready`. Advertising was exactly idempotent. Funnel retained an explained parent-linked source revision after WB changed six facts during the replay interval. The rollout fail-safe then disabled scheduled collection and cleared its allowlist; no consumer was switched.
- Verification and rollback evidence is in `docs/superpowers/plans/2026-09-05-satorna-canonical-shadow-collection.md`.

## Completed slice 10 — canonical finance loyalty evidence

- Migration `0060` adds the direct WB `cashbackAmount`, `cashbackDiscount` and `cashbackCommissionChange` fields as separate nullable signed kopeck values on immutable finance operations and both P&L projections. Missing evidence remains `NULL`; explicit zero remains `0`.
- New observations use `wb-finance-v2`; the three fields participate in operation identity and payload checksums. Existing v1 snapshots remain immutable and unknown for loyalty.
- Exact and custom-period rollups propagate completeness. Net loyalty cost is withheld amount plus participation charge minus WB reimbursement; percentage and identifier fields are never monetized.
- The guarded downgrade was proven with a non-`BYPASSRLS` PostgreSQL owner. Production canary and exact replay proved operation/rollup parity, tenant isolation, idempotency and a real `-14,000`-kopeck net loyalty observation without changing any report consumer.
- Implementation commit is `09afcc2`; verification, rollout and rollback evidence is in `docs/superpowers/plans/2026-09-05-satorna-finance-loyalty-evidence.md`.

## Completed slice 11 — completeness-aware ABC/P&L loyalty consumer

- `WbAbcPnlService` reads loyalty only from the selected canonical `wb-finance-v2` projection. V1 and incomplete components stay unknown; no legacy-zero fallback exists.
- Rows and summary expose the three direct WB amounts, net loyalty cost and profit after loyalty. The formula is `amount + commissionChange - discount`; empty v2 evidence is explicit zero.
- Final net profit, profit class and ABC code remain null while advertising accounting authority or earlier cost/economics evidence is incomplete. The HTTP path remains permission/account scoped and cache-only; no migration, scheduler, frontend or application cache was added.
- Production canary for organization/account `2`, closed day `2026-08-31`, selected the retained v2 run and returned 494 rows with complete loyalty evidence. Summary is `0 / 14,000 / 0` kopecks and net loyalty cost `-14,000`; the loyalty blocker is absent while the advertising blocker remains.
- Implementation commits are `1173b2d` and `6edfb82`; rollout evidence is `docs/superpowers/plans/2026-09-06-satorna-abc-pnl-loyalty-consumer.md`. Prompt-09 triage is integrated as `1a7354f`; prompt-11 observability is `25bbc7e` plus `016ead2`. No prompt-10 commit was available or deployed.

## Completed slice 12 — operational advertising authority

- `AdvertisingService.get_pnl_source` now selects only an exact, materialized,
  complete `ads_fullstats/raw` snapshot. Finance promotion, UPD documents and
  derived legacy fullstats remain parallel settlement/diagnostic evidence and
  are never selected, added or allocated into operational spend.
- Effective spend is source-SKU spend plus the nonnegative campaign-only
  residual. The already proven one-kopeck negative hierarchy tolerance lets
  source detail win; larger disagreement, missing money or incomplete evidence
  fails closed. Complete empty evidence is authoritative zero.
- Source SKU spend is published to rows only when every carrying `nm_id` has one
  canonical catalog mapping and attributed spend equals the effective total.
  Missing or ambiguous mappings preserve the known summary total as
  unattributed and keep row advertising/profit null.
- ABC/P&L formula is `wb-abc-pnl-fullstats-loyalty-v1`. Operational advertising
  and profit after loyalty are available when their evidence is complete;
  final net profit, profit class and `abcCode` remain null behind the distinct
  `WB_PNL_CLASSIFICATION_NOT_CANONICAL` gate. No migration, collection path,
  scheduler, cache, endpoint or frontend change was added.
- Runtime commits are `592073d`, `5b48b23` and `8c84e1e`; implementation and
  rollout evidence is in
  `docs/superpowers/plans/2026-09-06-satorna-advertising-operational-authority.md`.

## Completed slice 13 — final-profit boundary and Avito log redaction

- Final net profit cannot be promoted from `profitAfterLoyaltyKopecks` without
  inventing a business rule. The product contract still requires Maxim's final
  formula; profit ABC needs final profit inputs, and tie/zero/negative semantics
  are not approved. Existing sales ABC thresholds do not close that gap.
- Production also proves an omitted expense domain: organization `2` has `503`
  completed 1C jobs and `4,016` operational-expense rows across `347` jobs.
  `one_c_cash_flow_jobs` has no marketplace-account identity and no PostgreSQL
  RLS, while the approved contract allows OPEX to remain unallocated or use a
  separately approved revenue/orders/stocks allocation. No SKU allocation was
  fabricated; `netProfitKopecks`, `profitClass` and `abcCode` remain null.
- The Avito live orders client no longer retains `bodyPreview` in diagnostics or
  emits `[AVITO_ORDERS_BODY]`. This closes both the direct warning sink and the
  Celery task-success copy while preserving typed errors, order parsing,
  request metadata, safe key names, status and order counts.
- TDD captured the synthetic buyer/phone/address leak before the fix. Focused
  Avito consumers pass `21` tests with the two exact legacy failures excluded;
  the canonical finance/advertising gate is `110 passed`. Full backend is `678
  passed / 105 known failures / 26 warnings`, with an exact failure-ID set and
  no added, missing or error IDs.
- Runtime commit is `b96e602`; documentation commit is `e5c0b5b`.
  Implementation, blocker proof, rollout and rollback evidence is in
  `docs/superpowers/plans/2026-09-07-satorna-final-profit-blocker-avito-log-redaction.md`.

## Production evidence

- Historical snapshot `2026-08-17…2026-08-23`: `62,465` operations, `929` attributed SKUs and `635,537,451` kopecks.
- Prior 7-day evidence snapshot `2026-08-27…2026-09-02`: run `4b00cc0f-14f1-4bca-b71f-3ceccafb71fb`, `48,529` operations, `848` attributed SKUs and `634,901,083` kopecks. A newer exact `2026-08-28…2026-09-03` snapshot is live and was used for the final latency gate.
- Changed 30-day canary `2026-08-04…2026-09-02`: run `7af208f3-2a14-4b42-8ba9-e777aa845483`, `271,211` operations, `1,228` attributed SKUs and `2,983,463,860` kopecks. Fetch took `151.578 s`; delta ingest took `399.629 s`.
- The 30-day canary preserved API availability throughout, had no lock waits, and stored `333,676` membership changes across three snapshots rather than copying every full revision.
- Rollup backfill ran through `satorna_runtime`, compared every aggregate field with the operation-level query, and committed each snapshot separately. Gate: `3` published, `3` rollup-ready, `0` pending/incomplete; table rows are `930 + 849 + 1,229`, including one unattributed sentinel per snapshot.
- A two-session PostgreSQL probe proved an uncommitted rollup replacement does not hide the previous published projection. No tenant context and organization `1` see zero organization `2` rollups; organization `2` sees all `3,008` rows.
- Direct production-DB p50/p95: `7.01/9.08 ms` for 7 days and `8.22/10.31 ms` for 30 days. Authenticated route p50/p95: `20.92/23.92 ms` and `25.36/27.92 ms`. The 30-day projection query executes in `0.786 ms` with shared-buffer hits and no reads.
- P&L backfill through `satorna_runtime`: `3/3` aggregate and daily projections ready, `3,008` aggregate rows and `20,891` daily rows. All finance components match operation-level aggregation with zero tolerance.
- Independent dated-cost/formula parity: 7d `849` rows, `48,529` operations, `634,901,083` revenue, `174,913,000` COGS, zero mismatches; 30d/custom correctly return summary COGS/profit `null` because `840/519` rows predate their first cost evidence.
- P&L forced-RLS probes: no tenant context and organization `1` see zero organization `2` rows; organization `2` sees all `3,008` aggregate and `20,891` daily rows; cross-tenant writes fail.
- Authenticated `/api/v2/wb/reports/abc-pnl` p50/p95 over 25 requests: `142.7/330.2 ms` (7d), `343.1/400.3 ms` (30d), `95.5/237.8 ms` (custom). All pass the `500 ms` p95 gate without an application cache.
- Focused finance/ABC/security checks: `48 passed`. Full backend result: `438 passed / 105 failed` in `272.68 s`; the same `105` failures are legacy baseline debt, not regressions from this slice.
- Dated-economics zero-tolerance evidence: 7d `849` rows, `848` calculable and one source row without `business_date`; 30d `1,229` rows, `518` calculable and `711` intentionally missing historical coverage; custom `2026-08-20…2026-08-26` is `926/926` calculable with tax `42,077,260` and other expenses `35,064,382` kopecks. Every calculable delta is zero; incomplete summaries stay `null`.
- Final authenticated live p50/p95 over 25 requests: `152.55/343.83 ms` (7d), `394.28/445.30 ms` (30d), `151.70/332.04 ms` (custom). Measurements overlapping real legacy repricer pagination or the five-minute Celery burst were rejected; the quiet-window gate passes without an application cache.
- Final relevant checks: combined infrastructure/economics/finance tests `36 passed`, ABC/performance tests `22 passed`, contracts `20 passed`; full backend `476 passed / 105 failed` in `264.25 s`, with exact legacy identifiers and no added/missing/error IDs.
- Economics forced-RLS probe under `satorna_runtime`: no tenant, organization `1` and organization `3` see `0/0`; organization `2` sees `2/3,052`, revision `3,054`. The runtime role has no superuser, create DB/role, replication or `BYPASSRLS` attributes.
- Advertising production-schema rehearsal passed `0056→0057→0056→0057`; both tables and policies disappear/reappear at the correct boundary, retain `FORCE ROW LEVEL SECURITY`, and leave one Alembic head. The pre-existing empty-chain `0019` defect remains unrelated.
- Exact advertising backfill `2026-08-17…2026-08-23` inserted `2` runs then `0` on replay. Finance is `1` aggregate-only fact / `981,000` kopecks; fullstats is `730` derived-legacy facts / `111,076` kopecks. Current totals are `2` runs, `731` facts and `1,092,076` diagnostic kopecks; P&L selects only finance and reports `981,000` unattributed.
- Advertising RLS under `satorna_runtime`: no tenant and organization `1` see `0`; organization `2` sees both runs. Both tables have enabled/forced RLS with tenant `ALL` policies; cross-tenant insert fails with SQLSTATE `42501`. An enabled-bridge replay returns `disabled` for organization `1` and idempotent `ready` for organization `2`.
- Authenticated retained-period ABC/P&L returns HTTP `200`, formula `wb-abc-pnl-advertising-v1`, source/evidence `finance_promotion/aggregate_only`, spend/unattributed `981,000/981,000`, and null final profit. Twenty-five-request production p95 is `266.86 ms` retained, `337.98 ms` 7-day, `435.03 ms` 30-day and `334.62 ms` custom; post-shadow retained p50/p95/max is `119.34/294.57/295.75 ms`.
- Final local command reports `520 passed / 105 failed / 26 warnings` in `273.54 s`; the same exact 105 legacy IDs remain and no advertising/ABC/FK test regresses. `compileall`, Git whitespace/object checks, backup checksums, external health, Celery `pong`, empty active/reserved/scheduled queues, one-image parity and zero restart/error-line checks all pass.
- Raw-advertising production canary for `2026-09-02` published final run `bbce1497-feb1-4497-b270-6bd50762ca15`, snapshot `cf233b3101fbe0ce277212d57856ca6e0ce82bdd04781902c6a4a3fdaac1bc9f`, manifest `16/16`, `138` facts, `636` campaigns, `0` UPD documents and `2,282` source kopecks. A replay after `107 s` returned the same run/checksum/counts and advanced `lastObservedAt` from `02:08:48Z` to `02:16:18Z`; child identity duplicates are `0/0/0` and no secret-like manifest key exists.
- The first pre-fix canary pair exposed discovery-order-dependent 50-ID partitions despite identical normalized rows. Its two snapshots are retained as append-only diagnostic audit. `d6ad0b0` fixes the root cause; the live final request plan is `636` unique globally sorted IDs in `12×50 + 36` batches.
- Raw-table RLS under `satorna_runtime`: no tenant context and organization `1` see `0/0/0/0`; organization `2` sees its rows; cross-tenant insert fails with SQLSTATE `42501` and persists `0`. All four advertising tables have enabled/forced RLS and tenant `ALL` policies with `USING` and `WITH CHECK`.
- Post-raw authenticated ABC/P&L remains unchanged and never selects the raw run. Retained evidence is `finance_promotion/aggregate_only`, spend/unattributed is `981,000/981,000`; production p95 over 25 requests each is `254.96 ms` retained, `23.75 ms` 7-day, `19.87 ms` 30-day and `101.40 ms` custom, all below `500 ms`.
- Latest independent raw-slice verification is `591 passed / 105 known baseline failures / 0 errors / 26 warnings` in `271.79 s`; the failure-ID set is exact. Raw targeted tests are `115 passed`; compileall, one Alembic head, whitespace/object checks, backup checksums, external health, image parity, pong and zero restart/error-line checks pass. At that recheck one normal periodic repricer task was active; reserved and scheduled queues were empty.
- Funnel canary `2026-09-02...2026-09-03` published run `4d21594d-8106-4a3c-bedd-e2b7a23efad5`, checksum `c7d2e942caab1905f7d352dc258b348593f350a9f19d5a7efd72b132b644f3c0`, `167/167` completed requests and `6,608` facts. WB returned `3,304` of `3,337` requested SKUs on both days; the `33` omissions remain absent rather than synthetic zero. Source identities and `(date, nm_id)` are unique, and no returned SKU falls outside the request.
- Funnel forced-RLS probes: no tenant and organization `1` see `0/0`; organization `2` sees `1/6,608`; a cross-tenant insert fails with SQLSTATE `42501` and persists zero rows. Production-schema rehearsal passed `0058 -> 0059`, publish/replay/change, guarded populated downgrade and empty downgrade/upgrade.
- Advertising reconciliation read-only probe on raw run prefix `bbce1497` is `ready`: campaign/source-SKU/campaign-only spend is `2,282/2,283/0` kopecks, all `44` source SKUs resolve to catalog SKUs, unknown document spend is zero, and the one-kopeck clamp is explicitly diagnosed. `WB_ADS_ACCOUNTING_AUTHORITY_UNRESOLVED` remains, and no report consumer changed.
- Final local gate at deployed code `c9e5747`: advertising tests `101 passed`; full backend `650 passed / 105 known baseline failures / 26 warnings` in `268.97 s`; JUnit identities are exact with no added, missing or error IDs. Compileall, Ruff, one Alembic head, whitespace/object checks, backup checksums, external health, image parity, Celery pong and zero restart/fresh-critical-error checks pass. CodeRabbit was unavailable because its CLI was not authenticated; no CodeRabbit approval is claimed.
- Scheduled-shadow release `59de372`: targeted gate `105 passed`; full backend `650 passed / 105 known baseline failures / 26 warnings` in `268.96 s`, with exact JUnit IDs and no added/missing/errors. Production image parity, queue-specific pongs, head `0059`, public health `200`, empty canonical queue, zero raw runs in the first 30 minutes, unchanged `.env` checksum, zero restarts/OOM/fresh-critical-log matches and fail-closed credential resolution all pass.
- Credential-binding release `6d55722`: targeted `48 passed`; full backend `655 passed / 105 known baseline failures / 26 warnings`, with the same exact failure-ID set. The official WB identity check matched organization `2`, the explicit credential reference was stored, and the deployment/backup/image/health/RLS gates passed without exposing credentials.
- Scheduled canary for `2026-09-04` published advertising run `58d01ea5-62d5-4d3f-960e-8135b42dea32` (`124` facts, `636` campaigns, `0` documents, `16/16`) and funnel run `e8699b06-a6d0-486d-addd-baae828239e6` (`3,303` facts, `167/167`). Replay task `8c6a7691-3d72-4fc3-8d49-5a0e824d73f2` kept advertising's exact run/checksum and advanced freshness. Funnel request and identity sets stayed exact, but WB revised six facts after `3 h 49 m`: `openCount +4`, `buyoutCount +3`, `buyoutSum +606,400` kopecks. Canonical storage correctly created parent-linked run `ca4be26d-da8f-4b96-bea6-36c2e92c64f5`; duplicates remain zero and legacy advertising counts remain `314 / 2,656,964 / 32,828`.
- Loyalty release `09afcc2`: focused finance/ABC gate `66 passed`; full backend `662 passed / 105 known legacy failures / 26 warnings`, with the exact baseline failure-ID set. Production migration `0059 -> 0060`, non-`BYPASSRLS` downgrade rehearsal, backup/restore-list, image parity, public health, two pongs and zero restart/OOM/fresh-critical-log gates pass.
- Closed-day finance canary `2026-08-31` published v2 run `327ee61d-daa4-4ea9-9c9c-9779e2b8d183`, checksum `e18e98db9ebc92b65e4efb16e35f60ad2fefa465a56f9c5db1df5ad0e20ba226`, with `9,240` operations, `494` aggregate and `491` daily P&L rows. All loyalty components are known; seven reimbursements total `14,000` kopecks and net loyalty cost is `-14,000` kopecks. Aggregate and daily parity mismatches are zero; immediate replay reused the exact run/checksum and created no duplicates.
- Loyalty-consumer release `1a7354f`: focused final gate `21 passed`; the wider backend profile is `174 passed` and contracts are `20 passed`. The runtime-identical complete backend run is `666 passed / 105 known failures`, with an exact failure-ID set. Production runs one image `sha256:5155436ff49a8a4ffe0e62489780afb0865bf9d2a61ae2f135b67259b8f75230` at schema `0060`; public health, two pongs, empty worker queues, backup checksums, unchanged environment/source, disabled scheduler and zero restart/OOM/strict-error gates pass.
- Twenty-five production cache-only loyalty reads, including response-schema validation, measured p50/p95/max `72.50/157.54/179.80 ms`. The canary returned formula `wb-abc-pnl-loyalty-v1`, all 494 row loyalty values known, summary net loyalty cost `-14,000`, and null final profit/classification. The invalid empty pre-count capture is disclosed in the rollout evidence; no exact pre/post count parity is claimed, while maximum write timestamps prove no canonical finance/advertising/funnel write occurred after the rollout boundary.
- Operational-advertising release `8c84e1e`: focused service/API/contract gate
  `110 passed`; one fresh isolated backend run is `677 passed / 105 known
  failures / 15 warnings`, with the exact baseline failure-ID set and no added,
  missing or error IDs. Production uses one image
  `sha256:a247504bcb3db354f77fa5b11e5bbdf73127852abf912ecc400eab9dad41339a`
  at schema `0060`; public health, two pongs, empty queues, disabled canonical
  scheduler, unchanged environment/checkout, backup checksums and zero
  restart/OOM/strict-error gates pass.
- Transaction-read-only production canary for `2026-09-02` returns
  `ads_fullstats/raw`, formula `wb-abc-pnl-fullstats-loyalty-v1`, raw campaign
  total `2,282`, effective/row total `2,283` and unattributed `0` kopecks. Exact
  `2026-08-31` finance-promotion evidence is deliberately not substituted.
  Classification stays blocked by existing upstream assumed cost/economics
  evidence rather than being fabricated. Twenty-five validated cache-only reads
  measured p50/p95/max `82.46/147.84/161.37 ms`.
- Avito-redaction release `b96e602` runs immutable archive
  `bb0949dd22a6be35bd2b7d2d2a95e7f1a163bb11a77f8088f961d52aa02bfac8`
  and one image
  `sha256:0aad3379406afd344b1ede23859350752f40efe9a2e8d19a988f8431f4040fa1`
  across migrate, API, both workers and beat. Schema remains `0060`; internal
  and public health are `200`, both workers pong, all queues are empty,
  canonical collection remains disabled with an empty allowlist, and restart,
  OOM and strict post-boundary error counts are zero.
- A read-only synthetic fetch inside the production worker retained parsed buyer
  data in the typed result and emitted status/count diagnostics, while the body
  marker and every synthetic PII value were absent. The closed-day membership-
  and account-scoped canary returned all `457` rows with null final fields and
  exact upstream blockers `WB_PNL_COST_ASSUMED`,
  `WB_PNL_COST_EVIDENCE_UNDATED`, `WB_PNL_ECONOMICS_ASSUMED`; pagination was
  stable and 25 reads measured p50/p95/max `72.88/90.19/147.62 ms`.

## Hard gates still open

1. The historic `120,800`-kopeck correction is absent from the current WB source and no retained raw `rrdId` exists. Do not claim the frozen `635,658,251` raw-operation gate passed and never synthesize an identity.
2. A brand-new empty database still fails at pre-existing migration `20260717_0019` because `ai_prompt` already exists. Production-schema clone and scoped restore paths through `0060` pass; do not misattribute the empty-chain defect.
3. The `105` baseline test failures remain real repository debt.
4. Satorna processes are isolated behind the runtime role, but the unrelated `foundhub-backend-debt-adjustment-r33-prod` workload still holds PostgreSQL-owner sessions in the shared cluster. Do not claim cluster-wide superuser eradication or alter that workload from this slice.
5. Frontend finance remains legacy until a separate consumer canary proves contract/UX parity and rollback. No backend gate requires a second cache layer.
6. Historical costs before their first evidence are intentionally incomplete: 30-day/custom total COGS and settlement profit remain `null`; do not backfill them from later costs.
7. Operational advertising authority and its ABC/P&L consumer cutover are complete. Loyalty is consumed only from complete v2 finance snapshots; v1 remains unknown. Final net profit, profit class and ABC code still lack an approved canonical formula and classification rule. Production 1C OPEX is organization-scoped without marketplace-account identity or RLS, and no SKU allocation is approved. Final fields must remain null whenever that rule or any upstream evidence is incomplete.
8. `/health/ready` proves database/Redis/Celery transport dependencies, but worker and beat are still `not_monitored`; add readiness gating only after a canonical shared heartbeat exists.
9. Scheduled canonical collection is intentionally disabled after the canary replay observed a fully explained closed-day WB funnel revision. Before reactivation, define the gate as an exact identity-level source diff rather than byte-stability over a multi-hour fetch; never treat a real revision as an idempotency failure or silently accept an unexplained diff.

Architecture completion estimate after slice 13 remains about `77%` complete and `23%` remaining (`±5 pp`). This is a scope-weighted engineering estimate, not a line-count metric. The security risk is closed and the final-profit boundary is now evidence-backed, but no completion credit is invented for the still-unapproved formula. Final net-profit/classification semantics, always-on collection, frontend cutover, price/stock history, remaining domain facts and several operational modules are not yet credited.

## Recommended next bounded slice

Move the frontend ABC/P&L consumer to a canonical adapter behind a default-off
flag while the final-profit decision stays with the product owner:

1. Consume only `/api/v2/wb/reports/abc-pnl` through one typed adapter; do not
   reconstruct finance or classification from legacy routes.
2. Preserve `null`, source state and every blocker distinctly from zero. Do not
   label `profitAfterLoyaltyKopecks` as final net profit or synthesize a second
   ABC letter.
3. Prove loading/empty/no-access/partial/error states, exact and custom periods,
   pagination and current legacy UX parity with focused frontend tests.
4. Keep the flag disabled until a read-only production consumer canary passes;
   rollback is the flag, with no backend, migration, scheduler or cache change.

Return to final-profit implementation only after Maxim approves the expense
domain, OPEX allocation (including `none`), profit-letter tie/zero/negative
semantics and final formula version.

## Safe parallel work

Parallel agents must use separate worktrees and must not deploy or create Alembic revisions while the next canonical backend slice is active. Safe streams are:

- frontend-only canonical finance client/adapter and consumer tests behind a disabled flag;
- read-only classification of the `105` legacy failures, followed by isolated fixes outside canonical finance/period/migrations/runtime compose;
- observability/runbook work for snapshot freshness, latency, rollup readiness and RLS, in a new document/script;
- read-only discovery for prices/stocks/KTR/loyalty boundaries, producing a call/data-flow map rather than implementation;
- a documentation-only decision package for final profit/OPEX allocation and profit-class tie/zero/negative semantics.

Until explicitly released, parallel work must not touch `app/platform/finance/**`, `app/platform/economics/**`, `app/platform/advertising/**`, `app/platform/funnel/**`, `app/wb_api/raw_advertising.py`, `app/wb_api/raw_funnel.py`, `app/platform/period.py`, `app/modules/wb_reports/**`, migrations `0047…0060`, `docker-compose.yml`, `ops/runtime-db-role.sql`, or this handoff.
