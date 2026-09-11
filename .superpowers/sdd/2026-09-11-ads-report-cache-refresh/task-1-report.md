# Task 1 — ads report cache refresh

## Результат

Исправлены все три writer-path рекламного отчёта: manual refresh, `build_report_for_org` и `_materialize_report_snapshots_for_profile`. Явный refresh теперь пересобирает cache-only snapshot из текущего source cache. При `source_status == "blocked"` общий builder возвращает `HTTPException(409, "WB_ADS_CACHE_EMPTY")` до mapper/store/history.

## RED

Команда (child process с `ops.release_gate.safe_environment()`, `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`, Python `/tmp/satorna-audit-python-3NlHN5/venv/bin/python -B`, cwd `backend`):

```text
/tmp/satorna-audit-python-3NlHN5/venv/bin/python -c 'import os, subprocess; from ops.release_gate import safe_environment; env=safe_environment(); env["PYTEST_DISABLE_PLUGIN_AUTOLOAD"]="1"; raise SystemExit(subprocess.run(["/tmp/satorna-audit-python-3NlHN5/venv/bin/python", "-B", "-m", "pytest", "-q", "-o", "addopts=", "-o", "junit_family=legacy", "-p", "no:cacheprovider", "--basetemp=/tmp/satorna-ads-refresh-red", "--tb=line", "--show-capture=no", "--junitxml=/tmp/satorna-ads-refresh-red.xml", "tests/test_ads_report_refresh.py"], env=env).returncode)'
```

Exit code: `1`.

```text
FFFFFFFFF                                                                [100%]
=================================== FAILURES ===================================
E   AssertionError: assert 'hit' == 'refreshed'
      - refreshed
      + hit
/Users/ilagulakin/Desktop/Work/OgniWB/.worktrees/satornawb-audit-20260910/backend/tests/test_ads_report_refresh.py:59: AssertionError: assert 'hit' == 'refreshed'
E   assert 100 == 200
/Users/ilagulakin/Desktop/Work/OgniWB/.worktrees/satornawb-audit-20260910/backend/tests/test_ads_report_refresh.py:63: assert 100 == 200
E   assert 100 == 200
E   AssertionError: assert 'hit' == 'refreshed'
      - refreshed
      + hit
E   assert 100 == 0
/Users/ilagulakin/Desktop/Work/OgniWB/.worktrees/satornawb-audit-20260910/backend/tests/test_ads_report_refresh.py:63: assert 100 == 0
E   assert 100 == 0
E   Failed: DID NOT RAISE HTTPException
/Users/ilagulakin/Desktop/Work/OgniWB/.worktrees/satornawb-audit-20260910/backend/tests/test_ads_report_refresh.py:81: Failed: DID NOT RAISE HTTPException
E   Failed: DID NOT RAISE HTTPException
E   AssertionError: assert 'completed' == 'failed'
      - failed
      + completed
/Users/ilagulakin/Desktop/Work/OgniWB/.worktrees/satornawb-audit-20260910/backend/tests/test_ads_report_refresh.py:79: AssertionError: assert 'completed' == 'failed'
      - failed
      + completed
9 failed in 0.90s
```

JUnit XML: `/tmp/satorna-ads-refresh-red.xml`.

## GREEN

Команда с тем же `safe_environment` wrapper и отдельными путями:

```text
/tmp/satorna-audit-python-3NlHN5/venv/bin/python -c 'import subprocess; from ops.release_gate import safe_environment; env=safe_environment(); env["PYTEST_DISABLE_PLUGIN_AUTOLOAD"]="1"; raise SystemExit(subprocess.run(["/tmp/satorna-audit-python-3NlHN5/venv/bin/python", "-B", "-m", "pytest", "-q", "-o", "addopts=", "-o", "junit_family=legacy", "-p", "no:cacheprovider", "--basetemp=/tmp/satorna-ads-refresh-green", "--tb=line", "--show-capture=no", "--junitxml=/tmp/satorna-ads-refresh-green.xml", "tests/test_ads_report_refresh.py", "tests/test_repricer_tasks.py", "tests/test_report_refresh_handoff.py", "tests/test_report_job_cache_lifecycle.py"], env=env).returncode)'
```

Exit code: `0`.

```text
........................................................................ [ 42%]
........................................................................ [ 85%]
.........................                                                [100%]
=============================== warnings summary ===============================
../../../../../../../../private/tmp/satorna-audit-python-3NlHN5/venv/lib/python3.11/site-packages/fastapi/testclient.py:1
  StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
../../../../../../../../private/tmp/satorna-audit-python-3NlHN5/venv/lib/python3.11/site-packages/starlette/testclient.py:53
  DeprecationWarning: The anyio.abc.BlockingPortal alias is deprecated, use anyio.from_thread.BlockingPortal instead.
169 passed, 2 warnings in 9.14s
```

JUnit XML: `/tmp/satorna-ads-refresh-green.xml`.

## Файлы

- `backend/app/routers/wb_reports_bff.py` — blocked guard и manual `refresh=True`.
- `backend/app/repricer_tasks.py` — ads `refresh=True` в worker/profile сборщиках.
- `backend/tests/test_repricer_tasks.py` — обновлено существующее ожидание worker argument.
- `backend/tests/test_ads_report_refresh.py` — реальные regression checks для трёх путей, zero spend, cache-hit и сохранности last-good при blocked.

## Self-review и ограничения

- `git diff --check` прошёл.
- Mapper, cache-only builder, cache store и history publication не заменялись; внешние source/DB/auth boundaries изолированы только в тестовом fixture.
- GET/default cache reuse не изменён; provider calls, financial policy, schema, dependencies и baseline не изменялись.
- Полный backend suite не запускался: его запускает controller.
- Рабочее дерево содержит исходный unrelated `docs/` без изменений от этой задачи.
