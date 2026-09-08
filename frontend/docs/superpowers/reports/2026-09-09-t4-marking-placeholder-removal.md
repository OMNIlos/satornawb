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

## Follow-up: independent copy and prototype navigation

Removed the marking module from the prototype production user's displayed module
list, the invented marking prerequisite from a prototype order notification,
and the two static repricer marking counters/navigation sections. The removed
sections contained no other entries. Account IDs, dangerous permissions, price
controls and other notification restrictions are unchanged. `blockedActions` is
descriptive UI content here, not a print execution policy.

Four new real projection/SSR cases reproduced failures before the change;
combined settings/notifications/repricer/navigation/print-list tests: 26 pass.
Independent scoped review: PASS, no important findings.
Direct typecheck and Git diff checks after this follow-up: exit 0.

Shared HTML dependency discovery: `ordersIsProblemStatus` includes the historical
`missing_honest_sign` state and affects problem/ready filtering. `honestSign` also
participates in manual/edit fields, drawer external-code display and the sticker
code fallback. It is not proven to be a backend execution gate. These are not
safe targets for blind string deletion or automatic status conversion. Preserve
historical fields/data and barcode fallback until a compatibility-tested removal
of exposed controls is implemented. No additional marking service is required.
