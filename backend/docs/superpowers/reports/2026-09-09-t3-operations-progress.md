# T3 Orders / Production: requirement tracking

Branch `codex/arch-t3-operations`; исходная база `c88a474`.
Общая очередь не активирована. Legacy writers/prototype сохранены.

## Scope override пользователя, 2026-09-09

КИЗ/Честный знак и отдельный recovered matcher исключены из продукта по прямому
указанию пользователя. Isolated matcher harness/report удалены: runtime imports
или consumers отсутствуют. PHP runtime tests не запускались. Исторические строки
ниже про КИЗ/source recovery описывают прежний scope и больше не являются gates.
Avito return matching, Catalog resolution, WB/Avito order identities, XLSX и
обычная печать не относятся к удаляемому КИЗ subsystem и сохранены.
Backend app scan не обнаружил kiz/chz/КИЗ/Честный знак runtime references.
Frontend placeholders требуют отдельной правки владельца T4; координатор уведомлён.
Backup/user data и исторические Git commits не удалялись.

| Этап / requirement | Реализованные commits / проверки | Remaining / blocker |
|---|---|---|
| 1 Discovery / parity / schema request | `4323821` Stage1; `3a30b16` offline/XLSX; `f4d6d55` returns/XLSX edge characterization | Полного production prototype/matcher нет; доступны только частичные исходники, см. recovery reports |
| 2 Identity / normalized ingestion | Existing pure orders contract; `1afd5a2` manifest/replay validation; `2f1724a` observation serialization binding | Exact installed T1 schema не передана; ORM/durable publication/CAS/revocation DB tests не выполнены |
| 3 Catalog / read API | `1afd5a2` item-scoped read models; `2f1724a` frozen payload; текущий decoder slice | Не реализованы repository resolution, permissions/cursors/API wiring; нужны schema и shared auth protocol |
| 4 Production work items / commands | `1afd5a2` pure assignment preconditions; DB09-DB13 specification | Production schema/receipts/audit отсутствуют в Orders candidate; нужны отдельный binding и T1 DDL; concurrency proof NOT_RUN |
| 5 Batches / groups / frozen sheets | Только discovery/parity requirements | Полный legacy schedule/grouping source не восстановлен; Orders read snapshot не равен Production sheet |
| 6 XLSX | Реальный renderer characterization: inline text, leading zeros, Cyrillic, quantities, 1000 rows, XML-invalid controls | Controls defect выделен в отдельное изменение; frozen sheet adapter/артефакт persistence требуют Production contract |
| 6 A4 PDF | Source gap описан | Нет полного renderer/fixtures, не реконструировать по screenshots; multipage/48+ rows NOT_RUN |
| 6 Stickers 120x75 / 58x40 | Partial matcher evidence only | Доступный fragment 58x58 не доказывает эти форматы; selected unit identity/barcode/quantity tests blocked source |
| 7 Archive / delivery / KIZ | Requirements and safety boundaries preserved | Immutable historical artifact, receipt/ambiguity и atomic allocations не реализованы; source+schema prerequisites |
| 8 Cutover / retirement | Proposed T4 wire/error handoff `f4d6d55`, no activation | Нет полной parity/reconciliation/writer fence/rollback proof; prototype не удалён; switch запрещён |

## Strict storage decoder slice

`deserialize_observation` и `deserialize_read_row` в `app/orders/serialization.py`:
exact envelope/version, exact nested fields, strict scalars/arrays, canonical UTC
timestamp encoding, reconstruction через existing validated frozen models.
Отвергает unknown version, bool/float/string version, extra/missing fields, forged
source line key/account/status mapping, invalid resolution и mismatched read item.
Нет fallback на current Catalog или provider. JSONB object input, не JSON text
parser: duplicate JSON keys должны отвергаться до JSONB, если будет внешний JSON
ingress. Этот decoder не подключён к API и не устанавливает authority SQL FK.

Формат v1 связан с существующими mapping versions. При будущем изменении mapper
нужен явный versioned decoder/mapping registry; нельзя silently remap historical
status или переименовать v1 fields. Повреждённая история требует reconciliation,
не скрытого repair. Права проверяет будущий repository на каждой странице.

TDD RED: отсутствующий `deserialize_observation`, pytest exit2. GREEN: 27 decoder
cases; combined scoped offline regression **232 passed, 2 прежних dependency
warnings**, exit0. Ruff проходит. Compileall/diff проверяются перед commit.
Self-review: проверены schema versions, nested domain validation, отсутствие
mutation входного JSON и mutable Catalog/network imports. Full backend baseline,
DB/CAS/RLS/renderer visual parity НЕ заявляются.

