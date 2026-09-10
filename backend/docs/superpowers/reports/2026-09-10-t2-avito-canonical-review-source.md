# T2: существующая canonical Avito Review source boundary

## Доказанные компоненты, без нового metadata endpoint

| Existing path | Поддержка / граница |
|---|---|
| `canonical_contract.normalize_avito_review` | org/account/provider/exact external identity; точный text/null/empty; rating, answered, can_answer, source_status, created/updated, source/run/normalization versions |
| `review_fact_checksum` | Существующий hash включает scope и semantic fields; не включает observed_at/run id. Не менять алгоритм или source schema ради совпадения |
| `canonical_orm.CanonicalReviewObservationRow` | exact text + UTF-8 pair, rating/status/time/answered, immutable revisions; answer body/id/status не хранятся |
| `ReviewFactsRepository(ReviewOwner(...,'avito',...))` | generic org/account/provider-bound get/reserve/ingest, CAS version, revision, source-order conflict и historical binding fences |
| `local_service.read_local_review_context` | Уже поддерживает Avito. `reviews:read`, exact account context, shared guard до physical commit, без provider credentials |
| `local_http /api/v2/reviews/local/context` | Для известного факта требует одновременно internal review UUID и external_review_id; возвращает exact text/observation/checksum/answered/canAnswer |
| `local_repository.source` | Проверяет UUID↔external id и исторический account binding; ambiguous source отвергается, не становится current |
| `canonical_read /api/v2/reviews/wb/fact` | Только WB; не нужно копировать этот endpoint ради уже существующего Avito local context |
| `shadow_service`, `canonical_sync` | Действующий guarded producer WB-only: wb_api credential, WB DTO types, normalize_wb_review; Avito нельзя подставить через cast |
| `review_job_authority` | Send/attempt authority для WB+Avito, не permission публиковать source observations |

Ответ продавца намеренно не является canonical source body: существующий тест
`test_review_canonical_contract.py::test_received_wb_and_avito_dto_shapes_normalize_without_adapter_calls`
проверяет отсутствие `answer` в fact. Поэтому изменение только answer.text/id/status
при неизменном answered не меняет canonical content checksum. Нельзя выдавать это
за полную версию provider response или хранить source answer в local AI draft.

## Конкретный missing decoder

Raw Avito fixture в `tests/test_avito_reviews.py` содержит native `createdAt` как
Unix seconds и `item.id` вложенно. Canonical normalizer ожидает aware datetime/ISO
и flattened itemId. Legacy `LiveAvitoReviewsClient._review_row` выполняет bridge,
но одновременно подменяет missing text → empty, missing score → 5, clamps score,
coerces bool и time. Он не подходит для canonical facts без strict raw admission.

Минимальная pure граница: `canonical_avito_decode.decode_avito_review(raw, *,
organization_id, marketplace_account_id, source_run_id, observed_at)` возвращает
существующий `NormalizedReviewFact` через существующий normalizer, а не новый
repository или новую source-authority сущность. Native time → aware UTC; nested
item.id → itemId; text сохраняется побайтно в существующей semantic UTF-8 модели.
Никаких network/clock/repository/global state/serialization side effects.

Обязательные ограничения нового raw decoder:

- native IDs принимаются без bool/float/coercion; opaque strings/leading zeros
  сохраняются по existing identity contract, не считаются internal IDs;
- invalid rating/text/canAnswer не исправляются; missing nullable поля остаются null;
- `answer: null` — доказанное answered=false, объект с проверенным id — true;
  отсутствующее поле answer не доказывает отсутствие ответа и блокирует raw admission;
- existing normalized fixtures и normalizer defaults не изменяются;
- неподтверждённые owner/update aliases блокируются; источник updated time не
  синтезируется из observed_at/createdAt/порядка fetch;
- caller org/account/run/observed_at проходят existing contract validation, но
  сами по себе **не являются authenticated authority**;
- answer body, buyer name, title, images не проходят в canonical fact; это явная
  неполнота модели, а не потеря незаметно обещанных полей.

## Минимальное будущее подключение

```text
authenticated original actor + exact encrypted Avito account
  -> explicit reviews:write source owner/guard (ещё не подключён)
  -> durable reserve_run before fetch, exact paired binding
  -> bounded raw source fetch, outside transaction
  -> pure decoder -> existing normalize_avito_review
  -> same captured authority revalidation + generic repository ingest/CAS
  -> partial immutable observations/run receipt
  -> existing /reviews/local/context with reviews:read and both IDs
```

Это reuse plan, не реализованная публикация. Текущая работа не расширяет WB
ticket, не создаёт fake worker principal, не использует cabinet:read/preview как
publish permission и не выдаёт request metadata за guard.

Для полноценного list/table потребуется bounded projection существующих
review_observations.rating/source_status и scoped discovery internal UUID —
`ReviewFactSnapshot`/local context сейчас этих display fields не возвращают.
Для exact source answer body/version существующей колонки/semantic hash нет:
нужен отдельный ownership/schema slice T1+Reviews owner, не guessed JSON reuse.
Plain-text безопасный rendering/стандартная account isolation входят в уже
утверждённый продукт, отдельное бизнес-согласование на них не требуется.

Source updated time неизвестен: остаётся null. Repository использует свой
run_sequence и уже существующие known-time/history fences; receipt sequence не
называется provider freshness и не разрешает send по stale/ambiguous evidence.

## Проверки и ограничения текущего slice

Existing canonical contract: **38 passed, 0.20s, exit 0**, offline Python3.11.
Новый raw decoder реализован после explicit ROOT approval ровно в одном pure
module, с отдельным test file. RED `ModuleNotFoundError` до создания module;
GREEN **81 passed, 0.24s, exit 0** (43 new + 38 existing canonical contract).
Literal raw/native mapping сопоставлен с независимо составленной existing
normalized формой и тем же semantic checksum. Проверены null/empty/whitespace,
Unicode/NUL + existing UTF-8 codec roundtrip, source/run hash distinctions,
exact IDs, missing answer blockade, malformed native input, safe exception context.
Изменение только source answer text намеренно оставляет existing checksum тем же:
тест доказывает limitation, не новую answer revision guarantee.

Decoder принимает только dict/raw native shape, internal positive int4 owner data,
positive integer Unix seconds <=253402300799; conflicting normalized identity,
source-version и update aliases отклоняются. Это raw adapter admission, не
изменение existing canonical normalizer или historical keys/checksums.

Ruff/compile/diff проверяются перед commit. Первичный Ruff нашёл deliberate naive
datetime в negative test; тот же naive input построен через `replace(tzinfo=None)`,
защитная проверка не ослаблена. Внутренний critic pass: authority не создаётся,
new context endpoint не нужен, source answer не подменяется AI draft, missing
source time не восстанавливается из runtime clock. PostgreSQL/provider jobs не
запускались; schema/guards/local workflow/legacy/flags не менялись.
