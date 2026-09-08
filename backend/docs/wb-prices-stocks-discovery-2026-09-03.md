# Discovery: canonical WB prices and stocks

Дата: 2026-09-03

Статус: architecture/discovery only

Ветка отчёта: `codex/satorna-wb-prices-stocks-discovery` от canonical backend commit `1c9dd5a`

Дополнительный read-only baseline: локальный backend `main` на `748888f` и текущий frontend workspace

## 1. Решение

Для WB prices и stocks нужны не новые JSON-кэши, а три уже предусмотренных архитектурой append-only набора данных:

- `wb_price_snapshot` — неизменяемые наблюдения цены из одного завершённого source snapshot;
- `wb_stock_snapshot` — неизменяемые строки текущего остатка в фактическом grain источника;
- `wb_stock_daily` — дневной срез, построенный только из реально полученного полного stock snapshot.

Каждый набор обязан быть привязан к `organization_id`, `marketplace_account_id`, источнику, версии семантики, sync run, внешней identity и business time. Текущим значением считается строка из последнего **полного успешного** snapshot того же account/source/semantic version. Частичный или ошибочный запуск не становится current: разрешено показать последний полный snapshot как `stale`, но нельзя смешивать его со строками нового запуска.

Критические выводы:

1. `clubDiscount` и `clubDiscountedPrice` — отдельная плоскость WB Club/кошелька, а не подтверждение SPP и не подтверждённая buyer price без кошелька.
2. `supplier.orders.spp` и finance-derived SPP — исторические значения событий/периода. Они не заменяют current SPP и не могут разблокировать изменение цены.
3. `nmId` идентифицирует `MarketplaceProduct`. Размер/вариант можно привязать к `MarketplaceOffer` только после доказанного mapping стабильного WB external offer key. `sellerArticle`, индекс первого размера и `content.sizes[].skus` таким доказательством сейчас не являются.
4. Остатки WB, async warehouse remains, seller/FBS stock, product stock metrics и ручной XLSX-остаток — разные факты. Их нельзя сливать через `max`, вычитание или общий cache key `stocks`.
5. Price, SPP, wallet, stock valuation, P_min/P_max и margin должны вычисляться backend-проекцией. Frontend получает готовые значения и состояния, а не формулы.

До подтверждения buyer-price semantics и offer identity безопасный минимальный результат — canonical seller-price и product-level/current stock snapshots с заблокированным auto-apply для неоднозначных SKU.

## 2. Границы и способ исследования

Исследование выполнено без GitHub, production и live WB calls. Код, DDL, Alembic, handoff и runtime-конфигурация не менялись. Рассматривались:

- обязательные SATORNA handoff/audit/architecture документы;
- canonical platform worktree с `MarketplaceAccount`, catalog, costs, period и finance patterns;
- legacy WB ingestion/BFF/tasks/caches в canonical worktree;
- локальный backend `main` только для выявления branch drift;
- текущие frontend consumers только read-only.

Ветка `main` и canonical platform branch расходятся после общего предка: `main` содержит более поздние legacy WB/report изменения, а canonical branch — новые platform catalog/finance/economics сущности. Поэтому дизайн ниже следует canonical architecture, а фактические legacy риски проверены в обеих локальных версиях. Перед реализацией будущего slice нужен обычный rebase/merge audit; переносить выводы через конфликт автоматически нельзя.

## 3. Наблюдаемый pipeline сегодня

| Этап | Реализация | Фактический результат | Риск |
|---|---|---|---|
| Seller prices | `repricer_sync.fetch_catalog_goods_page` / `repricer_bff._fetch_catalog_goods`, WB `POST /api/v2/list/goods/filter` | goods с `nmID`, `vendorCode`, `discount`, `clubDiscount`, `sizes[]` | Дальше используется только `sizes[0]` |
| Buyer price | `repricer_sync.fetch_external_spp_prices`, внешний `GET /prices?nm=...` | `{nm, product, status}` превращается в buyer price | Нет account/offer/region/cohort/source time; контракт значения `product` не зафиксирован |
| Price enrichment | `_apply_external_spp_prices_to_goods` / `_merge_good_spp_fields` | buyer aliases внедряются в первый size | Остальные sizes удаляются; provenance теряется |
| Goods storage | `wb_repricer_goods_cache` + Redis goods list/meta + process cache | страницы JSON по organization | Нет marketplace account, snapshot ID и атомарной публикации |
| Content identity | `_fetch_content_cards` | cards по `vendorCode`/`nmID`; `sizes[].skus` собираются как `chrtIds` | Mapping на WB offer/`chrtId` не доказан; ограниченная пагинация может обрезать набор |
| Current WB stock | `fetch_stock_aggregates`, `POST /api/analytics/v1/stocks-report/wb-warehouses` | строки немедленно суммируются по `nmId` | Теряются `chrtId`, warehouse ID/name и исходный grain |
| Product stock metrics | `POST /api/v2/stocks-report/products/products` | `stockCount` за переданный date range | Смешивается с current WB stock через `max`; семантика периода теряется |
| Detailed report stock | `reports_sources_runtime` | current detailed rows либо async remains rows | При rate limit сохраняется неполный prefix; async identity дополняется эвристически |
| Seller/FBS stock | `POST /api/v3/stocks/{warehouseId}` | `warehouseId × chrtId × amount` | Отдельный источник, но downstream bundle допускает совместную обработку с WB stock |
| Manual stock | `/imports/stocks-excel`, nomenclature import, simulator | ручные значения пишутся в тот же `stocks` cache | Ручной input подменяет WB observation |
| Stock storage | `wb_repricer_source_cache`, key `stocks` и вспомогательные source keys | mutable JSON latest-state по organization | Нет account, source revision, immutable history и надёжной completeness |
| Daily stock history | `reports_history.ensure_daily_stock_history` | process-memory rows по date/nmId/warehouseName | Прошлые дни заполняются текущим значением; organization/account отсутствуют |
| Repricer | `list_repricer_skus` → `_build_sku_row` → `repricer_execution` / `repricer_sprint_b` | одна строка на goods product/vendor article | First-size price, nmId-only joins, period SPP в planning margin, небезопасные stock defaults |
| Reports | `build_cached_wb_reports_sources_snapshot` → report payload caches | current stock объединяется с period stats/finance | Один current stock cache используется для любого периода; source/grain labels могут быть ложными |
| Catalog v2 | `/api/v2/wb/products` | canonical products дополняются legacy goods prices | Goods индексируются по `nmId` в organization scope, поэтому возможен cross-account match |
| Frontend | `liveParityData.ts`, `VellaHtmlParityPage.tsx`, report repository/types | UI повторно считает buyer price, wallet, bounds, margin, stock value и days-to-OOS | Backend перестаёт быть единственным владельцем формул и source state |

