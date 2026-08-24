# WB Репрайсер — pending decisions

---

## 🔴 gstack Review — 2026-04-27

Полный прогон: `/review` + `/qa` + `/cso` + `/design-review`. Все находки ниже тегированы источником.
Тег в конце каждой строки: `[review]` `[qa]` `[cso]` `[design]`

### БЛОКЕРЫ ДО ПРОДАКШН-ДЕПЛОЯ (не деплоить с реальным бэком пока не закрыты)

- [ ] **MSW в проде — намеренно, до подключения бэкенда** — `main.tsx` запускает MSW в продакшне чтобы демо работало без реального API. Снять DEV-гард (`if (!import.meta.env.DEV)`) когда Филипп поднимет `GET /api/v1/wb-repricer/skus`. До тех пор — оставить как есть. `[cso]` ⏳ ждёт бэкенд
- [ ] **`liquidation` отсутствует в `SkuStatus`** — `schemas.ts:6`. `StatusPill` (`SkuListPage.tsx:144`) и `StatusBadge` (`SkuSettingsCard.tsx:871`) используют `Record<SkuStatus, ...>` без `'liquidation'`. При `status: 'liquidation'` от бэка — runtime crash. Добавить в enum + badge config с красным цветом. `[review]` `[design]`
- [ ] **Нет AbortController в 5 useEffect** — `SkuListPage.tsx:343`, `AlgorithmSettingsPage.tsx:181`, `LiquidationPage.tsx:67`, `PromotionsPage.tsx:77`, `TemplatesPage.tsx:187`. Stale setState после unmount. Скопировать паттерн из `SkuSettingsCard.tsx:33–64`. `[review]`
- [ ] **Unhandled promise rejections** — `PromotionsPage.tsx:91–114` (`openDrawer`, `uploadExcel`), `LiquidationPage.tsx:81–108` (`startLiquidation`, `stopLiquidation`, `confirmNegative`), `TemplatesPage.tsx:203–221` (`saveTemplate`, `applyTemplate`) — все без `try/catch`. Drawer спинит вечно при ошибке. `[review]`
- [ ] **setTimeout без clearTimeout на unmount** — `SkuSettingsCard.tsx:141`, `SkuListPage.tsx:358`, `PromotionsPage.tsx:88`, `LiquidationPage.tsx:78`, `TemplatesPage.tsx:200`. Хранить ref на таймер, чистить при unmount. `[review]`

### БЛОКЕРЫ ДО ДЕМО (не показывать клиенту)

- [ ] **9 из 12 разделов сайдбара не навигируют** — Дашборд, Отчёты, Отзывы WB, Чаты, Объявления, Кошельки, Заказы, КИЗ, Настройки — кликабельны, но ничего не происходит. Нужны либо реальные роуты, либо заглушки "В разработке" вместо немого фейла. `[qa]`
- [ ] **SKU-карточка блокирует навигацию** — после открытия `SkuSettingsCard` клик по любому пункту сайдбара тайм-аутится (5s). Только hard reload спасает. Кнопка "Закрыть" на первой попытке тоже зависает. `[qa]`
- [ ] **DashboardPage: silent error → infinite spinner** — `DashboardPage.tsx:64–65` `.catch(() => setLoading(false))` при ошибке даёт `loading=false, data=null` → условие `loading || !data` вечно истинно → бесконечный спиннер. Нет error state вообще. `[design]`
- [ ] **Pagination overflow** — `SkuListPage.tsx:822–838` рендерит все страницы кнопками: 1500 SKU / PAGE_SIZE=50 = 30 кнопок, переполнение контейнера. Реализовать ellipsis-пагинацию (prev | 1 | … | 14 | 15 | 16 | … | 30 | next). `[review]` `[design]`
- [ ] **Кнопка "Отмена" в модалах** — первая ссылка (`@e798`) на кнопку Cancel стабильно тайм-аутится, работает только вторая (`@e826`). Два overlapping cancel элемента. `[qa]`

