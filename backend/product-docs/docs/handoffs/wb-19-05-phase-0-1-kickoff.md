# Phase 0/1 kickoff после 19.05

**Источник:** `docs/handoffs/wb-19-05-implementation-roadmap.md`  
**Цель:** запустить реализацию без ожидания полного закрытия всех вопросов: клиентские решения собираются параллельно с backend foundation.

## Что запускаем сейчас

| Поток | Owner | Старт | Результат |
|---|---|---|---|
| Client decisions | Фил + Дмитрий | сразу | Ответы по P&L, Ads, SPP, локомотивам, Service Token timing |
| Backend Sprint A | backend | сразу | FastAPI foundation, source registry, blocked/partial stubs |
| Contract triage | frontend + backend | после старта Sprint A | 19.05 contract delta разнесен на Zod/OpenAPI-ready vs discovery |

## 1. Сообщение Филу для клиента

Формулировка для отправки Марии/Максиму:

```text
Коллеги, после созвона 19.05 мы не расширяем Vella новым большим модулем, а добиваем текущий WB-контур: P&L, РНП/рекламу, ABC/локомотивы, SPP-safe репрайсер и approval по отзывам.

Чтобы backend не заложил неверные формулы, нам нужно закрыть 6 точек:

1. P&L: какие налоги, хранение и общие расходы учитываем в первой версии, за какой период и как распределяем по SKU/брендам/менеджерам?
2. Финансовый отчет WB: в первой версии тянем через API, Excel/CSV или делаем гибрид API + ручная загрузка?
3. Реклама WB: где сейчас берется расход за период, можно ли выгрузить его с привязкой к SKU/кампании, какие поля обязательны?
4. РНП: подтвердите формулы ДРР, ROI/ROMI и маржи, чтобы мы не считали их иначе.
5. Локомотивы: какие итоги нужно видеть сверху по отфильтрованному набору: количество SKU, заказы/выручка, прибыль, маржа, рекламный расход?
6. SPP: где сейчас смотрите СПП по SKU и какие изменения цены/остатков/себестоимости должны замораживать отправку цены?

Отдельно по Service Token: нужно решить, готовим пакет WB Catalog заранее параллельно с пилотом или подаем после тестирования core WB flows. Проверка может занять 2-5 недель, поэтому лучше выбрать момент сейчас.
```

## 2. Таблица ответов, которую нужно получить

| ID | Кому | Вопрос | Нужный формат ответа | Блокирует |
|---|---|---|---|---|
| Q0-01 | Максим | Налоги/НДС в P&L | процент/правило/не считаем в v1 | P&L final |
| Q0-02 | Максим | Хранение WB | правило allocation или ручной ввод | P&L final |
| Q0-03 | Максим | Общие расходы | список статей, период, база распределения | P&L, план-факт |
| Q0-04 | Мария/Максим | Financial report source | API / Excel / hybrid | P&L source mapping |
| Q0-05 | Мария/реклама | Ads source | endpoint/export/screenshot + поля | Ads, РНП, ABC, P&L |
| Q0-06 | Мария/Максим | ДРР/ROI/ROMI formulas | формулы и база расчета | РНП |
| Q0-07 | Мария | Локомотивы summary | список агрегатов | ABC filtered summary |
| Q0-08 | Мария/backend | SPP source | где смотреть/выгрузить/вычислить | Repricer price guard |
| Q0-09 | Мария | Freeze thresholds | stock/SPP/COGS/price пороги | Repricer apply safety |
| Q0-10 | Фил + Дмитрий | Service Token timing | дата/условие подачи | SaaS launch calendar |

## 3. Backend Sprint A kickoff

Backend можно запускать до ответов клиента. Но unresolved источники должны вернуться как `blocked`, `unknown` или `partial`.

Первые задачи backend:

| День | Задача | Файл-источник | Done |
|---:|---|---|---|
| 1 | Repo skeleton + healthcheck | `docs/handoffs/wb-backend-sprint-a-tickets.md` A0 | app поднимается, `/health` ok |
| 1-2 | Postgres/Redis/Celery/Alembic | A1 | миграции/worker работают локально |
| 2 | Common envelope | A2/A4 | response/error/source states serializable |
| 2-3 | Account/token health | A3 | missing token/scopes are first-class states |
| 3 | Source registry seed | A5 | WB-02/WB-03/WB-06/WB-11/WB-12/WB-13/WB-14A/WB-19A/WB-22/WB-23 seeded |
| 3-4 | 19.05 source-state stubs | A11.1 | P&L/Ads/РНП/ABC/SPP/reviews return contract-shaped blocked/partial states |

## 4. Contract triage order

Не нужно сразу писать все OpenAPI. Порядок triage:

1. Common source state: `sourceStatus`, `confidence`, `SourceEvidence`, `blockerIds`.
2. SPP guard: самый рискованный для price apply.
3. Ads normalized layer: блокирует РНП, ABC advertising fields и P&L.
4. P&L: зависит от financial source и правил Максима.
5. ABC `filteredSummary`: можно сделать early, часть рекламных полей partial.
6. AI reviews approval: отдельно, через agent harness.

## 5. Что frontend может делать до backend

Можно:

- подготовить Zod draft из `docs/api-contracts/wb-19-05-contract-delta.md`;
- найти в Vella surfaces, куда подключатся states;
- подготовить copy для `blocked/partial/stale`;
- сделать mock states только как explicit mock, не как production truth.

Нельзя:

- считать SPP/freeze на frontend как источник истины;
- показывать P&L final без backend/source state;
- распределять `campaign_only` Ads spend в SKU P&L;
- добавлять brand plan UI до `WB-14A`.

## 6. Первый контрольный checkpoint

Checkpoint через 2-3 рабочих дня после старта:

| Проверка | Ожидаемый результат |
|---|---|
| Backend поднят локально | README + healthcheck + tests |
| Source registry есть | blockers seeded, endpoints return list |
| 19.05 stubs есть | P&L/Ads/РНП/ABC/SPP/reviews return blocked/partial states |
| Клиентские вопросы отправлены | есть owner и дедлайн по каждому вопросу |
| Contract triage начат | каждый slice имеет статус: schema/discovery/client |

## 7. Решение после checkpoint

Если SPP source и price apply status подтверждены, Sprint B идет в repricer guard/apply.  
Если Ads source подтвержден раньше SPP, можно параллельно начинать Ads/РНП data layer.  
Если P&L расходы не подтверждены, P&L остается `operative/preliminary`, без `final`.
