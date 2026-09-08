# Satorna economics versions discovery — 2026-09-04

## Итог

Запрошенный в discovery датированный canonical ledger уже реализован и, согласно
локальному handoff, развёрнут с миграцией `0055`. Создавать третью модель,
универсальный settings framework или новый cache layer не нужно. Текущие
`organization_economics_versions` и `catalog_economics_override_versions`
покрывают минимальную форму: tenant ownership, integer basis points/kopecks,
effective time, provenance, idempotent source identity, supersession, partial SKU
override, явные `configured | assumed | missing` и forced RLS
(`app/platform/economics/orm.py:99-270`,
`app/platform/economics/policies.py:350-533`,
`alembic/versions/20260902_0055_dated_economics.py:19-194`).

Но локальная реализация пока не полностью доказывает заявленный контракт:

1. append-only соблюдается сервисом, но runtime role всё ещё имеет
   `UPDATE, DELETE` на обе ledger-таблицы;
2. FK коррекции SKU tenant-safe, но не гарантирует на уровне БД тот же SKU;
3. legacy SKU bridge превращает одно изменённое поле в полный override и не
   сохраняет автора;
4. canonical ABC/P&L читает ledger, а repricer и legacy reports продолжают читать
   несовместимые JSON/default chains;
5. бизнес-контракт налоговой базы в product docs расходится с фактической
   canonical формулой;
6. в репозитории нет воспроизводимого policy-backfill command/raw manifest, а два
   локальных документа расходятся по cardinality исходных SKU observations.

Следовательно, минимальная следующая работа — закрыть перечисленные gates вокруг
существующей модели, а не реализовывать ещё одну схему. До этого canonical
ABC/P&L правильно оставляет недоказанные значения `null`; `missing` нигде нельзя
подменять нулём.

## Граница и доказательная база

Аудит выполнен на backend commit
`d72d0f58b51a1258ba018ed75a3ca4027984b5e8` в отдельном worktree. GitHub,
production, сетевые источники и runtime writes не использовались. Production
утверждения ниже — только уже сохранённое локальное evidence; этот discovery их
повторно не проверял.

Полностью прочитаны:

- `/Users/ilagulakin/Desktop/Work/OgniWB/SATORNA_ARCHITECTURE_HANDOFF.md`;
- `/Users/ilagulakin/Desktop/Work/OgniWB/SATORNA_SPEC_AUDIT.md`;
- architecture design
  `/Users/ilagulakin/Desktop/Work/OgniWB/.worktrees/frontend-wb-abc-production/docs/superpowers/specs/2026-08-26-satorna-platform-rebuild-architecture-design.md`;
- canonical costs plan
  `/Users/ilagulakin/Desktop/Work/OgniWB/.worktrees/frontend-wb-abc-production/docs/superpowers/plans/2026-08-28-satorna-slice-1-canonical-costs.md`;
- `docs/superpowers/plans/2026-09-01-satorna-period-finance-slice.md`;
- `docs/superpowers/plans/2026-09-02-satorna-dated-economics.md`;
- `docs/superpowers/reports/2026-09-03-satorna-abc-pnl-inventory-1c9dd5a.md`;
- применимые `AGENTS.md`, README и delegation prompt.

Локальный поиск всех camelCase и canonical snake_case полей охватил `app/`,
`alembic/`, `ops/` и `tests/`. CamelCase readers/writers находятся в
`repricer_bff.py`, `repricer_execution.py`, `repricer_nomenclature_excel.py`,
`wb_reports_sprint_d.py`, repricer/report routers и canonical bridge; snake_case
поля — в economics ORM/service, canonical ABC/P&L, migration и их тестах. Отдельный
economics backfill отсутствует: `app/platform/economics/backfill.py` импортирует
только `CostsService`, а локальный поиск policy writer calls нашёл лишь legacy
router, tests и сами service methods.

Локальный tracked `var/vella_repricer_runtime_state.json` — не production
evidence. В audited commit он содержит org `1` с algorithm `6 / 5 / 0`, 12 SKU
settings rows и одним economics-bearing row; org `7` — `6 / 5 / 0` и без SKU
overrides. Organization `2` в этом файле отсутствует, поэтому из него нельзя
восстановить задокументированный production backfill.

