# SATORNA: triage 105 legacy backend test failures

Дата: 2026-09-06

Исследованная база: `ddaf087233db46d85eada0ede2a23d48271ba89f` (`codex/satorna-canonical-funnel-ads-raw`)

Рабочая ветка: `codex/satorna-legacy-test-triage-20260906`

Статус: discovery/triage only. Production code, тесты, baseline, schema, migrations, compose/runtime role, handoff и production не изменялись.

## 1. Итог

Документированный baseline воспроизведён точно:

| Метрика | Результат |
|---|---:|
| Собрано тестов | 767 |
| Passed | 662 |
| Failed | 105 |
| Errors | 0 |
| Warnings | 15 |
| JUnit duration | 285.041 s |
| Documented failures | 105 |
| Новые failure IDs | 0 |
| Исчезнувшие failure IDs | 0 |

Все 105 failure IDs дополнительно воспроизведены:

- в 18 минимальных группах по test-файлам — в каждой группе фактический набор совпал с ожидаемым;
- по одному node ID в отдельном процессе — `105/105` снова упали, `0` неожиданно прошли, `0` errors, `0` timeouts.

Все авторитетные процессы получили отдельный runtime-state и полностью чистое
окружение с недоступными task-local DB, Redis, Celery broker/result backend и
OpenAI base URL. Поэтому текущий baseline не объясняется order dependence или
межтестовой cache contamination. Основная причина — рассинхронизация legacy tests
с production-overlay: `ed80c0f` перенёс 31 файл под `app/` и не перенёс ни одного
файла под `tests/`. Поверх этого обнаружены несколько узких реальных product
defects, уже исправленных в локальной sibling-lineage и перечисленных ниже.

## 2. Repository, worktree и dirty state

Авторитетный handoff указывает активную backend-lineage в `.worktrees/backend-satorna-canonical-advertising`, поэтому triage начат от её локального HEAD `ddaf087`, а не от расходящейся ветки `main` (`748888f`).

Создан отдельный worktree:

```text
/Users/ilagulakin/Desktop/Work/OgniWB/.worktrees/backend-satorna-legacy-test-triage-20260906
```

Исходный worktree был чистым. В canonical checkout до начала уже существовали пользовательские `M var/vella_repricer_runtime_state.json` и untracked `.venv`; они не изменялись и не восстанавливались. Первый диагностический запуск в новом worktree изменил только его собственную tracked-копию `var/vella_repricer_runtime_state.json`; файл оставлен как есть и исключён из commit. Все авторитетные повторные запуски использовали отдельные state-файлы под `/tmp`.

GitHub, production, Docker и реальные WB/Avito/OpenAI endpoints не использовались.

## 3. Воспроизведение

### 3.1. Окружение

Использован существующий project venv:

```text
/Users/ilagulakin/Desktop/Work/OgniWB/.worktrees/backend-satorna-period-finance/.venv/bin/python
Python 3.14.3
pytest 9.1.1
```

Первый проход наследовал benign environment и поэтому не считался достаточным
доказательством изоляции. Авторитетный повтор запущен через `env -i`: child
processes получили только фиксированный allowlist ниже, без credentials, proxy и
настроек внешних сервисов.

```text
CI=1
PYTHONUNBUFFERED=1
PATH=/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin
TMPDIR=/tmp
LANG=en_US.UTF-8
TZ=Europe/Moscow
VELLA_WB_API_MODE=fake
VELLA_AVITO_API_MODE=fake
VELLA_REAL_PRICE_APPLY_ENABLED=false
VELLA_WB_FEEDBACKS_SEND_ENABLED=false
VELLA_AVITO_REPRICER_PRICE_APPLY_ENABLED=false
VELLA_DATABASE_URL=postgresql+psycopg://satorna_gate@127.0.0.1:1/unreachable
VELLA_REDIS_URL=redis://127.0.0.1:1/15
VELLA_CELERY_BROKER_URL=redis://127.0.0.1:1/14
VELLA_CELERY_RESULT_BACKEND=redis://127.0.0.1:1/13
VELLA_OPENAI_API_BASE_URL=http://127.0.0.1:1/v1
VELLA_REPRICER_STATE_FILE=<fresh task directory>/runtime-state.json
```

Bounded-команда приведена в разделе 5. JUnit зафиксировал
`105 failed, 662 passed, 15 warnings in 285.06s`. После полной записи parseable
JUnit и десятисекундного grace period Python 3.14 остался в interpreter shutdown;
supervisor остановил только точный pytest PID через `SIGTERM` (`143`). Это
отдельная runner-level аномалия без test ID; группы и singleton-процессы
завершались штатно.

Проверенные artifact hashes:

```text
d1b34a6b71f4c28817d19268ff2dad7d71588f084132f30bb53efbd97b7b33db  full.xml
ad799d63d798bfcc0b7b6994c2a11a55c3a75d7a7e57ef564d8dc52019cac7de  full.log
819b61ad933b5cb6dd45f82671f7e1e96212b2a63194ee917dcf33b7349a8828  isolated-rerun-summary.json
```

### 3.2. Diff с baseline

Источник ожидания: `ops/legacy-test-failures.txt`, 105 уникальных IDs, историческая пометка `44cab60`.

```text
expected_count=105
actual_count=105
error_count=0
added_ids=[]
missing_ids=[]
status=exact
```

Ни отсутствие нового ID, ни отсутствие старого ID не интерпретировалось автоматически как улучшение или регрессия; оба множества пусты.

### 3.3. Минимальные группы

Каждая строка ниже запускалась отдельным pytest-процессом с clean allowlist,
unreachable DB/Redis/Celery/OpenAI endpoints и собственным JSON state.

