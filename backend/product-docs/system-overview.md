# System overview: Ogni / Vella

Обновлено: 2026-06-23.

Этот документ описывает текущую систему целиком: backend `ogni-elfs` и frontend `ogni-react-frontend/frontend`, как они связаны, какие домены уже есть, где живут данные, как запускается проект и куда смотреть при доработках.

## 1. Что это за проект

Ogni / Vella - SaaS для команды "Огни", сейчас в фокусе WB-first замена INDEEPA:

- WB репрайсер;
- WB отчеты: дайджест, ABC, РНП, P&L, реклама, остатки, week-over-week;
- ликвидация товаров;
- акции WB;
- автоответы на отзывы WB в draft-first режиме;
- личный кабинет, роли, WB token, сессии, audit;
- позже: Avito, заказы, производство, кошельки, мультиаккаунт.

Главный принцип системы: если источник данных не подтвержден или устарел, backend должен возвращать typed state (`fresh`, `partial`, `stale`, `blocked`, `unknown`, `manual_fallback`), а не имитировать production-ready данные.

## 2. Репозитории

| Слой | Путь | Назначение |
|---|---|---|
| Backend | `C:\Users\porka\OneDrive\Рабочий стол\folders\кодерские архивы\ogni-elfs` | FastAPI API, WB adapters, PostgreSQL/Redis/Celery, contracts, migrations, tests |
| Frontend | `C:\Users\porka\OneDrive\Рабочий стол\folders\кодерские архивы\ogni-react-frontend\frontend` | React/Vite UI, Vella shell/parity layer, feature pages, API clients, visual QA scripts |

В backend также лежит `product-docs/` - продуктовые handoff/spec документы, source registry и материалы по WB replacement.

## 3. Архитектура верхнего уровня

```text
Browser
  |
  v
React/Vite frontend
  |  /api/* через Vite proxy или VITE_API_BASE_URL
  v
FastAPI backend
  |
  +-- Auth/Cabinet/Settings/Notifications
  +-- WB Reports BFF + Sprint D contracts
  +-- WB Repricer BFF + strategies + guards
  +-- WB Reviews service
  +-- Source Registry / Control Plane / Account Health
  |
  +-- PostgreSQL via SQLAlchemy/Alembic
  +-- Redis cache/result backend
  +-- Celery worker + Celery beat
  |
  v
WB typed adapters
  |
  +-- fake fixtures by default
  +-- real WB API when VELLA_WB_API_MODE=real and tokens are set
```

## 4. Backend stack

Backend - Python 3.11+ приложение на FastAPI.

Основные зависимости:

- `fastapi`, `pydantic v2`, `uvicorn`;
- `sqlalchemy`, `alembic`, `psycopg`;
- `redis`, `celery`;
- `httpx` для real WB API clients;
- `pytest`, `datamodel-code-generator` для тестов и contract models.

Главные entrypoints:

- `app/main.py` - создает FastAPI app, CORS, error envelope handlers, `/health`, подключает routers;
- `app/config.py` - все env-настройки и feature flags;
- `app/infra/db.py` - SQLAlchemy engine/session;
- `app/infra/celery_app.py` - Celery app и beat schedule;
- `app/repricer_tasks.py` - фоновые задачи репрайсера и WB sync.

## 5. Backend запуск