## Запрошенный target и фактическая реализация

| Требование discovery | Фактический статус на `d72d0f5` | Вывод |
|---|---|---|
| Датированные org defaults | Реализованы в `0055`; полный triple либо явный missing (`orm.py:99-183`) | Не создавать новую таблицу |
| Датированные SKU overrides | Реализованы; каждое поле nullable, включая all-null clear (`orm.py:186-270`) | Сохранить sparse override semantics |
| `SKU override → org → missing` | Реализовано field-by-field (`policies.py:699-759`) | Это canonical selection |
| Idempotency | Unique `(organization_id, source, source_reference)`; identical replay возвращает прежнюю row, отличный command конфликтует (`policies.py:389-413`, `:480-506`) | Достаточно; новый idempotency framework не нужен |
| Append-only correction | Service только вставляет новую row и может ссылаться на superseded row (`policies.py:414-441`, `:507-533`) | Нужна DB/runtime-role гарантия |
| Tenant isolation | Composite ownership и forced RLS (`orm.py:113-125`, `:200-217`; migration `:188-194`) | Реализовано, кроме exact SKU supersession constraint |
| Dated P&L | Moscow day-end lookup, signed revenue, gross sales units, half-even (`abc_pnl.py:120-136`, `:239-322`) | Реализовано |
| `economicsRevision` | Tenant count обеих ledger-таблиц (`policies.py:761-778`) и response metadata (`wb_reports_v2.py:122-147`) | Пригодно только при настоящем append-only |
| Canonical response cache | Отсутствует; route авторизует и считает из DB (`wb_reports_v2.py:169-211`) | Не добавлять, пока SLO проходит |
| Backfill classification | State/evidence поддерживаются; documented production snapshots записаны как assumed | Воспроизводимый локальный manifest/command отсутствует |

Handoff фиксирует `2` org versions + `3,052` override versions = revision `3,054`,
missing coverage и отсутствие application cache
(`/Users/ilagulakin/Desktop/Work/OgniWB/SATORNA_ARCHITECTURE_HANDOFF.md:75-83`,
`:113-120`). Это completion evidence существующего slice, а не proposal этого
discovery.

## Source matrix

### Общая цепочка

Canonical и legacy сейчас имеют разные authorities:

```text
canonical ABC/P&L:
organization_economics_versions
  + sparse catalog_economics_override_versions
  → point-in-time policy → canonical ABC/P&L

repricer и legacy reports:
wb_repricer_algorithm_settings DB
  → fallback JSON file → fallback process memory → code defaults
wb_repricer_runtime_state DB
  → fallback JSON file → fallback process memory
  → type/template/demo/SKU overlays → repricer / Sprint D / generic reports
```

DB-first, file-second, memory-last loading находится в
`app/repricer_persistence/store.py:128-161`. Hydration начинает с code defaults,
затем накладывает stored algorithm settings и при unrelated night-median bootstrap
может сохранить весь получившийся default object (`store.py:402-443`). JSON не
является canonical source по architecture invariant
(`...architecture-design.md:128-135`).

### Значения

