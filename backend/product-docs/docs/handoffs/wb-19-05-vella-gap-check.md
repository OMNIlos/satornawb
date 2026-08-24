# Vella gap-check по созвону 19.05

**Источник:** `Встречи/19.05/meeting-protocol-backlog-2026-05-19.md`  
**Связанный backlog:** `docs/handoffs/wb-19-05-action-backlog.md`  
**Проверено по текущей реализации:** `frontend/public/vella-production.html`, `frontend/src/features/wb-reports/*`, `frontend/src/features/wb-repricer/*`, `docs/api-contracts/README.md`  
**Вывод:** после 19.05 не нужен новый большой UI-модуль. В Vella уже есть визуальные поверхности P&L, РНП, рекламы, ABC, SPP и отзывов. Риск в другом: эти поверхности пока не закрывают источники данных, API contracts, freshness/confidence и guard-состояния, которые стали P0 после созвона.

## Короткий статус

| Поток 19.05 | Что уже видно в Vella | Главный gap | Следующий шаг |
|---|---|---|---|
| Data / P&L | Есть P&L tab, переключатель operational/financial source, карточки ROMI/ROI/EBITDA, блок расходов. | Нет подтвержденного field mapping и day-level allocation; часть расходов выглядит как ручной mock. | Backend discovery + P&L contract до UI-доработок. |
| Ads / РНП | Есть РНП и Ads tabs, spend/ДРР/ROMI/ROI, confidence/attribution wording. | Не доказан реальный источник WB Ads за период и связь spend -> SKU/report period. | Закрыть `M19-ADS-01`, затем нормализованный ads layer. |
| ABC / ассортимент | Есть ABC tab, статусы, фильтр/чип `Локомотивы`, таблица SKU и summary-блоки. | Нет явного contract для пересчета summary по текущему отфильтрованному набору. | Добавить `filteredSummary` в reports API contract. |
| Repricer / SPP | В shell видны SPP, P_min/P_max до/после SPP и объяснения алгоритма. | `pricing.ts` не содержит SPP-aware расчета; freeze-state визуально описан, но не contract-backed. | Сначала источник SPP + guard API, потом UI apply-state. |
| Plans / brands | Есть фильтр brand и groupBy brand; план-факт есть по компании/менеджерам. | `PlanFactRow.owner` ограничен `company | manager`; brand plan как dimension не выражен. | Подтвердить у Марии/Максима и расширить schema при необходимости. |
| AI reviews | Есть draft/approval UI для отзывов. | Для production нужен agent harness: approval gate, audit, evals, prompt caching, permissions. | Закрыть contract и eval pack до автопубликации. |
| Service Token | В UI не требуется отдельный модуль. | Это ops/docs blocker: пакет для WB Catalog и переход с Personal Token. | Готовить Service Token package отдельно от frontend. |

## Детализация по потокам

### Data / P&L

Текущий shell уже правильно показывает, что P&L не равен одному оперативному отчету: есть разделение financial/operational source, свежесть данных и ручные расходы. Это совпадает с логикой созвона.

Но задачи `M19-PNL-01` - `M19-PNL-04` нельзя считать закрытыми. В коде не найден contract, где для каждой P&L-метрики зафиксированы источник, поле, формула, частота и fallback. Также нет отдельной модели раскладки продаж и расходов по календарным дням.

**Следующее действие:** сделать source registry / P&L mapping в backend handoff и API contract. UI менять только после появления статусов `fresh`, `partial`, `pending_financial`, `blocked` на реальных данных.

### Ads / РНП

Текущая Vella уже содержит нужные смысловые элементы: рекламные расходы, ДРР, ROI/ROMI, confidence и attribution hints. Поэтому frontend-поверхность в целом направлена верно.

Главный blocker остается backend: `M19-ADS-01`, `M19-ADS-02`, `M19-RNP-01`, `M19-RNP-02`. Нужен проверенный источник рекламных расходов за период и нормализованный слой, который отдаёт spend, показы, клики, корзины, заказы, ДРР, ROI/ROMI и confidence.

**Следующее действие:** не расширять таблицы руками. Сначала добавить ads source contract и blocked/confidence states, чтобы РНП честно показывал, когда атрибуция неполная.

### ABC / ассортимент

ABC-раздел уже покрывает большую часть демонстрационной идеи: статусы SKU, локомотивы, чистая прибыль, реклама, маржа, фильтры и summary. Это хороший UI baseline.

Gap по созвону точечный: Мария просила видеть агрегаты по выбранному набору товаров/локомотивов. Сейчас это не выглядит как обязательный contract. Для production нужен ответ API, который пересчитывается после фильтров, а не статичная карточка.

