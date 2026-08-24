# WB Repricer: источники данных и формулы

Документ описывает текущую реализацию страницы `/wb/repricer`: откуда берутся значения в верхних KPI, таблице всех товаров, drawer SKU, акциях, себестоимости, стратегиях и ликвидации.

## Где находится реализация

- Фронтенд: `C:\Users\porka\OneDrive\Рабочий стол\folders\кодерские архивы\ogni-react-frontend\frontend`.
- Основной route: `src/App.tsx`, пути `/wb/repricer`, `/wb/repricer/sku/:articleId`, `/wb/repricer/liquidation`, `/wb/repricer/promos` ведут в `VellaHtmlParityPage`.
- Канонический экран: `public/vella-production.html`.
- Маппинг backend -> UI: `src/features/wb-repricer/liveParityData.ts`, функция `mapLiveRepricerRowToParityProduct`.
- Загрузка списка товаров: `GET /api/v1/wb-repricer/sku?periodDays=...&page=...&pageSize=...`.
- Бэкенд BFF: `app/routers/wb_repricer_bff.py`.
- Основные расчеты SKU: `app/repricer_bff.py`.
- Выполнение стратегий: `app/repricer_execution.py`, `app/repricer_sprint_b.py`, `app/repricer_sprint_c.py`.

Важно: в `public/vella-production.html` есть demo/fallback массив `PRODUCTS`. В рабочем режиме после авторизации фронт заменяет его данными из `/api/v1/wb-repricer/sku`. Если backend/API недоступен, UI может показывать fallback или нейтральные состояния.

## Общий поток данных

1. Пользователь нажимает синхронизацию или планировщик запускает `POST /api/v1/wb-repricer/sync/run`.
2. Бэкенд обновляет кэши:
   - `goods`: каталог и цены WB;
   - `content_cards`: карточки контента WB;
   - `promotions`: акции WB;
   - `stocks`: остатки WB;
   - `period_stats_{N}`: заказы/продажи WB Statistics за выбранный период;
   - `finance_{N}`: финансовый отчет WB Finance за выбранный период;
   - `baskets_{N}`: корзины из WB Analytics sales funnel.
3. `GET /api/v1/wb-repricer/sku` берет эти кэши, собирает строки SKU и возвращает `items`, `summary`, `cache`.
4. Фронт маппит каждую строку `LiveRepricerSkuRow` в объект `PRODUCTS` и рендерит таблицу/drawer.

## Верхние KPI страницы `/wb/repricer`

Фронт берет `summary` из `/api/v1/wb-repricer/sku`. Если `summary` пустой, считает fallback по загруженным `PRODUCTS`.

