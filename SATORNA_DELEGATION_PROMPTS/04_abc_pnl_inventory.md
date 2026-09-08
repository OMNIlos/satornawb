DONE

# Задача: инвентаризация ABC/P&L перед canonical projection

Ты работаешь отдельным read-only агентом в `/Users/ilagulakin/Desktop/Work/OgniWB`.

## Перед началом

Полностью прочитай `SATORNA_ARCHITECTURE_HANDOFF.md`, `SATORNA_SPEC_AUDIT.md`, architecture design, canonical costs plan, period/finance plan и все применимые инструкции. Проверь текущий код, тесты, fixtures и локальные production evidence. GitHub и production не использовать.

## Цель

Подготовить доказательную карту текущих ABC и P&L для следующего bounded backend slice. Это discovery, не реализация.

## Работа

Проследи каждый фактический flow:

```text
HTTP route / Celery task
→ builder/use case
→ runtime/cache/database
→ WB/source adapter
→ formula
→ response/cache
```

Зафиксируй с `file:line`:

- все ABC/P&L endpoints и background producers;
- formula/rules versions;
- signed sales, returns, redemptions и late corrections;
- commission, logistics, storage, acceptance, acquiring, penalties, deductions и compensations;
- COGS и economics selection на business date;
- grain каждой метрики и mapping `nmId → offer → CatalogSku`;
- union-SKU semantics и unattributed finance facts;
- `null`, `0`, `missing`, `assumed`, `blocked`, `restricted`;
- cache keys, TTL, revision identity и invalidation;
- прямые зависимости от repricer cache/module globals;
- frozen fixtures, live evidence и необъяснённые gaps;
- current response size и performance baseline.

Предложи минимальный canonical ABC/P&L contract: inputs, outputs, source states, pagination/summary, version identity и acceptance gates. Не проектируй универсальный reporting engine.

## Жёсткие границы

- Код, tests, schema, migrations, handoff и production не менять.
- Никаких WB-запросов и новых live snapshots.
- Не объявлять исторические live-числа вечной константой.
- Не синтезировать отсутствующую корректировку `120,800` kopecks.

## Результат

Создай только один новый Markdown-отчёт в отдельном worktree с уникальным именем. Он должен содержать current-flow map, таблицу формул/источников, blockers, минимальный slice boundary, тестовую матрицу и список решений, требующих подтверждения. Один локальный docs-only commit; без реализации.
