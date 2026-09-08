DONE

# Задача: реальные health и readiness endpoints

Ты работаешь отдельным автономным агентом над backend Satorna в `/Users/ilagulakin/Desktop/Work/OgniWB`.

## Перед началом

Полностью прочитай `SATORNA_ARCHITECTURE_HANDOFF.md`, `SATORNA_SPEC_AUDIT.md`, указанный там architecture design и все применимые инструкции/README. Проверь фактический backend Git state и создай отдельный worktree/branch от актуального canonical head. Пользовательские изменения сохранить.

## Цель

Test-first реализовать настоящие `/health/live` и `/health/ready`, сохранив обратную совместимость существующего `/health`.

## Требования

- `/health/live` подтверждает только жизнеспособность процесса и не зависит от внешних сервисов.
- `/health/ready` с короткими bounded timeout реально проверяет PostgreSQL и Redis.
- Worker/Beat отражаются через уже существующий heartbeat, если он есть. Если его нет, не создавай распределённую подсистему: сначала зафиксируй честное ограничение и реализуй минимальную проверяемую readiness semantics.
- При недоступной обязательной зависимости readiness возвращает non-2xx и стабильный error/state contract.
- Не проглатывай DB/Redis errors и не переходи к локальным defaults.
- Ответ может содержать безопасные revision, build time, Alembic revision и contract version.
- Не выводи DSN, host credentials, tokens, cookies или stack traces.
- Существующий `/health` остаётся совместимым для текущего monitoring.
- Переиспользуй текущие DB/Redis factories; не добавляй dependency или framework без необходимости.

## Тесты

Минимально проверь:

- live при healthy/degraded dependencies;
- ready при healthy dependencies;
- DB failure;
- Redis failure;
- timeout;
- отсутствие sensitive fields;
- совместимость `/health`.

Запусти targeted tests, compile check и релевантный backend suite.

## Жёсткие границы

- Не изменять `app/platform/finance/**`, `app/platform/period.py`, миграции `0047–0052`, `docker-compose.yml`, `ops/runtime-db-role.sql` и handoff.
- Не создавать Alembic revision.
- GitHub и production не использовать; ничего не деплоить.
- Не исправлять попутно unrelated legacy failures.

## Результат

Оставь один локальный commit. Сообщи contract endpoints, изменённые файлы, тесты, ограничения проверки Worker/Beat и безопасную последовательность отдельного будущего rollout.
