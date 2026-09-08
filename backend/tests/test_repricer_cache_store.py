from datetime import date, datetime, timezone

from app.repricer_cache.store import (
    _source_cache_metadata,
    cached_goods_meta,
    list_source_cache_ranges_by_prefix,
    save_source_cache,
    slim_source_cache_payload,
)
from app.repricer_cache.orm import WbRepricerSourceCacheRow
from sqlalchemy.exc import IntegrityError


def test_source_cache_metadata_is_derived_without_mutating_payload():
    payload = {
        "dateFrom": "2026-07-11",
        "dateTo": "2026-08-09",
        "dailyDetailStatus": "partial",
        "dailyDetailError": "часть запросов не загрузилась",
        "dailyDetailRequestsCompleted": 10,
        "dailyDetailRequestsTotal": 92,
        "dailyAggregates": {
            "2026-07-11": {"123": {"baskets": 2}},
            "2026-07-12": {"123": {"baskets": 1}},
        },
    }
    original = dict(payload)

    metadata = _source_cache_metadata("baskets_2026-07-11_2026-08-09", payload)

    assert metadata == {
        "range_date_from": date(2026, 7, 11),
        "range_date_to": date(2026, 8, 9),
        "daily_detail_status": "partial",
        "daily_detail_error": "часть запросов не загрузилась",
        "daily_detail_deferred_at": None,
        "daily_detail_paused_at": None,
        "daily_detail_failed_at": None,
        "daily_detail_fetched_at": None,
        "daily_detail_partial_at": None,
        "daily_detail_preserved_at": None,
        "daily_detail_preserved_by": None,
        "daily_detail_requests_completed": 10,
        "daily_detail_requests_total": 92,
        "daily_aggregate_dates": ["2026-07-11", "2026-07-12"],
    }
    assert payload == original


def test_list_source_cache_ranges_avoids_payload_and_parses_legacy_key(monkeypatch):
    class FakeResult:
        def mappings(self):
            return self

        def __iter__(self):
            return iter(
                [
                    {
                        "source_key": "baskets_2026-07-11_2026-08-09",
                        "range_date_from": None,
                        "range_date_to": None,
                        "daily_detail_status": None,
                        "daily_detail_error": None,
                        "daily_detail_deferred_at": None,
                        "daily_detail_paused_at": None,
                        "daily_detail_failed_at": None,
                        "daily_detail_fetched_at": None,
                        "daily_detail_partial_at": None,
                        "daily_detail_preserved_at": None,
                        "daily_detail_preserved_by": None,
                        "daily_detail_requests_completed": None,
                        "daily_detail_requests_total": None,
                        "daily_aggregate_dates": None,
                        "fetched_at": datetime(2026, 8, 10, 16, 10, tzinfo=timezone.utc),
                    }
                ]
            )

    class FakeSession:
        def execute(self, statement, params):
            sql = str(statement).lower()
            assert "payload" not in sql
            assert "jsonb" not in sql
            assert params == {
                "organization_id": 2,
                "source_key_pattern": "baskets_%",
                "limit": 100,
            }
            return FakeResult()

    monkeypatch.setattr("app.repricer_cache.store._run_db", lambda db_fn: db_fn(FakeSession()))

    result = list_source_cache_ranges_by_prefix(2, "baskets_", limit=100)

    assert result[0]["dateFrom"] == "2026-07-11"
    assert result[0]["dateTo"] == "2026-08-09"
    assert result[0]["dailyAggregateDates"] == []
    assert result[0]["dailyAggregatesDays"] is None


def test_slim_finance_source_cache_drops_raw_rows():
    payload = {
        "aggregates": {"123": {"salesUnits": 2}},
        "rows": [{"nmId": 123, "quantity": 1}],
        "count": 1,
        "rowsCount": 1,
    }
    slim = slim_source_cache_payload("finance_30", payload)
    assert "rows" not in slim
    assert slim["aggregates"]["123"]["salesUnits"] == 2


def test_save_finance_source_cache_omits_raw_rows():
    saved = save_source_cache(
        99,
        "finance_30",
        {
            "aggregates": {"1": {"salesUnits": 1}},
            "rows": [{"nmId": 1}],
            "count": 1,
        },
    )
    assert "rows" not in saved


def test_slim_source_cache_preserves_category_fields():
    content = slim_source_cache_payload(
        "content_cards",
        {
            "cards": [
                {
                    "vendorCode": "ФБbt_1133",
                    "nmID": 453200669,
                    "title": "Футболка",
                    "object": "Футболки",
                    "objectID": 192,
                    "subjectID": 192,
                    "brand": "Anomie Studio",
                    "sizes": [{"skus": [123]}],
                }
            ]
        },
    )
    goods = slim_source_cache_payload(
        "goods",
        {
            "goods": [
                {
                    "vendorCode": "ФБbt_1133",
                    "nmID": 453200669,
                    "brand": "Anomie Studio",
                    "subjectName": "Футболки",
                    "subjectID": 192,
                    "sizes": [{"price": 2809}],
                }
            ]
        },
    )

    assert content["cards"][0]["objectID"] == 192
    assert content["cards"][0]["subjectID"] == 192
    assert goods["goods"][0]["subjectID"] == 192
    assert goods["goods"][0]["subjectName"] == "Футболки"


def test_save_source_cache_recovers_from_insert_race(monkeypatch):
    class FakeResult:
        def __init__(self, rowcount: int):
            self.rowcount = rowcount

    class FakeSession:
        def __init__(self):
            self.execute_calls = 0
            self.commits = 0
            self.rollbacks = 0

        def execute(self, statement):
            self.execute_calls += 1
            if self.execute_calls == 1:
                return FakeResult(0)
            return FakeResult(1)

        def add(self, row):
            assert isinstance(row, WbRepricerSourceCacheRow)

        def commit(self):
            self.commits += 1
            if self.commits == 1:
                raise IntegrityError("insert", {}, Exception("duplicate key"))

        def rollback(self):
            self.rollbacks += 1

    fake_session = FakeSession()

    monkeypatch.setattr("app.repricer_cache.store._run_db", lambda db_fn: db_fn(fake_session))

    saved = save_source_cache(2, "reports_job_stock_2026-06-10_2026-07-10_sku", {"state": "completed"})

    assert saved["state"] == "completed"
    assert fake_session.rollbacks == 1
    assert fake_session.execute_calls == 2


def test_cached_goods_meta_uses_sql_aggregate_without_loading_payload(monkeypatch):
    class FakeResult:
        def mappings(self):
            return self

        def first(self):
            return {
                "pages_cached": 2,
                "total_cached": 1750,
                "next_offset": 2000,
                "page_limit": 1000,
                "latest_fetched_at": datetime(2026, 7, 28, 8, 30, tzinfo=timezone.utc),
            }

    class FakeSession:
        def scalars(self, _statement):
            raise AssertionError("cached_goods_meta must not load goods_payload rows")

        def execute(self, _statement, params=None):
            assert params == {"organization_id": 5}
            return FakeResult()

    monkeypatch.setattr("app.repricer_cache.store._run_db", lambda db_fn: db_fn(FakeSession()))
    monkeypatch.setattr("app.repricer_cache.store._redis_get_json", lambda _key: None)
    monkeypatch.setattr("app.repricer_cache.store._redis_set_json", lambda *_args, **_kwargs: None)

    assert cached_goods_meta(5) == {
        "pagesCached": 2,
        "totalCached": 1750,
        "nextOffset": 2000,
        "pageLimit": 1000,
        "latestFetchedAt": "2026-07-28T08:30:00+00:00",
    }
