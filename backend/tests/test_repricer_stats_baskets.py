from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from datetime import date

import pytest
from fastapi.testclient import TestClient

from app import repricer_bff as repricer_bff_module
from app.main import create_app
from app.repricer_cache.store import FINANCE_SCHEMA_VERSION
from app.routers import wb_repricer_bff as wb_repricer_bff_router
from tests.auth_helpers import auth_headers


DATE_FROM = "2026-07-01"
DATE_TO = "2026-07-07"
SUFFIX = f"{DATE_FROM}_{DATE_TO}"
FETCHED_AT = "2026-07-08T01:00:00+00:00"


def _good(index: int) -> dict:
    return {
        "vendorCode": f"STATS_{index:02d}",
        "nmID": 10_000 + index,
        "brand": "Ogni",
        "subjectName": "Футболки",
        "sizes": [
            {
                "price": 1_000,
                "discountedPrice": 1_000,
                "buyerPriceNoWalletKopecks": 90_000,
            }
        ],
    }


def _source_payload(aggregates: dict, **metadata: object) -> dict:
    return {
        "fetchedAt": FETCHED_AT,
        "dateFrom": DATE_FROM,
        "dateTo": DATE_TO,
        "periodDays": 7,
        "aggregates": aggregates,
        **metadata,
    }


def _fail(message: str):
    def fail(*_args, **_kwargs):
        raise AssertionError(message)

    return fail


@pytest.fixture
def stats_runtime(monkeypatch):
    goods = [_good(1)]
    storage: dict[tuple[int, str], dict] = {}
    save_calls: list[tuple[int, str]] = []
    settings = replace(repricer_bff_module.get_settings(), wb_api_mode="real")

    def get_cache(organization_id: int, key: str, **_kwargs):
        return deepcopy(storage.get((organization_id, key)))

    def save_cache(organization_id: int, key: str, payload: dict):
        save_calls.append((organization_id, key))
        storage[organization_id, key] = deepcopy(payload)
        return deepcopy(payload)

    def meta_fields(organization_id: int, key: str):
        cache = storage.get((organization_id, key)) or {}
        return {
            field: cache.get(field)
            for field in (
                "fetchedAt",
                "cachedGoodsNmIds",
                "matchedCachedGoodsNmIds",
                "requestedNmIds",
                "matchedNmIds",
            )
            if cache.get(field) is not None
        }

    monkeypatch.setattr(wb_repricer_bff_router, "get_source_cache", get_cache)
    monkeypatch.setattr(wb_repricer_bff_router, "save_source_cache", save_cache)
    monkeypatch.setattr(wb_repricer_bff_router, "get_source_cache_meta_fields", meta_fields)
    monkeypatch.setattr(
        wb_repricer_bff_router,
        "get_source_cache_fetched_at",
        lambda organization_id, key: (storage.get((organization_id, key)) or {}).get("fetchedAt"),
    )
    monkeypatch.setattr(wb_repricer_bff_router, "list_cached_goods", lambda organization_id: deepcopy(goods) if organization_id == 1 else [])
    monkeypatch.setattr(wb_repricer_bff_router, "cached_goods_meta", lambda organization_id: {"totalCached": len(goods) if organization_id == 1 else 0})
    monkeypatch.setattr(wb_repricer_bff_router, "get_wb_sync_status", lambda _organization_id: {})
    monkeypatch.setattr(wb_repricer_bff_router, "_hydrate_org_repricer_state", lambda _request: 1)
    monkeypatch.setattr(repricer_bff_module, "get_settings", lambda: settings)
    monkeypatch.setattr(repricer_bff_module, "fetch_commission_tariffs", _fail("commission provider must not be called"))
    monkeypatch.setattr(repricer_bff_module, "build_wb_common_client", _fail("WB provider must not be called"))

    def seed_common() -> None:
        period = {str(good["nmID"]): {"ordersUnits": 0} for good in goods}
        finance = {
            str(good["nmID"]): {
                "salesUnits": 0,
                "returnsUnits": 0,
                "sellerRevenueKopecks": 0,
                "commissionPct": 10,
            }
            for good in goods
        }
        ads = {str(good["nmID"]): {"adImpressions": 0} for good in goods}
        storage[1, f"period_stats_{SUFFIX}"] = _source_payload(period)
        storage[1, f"finance_{SUFFIX}"] = _source_payload(
            finance,
            revenueBasis="retailAmount",
            financeSchemaVersion=FINANCE_SCHEMA_VERSION,
        )
        storage[1, f"ads_{SUFFIX}"] = _source_payload(ads)
        storage[1, "stocks"] = {
            "fetchedAt": FETCHED_AT,
            "aggregates": {str(good["nmID"]): {"wbStockUnits": 10} for good in goods},
        }

    def request(*, baskets: dict | None, params: dict | None = None) -> dict:
        seed_common()
        if baskets is not None:
            storage[1, f"baskets_{SUFFIX}"] = deepcopy(baskets)
        api = TestClient(create_app())
        response = api.get(
            "/api/v1/wb-repricer/stats",
            params={"dateFrom": DATE_FROM, "dateTo": DATE_TO, "periodDays": 7, "topMode": "false", **(params or {})},
            headers=auth_headers(api, "viewer"),
        )
        assert response.status_code == 200, response.text
        return response.json()

    request.save_calls = save_calls
    return goods, storage, request


