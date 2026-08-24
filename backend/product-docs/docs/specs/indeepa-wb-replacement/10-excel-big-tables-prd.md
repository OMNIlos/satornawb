# PRD: Excel import/export и большие таблицы

## 1. Назначение

Закрыть практическую работу с большими WB-таблицами: Excel import/export, sticky columns, horizontal scroll, virtualization, validation preview и сохраненные представления.

## 2. Роли

- Мария: массово проверяет и выгружает данные.
- Менеджер: работает со своими SKU и export.
- Максим: выгружает финансовые/P&L отчеты.
- `settings_editor/finance_editor`: импортирует планы, себестоимость, расходы.
- Разработка: обеспечивает performance и validation.

## 3. Пользовательские сценарии

- Export текущего отчета с фильтрами, периодом и колонками.
- Import цен, себестоимости, планов или расходов через Excel.
- Preview import: валидные строки, ошибки, blocked rows, влияние на маржу.
- Работать с 1500+ SKU без лагов.
- Скроллить широкие таблицы, сохраняя фото/артикул.
- Сохранить column preset/saved view.

## 4. Данные

- import job;
- file metadata;
- sheet mapping;
- row validation result;
- affected entity;
- old/new values;
- blocked reason;
- actor;
- approval id;
- export snapshot metadata;
- table view config.

## 5. Таблицы и контролы

Общие требования:

- sticky фото/артикул;
- sticky header;
- horizontal scroll;
- vertical virtualization;
- column toggle;
- column presets;
- saved views;
- density for operational SaaS, без декоративных карточек;
- tooltips для сокращений.

Import:

- upload;
- mapping columns;
- validation;
- preview;
- approve/apply;
- audit.

Export:

- current view;
- all columns / visible columns;
- include metadata: period, filters, generated_at, source freshness;
- finance export only with permission.

## 6. Бизнес-правила

- Excel import никогда не отправляет цены напрямую в WB.
- Любой import с изменением цены, плана, COGS или расходов идет через approval.
- Ошибки строк не должны валить весь файл, если можно применить валидную часть после preview.
- Large import должен быть async job.
- Export не должен включать sensitive/token fields.
- Для financial export соблюдать `finance_viewer`.

## 7. Состояния

| State | Поведение |
|---|---|
| `uploading` | Progress |
| `validating` | Job status |
| `validation_error` | Ошибки по строкам |
| `partial_valid` | Можно применить валидные строки |
| `approval_required` | Нужен approval |
| `applying` | Async apply |
| `apply_failed` | Ошибка с retry/report |
| `export_ready` | Ссылка/статус готовности |
| `export_failed` | Повторить export |

## 8. Опасные действия

- import price changes;
- import COGS;
- import financial expenses;
- import plan values;
- apply partial import;
- export finance;
- delete saved view shared with team.

## 9. Что уже есть в Vella

- UI-pattern для больших таблиц;
- sticky и horizontal scroll в production shell;
- Excel import/export уже зафиксирован в ТЗ и PRD.

## 10. Что нужно доделать

- generic table infra;
- import job pipeline;
- row-level validation;
- preview UI;
- async apply;
- export generator;
- column presets/saved views persistence;
- performance checks.

## 11. v1 replacement minimum

- export для repricer/reports/P&L/RnP;
- import для цен и COGS/операционных расходов;
- import планов на минимальном уровне;
- sticky + virtualization for large tables;
- row validation + approval.

## 12. Production hardening

- import templates;
- versioned imports;
- rollback files;
- full 150k-row plan import;
- background exports;
- table performance budget.

## 13. P2 / change request

- full INDEEPA Excel parity до 150k строк по всем плановым матрицам;
- BI pivot builder;
- user-defined calculated columns.

## 14. Сложность

Оценка: 4-8 рабочих дней для v1 Excel/table layer. Full 150k-row planning parity: отдельный scope.

## 15. Открытые вопросы

- Какие import templates нужны первыми: цены, COGS, план, расходы?
- Нужен ли XLSX с несколькими листами или один лист на import type?
- Какие лимиты файла в v1?
- Нужно ли хранить исходный файл импорта?
- Какие exports можно отдавать менеджерам без финансового доступа?

