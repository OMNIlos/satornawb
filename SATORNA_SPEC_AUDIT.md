# Аудит спеки «Архитектура постепенной пересборки платформы Satorna»

**Дата аудита:** 2026-08-26
**Предмет:** `docs/superpowers/specs/2026-08-26-satorna-platform-rebuild-architecture-design.md`
**Метод:** сверка утверждений спеки с кодом, файлами состояния, миграциями и живыми ответами production.
**Вердикт:** целевая архитектура выбрана верно. Блокируют не решения, а фактические расхождения baseline'а (§0.1) с кодом и невыполнимые критерии приёмки первого среза.

---

## 0. Что и где проверялось

Рабочая директория: `/Users/ilagulakin/Desktop/Work/OgniWB`

| Путь | Что это |
|---|---|
| `ogni-elfs-live/`, `ogni-elfs-prod/` | Копии backend, совпадающие с развёрнутым (по составу `/health`) |
| `ogni-elfs-main/`, `backend/ogni-elfs/` | Отставшие копии того же backend |
| `ogni-frontend-main/frontend/` | React SPA (деплоится на Vercel) |
| `ogni-frontend-main/backend/` | **Отдельный** FastAPI-прототип производства внутри репо фронтенда |
| `wb-pdf-matcher/` | **Отдельный** Node/TS сервис для КИЗ/ЧЗ + PDF |
| `.worktrees/backend-wb-abc-production/` | Worktree с аудитом ABC и фикстурами |
| `abc_sales_reconciliation_2026-08-17_23/` | Артефакт финансовой сверки |

Живые пробы: `https://satorna-wb.vercel.app`, `https://api.elfprint-system.ru`.

Все номера строк ниже — по `ogni-elfs-live` (развёрнутая версия), если не указано иное.

**Оговорка о полноте:** файлы состояния (`var/vella_repricer_runtime_state.json`) читались локальные. Покрытие себестоимости в production DB может быть выше локального; аудит подтверждает per-SKU COGS у 19 из 20 контрольных SKU, но не по всему каталогу.

---

## 1. Блокеры

### B1. Контрольная сумма 6 356 582,51 ₽ невоспроизводима

**Спека:** §3.3 фиксирует итог `6 356 582,51 ₽` (635 658 251 коп.) как контрольный regression; §7.2 повторяет его как ожидаемый итог golden dataset; §6.2 запрещает переключение «при необъяснённом денежном diff больше 1 копейки».

**Факт** — `.worktrees/backend-wb-abc-production/docs/wb-abc-production-audit-2026-08-26.md`:

- Раздел «Повторная live-сверка после деплоя»: повторная выгрузка Finance v3 вернула **635 537 451** коп. — ровно «Основной» + «По выкупам», уже **без** корректировки 1 208,00 ₽. Независимый запрос API с верхней датой 26.08 дал тот же результат.
- Таблица «Production smoke периодов», строка «Календарь»: `17.08.2026–23.08.2026 → 3 339 строк → 635 537 451 коп.`
- 19 из 20 контрольных SKU совпали до копейки; `nmId=453200669` разошёлся ровно на `−120 800` коп.

```
спека / фикстура     635 658 251 коп.
production сегодня   635 537 451 коп.
                     ─────────────────
разница                  120 800 коп. = 1 208,00 ₽
порог §6.2                         1 коп.
```

**Последствие:** любая shadow-сверка против живого WB упирается в 120 800 коп. и по §6.2 блокирует rollout бессрочно. WB меняет выдачу за закрытый период задним числом — это свойство источника, а не ошибка агрегатора.

**Что сделать:** развести два независимых гейта.
1. **Regression против замороженной фикстуры** — `.worktrees/backend-wb-abc-production/tests/fixtures/wb_abc_2026_08_17_23.json` уже содержит `mainKopecks / buyoutKopecks / lateCorrectionKopecks / liveKopecks / uiRoundedRubles` и 20 SKU. Допуск 0.
2. **Сверка против live WB** — с явным допуском и правилом «поздняя корректировка может исчезнуть/появиться; расхождение объясняется diff'ом по `rrdId`, а не блокирует релиз».

---

### B2. Backfill себестоимости не покрывает реальный источник данных

**Спека:** §8.4 переносит в `cost_versions` только `skuSettingsOverrides/cogsHistory`.

**Факт** — реальная цепочка разрешения COGS, `app/wb_reports_sprint_d.py:640–661`:

```
1  TYPE_DEFAULTS[первая буква артикула]
     app/repricer_bff.py:599 → F 45000 / H 85000 / L 44000 коп.
     app/wb_reports_sprint_d.py:611 → неизвестный префикс молча даёт "F"
2  algorithm["cogsByGarmentRub"][tshirt|hoodie|longsleeve]
     app/repricer_bff.py:678 → дефолт {tshirt: 380, hoodie: 720, longsleeve: 440} ₽
3  runtime["skuSettingsOverrides"][article_id]["cogsKopecks"]
     ← единственный уровень, который переносит §8.4
```