### ВЫСОКИЙ ПРИОРИТЕТ

- [ ] **Нет CSP-заголовка** — `vercel.json` не содержит `Content-Security-Policy`, `X-Frame-Options`, `X-Content-Type-Options`. Добавить в `headers` минимум: `default-src 'self'; frame-ancestors 'none'` + `X-Frame-Options: DENY` + `X-Content-Type-Options: nosniff`. `[cso]`
- [ ] **PUT /sku/:id/settings — unsafe cast** — `SkuSettingsCard.tsx:138` `as { meta: typeof meta }` вместо Zod parse. Сделать как GET: `SkuSettingsResponseSchema.parse(json)`. `[review]`
- [ ] **Bulk automation: optimistic update без rollback** — `SkuListPage.tsx:486–507` обновляет state и очищает selection ДО ответа от API, ошибки отдельных PATCH-запросов глотаются. При частичном провале UI говорит "успех", бэк — нет. Трекать per-ID, откатывать при ошибке. `[review]` `[cso]`
- [ ] **`x-scenario` header идёт в реальный API** — `SkuSettingsCard.tsx:40,131` шлёт `x-scenario: scenario` в каждый GET и PUT. URL param `?scenario=` виден в логах сервера. Убрать из prod-fetch. `[cso]`
- [ ] **AlgorithmSettings без Zod схемы** — `AlgorithmSettingsPage.tsx:6–35` — plain TypeScript interface, нет схемы в `schemas.ts`. MSW handler (`handlers.ts:282–306`) тихо пропускает поля `storageCostPer60Days`, `acquiringPct` и др. Добавить `AlgorithmSettingsSchema` в `schemas.ts` и `.parse()` при загрузке. `[review]`
- [ ] **Bare loading text вместо skeleton** — `SkuListPage.tsx:538–544`, `LiquidationPage.tsx:111`, `PromotionsPage.tsx:181`, `TemplatesPage.tsx:224–228`, `AlgorithmSettingsPage.tsx` (нет loading state вообще). Использовать `SkeletonCard` как в `SkuSettingsCard.tsx:1024`. `[design]`
- [ ] **Индиго вместо `primary` токена** — `AlgorithmSettingsPage.tsx:95,139` (`bg-indigo-500`), `PromotionsPage.tsx:300–308` и `LiquidationPage.tsx:239–256` (таб `border-indigo-500`), `ChangelogPage.tsx:273` (`bg-indigo-600`) — всё заменить на `bg-primary`/`border-primary`. Остальной код использует `primary`. `[design]`
- [ ] **Формула P_min — уточнить с Марией** — `pricing.ts:1–12` не включает хранение 21₽/60дн и эквайринг, но `PENDING.md#1` (handover-документ) говорит, что они входят в формулу. Комментарий в коде `// подтверждено Марией 24.04.2026` противоречит тултипу `SkuSettingsCard.tsx:500`. Нужна явная сверка: либо формула + тултип, либо тултип убрать. `[review]`
- [ ] **Мобайл 375px: сайдбар перекрывает контент** — сайдбар не коллапсируется автоматически при ≤768px. Нужен `md:hidden` toggle или "откройте на ПК" для планшет/мобайл. `[qa]` `[design]`

### СРЕДНИЙ ПРИОРИТЕТ