Локально:

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -e .[test]
.\.venv\Scripts\python -m uvicorn app.main:app --reload
```

Проверка:

```powershell
.\.venv\Scripts\python -m pytest -q tests backend_contracts\tests
```

Docker stack:

```powershell
docker compose up --build
```

Поднимаются:

- `postgres`;
- `redis`;
- `api`;
- `worker`;
- `beat`.

В compose API внутри контейнера слушает `8000`, наружу пробрасывается `${VELLA_API_HOST_PORT:-8001}`.

## 6. Backend env и режимы

Ключевые flags из `app/config.py` и `docker-compose.yml`:

| Env | По умолчанию | Что делает |
|---|---:|---|
| `VELLA_WB_API_MODE` | `fake` | `fake` использует fixtures, `real` ходит в WB API |
| `VELLA_REAL_PRICE_APPLY_ENABLED` | `false` | разрешает реальную отправку цен в WB |
| `VELLA_REPRICER_LOCAL_PRICE_APPLY_ENABLED` | `true` | разрешает local mock apply без WB mutation |
| `VELLA_REPRICER_PRESERVE_LOCAL_PRICE_OVERRIDES` | `true` | сохраняет локальные override цены |
| `VELLA_REPRICER_SCHEDULER_ENABLED` | `true` в коде, `false` в compose | включает auto execute assigned strategies |
| `VELLA_REPRICER_WB_SYNC_ENABLED` | `true` | включает периодический WB sync |
| `VELLA_DATABASE_URL` | local PostgreSQL | подключение к БД |
| `VELLA_REDIS_URL` | local Redis | Redis для Celery/cache |
| `VELLA_AUTH_SECRET` | dev default | подпись access/refresh auth |
| `VELLA_CORS_ALLOWED_ORIGINS` | localhost 5173/5174 | фронтовые origins |

WB tokens разделены по API зонам:

- `VELLA_WB_API_TOKEN`;
- `VELLA_WB_STATISTICS_API_TOKEN`;
- `VELLA_WB_FINANCE_API_TOKEN`;
- `VELLA_WB_COMMON_API_TOKEN`;
- `VELLA_WB_ANALYTICS_API_TOKEN`;
- `VELLA_WB_CONTENT_API_TOKEN`;
- `VELLA_WB_PROMOTIONS_API_TOKEN`;
- `VELLA_WB_ADS_API_TOKEN`;
- `VELLA_WB_FEEDBACKS_API_TOKEN`.

Raw tokens и raw external payloads не должны попадать в logs/API responses.

## 7. Backend API домены

### Auth

Файлы:

- `app/routers/auth.py`;
- `app/cabinet/store.py`;
- `app/cabinet/permissions.py`;
- `app/cabinet/orm.py`.

Endpoints:

- `POST /api/v1/auth/register`;
- `POST /api/v1/auth/login`;
- `POST /api/v1/auth/refresh`;
- `POST /api/v1/auth/logout`.

Схема:

- access token короткоживущий;
- refresh token хранится в `HttpOnly` cookie;
- refresh rotation на `/refresh`;
- frontend хранит access token и умеет автоматически refresh/retry после `401`.

### Cabinet / LK

Endpoints:

- `GET /api/v1/cabinet/me`;
- `GET /api/v1/cabinet/team/users`;
- `POST /api/v1/cabinet/team/users`;
- `PATCH /api/v1/cabinet/team/users/{userId}/permission-profile`;
- `GET /api/v1/cabinet/sessions`;
- `GET /api/v1/cabinet/sessions/current`;
- `POST /api/v1/cabinet/sessions/revoke-others`;
- `POST /api/v1/cabinet/sessions/{sessionId}/revoke`;
- `GET /api/v1/cabinet/integrations`;
- `PUT /api/v1/cabinet/integrations/{provider}`;
- `GET /api/v1/cabinet/wb-token`;
- `PUT /api/v1/cabinet/wb-token`;
- `DELETE /api/v1/cabinet/wb-token`;
- `GET /api/v1/cabinet/audit/events`;
- `GET /api/v1/cabinet/preferences`;
- `PUT /api/v1/cabinet/preferences`.

Permission profiles:

- `viewer`;
- `settings_editor`;
- `price_sender`;
- `finance_viewer`;
- `admin`;
- `custom`.

### Source Registry

Файлы:

- `app/source_registry/*`;
- `app/routers/source_registry.py`;
- `product-docs/wb-repricer-data-sources.md`;
- `contracts/openapi/v1.yaml`.

Endpoints:

- `GET /api/v1/source-registry`;
- `GET /api/v1/source-registry/entries`;
- `GET /api/v1/source-registry/entries/paginated`;
- `GET /api/v1/source-registry/blockers/catalog`;
- `GET /api/v1/source-registry/blockers/catalog/paginated`;
- `GET /api/v1/source-registry/formulas`;
- `GET /api/v1/source-registry/formulas/paginated`;
- `GET /api/v1/source-registry/entries/unresolved-blockers`.

Назначение: держать карту "UI metric/action -> backend field -> source -> formula -> freshness/fallback/blockers".

### Control Plane

Файлы:

- `app/control_plane/*`;
- `app/routers/control_plane.py`.

Endpoints:

- settings versions: create/list/read/diff/activate;
- audit events;
- sync jobs;
- price apply routes.

Опасные действия должны идти по схеме:

```text
draft -> preview/diff -> approval -> commit -> audit
```

Реальная отправка цены в WB закрыта флагом `VELLA_REAL_PRICE_APPLY_ENABLED`.

### WB API adapter layer

Файлы:

- `app/wb_api/client.py`;
- `app/wb_api/price_units.py`;
- `app/wb_api/reports_sources_runtime.py`;
- `app/wb_api/ads_runtime.py`;
- `app/wb_api/feedbacks_runtime.py`.

Слой делает:

- typed request/response envelope;
- fake client fixtures;
- real `httpx` client;
- error classification: auth, billing, scope, rate limit, server error;
- rate-limit metadata;
- разные client builders для prices, ads, statistics, analytics, finance, common, content, promotions, feedbacks.

Все внешние WB вызовы должны идти через typed adapters.

### WB Reports

Есть две API зоны:

- `/api/v1/wb-reports/...` - contract/runtime слой Sprint D;
- `/api/wb/reports/...` - BFF слой под frontend reports UI.

Файлы:

- `app/routers/wb_reports_sprint_d.py`;
- `app/wb_reports_sprint_d.py`;
- `app/routers/wb_reports_bff.py`;
- `app/reports_exports.py`;
- `app/reports_history.py`.

Sprint D endpoints:

- `GET /api/v1/wb-reports/pnl`;
- `GET /api/v1/wb-reports/ads/performance`;
- `GET /api/v1/wb-reports/rnp`;
- `GET /api/v1/wb-reports/abc`;
- `GET /api/v1/wb-reports/plan-fact`;
- `GET /api/v1/wb-reports/sku-rating`;
- `GET /api/v1/wb-export/current-view`.

BFF endpoints:

- `GET /api/wb/reports/digest`;
- `GET /api/wb/reports/alerts`;
- `GET /api/wb/reports/export/{report_id}`;
- `POST /api/wb/reports/export/{report_id}`;
- `GET /api/wb/reports/export/jobs/{export_id}`;
- `GET /api/wb/reports/{report_id}`.

Reports собираются из WB runtime snapshots, ads attribution, derived formulas и fallback states.

### WB Repricer

Файлы:

- `app/routers/wb_repricer_bff.py`;
- `app/repricer_bff.py`;
- `app/repricer_sync.py`;
- `app/repricer_execution.py`;
- `app/repricer_sprint_b.py`;
- `app/repricer_sprint_c.py`;
- `app/repricer_settings.py`;
- `app/repricer_cache/*`;
- `app/repricer_persistence/*`;
- `app/wb22_apply.py`;
- `app/wb23_runtime.py`.

Главные блоки:

- SKU list и карточка SKU;
- settings per SKU: себестоимость, комиссии, логистика, P_min/P_max, automation;
- manager assignment;
- стратегии и bulk assignment;
- preview/execute strategies;
- simulator;
- promotions;
- liquidation;
- changelog;
- pricing status и timeseries;
- WB sync status/run;
- Excel imports for costs/stocks.

Ключевые endpoints:

- `GET /api/v1/wb-repricer/sku`;
- `GET /api/v1/wb-repricer/sku/{articleId}/settings`;
- `PUT /api/v1/wb-repricer/sku/{articleId}/settings`;
- `PATCH /api/v1/wb-repricer/sku/{articleId}/automation`;
- `POST /api/v1/wb-repricer/sku/{articleId}/manager-simple`;
- `GET /api/v1/wb-repricer/dashboard`;
- `GET /api/v1/wb-repricer/templates`;
- `PUT /api/v1/wb-repricer/templates`;
- `GET /api/v1/wb-repricer/strategies/catalog`;
- `GET /api/v1/wb-repricer/strategy-assignments`;
- `POST /api/v1/wb-repricer/strategy-assignments/bulk`;
- `POST /api/v1/wb-repricer/strategies/preview`;
- `POST /api/v1/wb-repricer/strategies/execute`;
- `POST /api/v1/wb-repricer/strategies/execute-assigned`;
- `GET /api/v1/wb-repricer/simulator`;
- `PUT /api/v1/wb-repricer/simulator/sku/{articleId}`;
- `POST /api/v1/wb-repricer/simulator/run`;
- `GET /api/v1/wb-repricer/liquidation`;
- `POST /api/v1/wb-repricer/liquidation/start`;
- `POST /api/v1/wb-repricer/liquidation/{articleId}/stop`;
- `POST /api/v1/wb-repricer/liquidation/{articleId}/confirm-negative`;
- `GET /api/v1/wb-repricer/algorithm`;
- `PUT /api/v1/wb-repricer/algorithm`;
- `GET /api/v1/wb-repricer/promotions`;
- `GET /api/v1/wb-repricer/promotions/{promoId}/skus`;
- `POST /api/v1/wb-repricer/promotions/{promoId}/upload-excel`;
- `POST /api/v1/wb-repricer/promotions/upload-excel`;
- `GET /api/v1/wb-repricer/changelog`;
- `GET /api/v1/wb-repricer/sku/{articleId}/changelog`;
- `GET /api/v1/wb-repricer/work-status`;
- `GET /api/v1/wb-repricer/sku/{articleId}/pricing-status`;
- `GET /api/v1/wb-repricer/sku/{articleId}/timeseries`.

Refresh endpoints:

- `POST /api/v1/wb-repricer/sku/refresh`;
- `POST /api/v1/wb-repricer/sku/refresh-content`;
- `POST /api/v1/wb-repricer/sku/refresh-promotions`;
- `POST /api/v1/wb-repricer/sku/refresh-stocks`;
- `POST /api/v1/wb-repricer/sku/refresh-period-stats`;
- `POST /api/v1/wb-repricer/sku/refresh-finance`;
- `POST /api/v1/wb-repricer/sku/refresh-ads`;
- `POST /api/v1/wb-repricer/sku/refresh-baskets`.

Excel imports:

- `POST /api/v1/wb-repricer/imports/costs-excel`;
- `POST /api/v1/wb-repricer/imports/stocks-excel`.

Core formulas/guards:

- `P_min = (COGS + logistics) / (1 - commissionPct - minMarginPct)`;
- all money values are integer kopecks;
- price step guards use per-update and per-day limits;
- SPP/freeze state can block apply;
- real WB mutation happens only through `run_price_apply` in `app/wb22_apply.py`.

### WB Repricer background jobs

`app/infra/celery_app.py` registers beat schedule:

- `repricer-sync-wb-data` -> `repricer.sync_wb_data_all_orgs`;
- `repricer-execute-assigned` -> `repricer.execute_assigned_all_orgs`.

`app/repricer_tasks.py`:

- hydrates repricer runtime state for organization;
- skips execution if scheduler disabled or WB sync is running;
- reads WB token;
- loads/caches goods;
- runs `execute_all_assigned_skus`;
- flushes runtime state back to persistence;
- records WB sync notification after sync status changes.

### WB Reviews

Файлы:

- `app/routers/wb_reviews.py`;
- `app/reviews/service.py`;
- `app/reviews/schemas.py`;
- `app/reviews/orm.py`;
- `app/wb_api/feedbacks_runtime.py`.

Endpoints:

- `GET /api/v1/wb-reviews/settings`;
- template/stop-topic/moderation-rule create/update;
- `POST /api/v1/wb-reviews/sync`;
- `GET /api/v1/wb-reviews/feedbacks`;
- `GET /api/v1/wb-reviews/feedbacks/{feedbackId}`;
- `POST /api/v1/wb-reviews/drafts/generate`;
- `GET /api/v1/wb-reviews/drafts/{draftId}`;
- `GET /api/v1/wb-reviews/drafts/{draftId}/prompt-trace`;
- `POST /api/v1/wb-reviews/drafts/{draftId}/approve`;
- `POST /api/v1/wb-reviews/drafts/{draftId}/reject`;
- `POST /api/v1/wb-reviews/drafts/{draftId}/send`;
- `GET /api/v1/wb-reviews/send-jobs/{sendJobId}`;
- `GET /api/v1/wb-reviews/{reviewId}/approval`.

Логика: отзывы синхронизируются, draft генерируется по шаблону/рейтингу/бренд-голосу, проходит moderation rules, затем approve/reject/send. External send дополнительно закрыт `VELLA_WB_FEEDBACKS_SEND_ENABLED`.

### Notifications

Файлы:

- `app/notifications.py`;
- `app/routers/notifications.py`.

Endpoints:

- `GET /api/v1/notifications`;
- `POST /api/v1/notifications/{notificationId}/read`;
- `POST /api/v1/notifications/read-all`.

Notifications хранятся в `wb_repricer_source_cache` под source key `notifications`. WB sync может писать системные уведомления: completed, partial, failed, stale.

## 8. Backend хранение данных

Основные таблицы:

| Prefix/table | Назначение |
|---|---|
| `lk_organizations` | организации |
| `lk_users` | пользователи |
| `lk_user_permissions` | permission list |
| `lk_sessions` | auth sessions и refresh token hash |
| `lk_integrations` | marketplace integrations |
| `lk_user_wb_tokens` | WB token пользователя, masked token для UI |
| `lk_audit_events` | audit личного кабинета |
| `lk_user_preferences` | пользовательские preferences |
| `cp_settings_versions` | версии настроек control plane |
| `cp_audit_events` | audit risky actions/settings |
| `cp_sync_jobs` | sync jobs |
| `source_registry_entries` | source registry rows |
| `source_registry_blockers` | blocker catalog |
| `source_registry_formulas` | formula catalog |
| `wb_accounts` / `wb_account_*` | health/capabilities/token checks |
| `wb_repricer_goods_cache` | cached WB catalog goods pages |
| `wb_repricer_source_cache` | source caches: content, stocks, finance, ads, notifications, etc. |
| `wb_repricer_runtime_state` | runtime state per organization |
| `wb_repricer_algorithm_settings` | algorithm settings per organization |
| `wb_repricer_execution_runs` | strategy execution reports |
| `wb_repricer_changelog` | repricer changelog |
| `rv_review_*` | review templates, stop topics, feedbacks, drafts, send jobs, prompt traces |
| `infra_runtime_state` | simple infra validation state |

Migrations лежат в `alembic/versions`.

## 9. Frontend stack

Frontend - React 19 + TypeScript + Vite.

Основные зависимости:

- `react`, `react-dom`, `react-router-dom`;
- `zod`;
- `lucide-react`;
- Radix/shadcn-style primitives;
- Tailwind utilities;
- MSW for dev mocks;
- Playwright/pixelmatch scripts for visual parity checks.

Entrypoints:

- `src/main.tsx` - MSW bootstrap и React mount;
- `src/App.tsx` - routing, auth gates, protected app;
- `src/index.css` - global styles;
- `vite.config.ts` - alias `@` and optional `/api` proxy through `VITE_API_PROXY_TARGET`.

## 10. Frontend запуск

```powershell
npm install
npm run dev
```

Build/typecheck/test:

```powershell
npm run build
npm run typecheck
npm run test
```

Полезные env:

| Env | Что делает |
|---|---|
| `VITE_API_BASE_URL` | base URL для `apiRequest/apiData` |
| `VITE_API_PROXY_TARGET` | Vite dev proxy target для `/api` |
| `VITE_ENABLE_MSW=true` | включает MSW в dev |
| `VITE_AUTH_BYPASS=true` | dev bypass auth |

## 11. Frontend routing

`src/App.tsx`:

- `/auth/login`, `/auth/register` доступны только anonymous пользователю;
- почти все остальные маршруты идут через `RequireAuth`;
- `/` и `/dashboard` редиректят на `/wb/repricer`;
- основные production-like WB pages рендерятся через `VellaHtmlParityPage`;
- часть внутренних preview routes рендерит React pages или static/parity views.

Основные пользовательские маршруты:

- `/wb/repricer`;
- `/wb/repricer/sku/:articleId`;
- `/wb/repricer/changelog`;
- `/wb/repricer/simulator`;
- `/wb/repricer/liquidation`;
- `/wb/repricer/promos`;
- `/wb/repricer/work-status`;
- `/wb/algorithm`;
- `/wb/templates`;
- `/wb/promotions`;
- `/wb/liquidation`;
- `/wb/reports`;
- `/wb/reports/abc`;
- `/wb/reports/rnp`;
- `/wb/reports/pnl`;
- `/wb/reports/ads`;
- `/wb/reports/sales`;
- `/wb/reports/stock`;
- `/wb/reports/week-over-week`;
- `/wb/reviews`;
- `/notifications`;
- `/settings/profile`;
- `/settings/access`;
- `/settings/imports`;
- `/settings`;
- `/orders`;
- `/wiki/...`;
- `/avito/...` mostly preview/coming-soon/parity routes.

Navigation config:

- `src/config/navigation.ts`;
- `src/lib/routes.ts`.

## 12. Frontend auth flow

Файлы:

- `src/features/auth/AuthProvider.tsx`;
- `src/features/auth/authApi.ts`;
- `src/features/auth/AuthRoutes.tsx`;
- `src/lib/api.ts`;
- `src/lib/authTokenStore.ts`.

Flow:

1. User logs in through `/api/v1/auth/login`.
2. Backend returns `accessToken`; refresh token is stored as cookie.
3. Frontend stores access token through `authTokenStore`.
4. `AuthProvider` hydrates `/api/v1/cabinet/me` and `/api/v1/cabinet/sessions`.
5. `window.fetch` is wrapped to attach `Authorization: Bearer`.
6. `apiRequest` and fetch wrapper can refresh token on `401`, then retry.
7. Logout calls `/api/v1/auth/logout`, then clears local auth state.

## 13. Frontend API clients

Shared API helper:

- `src/lib/api.ts`;
- `apiRequest<T>()` parses JSON/errors;
- `apiData<T>()` unwraps backend `DataEnvelope<T>`;
- supports `VITE_API_BASE_URL`;
- retries once after access-token refresh.

Feature API clients:

| File | Backend zone |
|---|---|
| `src/features/auth/authApi.ts` | `/api/v1/auth`, `/api/v1/cabinet` |
| `src/features/settings/backend.ts` | cabinet team/users/integrations/audit/preferences/WB token |
| `src/features/notifications/api.ts` | `/api/v1/notifications` |
| `src/features/wb-reports/api.ts` | `/api/wb/reports/...` |
| `src/features/wb-repricer/liveParityData.ts` | `/api/v1/wb-repricer/...` |
| `src/features/wb-repricer/schemas.ts` | Zod schemas/contracts for repricer |
| `src/features/wb-contracts/sourceState.ts` | source state schemas |

## 14. Frontend UI architecture

Есть два слоя UI:

### Normal React app shell

Файлы:

- `src/layouts/AppShell.tsx`;
- `src/layouts/AppSidebar.tsx`;
- `src/layouts/AppHeader.tsx`;
- `src/components/ui/*`;
- `src/components/ThemeProvider.tsx`;
- `src/components/CommandPalette.tsx`.

Этот слой отвечает за shell, sidebar, header, themes, command palette, settings/wiki/stub pages.

### Vella parity/runtime bridge

Главный файл:

- `src/features/vella-parity/VellaHtmlParityPage.tsx`.

Это гибридный слой, который:

- берет production-like Vella HTML/runtime;
- рендерит его внутри React;
- патчит legacy DOM/runtime функции;
- подключает backend auth profile;
- грузит live repricer products, strategies, sku groups, promotions, settings, notifications;
- пишет данные в `window.__vella...`;
- вызывает backend endpoints для refresh/import/preview/execute;
- сохраняет parity поведение и визуальный контракт.

Этот слой важен: многие боевые WB страницы сейчас не являются чистыми React-компонентами, а работают через bridge между legacy HTML runtime и typed backend calls.

## 15. Frontend feature map

| Feature | Основные файлы | Состояние |
|---|---|---|
| Auth | `src/features/auth/*` | подключен к backend |
| Settings | `src/features/settings/*` | backend snapshot + UI |
| Notifications | `src/features/notifications/*` | backend source cache |
| WB reports | `src/features/wb-reports/*`, parity page | BFF + local contracts/fixtures |
| WB repricer | `src/features/wb-repricer/*`, `liveParityData.ts`, parity page | live BFF + simulator + schemas |
| Vella parity | `src/features/vella-parity/*` | основной bridge |
| Vella static/react | `src/features/vella-static/*`, `src/features/vella-react/*` | preview/internal routes |
| Wiki | `src/wiki/*` | справка |
| Avito | `src/features/avito/*`, parity routes | mostly preview/future |
| Orders | `src/features/orders/*` | production/order print list stub/workflow |

## 16. Главный runtime flow: WB repricer page

```text
User opens /wb/repricer
  -> App.tsx protects route with RequireAuth
  -> VellaHtmlParityPage mounts production-like Vella UI
  -> AuthProvider attaches Bearer token
  -> liveParityData loads /api/v1/wb-repricer/sku
  -> backend list_repricer_skus builds rows from:
       WB goods cache or WB catalog
       content cards
       promotions
       stocks
       period stats
       finance
       ads
       baskets
       local settings/runtime overrides
  -> response is mapped to parity products
  -> user can refresh sources, edit settings, assign manager/strategy, preview/execute, import Excel
  -> backend persists runtime/cache/changelog/execution reports
```

## 17. Главный runtime flow: WB sync

```text
User or Celery beat starts sync
  -> /api/v1/wb-repricer/sync/run or scheduled repricer.sync_wb_data_all_orgs
  -> repricer_sync.begin_wb_sync marks state running
  -> refresh_wb_data_sources loads selected sources:
       goods, content, promotions, stocks, period-stats, finance, ads, baskets
  -> each source is cached in wb_repricer_source_cache / goods cache
  -> finish_wb_sync writes completed/partial/failed/stale status
  -> notification is recorded for UI
```

## 18. Главный runtime flow: strategy execution

```text
User previews or executes strategy
  -> frontend calls /api/v1/wb-repricer/strategies/preview or /execute
  -> repricer_execution resolves assigned/selected strategy
  -> calculates recommended seller price
  -> applies guards: P_min/P_max, step limits, SPP/freeze/source states
  -> preview returns report without mutation
  -> execute can call price apply
  -> wb22_apply blocks unless real apply flag is enabled or local mock apply is allowed
  -> execution run/changelog are persisted
```

## 19. Главный runtime flow: reports

```text
User opens /wb/reports/*
  -> VellaHtmlParityPage or reports API layer requests /api/wb/reports/...
  -> BFF builds digest/report/export payload
  -> Sprint D layer can provide contract-shaped /api/v1/wb-reports/...
  -> WB source runtime and ads attribution snapshots normalize external data
  -> frontend renders freshness/source status/alerts/table/chart/export states
```

## 20. Contracts

Backend contracts:

- `contracts/openapi/v1.yaml`;
- `app/contracts/vella_wb_19_05_generated.py`;
- `app/contracts/envelopes.py`;
- `app/contracts/adapter_result.py`;
- `backend_contracts/vella_wb_19_05/*`.

Frontend contracts:

- `src/features/wb-repricer/schemas.ts`;
- `src/features/wb-reports/types.ts`;
- `src/features/wb-contracts/sourceState.ts`;
- `src/features/vella-parity/vellaBackendContracts.ts`.

Conventions:

- success envelope: `{ data, timestamp }`;
- paginated envelope: `{ items, total, limit, offset, timestamp }`;
- error envelope: `{ error: { code, message, details }, timestamp }`;
- money: integer kopecks;
- datetime: UTC-aware ISO;
- sources: typed status + confidence + blocker ids + evidence.

## 21. Safety rules

Production-sensitive rules:

- WB calls only through typed adapters;
- real WB price mutation only when `VELLA_REAL_PRICE_APPLY_ENABLED=true`;
- feedback send only when `VELLA_WB_FEEDBACKS_SEND_ENABLED=true`;
- token values never leak to frontend except masked token;
- unknown/stale/blocked sources must be explicit in response;
- P&L finance fields depend on permission profile;
- campaign-only ads attribution must not be allocated into exact SKU P&L;
- risky actions need audit trail and, where applicable, approval.

## 22. Тесты и проверки

Backend:

```powershell
.\.venv\Scripts\python -m pytest -q tests backend_contracts\tests
```

Frontend:

```powershell
npm run typecheck
npm run test
npm run build
```

Visual/parity scripts exist in `package.json`:

- `visual:vella-page-parity:*`;
- `contract:vella-page:*`;
- `smoke:vella-system`;
- `smoke:vella-react`;
- `smoke:vella-page-interactions`;
- `smoke-openapi`.

## 23. Где что менять

| Нужно изменить | Backend | Frontend |
|---|---|---|
| Новый auth/cabinet endpoint | `app/routers/cabinet.py`, `app/cabinet/*` | `src/features/auth/authApi.ts`, `src/features/settings/backend.ts` |
| Новый WB source | `app/wb_api/*`, `app/repricer_sync.py`, cache store | `liveParityData.ts`, parity bridge |
| Новое поле SKU | `app/repricer_bff.py`, schemas/tests | `liveParityData.ts`, `schemas.ts`, parity rendering |
| Новая стратегия | `app/repricer_execution.py`, `app/repricer_sprint_c.py` | strategy UI in parity / `liveParityData.ts` |
| Новый отчет | `app/wb_reports_sprint_d.py` or `wb_reports_bff.py` | `src/features/wb-reports/*`, parity page |
| Новая настройка алгоритма | `app/repricer_bff.py`, `app/repricer_settings.py` | algorithm page / parity algorithm handlers |
| Excel import | `app/wb_import_excel.py`, router endpoint | Settings import UI / parity upload controls |
| Notification type | `app/notifications.py` | `src/features/notifications/*`, parity notifications |
| DB schema | `app/**/orm.py`, Alembic migration | API mapping if exposed |

## 24. Важные файлы

Backend:

- `README.md`;
- `app/main.py`;
- `app/config.py`;
- `app/routers/*`;
- `app/repricer_bff.py`;
- `app/repricer_execution.py`;
- `app/repricer_sync.py`;
- `app/wb_api/client.py`;
- `app/wb_reports_sprint_d.py`;
- `app/reviews/service.py`;
- `alembic/versions/*`;
- `contracts/openapi/v1.yaml`;
- `tests/*`.

Frontend:

- `src/App.tsx`;
- `src/main.tsx`;
- `src/lib/api.ts`;
- `src/features/auth/*`;
- `src/features/vella-parity/VellaHtmlParityPage.tsx`;
- `src/features/wb-repricer/liveParityData.ts`;
- `src/features/wb-repricer/schemas.ts`;
- `src/features/wb-reports/*`;
- `src/features/settings/*`;
- `src/config/navigation.ts`;
- `package.json`;
- `vite.config.ts`.

Product docs:

- `product-docs/00-START-HERE.md`;
- `product-docs/AGENTS.md`;
- `product-docs/wb-repricer-data-sources.md`;
- `product-docs/docs/specs/indeepa-wb-replacement/*`;
- `product-docs/docs/handoffs/*`;
- `product-docs/contracts/openapi/v1.yaml`.

## 25. Текущая картина зрелости

Уже есть:

- backend skeleton + migrations + Docker stack;
- auth/cabinet/session/token flows;
- source registry;
- WB adapters with fake/real modes;
- repricer BFF with live source refresh/cache;
- strategy preview/execute pipeline;
- local/mock and real-flagged price apply;
- reports runtime/BFF;
- reviews draft/approval/send-job service;
- frontend protected routes and Vella parity bridge;
- visual/contract/smoke scripts.

Гибридные или требующие аккуратности зоны:

- `VellaHtmlParityPage.tsx` очень большой и держит много runtime bridge-логики;
- часть frontend reports data все еще имеет fixture/contract слой рядом с BFF;
- real WB mode требует корректных tokens/scopes и осторожного rate-limit поведения;
- production price mutation запрещена без явного feature flag;
- Avito в UI присутствует как направление/preview, но не как полноценный backend module.

