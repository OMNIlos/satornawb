from app import repricer_bff as repricer_bff_module


def test_cached_sku_list_does_not_fetch_commission_tariffs(monkeypatch):
    repricer_bff_module.COMMISSION_TARIFFS_CACHE.clear()
    monkeypatch.setattr(
        repricer_bff_module,
        "fetch_commission_tariffs",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("cached list read must not call WB tariffs")),
    )

    rows = repricer_bff_module.list_repricer_skus(
        wb_token="token",
        include_promotions=False,
        include_content=False,
        cached_goods=[
            {
                "vendorCode": "FBBT_42",
                "nmID": 123456,
                "brand": "Ogni",
                "subjectName": "Футболки",
                "sizes": [{"price": 139000, "discountedPrice": 119000}],
            }
        ],
        cached_content_cards=[],
        cached_promotions=[],
        cached_stock_aggregates={},
        cached_period_stats={},
        cached_finance_aggregates={},
        cached_ads_aggregates={},
        cached_baskets_aggregates={},
        list_view=True,
        allow_commission_tariff_fetch=False,
    )

    assert len(rows) == 1
    assert rows[0]["meta"]["articleId"] == "FBBT_42"
    assert rows[0]["analytics"]["commissionState"] == "no_data"