| Поле | Legacy org/default и SKU chain | Canonical source и units | `0`, `null`, absence | Историчность/provenance | Влияние |
|---|---|---|---|---|---|
| `taxPct` | Algorithm DB/file/memory, затем code default `6`; runtime SKU row существует, но repricer после SKU overlay снова ставит org tax (`repricer_bff.py:4228-4325`). Sprint D, напротив, накладывает SKU tax (`wb_reports_sprint_d.py:740-756`) | Org/SKU `tax_basis_points`, integer `0..10000`; legacy percent умножается на 100 и half-even (`policies.py:139-175`) | Canonical configured `0` валиден; missing triple даёт `null`. Legacy reports превращают absent/invalid в `0` (`wb_reports_sprint_d.py:237-256`) | Legacy не имеет field history/author; canonical имеет effective/source/ref/optional membership/createdAt | Canonical: signed seller revenue × bps. Repricer: price floors/ceilings, draft economics; legacy P&L/ABC: seller revenue × percent |
| `otherExpensePricePct` | Algorithm DB/file/memory, code default `5`, template/demo/SKU overlay. Repricer заменяет любое resolved `<=0` на code default `5`; Sprint D сохраняет SKU/org zero (`repricer_bff.py:4251-4257`, `:4327-4335`; `wb_reports_sprint_d.py:740-756`) | Org/SKU `other_expense_price_basis_points`, integer `0..10000`; legacy percent → bps half-even | Canonical configured `0` валиден. В repricer явный zero неотличим от fallback и становится `5`; в Sprint D absence становится `0` | Та же canonical provenance; legacy snapshot timestamp не доказывает дату business change | Canonical: signed seller revenue × bps. Repricer: `max(promoCostPercent, otherExpensePricePct)` входит в variable denominator (`repricer_execution.py:132-188`, `:400-403`) |
| `otherExpensePerSaleKopecks` | Org хранится как `otherExpensePerSaleRub`, default `0`; SKU — kopecks. Runtime SKU overlay идёт после derived org value (`repricer_bff.py:4243-4269`, `:4319-4339`) | Org/SKU `other_expense_per_sale_kopecks`, integer `>=0`; legacy rubles × 100 half-even, либо direct kopecks half-even (`policies.py:153-175`) | Canonical configured `0` валиден, missing — `null`. Repricer/Sprint D coerce absence/invalid to `0` | Legacy file `updatedAt` относится ко всему save, не к полю; canonical row provenance явная | Canonical: kopecks × gross positive sales units. Repricer: fixed cost в Pmin/Pmax и logistics-like draft input; legacy P&L: per-sale × sales units |

`DEFAULT_ALGORITHM_SETTINGS` явно задаёт `6 / 5 / 0`
(`app/repricer_bff.py:741-758`). Это runtime compatibility defaults, не
историческая истина и не основание создавать configured ledger rows.

### Scope, author и audit evidence

| Source | Scope | Date/author evidence | Canonical пригодность |
|---|---|---|---|
| Org algorithm row | Organization | `updated_at` имеет только server default без `onupdate`; field-specific author/event отсутствует (`repricer_persistence/orm.py:11-20`) | Текущий snapshot максимум `assumed` с реальным observation/import anchor |
| Runtime SKU JSON | Organization + string article | Runtime row timestamp обновляется для всего blob; значения обычно являются полным resolved object, а не sparse field intent (`repricer_persistence/orm.py:22-35`, `store.py:446-492`) | Только поля с доказанным override intent; иначе assumed diff/needs_review |
| Fallback file | Organization | `updatedAt` меняется при любом file save (`store.py:87-106`) | Не является effective date конкретного economics field |
| Process globals/defaults/templates | Process; org hydration временно подменяет globals | Нет durable author/effective event | Никогда configured; не backdate |
| Canonical row | Organization, optional catalog SKU | `effective_from`, source/reference, evidence, optional membership, createdAt | Authority для canonical ABC/P&L |

`SKU_AUDIT_EVENTS` создаются в памяти при UI/XLSX writes
(`repricer_bff.py:5326-5357`, `routers/wb_repricer_bff.py:4315-4332`), но
`flush_repricer_bff_state` не включает их в persisted payload
(`repricer_persistence/store.py:446-492`). Текущие dual-write routes также не
передают `created_by_membership_id`, поэтому canonical author остаётся `null`,
хотя column и tenant-safe FK существуют.

## Mutation matrix