**Предлагаемый contract slice:**

| Поле | Смысл |
|---|---|
| `filterHash` | Идентификатор текущего набора фильтров. |
| `skuCount` | Количество SKU в выбранном наборе. |
| `ordersRub` | Заказы или продажи в рублях по согласованной базе. |
| `profitRub` | Чистая прибыль по выбранным SKU. |
| `marginPct` | Маржа выбранного набора. |
| `adSpendRub` | Рекламные расходы по выбранному набору, если доступны. |
| `confidence` | Уровень надежности расчета. |

### Repricer / SPP

В canonical shell уже есть правильные сигналы для клиента: SPP показывается рядом с ценой, P_min/P_max объясняются, есть предупреждения о защите. Это соответствует направлению 19.05.

Но в React pricing layer сейчас виден базовый расчет P_min от себестоимости/логистики/комиссий/маржи. SPP-aware логика и freeze-state при скачках stock/SPP/себестоимости/цены должны прийти из backend/API, иначе frontend будет имитировать безопасность.

**Следующее действие:** закрыть `M19-REP-01` - `M19-REP-03` как backend/API. Frontend после этого должен только отображать `canApply`, `blockedReason`, `sourceEvidence`, `lastKnownGoodPrice`, `sppSnapshot` и impact на buyer price.

### Plans / Brands

Созвон уточнил, что план по брендам может стать измерением. В текущем frontend есть brand filter и groupBy brand, но plan-fact rows типизированы только как компания или менеджер.

**Следующее действие:** не добавлять brand plan в UI без подтверждения. Вопрос уже должен жить как client question: если brand plan подтверждается, меняем типы и contract, затем UI.

### AI reviews

В UI уже есть паттерн draft -> approval для отзывов. Это совпадает с созвоном, где низкие оценки не должны уходить автоматически.

Production-ready часть не в кнопках. Нужны permission matrix, audit trail, approval gate, eval pack и prompt caching из `docs/architecture/agent-harness-standard.md` и `docs/evals/ai-agent-evals.md`.

### Service Token

Service Token не должен превращаться в новый frontend backlog. Это пакет готовности сервиса: сайт/лендинг, описание сервиса, поддержка, privacy/security материалы, onboarding и план подачи в WB Catalog.

Personal Token допустим только для single-client пилота. В документах и onboarding нельзя описывать его как SaaS-ready способ подключения.

## Что не делать следующим шагом

- Не начинать новый визуальный редизайн отчетов: текущая Vella уже покрывает основные экраны.
- Не считать P&L/Ads/РНП готовыми по наличию mock UI.
- Не переносить кастомный rule-engine INDEEPA в v1.
- Не делать SPP safeguards на frontend-only логике.
- Не добавлять brand plan как UI-фичу до подтверждения и schema change.

## Рекомендуемый порядок работ

1. **Backend discovery:** P&L mapping, ads source, SPP source, Service Token package timing.
2. **Contracts:** P&L report, ads normalized layer, ABC filtered summary, SPP guard/freeze state, plan fact dimension. Draft: `docs/api-contracts/wb-19-05-contract-delta.md`.
3. **Frontend patch:** только после contracts - blocked states, confidence, filtered summary, brand plan if confirmed.
4. **AI reviews hardening:** approval gate, permissions, audit, evals, prompt caching before production send.

## Связь с backlog 19.05

| Backlog ID | Статус по Vella | Комментарий |
|---|---|---|
| `M19-PNL-01` - `M19-PNL-04` | Не закрыто | UI есть, mapping/source/fallback нет. |
| `M19-ADS-01` - `M19-ADS-02` | Не закрыто | UI есть, источник WB Ads и нормализация требуют discovery. |
| `M19-RNP-01` - `M19-RNP-02` | Частично покрыто UI | Нужно связать РНП с реальным spend/confidence. |
| `M19-ABC-01` - `M19-ABC-03` | Частично покрыто UI | Нужен contract для filtered aggregate. |
| `M19-REP-01` - `M19-REP-03` | Не закрыто | SPP/freeze должны быть backend-backed. |
| `M19-REP-04` | Не проверено как готовое | Рублевый шаг стратегии нужно сверить с typed settings. |
| `M19-REP-05` | Подтверждено как исключение | Rule-engine INDEEPA не тащим в v1. |
| `M19-AI-01` - `M19-AI-02` | Частично покрыто UI | Нужны agent harness, evals и approval contracts. |
| `M19-TOKEN-01` - `M19-TOKEN-03` | Вне UI | Ops/docs blocker. |
