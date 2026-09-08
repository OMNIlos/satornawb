# Задача: аудит module-global состояния WB repricer

Ты работаешь отдельным read-only агентом в `/Users/ilagulakin/Desktop/Work/OgniWB`.

## Перед началом

Полностью прочитай handoff, audit, architecture design и инструкции. Изучи все repricer modules, routers, Celery tasks, persistence/cache layers, tests и real-price feature flags. GitHub и production не использовать.

## Цель

Получить доказательный план устранения mutable module globals до появления второго writer/replica, не меняя работающий repricer.

## Исследование

Найди каждый изменяемый module-level dict/list/set и для каждого укажи:

- readers и writers;
- hydrate/flush path;
- DB/Redis/file/in-memory persistence;
- organization/account scope;
- price-affecting ли состояние;
- cross-tenant leakage scenario;
- lost-update/race scenario;
- поведение API и Celery после restart;
- optimistic concurrency/idempotency requirements;
- минимальный canonical owner/table/service.

Отдельно проверь approvals, price actions, strategy assignments, audit/changelog, comments, promotions, tariff/commission cache и catalog cache.

Сформируй порядок containment:

1. state, влияющий на реальное применение цены;
2. approvals/actions;
3. organization settings/assignments;
4. diagnostics и disposable caches.

Предпочитай существующие PostgreSQL tables/services; не проектируй универсальное state repository.

## Жёсткие границы

- Только чтение и один новый Markdown-отчёт.
- Не менять real-price flags, runtime state, code, tests, schema, migrations или production.
- Не запускать задачи, способные отправить цену в WB.
- Не читать и не выводить marketplace credentials.

## Результат

Один docs-only commit с inventory matrix, race diagrams в текстовой форме, severity, минимальными bounded slices и безопасным первым implementation candidate.