| Mutation path | Что пишет | Canonical reconciliation | Риск/gap |
|---|---|---|---|
| `PUT /api/v1/wb-repricer/algorithm` | Полный legacy algorithm object → memory/file/DB | Только если payload содержит одно из трёх economics fields; после legacy save, полный triple, source ref от `savedAt` (`routers/wb_repricer_bff.py:7193-7217`) | Неатомарный dual-write; author не передаётся |
| `PUT /api/v1/wb-repricer/sku/{article}/settings` | Patch накладывается на полный resolved SKU object и весь object сохраняется (`repricer_bff.py:5326-5357`) | Только economics-bearing patch; после legacy save reconciles **полный** returned triple (`routers/wb_repricer_bff.py:5785-5821`) | Одно поле замораживает два inherited поля как SKU override; author не передаётся |
| `POST /api/v1/wb-repricer/sku/import-xlsx` | TaxRate → `taxPct`; PickPack amount → kopecks; PromoCostPercent также → `otherExpensePricePct` (`repricer_nomenclature_excel.py:68-104`, `:425-439`) | После общего legacy flush цикл отдельных SKU commits с source ref `fileHash + article + importedAt` (`routers/wb_repricer_bff.py:4254-4318`, `:4387-4422`) | Не одна transaction; поздний unmapped `409` возможен после частичного legacy/canonical write; известный actor не передаётся |
| Template PUT/apply | Произвольный dict накладывается на SKU settings (`repricer_bff.py:5433-5470`) | Нет | Economics keys могут обойти canonical bridge; state process-local до последующего flush |
| Costs-Excel hydration | При отсутствии SKU row материализует полный `_sku_cost_settings` object в `SKU_SETTINGS_OVERRIDES` (`routers/wb_repricer_bff.py:381-425`) | Нет | Последующий unrelated flush может сохранить derived economics как будто SKU settings |
| Direct `EconomicsService` | Только canonical insert/replay | Да, это canonical writer | Публичного typed v2 mutation contract нет; допустимо, пока нет подтверждённого consumer |
| Direct SQL runtime role | Любую таблицу | Обходит service | Role имеет `UPDATE, DELETE`; append-only не доказан (`ops/runtime-db-role.sql:50-61`) |

Legacy-first reconciliation позволяет retry добавить отсутствующую canonical row,
если первый canonical commit упал, и unchanged values не создают дубликат
(`policies.py:188-303`; tests `test_economics_policies.py:258-320`). Но retry
формирует новый wall-clock reference/effective timestamp, поэтому первоначальный
event time не гарантирован. `EconomicsConflictError` отдельно route не переводит
в устойчивый API conflict. Эти свойства надо закрыть writer fixtures до
утверждения bridge как lossless.

## Readers и формулы

### Canonical ABC/P&L

Это единственный application reader `get_policies_for_points`; локальный поиск не
нашёл других production call sites. Flow:

1. route проверяет `finance:read` и account scope до service call
   (`app/routers/wb_reports_v2.py:169-205`);
2. finance даёт immutable daily signed seller revenue и gross positive sales
   units (`app/platform/finance/service.py:895-946`, `:1165-1177`);
3. `nmId` разрешается ровно в один tenant-owned `CatalogSku`; missing/ambiguous
   mapping не угадывается (`abc_pnl.py:542-572`);
4. policy выбирается на последнюю микросекунду каждого Moscow business day
   (`abc_pnl.py:120-123`, `:546-571`);
5. дни группируются по неизменному numeric policy triple; tax и percent overhead
   округляются signed half-even один раз на bucket, per-sale overhead умножается
   на gross sales units (`abc_pnl.py:274-303`);
6. missing policy/mapping/daily reconciliation возвращает `null` + blocker, а
   assumed/non-dated остаётся вычислимым, но явным (`abc_pnl.py:248-322`).

Пустой daily set возвращает `0 / 0` только после reconciliation с нулевым period
fact (`abc_pnl.py:248-260`); это не подмена missing. Formula version на audited
HEAD уже `wb-abc-pnl-advertising-v1`, то есть позднее расширение ранее
задокументированной `wb-abc-pnl-economics-v1`
(`abc_pnl.py:24`, handoff `:85-91`).

### Repricer и legacy reports

Repricer canonical ledger не читает. Он использует legacy resolved settings:

- tax, other percent и per-sale входят в Pmin/Pmax (`repricer_execution.py:132-188`);
- draft tax считается от current price, а per-sale добавляется к logistics
  (`repricer_execution.py:279-297`);
- row/period analytics также вычитают tax и overhead
  (`repricer_bff.py:4696`, `:4788-4791`, `:4937-4940`).

