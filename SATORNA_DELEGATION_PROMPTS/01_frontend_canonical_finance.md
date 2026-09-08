DONE

# Задача: frontend-клиент canonical finance

Ты работаешь отдельным автономным агентом над frontend Satorna в `/Users/ilagulakin/Desktop/Work/OgniWB`.

## Перед началом

Полностью прочитай:

1. `/Users/ilagulakin/Desktop/Work/OgniWB/SATORNA_ARCHITECTURE_HANDOFF.md`.
2. `/Users/ilagulakin/Desktop/Work/OgniWB/SATORNA_SPEC_AUDIT.md`.
3. Architecture design и frontend plan, указанные в handoff.
4. Все применимые `AGENTS.md`, `SYSTEM_PROMPT.md` и README.

Найди canonical frontend Git repository самостоятельно. Создай отдельный worktree и branch. Не изменяй существующие рабочие деревья и не перезаписывай пользовательские изменения.

## Цель

Подготовить frontend к безопасному canary чтения `GET /api/v2/wb/finance`, не переключая production и не удаляя legacy route.

Сначала проверь, существуют ли уже:

- rewrite `/api/v2/*`;
- явная `INVALID_API_RESPONSE` для успешного non-JSON ответа;
- типы canonical finance;
- feature flag или organization rollout;
- общий period/account selector и stale-request protection.

Переиспользуй существующее. Не создавай второй API client, formatter или period model.

## Требования

- Добавь минимальный типизированный client для `/api/v2/wb/finance`.
- `marketplaceAccountId` и period передаются явно.
- Поддержи `ready`, `partial`, `future`, `empty`, `missing` без неявного fallback на v1.
- `null` не превращается в `0`; `0` остаётся валидным значением.
- Деньги приходят в kopecks и форматируются только на уровне UI.
- Не рассчитывай финансовые формулы в React.
- Сохрани отмену stale A→B→A запросов.
- Новый route/consumer включается только feature flag, выключенным по умолчанию.
- Legacy consumer остаётся явным rollback path.
- Если `/api/v2` rewrite отсутствует, добавь его выше общего `/api/*` fallback.
- Если обработка non-JSON уже корректна, только закрепи её тестом.

## Тесты

Добавь минимальные consumer/Vitest tests для:

- каждого source state;
- `null` против `0`;
- account и custom period params;
- stale response;
- non-JSON API response;
- выключенного feature flag.

Запусти relevant tests, полный frontend test suite, typecheck и production build.

## Жёсткие границы

- Backend, Alembic и production не изменять.
- GitHub, pull request, Vercel deploy и внешние review-сервисы не использовать.
- Feature flag не включать.
- Не переносить ABC/P&L формулы во frontend.
- Не редактировать `SATORNA_ARCHITECTURE_HANDOFF.md`.

## Результат

Оставь один локальный commit. В финале сообщи branch/worktree, commit, изменённые файлы, проверки, результаты и точный способ будущего включения/rollback. Если обнаружен конфликт или уже готовая реализация, не дублируй её: зафиксируй доказательства и остановись.