@pytest.mark.parametrize(
    "baskets,want,conversion",
    [(None, None, None), (0, 0, None), (7, 7, 42.9)],
)
def test_stats_mapper_does_not_substitute_synthetic_baskets(baskets, want, conversion):
    row = {
        "meta": {"basketsLast7d": 22},
        "analytics": {"baskets": baskets, "ordersUnits": 3},
    }
    metrics = wb_repricer_bff_router._repricer_stats_metrics(row)
    assert metrics["baskets"] == want
    assert metrics["cartToOrderCrPct"] == conversion


@pytest.mark.parametrize(
    "loaded,aggregates,mode,want_baskets,want_state,want_meta",
    [
        (False, {}, "real", None, "no_data", None),
        (True, {}, "real", None, "no_data", 0),
        (True, {"123456": {"cartCount": None}}, "real", None, "no_data", 0),
        (True, {"123456": {"cartCount": 0}}, "real", 0, "ok", 0),
        (False, {}, "fake", 20, "fallback", 20),
    ],
)
def test_cached_list_distinguishes_missing_zero_and_demo_fallback(
    monkeypatch, loaded, aggregates, mode, want_baskets, want_state, want_meta
):
    settings = replace(repricer_bff_module.get_settings(), wb_api_mode=mode)
    monkeypatch.setattr(repricer_bff_module, "get_settings", lambda: settings)
    monkeypatch.setattr(repricer_bff_module, "fetch_commission_tariffs", _fail("commission provider must not be called"))
    row = repricer_bff_module.list_repricer_skus(
        wb_token=None,
        include_promotions=False,
        include_content=False,
        cached_goods=[
            {
                "vendorCode": "DIRECT_UNKNOWN",
                "nmID": 123456,
                "sizes": [{"price": 1_000, "discountedPrice": 1_000}],
            }
        ],
        cached_content_cards=[],
        cached_promotions=[],
        cached_stock_aggregates={},
        cached_period_stats={},
        cached_finance_aggregates={},
        cached_ads_aggregates={},
        cached_baskets_aggregates=aggregates,
        baskets_cache_loaded=loaded,
        list_view=True,
        allow_commission_tariff_fetch=False,
    )[0]
    assert row["analytics"]["baskets"] == want_baskets
    assert row["analytics"]["basketsState"] == want_state
    if want_meta is not None:
        assert row["meta"]["basketsLast7d"] == want_meta


@pytest.mark.parametrize(
    "baskets_payload,want_baskets,want_conversion,want_state",
    [
        (None, None, None, "no_data"),
        (_source_payload({}, requestedNmIds=1, matchedNmIds=0), None, None, "no_data"),
        (_source_payload({"10001": {"cartCount": None, "orderCount": 3}}, requestedNmIds=1, matchedNmIds=1), None, None, "no_data"),
        (_source_payload({"10001": {"cartCount": 0, "orderCount": 0}}, requestedNmIds=1, matchedNmIds=1), 0, None, "ok"),
        (_source_payload({"10001": {"cartCount": 7, "orderCount": 3}}, requestedNmIds=1, matchedNmIds=1), 7, 42.9, "ok"),
    ],
)
def test_stats_endpoint_preserves_unknown_and_explicit_baskets(
    stats_runtime, baskets_payload, want_baskets, want_conversion, want_state
):
    _goods, _storage, request = stats_runtime
    payload = request(baskets=baskets_payload)
    item = payload["items"][0]
    assert item["metrics"]["baskets"] == want_baskets
    assert item["metrics"]["cartToOrderCrPct"] == want_conversion
    assert item["sources"]["states"]["baskets"] == want_state
    assert payload["summary"]["baskets"] == want_baskets
    assert payload["summary"]["cartToOrderCrPct"] == want_conversion
    if want_baskets is None:
        assert "baskets" in item["sources"]["missing"]
        assert "below_basket_norm" not in item["flags"]
        assert payload["cache"]["statsSourceStatus"] != "ready"