Sprint D строит собственный settings resolution и P&L
(`app/wb_reports_sprint_d.py:740-756`, `:950-976`). Поэтому изменение canonical
ledger само по себе не изменит цену repricer, а одинаковый legacy input может
дать разные результаты: repricer игнорирует SKU tax и заменяет explicit zero
other-percent на `5`, Sprint D эти значения принимает. Это важный consumer-cutover
gate, а не причина расширять ledger.

## Минимальная schema contract

Ниже не новая миграция, а минимальная форма, которой должна соответствовать уже
существующая `0055` модель.

### `organization_economics_versions`

| Группа | Минимальные поля/правило | Сейчас |
|---|---|---|
| Identity/owner | opaque monotonic PK; `organization_id` FK | Есть |
| Values | `tax_basis_points int`, `other_expense_price_basis_points int`, `other_expense_per_sale_kopecks bigint`, nullable | Есть |
| State | configured/assumed требуют полный triple; missing требует все три `null` | Есть DB CHECK |
| Time | aware `effective_from`; `created_at` только tie-break/audit, не business-effective date | Есть |
| Provenance | non-empty `source`, immutable `source_reference`, evidence status, optional tenant membership author | Есть; writers не заполняют author |
| Idempotency | unique `(organization_id, source, source_reference)` | Есть |
| Correction | nullable same-tenant `supersedes_organization_economics_version_id`; correction — новая row/ref | Есть |
| Isolation | forced RLS + tenant context | Есть |
| Immutability | runtime может `SELECT, INSERT`, но не `UPDATE, DELETE` | **Нет на уровне privileges** |

### `catalog_economics_override_versions`

Те же identity/time/provenance/idempotency правила плюс non-null
`catalog_sku_id` с composite `(organization_id, catalog_sku_id)` FK. Каждое value
nullable: non-null поле перекрывает org, null наследует org; all-null row — явный
clear, возвращающий все поля к org. `value_state` здесь только configured/assumed;
resolved missing вычисляет reader.

Минимальная обязательная schema delta — exact-scope supersession FK. Сейчас FK
содержит только `(organization_id, superseded_version_id)`
(`app/platform/economics/orm.py:210-217`), поэтому direct SQL может связать
correction SKU A с row SKU B. Целевой invariant требует unique candidate
`(organization_id, catalog_sku_id, version_id)` и FK по тем же трём полям.
Service уже проверяет тот же SKU (`policies.py:507-518`), но DB должна сохранять
инвариант для любого writer.

Дополнительные tables, event bus, generic bitemporal model и отдельный revision
counter сейчас не нужны. При запрете UPDATE/DELETE insert graph не может образовать
цикл назад в будущую row; отдельный cycle framework избыточен. Если продукту нужен
строго один successor, это отдельное решение о correction concurrency, а не
условие point-in-time resolution.

## Selection algorithm

```text
resolve(org, account, nmId, businessDate):
  sku = exact tenant/account catalog mapping(nmId)
  if sku is absent or ambiguous: return missing(null, blocker)

  instant = end_of_business_day(businessDate, Europe/Moscow) in UTC
  orgRow = latest org row where effective_from <= instant
           ordered by (effective_from, created_at, id)
  skuRow = latest row for exact (org, sku) where effective_from <= instant
           ordered by (effective_from, created_at, id)

  for field in [taxBps, otherExpensePriceBps, otherExpensePerSaleKopecks]:
    value[field] = skuRow[field] if skuRow[field] is not null
                   else orgRow[field] if orgRow exists
                   else null

  if any value is null: state = missing
  else if any contributing row is assumed: state = assumed
  else: state = configured

  evidence = worst(contributors): period_end_fallback > undated > dated
  effectiveFrom = max(effective_from of rows that actually contributed)
  return values + state + evidence + contributing version ids
```

Это описание фактического кода (`policies.py:592-759`), а не speculative
algorithm. Supersession link — provenance correction; selection определяется
детерминированным ordering. Future row не влияет на past point. Никакая текущая
undated setting row не должна получить fabricated past `effective_from`.

## `economicsRevision` и cache contract

### Фактическое состояние

