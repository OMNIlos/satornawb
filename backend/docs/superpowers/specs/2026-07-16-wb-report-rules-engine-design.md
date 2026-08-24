# WB Report Rules Engine Design

**Date:** 2026-07-16  
**Status:** awaiting written specification review

## Goal

Turn `/wb/reports/rules` from a browser-only prototype into the backend source of truth for report classification. A registered Satorna account has one organization and one connected WB token, so the active rule profile is scoped by `organization_id` and shared by the users of that account.

Every supported report must evaluate its rows with the active saved profile. The profile produces statuses, reasons, alerts, and recommendation drafts. It never changes a WB price or advertising campaign automatically.

## Current State

The rules page currently keeps `activeThresholdProfile` and `thresholdDraft` inside `vella-production.html`. Saving changes only the in-memory JavaScript object. The manager plan table, automation mapping, and audit rows shown by the React island are static samples.

Report builders do not read this browser state. They either use independent hard-coded values, such as the stock report's seven-day OOS threshold, or return temporary classifications. Consequently, changing a preset or threshold on the page does not reliably affect backend report results.

## Scope

This feature includes:

- durable, versioned report-rule profiles per organization;
- working standard, conservative, aggressive, and custom profiles;
- backend validation and fixed ABC shares;
- server-side impact preview;
- real profile history and audit events;
- editable manager plans backed by the existing report plan API;
- server-side evaluation in ABC, RNP, P&L, advertising, stock, and week-over-week reports;
- recommendation drafts that require explicit confirmation;
- report cache separation by rules version;
- replacement of static rules-page data with backend data.

This feature does not include:

- automatic price submission to WB;
- automatic advertising campaign changes;
- separate profiles by manager, brand, or SKU;
- multiple WB accounts inside one organization;
- changing the fixed ABC distribution.

## Profile Ownership

The profile is keyed by `organization_id`. The organization is the Satorna account created during registration and is the same scope that owns the connected WB token and report source caches. All users in the organization read the same active profile. Only actors with `settings:write` may preview-and-save changes; normal report readers may read the active profile and its evaluation metadata.

## Persistence Model

Add an append-only `wb_report_rule_profiles` table:

| Column | Purpose |
| --- | --- |
| `profile_id` | Primary key |
| `organization_id` | Owning Satorna organization |
| `version` | Monotonically increasing organization-local version |
| `name` | User-facing profile name |
| `preset` | `standard`, `conservative`, `aggressive`, or `custom` |
| `config_json` | Validated rule configuration |
| `created_by_user_id` | Actor who activated the version |
| `created_at` | Activation time |
| `is_active` | The current version marker |

Constraints:

- unique `(organization_id, version)`;
- at most one active row per organization;
- an update inserts a new version and deactivates the previous version in one transaction;
- old versions remain available for history and audit display.

If an organization has no stored profile, the service returns the standard preset as version `1` and persists it on the first write. Report evaluation may use this deterministic default before the first write.

## Configuration Contract

The stored configuration uses the following shape:

```json
{
  "abc": {
    "salesShare": {"aPct": 20, "bPct": 30, "cPct": 50},
    "netProfitShare": {"aPct": 20, "bPct": 30, "cPct": 50}
  },
  "qualityBands": {
    "ctrPct": {"goodMin": 10, "averageMin": 6},
    "crPct": {"goodMin": 4, "averageMin": 2},
    "cartToOrderPct": {"goodMin": 45, "averageMin": 25},
    "buyoutPct": {"goodMin": 80, "averageMin": 60},
    "marginPct": {"goodMin": 25, "thinMin": 10, "lossBelow": 0},
    "drrPct": {"goodMax": 9, "warnMin": 14},
    "roiPct": {"goodMin": 250, "warnBelow": 100},
    "daysToOos": {"warnBelow": 7},
    "stockUnits": {"criticalBelow": 12},
    "localizationPct": {"badBelow": 60}
  },
  "automationMapping": {
    "aaGood": "raise_price",
    "badCr": "rnp",
    "loss": "liquidation",
    "highDrr": "stop_ads",
    "oos": "alert",
    "cWeak": "audit"
  }
}
```

All three built-in presets are complete backend constants. Selecting a preset replaces the whole draft. Editing any preset value changes the draft preset marker to `custom`.

The backend always overwrites both ABC axes with `20/30/50`. ABC fields stay visible and disabled on the page so the classification contract is explicit.

Validation enforces finite numeric values, sensible percentage and count ranges, and ordering rules:

- good funnel thresholds are greater than average thresholds;
- `margin.goodMin > margin.thinMin > margin.lossBelow`;
- `drr.goodMax < drr.warnMin`;
- `roi.goodMin > roi.warnBelow`;
- day and stock thresholds are non-negative;
- automation actions belong to a closed enum.

## API

### Read active profile

`GET /api/wb/reports/rules`

Returns the active profile, version, preset, timestamps, actor information, fixed ABC metadata, built-in presets, available automation actions, and `canWrite`.

### Preview a draft

`POST /api/wb/reports/rules/preview`

Requires `settings:write`. Accepts `expectedVersion`, profile metadata, and the complete draft configuration. It validates the draft and evaluates it against available current report rows or source-cache aggregates. The response contains:

- affected row count;
- status changes by report;
- ABC and recommendation changes;
- automation impact counts;
- representative changed rows with old status, new status, and reasons;
- a short-lived `previewToken` containing a hash of the normalized draft and expected version.

Preview never mutates the active profile. Missing report data is reported as unavailable rather than treated as zero.

### Activate a draft

`PUT /api/wb/reports/rules`

Requires `settings:write`. Accepts the normalized draft, `expectedVersion`, and `previewToken`. The token must match the draft and current active version. A successful request creates the next active version and records an audit event. A stale version returns HTTP `409` without modifying the active profile.

