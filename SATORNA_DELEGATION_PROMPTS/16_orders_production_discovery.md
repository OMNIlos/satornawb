# Задача: discovery Orders и Production

Ты работаешь отдельным read-only агентом в `/Users/ilagulakin/Desktop/Work/OgniWB`.

## Перед началом

Полностью прочитай handoff, audit, architecture design и инструкции. Изучи основной backend, frontend/backend production prototype, frontend consumers, WB/Avito order adapters, exports, print flows, tests и fixtures. GitHub и production не использовать.

## Цель

Подготовить bounded migration plan общей очереди WB+Авито и production, сохранив работающие печать/экспорт до parity.

## Исследование

Проследи:

- marketplace orders и items;
- external order/item identities;
- statuses, deadlines и transitions;
- returns/cancellations;
- mapping к MarketplaceAccount/Product/Offer/CatalogSku;
- production SKU/mapping;
- batches, print groups и print sheets;
- XLSX/PDF/export paths;
- audit и operator actions;
- concurrency/lost updates;
- JSON snapshot repository;
- tenant/account isolation;
- frontend/serverless ownership конфликтов.

Предложи минимальные границы модулей `Orders` и `Production`, canonical tables, optimistic concurrency и sequence `expand → backfill → shadow → canary → switch`. Production prototype нельзя удалять до полного функционального parity.

## Жёсткие границы

- Только чтение и один новый architecture-discovery document.
- Не менять backend/frontend code, JSON data, schema, migrations, handoff или production.
- Не объединять WB/Avito statuses без явной canonical mapping.
- Не выполнять печать, export или внешние actions.

## Результат

Один docs-only commit: current flow map, domain boundaries, proposed schema, status mapping, concurrency rules, parity matrix и независимые implementation slices.
