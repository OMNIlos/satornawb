# INDEEPA WB replacement PRD pack

Дата: 2026-05-19  
Статус: рабочий PRD-пакет после live-аудита INDEEPA. Production-код Vella не менялся.

## Как читать пакет

Этот пакет превращает файл для Фила `research/33-indeepa-wb-scope-for-fil-2026-05-18.html` в разработческие PRD по ключевым разделам WB replacement. Цель не в том, чтобы скопировать INDEEPA один-в-один, а в том, чтобы зафиксировать production-функционал Vella: что нужно для отключения INDEEPA, что нужно для hardening, а что является отдельным change request.

## Документы

| Файл | Раздел |
|---|---|
| `00-master-prd.md` | Общий master PRD и scope-cut |
| `01-repricer-core-prd.md` | Репрайсер WB: таблица товаров, SKU drawer, расчеты, отправка цен |
| `02-repricer-settings-prd.md` | Глобальные настройки репрайсера: 17 параметров, presets, guards |
| `03-repricer-strategies-prd.md` | Стратегии 4599, 4600, 4442, 4445 и formula/rule layer |
| `04-price-input-safety-prd.md` | Защита от скачков цен и входных метрик |
| `05-accounts-roles-audit-prd.md` | Аккаунты, роли, доступы, audit trail |
| `06-nrp-unit-pnl-prd.md` | NRP: Unit WB / P&L |
| `07-nrp-planfact-prd.md` | NRP: План-факт WB |
| `08-nrp-rnp-ads-prd.md` | NRP: РнП WB / реклама |
| `09-nrp-rating-prd.md` | NRP: рейтинг товара / Vella score |
| `10-excel-big-tables-prd.md` | Excel import/export, большие таблицы, sticky/virtualization |
| `11-readiness-matrix.md` | Связка PRD -> Sprint cut -> blockers -> handoff |

## Handoff artifacts

| Файл | Назначение |
|---|---|
| `docs/client-summary-indeepa-wb-replacement-2026-05-19.md` | Короткое резюме для Фила: v1, P2, вопросы |
| `docs/handoffs/indeepa-wb-backend-checklist.md` | Backend checklist: entities, jobs, source mapping, guards, audit |
| `docs/handoffs/indeepa-wb-frontend-checklist.md` | Frontend checklist: shell, tables, drawer, states, import/export |
| `docs/handoffs/indeepa-wb-uat-checklist.md` | UAT checklist для Марии, Максима и Фила |

## Главная рамка

`v1 replacement minimum` закрывает рабочую замену INDEEPA по WB: безопасный репрайсер, настройки Марии, typed strategies, роли, audit, Excel, P&L/РнП/план-факт/рейтинг в Vella-логике.

`production hardening` добавляет устойчивость: source freshness, retry, partial data, большие таблицы, расширенный audit, мониторинг apply jobs, richer NRP.

`full INDEEPA parity` означает BI-плотность, rule-engine, extensions dependency graph, многоуровневые планы и campaign detail parity. Это не входит в текущий v1 без отдельного согласования.

`change request` нужен для кастомного rule-builder как в INDEEPA, Ozon/cross-marketplace, competitor following, black-box `Indeepa.Index`, полного Excel-планирования до 150k строк и полной NRP BI-платформы.
