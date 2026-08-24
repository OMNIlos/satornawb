# Актуальные открытые вопросы

**Дата:** 21 мая 2026
**Статус:** текущий рабочий реестр блокеров после аудита созвонов, ТЗ, майских правок и live-аудита INDEEPA WB.

---

## Как пользоваться

Этот файл заменяет старый рабочий список `Встречи/open-questions-2026-04-20.md` для текущей разработки. Старый файл остается историческим источником, но в работу берем этот список.

Статусы:

- `BLOCKER` - без ответа нельзя надежно реализовать production-логику.
- `CONFIRM` - нужно подтвердить до финальной реализации или UAT, но можно временно мокать.
- `LATER` - не блокирует v1.

---

## BLOCKER

| ID | Вопрос | Владелец | Где влияет | Что нужно получить |
|---|---|---|---|---|
| WB-01 | Источник локальных заказов для индекса локализации | Backend discovery | Репрайсер, отчеты, логистика, маржа | Формула и таблица от Марии получены 09.05: локализация = локальные заказы / все заказы × 100%, КТР берется по диапазону локализации. Осталось подтвердить источник `локальные заказы` по складу/кластеру |
| WB-03 | Endpoint/field mapping по отчетам WB | Дмитрий/backend discovery | Все WB-отчеты | Таблица `экран -> метрика -> источник -> поле -> формула -> fallback`; рабочая матрица фронт/бэк: `docs/handoffs/wb-03-frontend-backend-reports-matrix-2026-06-01.md`. BFF `/api/wb/reports/*`, adapter sources `orders/sales/reportDetailByPeriod/sales-reports-list/warehouse_remains/penalties/acceptance/paid_storage` реализованы 02.06.2026; остаток — live semantic validation полей `sale_percent`, `dlv_prc` и накопление собственной daily history по остаткам |
| WB-04 | Критерии ликвидации | Мария | Отчет по ликвидации, репрайсер | Пороги оборачиваемости, корзин, продаж, рекламы; логика AND/OR |
| WB-05 | КИЗ-процесс | Максим | Заказы WB, производство | Владелец, источник пула, тестовый пул, формат импорта, порядок пополнения |
| WB-17 | Формула складского решения `норма/держать/дозагрузить` | Мария + backend discovery | Отчеты остатков, складская экономика | Правило по SKU, складу WB, кластеру, доступному остатку, КТР/локализации и заказам/день |
| WB-18 | Правило доступного остатка и поля `к клиенту` / `от клиента` | Backend discovery + Мария | Отчеты остатков, week-over-week, OOS | Подтвердить поля WB API; бизнес-правило 8.05: доступный остаток = `остаток WB + от клиента`, `к клиенту` не прибавлять |
| AV-01 | QR-коды возвратов Авито | Backend discovery + Максим | Возвраты Авито | Проверить, отдает ли Avito Delivery API QR возврата; описать fallback |
| AV-02 | Авито кошельки и платежи | Максим + backend discovery | Автопополнение кошельков | Balance read likely; top-up API не найден. Подтвердить провайдера, лимиты, владельца платежки, схему ручного/approval top-up |
| AV-05 | Avito live API UAT доступ | Фил + клиент + backend discovery | Вся Phase 2 оценка | Дать безопасный аккаунт с платным тарифом, активными объявлениями и по возможности чатами/отзывами/заказами; подтвердить read-only режим discovery |
| AV-06 | Messenger тариф/scopes/rate limits | Backend discovery | Единый inbox, бот, уведомления <=30 сек | Проверить на реальном аккаунте: chats/messages, write capability, webhook, rate limits, требование `Максимальный` |
| AV-07 | XML/autoload registry and publish mechanics | Backend discovery | Объявления, XML safety, репрайсер | Проверить autoload profile/reports, active registry, report errors, safe publish path; real publish только на sandbox/test после отдельного approval |
| AV-08 | Items REST write coverage | Backend discovery | Listing edit/create/photo | Подтвердить, есть ли direct REST create/update/photo publish. Если нет — v1 external mutations остаются XML/autoload-only |
| AV-09 | Avito stats fields and depth | Backend discovery | Analytics, repricer | Подтвердить views/contacts/favorites/impressions/spend, период 7d/30d/custom, rate limits |
| AV-10 | Reviews API reply/delete scopes | Backend discovery | Отзывы, AI replies | Подтвердить read/reply/delete fields; external reply remains approval-gated |
| AV-11 | Order-management labels and side effects | Backend discovery | Заказы, стикеры, production queue | Подтвердить orders/list/detail, labels job, mutating vs read-only behavior |
| AV-12 | Avito marking codes workflow | Backend discovery + Максим | Авито заказы, Честный знак | Проверить `/markings` workflow and whether it intersects with external КИЗ process |