def test_fetched_empty_baskets_cache_retains_coverage_metadata(stats_runtime):
    _goods, storage, request = stats_runtime
    payload = request(
        baskets=_source_payload({}, requestedNmIds=1, matchedNmIds=0),
    )
    saved = storage[1, f"repricer_stats_baskets_{SUFFIX}"]
    assert saved["fetchedAt"] == FETCHED_AT
    assert saved["requestedNmIds"] == 1
    assert saved["matchedNmIds"] == 0
    assert saved["aggregates"] == {}
    assert payload["cache"]["basketsFetchedAt"] == FETCHED_AT
    assert payload["cache"]["basketsRequestedNmIds"] == 1
    assert payload["cache"]["basketsMatchedNmIds"] == 0


@pytest.mark.parametrize(
    "cart_count,order_count,want_conversion",
    [(7, 3, 42.9), (0, 0, None)],
)
def test_fetched_empty_baskets_cache_recovers_from_newer_observation_without_deletion(
    stats_runtime, cart_count, order_count, want_conversion
):
    goods, storage, request = stats_runtime
    source_key = f"baskets_{SUFFIX}"
    stats_key = f"repricer_stats_baskets_{SUFFIX}"
    empty = _source_payload(
        {},
        fetchedAt="2026-07-08T01:00:00+00:00",
        requestedNmIds=1,
        matchedNmIds=0,
    )

    first = request(baskets=empty)
    assert first["items"][0]["metrics"]["baskets"] is None
    assert first["cache"]["basketsFetchedAt"] == "2026-07-08T01:00:00+00:00"
    assert first["cache"]["basketsRequestedNmIds"] == 1
    assert first["cache"]["basketsMatchedNmIds"] == 0
    assert storage[1, stats_key]["aggregates"] == {}

    range_start, range_end, period_days, period_suffix = wb_repricer_bff_router._repricer_period_context(
        7,
        date.fromisoformat(DATE_FROM),
        date.fromisoformat(DATE_TO),
    )
    saves_before_repeat = len(request.save_calls)
    repeated = wb_repricer_bff_router._ensure_repricer_stats_period_caches(
        1,
        "complete",
        wb_token=None,
        resolved_period_days=period_days,
        period_suffix=period_suffix,
        range_start=range_start,
        range_end=range_end,
    )
    assert "baskets" in repeated["missingSources"]
    assert len(request.save_calls) == saves_before_repeat
    assert storage[1, stats_key]["fetchedAt"] == "2026-07-08T01:00:00+00:00"

    storage[1, source_key] = _source_payload(
        {"10001": {"cartCount": cart_count, "orderCount": order_count}},
        fetchedAt="2026-07-09T01:00:00+00:00",
        requestedNmIds=1,
        matchedNmIds=1,
    )
    recovered = request(baskets=None)
    recovered_item = recovered["items"][0]
    assert recovered_item["metrics"]["baskets"] == cart_count
    assert recovered_item["metrics"]["cartToOrderCrPct"] == want_conversion
    assert recovered_item["sources"]["states"]["baskets"] == "ok"
    assert recovered["summary"]["baskets"] == cart_count
    assert recovered["summary"]["cartToOrderCrPct"] == want_conversion
    assert recovered["cache"]["basketsFetchedAt"] == "2026-07-09T01:00:00+00:00"
    assert recovered["cache"]["basketsRequestedNmIds"] == 1
    assert recovered["cache"]["basketsMatchedNmIds"] == 1
    assert storage[1, stats_key]["dateFrom"] == DATE_FROM
    assert storage[1, stats_key]["dateTo"] == DATE_TO
    assert storage[1, stats_key]["aggregates"]["10001"]["cartCount"] == cart_count

    del storage[1, source_key]
    unavailable = request(baskets=None)
    assert unavailable["items"][0]["metrics"]["baskets"] == cart_count
    assert unavailable["cache"]["basketsFetchedAt"] == "2026-07-09T01:00:00+00:00"

    goods.append(_good(2))
    storage[1, source_key] = _source_payload(
        {"10001": {"cartCount": 99, "orderCount": 99}},
        fetchedAt="2026-07-08T02:00:00+00:00",
        requestedNmIds=2,
        matchedNmIds=1,
    )
    older = request(baskets=None)
    by_article = {item["articleId"]: item for item in older["items"]}
    assert by_article["STATS_01"]["metrics"]["baskets"] == cart_count
    assert by_article["STATS_02"]["metrics"]["baskets"] is None
    assert by_article["STATS_02"]["sources"]["states"]["baskets"] == "no_data"
    assert older["summary"]["baskets"] is None
    assert older["cache"]["basketsFetchedAt"] == "2026-07-09T01:00:00+00:00"