`EconomicsService.revision()` возвращает tenant-scoped
`count(org rows) + count(SKU rows)` (`policies.py:761-778`). При insert-only это
монотонный invalidation token. Он намеренно over-invalidates: future-dated или
не относящаяся к period SKU row тоже меняет revision. Это безопаснее stale hit и
пока дешевле отдельного scoped revision index.

Однако count не видит in-place UPDATE, а DELETE может уменьшить token. Поэтому
revision корректен только после DB-enforced append-only. Его нельзя называть
content hash или использовать как доказательство конкретного набора values.

Canonical v2 сейчас не имеет response cache: route каждый раз читает local DB,
а `economicsRevision` возвращает как metadata. Локальный handoff фиксирует p95
ниже `500 ms` без application cache (`SATORNA_ARCHITECTURE_HANDOFF.md:115-120`).
Это минимальный текущий вариант; cache добавляется только после измеренного SLO
нарушения.

Legacy caches не подходят для canonical reuse:

- generic ABC `v16` hash включает legacy algorithm/SKU/COGS/rules, но не
  canonical economics/source revisions
  (`routers/wb_reports_bff.py:3362-3416`, `:3511-3533`);
- generic P&L key содержит только report/date/group/source, а DB storage лишь
  отдельно tenant-scoped (`routers/wb_reports_bff.py:3405-3421`);
- direct Sprint D key `v3|dates|group|requestedState|finance flag` не содержит
  source/cost/economics/rules revision; fresh и stale TTL оба 24h
  (`wb_reports_sprint_d.py:50-54`, `:559-654`).

### Минимальная identity, если cache станет нужен

```text
cacheVersion
+ organizationId
+ marketplaceAccountId/accountScope
+ dateFrom/dateTo + business timezone
+ formulaVersion
+ rulesVersion
+ finance syncRunId/snapshotChecksum
+ advertising sourceRevision/snapshotChecksum
+ costLedgerRevision
+ economicsRevision
+ filters + sort + selectedColumns
+ cursor/limit/offset
+ visibilityProfile, только если payload различается между разрешёнными ролями
```

Authorization и account-scope check выполняются до cache lookup. Revision mismatch
означает miss; wildcard deletion не является механизмом correctness. Summary и
page используют одну identity/snapshot. Неуказанные query dimensions не надо
изобретать заранее: добавлять их в key только вместе с реальным consumer. Это
соответствует architecture cache identity
(`...architecture-design.md:347-370`).

## Backfill: `configured | assumed | missing`

### Правила

1. `configured` — только явный user command или датированный import/source row,
   для которого доказаны scope, values, event/effective time и actor/source
   identity. Подтверждённый zero остаётся zero.
2. `assumed` — code/type/template default, undated current JSON, immutable
   observation без доказанной даты начала действия или иной compatibility value.
   Dated observation можно применять **не раньше observation timestamp**; это не
   утверждение, что значение действовало до observation.
3. `missing` — нет полного безопасного resolved triple либо mapping/evidence
   недостаточны. Результат — `null`/needs_review; не synthetic zero.
4. Отсутствие SKU override означает fallback к org, а не missing. All-null SKU row
   — датированный clear к org.
5. Полный legacy SKU object не доказывает, что все три поля были намеренными SKU
   overrides. При paired org/SKU observation переносить sparse assumed fields,
   которые отличаются от observed org policy; равные/inherited поля не
   замораживать. Без org observation — `needs_review`, не догадка.
6. Identical `(org, source, sourceReference)` replay — no-op; другой payload с тем
   же identity — conflict. Correction получает новый immutable reference и
   `supersedes`.
7. Backfill пишет batch manifest: source checksum, observation timestamp, mapping
   result, counts по configured/assumed/missing/needs_review, inserted/reused/
   conflicted и version/revision before/after. Ledger rows не обновляются.

### Классификация источников