---

## CONFIRM

| ID | Вопрос | Владелец | Где влияет | Что нужно получить |
|---|---|---|---|---|
| WB-07 | Полный справочник категорий | Мария | Фильтры репрайсера/отчетов | Муж/жен, футболки, худи, лонгсливы, шорты, балаклавы, новые категории |
| WB-08 | Полный формат артикулов и исключения | Мария | Заказы, SKU-справочник, себестоимость, производство | Примеры всех комбинаций и старые/грязные карточки |
| WB-09 | ABC-колонки подтверждены | Мария | ABC-отчет, репрайсер | Подтверждение списка из `От Марии/abc анализ.md` |
| WB-10 | Состав сводного дайджеста | Мария | Отчеты | Какие KPI и в каком порядке показываем на главной странице отчетов |
| WB-14A | Бренд как измерение план-факта | Мария | План-факт, отчеты, роли менеджеров | После созвона 19.05: не делать отдельный план-факт по SKU/кабинету; подтвердить, что план по бренду живет как измерение/фильтр в едином план-факте |
| WB-15 | OOS-защита | Мария | Репрайсер | Целевые дни оборачиваемости, верхний предел цены, источник ожидаемой поставки |
| WB-16 | База автоответов WB | Мария + сотрудница по отзывам | Автоответы WB | Шаблоны, стоп-темы, правила модерации |
| WB-19 | Критерии статусов товара из INDEEPA | Дмитрий + Мария | ABC, РНП, P&L по статусам | Пороги для `локомотив`, `новинка`, `средний`, `неликвид`, `ликвидация`; Мария 8.05 сказала взять логику INDEEPA |
| WB-19A | Агрегаты по отфильтрованным локомотивам | Мария | ABC, анализ ассортимента | После созвона 19.05: подтвердить первый набор итогов по фильтру - count, продажи/выручка, прибыль, маржа или другой список |
| WB-20 | Порог рекомендации `отключить рекламу` | Мария | Отчет рекламы, РНП, automation hints | V1-правило зафиксировано как кандидат на проверку: 21+ дней, ДРР продаж ≥ 25%, расход ≥ 1 500 ₽, без OOS/новинки/акции/ликвидации, атрибуция не ниже campaign-SKU. Осталось подтвердить финальный ДРР-порог и исключения по самовыкупам |
| WB-21 | Нужен ли `резерв` в остатках | Мария + backend discovery | Отчет остатков | Мария сомневается, что резерв есть на WB-складе или нужен в v1; проверить источник и убрать/пометить колонку |
| WB-25 | Live INDEEPA стратегии 4442/4445 | Мария | Стратегии репрайсера, v1/P2 boundary | Подтвердить, используются ли 4442/4445 реально; для 4442 выбрать окно `01:00-05:00` или `23:00-06:00 МСК`; для 4445 дать правила СПП + оборачиваемость или оставить `discovery_required` |
| WB-26 | Момент подачи на WB Service Token | Фил + Дмитрий | SaaS auth, запуск сервиса, календарный план | После созвона 19.05: выбрать, подаем после тестирования core WB flows или заранее на стадии завершения; учесть проверку 2-5 недель и пакет сайт/описание/поддержка/политики/security files |
| WB-22 | WB price apply/status и ошибки отправки цен | Backend discovery | Репрайсер, apply jobs, audit, UAT | Закрыто 28.05.2026: реализован боевой apply flow `POST /api/v2/upload/task` + polling `GET /api/v2/history/tasks` + row errors `GET /api/v2/history/goods/task`, добавлен runtime endpoint `/api/v1/wb-repricer/actions/price-apply` и audit trail |
| WB-23 | Source freshness/confidence registry | Backend discovery | Репрайсер, РнП, P&L, guards, reports | Закрыто 28.05.2026: runtime policies и API endpoints для critical metrics (`current price before/after SPP`, `SPP`, `margin`, `P_min/P_max`, `price apply status`) реализованы; auto-apply блокируется при stale/blocked critical data |
| AV-03 | Сценарии бота Авито | Максим | Авито чат-бот | Типовые вопросы, стоп-слова, правила эскалации менеджеру |
| AV-04 | Фото для Авито | Максим/Мария | Генерация фото | Подтвердить стили фонов, критерии уникальности, лимиты по аккаунтам |
| AV-13 | Promotion/boost management boundary | Мария/Максим + backend discovery | Аналитика, продвижение | В v1 читать promotion info if available; управление бустами P2 unless explicitly confirmed and approved |
| AV-14 | Account access roles for 10-15 accounts | Максим/Мария | Роли, no-access states | Кто видит финансы, кто отвечает в чатах, кто может approve XML/price/payment/review send |
| OPS-01 | Производственная мощность | Максим | Заказы, очереди, планирование | Количество термопрессов, операторы, смены |
| OPS-02 | Остатки бланков | Максим | Склад/заказы | Ведем в SaaS v1 или оставляем вне скоупа/ручным импортом |

