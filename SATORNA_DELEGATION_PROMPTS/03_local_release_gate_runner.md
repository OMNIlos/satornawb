DONE

# Задача: локальный release-gate runner

Ты работаешь отдельным автономным агентом в `/Users/ilagulakin/Desktop/Work/OgniWB`.

## Перед началом

Полностью прочитай `SATORNA_ARCHITECTURE_HANDOFF.md`, `SATORNA_SPEC_AUDIT.md`, architecture design и применимые инструкции. Инвентаризируй существующие test/build/migration scripts до написания нового. Создай отдельный worktree/branch; сохрани пользовательские изменения.

## Цель

Создать один локальный, неразрушающий release verification command, который заменяет ручную последовательность проверок. GitHub CI в эту задачу не входит.

## Требования

Команда должна переиспользовать уже установленные инструменты и последовательно проверять:

- compile и whitespace/diff checks;
- focused backend tests;
- полный backend `pytest`;
- frontend tests, typecheck и production build;
- единственный Alembic head;
- `upgrade → downgrade → upgrade` на task-owned PostgreSQL;
- существующие contract/OpenAPI checks.

Дополнительно:

- все временные container/database ресурсы получают уникальный task-owned prefix;
- cleanup удаляет только явно созданные ресурсы;
- interruption оставляет понятный recovery path;
- `105` legacy failures нельзя молча считать успехом: выведи отдельное точное сравнение с зафиксированным baseline, включая набор test IDs;
- новый failure всегда делает gate красным;
- вывод завершается коротким machine-readable summary и корректным exit code;
- секреты и environment values не печатаются.

Начни с самого короткого script на существующем shell/Python stack. Не добавляй orchestration framework.

## Тестирование

Проверь как минимум happy path, ранний failure, изменившийся baseline и точечный cleanup. Если полный suite дорогой, используй безопасный dry-run/unit seam для теста runner и один реальный targeted запуск.

## Жёсткие границы

- Не изменять canonical finance/period, миграции `0047–0052`, compose/runtime role или handoff.
- Не создавать GitHub workflow, не публиковать branch и не деплоить.
- Production DB/containers не использовать.
- Не выполнять broad Docker prune или recursive deletion.

## Результат

Оставь локальный commit с runner и короткой документацией. В финале укажи точную команду запуска, созданные ресурсы, результаты self-check и известные ограничения.