@pytest.mark.parametrize(
    "aggregates",
    [None, [], False, "broken", {"10001": []}, {"10001": ["broken"]}, {"10001": None}],
    ids=["null", "list", "boolean", "string", "empty-row-list", "row-list", "null-row"],
)
def test_newer_malformed_baskets_preserves_last_good_cache(stats_runtime, aggregates):
    _goods, storage, request = stats_runtime
    good = _source_payload(
        {"10001": {"cartCount": 7, "orderCount": 3}},
        requestedNmIds=1,
        matchedNmIds=1,
    )
    first = request(baskets=good)
    assert first["summary"]["baskets"] == 7
    cache_key = (1, f"repricer_stats_baskets_{SUFFIX}")
    saved = deepcopy(storage[cache_key])
    saves_before = list(request.save_calls)

    payload = request(baskets={
        **good,
        "fetchedAt": "2026-07-09T01:00:00+00:00",
        "aggregates": aggregates,
        "matchedNmIds": 0,
    })

    assert payload["items"][0]["metrics"]["baskets"] == 7
    assert payload["summary"]["baskets"] == 7
    assert payload["summary"]["cartToOrderCrPct"] == 42.9
    assert payload["cache"]["basketsFetchedAt"] == FETCHED_AT
    assert payload["cache"]["basketsMatchedNmIds"] == 1
    assert storage[cache_key] == saved
    assert request.save_calls == saves_before


def test_summary_is_unknown_when_missing_sku_is_outside_page(stats_runtime):
    goods, _storage, request = stats_runtime
    goods[:] = [_good(index) for index in range(1, 27)]
    baskets = {
        str(good["nmID"]): {"cartCount": 1, "orderCount": 0}
        for good in goods[:25]
    }
    payload = request(
        baskets=_source_payload(baskets, requestedNmIds=26, matchedNmIds=25),
        params={"pageSize": 25},
    )
    assert payload["itemsReturned"] == 25
    assert all(item["metrics"]["baskets"] == 1 for item in payload["items"])
    assert payload["summary"]["skuCount"] == 26
    assert payload["summary"]["baskets"] is None
    assert payload["summary"]["cartToOrderCrPct"] is None
    assert payload["cache"]["statsSourceStatus"] != "ready"


def test_filtered_summary_uses_only_known_selected_sku(stats_runtime):
    goods, _storage, request = stats_runtime
    goods[:] = [_good(1), _good(2)]
    payload = request(
        baskets=_source_payload(
            {"10001": {"cartCount": 7, "orderCount": 3}},
            requestedNmIds=2,
            matchedNmIds=1,
        ),
        params={"q": "STATS_01"},
    )
    assert payload["total"] == 1
    assert payload["summary"]["baskets"] == 7
    assert payload["summary"]["cartToOrderCrPct"] == 42.9


def test_stats_cache_rejects_wrong_tenant_and_malformed_range(stats_runtime):
    _goods, storage, request = stats_runtime
    storage[1, f"repricer_stats_baskets_{SUFFIX}"] = {
        **_source_payload({"10001": {"cartCount": 88, "orderCount": 3}}),
        "dateFrom": "not-a-date",
    }
    storage[2, f"repricer_stats_baskets_{SUFFIX}"] = _source_payload(
        {"10001": {"cartCount": 99, "orderCount": 3}}
    )
    payload = request(baskets=None)
    assert payload["items"][0]["metrics"]["baskets"] is None
    assert payload["summary"]["baskets"] is None
    assert payload["cache"]["basketsFetchedAt"] is None
    assert payload["cache"]["statsSourceStatus"] != "ready"
