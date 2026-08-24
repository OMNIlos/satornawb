# Avito Orders Extension UI Design

## Goal

Make Avito order collection feel like a simple operator workflow instead of a technical debug surface.

## Extension

- The popup has two top-level screens: "Сбор" and "Настройки".
- "Сбор" shows only the latest status, one primary "Собрать заказы" action, and a compact last-run hint.
- "Настройки" contains grouped sections:
  - "Подключение": Satorna token.
  - "Данные заказа": photo count, size mode, color and article toggles.
  - "Диагностика": logs and clear logs action.
- Technical logs stay available but hidden from the default screen.
- The Avito page overlay shows human progress and basic missing-field counts; detailed errors stay in extension logs.

## Frontend `/avito/orders`

- Before browser snapshot data exists, the page shows only one onboarding block.
- The onboarding block explains three steps: create/copy token, paste it into the extension, collect Avito orders.
- Tables, toolbars, KPI strips, and production blocks are hidden while there are no extension rows.
- Once extension rows exist, the page shows the production picking workflow.
- Remove the old top KPI strip with orders/status/sum cards from this route.
- Hide browser collector diagnostics from the normal data-present view.

## Testing

- Extension popup behavior is covered by DOM tests for default screen, settings screen, and logs placement.
- Frontend source tests assert that removed KPI labels and diagnostics do not ship on the Avito orders route.
