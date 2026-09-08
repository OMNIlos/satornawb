DONE

# Задача: discovery WB prices и stocks

Ты работаешь отдельным read-only агентом в `/Users/ilagulakin/Desktop/Work/OgniWB`.

## Перед началом

Полностью прочитай handoff, audit, architecture design и инструкции проекта. Найди все goods/prices/SPP/stocks adapters, caches, tasks, repricer/report consumers и tests. GitHub и production не использовать.

## Цель

Определить canonical facts/snapshots для WB prices и stocks без реализации.

## Исследование

Проследи:

- seller price, discount, buyer price, SPP и wallet discount;
- goods/content product identity;
- warehouse stocks и aggregate stocks;
- historical/daily stocks;
- current snapshot и business-time semantics;
- зависимости repricer, reports и production UI.

Для каждого значения укажи:

- источник и фактический grain (`account/product/offer/warehouse/date`);
- confirmed или derived значение;
- external identity;
- tenant/account scope;
- snapshot versus append-only history;
- freshness/error/partial states;
- cache identity;
- дедупликацию;
- period applicability;
- необходимые constraints/indexes.

Отдельно зафиксируй неоднозначность buyer price/SPP и запрещённые fallback. Предложи минимальную migration/shadow sequence и список legacy caches, удаляемых только после canary.

## Жёсткие границы

- Код, DDL, Alembic, production и handoff не менять.
- Не выполнять live WB calls.
- Не объединять product и offer grain без доказанного mapping.
- Не рассчитывать цены во frontend.

## Результат

Создай один новый Markdown-отчёт и docs-only commit. В финале перечисли inspected files, найденные противоречия и чёткий boundary будущего slice.
