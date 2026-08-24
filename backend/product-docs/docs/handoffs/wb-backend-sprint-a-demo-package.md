# WB Backend Sprint A Demo Package

Дата: 2026-05-26  
Статус: ready for frontend integration demo (foundation, not production).

## 1) Demo objective

Показать честный backend boundary:

- typed blocked/unknown/partial states;
- blocker-aware source registry;
- read-only discovery and blocked risky actions;
- no fake readiness for P&L/Ads/RNP/ABC/SPP/apply.

## 2) Run commands

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -e .[test]
.\.venv\Scripts\python -m pytest -q tests backend_contracts\tests
.\.venv\Scripts\python -m uvicorn app.main:app --reload
```

## 3) Demo endpoints checklist

1. `GET /health`
2. `GET /api/v1/wb/account/health`
3. `GET /api/v1/wb/account/health?scenario=missing_token`
4. `GET /api/v1/source-registry?module=wb`
5. `GET /api/v1/wb-reports/pnl?groupBy=sku`
6. `GET /api/v1/wb-reports/ads/performance?groupBy=campaign`
7. `GET /api/v1/wb-reports/ads/performance?groupBy=sku`
8. `GET /api/v1/wb-reports/rnp?groupBy=sku`
9. `GET /api/v1/wb-reports/abc?groupBy=sku`
10. `GET /api/v1/wb-repricer/sku/FBBT_42/price-guard`
11. `GET /api/v1/wb-reviews/wb-review-006/approval?rating=2`
12. `POST /api/v1/wb-repricer/actions/price-apply-placeholder?articleId=FBBT_42`

## 4) Expected blocked states

- `account health`: `partial|unknown|blocked` scenarios with blockers and next actions.
- `source registry`: blocker IDs and evidence refs from `docs/open-questions-current.md`.
- `P&L`: not final, blockers include `WB-12/WB-13/WB-23`.
- `Ads`: blocked/partial with `WB-02`, SKU rows never `campaign_only|unknown`.
- `RNP`: if `drrPct=null`, carries `WB-11`; blocked ads carries `WB-02`.
- `ABC`: filtered summary exists, ads fields can stay null, blockers include `WB-19A`.
- `SPP guard`: `canApply=false`, `freezeState=source_blocked`, blockers include `WB-06/WB-22/WB-23`.
- `price apply`: blocked placeholder only, with audit entry.

## 5) Negative scenarios to run

Covered by tests in `tests/test_phase_a5_demo_readiness.py` and `backend_contracts/tests/test_19_05_invariants.py`:

1. `test_pnl_final_rejects_blockers`
2. `test_ads_sku_rejects_campaign_only`
3. `test_ads_blocked_requires_wb02`
4. `test_rnp_missing_drr_requires_wb11`
5. `test_price_guard_apply_rejects_blockers`
6. `test_price_guard_apply_rejects_stale_spp`

## 6) Explicit non-goals in Sprint A

- No real WB price mutation.
- No final financial truth for P&L.
- No hidden fallback that pretends blocked source is ready.