| Test file | Selected IDs | Failed | Errors | Duration, s |
|---|---:|---:|---:|---:|
| `tests/test_app.py` | 1 | 1 | 0 | 1.137 |
| `tests/test_avito_orders.py` | 2 | 2 | 0 | 1.630 |
| `tests/test_avito_repricer_worker.py` | 1 | 1 | 0 | 0.657 |
| `tests/test_notifications.py` | 1 | 1 | 0 | 1.158 |
| `tests/test_one_c_cash_flow.py` | 1 | 1 | 0 | 0.949 |
| `tests/test_reports_sources_runtime.py` | 2 | 2 | 0 | 0.355 |
| `tests/test_repricer_cache_store.py` | 2 | 2 | 0 | 0.140 |
| `tests/test_repricer_tasks.py` | 12 | 12 | 0 | 0.640 |
| `tests/test_rnp_runtime.py` | 5 | 5 | 0 | 0.417 |
| `tests/test_sprint_b_workflow.py` | 4 | 4 | 0 | 1.270 |
| `tests/test_sprint_c_strategies.py` | 2 | 2 | 0 | 1.092 |
| `tests/test_sprint_d_reports.py` | 20 | 20 | 0 | 1.411 |
| `tests/test_stock_report_cache_persistence.py` | 1 | 1 | 0 | 0.548 |
| `tests/test_wb_adapter_probes.py` | 1 | 1 | 0 | 0.098 |
| `tests/test_wb_reports_bff.py` | 15 | 15 | 0 | 20.235 |
| `tests/test_wb_repricer_bff.py` | 31 | 31 | 0 | 2.891 |
| `tests/test_wb_reviews.py` | 3 | 3 | 0 | 1.000 |
| `tests/test_wb_sync_plan.py` | 1 | 1 | 0 | 0.016 |

Artifacts triage-run находились в:

```text
/tmp/satorna-triage-isolated.MFSsRo/full.xml
/tmp/satorna-triage-isolated.MFSsRo/full.log
/tmp/satorna-triage-isolated.MFSsRo/isolated-rerun-summary.json
/tmp/satorna-triage-isolated.MFSsRo/{groups,singletons}
```

Они намеренно не добавлены в repository.

## 4. Root-cause evidence и классификация

### 4.1. Исторический разлом

`ed80c0f` (`chore: capture Satorna production b749fe1 baseline`) имеет parent `13cba53` и изменил 57 tracked files: 31 под `app/`, 0 под `tests/`, остальные — migrations/contracts/config. Среди заменённых общих путей находятся `repricer_bff.py`, `repricer_cache/store.py`, `repricer_tasks.py`, `wb_reports_sprint_d.py`, `wb_sync_plan.py`, `routers/wb_reports_bff.py` и `routers/wb_repricer_bff.py`.

Локальная sibling-ветка `codex/wb-abc-production` независимо прошла тот же разлом и содержит узкие commits, которые либо исправляют product defect, либо переводят старые tests на cache-only/current-schema contract. Они используются только как локальное evidence; wholesale cherry-pick не рекомендуется, потому что ветки расходятся (`ddaf087...8c91d35`: 92/47 commits).

Наиболее сильные anchors:

- `7052537` — null WB probe field;
- `165e432` — Avito source-driven enrichment/fixtures;
- `ba2c3c3` — shadowed strategy catalog route;
- `7c7f013`, `e503687`, `d90eb15` — canonical blocker IDs и P&L TTL;
- `7bf5cf6` — exact cache-only background reports;
- `9360ea2` — cache-only repricer reads;
- `22ab4a7`, `cb7b0ea`, `fae5af5`, `177b75c`, `c9df3a7`, `0d428bc`, `071c246` — legacy test-contract realignment.

### 4.2. Категории

Категории ниже не взаимоисключающие; каждый test ID при этом принадлежит ровно одному файловому batch.

| Категория из задания | Вывод |
|---|---|
| Реальная продуктовая ошибка | Подтверждена в B01–B06: null-field probe, лишний Avito fetch, duplicate route, неканонические ads blocker IDs, 24h вместо 2h P&L TTL, inline/cache/job defects, два cache-only repricer edge cases. |
| Устаревший contract теста | Основная причина; присутствует в B02–B13. Tests всё ещё ожидают demo/live builders, старые cache keys/version/envelope, старый finance basis и старый sync profile. |
| Wall-clock/timezone | Не является первичной причиной ни одного из 105 IDs. Все IDs повторились singleton; даты в релевантных fixtures фиксированы. Runner shutdown hang вынесен отдельно. |
| Shared mutable/module state | Вклад в B06: legacy SKU settings/liquidation tests ожидают прежнюю module-state hydration. Singleton reproduction исключает зависимость от другого теста. |
| Order dependence | Исключена для baseline: 105/105 падают singleton в отдельных процессах. |
| Сеть/credentials | Вклад в B02, B06, B08: отсутствующие test token/strategy assignment и новые credential gates. Реальных network calls не было. |
| DB/JSON/in-memory fallback | Подтверждена в B10 и частично B06: tests предполагали прежний implicit store; isolated unreachable DB требует явного local cache fixture. |
| Cache contamination | Межтестовая contamination исключена clean-env singleton-прогонами с недоступным shared Redis. Cache contract/version/range drift остаётся причиной B04–B07, но это не contamination. |
| Authorization drift | Подтверждена в B06/B08: защищённые recommendation/worker routes вызываются без актуального auth/token fixture. |
| Fixture/schema drift | Подтверждена в B02, B04–B07, B09, B11, B12: новые metadata, source readiness, retry count, review policy и payload fields отсутствуют в fixtures. |

## 5. Общий verification contract для batch-агентов

Каждый batch должен выполняться в свежем worktree, clean environment и с новым
state-файлом. Interpreter здесь намеренно разрешён в существующий проверенный
project venv; перед запуском он валидируется.