### 3.1 Адаптеры и cadence

`wb_sync_plan.py` задаёт hourly goods и трёхчасовой current stock sync; onboarding также включает goods/content/stocks. Nightly reconciliation не создаёт истинную price/stock history. Celery только опрашивает schedule и материализует response payload caches. Готовность goods/content/stocks определяется преимущественно `count > 0`, а не account, snapshot completeness, age или source semantics.

Goods pagination публикуется page-by-page: на первой странице старый набор удаляется, затем каждая страница отдельно commit-ится. Ошибка поздней страницы оставляет опубликованный partial catalog. Внешний SPP failure логируется отдельно и не делает goods snapshot partial. Аналогично stock/report adapters могут сохранить уже полученные строки после 429.

## 4. Identity contract

### 4.1 Tenant и marketplace account

Canonical parent для любого WB fact:

`Organization → MarketplaceAccount(marketplace='wb') → MarketplaceProduct(account, nmId) → MarketplaceOffer(product, externalOfferKey) → CatalogSku`.

Правила:

- `organization_id` нужен для RLS, но недостаточен для business identity;
- `marketplace_account_id` обязателен на каждом sync run, price row, stock row, daily row и cache projection;
- credential/token выбирает account до запроса; token fingerprint не является business key;
- один `nmId` в разных WB accounts — разные `MarketplaceProduct`;
- legacy user/org token stores нельзя неявно связать с canonical account: связь должна быть явной и проверяемой;
- seller article — изменяемый атрибут/lookup hint, не primary identity.

Текущий `/api/v2/wb/products` нарушает эту границу: получает canonical products всех WB accounts организации, но legacy goods индексирует только по `nmId`. До account-scoped price projection такой merge нельзя считать canonical.

### 4.2 Product и offer

| Наблюдение источника | Canonical target | Условие |
|---|---|---|
| `nmID` / `nmId` | `MarketplaceProduct.external_product_id` | Прямая account-scoped identity |
| Product-level field вне `sizes[]` | product grain, logical key `product:<nmId>` | Не копировать во все offers |
| Size-level price/stock с подтверждённым stable ID | `MarketplaceOffer.external_offer_key` | Только после документированного mapping ID → WB variant |
| `vendorCode` / seller article | атрибут продукта и secondary lookup | Не объединять товары только по строке артикула |
| `content.sizes[].skus` | unresolved external identifiers | Не объявлять `chrtId`, пока mapping не доказан |
| Единственный canonical offer из cost import | не доказательство WB size identity | `seller_article` в current cost backfill — бизнес-артикул, не WB variant key |

Если источник даёт только product-level value, canonical row остаётся product-level даже при наличии одного offer. Правило `resolve_wb_product_skus`, которое разрешает product → SKU только при единственном offer, пригодно для read projection, но не изменяет исходный grain факта.

### 4.3 Warehouse

- Stable `warehouseId` используется как external warehouse identity только в источнике, который его действительно вернул.
- `warehouseName` без ID остаётся source-local key, например `name:<normalized source name>`; он не превращается в WB warehouse ID по догадке.
- Match `(nmId, lower(warehouseName))` между async remains и detailed report допустим как отдельный derived mapping с confidence/evidence, но не как изменение direct fact.
- Специальные async rows «в пути» нельзя целиком приписывать первому физическому складу.
- Marketplace seller warehouse (`/api/v3/stocks/{warehouseId}`) и WB/FBW warehouse — разные namespaces и stock scopes.

## 5. Canonical price facts

### 5.1 Матрица значений

