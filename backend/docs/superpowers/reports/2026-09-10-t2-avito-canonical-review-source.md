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

## Следующий согласованный slice: received-page publisher

Добавлены отдельные Avito definitions в `shadow_service.py`; девять прежних WB
definitions неизменны по AST. Нет HTTP caller, router registration, config,
новых grants или DDL. Pure decoder выше остаётся без изменений.

`begin_avito_review_shadow` получает original authenticated actor и paired fetch
binding, проверяет existing exact-org/account review-shadow gate и резервирует
run через existing repository. Authority — только public user-session guard с
фиксированным `reviews:write`, exact `avito_oauth_access` ID/generation/schema/
expiry. `cabinet:read` недостаточно; ticket — internal correlation data, не bearer
token, queue principal или доказательство разрешения.

```text
begin: original principal + paired binding + exact feature gate
  -> fresh root -> live guard/account lock -> reserve_run -> physical commit
  -> immutable ticket; transaction and account lock released
caller boundary: fetch is NOT implemented here
publish: same ticket/original principal, received tuple of <=50 native rows
  -> fresh root -> live guard + captured incarnation
  -> strict decoder -> existing repository/CAS -> partial manifest
  -> private incarnation fence -> shared final guard -> physical commit
  -> receipt returned only after commit
```

Coverage строго partial, даже для empty page; нет caller-supplied completeness,
inference об удалённых reviews или обещания полной pagination. Повторное содержимое
того же run проверяется existing manifest replay; другое содержимое — conflict.
После rollback публикации сохраняется ранее committed running reservation.
Автоматическое восстановление/повторная выдача authority после restart не реализованы.

### Physical commit fence: условный Core-only контракт

T1 подтвердил: shared credential guard удерживает account lock до commit, но
не сравнивает captured ingestion incarnation для ExpectedCredential. Поэтому
producer-private listener проверяет incarnation дополнительно. Он установлен
перед public acquire на private Session; shared hook не вызывается вручную,
не меняется и не переставляется. Effective dispatch обязан оканчиваться ровно
`(private fence, existing shared final)`. Pending ORM new/dirty/deleted блокируется
до SELECT; Session/callback не передаётся наружу. Shared final flush должен быть
пустым, иначе это не поддерживаемая композиция.

```text
late class listener -> incarnation changes -> private fence detects -> rollback
private fence -> unexpected listener -> shared final
  rejected by dispatch-tail check BEFORE unexpected listener executes
class listener queues ORM -> private fence rejects pending state -> no flush
other transaction changes locked account -> waits for current physical commit
```

Это узкое coupling к текущему shared hook identity/order, не generic registry.
Изменение listener topology требует повторной проверки, а не удаления fence.
Generic restricted-role fixture не доказывает готовность финального API-role:
его grants проверяет T1 отдельно. Runtime source route/fetch/activation остаются
за пределами этого commit; нельзя объявлять full Reviews cutover завершённым.

### Текущая проверка producer

RED: 8 missing page helper tests; затем 2 missing begin/publish tests при 8 PASS.
GREEN offline: **53 passed, 0.59s, exit 0** (10 producer + 43 decoder).
Ruff и compileall exact source/two new tests: exit 0. Старые WB definitions:
**9 unchanged**, AST comparison с parent. PostgreSQL suite: **17 collected,
0.80s, exit 0**; результат исполнения фиксируется отдельно после выделенного
ROOT serialized slot. Provider calls, реальные keys и production не используются.

Дополнительный bounded offline regression: producer, decoder, existing canonical
contract, review-shadow rollout и existing approval kernel — **229 passed, 0.77s,
exit 0**. Это не полный backend suite и не PostgreSQL evidence.

Первый allocated PG17: **17 setup errors, 5.33s, exit 1**, test bodies не
выполнялись. Новый synthetic fixture вызвал private resolver без tenant context;
RLS корректно скрыл account (`credential_account_not_found`). Existing production
wrapper задаёт context перед этим helper. Исправлен только fixture: exact actor
organization перед paired resolution; guards/RLS/source не ослаблены. Allocator
завершил exact owned DB/role cleanup и absence assertions без teardown errors.
Результат retry нельзя выводить из этого setup failure.

Второй PG17: **14 failed / 3 passed, 9.99s, exit 1**. Reservation блокировался
на SQL privilege boundary. Отдельный allocated diagnostic exact1: **1 failed,
3.77s, exit 1**, только `received-review-source SQLSTATE=42501`, без SQL/params/
raw exception. T1 подтвердил недостающие fixture-only EXECUTE для существующих
0068 PURE2: `review_binding_ascii_string(text)` и
`review_run_binding_bytes(integer,integer,text,text,text)`. Они выдаются только
owned disposable role; никаких trigger/all-functions/операционных grants.
Причина: migration выбирает уже имеющих права writers, reusable Stats fixture
выдаёт table rights позже. Обе попытки завершили explicit owned cleanup/absence.