```bash
PY=/Users/ilagulakin/Desktop/Work/OgniWB/.worktrees/backend-satorna-period-finance/.venv/bin/python
[ -x "$PY" ] || { echo "missing project python: $PY" >&2; exit 2; }
TRIAGE_TMP="$(mktemp -d)"
SAFE_ENV=(
  PATH=/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin
  TMPDIR=/tmp
  LANG=en_US.UTF-8
  TZ=Europe/Moscow
  CI=1
  PYTHONUNBUFFERED=1
  VELLA_WB_API_MODE=fake
  VELLA_AVITO_API_MODE=fake
  VELLA_REAL_PRICE_APPLY_ENABLED=false
  VELLA_WB_FEEDBACKS_SEND_ENABLED=false
  VELLA_AVITO_REPRICER_PRICE_APPLY_ENABLED=false
  VELLA_DATABASE_URL=postgresql+psycopg://satorna_gate@127.0.0.1:1/unreachable
  VELLA_REDIS_URL=redis://127.0.0.1:1/15
  VELLA_CELERY_BROKER_URL=redis://127.0.0.1:1/14
  VELLA_CELERY_RESULT_BACKEND=redis://127.0.0.1:1/13
  VELLA_OPENAI_API_BASE_URL=http://127.0.0.1:1/v1
)
run_isolated() {
  local run_state
  run_state="$(mktemp -d "$TRIAGE_TMP/run.XXXXXX")" || return
  env -i "${SAFE_ENV[@]}" \
    VELLA_REPRICER_STATE_FILE="$run_state/runtime-state.json" \
    "$PY" "$@"
}
```

Targeted-команды ниже вызывают `run_isolated`. После них нужен один bounded full
suite. Supervisor ждёт parseable JUnit, даёт interpreter десять секунд на штатный
exit и только затем останавливает точный PID; общий deadline — 10 минут.

```bash
FULL_STATE="$(mktemp -d "$TRIAGE_TMP/full.XXXXXX")"
env -i "${SAFE_ENV[@]}" \
  VELLA_REPRICER_STATE_FILE="$FULL_STATE/runtime-state.json" \
  "$PY" -m pytest -q --tb=no --no-summary \
  -o junit_family=legacy --junitxml="$TRIAGE_TMP/full.xml" tests \
  >"$TRIAGE_TMP/full.log" 2>&1 &
PYTEST_PID=$!
STARTED=$SECONDS
XML_READY=-1
while kill -0 "$PYTEST_PID" 2>/dev/null; do
  if "$PY" -c 'from xml.etree import ElementTree; import sys; ElementTree.parse(sys.argv[1])' \
      "$TRIAGE_TMP/full.xml" 2>/dev/null; then
    (( XML_READY < 0 )) && XML_READY=$SECONDS
    if (( SECONDS - XML_READY >= 10 )); then
      kill -TERM "$PYTEST_PID"
      break
    fi
  fi
  if (( SECONDS - STARTED >= 600 )); then
    kill -TERM "$PYTEST_PID" 2>/dev/null || true
    wait "$PYTEST_PID" 2>/dev/null || true
    echo "full suite timeout" >&2
    exit 124
  fi
  sleep 2
done
PYTEST_RC=0
wait "$PYTEST_PID" || PYTEST_RC=$?
case "$PYTEST_RC" in 0|1|143) ;; *) exit "$PYTEST_RC" ;; esac

"$PY" - "$TRIAGE_TMP/full.xml" <<'PY'
from pathlib import Path
import sys
from ops.release_gate import junit_failure_ids

expected = {
    line for raw in Path("ops/legacy-test-failures.txt").read_text().splitlines()
    if (line := raw.strip()) and not line.startswith("#")
}
actual, errors = junit_failure_ids(Path(sys.argv[1]))
result = {
    "remaining": len(actual),
    "removed": sorted(expected - actual),
    "added": sorted(actual - expected),
    "errors": sorted(errors),
}
print(result)
raise SystemExit(bool(result["added"] or result["errors"]))
PY
```

Критерий: `added=[]`, `errors=[]`, `removed` в точности равен IDs выбранного batch; при последовательном выполнении — union уже исправленных batches. `ops/legacy-test-failures.txt` batch-агенты не меняют: его один раз обновляет интегратор, иначе независимые ветки конфликтуют в одном общем файле.

## 6. Рекомендуемые непересекающиеся batches

### B01 — WB probe null semantics

- **Delta:** 1 failure; после одиночного fix остаётся 104.
- **Категории:** реальная продуктовая ошибка; fixture/schema drift.
- **Разрешённые файлы:** `app/discovery/repricer_probes.py`, `tests/test_wb_adapter_probes.py`.
- **Test IDs:**
  - `tests/test_wb_adapter_probes.py::test_read_prices_probe_keeps_wb06_blocked_without_spp_or_buyer_price_fields`
- **Root cause:** `_has_field_path` считает присутствующий `null` валидным значением. Поэтому `clubDiscount: null` ошибочно закрывает обязательный WB-06 field.
- **Evidence:** singleton assertion показывает лишний `clubDiscount`; функция имеет один общий путь через `_fields_present`. Локальный `7052537` заменяет финальный `return True` на `return current is not None`.
- **Минимальный fix:** применить только null-check в общей функции; тест менять лишь если нужно добавить regression case. Не расширять schema и не вводить новый validator.
- **Риск:** низкий; убедиться, что `0`, `False` и пустая строка остаются «поле присутствует», а только `None` — отсутствует.
- **Targeted verification:**
  ```bash
  run_isolated -m pytest -q tests/test_wb_adapter_probes.py
  ```

### B02 — Avito source-driven enrichment и fixtures

- **Delta:** 3 failures; после B01–B02 остаётся 101.
- **Категории:** реальная продуктовая ошибка; сеть/credentials; fixture/schema drift; устаревший contract теста.
- **Разрешённые файлы:** `app/routers/avito_orders.py`, `tests/test_avito_orders.py`, `tests/test_avito_repricer_worker.py`.
- **Test IDs:**
  - `tests/test_avito_orders.py::test_avito_orders_endpoint_ignores_blocked_cache_and_refetches`
  - `tests/test_avito_orders.py::test_avito_orders_picking_list_xlsx_matches_avito_order_rows`
  - `tests/test_avito_repricer_worker.py::test_avito_scheduler_execute_creates_pending_approval_when_real_apply_disabled`
