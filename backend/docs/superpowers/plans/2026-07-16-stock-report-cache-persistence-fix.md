# Stock Report Cache Persistence Fix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Сохранять stock report payload с длинным ключом и не показывать ложные 100%, если запись в общий кэш не произошла.

**Architecture:** Расширить `source_key` до 255 символов через ORM и Alembic. Перед публикацией `completed` читать report payload обратно из PostgreSQL; отсутствие записи переводит job в существующую ветку `failed`.

**Tech Stack:** Python, SQLAlchemy, Alembic, Celery, PostgreSQL, pytest.

## Global Constraints

- Не менять расчёты stock report и frontend-контракт.
- Ограничиться двумя регрессионными тестами и одним полным прогоном backend suite.

---

### Task 1: Регрессионные тесты

**Files:**
- Create: `tests/test_stock_report_cache_persistence.py`

- [ ] Добавить тест, требующий `source_key` длиной 255.
- [ ] Добавить тест, требующий `failed`, если report payload не читается после записи.
- [ ] Запустить файл тестов и подтвердить два ожидаемых падения.

### Task 2: Минимальный production fix

**Files:**
- Modify: `app/repricer_cache/orm.py`
- Create: `alembic/versions/20260716_0015_expand_source_cache_key.py`
- Modify: `app/repricer_tasks.py`
- Modify: `tests/test_wb_reports_bff.py`

- [ ] Расширить ORM и PostgreSQL колонку `source_key` с 64 до 255.
- [ ] Добавить read-after-write проверку report payload перед статусом `completed`.
- [ ] Обновить один существующий task-test так, чтобы fake cache моделировал сохранение.
- [ ] Запустить два регрессионных теста до зелёного состояния.

### Task 3: Проверка

- [ ] Запустить `python -m pytest -q` один раз.
- [ ] Проверить `python -m alembic heads` и `git diff --check`.
- [ ] Передать обязательную production-команду `python -m alembic upgrade head`.