Сколько данных на уровне 3 (`var/vella_repricer_runtime_state.json`, все четыре копии backend):

| org | записей в `skuSettingsOverrides` | из них с `cogsKopecks` |
|---|---:|---:|
| 1 | 12 | **1** (`FBBT_42 = 45000`) |
| 2 | 0 | 0 |
| 7 | 0 или 12 (различается по копиям) | 0 или 1 |

При этом в ABC — 2 953–3 339 строк.

Дополнительно: `cogsByGarmentRub.longsleeve` различается между организациями и копиями — **450** у одной, **440** у другой. То есть «одна себестоимость» не одна уже сейчас.

Показательно: пример в самой спеке (§5.1) `cogsKopecks=44000, cogsState=configured` — это ровно `TYPE_DEFAULTS["L"]["cogsKopecks"]`, хардкод-константа, а не настроенная стоимость.

**Последствие — развилка без выхода:**
- Перенести только уровень 3 → почти все SKU получат `value_state=missing`, `cogsKopecks=null` → чистая прибыль и ABC обвалятся → §6.2 заблокирует переключение.
- Перенести уровни 1–2 как `configured` → все SKU получат «настроенную» стоимость от константы, что ровно противоположно цели «сделать отсутствие видимым».

**Что сделать:**
- Ввести третье состояние: `configured | assumed | missing`. `assumed` = значение получено из type/garment-дефолта, показывается пользователю как неподтверждённое.
- В §8.4 перечислить все три источника с разным `source`: `legacy_type_default`, `legacy_garment_default`, `legacy_sku_override`.
- Первым срезом закрыть не схему, а **сбор реальной себестоимости** — иначе canonical cost ledger канонизирует три константы.

---

### B3. Golden dataset выбран на периоде, где себестоимость недоказуема

**Спека:** §7.2 фиксирует golden dataset на `2026-08-17..2026-08-23`; §8.4 запрещает применять текущую стоимость задним числом без подтверждённой даты; §8.7 требует «20 контрольных SKU совпадают».

**Факт** — тот же аудит:

- **Release gate 2:** «Для 17.08–19.08 15:37 МСК дать датированный источник изменений COGS… **В production нет более ранних `cogsHistory`, `cogsByGarmentHistory` или audit events с COGS, поэтому снимок нельзя доказательно распространить назад.**»
- Контракт колонок, строка 13 «Себестоимость», статус: **`BLOCKED для 17–19.08`**; снимок настроек подтверждён только с 19.08 15:37 МСК.
- `grep -rn "cogsHistory\|cogsByGarmentHistory" ogni-elfs-live/app ogni-elfs-prod/app` → **0 совпадений**. Механизм существует только в `.worktrees/backend-wb-abc-production/app/` (`wb_reports_sprint_d.py:721,758`, `repricer_persistence/store.py:37,451,468,479,489`).

**Последствие:** первые ~2,5 суток эталонного периода не имеют доказанной себестоимости. §8.7 недостижим по построению, §6.2 заблокирует переключение.

**Что сделать:** сдвинуть golden period на **19.08–25.08**. Он уже отснят в production smoke того же аудита: 3 338 строк, продажи `682 361 964` коп., чистая прибыль `118 247 476` коп., «Итог = строки, до копейки».

---

### B4. `/api/v2` не дойдёт до backend, и клиент проглотит это молча

**Спека:** §8.3 вводит `/api/v2/*`; §4.2 — «новая `/api/v2` ручка работает рядом с `/api/v1`». Слой rewrite'ов Vercel не упомянут нигде.

**Факт** — `ogni-frontend-main/frontend/vercel.json`:

```json
"rewrites": [
  { "source": "/api/v1/(.*)", "destination": "https://api.elfprint-system.ru/api/v1/$1" },
  { "source": "/api/wb/(.*)", "destination": "https://api.elfprint-system.ru/api/wb/$1" },
  { "source": "/api/1c/(.*)", "destination": "https://api.elfprint-system.ru/api/1c/$1" },
  { "source": "/api/(.*)",    "destination": "/api/$1" },
  { "source": "/(.*)",        "destination": "/index.html" }
]
```

Правила для `/api/v2` нет. Живые пробы 26.08.2026:

```
GET https://satorna-wb.vercel.app/api/v1/production/production-skus
  → 404  application/json  {"detail":"Not Found"}      (FastAPI, rewrite работает)

GET https://satorna-wb.vercel.app/api/v2/catalog/skus
  → 200  text/html  <!doctype html>…                   (SPA fallback, backend не задет)
```

Почему ошибка будет непонятной — `ogni-frontend-main/frontend/src/lib/api.ts:91`:

```ts
const isJson = response.headers.get('content-type')?.includes('application/json')  // false
const payload = isJson ? ((await response.json()) as T) : null                     // null
if (!response.ok) { … }                                    // не сработает: ok === true
return payload                                             // null
// затем apiData(): throw new ApiError('Empty API response', 204)
```

