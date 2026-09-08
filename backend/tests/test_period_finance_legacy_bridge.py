from __future__ import annotations

from datetime import datetime, timezone

from app.routers import wb_repricer_bff


def test_numeric_preset_uses_covering_date_range_cache(monkeypatch) -> None:
    covering = {
        "dateFrom": "2026-08-26",
        "dateTo": "2026-09-01",
        "periodDays": 7,
        "revenueBasis": "retailAmount",
        "financeSchemaVersion": "v3",
        "dailyAggregates": {
            "2026-08-26": {"123": {"buyerRevenueKopecks": 100}},
            "2026-09-01": {"123": {"buyerRevenueKopecks": 200}},
        },
        "aggregates": {"123": {"buyerRevenueKopecks": 300}},
    }
    monkeypatch.setattr(
        wb_repricer_bff, "get_source_cache", lambda *_args, **_kwargs: None
    )
    monkeypatch.setattr(
        wb_repricer_bff,
        "get_covering_source_cache",
        lambda *_args, **_kwargs: covering,
    )

    result = wb_repricer_bff._load_period_source_cache(
        2,
        "finance",
        "7",
        7,
        datetime(2026, 8, 26, tzinfo=timezone.utc),
        datetime(2026, 9, 1, tzinfo=timezone.utc),
        require_full_sync_coverage=False,
    )

    assert result["aggregates"]["123"]["buyerRevenueKopecks"] == 300
    assert result["coveredByCache"]["dateFrom"] == "2026-08-26"
