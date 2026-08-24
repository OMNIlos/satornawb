from __future__ import annotations

from types import SimpleNamespace

from fastapi.testclient import TestClient

from app import repricer_bff as repricer_bff_module
from app import repricer_execution as repricer_execution_module
from app.main import create_app


def client() -> TestClient:
    return TestClient(create_app())


def test_plan_fact_scales_basket_norm_to_fact_period():
    previous_settings = dict(repricer_bff_module.ALGORITHM_SETTINGS_STATE)
    try:
        repricer_bff_module.ALGORITHM_SETTINGS_STATE["basketNormPeriodDays"] = 7
        row = {
            "meta": {"basketNorm": 70, "currentPriceKopecks": 100_000},
            "analytics": {"ordersUnits": 140, "periodDays": 14},
        }

        assert repricer_execution_module._plan_fact_pct(row, metric="orders") == 100
        assert repricer_execution_module._daily_plan_orders(row) == 10
    finally:
        repricer_bff_module.ALGORITHM_SETTINGS_STATE.clear()
        repricer_bff_module.ALGORITHM_SETTINGS_STATE.update(previous_settings)


def test_basket_threshold_mode_uses_configured_cart_thresholds():
    previous_settings = dict(repricer_bff_module.ALGORITHM_SETTINGS_STATE)
    try:
        repricer_bff_module.ALGORITHM_SETTINGS_STATE.update(
            {
                "basketSignalMode": "thresholds",
                "cartHighBasketsThreshold": 30,
                "cartLowBasketsThreshold": 5,
                "priceStepPct": 10,
            }
        )
        row = {
            "meta": {"currentPriceKopecks": 100_000, "basketsLast7d": 12},
            "analytics": {"baskets": 31},
        }

        recommended, explanation = repricer_execution_module._basket_threshold_recommended_price(row)

        assert recommended == 110_000
        assert "31 >= 30" in explanation
    finally:
        repricer_bff_module.ALGORITHM_SETTINGS_STATE.clear()
        repricer_bff_module.ALGORITHM_SETTINGS_STATE.update(previous_settings)


def test_price_rounding_can_round_to_pretty_price():
    previous_settings = dict(repricer_bff_module.ALGORITHM_SETTINGS_STATE)
    try:
        repricer_bff_module.ALGORITHM_SETTINGS_STATE["priceRoundingEnabled"] = True

        rounded, note = repricer_execution_module._apply_price_rounding(201_300, current=190_000)

        assert rounded == 199_000
        assert note and "1990" in note
    finally:
        repricer_bff_module.ALGORITHM_SETTINGS_STATE.clear()
        repricer_bff_module.ALGORITHM_SETTINGS_STATE.update(previous_settings)


def _patch_cached_goods(monkeypatch):
    monkeypatch.setattr("app.routers.wb_repricer_bff.get_settings", lambda: SimpleNamespace(wb_api_token="env-token"))
    monkeypatch.setattr("app.routers.wb_repricer_bff.get_user_wb_token_secret", lambda _user_id: "user-token")
    monkeypatch.setattr(
        "app.routers.wb_repricer_bff.actor_from_request",
        lambda _request: SimpleNamespace(user_id="user-1", organization_id=1, actor_id="user-1", role="manager"),
    )
    monkeypatch.setattr(
        "app.routers.wb_repricer_bff.list_cached_goods",
        lambda _organization_id: [
            {
                "vendorCode": "FBBT_42",
                "nmID": 123456,
                "title": "Test SKU",
                "sizes": [{"price": 129000, "discountedPrice": 119900}],
            }
        ],
    )
    monkeypatch.setattr(
        "app.routers.wb_repricer_bff.cached_goods_meta",
        lambda _organization_id: {
            "pagesCached": 1,
            "totalCached": 1,
            "nextOffset": 1000,
            "pageLimit": 1000,
            "latestFetchedAt": None,
        },
    )


def test_bulk_strategy_assignment_triggers_execution(monkeypatch):
    _patch_cached_goods(monkeypatch)
    repricer_bff_module.FRONTEND_STRATEGY_ASSIGNMENTS.clear()
    repricer_bff_module.SKU_META_OVERRIDES.clear()
    repricer_bff_module.SKU_SETTINGS_OVERRIDES.clear()
    repricer_bff_module.CHANGELOG_ENTRIES.clear()

    api = client()
    before = api.get("/api/v1/wb-repricer/sku")
    assert before.status_code == 200
    old_price = before.json()["items"][0]["meta"]["currentPriceKopecks"]

    applied = api.post(
        "/api/v1/wb-repricer/strategy-assignments/bulk",
        json={"articleIds": ["FBBT_42"], "strategyName": "aggr", "executeAfterAssign": True},
    )
    assert applied.status_code == 200
    body = applied.json()
    assert body["strategy"]["id"] == "baskets_orders"
    assert "execution" in body
    execution = body["execution"]
    assert execution["executedCount"] >= 0

    after = api.get("/api/v1/wb-repricer/sku")
    assert after.status_code == 200
    new_price = after.json()["items"][0]["meta"]["currentPriceKopecks"]
    if execution["executedCount"] == 1:
        assert new_price != old_price