**Последствие:** пользователь увидит `Empty API response 204` без намёка, что запрос не дошёл до backend.

**Что сделать (в срез 1):**
1. Добавить в `vercel.json` rewrite `/api/v2/(.*)` → `https://api.elfprint-system.ru/api/v2/$1`, **выше** правила `/api/(.*)`.
2. В `parseResponse` бросать явную ошибку при не-JSON `content-type` на путях `/api/*`, а не возвращать `null`.

Побочно: локальные Vercel-функции `frontend/api/v1/avito/orders/*` и `frontend/api/wb/reports/*` перебивают rewrite (проверено: `/api/v1/avito/orders/browser-snapshot` → `405 {"error":{"code":"METHOD_NOT_ALLOWED"}}` — форма ответа не FastAPI). То есть `/api/v1/*` сегодня обслуживают **два разных backend'а**, разделённых по путям. §4.1 «ручные копии network contract в двух репозиториях запрещены» этого не учитывает.

---

### B5. RLS не сработает: приложение ходит в базу под суперпользователем

**Спека:** §5 — «Защита состоит из обязательного `TenantContext` в repository/use case и PostgreSQL RLS».

**Факт:**
- `app/config.py:69` → `postgresql+psycopg://postgres:postgres@127.0.0.1:5433/vella_backend`; `.env` и `docker-compose.yml` (`POSTGRES_USER: postgres`) подтверждают.
- PostgreSQL **не применяет RLS к суперпользователю вообще**, а к владельцу таблицы — только при `FORCE ROW LEVEL SECURITY`.
- `grep -rn "ROW LEVEL SECURITY\|set_config\|current_setting" app alembic` → **0 совпадений**.

**Что сделать (в срез 1):**
- Отдельная роль приложения без `SUPERUSER`/`BYPASSRLS`, не владеющая таблицами.
- `ALTER TABLE … ENABLE ROW LEVEL SECURITY` **и** `FORCE ROW LEVEL SECURITY`.
- Передача tenant через `SET LOCAL app.organization_id` **внутри транзакции** (не `SET` — иначе GUC протечёт между запросами на общем пуле SQLAlchemy).
- Тест «RLS активен именно под app-ролью», иначе §7.1 «RLS/cross-tenant access» будет зелёным, ничего не проверяя.

---

## 2. Высокий риск

### H1. CI не существует

`.github/workflows`, `.gitlab-ci.yml`, `Jenkinsfile` — **отсутствуют во всех репозиториях и копиях**.

Текущая тестовая база: backend — 51 тест-файл, из них к PostgreSQL обращаются **3** (`test_infra_baseline.py`, `test_avito_returns.py`, `test_one_c_cash_flow.py`); frontend — 43 тест-файла.

§7.1 требует интеграционный набор на PostgreSQL: RLS/cross-tenant, account scope, дедупликация finance, повторный SyncRun, union SKU, атомарная выдача КИЗ, optimistic concurrency, outbox/retry, legacy backfill, Alembic на пустой и production-подобной БД. Из этого не существует ничего.

§9.3 («Breaking OpenAPI diff и несовместимая migration блокируют release»), §9.4 и §7.5 («tests зелёные») исполнять негде.

**Что сделать:** «поднять CI» — первый пункт среза 0, а не следствие.

---

### H2. Нет единого репозитория backend

§9.1 требует фиксировать `backendCommit` на релиз. На диске четыре расходящиеся копии + два worktree; под git только `backend/ogni-elfs` и `frontend`.

```
ogni-elfs-main    vs ogni-elfs-live   →  14 различающихся файлов в app/
ogni-elfs-live    vs ogni-elfs-prod   →   7 файлов
                     (включая repricer_bff.py, wb_reports_bff.py, repricer_tasks.py)
backend/ogni-elfs vs ogni-elfs-live   →  14 файлов
```

Прод-`/health` отдаёт `legacyOneCEnabled` и `apiDocsEnabled` — полей, которых в `ogni-elfs-main` вообще нет.

**Практическое следствие:** одна и та же функция ведёт себя по-разному. В `ogni-elfs-main/app/repricer_persistence/store.py:85–102` чтение runtime-состояния делает `merged[key] = {**db, **file}` — локальный файл перетирает базу. В развёрнутой копии (`ogni-elfs-live/…:129–146`) этот merge уже убран. Пока не выбран один репозиторий, §9.1 и §9.4 не работают.

---

### H3. Legacy-хранилище себестоимости не одно, а три

§8.5 рисует дуал-райт `CostsService → cost_versions + legacy JSON projection`, предполагая одну legacy-цель.

`app/repricer_persistence/store.py:187–205`:

```python
def save_runtime_state(organization_id, state_payload):
    payload = _runtime_state_defaults(state_payload)
    _MEMORY_RUNTIME_STATE[organization_id] = deepcopy(payload)   # 1. память процесса
    file_saved = _save_file_runtime_state(organization_id, payload)  # 2. var/…runtime_state.json
    ...
    db_saved = _run_db(_db)                                       # 3. PostgreSQL
    return bool(db_saved) or file_saved                           # ← успех без базы
```

Чтение (`:129–146`): при ошибке БД `_run_db` возвращает `None`, и чтение уходит в файл, затем в память процесса.

В `docker-compose.yml` у сервиса `api` **нет volume для `var/`** — файл эфемерный и свой у каждой реплики.

**Последствие:** при двух репликах (§9.1) у каждой свой файл. Дуал-райт через один `CostsService` не спасёт от воскрешения старых значений с локального диска реплики.

**Что сделать:** §8.5 переписать как «отключить файловый и in-memory путь записи», а не «спроецировать в legacy JSON».

---

### H4. Репрайсер держит состояние организации в глобалах модуля

§0.1 это фиксирует, но §6 ставит репрайсер в **срез 4** — до него четыре среза работают поверх живой гонки. В проде `realPriceApplyEnabled: true` (видно в `/health`), то есть цены меняются по-настоящему.

- `app/repricer_bff.py:779–790, 1091–1093` — 13 изменяемых словарей и списков на уровне модуля.
- `hydrate_repricer_bff_state(organization_id, module)` (`app/repricer_persistence/store.py:406`) делает `.clear()` + `.update()` прямо на модуле. Вызывается из HTTP-роутера (`app/routers/wb_repricer_bff.py:393, 404, 4700, 5668, 6153`) и из шести Celery-задач (`app/repricer_tasks.py`).
- **Не восстанавливаются и не сохраняются вообще** — текут между организациями и теряются при рестарте: `SKU_COMMENTS`, `SKU_AUDIT_EVENTS`, `PROMOTION_UPLOAD_OVERRIDES`, `CATALOG_GOODS_CACHE`, `COMMISSION_TARIFFS_CACHE`, `CHANGELOG_ENTRIES`.
- `flush_repricer_bff_state` берёт `pendingPriceApprovals` из ранее прочитанного payload → конкурентные подтверждения цен затирают друг друга.

**Что сделать:** вынести устранение глобалов в срез 0/1, до того как рядом появится второй писатель.

---

### H5. Ключ кэша §3.5 — регресс относительно уже работающего

§3.5 перечисляет: `organization, account scope, dateFrom/dateTo, formulaVersion, rulesVersion, sourceRevision, filters`. **Версии себестоимости в ключе нет.**

Аудит, п. 10 и раздел «Период, кэш и скорость»: production уже использует ключ `v16` = организация + диапазон + formula version + **hash экономических настроек / COGS history / active rules**. «При изменении COGS, алгоритма или rule profile старый отчёт несовместим и не читается.»

`sourceRevision` относится к синхронизациям, а правка себестоимости — не факт из sync. По §3.5 директор поправит COGS и увидит старые цифры до истечения TTL.

**Что сделать:** добавить в ключ версию cost-ledger'а и хэш экономических настроек явно.

---

### H6. Бюджет «cached table p95 ≤ 500 мс» уже превышен

Аудит, «Период, кэш и скорость», production `v16`:

```
p50             481,50 мс        бюджет §7.4: p95 ≤ 500 мс
p95             637,56 мс        превышение на 27,5 %
строк                3 339
JSON ответа  6 558 954 байт      несжатый
```

Плюс: §9.1 отдаёт один Redis и под кэш, и под брокер Celery; §3.5 задаёт ключ из семи измерений, включая `filters`, при значениях по 6,5 МБ. **TTL, лимита памяти и политики вытеснения в спеке нет вообще** (в проде сейчас TTL 5 минут — аудит, п. 20).

**Что сделать:** либо поднять бюджет до честных ~700 мс, либо заложить в срез работу по размеру ответа. Redis под кэш развести с брокером.

---

## 3. Пробелы и неточности

### M1. §0.1 выдаёт непроверенное утверждение за подтверждённое

§0.1: «backend health доступен и **видит** PostgreSQL, Redis и Celery». Не видит.

`app/main.py:104`:

```python
"infrastructure": {
    "databaseConfigured": bool(settings.database_url),
    "redisConfigured": bool(settings.redis_url),
    ...
}
```

Это проверка «переменная окружения задана», а не связность — ровно то, что §9.2 объявляет неприемлемым.

Живые пробы `api.elfprint-system.ru`:

```
/health        → 200   {"status":"ok",…,"databaseConfigured":true}
/health/live   → 404
/health/ready  → 404
/openapi.json  → 404   (apiDocsEnabled: false)
/docs          → 404
```

§9.2 требует в health-ответе commit SHA, build time, Alembic revision, API contract version, formula version, heartbeat worker/Beat — из этого есть только `contractVersion`.

---

### M2. Модель `configured | missing` теряет провенанс

