# Задача: аудит tenant ownership всех таблиц

Ты работаешь отдельным read-only агентом в `/Users/ilagulakin/Desktop/Work/OgniWB`.

## Перед началом

Полностью прочитай handoff, spec audit, architecture design и security/DB instructions. Изучи все SQLAlchemy ORM, raw SQL, migrations, Redis keys, file/object paths и tests. GitHub и production не использовать.

## Цель

Классифицировать каждую persisted сущность и составить доказательный backlog tenant hardening.

## Классификация

Каждой таблице присвой ровно один класс:

- `tenant_owned`;
- `global_reference`;
- `infrastructure`.

Для `tenant_owned` проверь:

- `organization_id`;
- `marketplace_account_id`, если применимо;
- composite FK и unique constraints;
- service/repository predicate;
- `ENABLE/FORCE ROW LEVEL SECURITY`;
- policy name/expression;
- transaction-local tenant context;
- runtime-role integration test;
- Redis/cache key scope;
- Celery task arguments;
- export/file/object path scope.

Особенно подробно проверь account health/capabilities, reviews, control-plane, jobs, source registry, notifications, infra runtime state и legacy production storage.

Не добавляй фиктивный `organization_id` к действительно глобальным справочникам: для них документируй владельца и immutability.

## Жёсткие границы

- Только чтение и один новый Markdown/CSV report.
- Schema, policies, migrations, code, handoff и production не менять.
- Не подключаться к live DB.
- Не считать application predicate заменой RLS или наоборот.

## Результат

Один docs-only commit с полной matrix, severity, evidence `file:line`, recommended migration batches и cross-tenant test cases.
