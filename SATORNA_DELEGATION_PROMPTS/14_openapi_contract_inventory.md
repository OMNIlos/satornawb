# Задача: инвентаризация OpenAPI и typed contracts

Ты работаешь отдельным read-only агентом в `/Users/ilagulakin/Desktop/Work/OgniWB`.

## Перед началом

Полностью прочитай handoff, spec audit, architecture design и инструкции backend/frontend. Проверь текущие FastAPI routes/Pydantic models, OpenAPI artifacts, frontend Zod schemas, generated types, proxy rewrites и contract tests. GitHub и production не использовать.

## Цель

Спроектировать постепенный переход к направлению `backend Pydantic → OpenAPI → generated frontend types` без big bang и без изменения runtime contracts.

## Исследование

Составь inventory:

- каждый route без `response_model`;
- route с неточным/неполным model;
- generated Pydantic/TypeScript, который нигде не используется;
- OpenAPI, генерируемый из frontend Zod;
- ручные дубли contracts;
- одинаковые paths с разными владельцами backend/serverless;
- успешные non-JSON API responses;
- нестабильные error envelopes;
- money fields без `Kopecks` suffix;
- проценты-строки;
- sensitive fields;
- отсутствие source/snapshot/period metadata.

Разбей миграцию на небольшие batches с непересекающимися route files. Для каждого batch укажи source of truth, compatibility test, generated artifact и rollback. Приоритет: новые `/api/v2`, затем production-critical legacy routes.

## Жёсткие границы

- Только чтение и один новый Markdown/CSV report.
- Не генерировать и не коммитить contracts в этой задаче.
- Не менять routes, frontend, rewrite, finance/period, migrations, handoff или production.
- Не использовать GitHub CI.

## Результат

Один docs-only commit с route matrix, ownership conflicts, recommended generation direction, batch order и verification commands.