- **Root cause:** общий picking path запрашивает listings даже когда order items уже полны; blocked-cache monkeypatch подменяет все cache keys, fixture не содержит новых `size/color/imageUrl`; worker fixture не назначает стратегию и поэтому закономерно создаёт 0 approvals.
- **Evidence:** `KeyError F6`, `IndexError` и `0 == 1` повторяются singleton. `_enrich_orders_for_picking` вызывается двумя endpoint paths и не имеет раннего guard. Локальный `165e432` содержит ровно guard, complete order fixture, key-scoped cache mock и strategy assignment.
- **Минимальный fix:** один early return по `_missing_detail_item_ids(rows)` до cache/client creation; дополнить fixture и ограничить blocked mock ключами `avito_orders:`; назначить стратегию в worker test.
- **Риск:** средний; guard не должен пропустить item, у которого отсутствует хотя бы одно поле, и tests не должны разрешать live HTTP.
- **Targeted verification:**
  ```bash
  run_isolated -m pytest -q \
    tests/test_avito_orders.py tests/test_avito_repricer_worker.py
  ```

### B03 — единственный strategy catalog route

- **Delta:** 2 failures; после B01–B03 остаётся 99.
- **Категории:** реальная продуктовая ошибка; устаревший contract теста.
- **Разрешённые файлы:** `app/routers/wb_repricer_sprint_c.py`, `tests/test_sprint_c_strategies.py`.
- **Test IDs:**
  - `tests/test_sprint_c_strategies.py::test_4600_requires_mode_then_supports_percent_rub_floor`
  - `tests/test_sprint_c_strategies.py::test_sprint_c_catalog_defaults_include_disabled_4445_and_night_off`
- **Root cause:** Sprint C регистрирует `/strategies/catalog`, который дублирует BFF route и в зависимости от include order перехватывает contract; dry-run test одновременно проверяет router integration вместо чистой 4600-domain logic.
- **Evidence:** catalog отвечает `409`, dry-run теряет ожидаемые `500`; `rg` находит два route decorators. Локальный `ba2c3c3` удаляет shadow route и проверяет catalog/guard через domain API.
- **Минимальный fix:** удалить только duplicate Sprint C route/imports; domain tests вызвать через `list_strategy_catalog` и `run_strategy_item_with_guards`. BFF catalog route не менять.
- **Риск:** средний; OpenAPI должен содержать ровно один catalog operation, остальные Sprint C routes обязаны сохраниться.
- **Targeted verification:**
  ```bash
  run_isolated -m pytest -q tests/test_sprint_c_strategies.py
  ```

### B04 — Sprint D/RNP cache contract и response invariants

- **Delta:** 25 failures; после B01–B04 остаётся 74.
- **Категории:** реальная продуктовая ошибка; устаревший contract теста; fixture/schema drift; cache contract drift.
- **Разрешённые файлы:** `app/wb_reports_sprint_d.py`, `app/wb_api/rnp_runtime.py`, `tests/test_sprint_d_reports.py`, `tests/test_rnp_runtime.py`.
- **Test IDs:**
  - `tests/test_rnp_runtime.py::test_build_rnp_snapshot_does_not_block_funnel_on_optional_warehouse_snapshot`
  - `tests/test_rnp_runtime.py::test_build_rnp_snapshot_does_not_create_ads_only_rows_when_funnel_is_blocked`
  - `tests/test_rnp_runtime.py::test_build_rnp_snapshot_keeps_ads_metrics_unknown_when_ads_source_is_partial`
  - `tests/test_rnp_runtime.py::test_build_rnp_snapshot_merges_cached_sales_funnel_with_ads`
  - `tests/test_rnp_runtime.py::test_build_rnp_snapshot_reads_report_cache_without_refetching_wb`
  - `tests/test_sprint_d_reports.py::test_abc_report_keeps_funnel_opens_separate_when_impressions_missing`
  - `tests/test_sprint_d_reports.py::test_abc_report_net_profit_uses_full_finance_formula`
  - `tests/test_sprint_d_reports.py::test_abc_report_prefers_sales_funnel_orders_and_buyouts_for_portal_metrics`
  - `tests/test_sprint_d_reports.py::test_abc_report_uses_covering_repricer_daily_cache`
  - `tests/test_sprint_d_reports.py::test_abc_report_uses_repricer_period_cache_without_own_report_cache`
  - `tests/test_sprint_d_reports.py::test_abc_report_without_cache_returns_empty_backend_state_not_static_summary`
  - `tests/test_sprint_d_reports.py::test_ads_bff_exposes_confirmed_budget_balance_upd_and_daily_sources`
  - `tests/test_sprint_d_reports.py::test_ads_bff_refreshes_and_reuses_cached_report_payload`
  - `tests/test_sprint_d_reports.py::test_ads_weak_attribution_stays_campaign_level_and_not_sku_level`
  - `tests/test_sprint_d_reports.py::test_bff_abc_returns_sku_rows_not_summary_only`
  - `tests/test_sprint_d_reports.py::test_bff_abc_uses_repricer_rows_when_report_cache_is_empty`
  - `tests/test_sprint_d_reports.py::test_pnl_finance_cache_does_not_require_live_ads_token`
  - `tests/test_sprint_d_reports.py::test_pnl_finance_cache_normalizes_negative_revenue_rows`
  - `tests/test_sprint_d_reports.py::test_pnl_finance_viewer_gets_financial_fields_and_preliminary_state`
  - `tests/test_sprint_d_reports.py::test_pnl_report_response_is_cached_for_two_hours`
  - `tests/test_sprint_d_reports.py::test_pnl_supports_operative_and_final_states`
  - `tests/test_sprint_d_reports.py::test_pnl_uses_repricer_finance_cache_before_legacy_runtime`
  - `tests/test_sprint_d_reports.py::test_pnl_uses_repricing_period_cache_when_exact_range_cache_is_missing`
  - `tests/test_sprint_d_reports.py::test_rnp_has_confirmed_drr_formula_and_finance_viewer_can_see_roi`
  - `tests/test_sprint_d_reports.py::test_viewer_sees_all_financial_sections_except_monthly_company_costs`