- [ ] **Терминология: "P_min" видна пользователю** — `SkuListPage.tsx:671` (колонка таблицы "P_min" → "Мин. цена"), `SkuSettingsCard.tsx:386` (сайдбар "P_min" → "Мин. цена (РРЦ)"). Внутренний код оставить, в UI — термин Марии. `[design]`
- [ ] **"warmup" в русском тексте** — `SkuSettingsCard.tsx:394–396` "Не синхронизируется (warmup/карантин)" → "прогрев / карантин". `[design]`
- [ ] **DashboardPage: клик по SKU → весь список** — `DashboardPage.tsx:210` `onNavigate('sku-list')` вместо открытия конкретной карточки по articleId. `[design]`
- [ ] **Toast-шум** — `SkuListPage.tsx:506,521` (тост на каждый toggle автоматики), `TemplatesPage.tsx:212` (тост на save), `LiquidationPage.tsx:88,101,105` (тост на каждое действие). Тосты только для ошибок и bulk-операций. `[design]`
- [ ] **API error messages verbatim в UI** — `SkuSettingsCard.tsx:44–46,1059`, `AlgorithmSettingsPage.tsx:214–215`, `ChangelogPage.tsx:205`. Сырые `err.message` от бэка рендерятся пользователю. Завести whitelist кодов, остальное → "Ошибка соединения". `[cso]`
- [ ] **priceStepPct = 19 можно сохранить** — `AlgorithmSettingsPage.tsx:194–199` блокирует > 19, но не >= 19. WB карантинит при >= 19%/ч. Изменить на `>= 19`. `[review]`
- [ ] **Tablet 768px: колонки таблицы обрезаны** — ЦЕНА/P_MIN/МАРЖА/КОРЗИНЫ/ОСТАТОК не видны, горизонтального скролла нет. `[qa]`
- [ ] **LiquidationPage history tab hardcoded empty** — `LiquidationPage.tsx:449–453` всегда показывает "История пуста" независимо от данных. Нужна реальная рендер-логика `data.history`. `[design]`
- [ ] **ChangelogPage и SkuListPage: error state без retry** — `ChangelogPage.tsx:333–335`, `SkuListPage.tsx:546–548` — bare div без кнопки "Повторить". Использовать `ErrorCard` с retry как в `SkuSettingsCard.tsx:1054`. `[design]`
- [ ] **AlgorithmSettings: дефолты видны до загрузки** — форма рендерится с hardcoded defaults (комиссия 25% и т.д.) пока `useEffect`-fetch не вернётся. Мария может начать редактировать дефолты до того, как реальные значения загрузятся. Блокировать форму или показывать skeleton до загрузки. `[design]`
- [ ] **Zod validation пропущена в большинстве endpoint** — `SkuListPage.tsx:347`, `DashboardPage.tsx:59`, `LiquidationPage.tsx:69`, `TemplatesPage.tsx:190`, `AlgorithmSettingsPage.tsx:184`, `PromotionsPage.tsx:79` — нет `.parse()`. Только `SkuSettingsCard` и `ChangelogPage` делают правильно. `[cso]`
- [ ] **WbPromotion/PromotionSku импортируются из fixture-файла** — `PromotionsPage.tsx:3` `import { type WbPromotion, type PromotionSku } from './promotionsFixtures'`. Перенести типы в `schemas.ts`. `[review]`
- [ ] **Status tab counts не обновляются при поиске** — при фильтре "FBBT" таблица показывает ~6 строк, но таб "Все 1 482" не меняется. `[qa]`
- [ ] **URL никогда не меняется** — нет deep-link поддержки. Закладки/Back/Forward не работают. Нужен React Router с path-based routes. `[qa]`

### НИЗКИЙ ПРИОРИТЕТ