| KPI в UI | API поле | Источник | Формула |
|---|---|---|---|
| Выручка за период | `summary.revenueKopecks` | `finance_{periodDays}` или `period_stats_{periodDays}` | Сумма `analytics.sellerRevenueKopecks` / `analytics.revenueKopecks`: база продавца `retailPriceWithDisc * quantity` из WB Finance. Для старого кэша fallback = `sellerDiscountedPriceKopecks * salesUnits`. `buyerRevenueKopecks` хранится отдельно как `retailAmount`. |
| Средняя маржа % | `summary.avgMarginPct` | finance/period + расчет SKU | Если есть выручка: `marginKopecks / revenueKopecks * 100`. Иначе среднее по доступным `analytics.marginPct`. |
| Маржа ₽ | `summary.marginKopecks` | finance или расчет unit margin | Если есть `analytics.netProfitKopecks`, берется он. Иначе `analytics.marginKopecks * ordersUnits`. |
| Продажи по себестоимости | `summary.cogsKopecks` | Excel/настройки себестоимости + finance/period sales | `settings.cogsKopecks * salesUnits`. |
| Расходы ₽ | `summary.expensesKopecks` | finance + ads + настройки расходов | `commission + logistics + storage + acceptance + penalty + deduction + acquiring + ads + otherExpenses - additionalPayment`. `penalty` и `deduction` сохраняют знак WB: отрицательные компенсации уменьшают расходы. Налог хранится отдельно и не входит в расходы/маржу репрайсера. |
| Реклама ₽ | `summary.adSpendKopecks` | `ads_{periodDays}` | Сумма расходов WB Ads fullstats за выбранный период. |
| Заказы, шт | `summary.ordersUnits` | `period_stats_{periodDays}` | Количество неотмененных заказов из `/api/v1/supplier/orders`, отфильтрованных по `date` внутри периода. Отмены по `isCancel/cancelDate` не входят в KPI и отдельно доступны в `summary.cancelledOrdersUnits`. Дедуп: `srid`, затем `odid/rid`; `orderUid/gNumber` используются только в композитном ключе с `nmId`, размером/баркодом, датой и ценой. |
| Продажи, шт | `summary.salesUnits` | `finance_{periodDays}` или `period_stats_{periodDays}` | Количество продаж gross из finance detailed; возвраты показываются отдельно. |
| Возвраты, шт | `summary.returnsUnits` | `finance_{periodDays}` или `period_stats_{periodDays}` | Количество возвратов из finance detailed / supplier sales. |
| Цен изменено за период | `/api/v1/wb-repricer/changelog?from=...` -> `total` | журнал репрайсера | Количество записей changelog за период. |
| Корзины за период | `summary.totalBaskets` | `baskets_{periodDays}` | Сумма `analytics.baskets`; если его нет, fallback `meta.basketsLast7d`. |
| SKU в продаже | `summary.inSale` | `stocks` | Количество SKU, где `analytics.wbStockUnits > 0` и статус не `liquidation`. |
| % участия в акциях | `summary.promoSharePct` | `promotions` + Excel пороги | `SKU с analytics.promotionStatus == "yes" / все строки * 100`. |

Если в UI видно `—` или подпись вида `нет period stats / finance`, значит не было свежего `period_stats_{N}` и/или `finance_{N}`. Тогда фронт не показывает выдуманную выручку/маржу, либо использует fallback только когда есть достаточно строковых данных.

## Таблица всех товаров