- **Root cause:** runtime уже читает `baskets_<range>`/`ads_<range>` и `rnp_report_v5`, но tests monkeypatch removed `build_ads_attribution_snapshot` и `rnp_funnel_v2/v4`; Sprint D tests зависят от удалённых demo rows/live builders и старых finance/cache envelopes. Отдельно production возвращает `WB_ADS_CACHE_EMPTY` там, где Pydantic contract требует `WB-02`, и держит P&L fresh 24h вместо 2h.
- **Evidence:** 4 RNP AttributeErrors на удалённом builder, cache miss `missing != hit`, Pydantic validation errors про `WB-02`, `2 == 1` на TTL и blocked/empty finance rows. Локальные `cb7b0ea`, `7c7f013`, `e503687`, `d90eb15` изолируют соответствующие причины; `516a298` и `748888f` показывают текущий finance/cache contract.
- **Минимальный fix:** два blocker literals заменить на `WB-02`, TTL вернуть к 2h; RNP fixtures перевести на `baskets/ads` aggregates и v5 key; удалить/переписать только assertions, зависящие от статических demo/live paths, не возвращая сетевые fetches в read path.
- **Риск:** высокий; нельзя менять canonical v2 finance/period, превращать unknown в zero, восстанавливать live WB calls или ослаблять Pydantic blocker invariants.
- **Targeted verification:**
  ```bash
  run_isolated -m pytest -q \
    tests/test_rnp_runtime.py tests/test_sprint_d_reports.py
  ```

### B05 — exact cache-only generic reports

- **Delta:** 15 failures; после B01–B05 остаётся 59.
- **Категории:** реальная продуктовая ошибка; устаревший contract теста; fixture/schema drift.
- **Разрешённые файлы:** `app/routers/wb_reports_bff.py`, `tests/test_wb_reports_bff.py`.
- **Test IDs:**
  - `tests/test_wb_reports_bff.py::test_bff_digest_degrades_when_ads_token_is_missing`
  - `tests/test_wb_reports_bff.py::test_bff_rnp_endpoint_returns_full_backend_funnel_shape`
  - `tests/test_wb_reports_bff.py::test_bff_stock_and_week_over_week_endpoints_return_rows`
  - `tests/test_wb_reports_bff.py::test_digest_endpoint_reports_missing_cache_without_calling_wb`
  - `tests/test_wb_reports_bff.py::test_digest_read_uses_cached_result_without_calling_wb`
  - `tests/test_wb_reports_bff.py::test_latest_report_payload_cache_respects_requested_range`
  - `tests/test_wb_reports_bff.py::test_report_daily_sources_ready_accepts_covering_daily_detail`
  - `tests/test_wb_reports_bff.py::test_starting_pnl_job_immediately_exposes_cash_flow_job_to_1c`
  - `tests/test_wb_reports_bff.py::test_stock_report_payload_groups_warehouses_by_product_with_catalog_meta`
  - `tests/test_wb_reports_bff.py::test_week_over_week_get_returns_cached_payload_while_job_is_running`
  - `tests/test_wb_reports_bff.py::test_week_over_week_get_returns_completed_cached_job_payload`
  - `tests/test_wb_reports_bff.py::test_week_over_week_get_returns_missing_background_report_without_cache`
  - `tests/test_wb_reports_bff.py::test_week_over_week_job_endpoint_reuses_completed_cached_report`
  - `tests/test_wb_reports_bff.py::test_week_over_week_live_builder_uses_own_sources_not_abc_or_repricer`
  - `tests/test_wb_reports_bff.py::test_week_over_week_task_builds_current_and_previous_source_ranges`
- **Root cause:** generic read path смешивает special-case inline builders и exact cached background reports; tests частично monkeypatch удалённый `build_wb_reports_sources_snapshot`, а payload/job fixtures имеют старые version/range/state shapes. Stock descriptor потерял `marketplaceStockUnits`; P&L waiting response может не отдать уже созданный cash-flow.
- **Evidence:** 6 AttributeErrors на удалённых builders, unexpected enqueue, empty cached rows, missing stock column, range cache miss и `KeyError args`. Локальный `7bf5cf6` объединяет `{week-over-week,pnl,rnp,ads,stock}` в один cache-only branch, сохраняет running job, создаёт cash-flow до readiness check и bump-ит stock payload v5→v6.
- **Минимальный fix:** применить узкий production diff `7bf5cf6` вручную с учётом текущего HEAD и синхронно обновить fixtures/assertions. Не переносить весь commit и не менять report producers вне разрешённых файлов.
- **Риск:** высокий; cached payload должен соответствовать точному org/range/group/source, active job не должен становиться completed, HTTP GET не должен вызвать WB.
- **Targeted verification:**
  ```bash
  run_isolated -m pytest -q tests/test_wb_reports_bff.py
  ```

### B06 — WB repricer cache-only/current-contract boundary

