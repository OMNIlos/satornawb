о# Задача: finance observability и incident runbook

Ты работаешь отдельным автономным агентом в `/Users/ilagulakin/Desktop/Work/OgniWB`.

## Перед началом

Полностью прочитай handoff, period/finance plan, spec audit, architecture design, canonical finance ORM/migrations/service и существующие ops scripts. Создай отдельный worktree/branch. GitHub и production не использовать.

## Цель

Создать минимальный read-only observability pack для canonical finance, пригодный для ручной проверки и будущего monitoring.

## Требования к SQL/checks

Покрой:

- published/pending/incomplete sync runs;
- rollup readiness;
- snapshot-chain depth и cycles;
- operation/membership/rollup counts;
- operation-count reconciliation;
- total/component revenue reconciliation с нулевым monetary tolerance;
- source freshness и last observed age;
- orphan operations/memberships;
- RLS/FORCE RLS, policy и runtime-role attributes;
- отсутствие tenant context, org1/org2 visibility;
- exact-period query `EXPLAIN (ANALYZE, BUFFERS)`;
- lock waits и long transactions вокруг finance tables.

SQL должен быть только `SELECT`, catalog inspection и `EXPLAIN`. Tenant context устанавливается только `SET LOCAL` внутри read-only transaction. Никаких `UPDATE`, `DELETE`, DDL, password или DSN.

## Runbook

Опиши:

- normal/warning/critical thresholds;
- действия при pending rollup, mismatch, stale snapshot, failed migration и RLS violation;
- какие проверки безопасны под runtime role, а какие требуют migration owner;
- rollback к предыдущему image без немедленного DB downgrade;
- какие данные собрать до вмешательства;
- запрет синтетической finance correction.

Переиспользуй существующие tools; не создавай monitoring framework.

## Verification

Проверь syntax на task-owned PostgreSQL fixture/clone, если он уже доступен локально. Не подключайся к production. Докажи, что script не содержит mutating statements или secrets.

## Жёсткие границы

- Не менять canonical finance code/migrations, `ops/runtime-db-role.sql`, compose, handoff или production.
- Никаких GitHub/external services.
- Новые файлы должны иметь уникальные имена и не заменять существующие runbooks.

## Результат

Один локальный commit с read-only SQL и Markdown runbook. В финале укажи команды запуска, поддерживаемые роли, verification и намеренно отсутствующую автоматизацию.
