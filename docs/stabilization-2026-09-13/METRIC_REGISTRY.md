# Реестр метрик и проверка источников — 13–14 сентября 2026

Исходный анализ: `9f163989f14fd283af38711e2acded8880731533`. Описанные локальные исправления DATA-3 и пустого content cache зафиксированы в `e207b6d`; frontend-подписи и чтение нового контракта опубликованы из `16232ed`. Backend production остаётся `80c65b0`. Это проверка происхождения и отдельных контрольных расчётов, не приёмка чистой прибыли или всей CRM. Финансовый эталон пользователя ещё не получен.

Покрытие: все 13 KPI и 20 колонок «Все товары», метрики API статистики репрайсера, финансовые поля canonical P&L/ABC и их отображение/экспорт. Другие отчёты WB, все drawer-вкладки, графики и экспорт настроек не прошли полную поэлементную инвентаризацию в этом ограниченном пакете; DATA-1 для всего WB-контура остаётся открытой.

## Источники, период, права и полнота

### Живой источник WB — дополнительная проверка 14 сентября

В 00:27–00:30 МСК read-only просмотрена уже авторизованная пользовательская вкладка Safari [«Доходы и расходы»](https://seller.wildberries.ru/income-analytics/revenues-and-expenses). Страница Beta, режим «Продвинутый», период 06.09–12.09.2026; подпись обновления — 13.09.2026 13:20. Пользовательская сессия сохранена, изменений и выгрузок с созданием задач не выполнялось.

Фактически заполнены выкупы (продажи минус возвраты, ₽/шт), доставка, хранение, приёмка, штрафы, комиссия WB и эквайринг, удержания. Детализация отдельно показывает комиссию/эквайринг, прямую/обратную доставку и продвижение внутри удержаний. Поля лояльности, доплат, компенсаций потерь/подмен/дефектов и изменения срока перечисления доступны, в просмотренном периоде нулевые. **Расходы вне WB — «Не указано»**: нулевые внешние расходы из этого не следуют.

Тем самым существование и заполненность предложенного источника подтверждены. Его API-контракт, полнота по всем периодам и сверка CRM с этим экраном на одном фильтре/периоде пока не подтверждены. Он не заменяет отсутствующий эталон чистой прибыли. Бизнес-суммы в переносимый реестр не включены.

В следующих таблицах код источника включает период, права, свежесть и ограничения из этой таблицы. Все суммы `*Kopecks` — целые копейки RUB; UI обычно округляет до целого рубля. Наличие суммы в API само по себе не означает её финансовую полноту.

| Код | Источник и используемые поля | Период / свежесть / полнота / права |
|---|---|---|
| G | Кэш каталога `wb_repricer_goods_cache`: nmID, vendorCode, sizes.price/discountedPrice; content_cards, promotions, stocks | Это текущие снимки, не исторические остатки/цены за выбранный период. `cache.latestFetchedAt = max(fetched_at)` страниц **каталога**, а не время обновления всех данных. У остальных источников отдельные `*FetchedAt`. Пустой timestamp — неизвестно. Репрайсер требует активную CRM-сессию и использует organization_id; отдельного `finance:read` в SKU endpoint нет. |
| F | `fetch_finance_report_aggregates` → Finance detailed → агрегаты SKU/дней; `retailAmount`, docTypeName, quantity, forPay, deliveryService, paidStorage, paidAcceptance, penalty, deduction, acquiringFee, additionalPayment, paymentSchedule, cashback* | Выбранные включительные даты 1–90 дней. День из saleDt, затем rrDate/date, приводится к Europe/Moscow; endpoint запроса получает даты. Совместимый кэш обязан иметь `revenueBasis=retailAmount`, `financeSchemaVersion=v4`. `cache.financeFetchedAt` относится к выбранному кэшу периода; если он отсутствует, поле null. `financeState=ok` означает наличие агрегата, а не полноту затрат. Права как G. |
| O | WB orders / sales statistics, источник `period_stats`; ordersUnits, cancelledOrdersUnits, salesUnits, returnsUnits | Оперативные заказы не тождественны финансовым продажам. `periodStatsFetchedAt`, `periodStatsState`; в legacy преобразованиях часть отсутствующих значений становится 0. |
| B | WB Sales Funnel, `baskets`: cartCount, orderCount, orderSum, buyoutPct; previous | Выбранный и предыдущий периоды; `basketsFetchedAt`, `basketsState`, requested/matched nmIds. Число совпавших SKU не доказывает отсутствие пропусков по дням. |
| A | WB Ads fullstats: sum/spend, views, clicks, atbs, orders, sum_price; финансовые удержания «WB Продвижение» | Период задаётся отдельно. `adsFetchedAt`, adsDateFrom/To, adsLastStatus/Error; отсутствие/429 не равно нулевой рекламе. Расход для прибыли приоритетно берётся из Finance promotion, иначе из fullstats; показатели показов/кликов остаются fullstats. |
| S | Сохранённые SKU/algorithm settings, шаблон, назначение менеджера/стратегии; costs Excel | Текущие настройки, в legacy не исторический cost ledger. Применяются и к прошлому периоду. Дефолт типа товара или алгоритма не является подтверждённой себестоимостью/налогом. Чтение в репрайсере как G; права изменения этим пакетом не затрагиваются. |
| H | История изменения цен CRM | Счётчик загружается отдельно от финансового payload, период истории должен совпадать. Нет основания называть его показателем WB или выводить из различия текущей/базовой цены. |
| C | Canonical FinanceService, WbAbcPnlService, CostsService, EconomicsService, AdvertisingService | `Period`: включительные даты Europe/Moscow; UTC-интервал `[00:00 MSK dateFrom, 00:00 MSK dateTo+1)`. API сообщает period, snapshot, formulaVersion, revisions, blockers. Сегодня — partial, будущее — future; время ответа не время исходных данных. `finance:read` + организация + WB marketplace account + активный membership/account scope. |

Код: [legacy источники](../../backend/app/repricer_bff.py), [SKU endpoint и summary](../../backend/app/routers/wb_repricer_bff.py), [метаданные кэша](../../backend/app/repricer_cache/store.py), [Period](../../backend/app/platform/period.py), [canonical доступ](../../backend/app/platform/finance/access.py).

В legacy SKU endpoint есть различие путей доступа: построение строк вызывает `_request_wb_token`, готовый snapshot читается после `_hydrate_org_repricer_state` без этого вызова. Это существующее поведение, которое требует отдельной проверки REL-3; пакет DATA не меняет ни права, ни токены.

## «Все товары»: KPI

`R`, `Brev`, `Cogs`, `E`, `W`, `T`, `M` ниже — суммы в копейках, до отображения. Для текущего Finance v4 `revenueKopecks`, `sellerRevenueKopecks` и `buyerRevenueKopecks` имеют одну исходную базу: продажи минус возвраты `retailAmount`. Устаревшее имя sellerRevenue не делает её выручкой до СПП. Цена продавца до СПП — отдельное поле каталога.

Таблица описывает backend-поля, включая прежние названия карточек. В опубликованном UI «Средняя маржа» переименована в «Маржа / выручка, %»: отношение считается из общих raw сумм, в том числе при отрицательной выручке; нулевой/неизвестный знаменатель даёт «—». Явные null не подменяются суммами текущей страницы. При старом backend фильтр сопровождается подписью, что summary относится к каталогу; filtered summary принимается только при `cache.summaryScope=filtered_skus`.

| Карточка | Поле / расчёт | Источник, единица, отсутствие |
|---|---|---|
| Выручка за период | `summary.revenueKopecks = Σ analytics.revenueKopecks`; `retailAmount` продаж минус возвратов | F, ₽. Не сумма заказов, не выплата WB. При отсутствующем Finance legacy summary возвращает 0; это известная проблема полноты. |
| Средняя маржа % | `summary.avgMarginPct = 100*M/R`, если R>0; иначе среднее доступных row.marginPct или 0 | F+S, %. В основном пути это отношение итогов, не среднее по товарам в продаже; запасной путь меняет определение. |
| Маржа ₽ | `summary.marginKopecks`: Σ fact `netProfitKopecks`; если null, `plannedPeriodMarginKopecks`, затем unit margin × orders; далее коррекция общих остатков расходов | F+A+S, ₽. Может смешивать факт и план. Не финальная чистая прибыль. |
| Продажи по себестоимости | `summary.cogsKopecks = Σ cogsTotalKopecks`; обычно settings.cogsKopecks × (salesUnits−returnsUnits) | F+S, ₽. Возвраты уменьшают COGS; отсутствующая историческая ставка не доказана текущим дефолтом. |
| Расходы ₽ | `summary.expensesKopecks = E`, состав ниже | F+A, ₽. Налог показан вне E; workReturn вне E; прочие расходы legacy факта сейчас 0. |
| Реклама ₽ | `summary.adSpendKopecks`; raw Finance promotion при наличии authoritative totals, иначе ads cache | F/A, ₽. `adSpendSource` различает два источника. Итог может включать нераспределённую по SKU рекламу. |
| Заказы, шт | `summary.ordersUnits`; SKU: B.orderCount, затем O.ordersUnits, затем финансовая оценка sales+returns; источник `ordersSource` | B/O/F, шт. Финансовая оценка в row builder не совпадает с упрощённым source-summary builder, где последнего fallback нет. |
| Продажи, шт | `summary.salesUnits = ΣsalesUnits−ΣreturnsUnits` | F, шт **за вычетом возвратов**. Табличное raw analytics.salesUnits — валовые продажи; название без уточнения двусмысленно. |
| Возвраты, шт | `summary.returnsUnits = ΣreturnsUnits` | F, шт. Положительный счётчик; его уже вычли из предыдущего KPI. |
| Цен изменено за период | `window.__vellaProductsPriceChanges`, отдельно загруженная история | H, число SKU/событий согласно ответу истории; не часть финансового payload. Точный grain отдельного счётчика не подтверждён этим пакетом. |
| Корзины за период | `summary.totalBaskets = Σ analytics.baskets`, fallback meta.basketsLast7d | B, добавления, не уникальные покупатели. На пропусках legacy fallback требует аудита. |
| Товаров в продаже | `summary.inSale`: stock>0 и status != liquidation | G, число SKU на момент snapshot. Проверки «активная цена>0» здесь нет, несмотря на прежний tooltip. |
| % участия в акциях | `100 × promoCount / skuCount`, округление до целого | G, %. Для source summary знаменатель — текущий каталог, historicalOnly исключены; при фильтре — весь фильтрованный набор. |

Связь отображения: [liveParityData](../../frontend/src/features/wb-repricer/liveParityData.ts), функции `mapLiveRepricerRowToParityProduct`; [parity UI](../../frontend/src/features/vella-parity/VellaHtmlParityPage.tsx), `computeProductsKpiSnapshot`, `ProductsKpiStripIsland`. HTML-снимок содержит старые подписи; используемая React island имеет собственные подписи.

### Точный состав legacy результата

```text
netProfitKopecks = profitRevenue + workReturn − cogsTotal − expenses − tax
profitRevenue = buyerRevenue, с legacy fallback на sellerRevenue
workReturn = settings.workReturnPerSaleKopecks × (salesUnits − returnsUnits)
tax = round(sellerRevenue × settings.taxPct / 100)
expenses = commission + logistics + storage + acceptance
         + signed(penalty) + signed(deduction) + loyaltyCost + acquiring
         + adSpend + otherExpenses − additionalPayment
additionalPayment = −paymentSchedule −rawAdditionalPayment
loyaltyCost = cashbackAmount + cashbackCommissionChange
otherExpenses = 0 в текущем фактическом legacy расчёте
```

`tax` — расчёт из настроек CRM, не полученная от WB сумма налога и не утверждённый налоговый учёт. Плановая unit margin дополнительно использует настройки логистики, выкупа, расходов и выбранный режим СПП/кошелька; это другой расчёт. Диагностика `_margin_breakdown_from_rows` ограничивается `limit`, сообщает truncation, поэтому её ограниченный итог нельзя сравнивать со всем summary без проверки покрытия.

Комиссия F: при полном payable-покрытии = buyerRevenue−payable−acquiring; иначе reported ppvzSalesCommission, затем процентный fallback. Прибыль не вычитает одновременно payable и комиссию. Удержание с bonusTypeName «WB Продвижение» переносится из deduction в adSpend, чтобы не вычесть его дважды.

В legacy `_allocate_global_finance_costs` уже распределяет строки без nmId по положительной retail-выручке SKU; если все веса нулевые — поровну, остаток копеек распределяется детерминированно. Это существующая политика, не утверждённая заново этим аудитом. Фильтр сохраняет уже находящиеся в строках расходы; новое исправление только прекращает добавление к выборке остатка всего кабинета.

### DATA-2: разница 118 771 ₽

Независимо пересчитано: `25 935 626 − 7 426 500 − 11 079 007 = 7 430 119`; минус показанные `7 311 348` = `118 771 ₽`.

Видимая формула неполна: не содержит workReturn и tax, а при неполном Finance возможен плановый fallback. Если все строки фактические и источники согласованы, на точных копейках:

```text
R − Cogs − E − M = R − Brev − W + T
при текущей одинаковой retailAmount-базе R=Brev: разница = T − W
```

Это условная алгебра кода, **не объяснение конкретных 118 771 ₽**. Совместного сохранённого payload этого скриншота среди проверенных output-артефактов не найдено. Нельзя объявить разницу налогом, СПП или возвратами. Округление четырёх итогов до рублей само по себе даёт не более 2 ₽ разницы и такую сумму не объясняет.

Для завершения нужны из одного ответа только summary с buyer/seller revenue, workReturn, tax, cogs, expenses, margin, unassigned components, cache.dateFrom/To, source timestamps, filters, page/total и доля fact/planned строк. Полные бизнес-строки, авторизация и секреты в переносимый отчёт не нужны.

## «Все товары»: все колонки

| Column key | Значение и происхождение | Единица / отсутствие |
|---|---|---|
| select | Локальный выбор строки, не метрика | boolean |
| sku | G.meta.articleId/name/photoUrl, vendorCode | Строка/изображение; отсутствующее имя не должно становиться финансовой идентичностью |
| nmId | G.meta.nmId | Идентификатор WB, не число для суммирования |
| status | S.meta.status + unit margin/baskets heuristic | Категория управления. Нет подтверждения WB-статуса «локомотив». |
| abc | analytics.abcCode; mapper fallback `CC` | Класс; fallback CC не доказывает рассчитанный ABC. Canonical прибыльный класс ещё null. |
| promo | G.analytics.promotionStatus/name/id | yes/no/label; текущая акция, не финансовая история |
| manager | S.meta.managerId/name | Назначение CRM, без назначения — соответствующая подпись |
| price | G.meta.currentPriceKopecks / 100 | ₽, цена продавца до СПП; может иметь сохранённый local_override |
| avgPriceSpp | B.orderSum / orderCount, `analytics.avgPriceWithSppKopecks` | ₽/заказ. Историческая средняя в колонке «С СПП», не обязательно текущая buyerPriceNoWallet. При отсутствии null. |
| priceWithWallet | G.accountedBuyerPrice либо buyerPriceWithWallet | ₽. Учётный режим S может показывать цену без кошелька; не смешивать с финансовой средней. Null при отсутствии цены. |
| spp | `1−buyerPriceNoWallet/currentPrice`; direct spp при наличии | %, текущая наблюдаемая скидка. Не финансовая скидка за период. Null без buyer price. |
| mg | analytics.marginPct + marginKopecks | % и ₽/единицу, **план** из цены и S, не M/выручка за период. Значение может быть доступно без Finance. |
| commissionPct | analytics.commissionDisplayPct при commissionState=ok | %, тариф категории + acquiring. Backend fallback из Finance frontend скрывает; null, не 0. Не равна effective commission ₽. |
| bsk | B.analytics.baskets | Добавления за выбранный период; mapper хранит 0 при no_data и отдельный state. |
| ordersPeriod | B/O/F.analytics.ordersUnits при periodStatsState != no_data | шт за выбранный период; fallback происхождение в ordersSource. Mapper может скрыть доступные B/F orders при no_data O. |
| buyout | analytics.buyoutPct из B/O | %. Backend использует 90% при отсутствии исходной доли даже без demo; это предположение, не измерение. |
| stock | G.analytics.wbStockUnits | шт сейчас. Состояние no_data хранится отдельно; mapper присваивает 0, поэтому один числовой field недостаточен. |
| tpl | S.strategy/template assignment | Управляющая настройка, не измерение |
| actions | Действия интерфейса | Не метрика |
| comment | S.commentSummary/comments | Пользовательский текст, не измерение |

Дополнительные product-поля: `revenue7d`, `adSpend7d`, `orders7d` фактически несут **выбранный период**, несмотря на имя; `netSku` предпочитает факт, затем план. `views`, `views7d`, `cr`, `drr`, `adRoi` mapper явно оставляет null. `daysToOos` использует делитель 7 независимо от выбранного periodDays; это неподтверждённая эвристика. `stockRub=stock×currentPrice` — стоимость остатка в текущих ценах продажи, не COGS.

## Статистика репрайсера и реклама

`_repricer_stats_metrics`, `_repricer_stats_summary`: таблица ниже описывает каждое возвращаемое числовое поле. Источники и permissions G/F/O/B/A/S наследуются из первого раздела.

| Поле | Формула / единица / отсутствие |
|---|---|
| impressions, clicks, adCartAdds, adOrders, adRevenueKopecks | A: показы, клики, рекламные корзины, заказы, рекламная выручка ₽; при adDataAvailable=false null в строке |
| ctrPct / summary.adCtrPct | 100×clicks/impressions, %, null при нулевом/отсутствующем знаменателе |
| baskets, orders | B/O/F: добавления и заказы, шт; baskets summary=null, если хотя бы одна строка неизвестна |
| cartToOrderCrPct | 100×orders/baskets, %, null при нулевом/отсутствующем знаменателе |
| revenueKopecks, netProfitKopecks | F/S, ₽; тот же legacy факт/расчёт, не canonical чистая прибыль |
| marginPct | Плановая unit margin из S, %, не отношение двух предыдущих сумм |
| adSpendKopecks | F/A расходы рекламы, ₽ |
| drrPct | 100×adSpend/revenue, %; выручка F, не рекламные заказы |
| stockUnits, currentPriceKopecks, avgPriceWithSppKopecks | Остаток сейчас, текущая цена продавца, средняя цена заказа; шт / ₽ / ₽ |
| medianPriceKopecks | analytics.medianPrice либо avgPriceWithSpp либо currentPrice; без отдельного source поле **не доказывает медиану** |
| sppPct, commissionPct | Скидка текущей цены и тариф/комиссия; % |
| skuCount | Число строк всего фильтрованного набора, до pagination |
| canRecalculate, priceBlocked | Число SKU по decision.id и priceProtection.status; не число успешных отправок цен |
| sourceReady, sourcePartial, sourceBlocked | Число SKU по источникам; ready — проверка enum states, не независимая проверка свежести |

В отличие от baskets, summary статистики суммирует отсутствующие ad impressions/clicks/spend через `_int_or_zero`; нулевая сумма не доказывает полную рекламу. При доступном A без F основной SKU builder может оставить рекламные суммы null. Эти проблемы не исправлялись DATA-3.

## Canonical Finance / P&L / ABC

Код: [FinanceService](../../backend/app/platform/finance/service.py), [WbAbcPnlService](../../backend/app/modules/wb_reports/abc_pnl.py), [полный API-контракт](../../backend/app/modules/wb_reports/schemas.py), [frontend adapters](../../frontend/src/features/wb-finance/canonicalAbcPnl.ts). Все строки ниже наследуют C: period, snapshot/checksum, revisions, blockers, finance/account permissions. Суммы — копейки API, рубли в UI/экспорте.

| Поля API / смысл | Источник и формула | Отсутствие / ограничение |
|---|---|---|
| operationCount, skuCount | Количество операций snapshot; число nmId-групп | Это разные grain; расходы без SKU не увеличивают skuCount |
| revenueKopecks, salesRevenueKopecks, returnsRevenueKopecks | retailAmount; sale положительно, return отрицательно; returnsRevenue возвращается положительной величиной | Отсутствующий retailAmount в sale/return отклоняется, не превращается в 0 |
| mainRevenueKopecks, redemptionsRevenueKopecks, lateCorrectionRevenueKopecks, unknownRevenueKopecks | Категории отчёта/корректировок source | Проверять конкретный reportType и ingestion window; не считать все категории автоматически независимыми |
| salesUnits, returnsUnits, netUnits | quantity sale, quantity return, разность | quantity не revenue×quantity: retailAmount уже сумма строки |
| payableKopecks (Finance fact) | forPay / ppvz_for_pay со знаком документа | Null блокирует settlement profit для payable-based v3; не является выручкой |
| commissionKopecks | В payable-проекции revenue−payable−acquiring; fallback reported commission | Effective сумма удержаний WB, не только опубликованный тариф процента |
| logisticsKopecks | deliveryService / delivery_service / deliveryRub | Отсутствующий необязательный raw field сейчас 0 |
| storageKopecks | paidStorage / storageFee | Аналогично; отдельные raw exports нужны для полноты |
| acceptanceKopecks | paidAcceptance / acceptance | Аналогично |
| penaltyKopecks, deductionKopecks | max(0, signed raw amount); Finance promotion исключается из deduction | Отрицательная часть идёт в compensation; реклама не вычитается второй раз |
| additionalPaymentKopecks, financeOtherExpensesKopecks | adjustment=−paymentSchedule−additionalPayment; expense=max(0,−adjustment) | Знак определяется source, не названием «доплата» |
| compensationKopecks | max(0,adjustment)+max(0,−penalty)+max(0,−deduction) | Вычитается из расходов |
| acquiringKopecks | acquiringFee со знаком документа | Не вычитать повторно из уже net payable |
| financeExpensesKopecks | commission+logistics+storage+acceptance+penalty+deduction+financeOther+acquiring−compensation | Не включает COGS, economics tax/other, рекламу, лояльность |
| cogsKopecks; costValueState, costEvidenceStatus | Датированный CostsService по SKU и дневным units; configured/assumed/missing | При отсутствии mapping/cost — null и blocker; недатированный/assumed cost не принят автоматически |
| settlementProfitKopecks | revenue−cogs−financeExpenses | Null при missing COGS/payable; промежуточный результат |
| taxKopecks; economicsValueState/evidence | Revenue basis × taxBasisPoints / 10 000 по effective policy groups | Null при missing policy; округление ties-to-even, это правило кода, не налоговая консультация |
| otherExpensesKopecks | Revenue × otherBasisPoints / 10 000 + policy perSale × sales basis | Датированная EconomicsService; не чтение раздела WB «Доходы и расходы» |
| profitBeforeAdsAndLoyaltyKopecks | settlementProfit−tax−otherExpenses | Null, если любой вход неизвестен |
| advertisingSpendKopecks | Finance promotion при подтверждённом source, иначе canonical Ads | Null при неполноте; измеренный 0 сохраняется |
| unattributedAdvertisingSpendKopecks | Сумма рекламы, не связанной с nmId | Summary-only; не распределяется произвольно по строкам |
| profitBeforeLoyaltyKopecks | profitBeforeAdsAndLoyalty−advertisingSpend | Summary учитывает общий spend, row profit может быть null при нераспределённой рекламе |
| cashbackAmountKopecks, cashbackDiscountKopecks, cashbackCommissionChangeKopecks | Одноимённые финансовые поля | Null, если loyalty source не подтверждён |
| loyaltyNetCostKopecks | Для payable v3: cashbackAmount+cashbackCommissionChange; legacy basis дополнительно −cashbackDiscount | В payable compensation уже учтена: повторное прибавление даёт двойной учёт |
| profitAfterLoyaltyKopecks | profitBeforeLoyalty−loyaltyNetCost | Предварительная прибыль после перечисленных компонентов, не final netProfit |
| salesClass | Сортировка revenue DESC, netUnits DESC, nmId; A — первые 20% **SKU по рангу**, B — следующие 30%, C — остальные | Не пороги кумулятивной доли выручки; одинаковые классы на разных страницах |
| profitClass, abcCode, netProfitKopecks | Контракт намеренно возвращает null | Финальная чистая прибыль и прибыльный ABC не приняты до эталона |
| blockerIds, meta.state | Полнота исходников, mapping/evidence и финальной классификации | Населённый P&L остаётся partial при нерешённых блокировках; ready HTTP-ответ не означает ready finance |

P&L-таблица выводит identity/category, revenue, cogs, commission, logistics, storage, adSpend, tax, profitAfterLoyalty, margin, status, comment. Category отсутствует в canonical adapter; marginPct и overheadKopecks намеренно null. «Хранение/штрафы» в flow = storage+penalty+deduction, а не все WB-расходы. В нём не показаны все составляющие окончательной арифметики.

ABC имеет 24 UI-колонки. Canonical adapter заполняет только товар/артикул WB, продажи (netUnits/revenue), расход рекламы, прибыль после лояльности, salesClass и blockers. Статус/правило показывают «нет данных»; акция, менеджер, цена до/с СПП, unit COGS, unit margin, показы, клики/CTR, корзины, конверсия, заказы, логистика, комиссия, хранение, КТР/локализация и остаток не поставляются этим адаптером. Их пустота — отсутствие источника, а не нулевая активность. COGS total доступен в API, но `cogsPerUnitKopecks` для этой колонки не передаётся.

### Пагинация, фильтры, копейки и экспорт

- Legacy SKU: без фильтра summary строится по всем source aggregates, включая historical SKU, и общим остаткам расходов; catalog skuCount считает текущие товары. С фильтром до исправления summary использовал all_items вместо filtered. Локальное исправление суммирует **весь filtered**, затем UI показывает отдельную страницу; `cache.summaryScope=filtered_skus` или `catalog`. Дополнительные общие остатки расходов к фильтру не прибавляются.
- Canonical service вычисляет summary/classes до `rows[offset:offset+limit]`. Frontend `fetchCanonicalAbcPnl` дочитывает страницы; P&L visibleRows — окно отображения после выбора rows. `PnlLiveWorkbenchIsland` суммирует все выбранные rows и возвращает null при хотя бы одном неизвестном слагаемом. Итог аккаунта с нераспределённой рекламой показан отдельно.
- Экспорт P&L использует тот же выбранный набор; `reportTableExport.rubles` сохраняет дробные рубли, null остаётся пустой ячейкой. ABC проверяет соответствие originalIndex/row/identity перед экспортом и не подставляет неподдерживаемые поля. Это проверка кода + ранее сохранённых регрессий; новый browser/XLSX UI-прогон данным исполнителем не проводился.
- Legacy rub parser использует float и Python `round(value*100)`; canonical raw parser — Decimal ROUND_HALF_UP; economics — ties-to-even. UI округляет целые ₽ отдельно. Правила **не едины**; сопоставлять на копейках, отдельно проверять пограничные .005/отрицательные значения. Денежные правила этим пакетом не менялись.

## DATA-3: локальное исправление и свежая проверка

Изменены только [SKU endpoint](../../backend/app/routers/wb_repricer_bff.py) и добавлен [один regression test](../../backend/tests/test_repricer_filtered_summary.py). Ни production, ни WB API, цены, permissions, распределение и финансовые настройки не менялись.

Тест: 26 выбранных SKU на страницах 25+1, исключённый SKU с большой выручкой, общие storage/ads существенно выше выбранных. Поиск, бренд, менеджер, статус, пустой результат. До исправления **5 FAIL**: summary.skuCount=27 при ожидаемых 26 либо 0. После — **5 PASS**; сводка и деньги одинаковы на обеих страницах, общие остатки не приписываются выборке. Дополнительно **128 PASS**: существующие summary/snapshot, canonical ABC/P&L, rollup и полнота загрузки Finance. Использован существующий release-gate environment, изолированный runtime state, in-memory SQLite и запрет исходящих внешних соединений.

Это локальный DATA-3 fix, не закрытие всех пунктов DATA-3. Сохраняются перечисленные legacy неизвестное→0, факт/план, исторические настройки, различия округления и неподтверждённые source-grain/period сопоставления.

Дополнительно подтверждён и устранён независимый cache-miss defect: общий `_list_repricer_skus_from_cached_sources` обращался к `content_cache.get`, хотя `get_source_cache` вправе вернуть None. Единственная защита `or {}` стоит в общем читателе, как у соседних источников; затрагивает list/snapshot, liquidation, nomenclature и work-status при include_content=True. Существующий liquidation/changelog тест: **1 FAIL → PASS**, соседний набор в порядке исходного файла **11 PASS**. Изменения BFF заморожены перед общим backend-прогоном.

Нестандартный порядок pricing-status → work-status отдельно дал 1 FAIL/10 PASS: первый тест оставляет `SKU_META_OVERRIDES` со статусом liquidation. Work-status проходит отдельно и в исходном порядке. Это обнаруженное загрязнение глобального test state, не доказательство регрессии cache guard; полную suite-проверку ведёт отдельный REL-пакет.

## DATA-4: независимый WB-контроль и «Доходы и расходы»

Повторно выполнен сохранённый `verify_recent_finance_xlsx.py` на текущем коде с оригинальными локальными WB XLSX, отдельно 31.08 и 01–06.09. Четыре архива, **39 679 исходных строк**; контроль выручки, payable, effective commission и итоговой выплаты WB дал **0 копеек расхождения** во всех четырёх случаях. SHA256 источников и нулевые разницы сохранены в приватном evidence, без raw строк в этом документе. Скрипт использует исходные поля XLSX и ранее зафиксированные контрольные суммы; API rrdId в XLSX отсутствует и задаётся синтетически только для локального ingestion.

| Период / отчёт | Строки | SHA256 архива | Разницы четырёх сумм, коп. |
|---|---:|---|---|
| 01–06.09.2026, основной | 29 819 | `22e67f50522cef3af3b556b0a7ac226238d198313f61b1218733aaac307bec8e` | 0 / 0 / 0 / 0 |
| 01–06.09.2026, выкупы | 620 | `b19c4073bf794da6591e2682781d3711b0134c982acaa715f9df8971f6858d21` | 0 / 0 / 0 / 0 |
| 31.08.2026, основной | 9 074 | `8c62652e03997c86b5c585be346b90b18921bfc3ee01e23f76f16e7c56ec6352` | 0 / 0 / 0 / 0 |
| 31.08.2026, выкупы | 166 | `b62193966ead26fa2029d0e9995c47647cd602f13042a2b4de262cdace9be89d` | 0 / 0 / 0 / 0 |

Контрольные бизнес-суммы (только агрегаты, без SKU/операций/токенов) находятся в локальном `night-data/source-checks.json`; переносимый реестр их не публикует. Это evidence воспроизводимости, не отдельный источник новых финансовых правил.

Это независимая сверка WB settlement для двух конкретных периодов. Она не доказывает чистую прибыль, полноту расходов вне WB, равенство API-строк XLSX, весь месяц или источник значений на скриншоте DATA-2.

[Указанный пользователем раздел](https://seller.wildberries.ru/income-analytics/revenues-and-expenses) при новом публичном чтении возвращает JavaScript shell. Публичная [инструкция WB для России](https://seller.wildberries.ru/instructions/ru/ru/material/unit-economy-report) и [инструкция «Доходы и расходы» для Беларуси](https://seller.wildberries.ru/instructions/ru/by/material/income-and-expenses-report-by) доступны как страницы справки, но доступный в этом прогоне текст содержит навигацию, без тела статьи. Поэтому прежнее описание ручных расходов из исторического отчёта не выдано за заново проверенную заполненность российского кабинета.

В проверенных backend/app и frontend/src не найдено чтения income-analytics/revenues-and-expenses: текущие расходы поступают из Finance detailed, Ads и EconomicsService. Последующий read-only просмотр авторизованной вкладки подтвердил поля и заполненность одного периода (см. дополнительную проверку выше), но не API, экспорт, историю или отсутствие двойного учёта. Новый логин/SMS не выполнялся. DATA-4 в части единого контрольного периода CRM/WB и DATA-5 остаются открытыми; эталон пользователя не заменён предположениями.
