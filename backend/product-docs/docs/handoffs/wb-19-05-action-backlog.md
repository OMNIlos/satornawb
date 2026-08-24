# WB action backlog после созвона 19.05

**Источник:** `Встречи/19.05/meeting-protocol-backlog-2026-05-19.md`  
**Назначение:** meeting delta к WB / INDEEPA replacement handoff. Этот файл дополняет `wb-backend-programmer-brief.md`, `wb-backend-sprint-a-tickets.md` и `docs/open-questions-current.md`; он не заменяет основной Sprint A foundation.

## Data / P&L

| ID | Тип | Приоритет | Задача | Владелец | Affected docs/contracts | Acceptance | Таймкод |
|---|---|---|---|---|---|---|---:|
| M19-PNL-01 | Backend discovery | P0 | Составить field mapping P&L: метрика -> источник WB/API/Excel -> поле -> формула -> частота -> fallback. | Backend + Дмитрий | `docs/open-questions-current.md` WB-03, `docs/api-contracts/README.md` | Для выручки, COGS, комиссии, логистики, хранения, рекламы, налогов и чистой прибыли есть источник, формула и fallback. | 00:03:43-00:05:24 |
| M19-PNL-02 | Backend discovery | P0 | Добавить модель раскладки продаж/расходов P&L по дням. | Backend + Максим | WB-03, WB-12, P&L contract | P&L можно считать по календарю; дата продажи/расхода явно участвует в формуле. | 00:04:52-00:05:24 |
| M19-PNL-03 | Client question | Q | Подтвердить способ обновления финансового отчета: API, Excel import или гибрид. | Фил + Максим/Мария | WB-03 | Для финансового отчета выбран основной источник и fallback ручной загрузки. | 00:05:20-00:05:24 |
| M19-PNL-04 | Client question | Q | Подтвердить налоги, хранение и общие расходы. | Максим | WB-12, WB-13 | Известно, какие суммы вводятся руками и как распределяются по SKU/брендам/площадкам. | 00:06:36-00:06:54 |

## Ads / РНП

| ID | Тип | Приоритет | Задача | Владелец | Affected docs/contracts | Acceptance | Таймкод |
|---|---|---|---|---|---|---|---:|
| M19-ADS-01 | Backend discovery | P0 | Закрыть источник рекламных расходов за период. | Backend discovery | WB-02, WB-03, WB-23 | Подтверждены endpoint/export, поля, доступы, лимиты и fallback. | 00:09:40-00:11:34 |
| M19-ADS-02 | Backend/API | P0 | Собрать нормализованный слой рекламы для DRR/ROMI/ROI. | Backend + frontend contract review | WB-02, `frontend/src/features/wb-repricer/schemas.ts` | Таблица/contract содержит spend, показы, клики, корзины, заказы, DRR, ROMI/ROI, период и confidence. | 00:09:40-00:11:34 |
| M19-RNP-01 | Backend/API | P0 | Добавить рекламную стоимость за тот же период в РНП. | Backend | WB-02, WB-11 | РНП показывает spend за выбранный период; если атрибуция слабая, возвращает confidence/blocked state. | 00:23:36-00:24:29 |
| M19-RNP-02 | Backend/API | P0 | Добавить/проверить ДРР в РНП. | Backend + Мария/Максим | WB-11 | ДРР считается от согласованной базы; формула и период документированы. | 00:23:36-00:24:29 |

## ABC / ассортимент

| ID | Тип | Приоритет | Задача | Владелец | Affected docs/contracts | Acceptance | Таймкод |
|---|---|---|---|---|---|---|---:|
| M19-ABC-01 | Frontend/UI + API | P1 | Добавить summary по отфильтрованным товарам/локомотивам. | Frontend + backend API | WB-09, WB-19, reports/ABC contract | После фильтра видно count, продажи/заказы руб, прибыль и маржу по текущему набору. | 00:11:37-00:13:16 |
| M19-ABC-02 | Frontend/UI | P1 | Сделать верхний/sticky блок итогов в анализе ассортимента. | Frontend | Vella reports UI | Итоги не теряются при скролле и пересчитываются при изменении фильтров. | 00:12:49-00:13:16 |
| M19-ABC-03 | Client question | Q | Подтвердить первый набор агрегатов для локомотивов. | Фил + Мария | WB-09, WB-19 | Мария подтверждает минимум: count, продажи/выручка, прибыль, маржа или другой список. | 00:11:50-00:13:16 |

## Repricer / SPP

