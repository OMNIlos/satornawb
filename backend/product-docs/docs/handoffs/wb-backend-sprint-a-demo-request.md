# WB backend Sprint A demo request

**Статус:** отправить backend-разработчику перед первым демо  
**Связано:** `docs/handoffs/wb-backend-sprint-a-stub-pack.md`, `docs/handoffs/wb-19-05-backend-contract-handoff.md`  
**Цель демо:** показать foundation и contract-shaped blocked states, а не готовый production расчет.

## Что показать на демо

Backend-разработчик показывает локально:

1. Как поднять backend одной командой из README.
2. `pytest` или эквивалент test command.
3. `GET /health`.
4. Генерацию/подключение Pydantic моделей из `contracts/openapi/v1.yaml`.
5. Source/blocker registry с seed по WB-02/WB-03/WB-06/WB-11/WB-12/WB-13/WB-14A/WB-19A/WB-22/WB-23.
6. Пять 19.05 stubs: P&L, Ads, РНП, ABC, SPP guard.
7. Negative tests, которые запрещают ложную production-готовность.

## Команды перед демо

В этом repo:

```bash
cd "/Users/dima/Downloads/Projects/SAAS для Огней/frontend"
npm run smoke-openapi
```

В backend repo:

```bash
pytest
python -m py_compile app/contracts/vella_wb_19_05.py
```

Если в backend repo другие команды, README должен явно дать equivalent commands.

## Demo endpoints

Backend должен открыть или показать `curl`/HTTP client output для этих запросов.

### Health

```bash
curl -s http://localhost:8000/health
```

Ожидаемо:

```json
{"status":"ok"}
```

### Source registry

```bash
curl -s "http://localhost:8000/api/v1/source-registry?module=wb"
```

Что должно быть видно:

- blocker IDs из Sprint A stub pack;
- `status=blocked|unknown`, а не `ready`;
- `nextAction`;
- ссылка/строка evidence на `docs/open-questions-current.md`.

### P&L financial

```bash
curl -s "http://localhost:8000/api/v1/wb-reports/pnl?source=financial&dateFrom=2026-05-01&dateTo=2026-05-19&groupBy=sku"
```

Pass criteria:

- `reportState` не `final`;
- `blockerIds` содержит `WB-12`, `WB-13`, `WB-23`;
- `fieldMapping` присутствует;
- нет финальной чистой прибыли, если ручные расходы/налоги не подтверждены.

### Ads campaign

```bash
curl -s "http://localhost:8000/api/v1/wb-reports/ads/performance?dateFrom=2026-05-01&dateTo=2026-05-19&groupBy=campaign"
```

Pass criteria:

- `blockerIds` содержит `WB-02`;
- `attributionPolicy.campaignOnlyCanAllocateToSkuPnl=false`;
- `allowedSkuLevels` не содержит `campaign_only` и `unknown`;
- campaign-only rows, если есть, не имеют `confidence=high`.

### Ads SKU

```bash
curl -s "http://localhost:8000/api/v1/wb-reports/ads/performance?dateFrom=2026-05-01&dateTo=2026-05-19&groupBy=sku"
```

Pass criteria:

- нет SKU-row с `attributionLevel=campaign_only|unknown`;
- если SKU attribution не подтверждена, весь ответ честно `blocked/partial` с `WB-02`.

### РНП

```bash
curl -s "http://localhost:8000/api/v1/wb-reports/rnp?dateFrom=2026-05-01&dateTo=2026-05-19&groupBy=sku"
```

Pass criteria:

- если `drrPct=null`, есть `WB-11`;
- если `adsSourceStatus=blocked|unknown`, есть `WB-02`;
- период совпадает с запрошенным.

### ABC filtered summary

```bash
curl -s "http://localhost:8000/api/v1/wb-reports/abc?dateFrom=2026-05-01&dateTo=2026-05-19&groupBy=sku"
```

Pass criteria:

- есть `filteredSummary`;
- `filterHash` не пустой;
- рекламные поля могут быть null/blocked, но весь ABC не обязан падать;
- если агрегаты по локомотивам не подтверждены, есть `WB-19A`.

### SPP price guard

```bash
curl -s "http://localhost:8000/api/v1/wb-repricer/sku/FBBT_42/price-guard"
```

Pass criteria:

- `canApply=false`;
- `freezeState=source_blocked`;
- `blockerIds` содержит `WB-06`, `WB-22`, `WB-23`;
- есть blocker trigger `source_stale`;
- нет имитации успешной отправки цены.

## Negative tests to show

Backend должен показать имена тестов или test report, где явно есть проверки:

| Test | Проверяет |
|---|---|
| `test_pnl_final_rejects_blockers` | final P&L невозможен с unresolved blockers. |
| `test_ads_sku_rejects_campaign_only` | SKU Ads не принимает campaign-only attribution. |
| `test_ads_blocked_requires_wb02` | blocked/unknown Ads требует `WB-02`. |
| `test_rnp_missing_drr_requires_wb11` | missing DRR требует `WB-11`. |
| `test_price_guard_apply_rejects_blockers` | `canApply=true` невозможен с blockers. |
| `test_price_guard_apply_rejects_stale_spp` | stale/blocked SPP не дает apply. |

Названия могут отличаться, но смысл должен быть покрыт.

## Что считается провалом демо

Демо не принимается, если:

- backend возвращает `reportState=final` для P&L с unresolved `WB-12/WB-13`;
- Ads `campaign_only` попадает в SKU строки как точная атрибуция;
- SPP guard возвращает `canApply=true` без подтвержденного SPP source и price apply status;
- blocked source превращается в generic `500`, пустой массив или молчаливый mock;
- route handler напрямую вызывает WB API, обходя adapter envelope;
- README не объясняет, где взять OpenAPI artifact и как обновить generated Pydantic.

## Вопросы, которые backend должен вернуть после демо

После первого demo backend должен ответить:

1. Генерируемые Pydantic модели удобны для FastAPI response models или нужна правка OpenAPI/Zod?
2. Какие source registry поля стоит добавить до Sprint B?
3. Какие blockers требуют live WB token discovery первыми: `WB-02`, `WB-06`, `WB-22`, `WB-23`?
4. Какие endpoints можно оставить blocked stubs, а какие нужно расширить до Sprint B?
5. Есть ли риск, что текущий contract shape заставит backend писать ручные модели?

## Decision after demo

Если demo проходит:

- Sprint A продолжается в account/token health, source registry, settings/audit/sync jobs;
- Sprint B planning можно начинать вокруг SPP guard and price apply discovery.

Если demo не проходит:

- не трогаем Vella UI;
- сначала правим contract/stub boundary;
- затем повторяем demo на тех же endpoints.