| Значение | Наблюдаемый источник и raw field | Фактический grain | Класс | Canonical semantics | Period applicability |
|---|---|---|---|---|---|
| Seller list/base price | WB Prices API `sizes[].price` | account × product × source size, если size различим | direct/confirmed field presence | `seller_list_price_kopecks`; не называть current selling price | current snapshot only |
| Seller discount | `discount` | account × product в наблюдаемом payload | direct/confirmed field presence | `seller_discount_pct`; хранить независимо от price | current snapshot only |
| Seller discounted price | `sizes[].discountedPrice` | account × product × source size | direct/confirmed | `seller_discounted_price_kopecks`; это текущая seller plane до buyer-side discounts | current snapshot only |
| Club discount | `clubDiscount` | account × product | direct, semantics limited to WB Club | `club_discount_pct`; не `spp_pct` | current snapshot only |
| Club price | `sizes[].clubDiscountedPrice` | account × product × source size | direct, semantics limited to WB Club | `club_price_kopecks`; не buyer-no-wallet | current snapshot only |
| Buyer price without wallet | внешний 41-SPP `{nm, product, status}` и внедрённые aliases | фактически только nmId; buyer context неизвестен | **unconfirmed candidate** | отдельный `buyer_price_no_wallet_kopecks` только после фиксации provider contract/context | current observation only; пока blocked |
| Current SPP | seller discounted + confirmed buyer-no-wallet из совместимого snapshot/context | тот же account/product-or-offer/time/context | derived | `(seller_discounted - buyer_no_wallet) / seller_discounted × 100`; provenance обоих operands обязателен | current only |
| Buyer price with wallet | explicit compatible provider field либо buyer-no-wallet + wallet policy | тот же grain/context | direct или derived estimate, не смешивать | direct value хранить отдельно; derived value маркировать formula/rounding version | current only |
| Order SPP | WB Statistics `supplier.orders[].spp` | account × order event × product/offer when present × event time | direct historical event field | input для period aggregate/distribution, не current fact | период события |
| Order buyer price | `finishedPrice` | account × order event | direct historical event field | realized/order-context buyer price, не current catalog price | период события |
| Finance buyer/seller price relation | finance operations/rollups | account × finance operation × business date | direct operations + derived aggregate | P&L/reconciliation only | выбранный период/закрытие |
| Configured `wbWalletType` | algorithm settings | organization/account policy scope | configuration, не marketplace observation | scenario input; не записывать как observed WB discount | effective interval of config |
| Local price override | repricer runtime settings | org × article today | local state | отдельный proposed/local price; не подменяет WB observed current price | effective interval/audit |

Для каждого money field source adapter должен нормализовать документированную unit, currency и rounding rule. Текущий порог `value >= 100000 => already kopecks` неприемлем: реальная цена 100 000 RUB становится неотличима от legacy fixture 100 000 kopecks. Legacy compatibility следует решать версией payload/source adapter, а не величиной числа.

### 5.2 Buyer price/SPP: зафиксированная неоднозначность

В репозитории одновременно существуют три несовместимые трактовки:

1. Product docs/source registry/discovery map объявляют `clubDiscount` или разницу `discountedPrice → clubDiscountedPrice` SPP-like и считают `clubDiscountedPrice` ценой после SPP.
2. Runtime `_resolve_spp_analytics` и `test_wb_price_units.py` прямо утверждают, что Club — wallet/club plane, не SPP и не buyer-no-wallet.
3. Period orders/finance SPP используется как planning fallback для текущей маржи, а некоторые legacy tests ожидают, что он станет current `sppPct` и синтетической buyer price.

Canonical решение:

- presence полей WB Prices API подтверждает seller/Club fields, но не buyer public price semantics;
- внешний 41-SPP adapter остаётся `candidate` до фиксации: владелец/версия API, валюта/unit, meaning поля `product`, buyer cohort/region, wallet inclusion, account dependence, observed time, error/partial contract;
- current `spp_pct` не является independently observed fact, если нет отдельного подтверждённого source field; это derived fact из совместимых current seller/buyer operands;
- order/finance SPP сохраняется под отдельным metric name (`order_spp_pct`, `period_spp_*`) и никогда не переименовывается в current SPP;
- Club/wallet discount не разрешает WB-06/current buyer guard;
- если buyer price отсутствует или больше seller discounted price, строка получает validation error/blocked state. Значение не следует молча превращать в `null` без evidence причины.

### 5.3 Запрещённые price fallback

Запрещено:

- `clubDiscountedPrice` → buyer price without wallet;
- `clubDiscount` → SPP;
- latest/average `supplier.orders.spp` → current SPP;
- finance-period SPP → current SPP;
- `avgPriceWithSppKopecks` → current buyer price;
- current seller price × historical SPP → observed buyer price;
- configured wallet percent → observed marketplace field;
- first `sizes[0]` → все offers продукта;
- product price → offer price без доказанного mapping;
- local override → WB observed price;
- changelog last event → complete current/history snapshot;
- magnitude-based RUB/kopecks guessing;
- additive composition `1 - (SPP + wallet)` как эквивалент последовательных скидок без подтверждённого правила WB.

Последний пункт уже расходится внутри продукта: backend accounting применяет скидки последовательно, тогда как часть frontend calculator использует сумму процентов.

## 6. Canonical stock facts

### 6.1 Матрица значений