Реальных уровней четыре (см. B2). Двух состояний недостаточно, чтобы отличить «директор подтвердил 380 ₽» от «сработала константа 380 ₽».

Аудит уже оперирует более богатой моделью: `cogsPerUnitKopecks`, `cogsKopecks`, `cogsSource`, `cogsEffectiveFrom`, `cogsEvidenceStatus` со значениями `undated` / `period_end_fallback` и блокерами `WB_ABC_COGS_EFFECTIVE_DATE_MISSING`, `WB_ABC_COGS_DAILY_COVERAGE_MISMATCH`. Спека это теряет — она беднее уже достигнутого.

---

### M3. Версионируется только себестоимость, но не остальные экономические настройки

В расчёт чистой прибыли входят ещё три величины из того же JSON, без даты действия (`app/wb_reports_sprint_d.py:653–657`; аудит, строки 34–35):

- `taxPct`
- `otherExpensePricePct`
- `otherExpensePerSaleKopecks`

§8.1 создаёт `catalog_cost_versions`, аналога для налога и накладных нет. Значит §1 «отчёты используют стоимость, действовавшую на момент операции» выполняется для одной переменной из четырёх, и P&L за прошлый период по-прежнему будет меняться от правки настроек.

---

### M4. Грань `CatalogSku` не определена, и полей не хватает

- `catalog_skus UNIQUE(organization_id, code)` — уровень артикула продавца (`vendorCode`), но `размер` в атрибутах §1 тянет к уровню `chrtId`.
- Финансовые операции WB приходят на уровне `nmId` + `srid`/`rrdId`. В контрольном снимке: `financeSkuRows: 927` против 2 953–3 339 строк ABC. Правила «стоимость → nmId → chrtId» в спеке нет.
- Два partial-unique на `marketplace_offers` не запрещают одновременно существовать строке с `external_variant_id IS NULL` и строкам с вариантами для одного `external_product_id` → поиск по `nmId` станет неоднозначным.
- Поля, от которых зависит текущий ABC, положить некуда: `productStatus` и `manager`/`managerId` берутся из `skuMetaOverrides` (аудит, строки 4 и 9), а в `CatalogSku` (§1: внутренний артикул, printId, тип, цвет, размер) их нет.

---

### M5. UNIQUE по `source_reference` конфликтует с append-only исправлением

§8.1 требует одновременно:

```
UNIQUE (organization_id, source, source_reference) WHERE source_reference IS NOT NULL
```

и

> «Исправление записи с той же датой действия создаёт новую append-only версию с `supersedes_cost_version_id`»

Что такое `source_reference`, спека не определяет. Если это «строка XLSX» — повторное исправление того же импорта невозможно. Если «`importId` + строка» — тогда §8.7 «повторный apply не создаёт дубликаты» держится, но `import_apply` обязан быть строго идемпотентным по `importId`, чего §8.2 не фиксирует.

---

### M6. Backfill не покрывает четыре группы таблиц без `organization_id`

§0.1 упоминает «ряд reviews, control-plane и job таблиц». Список шире, а §8.4 переносит только `lk_integrations`/credentials:

| Файл | Таблицы | `organization_id` |
|---|---|---|
| `app/account_health/orm.py` | `wb_accounts`, `wb_account_capabilities`, `wb_account_missing_scopes`, `wb_token_health_checks` | **нет** |
| `app/source_registry/orm.py` | `source_registry_blockers`, `source_registry_formulas`, `source_registry_entries` | **нет** |
| `app/control_plane/orm.py` | `cp_settings_versions`, `cp_audit_events`, `cp_sync_jobs` | **нет** |
| `app/infra/models.py` | `infra_runtime_state` | **нет** |
| `app/reviews/orm.py` | 9 таблиц `rv_*`, `organization_id` есть только у `rv_review_sync_settings` и `rv_review_sync_runs` | частично |

`wb_accounts` + capabilities + health — это ровно то, что §2 отдаёт модулю Integrations, и чего нет в §8.4.

---

### M7. Направление генерации контракта в §4.1 противоположно реальному

§4.1: «Pydantic request/response models backend — исполняемый источник API-контракта». Сейчас наоборот.

- `ogni-frontend-main/frontend/scripts/export-openapi.ts` — Zod-схемы **фронтенда** → `@asteasolutions/zod-to-openapi` → `contracts/openapi/v1.yaml`.
- Файл `ogni-elfs-live/contracts/openapi/v1.yaml` датирован **12 июня** (2,5 месяца назад).
- `app/contracts/vella_wb_19_05_generated.py` — 415 строк generated Pydantic, **не импортируется нигде** (`grep -rn "vella_wb_19_05_generated" app` → 0).

Покрытие типами: **226 роутов, 109 с `response_model=`**. Непокрытая часть — вся production-поверхность:

