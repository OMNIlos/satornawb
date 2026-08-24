# API Contracts — Tooling

> Выбранный стек и обоснование. Процесс см. в [README.md](./README.md).

---

## Стек

### 1. Zod (TypeScript) — первоисточник правды

- **Версия:** Zod 3.x
- **Роль:** определение схем запросов/ответов на стороне фронта
- **Почему:**
  - Нативный TypeScript — Дмитрий использует его в UI-коде
  - Типы выводятся автоматически (`z.infer<typeof Schema>`) — нет дублирования
  - Поддерживает валидацию на уровне типов (min/max, email, regex)
  - Большое community, стабильный API

### 2. zod-to-openapi — экспорт OpenAPI 3.1 YAML

- **Пакет:** `@asteasolutions/zod-to-openapi`
- **Роль:** преобразование Zod-схем в OpenAPI YAML
- **Почему:**
  - Поддерживает OpenAPI 3.1 (включая nullable, oneOf, discriminated unions)
  - Хорошо интегрируется с express / fastify / Hono (если понадобится документация)
  - Активно поддерживается

### 3. datamodel-code-generator (Python) — генерация Pydantic

- **Пакет:** `datamodel-code-generator` (Koxudaxi)
- **Роль:** генерация Pydantic v2 моделей из OpenAPI YAML
- **Почему:**
  - Нативная поддержка OpenAPI 3.1
  - Pydantic v2 — стандарт FastAPI
  - Поддерживает сложные типы: Union, Literal, discriminator
  - Командная строка: `datamodel-codegen --input openapi/v1.yaml --output app/schemas/`

---

## Команды

### На стороне фронта (Дмитрий)

```bash
# Написать Zod схему
# contracts/schemas/wb-repricer/price-update.ts

# Экспортировать в OpenAPI и проверить базовые integration gotchas
npm run smoke-openapi

# Полученный файл: contracts/openapi/v1.yaml
# → PR в общий репо contracts
```

`export-openapi.ts` (упрощённо):

```ts
import { OpenAPIRegistry, OpenApiGeneratorV31 } from '@asteasolutions/zod-to-openapi'
import { WBRepricerUpdatePriceRequest, WBRepricerUpdatePriceResponse } from './schemas/wb-repricer/price-update'

const registry = new OpenAPIRegistry()

registry.registerPath({
  method: 'post',
  path: '/api/v1/wb-repricer/prices',
  operationId: 'wbRepricerUpdatePrice',
  request: { body: { content: { 'application/json': { schema: WBRepricerUpdatePriceRequest } } } },
  responses: {
    200: { description: 'OK', content: { 'application/json': { schema: WBRepricerUpdatePriceResponse } } },
    400: { description: 'Validation error', content: { 'application/json': { schema: ErrorSchema } } },
    429: { description: 'WB rate limit', content: { 'application/json': { schema: ErrorSchema } } },
  },
})

const yaml = new OpenApiGeneratorV31(registry.definitions).generateDocument({
  openapi: '3.1.0',
  info: { title: 'Огни API', version: '1.0.0' },
})

fs.writeFileSync('contracts/openapi/v1.yaml', yaml)
```

### На стороне бэка (Филипп)

```bash
# Pull последней версии contracts
git pull

# Генерация Pydantic
datamodel-codegen \
  --input contracts/openapi/v1.yaml \
  --input-file-type openapi \
  --output app/schemas/ \
  --target-python-version 3.11 \
  --use-schema-description \
  --output-model-type pydantic_v2.BaseModel

# → app/schemas/wb_repricer.py и т.д.
```

---

## Альтернативы, которые мы отклонили

| Альтернатива | Почему не подходит |
|---|---|
| **TypeBox** (вместо Zod) | Хорош, но менее популярен; Zod — де-факто стандарт для TS validation |
| **io-ts** | Более функциональный стиль, менее читаемый для команды |
| **JSON Schema напрямую** | Нет автокомплита в TS, сложнее поддерживать |
| **GraphQL + codegen** | Избыточно для ~50 REST endpoints. GraphQL хорош для read-heavy сложных клиентов, у нас CRUD |
| **tRPC** | Требует Node.js на бэке; у нас Python/FastAPI |
| **Protobuf + gRPC** | Overkill для внутреннего API, не нужна бинарная эффективность |
| **OpenAPI-first (писать YAML руками)** | Дмитрий пишет на TS ежедневно, YAML → дополнительный источник ошибок |

---

## Почему frontend-first

Альтернатива: **backend-first** — Филипп пишет Pydantic, генерирует OpenAPI, с него Дмитрий делает TS типы.

Мы выбираем **frontend-first** потому что:

1. **Фронт управляет UX** — какие именно поля нужны, в каком формате, с какой валидацией, знает Дмитрий из макетов
2. **Ошибки валидации приходят первыми с фронта** — Zod `.refine()` для сложных правил ближе к интерфейсу
3. **Pydantic авто-генерация проще, чем обратное направление** — `datamodel-code-generator` надёжен и не требует ручных правок
4. **Быстрее итерации** — Дмитрий правит схему в TS-проекте, один PR в contracts, бэк подхватывает

**Риск:** Филипп может упереться в ограничение (например, невозможно индексировать поле). Обязательная часть процесса — обсуждение до мерджа контракта, чтобы эти ограничения не всплывали после реализации.

---

## Версии пакетов (baseline)

| Пакет | Версия на 22.04.2026 |
|---|---|
| `zod` | `^3.22.0` |
| `@asteasolutions/zod-to-openapi` | `^7.0.0` |
| `datamodel-code-generator` | `^0.25.0` |
| Pydantic (на бэке) | `v2.x` |
| Python (на бэке) | `3.11+` |

Зафиксировать в `package.json` и `pyproject.toml` соответствующих репо.

---

## Проверка что всё работает

Для каждого PR в contracts:

1. `npm run smoke-openapi` — без ошибок
2. `datamodel-codegen --input ... --output /tmp/test_schemas` — без ошибок
3. Сгенерированные Pydantic модели импортируются в тестовом скрипте
4. (Опционально) минимальный CI: запуск обоих скриптов при PR