- **Delta:** 31 failures; после B01–B06 остаётся 28.
- **Категории:** реальная продуктовая ошибка; устаревший contract теста; shared mutable/module state; сеть/credentials; authorization drift; fixture/schema drift.
- **Разрешённые файлы:** `app/routers/wb_repricer_bff.py`, `tests/test_wb_repricer_bff.py`.
- **Test IDs:**
  - `tests/test_wb_repricer_bff.py::test_ads_spend_aggregates_reports_progress_by_campaign_batches`
  - `tests/test_wb_repricer_bff.py::test_baskets_detail_job_merges_exact_cache_and_cache_hit_avoids_duplicate`
  - `tests/test_wb_repricer_bff.py::test_baskets_detail_start_marks_stale_active_run_failed_and_starts_new`
  - `tests/test_wb_repricer_bff.py::test_baskets_detail_start_rejects_second_active_run_for_same_org`
  - `tests/test_wb_repricer_bff.py::test_baskets_detail_start_reuses_same_range_active_run`
  - `tests/test_wb_repricer_bff.py::test_build_sku_row_can_account_spp_plus_configured_wallet`
  - `tests/test_wb_repricer_bff.py::test_build_sku_row_margin_uses_planned_indeepa_formula_and_tariff_commission`
  - `tests/test_wb_repricer_bff.py::test_build_sku_row_uses_orders_spp_when_live_buyer_price_is_missing`
  - `tests/test_wb_repricer_bff.py::test_cyrillic_longsleeve_article_uses_longsleeve_defaults_and_official_spp`
  - `tests/test_wb_repricer_bff.py::test_finance_net_profit_subtracts_wb_costs_cogs_ads_and_other_expenses_without_tax`
  - `tests/test_wb_repricer_bff.py::test_finance_report_revenue_uses_sales_minus_returns_by_seller_discount_price`
  - `tests/test_wb_repricer_bff.py::test_manual_cold_full_sync_enqueues_onboarding_task`
  - `tests/test_wb_repricer_bff.py::test_period_source_cache_uses_covering_detail_cache_without_sync_status`
  - `tests/test_wb_repricer_bff.py::test_refresh_ads_endpoint_does_not_force_start_over_running_sync`
  - `tests/test_wb_repricer_bff.py::test_refresh_ads_endpoint_starts_background_sync_without_waiting_for_fullstats`
  - `tests/test_wb_repricer_bff.py::test_repricer_bff_frontend_strategy_catalog_and_sku_shape`
  - `tests/test_wb_repricer_bff.py::test_repricer_bff_liquidation_and_changelog_routes_work`
  - `tests/test_wb_repricer_bff.py::test_repricer_bff_sku_settings_match_frontend_shape`
  - `tests/test_wb_repricer_bff.py::test_repricer_list_summary_backfills_missing_other_expenses_from_revenue`
  - `tests/test_wb_repricer_bff.py::test_repricer_sku_list_blocks_cached_goods_without_user_wb_token`
  - `tests/test_wb_repricer_bff.py::test_repricer_sku_list_uses_covering_month_sync_daily_cache_for_week`
  - `tests/test_wb_repricer_bff.py::test_repricer_stats_endpoint_returns_backend_diagnostics`
  - `tests/test_wb_repricer_bff.py::test_repricer_stats_summary_uses_full_filtered_slice_not_first_page`
  - `tests/test_wb_repricer_bff.py::test_repricer_stats_uses_available_cache_range_when_requested_range_is_missing`
  - `tests/test_wb_repricer_bff.py::test_sku_list_page_limits_backend_row_build_for_unfiltered_first_page`
  - `tests/test_wb_repricer_bff.py::test_sync_status_marks_onboarding_partial_without_daily_baskets_detail`
  - `tests/test_wb_repricer_bff.py::test_sync_status_marks_onboarding_plan_queued`
  - `tests/test_wb_repricer_bff.py::test_wb_sync_can_opt_into_daily_baskets_detail`
  - `tests/test_wb_repricer_bff.py::test_wb_sync_runs_four_independent_sources_in_parallel_and_waits_for_goods`
  - `tests/test_wb_repricer_bff.py::test_worker_status_returns_next_run_and_recent_scheduler_logs`
  - `tests/test_wb_repricer_bff.py::test_worker_status_without_runs_uses_stable_interval_boundary`
- **Root cause:** один монолитный legacy test file остался на pre-overlay finance formulas, cache envelope/signatures, 8-source sync plan, strategy count и permissive auth. Current read path должен быть cache-only, но на HEAD остаются два узких product edge cases: `content_cards` может вернуть `None`, и list endpoint не передаёт явный `wb_token=None`, поэтому read пытается разрешить user credential.
- **Evidence:** deterministic `409/401`, missing settings/module data, старые expected formula values, `max_items`/`require_full_sync_coverage` signature mismatches, 8 против 9 sync sources. Локальный `9360ea2` исправляет только два production lines; `73b127e`…`748888f` и test part `9360ea2` фиксируют contract expectations в sibling-lineage.
- **Минимальный fix:** сначала внести две cache-only production правки из `9360ea2`, затем перенести только релевантные fixture/assertion изменения к текущим formulas/cache keys/signatures/auth. Не откатывать production к старым assertions и не менять canonical finance/period modules.
- **Риск:** высокий; финансовые ожидания нельзя «подогнать» без сверки с текущим formula contract; GET list не должен ходить в WB; tenant/auth guards нельзя ослаблять; module-state fixtures должны быть локальны тесту.
- **Targeted verification:**
  ```bash
  run_isolated -m pytest -q tests/test_wb_repricer_bff.py
  ```

### B07 — scheduler, report tasks и sync profiles

