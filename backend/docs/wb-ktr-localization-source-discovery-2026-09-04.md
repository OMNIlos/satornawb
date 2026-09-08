# Discovery: canonical source КТР и локализации WB

Дата: 2026-09-04

Статус: `BLOCKED` — подтверждённый canonical source не найден

Ветка отчёта: `codex/satorna-ktr-source-discovery` от canonical backend commit `d72d0f5`

Ограничения исследования: только локальные read-only evidence; GitHub, production, live DB и live WB API не использовались. Код, schema, migrations, reports, handoff и runtime-конфигурация не менялись.

## 1. Source verdict

Ожидаемый архитектурой `ktr_table` как подтверждённый, версионный и датированный источник КТР/локализации **отсутствует в доступных локальных данных**. Gate нельзя закрыть ни frontend-константой, ни generic cache slot, ни `krp_table`.

| Объект | Что найдено | Вердикт |
|---|---|---|
| Таблица диапазонов КТР | 20 диапазонов только в frontend dev/mock-константе; backend ожидает произвольный JSON `ktr_table`, но никто его не импортирует | Не canonical: нет raw source, версии, effective date, scope, approval и audit |
| Локализация для ABC | Legacy adapter распознаёт `statistic.selected.localizationPercent` в WB Sales Funnel на grain `period × nmId`; локальная CSV-выгрузка содержит «Локальные заказы, %» | Сильный candidate field, но не утверждённый canonical source и не warehouse-grain |
| Локализация для stock | Legacy stock builder выводит процент из приблизительных local/all orders на `nmId × warehouse/cluster` | Не exact source; `WB-01` остаётся открыт |
| `krp_table` | В backend генерируется отдельная трёхдиапазонная таблица коэффициента распределения продаж | Семантически несовместима и запрещена как fallback КТР |
| Production status | Локальный audit от 2026-08-26 фиксирует отсутствие production `ktr_table`; нового production-запроса не было | Историческое evidence подтверждает blocker, но не является live-проверкой на 2026-09-04 |

Безопасное состояние: `ktrIndex = null`, явный blocker, отсутствие финального stock action. Product-period `localizationPct` может стать отдельным canonical fact только после фиксации сырого ответа, account scope и семантики поля. Для warehouse/cluster consumer он пока также остаётся неизвестным.

## 2. Evidence index

### 2.1 Нормативные решения

| Evidence | Строки | Что подтверждает |
|---|---:|---|
| `SATORNA_SPEC_AUDIT.md` в workspace root | 442–446, 563 | `ktr_table` — незакрытый release gate; `krp_table` использовать нельзя; нужен owner и план |
| `docs/superpowers/specs/2026-08-26-satorna-platform-rebuild-architecture-design.md` во frontend architecture worktree | 53, 79–102, 265–282, 726–734 | canonical target `wb_ktr_reference`; account/product/offer identity; отсутствие source даёт `null + blocker`; владелец gate — `WB Reports` |
| `product-docs/docs/open-questions-current.md` | 20–28 | `WB-01`: формула и диапазонная таблица от Марии считаются полученными, но источник local orders по складу/кластеру не подтверждён |
| `product-docs/docs/handoffs/wb-backend-formula-catalog.md` | 58–68 | `localOrders / allOrders × 100`, затем lookup КТР; source всё ещё pending |
| `product-docs/docs/handoffs/wb-backend-source-registry.md` | 68–84 | intended portal sources, grains, manual versioned import и отдельные semantics KTR/KRP |
| `product-docs/docs/client-questions-wb-data-handoff-2026-05-25.md` | 29–35 | у клиента всё ещё запрошены точный источник local orders и финальность таблицы КТР |
| `product-docs/tz/TZ-WB.md` | 185–193 | до подтверждения формул КТР/локализацию нельзя использовать в критических расчётах |

### 2.2 Backend storage, imports и consumers