| Файл | Роутов | С `response_model=` |
|---|---:|---:|
| `app/routers/wb_repricer_bff.py` | 65 | **0** |
| `app/routers/wb_reports_bff.py` | 22 | **0** |
| `app/routers/avito_repricer.py` | 9 | **0** |
| `app/routers/avito_orders.py` | 8 | **0** |
| `app/routers/avito_overview.py` | 1 | **0** |

§4.1 — это не «включить CI-проверку», а сменить направление генерации и типизировать 105 роутов. Объём стоит назвать явно.

---

### M8. Предусловия «двух реплик» не выполнены: API запускает Alembic на старте

`docker-compose.yml`, сервис `api`:

```yaml
command: >
  sh -c "python -m alembic upgrade head &&
  python -m uvicorn app.main:app --host 0.0.0.0 --port 8000"
```

§9.4 верно требует «Миграция схемы выполняется отдельным release job. API не запускает Alembic при старте», но §6.2 «Deployment order» не содержит пункта «убрать alembic из команды запуска». Пока он там, две реплики из §9.1 дадут гонку миграций.

В compose сейчас по одному экземпляру `api`/`worker`/`beat`, балансировщика нет. Alembic-цепочка линейная, одна голова (`20260526_0001` → `20260810_0024`) — это в порядке.

---

### M9. Четыре слоя из §2–§4 не существуют вообще

`grep -rin` по `ogni-elfs-live/app`:

```
Idempotency / idempotency_key   0     §4.1 «мутации внешних действий поддерживают Idempotency-Key»
outbox                          0     §2 Operations, §2 Notifications, §9.6
pg_advisory / advisory_lock     0     §3.1 «параллельная синхронизация блокируется PostgreSQL-lock»
kiz / КИЗ / marking_code        0     §2 модуль KIZ, §6 срез 3
with_for_update                 3
```

Роутеров `production`, `orders` (WB) и `kiz` нет. В §6 срез 3 «Orders, production, KIZ» выглядит как один из восьми равных срезов, хотя фундамента под ним нет ни на строку.

---

### M10. Правило «модули не вызывают собственный `date.today()`» затрагивает 165 мест

```
app/ — date.today()               12
app/ — datetime.now() / utcnow()  153
   только app/routers/wb_repricer_bff.py — 50
```

Правило §3.4 верное, но механизма принуждения нет: ни инжектируемых часов, ни lint-правила. Стоит добавить `Period`/`Clock` в сигнатуры use case и запрещающее правило в CI.

Таймзоны: `Europe/Moscow` встречается 19 раз, `ZoneInfo` — только в `wb_sync_plan.py` и `repricer_execution.py`. Единого `Period` нет.

---

### M11. Пропущен открытый release gate: `ktr_table` отсутствует в production

Аудит, строка 38 контракта колонок: КТР и локализация — статус **`BLOCKED: ktr_table отсутствует в production`**, несовместимый `krp_table` использовать нельзя. Это **Release gate 1** в том же документе.

В спеке этого нет нигде: §0.1 не упоминает, §2 не даёт владельца в таблице модулей, §6 не планирует ни в одном срезе. При этом §9.7 говорит «Финансовый diff → витрина не получает `fresh`, rollout блокируется» — незакрытый gate будет держать источник в `partial/medium` и блокировать выкатку.

---

### M12. Токены маркетплейсов лежат открытым текстом

```
app/cabinet/orm.py
  lk_user_wb_tokens.wb_token               Text, plaintext
  lk_user_avito_credentials.client_secret  Text, plaintext
  lk_user_avito_credentials.cached_access_token  Text, plaintext

grep: cryptography / Fernet / encrypt / decrypt / AESGCM / KMS  → 0 совпадений
      (cryptography нет и в зависимостях pyproject.toml)

docker-compose.yml: VELLA_AUTH_SECRET default "change-this-secret"
```

§5.2 описывает целевое состояние правильно, но таблица срезов §6 **не назначает шифрование ни одному срезу**, а §9.6 обещает «ежедневный зашифрованный backup» — который сегодня снимает дамп с plaintext-токенами. Нет ни слова о том, где живёт ключ, и о процедуре ротации/перешифрования.

---

### M13. При недоступной базе система тихо деградирует вместо отказа

`app/cabinet/store.py:147`, `app/repricer_persistence/store.py:107` и ещё в 8 модулях:

```python
def _run_db(db_fn):
    try:
        ...
    except SQLAlchemyError:
        return None      # ← вызывающий уходит в in-memory defaults
```

`_ensure_defaults()` сеет организацию `vella-local` и набор пользователей с паролями.

§9.7 описывает желаемое («Database недоступна → readiness выключается, новые запросы не принимаются»), но пункта «убрать fallback» в плане нет. Сценарий опаснее описанного: **во время shadow-сверки транзиентная ошибка БД даст «объяснимый diff формулы» вместо честного отказа**, и решение о переключении будет принято на ложных данных.