| ID | Тип | Приоритет | Задача | Владелец | Affected docs/contracts | Acceptance | Таймкод |
|---|---|---|---|---|---|---|---:|
| M19-REP-01 | Backend/API | P0 | Зафиксировать freeze-state при скачках stock/SPP/себестоимости/цены. | Backend | WB-06, WB-22, WB-23 | При подозрительном изменении price apply блокируется; API возвращает причину, source evidence и последнюю корректную цену. | 00:15:01-00:16:00 |
| M19-REP-02 | Backend discovery | P0 | Проверить источник СПП по SKU. | Backend discovery | WB-06 | Подтвержден endpoint/field или безопасный fallback; если нет надежного источника, SPP-aware apply остается blocked. | 00:17:15-00:19:50 |
| M19-REP-03 | Backend/API | P0 | Добавить SPP-aware расчет цены. | Backend | WB-06, price recommendation contract | Рекомендация учитывает изменение СПП и показывает, как сохраняется целевая цена покупателя. | 00:18:36-00:19:50 |
| M19-REP-04 | Frontend/UI + API | P1 | Добавить шаг стратегии в рублях рядом с шагом в процентах. | Frontend + backend settings | WB-14, typed settings model | В настройках стратегии можно задать рублевый и процентный шаг; значения валидируются. | 00:17:15-00:18:36 |
| M19-REP-05 | P2/out of v1 | OUT/P2 | Не переносить кастомный rule-engine INDEEPA в v1. | Product | L-05 | В v1 доступны approved templates и параметры; произвольный builder условий не проектируется. | 00:16:26-00:16:50 |

## AI reviews

| ID | Тип | Приоритет | Задача | Владелец | Affected docs/contracts | Acceptance | Таймкод |
|---|---|---|---|---|---|---|---:|
| M19-AI-01 | Backend/API + agent harness | P0 | Зафиксировать approval gate для отзывов ниже 4 звезд. | Backend + frontend + AI | `docs/architecture/agent-harness-standard.md`, `docs/evals/ai-agent-evals.md` | Низкий рейтинг создает draft, требует approval, только потом допускается send. | 00:27:28-00:28:09 |
| M19-AI-02 | Client question | P1 | Развести brand voice и мемный стиль. | Фил + Максим/Мария | WB-16, AV-03 | Есть правила, где мемный стиль допустим, а где нужен нейтральный/брендовый тон. | 00:25:18-00:28:09 |
| M19-AVITO-01 | Frontend/UI | P1 | Уменьшить визуальную рябь Avito messages UI. | Frontend | Avito v1 handoff | Inbox читается без перегруза, статусы и draft actions остаются доступными. | 00:25:18-00:25:40 |

## Service Token

| ID | Тип | Приоритет | Задача | Владелец | Affected docs/contracts | Acceptance | Таймкод |
|---|---|---|---|---|---|---|---:|
| M19-TOKEN-01 | Client/project ops | P0 | Подготовить пакет для WB Service Token. | Фил + Дмитрий | `docs/constraints.md`, WB auth/billing notes | Есть лендинг/сайт, описание сервиса, поддержка, политика конфиденциальности, security files и план подачи. | 00:31:49-00:34:08 |
| M19-TOKEN-02 | Architecture/docs | P0 | Развести Personal Token пилот и Service Token SaaS. | Backend + Фил | auth/onboarding docs | Документы и onboarding явно говорят: Personal Token только для single-client пилота, Service Token для SaaS. | 00:33:49-00:34:08 |
| M19-TOKEN-03 | Client question | Q | Выбрать момент подачи на Service Token. | Фил + Дмитрий | project plan | Решено, подаем после тестирования core WB flows или заранее на стадии завершения; учтен срок проверки 2-5 недель. | 00:33:49-00:34:08 |

## Entry Points

- Подробный протокол: `Встречи/19.05/meeting-protocol-backlog-2026-05-19.md`
- Summary для Фила: `Встречи/19.05/phil-summary-2026-05-19.md`
- Gap-check текущей Vella против 19.05: `docs/handoffs/wb-19-05-vella-gap-check.md`
- Implementation roadmap 19.05: `docs/handoffs/wb-19-05-implementation-roadmap.md`
- Phase 0/1 kickoff: `docs/handoffs/wb-19-05-phase-0-1-kickoff.md`
- Contract delta 19.05: `docs/api-contracts/wb-19-05-contract-delta.md`
- Текущие blockers: `docs/open-questions-current.md`
- Backend first brief: `docs/handoffs/wb-backend-programmer-brief.md`