Отдельно PG обнаружил реальный error-boundary дефект: raise внутри генераторного
context manager сохраняет exception context через `contextlib.throw`, даже после
внутреннего except. Pure regression: **1 failed / 10 passed, 0.52s**. Теперь
collector сохраняет только safe code; ordinary begin/publish frame поднимает
новую ошибку после выхода из `with`. GREEN: **11 passed, 0.48s, exit 0**.
Это не изменение shared guard и не подавление DB ошибки успешным fallback.

Следующий frozen PG17 после PURE2/error-boundary: **13 failed / 4 passed, 4.62s,
exit 1**, SQLSTATE42501 всё ещё на reservation. Cleanup/absence подтверждены.
Нельзя считать begin commit-failure test причинным доказательством: до callback
могла сработать ранняя ACL ошибка. Повтор PG17 приостановлен до полного exact
fixture dependency assessment Т1; broad grants и superuser fallback запрещены.

Catalog-only diagnostic exact1: **1 failed, 4.70s, exit 1**. EXECUTE false только
для двух 0065 helpers, true для двух 0068 helpers; run SELECT/INSERT и account
SELECT/UPDATE true. T1 подтвердил полный source dependency set PURE4. Fixture
дополнен только недостающими 0065 EXECUTE, без grants на trigger functions или
изменения operational ACL. В тех же PG17 отрицательные commit/class tests теперь
обязаны доказать вызов нужного callback, чтобы ранняя unrelated ошибка не дала
ложный PASS. Ещё один PG17 — только по отдельному ROOT slot.

PG17 с PURE4: **16 passed / 1 failed, 5.95s, exit 1**, все catalog privileges
true, happy reserve→publish→replay→existing local context прошёл. Remaining
incarnation fixture вручную менял защищённый version; 0076 trigger правильно
отверг UPDATE. Late class test также не доказывал private fence, если его UPDATE
раньше отверг trigger. Исправлены только stimuli: legitimate external binding
roundtrip с возвратом descriptor, assert version=captured+2, callback completion
и точный AUTHORITY_CHANGED outcome. Нет прямой записи version/отключения trigger.

### Финальный gate и handoff

**PG17: 17 passed, 3.86s, exit 0.** Legitimate incarnation roundtrip действительно
завершается (+2), затем private fence возвращает AUTHORITY_CHANGED; в базе нет
facts/observations. Intervening callback не выполняется; pending ORM и actual
physical commit failure откатываются. Committed reservation, exact-text publish,
same-run replay и existing Avito local context проверены реальным PostgreSQL.
Owned database `orders_test_f7900d6d577243839100e36cb9f97e1d` и role
`orders_exact_08a34eee92264272bbcdcb9500a1e456` удалены; allocator явно проверил
их отсутствие. PG slot освобождён ROOT.

Последний bounded offline набор: **230 passed, 0.65s, exit 0**. Полный backend
suite не запускался. PG test counts не включают прежние setup failures как PASS.

Команды из backend worktree (все pytest запускались через `env -i` и existing
offline sandbox, с закрытыми NETRC/PGPASSFILE/PGSERVICEFILE):

```text
/tmp/satorna-backend311-20260909/bin/python -m pytest -q --tb=short tests/test_review_avito_shadow.py tests/test_review_canonical_avito_decode.py tests/test_review_canonical_contract.py tests/test_review_shadow_rollout.py tests/test_wb_repricing_approval_domain.py
ORDERS_TEST_USE_LOCAL_CLUSTER=1 ...python -m pytest -q -rP --tb=short tests/test_review_avito_shadow_postgres.py
/tmp/satorna-backend-verify-20260908/bin/python -m ruff check app/reviews/shadow_service.py tests/test_review_avito_shadow.py tests/test_review_avito_shadow_postgres.py
PYTHONPYCACHEPREFIX=/tmp/satorna-t2-account-discovery-pycache ...python -m compileall -q app/reviews/shadow_service.py tests/test_review_avito_shadow.py tests/test_review_avito_shadow_postgres.py
git diff --check
```

Внутренний отдельный critic pass: error context исправлен с causal regression;
ACL failure не принят за commit-failure proof; прямой version UPDATE не принят за
incarnation-fence proof; shared/WB definitions не изменены; роли fixture не
выдаются за final API-role. Указанный `preflight-critic/SKILL.md` локально отсутствует,
поэтому независимый внешний reviewer этим отчётом не заявляется.

Scope: additive Avito producer в одном existing module, два новых test files и
этот report. Не менялись schema/migrations/config/ops/flags/routers/tasks/legacy
WB flow. Нет decrypt/provider calls, новых credentials, network или production
mutations. Следующий разрешённый интеграционный slice требует ROOT/T1 wiring и
проверки реальных ограниченных role grants. Source answer body/list projection,
bounded fetch orchestration, crash recovery и activation этим commit не закрыты.