Побочно: `_run_db` глотает и `IntegrityError`. Значит новые `UNIQUE`-ограничения из §8.1 будут молча no-op'ить вместо ошибки — это прямо угрожает §8.7 «повторный apply не создаёт дубликаты».

---

### M14. Production-прототип больше, чем «in-memory repository», и попал не в тот срез

`ogni-frontend-main/backend/app/production/` — отдельный FastAPI внутри репо фронтенда:

```
repository.py          681 строка
export.py              322
contracts.py           295
mapping_import.py      267
print_list.py          144
storage.py              30
routers/production.py  631
                     ─────
                     2 372 строки    organization_id: 0 совпадений
```

`storage.py` — `JsonProductionStore.save()` сериализует **весь снимок целиком** в один JSON-файл, без ключа организации и без транзакции: два конкурентных записи = потеря одной.

§8.3 говорит, что `GET /api/v2/production/skus` «заменяет отсутствующий production endpoint и in-memory prototype». Но §8.1 не создаёт ни одной production-таблицы, а §6 ставит Production в срез 3. В срезе 1 endpoint заменит прототип только по каталогу и себестоимости — очередь, print groups, маппинги и экспорт останутся в прототипе. Если легаси-роут при этом выключить, производство потеряет функциональность.

---

### M15. КИЗ уже реализованы отдельным Node-сервисом, которого нет в спеке

`wb-pdf-matcher/` — самостоятельный TypeScript-сервис:

```
server/src/services/chzParser.ts     разбор кодов Честного Знака
server/src/services/wbParser.ts      разбор этикеток WB
server/src/services/matcher.ts       сопоставление
server/src/services/pdfBuilder.ts    сборка PDF с DataMatrix
server/src/services/chzPdfSync.ts
server/src/routes/{match,stats,importChz}.ts
```

Состояние — в `Map` и файлах на диске (`importChz.ts:34` — `const jobs = new Map<string, Job>()`).

В спеке он не упомянут ни разу. §2 заводит модуль `KIZ` внутри FastAPI-монолита, §10 запрещает микросервисы — значит генерацию PDF придётся переписать на Python. Это существенный объём, растворённый в срезе 3.

---

## 4. Что подтвердилось (проверка §0.1)

| Утверждение §0.1 | Вердикт | Что показывает код |
|---|---|---|
| `/api/v1/production/production-skus` → 404 | **Точно** | `404 {"detail":"Not Found"}`; в backend нет ни одного роута `/production` |
| Нет canonical Product/SKU таблиц | **Точно** | 36 `__tablename__`, ни одной товарной; 24 миграции |
| Себестоимость превращается в `0` или `1` | **Точно** | `app/repricer_sprint_b.py:569` — `cogsKopecks or 1`; `app/wb_reports_sprint_d.py:654` — `or 0` |
| Репрайсер использует module-global словари | **Точно** | 13 контейнеров; hydrate/flush из HTTP и 6 Celery-задач (см. H4) |
| Reports напрямую зависят от кэша репрайсера | **Точно** | `app/routers/wb_reports_bff.py:30–31` импортирует `repricer_cache.store` и `repricer_bff` |
| Один provider на организацию; 10–15 Авито не помещаются | **Точно** | `lk_integrations UNIQUE(organization_id, provider)`; `lk_user_avito_credentials.user_id UNIQUE`; `lk_users.organization_id` — прямой FK, membership-таблицы нет |
| `VellaHtmlParityPage` >40k строк, DOM/window bridge | **Точно** | 40 243 строки; 1 686 обращений к `window.`; период живёт в `window.__vellaProductsPeriodMode/Days/FromIso/ToIso` |
| Большие BFF-файлы смешивают HTTP, формулы, кэш, persistence | **Занижено** | В развёрнутой копии: 7 414 + 6 908 + 4 926 = **19 248** строк в трёх файлах |
| Ряд reviews/control-plane/job таблиц без `organization_id` | **Занижено** | Плюс `wb_accounts`, capabilities, health, `source_registry`, `infra_runtime_state` (см. M6) |
| Generated OpenAPI/Pydantic существует, маршруты handwritten | **Занижено** | Generated Pydantic не импортируется вообще; OpenAPI генерится из Zod фронтенда (см. M7) |
| Backend health видит PostgreSQL, Redis и Celery | **Неверно** | Проверяется `bool(env)`; `/health/live`, `/health/ready` → 404 (см. M1) |

### Уже сделано — перенести из «целей» в «сохраняем»

- **Refresh-токен уже в `HttpOnly`/`Secure`/`SameSite` cookie с ротацией и grace-периодом** — `app/routers/auth.py:19–43`, миграция `20260713_0013_refresh_rotation_grace`. §5.2 описывает это как целевое.
- **`AbortController` + request key + защита от A→B→A** — аудит, пп. 11 и 20. §3.6 описывает как целевое.
- **Union SKU (finance-only / funnel-only / goods-only не выпадают)** — аудит, п. 12. §3.5 описывает как целевое.
- **Exact cache key с org + formula version + economics/rules hash** — аудит, пп. 10 и 19. §3.5 описывает более бедную версию (см. H5).