| Колонка UI | Frontend product поле | Backend поле | Источник | Формула / логика |
|---|---|---|---|---|
| Фото / артикул | `sku`, `name`, `t` | `meta.articleId`, `meta.name`, `meta.subject` | WB goods + content cards | Артикул = `vendorCode` из goods. Название/предмет/бренд дополняются из content cards. Тип картинки выводится по первым буквам артикула. |
| WB-арт. | `nmId` | `meta.nmId` | WB goods `nmID` | Ссылка на `wildberries.ru/catalog/{nmId}/detail.aspx`. |
| Статус товара | `status` | `meta.status`, `analytics.marginPct`, корзины | настройки SKU + расчеты | `liquidation -> illiquid`, `manual -> manual`, `warmup -> new`; иначе фронт показывает `illiquid`, если `marginPct < 10` или корзины ниже нормы, иначе `loko`. |
| ABC | `abcCode` | `analytics.abcCode` | finance | Две буквы: первая по рангу продаж/заказов/выручки, вторая по `netProfitKopecks`. Пороги ранга: A до 20%, B до 50%, C остальные. |
| Акция | `promoActive`, `promoState` | `analytics.promotionStatus`, `promotionStatusText` | WB promotions + promotion Excel | `yes`, если SKU/nmId найден в активных акциях или загруженных порогах акции. |
| Ответственный | `managerId`, `managerName` | `meta.managerId`, `meta.managerName`, `assignmentSource` | локальное состояние репрайсера / назначения | Меняется через `PATCH /api/v1/wb-repricer/sku/{articleId}/manager`, причина обязательна. |
| Цена до СПП | `price` | `meta.currentPriceKopecks` | WB goods или локальный override | Берется `discountedPrice`, если есть, иначе `price`. Если включен preserve local override и есть `SKU_META_OVERRIDES.currentPriceKopecks`, показывается override. |
| Средняя с СПП | `avgPriceSpp` | `analytics.buyerPriceNoWalletKopecks` / `avgPriceWithSppKopecks` / `accountedBuyerPriceKopecks` | WB goods, period stats, finance | При `spp_plus_wallet` берется `accountedBuyerPriceKopecks`; иначе buyer price без кошелька или средняя цена из period stats. |
| % СПП | `spp` | `analytics.sppPct` | `supplier.orders.spp`, finance spp или live buyer price | Приоритет: `period_stats.sppPct`, затем `finance.sppPct`, затем расчет `(sellerDiscounted - buyerPriceNoWallet) / sellerDiscounted * 100`. |
| Маржа | `mg`, `mgRub` | `analytics.marginPct`, `analytics.marginKopecks` | настройки себестоимости + комиссии + логистика | Unit margin = `sellerDiscountedPrice - sellerDiscountedPrice * commissionPct - sellerDiscountedPrice * acquiringPct - deliveryToClient * buyoutPct - deliveryFromClient * buyoutPct - otherExpenses - cogs`. Margin % в backend = `unitNet / sellerDiscountedPrice * 100`. |
| Комиссия | `commissionPct`, `commissionRub` | `analytics.commissionDisplayPct`, `commissionKopecks` | тарифы WB + acquiring + finance | Базовая комиссия берется из тарифов по subject, fallback из настроек; effective = `baseCommissionPct + acquiringPct`. `commissionRub` из finance, если доступен. |
| Корректировки WB | `penaltyChargedKopecks`, `penaltyReturnedKopecks`, `deductionChargedKopecks`, `deductionCompensationKopecks`, `additionalPaymentKopecks` | Finance detailed `penalty`, `deduction`, `additionalPayment`, `sellerOperName`, `bonusTypeName`, `rrdId` | `penaltyKopecks` и `deductionKopecks` — net-суммы со знаком. Отдельно доступны начисленные штрафы, возвраты штрафов, начисленные удержания, компенсации удержаний и доплаты WB. |
| Корзины | `bsk` | `analytics.baskets` | `baskets_{periodDays}` | `cartCount` из `/api/analytics/v3/sales-funnel/products`; если кэш не загружен, `no_data`, в demo fallback `meta.basketsLast7d`. |
| Заказы | `ordersPeriod` | `analytics.ordersUnits` | `period_stats_{periodDays}` | Количество неотмененных заказов из `/api/v1/supplier/orders` по полю `date` внутри выбранного периода. `lastChangeDate` используется только как запасной вариант, если `date` отсутствует; отмены доступны отдельным полем `cancelledOrdersUnits`. |
| Выкуп | `buyout` | `analytics.buyoutPct` | `period_stats_{periodDays}` / baskets analytics | В period stats: `salesUnits / ordersUnits * 100`. В baskets analytics может прийти `buyoutPercent`. |
| Остаток WB | `stock` | `analytics.wbStockUnits` | `stocks` | Сумма `quantity` по складам из `/api/analytics/v1/stocks-report/wb-warehouses`. |
| Стратегия | `tpl`, `strategyName` | `strategy.id`, `strategy.name`, `strategy.assignmentSource` | локальные назначения + вывод по статусу | В таблице показывается только явное назначение `manual`/`xlsx`; derived strategy скрывается как `— нет —`. |
| Комментарий | comment fields | `commentSummary`, `comments` | локальное состояние/audit | В list view комментарии не грузятся полностью; drawer/settings возвращают подробнее. |

## Drawer SKU

Drawer открывается кликом по названию товара. Базовые значения берутся из того же объекта `PRODUCTS`, который пришел из `/api/v1/wb-repricer/sku`. Дополнительно React-доработка загружает:

- `GET /api/v1/wb-repricer/sku/{articleId}/changelog?limit=12` для истории;
- `GET /api/v1/wb-repricer/sku/{articleId}/pricing-status` для статуса стратегии/этапа;
- `GET /api/v1/wb-repricer/sku/{articleId}/timeseries?days=30` для дневных рядов спроса/цены/остатков.

| Блок drawer | Поля | Источник / формула |
|---|---|---|
| Заголовок | `name`, `sku`, `size/subject`, `nmId`, `brand`, `abcCode`, `manager` | Те же `meta.*`, `analytics.abcCode`, `managerId/managerName`. |
| Текущая цена | `dPrice`, `dPriceHint` | `price` и `prevPrice`. Hint = разница текущей и предыдущей цены, если отличается. |
| P_min / P_max | `pmin`, `pmax`, `rrp` | `settings.pMinKopecks`, `settings.pMaxKopecks`, `settings.rrpKopecks`; если P_min не задан, считается формулой ниже. |
| Цена после СПП | `priceAfterSpp`, `avgPriceSpp`, `spp` | `price * (1 - spp/100)` и backend buyer price / avg price. |
| Себестоимость | `cogs` | `settings.cogsKopecks`: из Excel импорта, ручных настроек или default по типу товара. |
| Маржа %/₽ | `mg`, `mgRub` | `analytics.marginPct`, `analytics.marginKopecks`; если `financeState == no_data`, UI показывает `нет данных` для маржи и затрат. |
| Комиссия | `commissionPct`, `commissionRub` | `analytics.commissionDisplayPct` и `commissionKopecks`; fallback = `price * commissionPct / 100`. |
| Логистика/хранение | `logistics`, `storagePerSku` | finance detailed, либо настройки логистики; без finance может быть `нет данных`. |
| Налоги | `taxes` | `analytics.taxPct`, `analytics.taxKopecks`, default `6%`; backend отдает налог отдельным справочным полем, но не включает его в `expensesKopecks`, `netProfitKopecks`, unit margin и planned margin. |
| Спрос | `bsk`, `ordersPeriod`, `views7d`, `cr`, `buyout` | Корзины/заказы/выкуп из backend. Просмотры/CR в текущем маппинге live данных равны `null`, если нет timeseries/отчетного источника. |
| Реклама | `adSpend7d`, `drr`, `adRoi` | `analytics.adSpendKopecks` из WB Ads fullstats за период. `drr`/`adRoi` могут оставаться пустыми, если нет дневного ряда или базы для расчета. |
| Запас | `stock`, `stockRub`, `daysToOos` | `stock` из WB stocks; `stockRub = stock * currentPrice`; `daysToOos = stock / max(1, ordersPeriod / 7)`. |
| Подробный расчет | price slider | Фронтовый preview: `priceWithSpp - cogs - commission - 53 - adPerSale - storage`; это UI-калькулятор, не финальный backend P&L. |
| Анализ маржи при акции | discount input | Фронтовый preview: `actionPrice = price * (1 - discount/100)`, `marginRub = actionPrice - cogs - 15% commission - 53 - storage`. |

## Основные формулы экономики

### P_min

Backend `app/repricer_bff.py`:

```text
P_min = (cogsKopecks + logisticsKopecks) / (1 - wbCommissionPct/100 - minMarginPct/100)
```

Если знаменатель `<= 0`, возвращается очень большое значение, чтобы цена не прошла guard. Если у SKU задан `settings.pMinKopecks`, он имеет приоритет.

### Unit margin

```text
unitNet = sellerDiscountedPriceKopecks
          - sellerDiscountedPriceKopecks * categoryCommissionPct/100
          - sellerDiscountedPriceKopecks * acquiringPct/100
          - deliveryToClientKopecks * buyoutPct
          - deliveryFromClientKopecks * buyoutPct
          - otherExpenses
          - taxes
          - cogsKopecks

marginKopecks = round(unitNet)
marginPct = unitNet / sellerDiscountedPriceKopecks * 100
```

