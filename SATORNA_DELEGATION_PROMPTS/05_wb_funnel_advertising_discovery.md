DONE

# Задача: discovery WB funnel и advertising facts

Ты работаешь отдельным read-only агентом в `/Users/ilagulakin/Desktop/Work/OgniWB`.

## Перед началом

Полностью прочитай handoff, spec audit, architecture design и применимые инструкции. Проверь текущие backend adapters, tasks, caches, report builders, tests и fixtures. Не используй GitHub или production.

## Цель

Подготовить минимальный canonical design для WB funnel и advertising facts, необходимых ABC, P&L и РНП. Не реализовывать schema или код.

## Исследование

Найди все источники и consumers для:

- views/transitions;
- baskets;
- orders;
- buyouts/redemptions;
- cancellations/returns;
- campaign identity;
- advertising impressions/clicks/orders/spend;
- attribution и неизвестной attribution.

Для каждого потока зафиксируй:

- WB endpoint и adapter function;
- source grain и external identity/fingerprint;
- organization/account/product ownership;
- business date, timezone и period limits;
- pagination/rate limits/retry;
- cache key, freshness и partial states;
- дедупликацию и repeated SyncRun semantics;
- текущих consumers и формулы;
- data-quality blockers.

Предложи минимальные таблицы facts/snapshots, обязательные constraints/indexes и idempotent SyncRun flow. Раздели confirmed facts и derived attribution. Никакой универсальной event model.

## Жёсткие границы

- Только чтение кода/evidence и один новый docs-файл.
- Не трогать canonical finance/period, Alembic, runtime config или handoff.
- Не вызывать WB и не менять production/cache state.
- Не придумывать missing fields и не смешивать funnel с finance revenue.

## Результат

Один docs-only commit: source/consumer matrix, proposed grain, identity rules, schema sketch, rollout sequence, parity fixtures и открытые вопросы.
