# INDEEPA WB implementation readiness matrix

Дата: 2026-05-19  
Назначение: связать PRD-разделы с backlog, blockers и handoff.

| PRD | Sprint cut | Главные blockers | Handoff |
|---|---|---|---|
| `01-repricer-core-prd.md` | Sprint B | WB-06, WB-22, WB-23 | Backend + Frontend |
| `02-repricer-settings-prd.md` | Sprint A | WB-14, WB-23 | Backend + Frontend |
| `03-repricer-strategies-prd.md` | Sprint C | WB-14, WB-22, WB-25 | Backend + Frontend + UAT |
| `04-price-input-safety-prd.md` | Sprint B | WB-06, WB-17, WB-18, WB-23 | Backend + Frontend + UAT |
| `05-accounts-roles-audit-prd.md` | Sprint A | WB-24 | Backend + Frontend |
| `06-nrp-unit-pnl-prd.md` | Sprint D | WB-12, WB-13, WB-24 | Backend + Frontend + UAT |
| `07-nrp-planfact-prd.md` | Sprint D | WB-12, WB-13, WB-24 | Backend + Frontend + UAT |
| `08-nrp-rnp-ads-prd.md` | Sprint D | WB-02, WB-03, WB-11 | Backend + Frontend + UAT |
| `09-nrp-rating-prd.md` | Sprint D | WB-19, WB-25 | Backend + Frontend + UAT |
| `10-excel-big-tables-prd.md` | Sprint E | WB-03, WB-24 | Backend + Frontend + UAT |

## Implementation gate

Sprint A can start after:

- WB account/token access is available.
- Current PRD-pack is accepted as implementation baseline.
- `docs/open-questions-current.md` has current `BLOCKER / CONFIRM / LATER` statuses.

Sprint B can start after:

- P_min/P_max, СПП fallback and price apply/status handling are mapped.
- Settings model is implemented or frozen enough for guard defaults.

Sprint C can start after:

- 4599 and 4600 rules are confirmed.
- 4600 mode is selected: INDEEPA percent-only or Vella percent/rub floor.
- Night schedule is confirmed.
- 4445 remains disabled unless Мария confirms rules.

Sprint D can start after:

- WB Ads source and report mapping are known.
- P&L formula decisions are confirmed by Максим.
- Plan-fact v1 level is locked to company/manager unless full matrix is approved.

Sprint E can start after:

- Import templates are selected.
- UAT dataset is prepared.
- Permission boundaries for financial export are confirmed.

