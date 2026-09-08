# Canonical WB Advertising Reconciliation Shadow

**Goal:** Reconcile the already persisted exact-period raw WB advertising hierarchy without changing any report consumer.

## Boundary

- Reuse `wb_advertising_sync_runs`, facts, campaign snapshots, UPD documents, canonical `Period`, and `CatalogService`; add no table, migration, dependency, endpoint, scheduler, flag, or cache.
- Select only the latest complete materialized `ads_fullstats/raw` run for the exact account and period. Covering-window stitching is out of scope.
- Keep campaign-period and source-SKU rows separate. `campaign_only = campaign - source_sku` is calculated only inside the same campaign interval; it is never allocated across campaign members.
- Missing metrics propagate as `None`. Integer hierarchy differences are exact. Money accepts only the proven one-kopeck WB rounding tolerance; a tolerated clamp is explicit in diagnostics and a larger negative residual fails closed.
- An UPD document is `unknown` unless a campaign spend observation matches both campaign ID and document date. UPD and fullstats are parallel evidence and are never summed.
- Resolve source `nm_id` values through the existing catalog mapping and expose mapped, unmapped, and ambiguous sets.
- Always emit `WB_ADS_ACCOUNTING_AUTHORITY_UNRESOLVED`; the shadow cannot unblock ABC/P&L, loyalty, or frontend consumers.

## Verification and rollout — 2026-09-04

- TDD implementation commits: `4eac307` and `c9e5747`. Focused reconciliation tests pass (`39 passed`); the broader raw advertising gate passed before the final diagnostic-only fix.
- Final full suite at `c9e5747`: `650 passed / 105 failed / 26 warnings` in `268.97 s`. JUnit comparison is exact: expected `105`, actual `105`, added `0`, missing `0`, errors `0`.
- Production runs immutable image `sha256:6385dd797206f2c265e57bce33c490e1cd4b1570e34de24851d4a307b38d5c2d`, revision `c9e5747`, from `/var/tmp/satorna-ads-reconciliation-c9e5747`; API, worker and beat use the same digest with zero restarts, and migrate exited `0` at head `0059`.
- Read-only organization-2 probe for `2026-09-02`: state `ready`, run prefix `bbce1497`, campaign/source-SKU/campaign-only spend `2,282/2,283/0` kopecks, `44/44` source/catalog SKUs, unknown spend `0`, and diagnostics `WB_ADS_ACCOUNTING_AUTHORITY_UNRESOLVED` plus `WB_ADS_HIERARCHY_TOLERANCE_APPLIED`.
- The probe changed no rows and no consumer. `/health`, `/health/live`, and `/health/ready` return `200`; Celery returns `pong`; fresh API/worker/beat critical-error counts and restart counts are zero.
- Immediate rollback tag `rollback-4eac307-pre-c9e5747` points to image `sha256:835b085ed466a8bf98f1bae3134640e0058379cf33e6c0357d1c3e81707496c6`. Both release archives are checksum-protected in `/var/backups/satorna-funnel-pre-0059-20260904T093739Z`.

Next safe step: schedule account-scoped canonical evidence collection behind organization-2-only shadow gating and compare freshness/checksums with legacy caches. Do not switch reads until accounting authority and loyalty are independently closed.