`effectiveCommissionPct = categoryCommissionPct + acquiringPct`. `acquiringPct` по умолчанию из algorithm settings = `2.71`. `otherExpensePricePct` по умолчанию `5%` от цены, `taxPct` по умолчанию `6%` от seller revenue.

### Finance net profit

Если есть `finance_{periodDays}`:

```text
sellerRevenue = retailPriceWithDisc * quantity for sales - returns
buyerRevenue = retailAmount for sales - returns

commissionExpense = sellerRevenue * commissionPercent
                    или sellerRevenue * categoryCommissionPct

netProfit = sellerRevenue
            - commission
            - logistics
            - storage
            - acceptance
            - penalty
            - deduction
            - acquiring
            - ads
            - otherExpenses
            - taxes
            - cogs * gross salesUnits
```

Это значение идет в `analytics.netProfitKopecks` и в KPI `Маржа ₽`.

### Выручка

Приоритет:

1. `finance.sellerRevenueKopecks` / `retailPriceWithDisc * quantity`;
2. `period_stats.revenueKopecks`;
3. fallback KPI для старого finance-кэша: `sellerDiscountedPriceKopecks * salesUnits`.

`analytics.buyerRevenueKopecks` отдельно показывает `retailAmount`, то есть сумму покупателя после WB-скидок/СПП. `analytics.platformDiscountKopecks` показывает разницу между seller- и buyer-базой.

### СПП

Приоритет:

1. `period_stats.sppPct` из `supplier.orders.spp`;
2. `finance.sppPct` из finance detailed;
3. расчет live: `(sellerDiscountedPrice - buyerPriceNoWallet) / sellerDiscountedPrice * 100`.

Если режим `sppAccountingMode = spp_plus_wallet`, для расчета цены покупателя дополнительно учитывается `wbWalletType` как процент кошелька WB.

## Себестоимость

Импорт: `POST /api/v1/wb-repricer/imports/costs-excel`.

Парсер `app/wb_import_excel.py` ищет колонки:

- `nm_id`: `nmid`, `артикулмп`, `артикулмпnmid`, `supsku`;
- `vendor_code`: `артпоставщика`, `артикулпоставщика`, `supplierarticle`, `vendorcode`, `артикулпродавца`;
- `cost`: `себестоимость`, `costprice`;
- опционально `p_min`, `p_max`, `stock_total`, `brand`, `subject`.

При импорте backend сопоставляет строку по `vendorCode` или `nmId`, обновляет настройки SKU:

- `cogsKopecks`;
- `pMinKopecks`;
- `pMaxKopecks`;
- историю импорта `excel_imports`;
- audit event `Импорт себестоимости`.

Если себестоимость не импортирована, используются defaults по типу артикула:

- `F`: cogs 450 ₽, logistics 50 ₽, min margin 15%, pMax 1900 ₽;
- `H`: cogs 850 ₽, logistics 55 ₽, min margin 15%, pMax 3200 ₽;
- `L`: cogs 440 ₽, logistics 41 ₽, min margin 15%, pMax 2400 ₽.

## Акции WB

Список акций:

- `GET /api/v1/wb-repricer/promotions`;
- backend: `list_promotions`;
- источники: WB promotions calendar/details/nomenclatures + локальный cache `promotions`.

Поля акции:

- `status`: `active`, если текущая дата между start/end; `upcoming`, если старт в будущем; `ended`, если конец прошел;
- `eligibleSkuCount`: всего подходящих SKU;
- `participatingSkuCount`: участвуют;
- `participationPct = participating / eligible * 100`;
- `excelLoaded/excelStatus`: наличие XLSX-порогов;
- `thresholdNmIds`: nmId, для которых известен порог входа.

