# WoW Ads Progress Fix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Убрать лишние budget-запросы из WoW и показывать монотонный, корректно подписанный прогресс.

**Architecture:** Общий Ads builder сохраняет budgets по умолчанию, но позволяет WoW отключить их. WoW worker namespace-ит
вложенные stages и масштабирует проценты по этапам; React сопоставляет только конкретные namespace.

**Tech Stack:** Python, Celery, pytest, React, TypeScript, Vitest.

## Global Constraints

- Не менять отдельный отчёт «Реклама».
- Не добавлять больше одной новой backend-регрессии.

---

### Task 1: RED

- [ ] Добавить backend-тест: `include_budgets=False` не вызывает `/adv/v1/budget`, проценты монотонны и не выходят за диапазон.
- [ ] Расширить существующий frontend source-test проверкой конкретных WoW stage matchers.
- [ ] Запустить только эти два теста и подтвердить ожидаемые падения.

### Task 2: GREEN

- [ ] Добавить `include_budgets` и относительное распределение прогресса в Ads builder.
- [ ] Передать `include_budgets=False` из обоих WoW Ads вызовов.
- [ ] Namespace-ить current/previous source callbacks и завершать WoW stage на summary.
- [ ] Исправить `WEEK_PROGRESS_STEPS` во frontend.

### Task 3: Verify

- [ ] Запустить целевые backend/frontend тесты.
- [ ] Запустить backend `git diff --check` и frontend `npm run typecheck`.
