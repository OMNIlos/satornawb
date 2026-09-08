# Задача: классификация 105 legacy test failures

Ты работаешь отдельным автономным агентом над backend Satorna в `/Users/ilagulakin/Desktop/Work/OgniWB`.

## Перед началом

Полностью прочитай handoff, spec audit, architecture design и инструкции проекта. Найди canonical backend repository, создай отдельный worktree/branch от актуального локального head и проверь dirty state. Пользовательские изменения не трогать. GitHub и production не использовать.

## Цель

Воспроизвести и классифицировать известный baseline `105` failures так, чтобы последующие агенты могли исправлять независимые root-cause batches без конфликтов.

## Работа

1. Запусти полный backend suite в том же окружении, сохрани итоговые test IDs и duration.
2. Сравни фактический набор с documented baseline. Новый или исчезнувший failure отметь отдельно; не объявляй его автоматически улучшением/регрессией.
3. Для каждого failure воспроизведи минимальную группу тестов и изучи общий code path.
4. Классифицируй причины:
   - реальная продуктовая ошибка;
   - устаревший contract теста;
   - wall-clock/timezone;
   - shared mutable/module state;
   - order dependence;
   - сеть/credentials;
   - DB/JSON/in-memory fallback;
   - cache contamination;
   - authorization drift;
   - fixture/schema drift.
5. Сформируй batches с непересекающимися production/test files.

Для каждого batch укажи test IDs, общий root cause, evidence, разрешённые файлы, риски, минимальный fix и команды verification.

## Жёсткие границы

- На этом проходе production code и ожидания тестов не менять.
- Разрешён только один новый triage Markdown/JSON summary.
- Не трогать canonical finance/period, migrations, compose/runtime role, handoff или production.
- Не выполнять реальные внешние API calls.
- `var/vella_repricer_runtime_state.json` и другие test-mutated пользовательские файлы не коммитить и не восстанавливать поверх чужих изменений.

## Результат

Один docs-only commit. Отчёт должен содержать точный reproduced count, diff с baseline, root-cause batches в рекомендуемом порядке и готовые scope boundaries для `10_fix_one_legacy_failure_batch.md`.