Excel акции:

- upload: `POST /api/v1/wb-repricer/promotions/{promoId}/upload-excel` или bulk `/promotions/upload-excel`;
- парсер ищет `nmId` и `threshold_price`;
- сохраняет `promoThresholdKopecks`, `promoThresholdDiscountPct`, `currentPriceKopecks`, `wbStatus`.

Защита акции по SKU:

```text
promo P_min = settings.pMinKopecks
           или P_min(cogs, commission, logistics, promoMarginThresholdPct)

isProtected = promoThresholdKopecks >= promo P_min
```

`promoMarginThresholdPct` по умолчанию `10`.

## Стратегии

Фронтовый каталог стратегий (`GET /api/v1/wb-repricer/strategies/catalog`) синхронизирован с Excel-файлом `Конструктор_кастомных_стратегий_WB_1.xlsx`.

Канонические id:

- `stockout_guard` / Защита out of stock;
- `turnover_control` / Контроль оборачиваемости;
- `plan_fact_daily` / План-факт стандартный;
- `plan_fact_period` / План-факт на период;
- `plan_fact_group` / План-факт на период групповой, пока blocker `group_scope_required`;
- `plan_fact_interval` / План-факт интервальный, пока blocker `hourly_sales_required`;
- `cross_marketplace` / Кроссмаркетплейс, пока blocker `ozon_mapping_required`;
- `illiquid` / Неликвид;
- `optimal_price` / Оптимальная цена;
- `baskets_orders` / Динамика корзин и заказов;
- `metric_dynamics` / Поддержание динамики показателя;
- `schedule` / Расписание, пока blocker `schedule_rules_required`;
- `bundles` / Комплекты, пока blocker `bundle_components_required`.

Старые имена `aggr`, `cons`, `warm`, `cust`, `liq` оставлены как алиасы для обратной совместимости и мапятся на новые стратегии.

Назначение стратегии:

- bulk endpoint: `POST /api/v1/wb-repricer/strategy-assignments/bulk`;
- сохраняется в `FRONTEND_STRATEGY_ASSIGNMENTS`;
- если стратегия не назначена явно, backend выводит derived strategy по статусу/корзинам, но таблица ее не показывает как активную.

### Стратегия 4599: корзины + заказы

Сигналы:

```text
basketsTrend = up, если baskets >= basketNorm, иначе down
ordersTrend = up, если ordersUnits >= round(basketNorm * 0.6), иначе down
```

Матрица шага:

| baskets | orders | raw delta |
|---|---|---:|
| up | up | +3% |
| up | down | -1% |
| down | up | +1% |
| down | down | -3% |

Затем delta ограничивается `capPct`, default 3%.

```text
recommendedPrice = currentPrice * (1 + deltaPct/100)
```

### Стратегия 4600: динамика выручки

Revenue index:

```text
если есть revenue, basePrice, orders:
  revenueIndex = revenue / (basePrice * orders) * 100
иначе:
  revenueIndex = baskets / basketNorm * 100
```

Диапазоны:

| revenueIndex | delta | floor |
|---|---:|---:|
| < 75% | -5% | 30 ₽ |
| 75-85% | -4% | 20 ₽ |
| 85-95% | -3% | 10 ₽ |
| 95-105% | 0% | 0 |
| 105-115% | +3% | 10 ₽ |
| 115-125% | +4% | 20 ₽ |
| >=125% | +5% | 30 ₽ |

`recommended = current + max(abs(current * delta%), floor)`.

### Дополнительные Excel-стратегии

- `turnover_control`: считает дни до OOS как `stockUnits / (ordersUnits / 7)` и применяет Excel-диапазоны 0-3 `+25%`, 3-5 `+20%`, 5-7 `+15%`, 30-60 `-15%`, 60-90 `-20%`, >90 `-25%`.
- `stockout_guard`: повышает цену, если дней до OOS меньше 7.
- `plan_fact_daily` / `plan_fact_period`: применяют Excel-таблицу выполнения плана; при 0-10% ставят `minPrice`, при 100-110% держат текущую цену, при >140% дают `+10%`.
- `optimal_price`: сравнивает скорость заказов с базой спроса и двигает цену на `+3%`, `0%` или `-3%`.