- [ ] **Math.random() в MSW liquidation handler** — `handlers.ts:226`. Non-deterministic фикстура ломает скриншот-тесты. Заменить на детерминированное значение по articleId. `[review]`
- [ ] **priceOverride не сбрасывается при смене articleId** — `SkuSettingsCard.tsx:77`. Latent bug при SPA-навигации без unmount. `[review]`
- [ ] **Дублирование формулы маржи** — `SkuListPage.tsx:209–213`, `SkuListPage.tsx:431–436`, `handlers.ts:128–133` — три копии. Вынести в `pricing.ts` как `computeMarginPct()`. `[review]`
- [ ] **Magic numbers** — `SkuListPage.tsx:92` (200000000, 300000000 — range nmId), `SkuListPage.tsx:111` (0.25 — порог basket), `AlgorithmSettingsPage.tsx:191` (15 — warning threshold). Вынести в named constants. `[review]`
- [ ] **Emoji в TYPE_META** — `TemplatesPage.tsx:21–23` `emoji: '👕'` рендерится в карточках. В остальном коде emoji нет. `[design]`
- [ ] **HTTP security headers** — `vercel.json`: добавить `Referrer-Policy: strict-origin-when-cross-origin`, `Permissions-Policy: geolocation=(), microphone=(), camera=()`. `[cso]`
- [ ] **Нет light/dark theme toggle** — приложение только dark. Луна в хедере открывает "Ночная медиана", не тему. Если single-theme — убрать иконку луны или добавить tooltip. `[qa]`
- [ ] **Liquidation "Завершено": текст вместо процента в колонке Маржа** — FBCT_44, LBCT_05 показывают "завершено" в числовой колонке. `[qa]`
- [ ] **NmId range check некорректен** — `SkuListPage.tsx:92` `nm > 200000000 && nm < 300000000`. Все fixture-nmId (от 185000000) не проходят — всегда SVG placeholder. Убрать range check, оставить только img `onError` fallback (уже реализован на `line 718`). `[review]`

---

*gstack review завершён: 2026-04-27. Источники: /review (code), /qa (browser), /cso (security), /design-review (UI).*
*Исправления: CLAUDE.md — ночная медиана исправлена с `00:00–04:00` на `23:00–04:00` (подтверждено 27.04.2026).*

---

Список вопросов, блокировавших финализацию модуля. В коде пометки вида `// PENDING[#N]` — `grep -rn 'PENDING\[' src/` показывает все точки.

**Обновлено 24.04.2026**: все **10 из 10 pending закрыты** анализом таблиц Марии (`От Марии/*.xlsx`) + транскриптов 10 встреч (`Встречи/*.md`). Сопроводительный документ для Филиппа и клиента: [`docs/wb-repricer-decisions-2026-04-24.md`](../docs/wb-repricer-decisions-2026-04-24.md).

## Статус всех 10 пунктов

