from __future__ import annotations

from datetime import date

from app.avito.listings import AvitoListingsFetchResult, AvitoListingRow
from app.routers.avito_repricer import _avito_worker_timing_payload, _cache_hit_payload, _cache_key, _response_payload
from app.avito.stats import AvitoStatsAccount


class RecordingRepricerListingsClient:
    def __init__(self, access_token: str | None = None) -> None:
        self.access_token = access_token
        self.requests: list[object] = []

    def fetch_listings(self, request: object) -> AvitoListingsFetchResult:
        self.requests.append(request)
        return AvitoListingsFetchResult(
            status="synced",
            accounts=[AvitoStatsAccount(accountId="365024549", accountName="Bless T", itemCount=3, activeItemCount=3)],
            rows=[
                AvitoListingRow(
                    itemId="8098482225",
                    title="High chat item",
                    accountId="365024549",
                    accountName="Bless T",
                    status="active",
                    priceKopecks=100_000,
                    impressions=1500,
                    views=500,
                    contactsMessenger=20,
                    contacts=24,
                    sourceStatus="fresh",
                ),
                AvitoListingRow(
                    itemId="8098482191",
                    title="Silent item",
                    accountId="365024549",
                    accountName="Bless T",
                    status="active",
                    priceKopecks=100_000,
                    impressions=900,
                    views=300,
                    contactsMessenger=0,
                    contacts=2,
                    sourceStatus="fresh",
                ),
                AvitoListingRow(
                    itemId="8098459618",
                    title="Metric unavailable",
                    accountId="365024549",
                    accountName="Bless T",
                    status="active",
                    priceKopecks=100_000,
                    views=200,
                    contacts=4,
                    sourceStatus="fresh",
                ),
            ],
        )


def test_avito_repricer_payload_uses_messenger_contacts_as_signal(monkeypatch):
    result = RecordingRepricerListingsClient().fetch_listings(object())

    monkeypatch.setattr(
        "app.routers.avito_repricer.get_source_cache",
        lambda _organization_id, source_key, **_kwargs: {
            "assignments": {
                "8098482225": "chat_demand_balanced",
                "8098482191": "chat_demand_balanced",
                "8098459618": "chat_demand_balanced",
            }
        }
        if source_key == "avito_repricer_strategy_assignments"
        else None,
    )

    payload = _response_payload(
        status=result.status,
        start=date(2026, 7, 1),
        end=date(2026, 7, 28),
        days=28,
        rows=result.rows,
        accounts=result.accounts,
        organization_id=10,
    )

    assert payload["summary"]["raiseCandidates"] == 1
    assert payload["summary"]["lowerCandidates"] == 1
    assert payload["summary"]["noData"] == 1
    assert payload["rows"][0]["strategySignal"] == "raise"
    assert payload["rows"][0]["recommendedPriceKopecks"] == 105_000
    assert payload["rows"][1]["strategySignal"] == "lower"
    assert payload["rows"][1]["recommendedPriceKopecks"] == 93_000
    assert payload["rows"][2]["strategySignal"] == "no_data"
    assert payload["rows"][2]["contactsMessenger"] is None
    assert _cache_key(date(2026, 7, 1), date(2026, 7, 28), []) == "avito_repricer:v2:2026-07-01:2026-07-28:all"


def test_avito_repricer_payload_applies_per_item_strategy_assignments(monkeypatch):
    result = RecordingRepricerListingsClient().fetch_listings(object())

    monkeypatch.setattr(
        "app.routers.avito_repricer.get_source_cache",
        lambda _organization_id, source_key, **_kwargs: {
            "assignments": {"8098482191": "chat_recovery_discount"}
        }
        if source_key == "avito_repricer_strategy_assignments"
        else None,
    )

    payload = _response_payload(
        status=result.status,
        start=date(2026, 7, 1),
        end=date(2026, 7, 28),
        days=28,
        rows=result.rows,
        accounts=result.accounts,
        organization_id=10,
    )

    silent_row = next(row for row in payload["rows"] if row["itemId"] == "8098482191")
    assert payload["strategies"][0]["id"] == "none"
    assert silent_row["strategyId"] == "chat_recovery_discount"
    assert silent_row["strategyName"] == "Вернуть спрос"
    assert silent_row["recommendedPriceKopecks"] == 90_000


