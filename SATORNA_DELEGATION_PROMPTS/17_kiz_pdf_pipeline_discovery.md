# Задача: discovery KIZ/ЧЗ и PDF pipeline

Ты работаешь отдельным read-only агентом в `/Users/ilagulakin/Desktop/Work/OgniWB`.

## Перед началом

Полностью прочитай handoff, audit, architecture design и инструкции всех затронутых repositories. Изучи `wb-pdf-matcher`, backend/frontend integrations, parsers, renderer, file storage, routes, jobs и tests. GitHub и production не использовать.

## Цель

Определить безопасную архитектуру canonical KIZ allocation в PostgreSQL с переиспользованием существующего matcher/parser/renderer как adapter.

## Исследование

Установи:

- форматы WB labels и Честного Знака;
- parsing/matching rules;
- текущее хранение codes/jobs/leases;
- process-memory и file risks;
- связь code с order item и CatalogSku;
- duplicate/empty code behavior;
- PDF render/merge flow;
- retry/crash recovery;
- external identities и checksums.

Спроектируй lifecycle:

```text
available → reserved → assigned → printed → void
```

Опиши PostgreSQL uniqueness, atomic allocation, row locking, idempotency key, lease expiry, audit и recovery. Определи минимальную границу Python modular monolith ↔ существующий Node adapter; не переписывай рабочие parsing/PDF компоненты без причины.

## Жёсткие границы

- Только чтение и один новый Markdown document.
- Не запускать production jobs, не импортировать реальные КИЗ и не генерировать боевые PDF.
- Код, schema, migrations, files state, handoff и production не менять.
- Не создавать микросервис/event bus.

## Результат

Один docs-only commit с component reuse matrix, canonical lifecycle/schema sketch, concurrency proof obligations, API boundaries, rollout и test plan.
