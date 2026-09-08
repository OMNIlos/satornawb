# Задача: discovery Reviews и Notifications

Ты работаешь отдельным read-only агентом в `/Users/ilagulakin/Desktop/Work/OgniWB`.

## Перед началом

Полностью прочитай handoff, audit, architecture design, review/notification plans и применимые instructions. Изучи WB/Avito review adapters, AI drafts, approval/send flows, Telegram/system notifications, ORM, caches, jobs, tests и frontend. GitHub и production не использовать.

## Цель

Подготовить canonical module boundaries и migration plan для Reviews и Notifications без изменения текущей отправки.

## Исследование

Проверь:

- organization/account ownership каждой таблицы;
- external feedback/review identity;
- sync snapshot и deduplication;
- templates/rules/brand voice;
- AI prompt/input/output provenance;
- draft → approve → send lifecycle;
- permissions `read/generate/approve/send`;
- idempotency/retry внешней отправки;
- audit и sensitive payload filtering;
- Telegram preferences/deliveries;
- где нужен outbox, а где прямой вызов достаточен;
- cross-tenant risks и missing RLS;
- plaintext secrets/tokens;
- cache/frontend contracts.

Предложи минимальные canonical facts/jobs и bounded rollout sequence. Outbox вводи только для действий, потеря которых недопустима.

## Жёсткие границы

- Только чтение и один новый Markdown report.
- Не вызывать OpenAI, WB, Avito или Telegram.
- Не генерировать и не отправлять реальные ответы/уведомления.
- Код, schema, migrations, secrets, handoff и production не менять.

## Результат

Один docs-only commit с ownership matrix, lifecycle, outbox decision, permission model, migration slices, tests и rollback strategy.