def test_avito_repricer_cache_hit_reapplies_current_strategy_assignments(monkeypatch):
    result = RecordingRepricerListingsClient().fetch_listings(object())
    cached = _response_payload(
        status=result.status,
        start=date(2026, 7, 1),
        end=date(2026, 7, 28),
        days=28,
        rows=result.rows,
        accounts=result.accounts,
    )

    monkeypatch.setattr(
        "app.routers.avito_repricer.get_source_cache",
        lambda _organization_id, source_key, **_kwargs: {
            "assignments": {"8098482191": "chat_recovery_discount"}
        }
        if source_key == "avito_repricer_strategy_assignments"
        else None,
    )

    payload = _cache_hit_payload(cached, organization_id=10)

    silent_row = next(row for row in payload["rows"] if row["itemId"] == "8098482191")
    assert payload["source"]["cache"]["status"] == "hit"
    assert silent_row["strategyId"] == "chat_recovery_discount"
    assert silent_row["strategyName"] == "Вернуть спрос"
    assert silent_row["recommendedPriceKopecks"] == 90_000


def test_avito_repricer_lowers_price_when_conversion_is_very_low(monkeypatch):
    result = RecordingRepricerListingsClient().fetch_listings(object())
    low_conversion_row = result.rows[0].model_copy(
        update={
            "itemId": "8226131268",
            "title": "Low conversion item",
            "priceKopecks": 130_000,
            "views": 2825,
            "contactsMessenger": 4,
            "contacts": 4,
        }
    )

    monkeypatch.setattr(
        "app.routers.avito_repricer.get_source_cache",
        lambda _organization_id, source_key, **_kwargs: {
            "assignments": {"8226131268": "chat_recovery_discount"}
        }
        if source_key == "avito_repricer_strategy_assignments"
        else None,
    )

    payload = _response_payload(
        status=result.status,
        start=date(2026, 7, 1),
        end=date(2026, 7, 28),
        days=28,
        rows=[low_conversion_row],
        accounts=result.accounts,
        organization_id=10,
    )

    row = payload["rows"][0]
    assert row["strategyId"] == "chat_recovery_discount"
    assert row["messengerConversionPct"] == 0.14
    assert row["strategySignal"] == "lower"
    assert row["recommendedPriceKopecks"] == 119_600


def test_avito_repricer_defaults_to_no_strategy_without_price_change():
    result = RecordingRepricerListingsClient().fetch_listings(object())

    payload = _response_payload(
        status=result.status,
        start=date(2026, 7, 1),
        end=date(2026, 7, 28),
        days=28,
        rows=result.rows,
        accounts=result.accounts,
    )

    high_chat_row = next(row for row in payload["rows"] if row["itemId"] == "8098482225")
    assert payload["strategies"][0]["id"] == "none"
    assert high_chat_row["strategyId"] == "none"
    assert high_chat_row["strategyName"] == "Без стратегии"
    assert high_chat_row["strategySignal"] == "keep"
    assert high_chat_row["recommendedPriceKopecks"] == high_chat_row["priceKopecks"]


def test_avito_worker_timing_shows_seconds_until_next_run(monkeypatch):
    monkeypatch.setattr(
        "app.routers.avito_repricer.get_source_cache",
        lambda _organization_id, source_key, **_kwargs: {
            "finishedAt": "2026-07-30T10:00:00+00:00",
        }
        if source_key == "avito_repricer_last_scheduler_run"
        else None,
    )

    payload = _avito_worker_timing_payload(
        organization_id=10,
        settings_payload={"executeIntervalMinutes": 60},
        now_iso="2026-07-30T10:30:00+00:00",
    )

    assert payload["lastRunAt"] == "2026-07-30T10:00:00+00:00"
    assert payload["nextRunAt"] == "2026-07-30T11:00:00+00:00"
    assert payload["secondsUntilNextRun"] == 1800
