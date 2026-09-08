# Satorna delegation prompts

Каждый файл в этой папке — самостоятельный промпт для отдельного чата. Передавайте содержимое файла целиком. Общий контекст и ограничения уже продублированы внутри каждого промпта.

## Первая волна

Эти задачи дают максимальное ускорение и не пересекаются по файлам:

1. `01_frontend_canonical_finance.md`
2. `02_backend_health_readiness.md`
3. `04_abc_pnl_inventory.md`
4. `09_legacy_test_failures_triage.md`
5. `11_finance_observability_runbook.md`

## Вторая волна

1. `03_local_release_gate_runner.md`
2. `05_wb_funnel_advertising_discovery.md`
3. `06_wb_prices_stocks_discovery.md`
4. `07_economics_versions_discovery.md`
5. `08_ktr_source_discovery.md`

## Последующие независимые исследования

1. `12_repricer_global_state_audit.md`
2. `13_credentials_encryption_design.md`
3. `14_openapi_contract_inventory.md`
4. `15_tenant_ownership_audit.md`
5. `16_orders_production_discovery.md`
6. `17_kiz_pdf_pipeline_discovery.md`
7. `18_avito_multi_account_discovery.md`
8. `19_reviews_notifications_discovery.md`

Для автономного продолжения по актуальному handoff используйте
`20_continue_satorna_architecture.md`.

`10_fix_one_legacy_failure_batch.md` запускается только после результата `09_legacy_test_failures_triage.md`. Для нескольких пакетов исправлений создавайте отдельный чат на каждый пакет.

## Текущее состояние архитектуры

- Текущая production-ревизия backend: `b96e602`, Alembic `20260905_0060`.
- Оценка всей утверждённой архитектуры: выполнено около `77%`, осталось около `23%` с погрешностью примерно ±5 процентных пунктов.
- Главный источник фактов: `../SATORNA_ARCHITECTURE_HANDOFF.md`.
- Промпты `01`–`19` сохраняют исторический контекст своих bounded-задач;
  перед запуском сверяйте их состояние с актуальным handoff.

## Правила параллельности

- Один агент — один чат, worktree, branch и ограниченный набор файлов.
- Не давайте двум агентам одновременно изменять один файл или одну подсистему.
- Discovery-задачи не должны превращаться в реализацию.
- Ни один из этих агентов не уполномочен деплоить, менять production или использовать GitHub.