def test_preview_endpoint_returns_dry_run_rows(monkeypatch):
    _patch_cached_goods(monkeypatch)
    repricer_bff_module.FRONTEND_STRATEGY_ASSIGNMENTS.clear()
    repricer_bff_module.SKU_META_OVERRIDES.clear()
    repricer_bff_module.SKU_SETTINGS_OVERRIDES.clear()

    api = client()
    response = api.post(
        "/api/v1/wb-repricer/strategies/preview",
        json={"articleIds": ["FBBT_42"], "scenario": "complete"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["runId"].startswith("exec_")
    assert len(payload["items"]) == 1


def test_execute_endpoint_returns_per_sku_results(monkeypatch):
    _patch_cached_goods(monkeypatch)
    repricer_bff_module.FRONTEND_STRATEGY_ASSIGNMENTS.clear()
    repricer_bff_module.SKU_META_OVERRIDES.clear()
    repricer_bff_module.SKU_SETTINGS_OVERRIDES.clear()

    api = client()
    api.post(
        "/api/v1/wb-repricer/strategy-assignments/bulk",
        json={"articleIds": ["FBBT_42"], "strategyName": "cons", "executeAfterAssign": False},
    )

    response = api.post(
        "/api/v1/wb-repricer/strategies/execute",
        json={"articleIds": ["FBBT_42"], "scenario": "complete"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["runId"].startswith("exec_")
    assert len(payload["items"]) == 1
    assert payload["items"][0]["articleId"] == "FBBT_42"


def test_execute_stops_wb_uploads_after_rate_limit(monkeypatch):
    rows = []
    for index, article_id in enumerate(["SKU1", "SKU2"], start=1):
        rows.append(
            {
                "meta": {
                    "articleId": article_id,
                    "currentPriceKopecks": 100_000,
                    "nmId": index,
                    "status": "auto",
                    "basketNorm": 10,
                    "assignmentSource": "manual",
                    "name": article_id,
                },
                "settings": {
                    "automationEnabled": True,
                    "pMinKopecks": 50_000,
                    "pMaxKopecks": 200_000,
                    "cogsKopecks": 10_000,
                    "wbCommissionPct": 10,
                    "logisticsKopecks": 1_000,
                    "minMarginPct": 10,
                },
                "analytics": {
                    "ordersUnits": 20,
                    "periodDays": 7,
                    "wbStockUnits": 10,
                    "buyoutPct": 90,
                    "wbCommissionPct": 10,
                },
                "strategy": {
                    "id": "plan_fact_daily",
                    "name": "План-факт стандартный",
                    "assignmentSource": "manual",
                    "typedStrategyId": None,
                },
            }
        )

    create_calls: list[str] = []
    apply_calls: list[str] = []

    monkeypatch.setattr("app.repricer_execution.is_auto_strategy_execution_allowed", lambda force=False: True)
    monkeypatch.setattr(
        "app.repricer_execution.get_settings",
        lambda: SimpleNamespace(real_price_apply_enabled=True, repricer_local_price_apply_enabled=False),
    )
    monkeypatch.setattr(
        "app.repricer_execution.build_price_recommendation",
        lambda **_kwargs: SimpleNamespace(guardReport=SimpleNamespace(canApply=True, blockers=[], triggers=[])),
    )

    def create_price_draft_stub(**kwargs):
        article_id = kwargs["payload"].articleId
        create_calls.append(article_id)
        return SimpleNamespace(state="ready", draftId=f"drf_{article_id}")

    monkeypatch.setattr("app.repricer_execution.create_price_draft", create_price_draft_stub)
    monkeypatch.setattr("app.repricer_execution.approve_draft", lambda **_kwargs: None)

    def apply_approved_draft_stub(**kwargs):
        apply_calls.append(kwargs["draft_id"])
        return SimpleNamespace(
            jobId="job_rate_limited",
            state="blocked",
            blockerIds=["wb_rate_limited"],
            notes=["WB price upload rate limit reached; retry after 7s"],
            lastApplyResult=SimpleNamespace(applyMode="wb_api"),
        )

    monkeypatch.setattr("app.repricer_execution.apply_approved_draft", apply_approved_draft_stub)

    report = repricer_execution_module.execute_repricer_strategies(
        ["SKU1", "SKU2"],
        client=object(),
        actor_id="scheduler",
        actor_role="system",
        options=repricer_execution_module.StrategyExecuteOptions(
            scenario="complete",
            createDrafts=True,
            autoApprove=True,
            applyPrices=True,
        ),
        sku_rows=rows,
        organization_id=10,
        persist_run=False,
    )

    assert create_calls == ["SKU1"]
    assert apply_calls == ["drf_SKU1"]
    assert report.blockedCount == 2
    assert [item.status for item in report.items] == ["blocked", "blocked"]
    assert report.items[0].blockedReasons == ["wb_rate_limited"]
    assert report.items[1].blockedReasons == ["wb_rate_limited"]
    assert report.items[1].draftId is None
    assert report.items[1].explanation == "WB price upload rate limit is active for this run; retry on the next scheduler cycle"


def test_execute_with_worker_approval_creates_pending_without_applying(monkeypatch):
    row = {
        "meta": {
            "articleId": "SKU_APPROVAL",
            "currentPriceKopecks": 100_000,
            "nmId": 123,
            "status": "auto",
            "basketNorm": 7,
            "assignmentSource": "manual",
        },
        "settings": {
            "automationEnabled": True,
            "pMinKopecks": 50_000,
            "pMaxKopecks": 200_000,
            "cogsKopecks": 10_000,
            "wbCommissionPct": 10,
            "logisticsKopecks": 1_000,
            "minMarginPct": 10,
        },
        "analytics": {
            "ordersUnits": 10,
            "periodDays": 7,
            "wbStockUnits": 0,
            "buyoutPct": 90,
        },
        "strategy": {
            "id": "stockout_guard",
            "name": "Защита out of stock",
            "assignmentSource": "manual",
            "typedStrategyId": None,
        },
    }
    pending_calls: list[dict[str, object]] = []

    monkeypatch.setattr("app.repricer_execution.is_auto_strategy_execution_allowed", lambda force=False: True)
    monkeypatch.setattr(
        "app.repricer_execution.build_price_recommendation",
        lambda **_kwargs: SimpleNamespace(guardReport=SimpleNamespace(canApply=True, blockers=[], triggers=[])),
    )

    def create_price_draft_stub(**kwargs):
        assert kwargs["payload"].articleId == "SKU_APPROVAL"
        assert kwargs["payload"].candidateSellerPriceKopecks == 106_000
        return SimpleNamespace(state="draft", draftId="drf_SKU_APPROVAL")

    monkeypatch.setattr("app.repricer_execution.create_price_draft", create_price_draft_stub)
    monkeypatch.setattr("app.repricer_execution.approve_draft", lambda **_kwargs: (_ for _ in ()).throw(AssertionError("must not auto-approve")))
    monkeypatch.setattr("app.repricer_execution.apply_approved_draft", lambda **_kwargs: (_ for _ in ()).throw(AssertionError("must not apply")))
    monkeypatch.setattr("app.repricer_execution.append_execution_run", lambda **_kwargs: True)
    monkeypatch.setattr("app.repricer_execution.upsert_pending_price_approvals", lambda **kwargs: pending_calls.append(kwargs))

    report = repricer_execution_module.execute_repricer_strategies(
        ["SKU_APPROVAL"],
        client=object(),
        actor_id="repricer-scheduler",
        actor_role="system",
        options=repricer_execution_module.StrategyExecuteOptions(
            scenario="complete",
            createDrafts=True,
            autoApprove=False,
            applyPrices=False,
        ),
        sku_rows=[row],
        organization_id=10,
        trigger="scheduler",
        persist_run=True,
    )

    assert report.executedCount == 1
    assert report.items[0].applyState == "approval_required"
    assert report.items[0].draftId == "drf_SKU_APPROVAL"
    assert len(pending_calls) == 1
    assert pending_calls[0]["organization_id"] == 10
    approval = pending_calls[0]["approvals"][0]  # type: ignore[index]
    assert approval["runId"] == report.runId
    assert approval["articleId"] == "SKU_APPROVAL"
    assert approval["recommendedPriceKopecks"] == 106_000
    assert approval["draftRequest"]["candidateSellerPriceKopecks"] == 106_000