---

## LATER / вне v1

| ID | Вопрос | Решение |
|---|---|
| L-01 | Прямая интеграция 1С | Вне v1. Не тянуть в P&L/КИЗ/склад без отдельного соглашения. |
| L-02 | Ozon / кроссмаркетплейс | Вне v1. |
| L-03 | Геймификация менеджеров | После MVP. |
| L-04 | Встроенный командный мессенджер | После MVP. |
| L-05 | Кастомный rule-engine как в INDEEPA | Не делать в v1. Готовые стратегии + параметры. |
| L-06 | Конкурентное следование по фиксированному списку | Не делать в v1. |
| L-07 | PDF/share отчетов | Убрано из обязательного v1; оставить Excel. |
| L-08 | Full NRP BI parity | Отдельный change request. В v1 делаем NRP-lite: P&L, РнП, план-факт, рейтинг в Vella-логике. |
| L-09 | Campaign detail parity как в INDEEPA | P2/change request. В v1 РнП дает воронку и review candidates без полной BI-модалки кампании. |

---

## Закрыто после старого списка

- WB-06 закрыт 27.05.2026: подтвержден seller-side источник SPP-like скидки через `POST https://discounts-prices-api.wildberries.ru/api/v2/list/goods/filter` (`discount`, `clubDiscount`, `sizes[].discountedPrice`, `sizes[].clubDiscountedPrice`), fallback: вычисление `sppPct = (discountedPrice - clubDiscountedPrice) / discountedPrice * 100`.
- WB-12 закрыт 28.05.2026: хранение считаем отдельной расходной статьей (как в INDEEPA), источник - WB finance source; детализация по SKU/менеджерам для v1 не требуется.
- WB-13 закрыт 28.05.2026: налог в P&L задается ручным `avgTaxPctFact` (средний фактический налог после всех расходов). Для ориентира сохраняем контекст `НДС 22%`, `доход-расход 15%`, но в расчетах используем фактический ручной процент.
- WB-14 закрыт 28.05.2026: применение стратегий в v1 подтверждено на уровне артикула (`SKU` / `vendorCode`) по логике INDEEPA.
- WB-11 закрыт 29.05.2026: формулы РНП подтверждены: `DRR = adSpend / revenue * 100`, `marginPct = netProfit / revenue * 100`, `ROI = (revenue - adSpend) / adSpend * 100` (sales-based).
- WB-24 закрыт 29.05.2026: политика видимости подтверждена Максимом и Марией: менеджеры видят отчеты и export, но ежемесячные затраты компании (`overhead`) скрываются для пользователей без `finance:read`.
- WB-02 закрыт 01.06.2026: подтвержден и реализован официальный WB Ads источник с SKU-атрибуцией: `GET /adv/v1/promotion/count` -> `GET /api/advert/v2/adverts` -> `GET /adv/v3/fullstats` (`https://advert-api.wildberries.ru`), в backend закреплены режимы `exact_sku / campaign_sku / campaign_only` и правило не распределять weak attribution в SKU P&L.
- Базовый формат артикула: `[Тип][Цвет]BT_[Номер принта]`.
- Стратегия корзин: 2x2-матрица "корзины растут/нет x заказы растут/нет".
- Порядок разработки: сначала WB, затем Авито+Заказы.
- Мобильная версия: упрощенная, ПК основной.
- Автоакции WB: не управляем через API, защищаем через `minPrice`.
- Авито и WB цены не синхронизируются.
- Мария не является главным ЛПР по Авито; Авито в основном зона Максима.