### Guards перед применением цены

Цена не применяется, если срабатывает blocker:

- нет готовности discovery WB-22/WB-23;
- source snapshot stale/blocked;
- нет СПП, себестоимости, комиссии, логистики, выкупа или остатка;
- остаток `<= 0`;
- активная акция без min price;
- candidate ниже `minPrice`;
- прогнозная маржа отрицательная;
- candidate не проходит P_min/P_max;
- изменение за один шаг больше `priceStepPct` по умолчанию 6%;
- изменение за 24 часа больше `maxPriceChangeDailyPct` по умолчанию 20%;
- margin preview blocked.

## Ликвидация

Endpoint:

- `GET /api/v1/wb-repricer/liquidation`;
- `POST /api/v1/wb-repricer/liquidation/start`;
- `POST /api/v1/wb-repricer/liquidation/{articleId}/stop`;
- `POST /api/v1/wb-repricer/liquidation/{articleId}/confirm-negative`.

Кандидат попадает в `Неликвид`, если:

```text
low_baskets = basketsLast7d < basketNorm * 0.25
или
low_orders = ordersUnits <= 1
или
negative_margin = marginPct < 0
```

Причина:

- `negative_margin`, если маржа ниже 0;
- `zero_orders`, если заказов нет;
- `low_baskets`, если корзины ниже 25% нормы;
- `weak_orders`, если заказов 1;
- иначе `slow_stock`.

Рекомендованная цена кандидата:

```text
если ordersUnits == 0: currentPrice * (1 - stepPct/100), но не ниже P_min(..., 0% margin)
если ordersUnits == 1: currentPrice
если ordersUnits > 1: currentPrice * (1 + stepPct/100)
```

Старт ликвидации:

```text
strategyId = illiquid
targetPrice = P_min(..., 0% margin)
stepPct = liquidationStepPct, default 3
nextStepAt = now + 24 hours после первого решения
requiresNegativeMarginConfirm = targetPrice < обычный P_min с minMarginPct
```

Дальше execution делает дневной шаг, только когда наступил `nextStepAt`:

```text
0 заказов -> снижение на stepPct
1 заказ -> удержание цены
>1 заказа -> повышение на stepPct
nextStepAt = now + 24 hours
```

Если нужна отрицательная маржа, подтверждение действует 24 часа и снимает `requiresNegativeMarginConfirm`.

## Статусы источников

В каждой SKU строке есть статусы:

- `stockState`: `ok`, `fallback`, `no_data`;
- `periodStatsState`: `ok`, `fallback`, `no_data`;
- `basketsState`: `ok`, `fallback`, `no_data`;
- `financeState`: `ok`, `fallback`, `no_data`;
- `sppState`: `ok`, `fallback`, `no_data`, `no_buyer_price`.

Для клиента это удобно объяснять так:

- `ok`: данные пришли из WB/cache за выбранный период;
- `fallback`: использованы demo/default/локальные значения;
- `no_data`: источник не загружен или WB не вернул данные;
- `no_buyer_price`: нет цены покупателя для расчета СПП.

## Короткая версия для заказчика

Репрайсер не берет цифры “из воздуха”: список и цены идут из WB goods, карточки из WB content, корзины из WB Analytics sales funnel, заказы/выручка/выкуп из WB Statistics orders/sales, финансовые расходы из WB Finance detailed report, остатки из WB stocks report, акции из WB promotions и XLSX-порогов, себестоимость из Excel или настроек по типу товара. Все ключевые расчеты проходят через P_min/P_max и price guards перед применением цены.