---

## 5. Список правок к спеке

1. **Разделить два финансовых гейта.** Regression против замороженной фикстуры `wb_abc_2026_08_17_23.json` (допуск 0) и сверка против live WB (допуск + правило «поздняя корректировка может исчезнуть»). Сейчас это один гейт с порогом 1 копейка. → §3.3, §6.2, §7.2
2. **Сдвинуть golden dataset на 19.08–25.08.** Период с доказанной себестоимостью, уже отснятый: 3 338 строк, 682 361 964 коп. → §7.2
3. **Ввести третье состояние себестоимости** `configured | assumed | missing` и переносить в backfill все три источника (`TYPE_DEFAULTS`, `cogsByGarmentRub`, `skuSettingsOverrides`) с разным `source`. Признать, что задача первого среза — не схема, а сбор реальной себестоимости. → §1, §8.1, §8.4
4. **Версионировать `taxPct`, `otherExpensePricePct`, `otherExpensePerSaleKopecks`** наравне с COGS, иначе §1 «стоимость на момент операции» держится для одной переменной из четырёх. → §8.1
5. **Добавить в срез 1 инфраструктурные пререквизиты:** rewrite `/api/v2/*` в `vercel.json`; жёсткая ошибка на не-JSON ответ в `parseResponse`; app-роль без BYPASSRLS + `FORCE ROW LEVEL SECURITY` + `SET LOCAL`; убрать `alembic upgrade` из команды запуска API. → §5, §8.3, §9.4
6. **Сделать срез 0 настоящим:** один репозиторий backend вместо четырёх копий; CI с тестами, миграциями и контрактами; удаление in-memory fallback в `_run_db`; устранение глобалов репрайсера. Это предусловия, а не этап после. → §6
7. **Признать реальный объём** вместо строк в таблице §6: 105 нетипизированных роутов, 2 372 строки production-прототипа без тенантности, отдельный Node-сервис КИЗ, 165 мест с собственным `date.today()`, нулевая база под outbox / idempotency / advisory locks.
8. **Добавить владельца и план для `ktr_table`** (Release gate 1 аудита) и **версию cost-ledger'а в ключ кэша** §3.5.
9. **Назначить срез для шифрования credentials.** Сейчас plaintext-токены в БД, `cryptography` нет в зависимостях, а §9.6 обещает шифрованный backup поверх plaintext-данных. → §5.2, §6
10. **Исправить §0.1:** health не проверяет связность; список таблиц без `organization_id` шире; generated Pydantic не используется вообще, а OpenAPI генерится из фронтенда.

---

## 6. Команды для перепроверки

```bash
cd /Users/ilagulakin/Desktop/Work/OgniWB

# B1 — контрольная сумма
grep -n "635 537 451\|635 658 251" .worktrees/backend-wb-abc-production/docs/wb-abc-production-audit-2026-08-26.md

# B2 — цепочка COGS и покрытие override'ов
sed -n '640,661p' ogni-elfs-live/app/wb_reports_sprint_d.py
sed -n '599,620p;678,682p' ogni-elfs-live/app/repricer_bff.py
python3 -c "import json;d=json.load(open('ogni-elfs-live/var/vella_repricer_runtime_state.json'));[print(o,len((p.get('runtimeState') or {}).get('skuSettingsOverrides') or {}),(p.get('algorithmSettings') or {}).get('cogsByGarmentRub')) for o,p in d.items()]"

# B3 — cogsHistory нет в развёрнутых копиях
grep -rn "cogsHistory" ogni-elfs-live/app ogni-elfs-prod/app | wc -l

# B4 — Vercel routing
curl -s -o /dev/null -w "%{http_code} %{content_type}\n" https://satorna-wb.vercel.app/api/v2/catalog/skus
curl -s -o /dev/null -w "%{http_code} %{content_type}\n" https://satorna-wb.vercel.app/api/v1/production/production-skus

# B5 — RLS
grep -rn "ROW LEVEL SECURITY\|set_config\|current_setting" ogni-elfs-live/app ogni-elfs-live/alembic | wc -l

# H1 — CI
find . -maxdepth 4 -name '.github' -o -name '.gitlab-ci.yml' -not -path '*/node_modules/*' | head

# H2 — расхождение копий
diff -rq ogni-elfs-live/app ogni-elfs-prod/app | grep -v __pycache__

# M7 — покрытие типами
grep -rn '@router\.\(get\|post\|put\|patch\|delete\)' --include='*.py' ogni-elfs-live/app | wc -l
grep -rn 'response_model=' --include='*.py' ogni-elfs-live/app | wc -l

# M9 — отсутствующие слои
cd ogni-elfs-live && for t in Idempotency outbox pg_advisory kiz; do echo -n "$t: "; grep -rin "$t" --include='*.py' app | wc -l; done
```