- **Delta:** 15 failures; после B01–B07 остаётся 13.
- **Категории:** устаревший contract теста; fixture/schema drift; cache contract drift; DB/JSON fallback.
- **Разрешённые файлы:** `tests/test_repricer_tasks.py`, `tests/test_wb_sync_plan.py`, `tests/test_one_c_cash_flow.py`, `tests/test_stock_report_cache_persistence.py`.
- **Test IDs:**
  - `tests/test_one_c_cash_flow.py::test_cash_flow_job_queue_roundtrip_and_pnl_attachment`
  - `tests/test_repricer_tasks.py::test_ads_report_task_presyncs_exact_range_before_building`
  - `tests/test_repricer_tasks.py::test_digest_task_presyncs_report_sources_before_building`
  - `tests/test_repricer_tasks.py::test_nightly_wb_sync_skips_recent_reconciliation`
  - `tests/test_repricer_tasks.py::test_onboarding_readiness_requires_daily_baskets_detail`
  - `tests/test_repricer_tasks.py::test_pnl_report_task_waits_for_1c_before_building`
  - `tests/test_repricer_tasks.py::test_report_snapshot_source_ready_accepts_covering_daily_detail`
  - `tests/test_repricer_tasks.py::test_rnp_report_task_presyncs_funnel_sources_before_building`
  - `tests/test_repricer_tasks.py::test_scheduler_execute_loads_full_cached_goods_list`
  - `tests/test_repricer_tasks.py::test_scheduler_wb_sync_replaces_stale_status_before_running_profiles`
  - `tests/test_repricer_tasks.py::test_scheduler_wb_sync_respects_recent_manual_sync`
  - `tests/test_repricer_tasks.py::test_scheduler_wb_sync_runs_due_periodic_windows`
  - `tests/test_repricer_tasks.py::test_stock_report_task_presyncs_exact_range_before_building`
  - `tests/test_stock_report_cache_persistence.py::test_background_report_job_fails_when_payload_is_not_persisted`
  - `tests/test_wb_sync_plan.py::test_periodic_profiles_use_short_refresh_windows`
- **Root cause:** report tasks теперь ждут source readiness и строят только из cache, но tests ожидают inline presync и monkeypatch removed live builder. Sync profiles теперь включают `goods`/current-basis `finance`, daily baskets readiness и дополнительный `sku-snapshot`; tests используют старые cache metadata/status shapes. 1C/stock tests не открывают readiness gate и ожидают старые cash-flow IDs.
- **Evidence:** 3 AttributeErrors/waiting states на старых builders, `('goods','period-stats') != ('period-stats',)`, `('finance','baskets') != ('baskets',)`, stale status `KeyError state`, missing `cashFlow`. Локальные `22ab4a7`, `fae5af5`, `c9df3a7` меняют только tests для этих путей; `748888f` содержит profile/schema transition.
- **Минимальный fix:** перевести task tests на explicit `_report_snapshot_sources_ready=(True, [])`, запретить inline refresh, использовать cached builders; обновить profile/cache fixtures и OneC IDs. Production в этом batch не менять; новый доказанный defect получает отдельный bounded batch и review.
- **Риск:** средне-высокий; task не должен silently строить report на неполных daily sources, но и не должен выполнять WB network внутри cache-only build.
- **Targeted verification:**
  ```bash
  run_isolated -m pytest -q \
    tests/test_repricer_tasks.py tests/test_wb_sync_plan.py \
    tests/test_one_c_cash_flow.py tests/test_stock_report_cache_persistence.py
  ```

### B08 — Sprint B auth/credential fixtures

- **Delta:** 4 failures; после B01–B08 остаётся 9.
- **Категории:** authorization drift; сеть/credentials; устаревший contract теста.
- **Разрешённые файлы:** `tests/test_sprint_b_workflow.py`.
- **Test IDs:**
  - `tests/test_sprint_b_workflow.py::test_apply_failure_has_retry_and_retry_can_recover`
  - `tests/test_sprint_b_workflow.py::test_draft_approval_and_apply_flow_reaches_accepted_with_feature_flag_enabled`
  - `tests/test_sprint_b_workflow.py::test_draft_blocks_when_required_inputs_are_missing`
  - `tests/test_sprint_b_workflow.py::test_recommendation_includes_formula_version_and_source_snapshot`
- **Root cause:** recommendation вызывается без authenticated actor (`401`), остальные flows проходят auth, но не предоставляют обязательный cabinet WB token (`409`). Это test setup drift, не основание ослаблять endpoint security.
- **Evidence:** все четыре singleton; локальный `177b75c` добавляет authenticated header и autouse token fixture, не меняя production.
- **Минимальный fix:** только test auth header и deterministic `get_user_wb_token_secret` fixture.
- **Риск:** низкий; не подменять permission check и не включать real apply/network.
- **Targeted verification:**
  ```bash
  run_isolated -m pytest -q tests/test_sprint_b_workflow.py
  ```

### B09 — source-cache metadata schema

- **Delta:** 2 failures; после B01–B09 остаётся 7.
- **Категории:** fixture/schema drift; устаревший contract теста.
- **Разрешённые файлы:** `tests/test_repricer_cache_store.py`.
- **Test IDs:**
  - `tests/test_repricer_cache_store.py::test_list_source_cache_ranges_avoids_payload_and_parses_legacy_key`
  - `tests/test_repricer_cache_store.py::test_source_cache_metadata_is_derived_without_mutating_payload`
- **Root cause:** metadata contract добавил `finance_schema_version` и `revenue_basis`; tests ожидают точное старое dict и legacy row без новых keys.
- **Evidence:** один exact-dict diff с двумя extra fields и один `KeyError revenue_basis`; transition присутствует в `748888f/3e534f1`.
- **Минимальный fix:** обновить expected metadata, сохранив проверку, что исходный payload не мутирует и list query не загружает payload.
- **Риск:** низкий; не удалять current-basis metadata из production ради старого exact dict.
- **Targeted verification:**
  ```bash
  run_isolated -m pytest -q tests/test_repricer_cache_store.py
  ```

### B10 — notifications store isolation

- **Delta:** 1 failure; после B01–B10 остаётся 6.
- **Категории:** DB/JSON/in-memory fallback; устаревший contract теста.
- **Разрешённые файлы:** `tests/test_notifications.py`.
- **Test IDs:**
  - `tests/test_notifications.py::test_notifications_api_returns_and_marks_wb_sync_event_read`
- **Root cause:** integration test полагается на implicit process store при unreachable DB; current notification service использует source-cache boundary, поэтому запись затем не находится (`StopIteration`).
- **Evidence:** singleton failure; локальный `fae5af5` вводит локальный dict через `get_source_cache/save_source_cache`, production не меняется.
- **Минимальный fix:** явный in-test cache fixture с org/key semantics.
- **Риск:** низкий; fixture не должен протекать между tests или маскировать tenant key.
- **Targeted verification:**
  ```bash
  run_isolated -m pytest -q tests/test_notifications.py
  ```

