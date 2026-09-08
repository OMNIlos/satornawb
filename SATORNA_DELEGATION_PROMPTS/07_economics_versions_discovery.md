DONE

# Задача: discovery версионных economics settings

Ты работаешь отдельным read-only агентом в `/Users/ilagulakin/Desktop/Work/OgniWB`.

## Перед началом

Полностью прочитай `SATORNA_ARCHITECTURE_HANDOFF.md`, `SATORNA_SPEC_AUDIT.md`, architecture design, canonical costs plan и period/finance plan. Затем проверь все readers, writers, defaults, caches, tests и audit evidence для экономических настроек. GitHub и production не использовать.

## Цель

Спроектировать минимальный датированный canonical ledger для:

- `taxPct`;
- `otherExpensePricePct`;
- `otherExpensePerSaleKopecks`;
- SKU-level economics overrides.

Это discovery-задача: schema и код не реализовывать.

## Исследование

Для каждого значения установи:

- текущий источник и fallback chain;
- все mutation paths;
- organization/SKU scope;
- units и rounding;
- наличие author/effective date/audit evidence;
- влияние на P&L, ABC, repricer и cache keys;
- поведение при `0`, `null` и отсутствии настройки;
- историческую применимость.

Предложи минимальные `organization_economics_versions` и `catalog_economics_override_versions`: identity, append-only correction, idempotency, supersession, `effectiveFrom`, provenance и constraints. Определи разрешение `SKU override → organization default → missing`, `economicsRevision` и его включение в report cache identity.

Составь backfill-классификацию `configured | assumed | missing`. Текущие недатированные значения нельзя автоматически применять к прошлым операциям.

## Жёсткие границы

- Только чтение и один новый Markdown-файл.
- Не менять finance/cost code, runtime state, schema, migrations, handoff или production.
- Не придумывать effective dates.
- Не превращать missing в `0`.

## Результат

Один docs-only commit с source matrix, proposed schema, selection algorithm, cache revision contract, backfill rules, fixtures и открытыми gates.
