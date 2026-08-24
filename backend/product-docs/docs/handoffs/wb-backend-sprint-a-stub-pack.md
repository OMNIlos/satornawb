# WB backend Sprint A stub pack

**Статус:** implementation checklist for first FastAPI stubs
**Scope:** WB first / INDEEPA replacement, 19.05 runtime boundary
**Primary contracts:** `contracts/openapi/v1.yaml`, `docs/handoffs/wb-19-05-backend-contract-handoff.md`
**Reference package:** `backend_contracts/vella_wb_19_05/`
**Local skeleton:** `backend/`
**Do not touch:** production Vella HTML shell or price apply side effects

## Цель

Sprint A должен доказать не “готовую аналитику”, а правильную backend boundary:

- backend поднимается локально;
- source registry знает blockers;
- unresolved источники возвращают typed `blocked/partial/unknown`, а не mock truth;
- Pydantic/FastAPI ответы совместимы с OpenAPI artifact;
- risky actions, особенно price apply, остаются заблокированы до guard/audit/source gates.

## Минимальный порядок реализации

| Step | Что сделать | Done |
|---:|---|---|
| 1 | Поднять FastAPI skeleton, `/health`, config, pytest | `GET /health` возвращает `{"status":"ok"}`; tests зелёные. |
| 2 | Подключить сгенерированные Pydantic модели | `datamodel-codegen` из `contracts/openapi/v1.yaml`; файл компилируется без ручных правок. |
| 3 | Seed source/blocker registry | Есть entries для WB blockers ниже; registry доступен read-only endpoint. |
| 4 | Вернуть 19.05 stubs | P&L/Ads/РНП/ABC/SPP endpoints отвечают contract-shaped states. |
| 5 | Покрыть negative tests | Нельзя вернуть финальный P&L с blockers, SKU Ads с `campaign_only`, price guard `canApply=true` с blockers. |
| 6 | Demo notes | README показывает команды запуска, endpoints, intentional blockers и Sprint B gates. |

## Commands from frontend/contracts repo

```bash
cd "/Users/dima/Downloads/Projects/SAAS для Огней/frontend"
npm run smoke-openapi
```

Backend repo generation:

```bash
datamodel-codegen \
  --input contracts/openapi/v1.yaml \
  --input-file-type openapi \
  --output app/contracts/vella_wb_19_05.py \
  --output-model-type pydantic_v2.BaseModel \
  --target-python-version 3.11

python -m py_compile app/contracts/vella_wb_19_05.py
```

Reference package check in this repo:

```bash
PYTHONPATH=backend_contracts uvx --with pydantic --with fastapi --with httpx --with pytest pytest backend_contracts/tests
python3 -m py_compile backend_contracts/vella_wb_19_05/*.py
```

Backend skeleton check:

```bash
PYTHONPATH=backend:backend_contracts uvx --with pydantic --with fastapi --with httpx --with pytest pytest backend/tests backend_contracts/tests
python3 -m py_compile backend/app/*.py backend/app/routers/*.py backend/app/discovery/*.py backend/app/wb_api/*.py
```

## Source registry seed

Sprint A seed должен включать минимум эти blockers:

| ID | Status | Module | Why |
|---|---|---|---|
| `WB-02` | `blocked` | Ads, РНП, ABC, P&L | Не подтвержден WB Ads source/per-SKU attribution. |
| `WB-03` | `blocked` | WB reports | Нет полной таблицы endpoint/field mapping. |
| `WB-06` | `blocked` | Repricer/SPP | Не подтвержден надежный SPP source/fallback. |
| `WB-11` | `blocked` | РНП | Не подтверждены формулы DRR/ROI/ROMI. |
| `WB-12` | `blocked` | P&L | Не подтверждено распределение хранения/overhead. |
| `WB-13` | `blocked` | P&L | Не подтвержден налог/НДС. |
| `WB-14A` | `unknown` | Plan-fact | Brand dimension не подтвержден. |
| `WB-19A` | `unknown` | ABC | Агрегаты по локомотивам требуют подтверждения. |
| `WB-22` | `blocked` | Repricer/apply | Не подтвержден price apply/status/errors. |
| `WB-23` | `blocked` | Cross-cutting | Нет freshness/confidence registry rules. |

Recommended registry shape:

```json
{
  "blockerId": "WB-06",
  "status": "blocked",
  "module": "repricer",
  "surface": "price_guard",
  "sourceStatus": "unknown",
  "confidence": "blocked",
  "owner": "backend discovery",
  "nextAction": "Confirm reliable SPP source/fallback before any SPP-aware apply",
  "evidenceRef": "docs/open-questions-current.md#WB-06"
}
```

## Required Sprint A stubs

### 1. P&L financial source

Endpoint:

```text
GET /api/v1/wb-reports/pnl?source=financial&dateFrom=2026-05-01&dateTo=2026-05-19&groupBy=sku
```

Expected stub semantics:

- `reportState` is `preliminary` or `blocked`, never `final`;
- `sourceStatus` is `partial` or `blocked`;
- `confidence` is `low` or `blocked`;
- `blockerIds` includes `WB-12`, `WB-13`, `WB-23`;
- `fieldMapping` exists even if some formulas are blocked;
- rows/totals may be null for blocked metrics.

### 2. Ads performance

Endpoint:

```text
GET /api/v1/wb-reports/ads/performance?dateFrom=2026-05-01&dateTo=2026-05-19&groupBy=campaign
```

Expected stub semantics:

- `sourceStatus=blocked|partial`;
- `blockerIds` includes `WB-02`;
- `attributionPolicy.campaignOnlyCanAllocateToSkuPnl=false`;
- `allowedSkuLevels` excludes `campaign_only` and `unknown`;
- campaign-level rows may expose `campaign_only`, but never `confidence=high`.

### 3. Ads SKU negative case

Endpoint:

```text
GET /api/v1/wb-reports/ads/performance?dateFrom=2026-05-01&dateTo=2026-05-19&groupBy=sku
```

Expected stub semantics:

- no row with `attributionLevel=campaign_only|unknown`;
- if backend cannot provide SKU-safe attribution, return `sourceStatus=blocked` with `WB-02` instead of campaign-only SKU rows.

### 4. РНП

Endpoint:

```text
GET /api/v1/wb-reports/rnp?dateFrom=2026-05-01&dateTo=2026-05-19&groupBy=sku
```

Expected stub semantics:

- if `drrPct=null`, `blockerIds` includes `WB-11`;
- if ads source is blocked/unknown, `blockerIds` includes `WB-02`;
- period matches Ads period exactly.

### 5. ABC filtered summary

Endpoint:

```text
GET /api/v1/wb-reports/abc?dateFrom=2026-05-01&dateTo=2026-05-19&groupBy=sku
```

Expected stub semantics:

- `filteredSummary.filterHash` changes when filters/groupBy change;
- non-ad fields may be partial/fresh if available;
- ad fields can be null/blocked without blocking the whole ABC response;
- blockers include `WB-19A` if locomotive aggregates are not confirmed.

### 6. SPP price guard

Endpoint:

```text
GET /api/v1/wb-repricer/sku/FBBT_42/price-guard
```

Expected default Sprint A response:

```json
{
  "articleId": "FBBT_42",
  "currentPriceKopecks": null,
  "buyerPriceKopecks": null,
  "sppSnapshot": {
    "sourceStatus": "blocked",
    "sppPct": null,
    "buyerPriceKopecks": null,
    "capturedAt": null,
    "blockerIds": ["WB-06"]
  },
  "recommendedSellerPriceKopecks": null,
  "lastKnownGoodPriceKopecks": null,
  "canApply": false,
  "blockedReason": "SPP source and price apply status are not confirmed",
  "freezeState": "source_blocked",
  "guardTriggers": [
    {
      "type": "source_stale",
      "severity": "blocker",
      "observedValue": "unknown",
      "previousValue": null,
      "threshold": "fresh SPP snapshot required",
      "message": "SPP-aware apply is blocked until WB-06/WB-22/WB-23 are resolved"
    }
  ],
  "sourceEvidence": [],
  "blockerIds": ["WB-06", "WB-22", "WB-23"]
}
```

## Required negative tests

Backend Sprint A tests should fail if any of these become valid:

| Test | Must fail when |
|---|---|
| `pnl_final_with_blockers` | `reportState=final` and `blockerIds` is not empty. |
| `pnl_final_with_blocked_manual_costs` | final P&L contains blocked manual costs/day allocation/field mapping. |
| `ads_sku_campaign_only` | `groupBy=sku` response contains `campaign_only` or `unknown` attribution. |
| `ads_blocked_without_wb02` | Ads source is blocked/unknown without `WB-02`. |
| `rnp_missing_drr_without_wb11` | `drrPct=null` without `WB-11`. |
| `rnp_blocked_ads_without_wb02` | `adsSourceStatus=blocked|unknown` without `WB-02`. |
| `price_guard_apply_with_blockers` | `canApply=true` while `blockerIds` is not empty. |
| `price_guard_apply_with_blocker_trigger` | `canApply=true` with any guard trigger severity `blocker`. |
| `price_guard_apply_with_stale_spp` | `canApply=true` while SPP snapshot is stale/blocked/unknown. |

## Demo acceptance

Sprint A demo is acceptable if it shows:

- healthcheck and local setup;
- generated Pydantic contract file compiles;
- source registry exposes the blocker seed;
- all five OpenAPI endpoints return contract-shaped stubs;
- repricer discovery endpoints expose candidate WB methods for `WB-06/WB-22/WB-23` without enabling write calls;
- adapter probes execute read-only fake WB checks for price/SPP and task history, preserving blockers when fields/errors are missing;
- risky action state is blocked and audited;
- README explicitly says real price apply is not implemented in Sprint A.

Sprint A demo is not acceptable if:

- it shows final P&L without Максим's formulas;
- it presents campaign-only Ads as SKU-accurate;
- it computes SPP/freeze only in frontend;
- it sends or simulates real WB price mutation as success;
- it hides unresolved source blockers behind generic 500/empty arrays.

## Sprint B entry gate from stubs

Sprint B can start only after backend can say, for each critical source:

| Gate | Required answer |
|---|---|
| SPP | confirmed source/fallback or explicit blocked path. |
| Price apply | endpoint, row-level status/errors, retry/backoff and audit plan. |
| Ads | attribution level and source limits. |
| P&L | storage/overhead/tax/manual allocation owner. |
| Freshness | source freshness/confidence rules for price-critical inputs. |