### B11 — report-source retry/current runtime contract

- **Delta:** 2 failures; после B01–B11 остаётся 4.
- **Категории:** fixture/schema drift; устаревший contract теста.
- **Разрешённые файлы:** `tests/test_reports_sources_runtime.py`.
- **Test IDs:**
  - `tests/test_reports_sources_runtime.py::test_pnl_report_uses_realization_details_and_finance_reconciliation`
  - `tests/test_reports_sources_runtime.py::test_stock_report_wb_warehouses_keeps_rows_when_next_page_is_rate_limited`
- **Root cause:** stock loader теперь делает bounded retry `STOCK_REPORT_MAX_ATTEMPTS`, а test всё ещё ожидает один 429 attempt; второй test вызывает legacy P&L demo path без current finance cache и потому закономерно получает `blocked`, а не `final`.
- **Evidence:** offsets `[0,1000,1000,1000,1000]` против `[0,1000]`; blocked/final mismatch. Локальный `fae5af5` использует exported retry constant и удаляет stale cross-module P&L assertion.
- **Минимальный fix:** assertion связать с `STOCK_REPORT_MAX_ATTEMPTS`; удалить только obsolete P&L test, уже покрытый Sprint D/current finance suites.
- **Риск:** низкий; не уменьшать production retry policy ради старого expected call count.
- **Targeted verification:**
  ```bash
  run_isolated -m pytest -q tests/test_reports_sources_runtime.py
  ```

### B12 — review generation policy fixture

- **Delta:** 3 failures; после B01–B12 остаётся 1.
- **Категории:** fixture/schema drift; authorization drift; устаревший contract теста.
- **Разрешённые файлы:** `tests/test_wb_reviews.py`.
- **Test IDs:**
  - `tests/test_wb_reviews.py::test_reviews_send_requires_reviews_send_permission`
  - `tests/test_wb_reviews.py::test_reviews_sync_generate_approve_and_send_workflow`
  - `tests/test_wb_reviews.py::test_safe_review_generation_stays_draft_only_without_live_send`
- **Root cause:** AI generation теперь требует configured prompt/low-star policy. Setup получает `409`; permission test затем каскадно обращается к отсутствующему `data`. Safe generation contract теперь требует approval вместо `not_required`.
- **Evidence:** два `409`, затем `KeyError data`; локальный `0d428bc` конфигурирует policy через public settings endpoint и ожидает `approvalState=required`, production не меняется.
- **Минимальный fix:** test helper для `aiPrompt` + `lowStarsAction=draft`, вызвать перед generation, обновить safe approval assertion.
- **Риск:** низкий; не ослаблять permission и не разрешать external send.
- **Targeted verification:**
  ```bash
  run_isolated -m pytest -q tests/test_wb_reviews.py
  ```

### B13 — backend report route smoke без demo-data assumptions

- **Delta:** 1 failure; после B01–B13 остаётся 0.
- **Категории:** устаревший contract теста.
- **Разрешённые файлы:** `tests/test_app.py`.
- **Test IDs:**
  - `tests/test_app.py::test_sprint_d_reports_are_served_through_backend_app`
- **Root cause:** smoke test проверяет `preliminary` и demo values при пустом cache; production read contract корректно возвращает `blocked` envelope.
- **Evidence:** deterministic `'blocked' != 'preliminary'`; локальный `071c246` оставляет route/envelope/status smoke и убирает static row assumptions.
- **Минимальный fix:** проверять доступность routes и обязательные response keys/status domain, а не наличие demo P&L/ads/RNP rows.
- **Риск:** низкий; не превращать smoke в пустой status-code-only test — сохранить проверки contract shape.
- **Targeted verification:**
  ```bash
  run_isolated -m pytest -q tests/test_app.py
  ```

### Отдельная runner anomaly — не входит в 105 failures

- **Delta:** `0`; JUnit полностью записан, все test IDs уже известны.
- **Evidence:** только full-suite процесс Python 3.14 не завершает interpreter
  shutdown после summary; file-group и singleton процессы выходят штатно.
- **Boundary будущей диагностики:** `ops/release_gate.py` и один новый узкий
  runner test. Не смешивать с B01–B13 и не менять application paths без нового
  минимального воспроизведения.
- **До исправления:** использовать bounded supervisor из раздела 5; завершать
  только его точный pytest PID и только после parseable JUnit плюс grace period.

## 7. Scope boundaries для `10_fix_one_legacy_failure_batch.md`

Для каждого следующего агента:

1. Выбрать ровно один batch B01–B13 и редактировать только перечисленные там production/test files.
2. Начать с текущего canonical local HEAD в отдельном worktree; не работать поверх dirty canonical checkout.
3. Сначала воспроизвести targeted files с safe fake env и отдельным runtime state, затем применить минимальный root-cause fix.
4. Не менять `app/platform/finance/**`, `app/platform/period.py`, canonical economics/catalog/advertising/funnel projections, migrations, compose/runtime roles, handoff, production и этот triage report.
5. Не вызывать реальные WB/Avito/OpenAI APIs и не использовать production/GitHub.
6. Не коммитить и не восстанавливать `var/vella_repricer_runtime_state.json`, `.venv` или другие user/test-mutated artifacts.
7. Не менять `ops/legacy-test-failures.txt` в batch-ветке. Интегратор обновляет baseline один раз после объединения проверенных batches.
8. Historical sibling commits использовать как evidence/patch reference, а не wholesale cherry-pick: текущая canonical lineage содержит более новые period/finance/advertising slices.
9. Targeted files после fix должны пройти полностью; full JUnit должен потерять ровно IDs batch и не получить новых failures/errors.

Приоритет выбран так: сначала узкие product defects, затем общие cache-only boundaries, затем deterministic contract-only updates. Файловые множества B01–B13 попарно не пересекаются; это позволяет делегировать batches параллельно без конфликтов в production/test files.