| Legacy evidence | Classification | Safe `effective_from` | Действие |
|---|---|---|---|
| Explicit user economics event с durable timestamp/identity | configured | Доказанный event/effective time | Org или sparse SKU row; actor membership обязателен для user source |
| Датированная immutable settings snapshot | assumed, evidence `dated` | Сам observation timestamp, не более ранняя дата | Snapshot source/ref/checksum; no backdating |
| Текущий DB/file JSON без field event | assumed, evidence `undated` | Реальный discovery/import observation time | Только forward compatibility; historical days до anchor missing |
| Code default `6 / 5 / 0`, type/template/demo derived value | assumed | Реальный cutover/observation time, если вообще materialized | Не configured и не retroactive |
| Field отсутствует/invalid, mapping ambiguous, source недоступен | missing | Нет | Не писать numeric value; manifest needs_review/rejected |

Architecture уже требует `null != 0`, exact source reference и запрет применять
current undated values назад
(`...architecture-design.md:582-593`).

### Что локально доказано о выполненном backfill

Два immutable observations задокументированы на
`2026-08-19T12:37:54Z` и `2026-08-28T11:17:46Z`; более ранняя история не
заявлена (`docs/superpowers/plans/2026-09-02-satorna-dated-economics.md:18-23`).
Completion evidence сообщает org `2`: `2/3052`, revision `3054`, а preamble того
же плана говорит о `3,054` economics-bearing SKU overrides в каждом snapshot
(`:18-22` против `:125-133`). Без raw immutable snapshots/manifest локально
нельзя установить, опечатка ли это, mapping exclusions или иной grain.

Нельзя повторять backfill только по этим prose counts. Gate закрывается
репозиторным sanitized manifest/checksums и воспроизводимым dry-run/replay
command, не production access из discovery.

## Fixtures и acceptance evidence

| Fixture/gate | Ожидаемый результат | Текущее покрытие |
|---|---|---|
| Полный configured org policy с `0 / 0 / 0` | Три numeric zero, state configured; не missing | Нужен отдельный explicit fixture |
| Нет org row и override | Все economics outputs `null`, blocker missing | Есть: `tests/test_economics_policies.py:100-136`, `test_abc_pnl_service.py:591-613` |
| Sparse SKU tax + org fallback | SKU tax, два org fields | Есть: `test_economics_policies.py:37-97` |
| All-null SKU clear | После effective time снова org triple | Есть: там же |
| Mid-period org change | Каждый Moscow day использует свою row; future change не меняет past | Есть: `test_abc_pnl_service.py:551-588` |
| Assumed observed snapshot | До observation missing; после — calculable assumed + blocker | Частично; pre-observation boundary нужен |
| Same source/ref identical vs changed | Replay same id; changed command conflict | Есть: `test_economics_policies.py:212-255` |
| Same-effective correction | Новая ref supersedes старую, later `(createdAt,id)` wins | Нужен exact fixture |
| Cross-tenant mapping/RLS | Чужой SKU missing/denied | Service + migration покрыты; real PostgreSQL RLS probe только в local handoff |
| Cross-SKU supersedes direct SQL | FK отклоняет correction A→B | Сейчас **не пройдёт**; schema gate |
| Runtime UPDATE/DELETE ledger | Role получает permission denied | Сейчас **не пройдёт**; privilege gate |
| Signed half-even ties | `±0.5→0`, `±1.5→±2`; per-sale использует gross sales units | Rounding есть: `test_abc_pnl_service.py:664-670`; daily formula есть |
| Missing/ambiguous/daily mismatch | Row и incomplete summary остаются null | Есть: `test_abc_pnl_service.py:591-637` |
| Route purity/access | Без WB; finance permission/account/tenant enforced | Есть: `test_abc_pnl_v2.py:224-283` |
| Algorithm/SKU/XLSX bridges | Только economics-bearing mutation reconciles | Есть: `test_wb_repricer_bff.py:660-720`, `:5741-5825` |
| One-field SKU patch | Canonical row остаётся sparse, inherited fields не заморожены | Сейчас **не пройдёт**; bridge передаёт полный triple |
| Actor provenance | User/import row содержит correct membership | Сейчас **не пройдёт** |
| Dual-write failure/retry/conflict | Stable event identity, no silent partial truth | Частичное service покрытие; route failure fixture нужен |
| Template/hydration bypass | Economics mutation либо canonical reconciled, либо rejected | Сейчас **не пройдёт** |
| Backfill replay/cardinality | Dry run, first apply, exact replay; counts/checksums сходятся | Нет command/manifest |
| Cache identity | Любая source/cost/economics/rules/page revision меняет hit outcome; tenant/account не пересекаются | Нужно только если canonical response cache появится |