| Значение | Источник и raw field | Фактический grain | Класс | Canonical use | Period applicability |
|---|---|---|---|---|---|
| WB warehouse quantity | `stocks-report/wb-warehouses.quantity` | account × nmId × chrtId? × warehouseId | direct current | `quantity_units` в `stock_scope=wb_warehouse` | current snapshot only |
| In way from client | `inWayFromClient` | тот же grain | direct current | отдельное поле | current snapshot only |
| In way to client | `inWayToClient` | тот же grain | direct current | отдельное поле, не включать в available | current snapshot only |
| Available units | quantity + inWayFromClient | тот же snapshot/grain | derived/confirmed business rule WB-18 | formula-versioned derived projection | current или actual daily snapshot |
| Warehouse remains quantity | async `warehouses[].quantity` | account × nmId × barcode/techSize × warehouseName | direct snapshot, weaker identity | отдельный source semantics; fallback display only | current-at-download |
| Async special in-way totals | special named rows | account × product/offer × special bucket | direct source bucket | хранить bucket отдельно; не назначать складу | current-at-download |
| Seller/FBS amount | `/api/v3/stocks/{warehouseId}` `chrtId`, `amount` | account × seller warehouseId × chrtId | direct current | `stock_scope=seller_fbs`; не WB stock | current snapshot only |
| Product `stockCount` | stock product metrics | account × nmId × requested period/context | direct source metric, semantics separate | QA/fallback signal; не сливать с quantity | только указанный source context |
| Size/office stock metric | stock products/sizes | account × nmId × chrtId × office | direct source metric | diagnostic/QA, пока mapping office↔warehouse не подтверждён | source period/context |
| Product/warehouse aggregate | сумма совместимых detailed rows | account × product/offer × selected warehouses × snapshot | derived | read projection с coverage и component count | snapshot time |
| Manual stock total/FBS/FBM | XLSX/nomenclature/settings | account? × seller article | manual/configuration | отдельный manual fact namespace; не WB observation | import/effective time |
| Was OOS | actual daily available <= 0 | account × product/offer × business date, после согласованной агрегации | derived | только при фактическом daily coverage | daily/history |
| Days to OOS | current available / period demand rate | смешанный current + period | downstream derived metric | backend report/repricer projection с явными basis/period, не stock fact | period-dependent |
| Stock value | units × chosen price/cost | смешанный stock snapshot + valuation snapshot | downstream derived metric | backend projection с `valuation_basis` и обеими snapshot IDs | as-of/period-dependent |

`reserve` отсутствует как подтверждённый stock fact (WB-21 открыт). Его нельзя добавлять нулём или вычислять из прочих полей.

### 6.2 Current и daily semantics

`wb_stock_snapshot` хранит каждую реально полученную строку полного source response. Product/warehouse totals строятся поверх него; исходные строки не заменяются aggregate JSON.

`wb_stock_daily` создаётся один раз на Moscow business date из конкретного полного successful snapshot:

- `business_date_msk` выводится из actual `source_observed_at`, а при его отсутствии — из явно отмеченного `received_at`, но не из `dateTo` пользовательского отчёта;
- membership содержит source snapshot ID;
- пропущенный день остаётся `missing`; вчера нельзя заполнить сегодняшним количеством;
- поздняя коррекция создаёт новую version/supersession с audit reason, а не переписывает историю без следа;
- availability по SKU/day агрегируется только по совместимым stock scope и безопасно разрешённым identities;
- при неполной warehouse/offer coverage результат `partial/unknown`, а не `false`/`0`;
- `stockAvailability7d` должен допускать `null`; преобразование `null → false` и default `[true × 7]` запрещены.

### 6.3 Запрещённые stock fallback

Запрещено:

- `max(stockCount, sum(quantity))` как «истинный total»;
- `marketplaceStock = total - wbStock` при разных source semantics;
- current stock → произвольная историческая дата отчёта;
- текущий quantity → все отсутствующие предыдущие дни;
- отсутствие nmId в существующем cache → stock zero/`stockState=ok`;
- missing stock → `1`, manual FBS+FBM или `basketsLast7d × 2` в price decision/guard;
- async special in-way quantity → первый warehouse;
- warehouse name → stable warehouse ID без evidence mapping;
- seller/FBS amount → WB warehouse stock;
- XLSX import → overwrite WB `stocks` snapshot;
- partial page prefix → current complete snapshot;
- product aggregate → offer rows без доказанного offer mapping.

## 7. Snapshot envelope и source state

Price и stock используют тот же минимальный pattern, который уже реализован для canonical finance: sync run header + immutable facts + run membership/current projection. Универсальный framework здесь не нужен.

Обязательные metadata sync run:

| Поле | Назначение |
|---|---|
| organization/account IDs | tenant isolation и business account scope |
| sync run / snapshot ID | immutable membership и reproducibility |
| source ID + semantic version | запрещает fallback между разными meanings |
| request kind/context | current vs period, stock scope, filters, provider/buyer context |
| requested/started/received/completed timestamps | transport chronology |
| source observed time | business observation time, nullable если источник не даёт |
| Moscow business date | daily selection, вычисляется один раз |
| status | `complete`, `partial`, `failed`; current pointer только для complete |
| page/cursor/count metadata | expected/received pages and rows, truncation evidence |
| request IDs, rate-limit/error metadata | diagnosis без потери причины |
| raw/snapshot checksum | idempotency и shadow comparison |
| formula/schema version | воспроизводимость derived fields |

Публичная projection state:

- `fresh`: последний complete snapshot младше source-specific TTL;
- `stale`: complete snapshot существует, но TTL истёк либо более новый run завершился partial/error;
- `partial`: относится к attempt/run diagnostics; partial rows не становятся current business facts;
- `missing`: ни одного совместимого complete snapshot нет;
- `blocked`: identity/semantics/credential validation не позволяет использовать факт;
- `error`: последняя попытка завершилась ошибкой; при наличии last-good UI может показать его только как stale.

Нельзя обновлять `fetchedAt` в момент чтения cache. Сейчас `build_price_metrics_snapshot_from_row` ставит `datetime.now()` и тем самым делает старый goods cache «свежим» ещё на 60 минут после каждого read.

## 8. Cache identity, deduplication и storage invariants

### 8.1 Cache identity

Redis/response cache — ускоритель, не source of truth. Минимальная identity:

- current price projection: `org + account + source semantic version + complete snapshot ID + product/offer filters`;
- current stock projection: `org + account + stock scope/source semantic version + complete snapshot ID + product/offer/warehouse filters`;
- period report: `org + account set + Moscow period + group/filter/sort/page + price/stock/finance/etc source revisions + formula version`;
- repricer list: те же account/source revisions плюс settings/economics revision.

TTL не заменяет snapshot revision. Cache entry от предыдущего snapshot не должен выглядеть current до истечения TTL. Legacy keys `organization + source_key`, goods list/meta и 24-hour report payload freshness этого не обеспечивают.

### 8.2 Deduplication

- Run dedupe: account + source + semantic version + request context + checksum.
- Price row dedupe: snapshot + external product ID + explicit grain key (`product:<nmId>` или доказанный `offer:<externalOfferKey>`).
- Stock row dedupe: snapshot + stock scope + product + optional proven offer + source warehouse key.
- Event/history dedupe: source-native immutable ID, иначе deterministic fingerprint всех identity/business fields; seller article не входит как единственная identity.
- Conflicting duplicates внутри response не выбираются «последней строкой»: run становится partial/blocked и сохраняет diagnostics.
- Пагинация публикуется атомарно только после terminal page/completeness validation.

### 8.3 Необходимые constraints и indexes (логически, без DDL)

Constraints:

- composite FK `(organization_id, marketplace_account_id)` к `marketplace_accounts` и соответствующие RLS policies;
- WB account marketplace discriminator;
- non-empty external product/grain/source keys;
- unique sync-run identity и snapshot checksum в account/source/request context;
- unique row membership по keys выше;
- money integer in kopecks, currency explicit, non-negative для catalog price facts;
- percent в `[0, 100]`;
- stock quantities integers; negative допустимы только если конкретный source contract это документирует, иначе validation error;
- derived SPP operands из одного account, grain, buyer context и совместимого observation window;
- daily business date соответствует выбранному source snapshot;
- `complete` snapshot не может иметь unresolved page/cursor/identity errors.

Indexes:

- latest complete snapshot: `(org, account, source, semantic_version, completed_at desc)`;
- price current/history: `(org, account, external_product_id, grain_key, observed_at desc)`;
- stock current: `(org, account, stock_scope, external_product_id, offer_key, warehouse_key, observed_at desc)`;
- stock daily/history: `(org, account, business_date_msk, external_product_id, offer_key, warehouse_key)`;
- sync diagnostics/checksum and source-native identity lookup;
- catalog joins по existing account-scoped product/offer composite keys.

## 9. Consumer contract

### 9.1 Repricer

Repricer получает backend row с раздельными:

- seller list price;
- seller discounted/current price;
- buyer-no-wallet direct value и source state;
- SPP derived value и operands/provenance;
- Club/wallet direct/derived values;
- current stock aggregate, stock scope, coverage и snapshot ID;
- period demand/SPP metrics под отдельными names;
- `asOf`, `sourceObservedAt`, `freshness`, `blockerIds`.

Price draft/apply обязан использовать только current confirmed same-context price/SPP и current complete stock. Period SPP может участвовать в аналитике с явной маркировкой, но не в mutation guard. Existing `repricer_sprint_b` уже умеет блокировать missing SPP/stock, однако upstream `_economics_from_row` заменяет missing stock на `1`; этот default должен исчезнуть при cutover. Strategy-specific `_stock_units` fallbacks также не должны попадать в mutation input.

Price history — последовательность фактических snapshots/observations, а не только changelog изменений, сделанных Vella. Changelog остаётся audit trail действий и detected changes.

### 9.2 Reports

- Stock report использует current snapshot для колонки «сейчас» и actual daily rows для historical/OOS.
- Period ABC/WoW price — либо period realized price из order/finance facts, либо явно current context; эти значения нельзя выдавать друг за друга.
- Stock valuation возвращается backend с valuation basis (`seller_current`, `buyer_current`, `cogs_as_of`) и обеими revisions.
- `daysToOos`/warehouse decisions — derived metrics с выбранным demand period, coverage и rule version.
- Report response cache хранит source revisions, не только `completedAt` payload.
- HTTP read path читает cache/canonical DB. Live WB refresh остаётся отдельной background job.

### 9.3 Frontend

Frontend только форматирует backend values/states. Из production UI следует убрать как authoritative logic:

- derivation SPP из seller/buyer;
- buyer price через `seller × (1-SPP)`;
- wallet composition;
- P_min/P_max conversion between before/after SPP;
- margin preview и hardcoded commission/logistics defaults;
- `stockRub = stock × currentPrice` без valuation basis;
- `daysToOos` и missing-data substitutions.

Client-side optimistic preview допустим только как явно non-authoritative draft, если тот же backend endpoint возвращает окончательный результат перед сохранением/apply. Для первого slice проще не переносить формулы: использовать существующие backend projections.

## 10. Найденные противоречия и дефекты контракта