```sh
python -m pytest -p tests.orders_offline_plugin -q tests/test_orders_decoding.py \
  tests/test_orders_serialization.py tests/test_orders_contract.py \
  tests/test_orders_stage1_characterization.py tests/test_orders_xlsx_characterization.py \
  tests/test_orders_offline_guard.py tests/test_avito_orders.py tests/test_avito_returns.py \
  tests/test_orders_ingestion.py tests/test_orders_read_contracts.py \
  tests/test_orders_avito_adapter_characterization.py tests/test_orders_returns_characterization.py
python -m ruff check app/orders/serialization.py tests/test_orders_decoding.py
python -m compileall -q app/orders/serialization.py tests/test_orders_decoding.py
```

SQL candidate не является installed migration. Ни application DB, ни Redis,
provider, production, реальные print/export, deploy или push не использовались.
## XLSX invalid-character rule change

Отдельное явное изменение legacy behavior в `app/avito/orders_picking_xlsx.py`:
`_cell` отклоняет запрещённые XML 1.0 codepoints до создания ZIP: NUL/недопустимые
controls, surrogate range, U+FFFE/U+FFFF. Разрешённые tab/LF/CR и Unicode ranges
не очищаются и не нормализуются. ValueError содержит постоянное сообщение без
исходного текста. Это не новый renderer и не schema work.

TDD: 4 RED failures (XML parse errors/Unicode encoding error вместо predictable
rejection), затем GREEN. Старые characterization assertions повреждённого XML
заменены на acceptance безопасного отказа; исторический отчёт `f4d6d55` остаётся
доказательством предыдущего поведения. Количества/layout/headers/inline formulas
не менялись. HTTP error envelope не меняется здесь: T1 router owner должен
согласовать отображение renderer ValueError перед UI activation. Без такого
binding запрос может завершиться generic 500, но не успешным corrupt XLSX.
Rollback возможен отдельным revert этого fix; он вернёт известный corrupt-output
риск, поэтому не рекомендуется как способ продолжить печать malformed данных.
Все проверки только synthetic in-memory rendering, без physical print/export.
Combined offline regression после изменения: **234 passed, 2 прежних warnings**,
exit0. Ruff/compileall проверены для renderer и characterization file. Полный
visual XLSX/Excel layout acceptance не заявляется.

После exact T1 ready commit приоритет переключается на Orders persistence.

## Orders evidence repository / accepted dependency

Merged exact verified T1 schema `f9c7401d946063465e0576a689eb247c368eed73`
with its prerequisite lineage, no merge conflicts or manual shared-file edits.
Active0062 dependency accepted by root; не запускалась против application DB.

`app/orders/evidence_repository.py` now implements transaction-participating
order-level fact storage via parameterized SQLAlchemy Session queries. It checks
scope and current tenant context, locks run FOR UPDATE, rejects terminal/source
binding drift, creates scoped order identity, stores immutable normalized evidence
with semantic replay check, and links receipt to run membership. Same run/different
evidence is rejected. New run replay returns original persisted observation receipt.
No commit, provider, secret access, authorization helper, snapshot publication,
item projection, cancellation inference or route registration in this repository.
Caller must roll back on errors and hold fresh auth/account locks.

TDD RED missing repository import, then5 actual PostgreSQL tests PASS: rollback,
terminal/source drift, same-run changed fact/scope rejection, cross-run replay,
two simultaneous sessions/Barrier yielding one immutable fact. Fresh random
disposable DB and runtime NOSUPERUSER/NOBYPASSRLS role; reused T1 bounded fixture
with deliberately broad DML grants (tests trigger defense, not exact final ACL).
Network denied by sandbox except local Unix PG socket. Fixture verified DB/role
cleanup. No working DB table read, only maintenance metadata/create/drop own DB.
Ruff/compileall passed; DB08/revocation and full publication remain NOT_RUN.

Root fixed trusted service permission decision: user-initiated publish requires
`sync:run`; persisted reads require `cabinet:read` and live scope. These are service
constants, never request strings. Existing membership+profile union retained;
worker denied. Guard implementation is T1-owned, still awaited for service wiring.

Production schema dependency separately committed `8a8722f`:3relations with CAS,
successful receipt and immutable assignment audit; does not require renderer source.