| # | Тема | Статус | Ответ |
|---|---|---|---|
| 1 | Формула P_min | ✅ ЗАКРЫТ | Через точку безубыточности на Валовой прибыли после НДС: `Себес + Логистика/выкуп + Комиссия WB + Хранение 21₽/60дн + НДС 20%`, целевая маржа 10%. Источник: `От Марии/ТАБЛИЦА КОМПАС.xlsx` лист `UNIT` |
| 2 | Шаг роста/снижения — ₽ или %, глобально или per-SKU | ✅ ЗАКРЫТ | **%, per-стратегия, с опциональным floor в ₽** («на 0.03, но не менее чем на 10₽»). Источник: `Конструктор_кастомных_стратегий_WB_1.xlsx` листы «Поддержание динамики», «Контроль оборачиваемости» |
| 3 | Период «нет корзин» — 3/7/14 дней | ✅ ЗАКРЫТ | **Per-стратегия**: «Оптимальная цена» = 3 vs 7 дней; «Динамика корзин» = вчера vs 7 дней; «План-факт» = среднее 3 дня (настраивается). Источник: Конструктор стратегий |
| 4 | Формула COGS | ✅ ЗАКРЫТ | **Себес = Сырьё + Зип-пакет + Вкладыш + Работа**. Пример: худи Anomie = 750+8+1+100=859₽. Источник: `UNIT` лист КОМПАС |
| 5 | Источник «корзин» — API endpoint или proxy | ✅ ЗАКРЫТ | **WB Analytics API, отчёт «Воронка продаж»**, поле `addToCart`. Источник: `Встречи/огни-созвон-с-марией-по-отчетам.md` (15:21), `ТЗ/TZ-WB.md:59` |
| 6 | Прогрев 30 дней — от SKU или от данных | ✅ ЗАКРЫТ | **30 календарных дней от появления остатка на складе WB**. Источник: `Встречи/огни-созвон-с-марией-по-отчетам.md` (6:39), `TZ-WB.md:63` |
| 7 | Ночная медиана — global или per-SKU | ✅ ЗАКРЫТ | **Глобально на весь кабинет**, два режима: консервативный (шаг ~5%) и агрессивный (~10%). Источник: `TZ-WB.md:65-71`, `Встречи/огни-созвон-с-марией-по-отчетам.md` (17:26). **Точные проценты** — ждём уточнения у Марии (раздел 1.3 в handover-документе) |
| 8 | P_max — вручную / коэффициент / конкуренты | ✅ ЗАКРЫТ | **% отстройка от базовой цены**, дефолт 5% («не более 5%»). Поле `pMaxAbovePricePct`. Источник: Конструктор стратегий, все 13 листов поле «Можем подняться выше баз. цены? Да, с отстройкой в %» |
| 9 | Порог маржи для акций — дефолт 10% | ✅ ЗАКРЫТ | **Да, 10%**. Источник: `TZ-WB.md:75-77`, `Встречи/briefing-2026-04-15-protocol.md:32`, `Встречи/saas-огни-брифинг-2.md:72` |
| 10 | Один или два порога маржи | ✅ ЗАКРЫТ | **Один общий `min_margin_pct`** (10%). Для ликвидации — временный флаг «разрешить отрицательную маржу», который снимает этот порог для конкретного SKU. Нет отдельного порога «маржа для акций». Источник: `TZ-WB.md:75-78`, `Встречи/saas-огни-брифинг-2.md:73-76` |

## 🆕 Критическая находка — карточка SKU требует полного редизайна

Из `Конструктор_кастомных_стратегий_WB_1.xlsx` стало ясно, что Мария ждёт **13 стратегий** репрайсера вместо одного алгоритма. Каждая — со своей формой настройки:

| # | Стратегия | Тип UI |
|---|---|---|
| 1 | Защита Out of Stock (универсальная) | тумблер + порог дней |
| 2 | Контроль оборачиваемости | Range Table Editor (диапазоны дней → % изменения) |
| 3 | План-факт стандартный | Range Table Editor (выполнение плана % → % цены) |
| 4 | План-факт на период | как #3 + выбор периода |
| 5 | План-факт на период на группу | как #4 + группировка SKU |
| 6 | План-факт интервальный | как #3 + настройка интервалов |
| 7 | Кроссмаркетплейс (Ozon) | select + отступ % от Ozon |
| 8 | Неликвид | пара полей «заказы от / до» |
| 9 | Оптимальная цена | период анализа + период сравнения + % |
| 10 | Динамика корзин и заказов | **Matrix 2×2** (рост корзин × рост заказов) → % |
| 11 | Поддержание динамики показателя | выбор метрики + Range Table Editor с floor в ₽ |
| 12 | Расписание | календарный виджет + правила |
| 13 | Комплекты | выбор артикулов + формула |

**Общие поля у всех стратегий:**
- «Можем подняться выше базовой цены?» + процент (default 5%)
- «Входим в акцию, если она ниже цены по стратегии?»

**План реализации** (отдельный спринт):
1. В карточке SKU добавить поле `strategy: enum` (Select)
2. Рендерить сабформу в зависимости от выбора
3. Для MVP реализовать 3 стратегии (остальные — заглушки «Скоро»): **Защита OOS**, **Контроль оборачиваемости**, **Динамика корзин и заказов**

## 🗺 Карта будущих дашбордов из КОМПАС

31 лист в `ТАБЛИЦА КОМПАС.xlsx` — это готовые шаблоны Марии для Фазы M2 «Отчёты WB». Приоритетные:

| Лист КОМПАС | В какой экран SaaS |
|---|---|
| «мини компас руководителя одежды» | **Главный дашборд Марии** (`/dashboard`) — 2-3 минуты утром |
| «Одежда ВБ Дашборд» | Модульный дашборд WB |
| «ПРОИЗВОДСТВО Дашборд» | Дашборд раздела «Заказы» |
| «Отчёт по уходимости» | `/wb/reports/stocks` (остатки и оборачиваемость) |
| «Планфакт» | `/wb/reports/pnl` |
| «Сводные 2025» | `/wb/reports/digest` |
| «Реестр РК» | `/wb/reports/ads` |
| «РНП» | `/wb/reports/margin` |
| «Выведено из оборота» | `/wb/liquidation` (история) |

Мария уже нарисовала все эти экраны в Excel — в Фазе 2 нам нужно воспроизвести их на React + Tremor.

## Как этим пользоваться дальше

1. **Передать handover-документ Филиппу и клиенту** — [`docs/wb-repricer-decisions-2026-04-24.md`](../docs/wb-repricer-decisions-2026-04-24.md). Там есть чеклисты «что подтвердить» для Марии, Максима, Филиппа.
2. После подтверждения — **убрать pending-маркеры** из кода (`grep -rn 'PENDING\[' src/`), оставив только #7 (ждём точные цифры режимов ночной медианы).
3. **Новый спринт «Карточка SKU 2.0»** — редизайн под Strategy Selector с 13 стратегиями. Приоритет: 3 стратегии для MVP.

## Где дублируется

- `docs/modules/03-wb-repricer.md` — секция **«Pending decisions — КРИТИЧНО»** (обновить по тому же шаблону)
- Memory `project_wb_repricer_pending` — обновить: теперь все закрыты
- `docs/wb-repricer-decisions-2026-04-24.md` — handover-документ для Филиппа и клиента

## 🆕 Ручной ввод нормы корзин (для Филиппа, бэк)

Из обсуждения 24.04.2026: автоматическая норма только по истории SKU закрепляет плохой прошлый результат — если SKU месяц жил без рекламы или с завышенной ценой, низкая норма становится целью для репрайсера (спираль вниз). Плюс новые карточки в прогреве остаются без нормы 30 дней.

**Решение:** норма — из трёх источников в порядке приоритета: `manual` (ручной ввод) → `auto` (addToCart за 7 дней) → `fallback` (по типу товара на период прогрева).

Фронт уже отправляет новые поля:

- `settings.basketNormMode: 'auto' | 'manual'` — выбор источника
- `settings.basketNormManual: number | null` — значение, когда `mode === 'manual'`
- `meta.basketNormSource: 'manual' | 'auto' | 'fallback'` — что фактически применяется (для бейджа)

**Что нужно от бэка:**

- PATCH/PUT `/api/v1/wb-repricer/sku/:articleId/settings` принимает `basketNormMode`/`basketNormManual`. При `manual` бэк **не** пересчитывает норму по Analytics, но продолжает собирать `basketsLast7d` для сравнения.
- При переключении `manual → auto` значение `basketNormManual` **хранить** (не обнулять), чтобы пользователь мог быстро вернуть последнюю ручную норму.
- `meta.basketNormSource` выставляется бэком: `manual` если `mode=manual`, иначе `fallback` пока SKU в прогреве (warmup), иначе `auto`.

Подробности — в [`docs/wb-repricer-decisions-2026-04-24.md`](../docs/wb-repricer-decisions-2026-04-24.md).

## История

- **2026-04-23**: реестр создан на Block 7 (scaffold + карточка настройки SKU)
- **2026-04-24**: все 10 pending закрыты анализом таблиц Марии + транскриптов 10 встреч. Handover-документ для клиента/разработки готов.
- **2026-04-24 (вечер)**: добавлен ручной ввод нормы корзин (приоритет над auto/fallback) — ждём API от Филиппа.
