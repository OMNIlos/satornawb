# PRD: Репрайсер WB core

## 1. Назначение

Раздел закрывает ежедневную работу с WB-ценами: таблица товаров, SKU drawer, расчет маржи, подготовка price drafts и безопасная отправка цен в WB.

## 2. Роли

- Мария: контролирует стратегии, статусы SKU и массовые изменения.
- Менеджер: работает со своими SKU, комментариями, ручными price drafts.
- Максим: проверяет маржу и финансовые компоненты.
- `price_sender`: подтверждает отправку цен.
- Администратор: следит за WB apply errors и интеграциями.

## 3. Пользовательские сценарии

- Открыть таблицу SKU и отфильтровать товары по менеджеру, бренду, категории, статусу, акции, ABC, проблемам данных.
- Открыть SKU drawer и понять, почему цена рекомендуется к изменению.
- Изменить цену вручную и сразу увидеть новую маржу до отправки.
- Сформировать массовый price draft из стратегии или Excel import.
- Отправить цены в WB после preview и approval.
- Увидеть, какие строки заблокированы P_min/P_max, дневным лимитом, СПП или stale-source.

## 4. Данные

- SKU: фото, nmId, vendorCode, внутренний артикул, бренд, категория, пол/тип изделия, менеджер.
- Цены: текущая цена, цена до СПП, цена после СПП, средняя цена за период, СПП, min_price.
- Экономика: COGS, комиссия, логистика, хранение, налоги, маржа руб/%.
- Спрос: корзины, заказы, продажи, выручка, остатки, % выкупа.
- Реклама: расходы, ДРР, ROI, если источник доступен.
- Стратегия: active strategy, version, last calculation, reason.
- Audit: старое значение, новое значение, actor, job, rule/version, источник.

## 5. Поля, фильтры и контролы

Обязательные колонки таблицы:

- фото;
- артикул WB и внутренний артикул;
- бренд, категория, менеджер;
- текущая цена;
- цена до СПП;
- цена после СПП;
- СПП;
- маржа руб/%;
- ABC/рейтинг;
- акция;
- остаток WB;
- корзины, заказы, продажи;
- реклама/ДРР/ROI;
- active strategy;
- status/reason.

Контролы:

- период: 7, 14, 30 дней, custom;
- фильтры: менеджер, бренд, категория, статус, акция, strategy, source state;
- сортировка и multi-sort;
- column presets;
- saved views;
- export;
- import preview;
- mass draft;
- send selected / send all approved.

SKU drawer:

- summary экономики;
- price planes до/после СПП;
- strategy explanation;
- P_min/P_max;
- input source freshness;
- история цен;
- комментарии;
- audit events;
- связанные отчеты: P&L, РнП, rating, plan-fact.

## 6. Расчеты и бизнес-правила

Маржа:

```text
Цена продажи с учетом СПП
- комиссия WB
- логистика
- хранение
- себестоимость
- налоги
= маржа
```

Правила:

- редактируется одна ценовая плоскость: либо до СПП, либо после СПП;
- конфликтующие значения до/после СПП запрещены;
- цена ниже P_min запрещена вне liquidation approval;
- price draft не отправляется без source confidence по критичным метрикам;
- любой auto-price должен иметь reason и strategy version;
- WB apply job хранит статус `draft`, `approved`, `queued`, `sent`, `accepted`, `failed`, `rolled_back/stop_required`.

## 7. Состояния

| State | Поведение |
|---|---|
| `loading` | Skeleton таблицы и drawer |
| `empty` | "Нет SKU по фильтрам/периоду" |
| `error` | Ошибка с retry и last successful snapshot |
| `partial_data` | Поля с warning, auto-send заблокирован для зависимых стратегий |
| `no_access` | Скрыть финансовые поля или кнопки отправки |
| `not_enough_data` | Показывать причину, не считать уверенную рекомендацию |
| `wb_apply_error` | Отдельный статус строки и job detail |

## 8. Опасные действия

Требуют `draft -> diff -> approval -> commit`:

- ручная отправка цены в WB;
- массовая отправка price drafts;
- Excel import с изменением цен;
- override P_min в liquidation flow;
- повторная отправка после WB error.

## 9. Что уже есть в Vella

- рабочий shell;
- таблица, drawer, saved views, preview-концепция;
- объяснение рекомендаций и audit-концепция;
- связь репрайсера с отчетами.

## 10. Что нужно доделать

- реальные WB data adapters;
- persistence для SKU, цен, drafts, apply jobs, audit, comments;
- price engine с typed strategies;
- source confidence и stale checks;
- Excel import/export;
- backend permissions;
- WB apply status polling.

## 11. v1 replacement minimum

- таблица SKU с обязательными полями;
- drawer с расчетом маржи и reason;
- ручной price draft;
- strategy-generated drafts;
- preview и approval;
- WB apply job;
- audit;
- Excel export/import для цен;
- states для partial data и source blockers.

## 12. Production hardening

- виртуализация больших таблиц;
- полноценный job monitor;
- richer history и diff per formula version;
- сохраненные представления с column presets;
- batch rollback/stop plan;
- deep links из отчетов в SKU drawer.

## 13. P2 / change request

- custom rule-engine;
- competitor following;
- cross-marketplace pricing;
- полная BI-плотность INDEEPA внутри drawer.

## 14. Сложность

Оценка: 7-12 рабочих дней для core production без full parity. Риск высокий из-за WB apply/status, СПП и финансовых источников.

## 15. Открытые вопросы

- Какой источник СПП считаем доверенным?
- Кто имеет право массово отправлять цены?
- Нужен ли staged rollout по части SKU перед массовой отправкой?
- Какие поля обязательны для блокировки auto-send?
- Нужно ли хранить ручную причину для каждого price override?

