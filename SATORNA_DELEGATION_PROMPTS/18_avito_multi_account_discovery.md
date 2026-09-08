# Задача: discovery Avito multi-account architecture

Ты работаешь отдельным read-only агентом в `/Users/ilagulakin/Desktop/Work/OgniWB`.

## Перед началом

Полностью прочитай handoff, spec audit, architecture design и Avito-related plans/instructions. Изучи credentials, listings, orders, returns, chats, messages, stats, repricer, Celery tasks, caches, tests и frontend consumers. GitHub и production не использовать.

## Цель

Подготовить migration plan для 10–15 Avito accounts на одну организацию с account-owned credentials и строгой изоляцией.

## Исследование

Зафиксируй:

- текущую привязку credentials к user/organization;
- blocking `UNIQUE` constraints;
- external account/item/order/chat/message identities;
- grain listings/statistics/orders;
- account selection и allowed-account permissions;
- Redis/cache keys;
- background tasks и token refresh;
- external price/message actions;
- idempotency/retry/audit;
- cross-user/cross-account/cross-tenant leakage risks;
- response contracts и frontend assumptions.

Предложи bounded slices для `MarketplaceAccount`-owned credentials, account-scoped facts и repricer actions. Сохрани существующие Avito clients/adapters, если их contracts корректны.

## Жёсткие границы

- Только чтение и один новый report.
- Не читать/выводить реальные credentials и access tokens.
- Не вызывать Avito API, не отправлять сообщения и не менять цены.
- Код, schema, migrations, caches, handoff и production не менять.

## Результат

Один docs-only commit с current constraint matrix, target ownership, migration slices, security tests, rollout и blockers.
