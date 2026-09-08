# T3 Orders / Production: requirement tracking

Branch `codex/arch-t3-operations`; исходная база `c88a474`.
Общая очередь не активирована. Legacy writers/prototype сохранены.

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
Следующий независимый slice: отдельный fail-closed fix invalid XML text в XLSX.
После exact T1 ready commit приоритет переключается на Orders persistence.
