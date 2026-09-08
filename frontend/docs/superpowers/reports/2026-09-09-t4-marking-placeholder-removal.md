# T4 — removal of unused marking workspace, first slice

Coordinator relayed the user's new scope: KIZ and the separate matcher are not
required. Remove only confirmed unused surfaces; preserve core WB/Avito operations,
Catalog resolution, return matching, historical evidence and real data.

Removed in this bounded slice:

- `/orders/kiz` ComingSoon route and unused route constant.
- Marking navigation item and its unused icon import.
- Prototype print-list marking field, four placeholder values and table column.

The orders and returns routes/navigation retain their previous role policy.
Product, quantity and WB sticker columns remain. No handlers, backend, schema,
provider, printing/export action, shared HTML or user data were changed.
The removed source is recoverable in Git; this is not deletion of stored records.
Search across frontend src/api/scripts found no remaining runtime consumers of
`orders.kiz`, `/orders/kiz` or `orders-kiz`; only regression assertions remain.

Verification: real SSR print-list test failed on the old marking column, then
passed after removal. Navigation test failed on the actual old marking item,
then passed; its initial incorrect owner-role assumption was corrected rather
than widening runtime permissions. Focused navigation/print-list/ABC set: 13 pass.
Direct `tsc -b --noEmit`: exit 0. Git diff check: exit 0. Full suite was not
rerun for this removal; the preceding test-only slice recorded 266 pass / 27 fail.
These tests do not prove actual printing, backend orders or hosted rendering.
Independent scoped review: PASS. The old URL now reaches the application's
existing generic wildcard ComingSoon page, not a new 404; no KIZ-specific route
remains. The generic unmatched-route behavior is outside this removal slice.

## Remaining removal work, not declared completed

- Settings prototype module label and Notifications prototype blocked-action copy.
- Repricer prototype navigation counters and future marking gate.
- Avito picking table: marking header maps to an always-empty cell; remove header,
  matching cell and adjust empty-state colspan together, preserving return badge,
  sticker designer and Avito identifiers.
- Shared Vella source HTML/generated snapshot: inspect generator ownership and
  regenerate from source, not a regex deletion from embedded shared markup.
- `vellaBackendContracts.ts`: `kiz_marking` and the combined quality source reference
  appear only in this frontend file in the searched app/contracts scope. Verify
  remaining hidden/card/penalty/return requirements before changing the registry.

No need for a new backend marking contract is inferred. Historical documentation
and source evidence are retained. This slice is not a claim that every marking
reference has been removed.