| Evidence | Строки | Наблюдение |
|---|---:|---|
| `app/repricer_cache/orm.py` | 33–66 | `wb_repricer_source_cache`: unique `(organization_id, source_key)`, JSON payload и `fetched_at`; `marketplace_account_id` и KTR lineage отсутствуют |
| `alembic/versions/20260604_0009_wb_repricer_source_cache.py` | 13–27 | исходный DDL того же mutable org-only cache |
| `app/repricer_cache/store.py` | 44–77, 452–483, 735–789 | range metadata необязательна; save перезаписывает единственную строку и ставит новое время записи |
| `alembic/versions/20260526_0002_source_registry.py` | 20–83 | `source_registry_*` хранит metadata каталога, не KTR data |
| `app/source_registry/seed_loader.py` | 9–12, 207–240 | registry заполняется из Markdown-документов |
| `app/source_registry/service.py` | 53–112 | metadata rows пересоздаются из seed; это не ingest справочника |
| `app/wb_reports_sprint_d.py` | 1802–1819, 1893–1896, 2013–2016, 2098–2099 | ABC читает `ktr_table`, берёт localization из baskets и при пустой таблице ставит `WB_ABC_KTR_TABLE_MISSING` |
| `app/wb_reports_sprint_d.py` | 2148–2196 | KTR evidence получает `lastSyncedAt=utc_now()` при построении ответа, а не source-observed time |
| `app/routers/wb_reports_bff.py` | 1499–1514, 1610–1641, 1663–1708 | stock report читает manual KTR slot, рассчитывает localization и выдаёт partial/comment при отсутствии источника |
| `app/routers/wb_reports_bff.py` | 1283–1302, 1502–1514 | `krp_table` создаётся inline и сохраняется как `fresh`; это не evidence КТР |
| `app/repricer_bff.py` | 3055–3117, 3120–3187 | Sales Funnel adapter запрашивает период и переносит `selected.localizationPercent` в product-level `localizationPct` |
| `app/wb_api/rnp_runtime.py` | 230–273 | второй normalizer Sales Funnel поле localization вообще не сохраняет |
| `app/report_rules/service.py` | 94–110 | `localizationPct = null` корректно превращается в rule band `unknown` |
| `app/platform/catalog/orm.py` | 13–108 | canonical `CatalogSku`, account-scoped `MarketplaceProduct` и `MarketplaceOffer` |
| `app/platform/catalog/service.py` | 178–227 | `nmId → CatalogSku` разрешается только при единственном SKU; множественные связи помечаются ambiguous |

Exact multiline search по `app/`, `alembic/` и `tests/` не нашёл:

- KTR-specific import route, CLI, task, parser или backfill;
- вызов `save_source_cache(..., "ktr_table", ...)`;
- typed DTO для строк КТР;
- таблицу/ORM/migration `wb_ktr_reference`, `ktr_table`, `krp_table` или localization facts.

Generic `save_source_cache` технически способен принять любой JSON, но сам по себе не является source contract или ingestion path.

### 2.3 Frontend-кандидат

| Evidence | Строки | Наблюдение |
|---|---:|---|
| `frontend/src/features/wb-reports/repository.ts` во frontend repo | 69–106 | hardcoded 20 bands с разными `territorialCoefficient` и `salesDistributionCoefficient` |
| тот же файл | 583–618 | коэффициенты применяются к искусственно построенным warehouse rows |
| `frontend/src/features/wb-reports/repository.test.ts` | 351–355 | тест называет константу «Maria localization table», но не даёт source reference |
| `frontend/src/mocks/handlers.ts` | 94–119 | repository обслуживает dev MSW report handler |
| `frontend/src/main.tsx` | 6–7 | MSW включается только при `DEV && VITE_ENABLE_MSW=true` |

`git blame` относит все 20 bands к commit `81b1ab7` (`Dima`, 2026-06-02, `Ship Vella React frontend`). Таблица внутренне непротиворечива на precision 0,01 п.п., но история кода не доказывает её источник, approval или срок действия. Импортировать её как canonical data нельзя.

### 2.4 Локальные XLSX/CSV assets

Проверены все 63 файла `*.xlsx`/`*.csv` в workspace, 31 уникальный SHA-256: 48 XLSX и 15 CSV. Дубликаты worktree-файлов дедуплицировались по SHA-256; XLSX проверялись через OOXML ZIP/XML, CSV — построчно. Семантический exact search включал `КТР/KTR`, `КРП/KRP`, localization, «локальные заказы», territorial и sales distribution.

Релевантны только три связанные CSV:

| Файл | SHA-256 | Что есть | Почему не canonical |
|---|---|---|---|
| workspace `df_products.csv` | `2520b1d678fb35e1cfc7a631f7e2cfbb911f0b4a0bf3c92fac9eeadcefbf7d71` | 3 231 product rows; `Артикул WB`, seller article, current/previous «Локальные заказы, %» | все 3 231 current и previous values равны `100`; нет дат периода, org/account, raw source ID или extraction audit |
| workspace `df_filters.csv` | `50283c331803652044870b2b2add365b37bbfe9e10730c4c06e9ff91633ec22e` | один aggregate row, current/previous local orders = `100%` | aggregate без product identity и периода |
| workspace `df_metrics.csv` | `8971e22eb457aee8314ffe09a35b6d96562c3d07b001e7b5fadb4d553cbc9c51` | определение: локальные заказы / все заказы; локальный заказ совершается в одном регионе | справка, а не fact/reference data |

В остальных XLSX/CSV таблицы диапазонов КТР, KTR values, version/effective dates и provenance нет. Два лексических совпадения после ручной проверки исключены: `krp` находится внутри opaque КИЗ-строки finance row, «территориальный» — часть адреса доставки.

Дополнительно проверено отсутствие локальных `*.db`, `*.sqlite*` и DB dump с KTR data. Live DB не запрашивалась, потому что отдельного разрешения пользователя нет.

### 2.5 Repository coverage и production evidence

- Git repositories: `backend/ogni-elfs`, `frontend`, `avito-orders-extension`.
- Read-only deploy/snapshot copies: `ogni-elfs-main`, `ogni-elfs-live`, `ogni-elfs-prod`, `ogni-frontend-main` и зарегистрированные backend/frontend worktrees.
- Adjacent workspaces `comcookie` и `wb-pdf-matcher`: релевантных KTR/localization source hits нет.
- `docs/wb-abc-production-audit-2026-08-26.md` в historical backend worktree, строки 54, 130, 170–173: на дату аудита production `ktr_table` отсутствовал, `krp_table` не использовался, вывод был `null + partial + blocker`.

Этот historical audit — единственное локальное production evidence. Текущий production state намеренно не проверялся.

## 3. Наблюдаемый data flow

```text
WB Sales Funnel selected.localizationPercent
  -> legacy baskets_{period} org-only JSON cache
  -> ABC row localizationPct at period × nmId
  -> lookup in ktr_table JSON
  -> ktrIndex or null + WB_ABC_KTR_TABLE_MISSING

local/buyer-region estimates
  -> stock row at nmId × warehouse/cluster
  -> derived localizationPct
  -> same missing ktr_table lookup
  -> source_partial/review-only stock decision

frontend LOCALIZATION_BANDS / backend inline krp_table
  -> demo or incompatible values
  -> never a canonical KTR fallback
```

Canonical `app/modules/wb_reports` пока не содержит KTR/localization consumer. Фактические consumers находятся в legacy ABC/stock builders, background report tasks, rule evaluator и parity UI. UI уже умеет показывать `—`/«нет данных», поэтому синтетическое число не требуется.

## 4. Source location, owner и update process

### 4.1 Intended source

Локальный source registry указывает:

- KTR bands: WB Seller Portal → Warehouse tariffs → Localization index;
- exact local orders: WB Seller Portal → Analytics → Stock analytics → Order geography;
- публичный API для этих portal tables не подтверждён;
- ожидаемый cadence: manual versioned import при изменении таблицы WB;
- отсутствие approved version оставляет KTR неизвестным и запрещает финализировать stock decision.

Фактического export-файла, import pipeline или утверждённой версии в workspace нет.

### 4.2 Ownership

- accountable owner снятия gate: `WB Reports`;
- business approver диапазонов/формулы: Мария, сейчас `source pending`;
- discovery owner exact local orders: `Backend discovery`, blocker `WB-01`;
- importer/operator и SLA обновления не назначены.

Минимальный operating process после снятия blocker: owner сохраняет неизменяемый raw artifact с checksum, business approver фиксирует semantics/scope/effective date, import валидирует и публикует новую append-only version. Предыдущая версия не перезаписывается.

## 5. Grain, scope и mapping

### 5.1 Разделить reference и observation

KTR reference и localization observation — разные сущности:

| Сущность | Правильный grain | Business key |
|---|---|---|
| KTR band version | source scope × effective version × localization band | `(scope, effective_from, lower_bp, upper_bp)` |
| Product localization | organization × WB account × period/day × `nmId` | `(organization_id, marketplace_account_id, period, nm_id, source_identity)` |
| Warehouse localization | organization × WB account × period/day × `nmId` × direct warehouse/cluster identity | тот же key + source warehouse/cluster key |
| Derived KTR observation | localization observation × applicable KTR version | source observation key + KTR version ID |

`bp` означает integer basis points процента: `0..10000`. Это исключает floating gaps между диапазонами вида `94.99` и `95`.

### 5.2 Organization/account scope

Текущий `ktr_table` slot scope — только organization, чего недостаточно для нескольких WB accounts. До import необходимо получить доказательство одного из вариантов:

- `wb_global`: одна опубликованная WB version, tenant projection явно ссылается на неё;
- `marketplace_account`: version принадлежит `(organization_id, marketplace_account_id)`.

Scope нельзя вывести из того, что два аккаунта временно получили одинаковые значения. Любой localization fact всегда account-scoped.

### 5.3 Product, offer и CatalogSku

- WB `nmId` → `MarketplaceProduct.external_product_id` только внутри `(organization_id, marketplace_account_id)`.
- Прямая строка с доказанным WB `chrtId` → `MarketplaceOffer.external_offer_key`.
- `sellerArticle` — диагностический атрибут, не primary mapping key.
- `df_products.csv` и текущий Sales Funnel candidate дают `nmId`, но не `chrtId`/barcode/warehouse identity: значение остаётся на `MarketplaceProduct`.
- Product-level localization/KTR нельзя размножать по всем offers или `CatalogSku`.
- Projection на `CatalogSku` допустима только при доказанном offer mapping; существующий resolver возвращает mapping лишь для единственного SKU и отдельно помечает ambiguous products.
- KTR reference сам по себе не имеет `nmId/chrtId`: он присоединяется к localization observation по проценту, scope и business date.

## 6. Business/effective dates, freshness и audit

У найденных KTR-кандидатов нет воспроизводимого business time:

- frontend bands не имеют source version, `effective_from/effective_to` и published date;
- generic `ktr_table` cache перезаписывается целиком, поэтому исторический отчёт применил бы текущую таблицу к старому периоду;
- cache `fetchedAt` — время записи, не время публикации/действия WB table;
- ABC формирует KTR `lastSyncedAt` текущим временем чтения;
- CSV local-orders export содержит current/previous columns, но не сами границы периодов;
- отсутствуют raw artifact URI/checksum, source row identity, import actor, approver, change reason и supersession link.

Следовательно, никакой найденный timestamp не доказывает freshness КТР.

## 7. KTR и KRP несовместимы

| Свойство | `ktr_table` | `krp_table` |
|---|---|---|
| Семантика | коэффициент территориального распределения / localization index, связанный с логистикой | коэффициент распределения продаж |
| Expected field | `ktr` / `ktrIndex` | `krp` / sales distribution coefficient |
| Backend lookup | отдельный reader `ktr_table` | inline 3-band seed `1.0/0.8/0.6` |
| Допустимость fallback | canonical только после approval | не заменяет KTR |

Frontend mock хранит оба коэффициента рядом, но в разных полях. Даже если единый raw document когда-нибудь подтвердит оба столбца, они должны сохраняться и версионироваться как разные metrics.

Есть терминологическая ловушка: `frontend/docs/wb-reports-terminology-presentation-2026-05-08.md:121–130` называет «КТР» транслитерацией CTR. Для этого gate такое значение неверно: `frontend/research/indeepa-wiki/wb-02-editor.md:207–218` и клиентский контекст определяют КТР как коэффициент территориального распределения, влияющий на логистику.

## 8. Exact blocker contract

До получения approved source canonical projection обязана вести себя так:

```json
{
  "localizationPct": null,
  "ktrIndex": null,
  "sourceStatus": "partial",
  "blockerIds": ["WB_ABC_KTR_TABLE_MISSING"]
}
```

Правила:

