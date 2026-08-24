# Frontend checklist: INDEEPA WB replacement

Дата: 2026-05-19  
Основа: PRD-пакет `docs/specs/indeepa-wb-replacement/`.

## Цель

Frontend должен перенести PRD в рабочий Vella UX: понятные таблицы, drawer, settings, approval flows, report states и UAT-ready сценарии без копирования перегруженной INDEEPA BI-плотности.

## Общие правила

- Использовать Vella production shell и существующие tokens/classes.
- Не создавать новый визуальный shell без отдельного согласования.
- Большие таблицы: sticky фото/артикул, sticky header, horizontal scroll, virtualization.
- Все сокращения и рискованные controls получают tooltip.
- Все risky actions идут через preview/diff/approval, без скрытого сохранения.

## Sprint A: settings/account surfaces

- Экран account health: token status, expiry, missing scopes, last sync.
- Settings screen с 17 параметрами, сгруппированными 1-5 как в PRD.
- Для каждого параметра: текущее значение, allowed options, affected strategies/guards.
- Diff перед сохранением настроек, no-access/read-only state.
- Audit drawer/filter для settings changes.

## Sprint B: repricer core

- Таблица SKU: фото, артикулы, бренд, категория, менеджер, цены, СПП, маржа, ABC/rating, акция, остатки, корзины, заказы, реклама, strategy, status.
- SKU drawer: экономика, price planes, P_min/P_max, source freshness, strategy explanation, history, comments, audit.
- Price draft UI: ручное изменение, пересчет маржи, blocked guard reasons.
- Apply preview: selected rows, valid, blocked, partial data, expected margin impact.
- Job state UI: queued/sent/accepted/failed/retry.

## Sprint C: strategies

- Strategy list: 4599, 4600, night mode, 4445 placeholder.
- Dry-run preview: SKU count, examples, price deltas, blocked guards.
- 4600 mode choice visible as unresolved until confirmed.
- 4445 displayed as `discovery_required`; no enable/apply button.
- Night mode off-by-default with explicit schedule, warning and audit.

## Sprint D: NRP-lite

- Unit P&L: preliminary/final state, expense breakdown, no-access financial state.
- РнП: funnel rows, campaign status breakdown, attribution confidence, review candidates only.
- План-факт: company/manager view, plan/fact/deviation/%/forecast/minimum per day.
- Рейтинг SKU: group cards, reason chips, transition to SKU drawer and actions.
- Empty states distinguish no data, no plan, no access, source missing.

## Sprint E: Excel + UAT UI

- Import flow: upload, mapping, validation result, preview, approval, apply state.
- Export flow: current view, visible/all columns, filters/period metadata.
- Column presets and saved views for repricer and reports.
- UAT mode/screenshots: stable visible states for price draft, blocked guard, preliminary P&L, weak ad attribution, empty plan.

## Acceptance

- Фил может показать v1/P2 boundaries from UI copy and docs without explaining hidden assumptions.
- Менеджер sees why a price is blocked without opening developer logs.
- Мария can move from report problem to SKU action in one drill-down.
- Максим can identify preliminary vs final financial data immediately.

