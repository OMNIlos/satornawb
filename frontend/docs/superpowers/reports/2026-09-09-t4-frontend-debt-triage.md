# T4 — frontend debt: first verified correction and remaining gates

This is a work ledger, not approval of baseline failures. No runtime frontend
code changed in this slice; no missing backend API is invented.

## Verified ABC auth test correction

`abcAuthHelpSource.test.ts` required a literal standalone
`if (state.authExpired) return null`. The real KPI guard also checks loading,
missing report and missing rows. The literal assertion failed despite the
auth guard being present. Reproduced before change: 1 failed / 1 passed.

Replaced only that brittle assertion with real `AbcKpiStripIsland` rendering:
loaded rows first render visible KPIs, then the same rows with expired auth
render nothing. Other existing panel/help checks remain. The new test does not
claim to exercise the entire authentication flow or every report block.

Mutation check: temporarily remove only the KPI auth guard; new test fails.
Restore the guard; 65 focused tests pass. Production file has no final diff.
Independent critic: scoped PASS. Direct `tsc -b --noEmit`: exit 0, without
regenerating the HTML snapshot.

Fresh full Vitest: **266 passed / 27 failed / 0 pending**, versus previous
264 passed / 28 failed / 0 pending. Exact failure-ID comparison: **0 new,
1 resolved**. Full suite exit 1, not green. JSON reports:
`/tmp/satorna-t4-clock-after.json`, `/tmp/satorna-t4-auth-after.json`;
mutation evidence `/tmp/satorna-t4-abc-auth-mutation.json`.

## Remaining failures — investigation queue

These are classified by what their failing assertion measures, not by presumed
acceptability. Source assertions can mask real missing behavior. None below is
waived, deleted or skipped.

| Group | Requirement to preserve | Next verification / dependency |
|---|---|---|
| Avito live wiring (8) | Repricer settings, explicit period apply, overview/listings/stats, details, Orders and Notifications | Trace current hooks and route islands; replace obsolete source snippets only with behavior evidence. Canonical switch waits for approved domain HTTP contracts. |
| Performance source (1) | Route-scoped loading, no unnecessary strategy refetch | Verify actual effect dependencies and request counts on navigation/account change. |
| Report help (1) | Understandable expense headers/formulas | Verify rendered help, not exact JSX formatting. Do not invent financial definitions. |
| Repricer stats source (1) | Backend stats selected by active route | Trace current route and load path; preserve T2 ownership of canonical commands. |
| RNP loading source (1) | Cache/results bound to selected period | Verify period changes, stale response suppression and exact cache key. |
| Stock/week state source (2) | Useful loading/empty/error states | Resolve old blanket ban on progress panels against actual displayed state; no blanket suppression of errors. |
| Static-source assertions (8) | Live report paths, active-tab ownership, no mock fallback, threshold wording, legacy boundaries | Inspect current extracted code and generated snapshot source; no reintroducing demo rows to satisfy old text. |
| Static HTML browser cases (5) | Report copy, filters, digest chart, strategy create/edit, Reviews UX | These load local `public/vella-production.html` via file URL, not authenticated React application. Establish prototype versus integrated-route expectations; do not infer production parity from either alone. |

The five browser cases currently fail on tax-base wording, absent stock rows,
missing digest chart items, strategy editor expectation and Reviews timeout.
They need individual behavioral diagnosis. No claim yet whether each is a stale
fixture or a real defect. Canonical Reviews/Orders/Production and runtime proxy,
session and readiness integration still wait for actual committed contracts.

## Avito notification toolbar correction

Independent review identified the obsolete `Обновить Avito` source assertion.
The actual toolbar already renders the shared `AvitoRefreshButton`, whose label
is `Обновить данные` and tooltip is `Обновить данные Авито`. Its existing callback
still invokes the Avito notification refresh bridge.

Replaced only the obsolete literal with a real toolbar SSR test under MemoryRouter
at `/avito/notifications`, checking the refresh control and read-all control.
Other backend/action/no-static-mock assertions remain. The island receives a named
export for direct rendering; runtime behavior and callbacks do not change.
Original selected checks: 1 failed / 1 passed. Mutation removing the actual refresh
component: the new rendering test fails; restored component has no behavioral diff.
This is toolbar-render evidence, not an executed read-all/refresh action, session
integration, provider call or durable receipt proof. No external action was invoked.

After restoring the component: selected notifications checks 2 passed (the `-t`
selection excludes unrelated cases, not committed skips). Typecheck: exit 0.
Independent scoped critic: PASS. Fresh full suite, including both safe marking
cleanup slices: **274 passed / 26 failed / 0 pending**, exit 1; versus the preceding
266/27 report, **0 new failure IDs, 1 resolved**. New cases account for the additional
passes. Report: `/tmp/satorna-t4-notifications-after.json`. The next SKU browser
fixture was created after this full run began and is verified separately.