Existing focused tests доказывают implemented service behavior, но SQLite service
fixtures не заменяют PostgreSQL privilege/constraint tests. Migration tests
проверяют forced RLS и composite tenant keys
(`tests/test_economics_migration.py:23-68`), а runtime-role test сейчас прямо
утверждает широкие DML grants (`tests/test_runtime_database_role.py:7-35`).

## Открытые gates

| Priority | Gate | Почему блокирует claim | Минимальное решение |
|---|---|---|---|
| P0 | DB append-only | Runtime role может UPDATE/DELETE; count revision тогда не гарантирует invalidation | Revoke UPDATE/DELETE на две ledger-таблицы или эквивалентный DB guard; PostgreSQL negative test |
| P0 | Tax business semantics | Product docs требуют manual `avgTaxPctFact` «после всех расходов» и отдельно называют buyer revenue before commission/logistics; код применяет `taxPct` к signed seller revenue (`product-docs/docs/open-questions-current.md:87-94`, `product-docs/docs/wb-reports-data-contract-2026-05-08.md:21-27`, `:86-96`) | Product/finance sign-off: canonical tax base, sign, returns, thresholds; затем новая formula version, если контракт меняется |
| P0 | Reproducibility/cardinality backfill | Нет raw/sanitized manifest или committed command; `3054 SKU` vs `3052 overrides` не сходятся | Preserve checksums/mapping exclusions/classification counts; dry-run + idempotent replay fixture |
| P1 | Exact SKU supersession | DB допускает cross-SKU supersedes при direct SQL | Composite FK с SKU + migration test |
| P1 | Sparse intent и author | One-field patch записывает полный override; user/import author null | Bridge передаёт только changed fields и membership; provenance fixtures |
| P1 | Dual-write/bypass | Legacy commit предшествует canonical; XLSX commits per SKU; templates/hydration обходят bridge | Stable event identity/outbox либо bounded transactional recovery; запрет/bridge для bypass paths |
| P1 | Consumer authority divergence | Repricer не читает ledger, игнорирует SKU tax и не допускает zero other-percent; Sprint D ведёт себя иначе | Отдельный measured consumer cutover/parity slice с rollback; до него документировать authorities |
| P1 | Revision contract зависит от discipline | Count безопасен лишь insert-only и over-invalidates future/unrelated rows | Сначала DB immutability; оставить count до измеренной необходимости более узкого token |
| P2 | Нет typed canonical mutation API | Direct service + legacy bridge достаточны для текущего consumer set, но не для нового settings UI | Добавлять endpoint только вместе с подтверждённым consumer и actor contract |
| P2 | Нет response cache | Это не дефект: documented p95 gate проходит | Не добавлять; при необходимости использовать полную identity выше |

## Ограничения вывода

- Raw production backups, DB rows и deploy environment не читались; deployment
  status принят только из canonical local handoff/plan.
- Observation timestamps доказывают «значение было замечено тогда», но не
  доказывают более ранний `effective_from`. Других дат этот отчёт не предлагает.
- Tracked runtime JSON — лишь repository fixture двух других organizations и не
  доказательство org `2`.
- Локальный product contract содержит внутренне разные определения tax base;
  выбрать одно инженерно без владельца продукта нельзя.
- Schema/code/runtime/migrations/handoff в этом discovery не изменялись.

## Рекомендованное решение

Принять `0055` как canonical minimum и не делать новый economics-ledger slice.
Следующая bounded работа должна сначала закрыть P0 gates: DB immutability,
утверждённую tax semantics и воспроизводимое backfill evidence. Затем отдельным
writer-hardening slice закрыть exact-SKU supersession, sparse/actor provenance и
bypass/retry fixtures. Repricer cutover и response cache остаются отдельными
задачами с собственными consumers, parity и rollback gates.
