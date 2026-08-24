# Digest progress and data contract design

The background digest job persists progress for four stages: queued (0%), orders/sales/finance (20%), warehouse stocks (50%), and ads/final assembly (80–100%). Each update carries a stable stage id, human-readable label, and current WB source. The digest page polls that status and renders a progress card with selected range, percentage, current request, start time, and fallback-data note.

The frontend normalizes the backend weekly-balance contract by reading `ordersUnits` and `salesUnits` into the chart's `value` and `compareValue` fields. This makes chart bars agree with the existing period cards and KPI totals.

OOS remains one backend aggregate row but includes its authoritative `skuCount` and SKU sample. The frontend displays that count rather than counting aggregate rows, labels it as affected SKU, and links to the stocks report.