### Read history

`GET /api/wb/reports/rules/history?limit=...`

Returns real profile versions and audit metadata in reverse chronological order. History is read-only in this feature; rollback may be implemented later as a new preview-and-save operation.

### Manager plans

The rules page uses the existing monthly digest plan endpoints rather than embedding plans inside the threshold profile. It loads the selected month, supports manual edits and XLSX import, and saves through the existing backend validation. Manager plans remain organization-scoped and feed the plan-versus-actual report calculation.

## Rule Evaluation Service

Add a report-rules service that owns normalization, validation, band classification, composite rule evaluation, and recommendation generation. Report builders call this service instead of duplicating thresholds.

The service accepts a metric dictionary and returns:

```json
{
  "bands": {"marginPct": "good", "crPct": "bad"},
  "status": "risk",
  "statusReasons": ["CR below average threshold"],
  "recommendedActions": [
    {
      "type": "rnp",
      "state": "draft",
      "reason": "badCr",
      "requiresConfirmation": true
    }
  ]
}
```

Metric states are `good`, `average`, `bad`, or `unknown`. A missing or untrusted source produces `unknown`; it must not create a negative recommendation.

Composite conditions follow the page's rule language:

- `AA + good margin` creates the mapped price-review draft;
- bad CR with at least 500 trustworthy observations creates the mapped RNP draft;
- margin below loss creates the mapped liquidation-review draft;
- high DRR combined with low ROI creates the mapped advertising-review draft;
- OOS risk creates the mapped alert draft;
- weak margin or a C classification creates the mapped audit draft.

The rule engine only describes the recommendation. Existing confirmation flows remain responsible for any later external mutation.

The 500-observation minimum is a fixed evidence guard, not a user-editable business threshold. It preserves the page's existing `Bad CR + показы` meaning and prevents recommendations from sparse samples.

## Report Integration

Each response includes `rulesProfileVersion` and applies only the rules for which it has trustworthy metrics.

| Report | Applied rules |
| --- | --- |
| ABC | Fixed rank shares, funnel bands, buyout, margin, DRR/ROI, composite status and recommendation drafts |
| RNP | CTR, CR, cart-to-order, buyout, margin and advertising-quality recommendations |
| P&L | Margin, thin-margin, loss and buyout states |
| Advertising | CTR/CR where available, DRR, ROI and advertising-review drafts |
| Stock | Days to OOS, critical stock units, localization and OOS alerts |
| Week over week | Current-period quality bands plus reasons for material deterioration where the metric exists |

Hard-coded thresholds within these classifications are replaced by the active profile. Structural calculations, financial formulas, WB source interpretation, and safety limits such as `P_min` are not report rules and remain unchanged.

The stock report's OOS KPI and management-card text use the saved `daysToOos.warnBelow` and `stockUnits.criticalBelow` values. Similar top-level counters in other reports must be derived from the same evaluated row states, so headline numbers and row badges cannot disagree.

## Cache Behavior

Derived report cache identity includes the active rules version. A response built with version `N` is not returned as current after version `N+1` becomes active. Source caches are not deleted because their WB data remains valid; only derived report payloads are rebuilt.

Background job keys and returned metadata retain enough rule-version information to prevent an older in-flight job from overwriting or masquerading as a report for the newly active profile. If a job finishes under an old version, it may remain stored under that version but the next request starts or returns the current-version report.

## Frontend Behavior

The `ReportRulesIsland` replaces static constants and direct mutation of the HTML prototype state with API-backed state:

- initial loading, error, and permission states;
- active profile and editable draft;
- complete preset selection;
- `custom` state after manual editing;
- all current fields plus the missing editable ROI warning threshold;
- editable automation mapping using allowed backend action values;
- dirty-state and reset behavior;
- backend preview modal;
- save enabled only for the exact successfully previewed draft;
- real version, author, timestamp, and history;
- monthly manager-plan loading and editing.

After save, the island replaces its active state with the returned canonical profile. Report pages consume backend-evaluated fields; frontend code may render labels and chips but must not independently reclassify live report rows.

## Error Handling

- Invalid fields return HTTP `422` with field paths and human-readable Russian messages.
- A stale `expectedVersion` or preview token returns HTTP `409`; the page keeps the user's draft and offers to reload the active version.
- Preview failure leaves the active profile untouched.
- Save failure leaves the draft and preview visible for retry.
- Read failure shows a retry state and does not silently substitute demo values.
- Missing source metrics produce `unknown` bands and no unsafe recommendation.
- Users without `settings:write` see a read-only profile and history.

## Audit and Observability

Successful activation records an existing control-plane audit event with organization, actor, old and new versions, preset, changed field paths, preview impact totals, and request correlation information. Logs and report metadata include `rulesProfileVersion` so a displayed classification can be traced back to its configuration.

## Verification Strategy

Verification remains targeted:

- persistence and reload of an organization profile;
- all three presets and transition to custom;
- fixed ABC enforcement and threshold ordering validation;
- optimistic concurrency conflict;
- preview token and no-mutation guarantee;
- one representative trigger in ABC/RNP, P&L, advertising, stock, and WoW;
- missing metrics returning `unknown` without a recommendation;
- rules version separating derived report caches;
- frontend load, preview, save, reset, and read-only behavior;
- manager plans loading and saving through the real endpoint.

No broad unrelated regression suite is required for this feature. Existing focused report tests should be extended where the classification contract changes.

## Implementation Boundaries

Backend profile persistence, rule evaluation, API routes, and report-builder integration form one coherent feature because persisted values are not useful until reports consume them. The frontend island then exposes that contract. Work should preserve the existing uncommitted WoW changes and avoid unrelated refactoring of the large parity page.
