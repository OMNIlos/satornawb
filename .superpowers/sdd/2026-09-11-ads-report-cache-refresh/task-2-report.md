# Task 2 — manual ads outer-cache publication

## Изменение

После успешного manual `refresh_ads_report_cache` добавлена публикация в существующий `reports_payload_ads_*` через `_apply_report_rules_to_payload` и `_save_exact_report_payload_cache` для текущих organization/периода, `group_by="campaign"`, `source="operational"`. Shared builder/GET и worker/profile paths не изменялись.

## RED

Child process использовал `ops.release_gate.safe_environment()`, `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`, Python `/tmp/satorna-audit-python-3NlHN5/venv/bin/python -B`, cwd `backend`.

```text
/tmp/satorna-audit-python-3NlHN5/venv/bin/python -c 'import subprocess; from ops.release_gate import safe_environment; env=safe_environment(); env["PYTEST_DISABLE_PLUGIN_AUTOLOAD"]="1"; raise SystemExit(subprocess.run(["/tmp/satorna-audit-python-3NlHN5/venv/bin/python", "-B", "-m", "pytest", "-q", "-o", "addopts=", "-o", "junit_family=legacy", "-p", "no:cacheprovider", "--basetemp=/tmp/satorna-ads-outer-red", "--tb=line", "--show-capture=no", "--junitxml=/tmp/satorna-ads-outer-red.xml", "tests/test_ads_report_refresh.py"], env=env).returncode)'
```

Exit code: `1`.

```text
F..F.....                                                                [100%]
=================================== FAILURES ===================================
E   assert 100 == 200
/Users/ilagulakin/Desktop/Work/OgniWB/.worktrees/satornawb-audit-20260910/backend/tests/test_ads_report_refresh.py:72: assert 100 == 200
E   assert 100 == 0
/Users/ilagulakin/Desktop/Work/OgniWB/.worktrees/satornawb-audit-20260910/backend/tests/test_ads_report_refresh.py:72: assert 100 == 0
=========================== short test summary info ============================
FAILED tests/test_ads_report_refresh.py::test_ads_refresh_replaces_old_report_from_current_cached_sources[200-manual] - assert 100 == 200
FAILED tests/test_ads_report_refresh.py::test_ads_refresh_replaces_old_report_from_current_cached_sources[0-manual] - assert 100 == 0
2 failed, 7 passed in 0.66s
```

JUnit XML: `/tmp/satorna-ads-outer-red.xml`.

The two failing latest-reader cases demonstrate the missing manual outer publication; the worker/profile seven control cases passed.

## GREEN

Child process used the same safe environment and Python setup, with unique outer-green temp/XML paths:

```text
/tmp/satorna-audit-python-3NlHN5/venv/bin/python -c 'import subprocess; from ops.release_gate import safe_environment; env=safe_environment(); env["PYTEST_DISABLE_PLUGIN_AUTOLOAD"]="1"; raise SystemExit(subprocess.run(["/tmp/satorna-audit-python-3NlHN5/venv/bin/python", "-B", "-m", "pytest", "-q", "-o", "addopts=", "-o", "junit_family=legacy", "-p", "no:cacheprovider", "--basetemp=/tmp/satorna-ads-outer-green", "--tb=line", "--show-capture=no", "--junitxml=/tmp/satorna-ads-outer-green.xml", "tests/test_ads_report_refresh.py", "tests/test_repricer_tasks.py", "tests/test_report_refresh_handoff.py", "tests/test_report_job_cache_lifecycle.py"], env=env).returncode)'
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
-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
169 passed, 2 warnings in 9.06s
```

JUnit XML: `/tmp/satorna-ads-outer-green.xml`.

All nine latest-reader cases pass: manual 200, manual zero, worker 200, worker zero, profile 200, profile zero, and blocked manual/worker/profile preserving both inner and outer last-good reports.

## Файлы и границы

- `backend/app/routers/wb_reports_bff.py`
- `backend/tests/test_ads_report_refresh.py`
- `.superpowers/sdd/2026-09-11-ads-report-cache-refresh/task-2-report.md`

`git diff --check` прошёл. Не менялись signatures, namespaces, permissions, jobs, formulas, GET/default behavior, other writer paths, dependencies, baseline, plan/ledger or external services. Full suite and contracts intentionally not rerun; controller owns final immutable verification. Unrelated untracked `docs/` preserved.