1. Для ABC числовой `localizationPct` допустим отдельно от КТР только после подтверждения account-scoped `Sales Funnel statistic.selected.localizationPercent`; `ktrIndex` всё равно остаётся `null` до approved bands.
2. Для warehouse stock `localizationPct` остаётся `null`, пока не закрыт `WB-01`. Приближение из raw orders/buyer region можно публиковать только отдельным estimated field, не как exact localization.
3. Missing нельзя заменять на `0`, `1`, последнее mock-значение, frontend constant или `krp`.
4. Stock decision остаётся `source_partial`/`review_candidate`; КТР не участвует в final action, repricer guard, логистике или марже.
5. UI показывает `—`/«нет данных» и blocker, а не числовой placeholder.
6. Отсутствие KTR блокирует только KTR/localization columns и полный ABC column gate; независимые finance metrics продолжают работать.

`WB_ABC_KTR_TABLE_MISSING` уже реализован для ABC. Registry blocker `WB-01` продолжает описывать отсутствие exact warehouse/cluster localization source. Stock endpoint пока имеет только текстовый warning; это наблюдение, не разрешение менять report в рамках discovery.

## 9. Contract снятия blocker

Это acceptance contract, а не новая schema.

### 9.1 KTR version envelope

Обязательны:

- `source_version_id: string`;
- `scope_kind: wb_global | marketplace_account` и соответствующий scope key;
- `effective_from: date`, `effective_to: date | null`, `published_at: datetime | null`;
- `source_reference: string`, immutable raw artifact и `raw_sha256`;
- `imported_at`, `imported_by`, `approved_at`, `approved_by`;
- semantic/schema version и явное имя metric: territorial KTR, не CTR и не KRP.

Каждый band содержит `lower_bp: int`, `upper_bp: int`, точное правило границ и `ktr_index: decimal`. Если source содержит KRP, он получает отдельное поле/contract и никогда не заполняет `ktr_index`.

### 9.2 Localization observation

Обязательны:

- `organization_id`, `marketplace_account_id`, source run/reference;
- `period_from/period_to` либо `business_date`;
- positive `nm_id`;
- `chrt_id`, warehouse и cluster только если они прямо присутствуют в source;
- `local_orders`, `all_orders`, `localization_pct` с указанием, какие поля direct, а какие derived;
- source row identity/fingerprint, raw checksum и observed/imported timestamps;
- grain enum: product-period или product-warehouse-cluster-period.

### 9.3 Data-quality gates

- диапазоны полностью и ровно покрывают `0..10000 bp` на заявленной precision, без gap/overlap;
- для любого процента находится ровно один KTR band;
- KTR finite и non-negative;
- на scope/date активна ровно одна approved version;
- effective intervals не пересекаются; исторический lookup использует business date, не import time;
- `0 <= local_orders <= all_orders`, `0 <= localization_pct <= 100`; при `all_orders = 0` процент остаётся `null`;
- если одновременно даны counts и percent, расхождение после утверждённого rounding не превышает 0,01 п.п.;
- дубликаты source identity идемпотентны, конфликтующие дубликаты блокируют import;
- account ownership и `nmId` mapping существуют; ambiguous offer/CatalogSku mapping не fan-out'ится;
- imported row counts, rejected rows, checksum и approver сохраняются как audit evidence.

Backfill разрешён только внутри доказанного effective interval и source period. Frontend bands, file mtime и current cache нельзя распространять назад как historical truth.

## 10. Точное условие снятия blocker и следующий минимальный шаг

Gate снимается только после одновременного выполнения двух условий:

1. `WB Reports` получает от Марии/владельца WB-кабинета исходный WB Seller Portal export, screenshot с воспроизводимым navigation context либо официальный документ с диапазонами КТР, названием/единицей metric, scope и датой действия; artifact утверждён и имеет checksum.
2. Для каждого нужного consumer grain отдельно подтверждён source локализации:
   - ABC: frozen raw Sales Funnel response/export с `period × nmId × localizationPercent` и account identity;
   - stock: source с `period/day × nmId × warehouse/cluster` и exact local/all orders либо прямым exact percent.

Следующий минимальный шаг: `WB Reports` запрашивает и складывает в discovery intake **один source package** — KTR table artifact + один raw localization sample для конкретного WB account/period + effective date/scope + approval Марии. После этого выполняется только contract/DQ review; ingestion и backfill проектируются уже по подтверждённому grain.

До появления этого package дальнейшая разработка KTR storage/import не нужна: она закрепила бы недоказанную семантику.
