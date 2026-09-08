# Задача: исправить один batch legacy failures

Ты работаешь отдельным автономным агентом над backend Satorna в `/Users/ilagulakin/Desktop/Work/OgniWB`.

## Обязательное предусловие

Сначала найди и полностью прочитай актуальный отчёт, созданный задачей `09_legacy_test_failures_triage.md`. Если отчёта нет, набор failures изменился или невозможно однозначно выбрать один свободный batch — остановись без изменений и сообщи blocker.

Также полностью прочитай handoff, spec audit, architecture design и применимые инструкции. Создай отдельный worktree/branch от актуального canonical head. GitHub и production не использовать.

## Цель

Выбрать ровно один ещё не занятый root-cause batch из triage и исправить его минимальным общим изменением.

## Правила реализации

- Зафиксируй выбранный batch и список разрешённых файлов до редактирования.
- Воспроизведи каждый failure batch отдельно.
- Проследи всех callers изменяемой функции.
- Исправляй общий root cause в shared boundary, а не добавляй guards во все callers.
- Ожидание теста меняй только при доказанном contract drift.
- Wall clock фиксируй существующей инъекцией времени или минимальным clock seam.
- Unit tests не должны выполнять реальные network calls.
- Не добавляй abstraction/configuration «на будущее».
- Не расширяй scope на второй batch.

## Verification

Запусти:

1. один failing test до исправления;
2. весь выбранный batch;
3. соседние tests общего code path;
4. полный backend suite;
5. compile и diff checks.

Явно сравни оставшийся failure set с triage baseline.

## Жёсткие границы

- Не менять `app/platform/finance/**`, `app/platform/period.py`, migrations `0047–0052`, compose/runtime role или handoff.
- Не деплоить, не менять production, не использовать GitHub.
- Не коммитить test-mutated runtime files.
- Если root cause требует изменения запрещённого файла или другого batch, остановись и отчитайся.

## Результат

Один локальный commit. В финале: выбранный batch, root cause, изменённые файлы, before/after test counts, полный suite result и оставшиеся failures.