| ID | Противоречие | Evidence | Решение |
|---|---|---|---|
| P1 | Docs/discovery называют Club SPP, runtime/tests запрещают это | source registry/open questions/`repricer_sources.py` vs `_resolve_spp_analytics`/`test_wb_price_units.py` | Club отделить; WB-06 снова blocked до buyer contract |
| P2 | Внешний 41-SPP объявлен live buyer price без контекста | `fetch_external_spp_prices` | Candidate source; не current canonical до contract evidence |
| P3 | Period SPP влияет на current planned margin | `_build_sku_row.planning_spp_pct` | Отдельная period analytic; current/mutation не fallback |
| P4 | Test требует period SPP как current, код выдаёт current SPP `null` | `test_build_sku_row_uses_orders_spp...` | Исправить contract/test в future slice, не возвращать запрещённый fallback |
| P5 | WB Club/wallet composition различается frontend/backend | `liveParityData`, drawer calculator, `_buyer_price_for_accounting` | Одна backend formula/version или direct price |
| P6 | Goods и SPP enrichment уничтожают все sizes кроме первого | `_apply_external_spp_prices_to_goods`, `_merge_good_spp_fields`, `list_repricer_skus` | Сохранять raw grain; product-level fallback явно |
| P7 | Content `sizes[].skus` объявляются `chrtIds` без доказательства | `list_repricer_skus` | Unresolved identifier до mapping evidence |
| P8 | Money unit определяется величиной | `wb_api/price_units.py` | Source/version-specific unit normalization |
| P9 | Goods publish неатомарен, SPP failure не делает run partial | `refresh_wb_data_sources`, `save_goods_page` | Terminal complete snapshot before publish |
| P10 | Legacy data org-scoped, canonical account-scoped | cache ORM/store, `/api/v2/wb/products` | Mandatory marketplace account in fact/cache keys |
| S1 | Detailed stock немедленно схлопывается по nmId | `fetch_stock_aggregates` | Persist detailed snapshot, aggregate only in read model |
| S2 | Два stock sources смешиваются через `max`/subtraction | `_merge_stock_product_totals` | Хранить source semantics отдельно; product metric only QA |
| S3 | Один payload маркируется одновременно как detailed current и async remains | `_build_stock_source_bundle` | Не создавать evidence/grain, которого source не дал |
| S4 | Async in-way целиком назначается первому warehouse | `_warehouse_remains_to_stock_rows` | Separate special bucket; no fabricated warehouse attribution |
| S5 | Partial prefix после 429 остаётся usable | detailed stock loader + source readiness | Partial attempt не публикуется current |
| S6 | Missing nmId в непустом cache становится stock=0/ok | `_build_sku_row.has_stock_data` | Per-identity presence/coverage state |
| S7 | Manual XLSX/simulator перезаписывают WB `stocks` | WB repricer router imports | Separate manual source/fact namespace |
| S8 | Daily history заполняет прошлые дни текущим stock | `reports_history.py` | Только actual captured day; missing stays missing |
| S9 | History key теряет org/account/warehouse identity и перезаписывает warehouses | `reports_history.py` | Canonical composite identity and DB history |
| S10 | Unknown availability превращается в available или false | WoW builder/frontend types | Nullable daily states + real coverage |
| S11 | Current stock используется с любым report period | cached reports snapshot | Separate current context and daily period history |
| C1 | Source freshness обновляется во время read | `wb23_runtime.build_price_metrics_snapshot_from_row` | Persist actual observation timestamps |
| C2 | Repricer defaults missing stock to `1`, manual stock or baskets estimate | `repricer_execution.py` | Missing remains blocked |
| C3 | Report/sku read paths местами выполняют live WB calls | report source bundle, SKU timeseries | Cache-only HTTP; refresh background only |
| C4 | Frontend владеет price/stock/margin formulas | `liveParityData.ts`, `VellaHtmlParityPage.tsx` | Backend computed fields + revisions |
| C5 | Product docs утверждают «не берёт цифры из воздуха» | docs vs defaults/backfills выше | Обновить docs после canonical cutover, не маскировать uncertainty |
| C6 | Canonical branch и local main разошлись; main удалил конфликтный price test, но сохранил planning behavior | local branch diff | Re-audit after integration before implementation |

## 11. Минимальная migration/shadow sequence

Ниже — последовательность будущего implementation slice; в этом discovery DDL и код не создавались.

1. **Закрепить contracts.** Зафиксировать price field meanings/units, buyer provider context, stock source semantics, TTL и stable offer/warehouse mappings. Пока два hard gates не закрыты, auto-apply остаётся blocked.
2. **Добавить canonical storage по существующему pattern.** Price/stock sync runs, immutable rows, run membership/current selection и true daily stock rows; account FKs/RLS обязательны. Не создавать общий ingestion framework.
3. **Shadow normalize existing sync output.** Legacy adapters продолжают кормить текущих consumers, а те же raw responses параллельно нормализуются в canonical rows до публикации legacy cache. Сравниваются request IDs, row counts, identity coverage, checksums, units и aggregates.
4. **Не делать synthetic backfill.** Импортировать только raw snapshots/events с доказанными timestamps и source identity. Changelog можно сохранить как audit events, но не превращать в полную price history. Fabricated stock days не переносить.
5. **Добавить cache-only canonical reads.** Account-scoped current price/stock projections и daily history behind existing backend DTOs; cache keys включают snapshot revisions. Legacy endpoints продолжают работать.
6. **Canary одного WB account.** Shadow compare legacy/canonical UI rows; price mutations читают canonical inputs, но остаются dry-run/blocked при любой buyer/offer/stock ambiguity. Проверяется отсутствие live calls в HTTP reads.
7. **Переключить backend consumers.** Сначала reports/diagnostics, затем repricer list/guard, затем mutation input. Frontend получает server-computed fields и перестаёт считать цены/stock metrics.
8. **Удалить legacy только после canary и rollback window.** Остановить legacy writes, проверить отсутствие readers, сохранить immutable audit, затем удалить/очистить перечисленные ниже caches. Не удалять их сразу после dual-write.

Canary считается пройденным только если:

- каждая строка сопоставлена в рамках одного marketplace account;
- product/offer grain совпадает либо явно blocked, без silent fan-out;
- seller/buyer/Club values и units совпадают с raw evidence;
- current projection всегда указывает на полный snapshot;
- partial/error attempt оставляет last-good только stale;
- actual stock aggregates равны сумме совместимых detailed rows;
- daily coverage соответствует реально захваченным дням;
- missing buyer/SPP/stock блокирует apply;
- frontend не изменяет backend price/stock facts;
- rollback возвращает legacy readers без потери canonical history.

## 12. Legacy caches: удалять только после canary

| Legacy state | Когда можно удалить/перестать писать |
|---|---|
| `wb_repricer_goods_cache` и Redis `vella:repricer:goods-list:*`, `goods-meta:*` | После перехода catalog/repricer price readers на account-scoped canonical catalog + price projection |
| Process `CATALOG_GOODS_CACHE` | После отсутствия live goods reads в request path |
| `wb_repricer_source_cache` row `stocks` | После перехода repricer/reports/guards на canonical current stock |
| `stocks_excel` и manual stock внутри `stocks` | После отдельного manual-stock import contract; не мигрировать как WB fact |
| `wb_stock_current`, `wb_stock_remains_async` legacy payload rows | После раздельного canonical ingestion и source-grain parity |
| `seller_stock_current*`, `stock_product_metrics`, `stock_size_office_metrics` mutable JSON | После соответствующих source-specific canonical snapshots либо решения оставить их response caches с snapshot revision |
| Process-memory stock history в `reports_history.py` | После `wb_stock_daily` и consumer cutover; fabricated rows не переносить |
| `sku_list_snapshot_*` price/stock projections | После account/revision-aware repricer list cache |
| `reports_payload_*`, `reports_digest_*`, latest aliases | Старые версии — после новых account/source-revision cache keys и report canary; сам response-cache pattern может остаться |
| `wb_repricer_changelog` как источник price timeseries | Перестать использовать как source history после canonical price history; таблицу можно оставить как audit log |

`content_cards`, sync status/history и unrelated finance/ads caches не удаляются этим slice автоматически. Их удаление относится к владельцам catalog/operations соответствующих доменов.

## 13. Boundary будущего slice

### In scope

- account-scoped canonical current seller price snapshots;
- buyer-no-wallet source contract, provenance и current SPP derivation;
- явное разделение Club/wallet и SPP;
- сохранение фактического product/offer grain без first-size collapse;
- detailed current WB stock snapshots и source-specific seller/async facts;
- true Moscow daily stock capture без backfill;
- freshness/partial/error/current selection;
- cache-only backend projections для repricer, reports и `/api/v2` catalog reads;
- shadow dual-write/parity, one-account canary и legacy reader cutover;
- блокировка mutations при missing/stale/ambiguous price/SPP/stock;
- удаление frontend-owned authoritative calculations из price/stock paths.

### Out of scope

- изменение WB price upload/task lifecycle и включение production mutations;
- новые repricer strategies, promo rules, liquidation formulas или auto-actions;
- KTR/localization/warehouse replenishment decision rules (WB-01/WB-17);
- finance/economics redesign и historical realized-price backfill;
- frontend redesign, multi-account selector UX и новые таблицы;
- synthetic reconstruction of historical prices/stocks;
- reserve field до решения WB-21;
- перенос manual XLSX stock в WB canonical facts;
- live WB semantic verification в рамках этого read-only discovery.

### Hard start gates

1. Подписанный source contract для buyer price without wallet: meaning, unit, wallet inclusion, buyer context, account/region dependence, source time и failure semantics.
2. Доказанный mapping WB size identifiers к `MarketplaceOffer.external_offer_key`; до этого size rows остаются unresolved или product-level там, где source действительно product-level.
3. Явная связь используемого WB credential с одним `MarketplaceAccount`.

Если gate 1 или 2 не закрыт, slice всё равно может безопасно доставить seller-price snapshots и product-level stock facts, но не может разблокировать current SPP-dependent repricing.

## 14. Проверка существующими тестами

Запущен минимальный read-only набор через локальный dev virtualenv:

```text
pytest -q \
  tests/test_wb_price_units.py \
  tests/test_wb_repricer_bff.py::test_build_sku_row_uses_orders_spp_when_live_buyer_price_is_missing \
  tests/test_reports_sources_runtime.py::test_stock_report_wb_warehouses_keeps_rows_when_next_page_is_rate_limited \
  tests/test_wb_reports_bff.py::test_week_over_week_row_exposes_stock_history_coverage_and_null_unavailable_values
```

Результат: `10 passed, 2 failed`.

- Price failure подтверждает contract drift: test ожидает period orders SPP в current `analytics.sppPct`, runtime оставляет current SPP `null`. Canonical решение — сохранить `null/blocked`, а не восстановить запрещённый fallback.
- Stock failure относится к retry count (`[0, 1000, 1000, 1000, 1000]` вместо `[0, 1000]`); adapter при этом сохраняет 1000 partial rows после 429. Для canonical current важен вывод: такие строки принадлежат partial attempt и не должны публиковаться как полный snapshot.

Первый запуск системным Python остановился на отсутствующем пакете `redis`; повторный запуск использовал только локальный dev virtualenv, не live/prod environment.

## 15. Inspected files

Обязательные документы прочитаны полностью; код и тесты прослежены по source-to-consumer paths и targeted branch diff.

Root/SATORNA paths ниже указаны от workspace root, backend paths — от task worktree, frontend paths — от корня репозитория `frontend`.

### Root/SATORNA

- ` SYSTEM_PROMPT.md`
- `MAIN_GOAL.md`
- `SATORNA_ARCHITECTURE_HANDOFF.md`
- `SATORNA_SPEC_AUDIT.md`
- `SATORNA_DELEGATION_PROMPTS/README.md`
- `SATORNA_DELEGATION_PROMPTS/06_wb_prices_stocks_discovery.md`
- `.worktrees/frontend-wb-abc-production/docs/superpowers/specs/2026-08-26-satorna-platform-rebuild-architecture-design.md`
- `.worktrees/frontend-wb-abc-production/docs/superpowers/plans/2026-08-28-satorna-slice-1-canonical-costs.md`
- `.worktrees/backend-wb-prices-stocks-discovery/docs/superpowers/plans/2026-09-01-satorna-period-finance-slice.md`

### Backend project/canonical platform

- `README.md`
- `app/platform/integrations/orm.py`
- `app/platform/catalog/orm.py`
- `app/platform/catalog/schemas.py`
- `app/platform/catalog/service.py`
- `app/platform/economics/backfill.py`
- `app/platform/finance/orm.py`
- `app/platform/period.py`
- `app/routers/catalog_v2.py`
- `alembic/versions/20260604_0008_wb_repricer_goods_cache.py`
- `alembic/versions/20260604_0009_wb_repricer_source_cache.py`
- `alembic/versions/20260810_0024_source_cache_metadata.py`
- `alembic/versions/20260901_0046_catalog_costs.py`
- `alembic/versions/20260901_0047_period_finance.py`

### Backend adapters, caches, tasks and consumers

- `app/wb_api/client.py`
- `app/wb_api/price_units.py`
- `app/wb_api/reports_sources_runtime.py`
- `app/discovery/repricer_probes.py`
- `app/discovery/repricer_sources.py`
- `app/repricer_sync.py`
- `app/repricer_bff.py`
- `app/repricer_execution.py`
- `app/repricer_sprint_b.py`
- `app/wb23_runtime.py`
- `app/repricer_cache/orm.py`
- `app/repricer_cache/store.py`
- `app/repricer_persistence/orm.py`
- `app/repricer_nomenclature_excel.py`
- `app/reports_history.py`
- `app/wb_reports_sprint_d.py`
- `app/wb_sync_plan.py`
- `app/repricer_tasks.py`
- `app/infra/celery_app.py`
- `app/routers/wb_repricer_bff.py`
- `app/routers/wb_reports_bff.py`
- `app/cabinet/orm.py`
- `app/cabinet/store.py`

### Backend tests

- `tests/test_wb_price_units.py`
- `tests/test_wb_repricer_bff.py`
- `tests/test_wb_adapter_probes.py`
- `tests/test_reports_sources_runtime.py`
- `tests/test_wb_reports_bff.py`
- `tests/test_stock_report_cache_persistence.py`
- `tests/test_repricer_cache_store.py`
- `tests/test_repricer_tasks.py`
- `tests/test_wb_sync_plan.py`
- `tests/test_repricer_execution.py`
- `tests/test_sprint_b_workflow.py`
- `tests/test_sprint_d_reports.py`
- `tests/test_wb_real_client.py`
- `tests/test_wb_rate_limiter.py`

### Product contracts/handoffs

- `product-docs/AGENTS.md`
- `product-docs/wb-repricer-data-sources.md`
- `product-docs/docs/wb-reports-data-contract-2026-05-08.md`
- `product-docs/docs/handoffs/wb-backend-source-registry.md`
- `product-docs/docs/handoffs/wb-backend-reuse-dependency-map.md`
- `product-docs/docs/open-questions-current.md`
- `product-docs/docs/constraints.md`
- `product-docs/docs/specs/indeepa-wb-replacement/00-master-prd.md`
- `product-docs/docs/specs/indeepa-wb-replacement/01-repricer-core-prd.md`
- `product-docs/docs/specs/indeepa-wb-replacement/04-price-input-safety-prd.md`

### Frontend consumers

- `frontend/AGENTS.md`
- `frontend/CLAUDE.md`
- `frontend/README.md`
- `frontend/src/features/wb-repricer/liveParityData.ts`
- `frontend/src/features/wb-repricer/liveParityData.test.ts`
- `frontend/src/features/wb-repricer/schemas.ts`
- `frontend/src/features/wb-repricer/WbRepricerSkuPage.tsx`
- `frontend/src/features/wb-repricer/SkuListPage.tsx`
- `frontend/src/features/vella-parity/VellaHtmlParityPage.tsx`
- `frontend/src/features/wb-reports/types.ts`
- `frontend/src/features/wb-reports/schemas.ts`
- `frontend/src/features/wb-reports/repository.ts`
- `frontend/src/features/wb-reports/reportContracts.ts`
- `frontend/src/features/wb-reports/api.ts`
- `frontend/src/features/wb-reports/WbReportsPage.tsx`
- `frontend/src/features/settings/SettingsPage.tsx`

## 16. Итоговый handoff будущему implementer

Начинать следует не с таблиц и не с замены frontend. Сначала закрываются три hard gates, затем existing WB adapters получают атомарный account-scoped snapshot boundary и shadow writer. Минимальный первый vertical path: один account, product-level seller price + detailed current stock + actual daily capture → cache-only backend read → shadow report/repricer comparison. Buyer/SPP-dependent apply остаётся blocked, пока source semantics и offer mapping не доказаны.
