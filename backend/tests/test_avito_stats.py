from __future__ import annotations

from datetime import date

from fastapi.testclient import TestClient
import httpx

from app.avito.stats import AvitoStatsAccount, AvitoStatsClient, AvitoStatsFetchRequest, AvitoStatsFetchResult, AvitoStatsItem, LiveAvitoStatsClient
from app.main import create_app
from tests.auth_helpers import auth_headers


EXPECTED_AVITO_ITEM_ANALYTICS_METRICS = [
    "impressions",
    "views",
    "contactsMessenger",
    "contacts",
    "contactsShowPhone",
    "contactsShowPhoneAndMessenger",
    "favorites",
    "allSpending",
    "orderedItems",
    "deliveredItems",
]


class RecordingAvitoStatsClient:
    def __init__(self, access_token: str | None = None) -> None:
        self.access_token = access_token
        self.requests: list[AvitoStatsFetchRequest] = []

    def fetch_stats(self, request: AvitoStatsFetchRequest) -> AvitoStatsFetchResult:
        self.requests.append(request)
        return AvitoStatsFetchResult(
            status="synced",
            accounts=[
                AvitoStatsAccount(accountId="365024549", accountName="Bless T", itemCount=2),
            ],
            items=[
                AvitoStatsItem(
                    itemId="8098482225",
                    title="Худи yohji yamamoto pour homme",
                    accountId="365024549",
                    accountName="Bless T",
                    category="Одежда, обувь, аксессуары",
                    url="https://www.avito.ru/item/8098482225",
                    impressions=10_000,
                    views=7_850,
                    contacts=88,
                    favorites=640,
                    spendKopecks=1_651_900,
                    orders=15,
                    buyouts=11,
                    sourceStatus="fresh",
                    updatedAt="2026-07-28T06:55:00+00:00",
                ),
                AvitoStatsItem(
                    itemId="8098459618",
                    title="Футболка Devil Nut Evil Skull",
                    accountId="365024549",
                    accountName="Bless T",
                    category="Одежда, обувь, аксессуары",
                    url="https://www.avito.ru/item/8098459618",
                    impressions=220,
                    views=100,
                    contacts=0,
                    favorites=13,
                    spendKopecks=0,
                    orders=0,
                    buyouts=0,
                    sourceStatus="stale",
                    updatedAt="2026-07-28T05:30:00+00:00",
                ),
            ],
            diagnostics={
                "status": 200,
                "groupings": 2,
                "dataTotalCount": 2,
                "requestUrl": "https://api.avito.ru/stats/v2/accounts/365024549/items",
                "requestBody": {
                    "grouping": "item",
                    "metrics": EXPECTED_AVITO_ITEM_ANALYTICS_METRICS,
                },
                "bodyPreview": {"result": {"dataTotalCount": 2, "groupings": [{"id": 8098482225}, {"id": 8098459618}]}},
                "itemsCount": 2,
                "itemIdsSample": ["8098482225", "8098459618"],
            },
        )


class AvitoStatsHttpResponse:
    def __init__(self, payload: dict, status_code: int = 200) -> None:
        self.payload = payload
        self.status_code = status_code
        self.text = str(payload)

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            request = httpx.Request("POST", "https://api.avito.ru/test")
            response = httpx.Response(self.status_code, request=request, json=self.payload)
            raise httpx.HTTPStatusError(f"HTTP {self.status_code}", request=request, response=response)
        return None

    def json(self) -> dict:
        return self.payload


class RecordingAvitoStatsHttpClient:
    def __init__(self, payload: dict) -> None:
        self.payloads = [payload]
        self.posts: list[dict] = []

    def post(self, url: str, **kwargs) -> AvitoStatsHttpResponse:
        self.posts.append({"url": url, **kwargs})
        payload = self.payloads.pop(0) if self.payloads else {}
        if isinstance(payload, tuple):
            body, status_code = payload
            return AvitoStatsHttpResponse(body, status_code)
        return AvitoStatsHttpResponse(payload)


class SequencedAvitoStatsHttpClient(RecordingAvitoStatsHttpClient):
    def __init__(self, payloads: list[dict]) -> None:
        self.payloads = list(payloads)
        self.posts: list[dict] = []


class RecordingAvitoItemsHttpClient:
    def __init__(self, payloads: list[dict]) -> None:
        self.payloads = list(payloads)
        self.gets: list[dict] = []

    def get(self, url: str, **kwargs) -> AvitoStatsHttpResponse:
        self.gets.append({"url": url, **kwargs})
        return AvitoStatsHttpResponse(self.payloads.pop(0))


def test_live_avito_stats_client_posts_v2_item_analytics_payload_expected_by_avito():
    http_client = RecordingAvitoStatsHttpClient(
        {
            "result": {
                "groupings": [
                    {
                        "id": 8098482225,
                        "type": "item",
                        "metrics": [
                            {"slug": "impressions", "value": 20},
                            {"slug": "views", "value": 6},
                            {"slug": "contactsMessenger", "value": 2},
                            {"slug": "contacts", "value": 3},
                            {"slug": "contactsShowPhone", "value": 1},
                            {"slug": "contactsShowPhoneAndMessenger", "value": 1},
                            {"slug": "favorites", "value": 8},
                            {"slug": "allSpending", "value": 1200},
                            {"slug": "orderedItems", "value": 2},
                            {"slug": "deliveredItems", "value": 1},
                        ],
                    }
                ]
            }
        }
    )
    client = LiveAvitoStatsClient(access_token="token", base_url="https://api.avito.ru")

    rows = client._stats_for_items(
        http_client,
        AvitoStatsFetchRequest(dateFrom=date(2026, 7, 1), dateTo=date(2026, 7, 28)),
        [AvitoStatsAccount(accountId="365024549", accountName="Bless T", itemCount=0)],
        [
            {
                "itemId": "8098482225",
                "title": "Худи yohji yamamoto pour homme",
                "accountId": "365024549",
                "accountName": "Bless T",
                "category": "Одежда, обувь, аксессуары",
                "url": "https://www.avito.ru/item/8098482225",
            }
        ],
    )

    assert http_client.posts[0]["url"] == "https://api.avito.ru/stats/v2/accounts/365024549/items"
    assert http_client.posts[0]["json"] == {
        "dateFrom": "2026-07-01",
        "dateTo": "2026-07-28",
        "grouping": "item",
        "metrics": EXPECTED_AVITO_ITEM_ANALYTICS_METRICS,
        "limit": 1000,
        "offset": 0,
    }
    assert len(http_client.posts) == 1
    assert rows[0].impressions == 20
    assert rows[0].views == 6
    assert rows[0].contactsMessenger == 2
    assert rows[0].contacts == 3
    assert rows[0].contactsShowPhone == 1
    assert rows[0].contactsShowPhoneAndMessenger == 1
    assert rows[0].favorites == 8
    assert rows[0].spendKopecks == 1200
    assert rows[0].orders == 2
    assert rows[0].buyouts == 1


def test_live_avito_stats_client_keeps_items_when_v2_item_analytics_are_empty():
    http_client = SequencedAvitoStatsHttpClient(
        [
            {"result": {"groupings": []}},
        ]
    )
    client = LiveAvitoStatsClient(access_token="token", base_url="https://api.avito.ru")

    rows = client._stats_for_items(
        http_client,
        AvitoStatsFetchRequest(dateFrom=date(2026, 7, 1), dateTo=date(2026, 7, 28)),
        [AvitoStatsAccount(accountId="365024549", accountName="Bless T", itemCount=0)],
        [
            {
                "itemId": "8098482225",
                "title": "Худи yohji yamamoto pour homme",
                "accountId": "365024549",
                "accountName": "Bless T",
                "category": "Одежда, обувь, аксессуары",
                "url": "https://www.avito.ru/item/8098482225",
            }
        ],
    )

    assert len(http_client.posts) == 1
    assert http_client.posts[0]["url"] == "https://api.avito.ru/stats/v2/accounts/365024549/items"
    assert rows[0].views is None
    assert rows[0].contacts is None
    assert rows[0].sourceStatus == "partial"


def test_live_avito_stats_client_uses_null_when_v2_metric_is_absent():
    client = LiveAvitoStatsClient(access_token="token", base_url="https://api.avito.ru")

    rows = client._stats_for_items(
        RecordingAvitoStatsHttpClient(
            {
                "result": {
                    "groupings": [
                        {"id": 8098482225, "type": "item", "metrics": [{"slug": "views", "value": 0}]},
                    ]
                }
            }
        ),
        AvitoStatsFetchRequest(dateFrom=date(2026, 7, 1), dateTo=date(2026, 7, 28)),
        [AvitoStatsAccount(accountId="365024549", accountName="Bless T", itemCount=0)],
        [
            {
                "itemId": "8098482225",
                "title": "Худи yohji yamamoto pour homme",
                "accountId": "365024549",
                "accountName": "Bless T",
            }
        ],
    )

    assert rows[0].views == 0
    assert rows[0].contacts is None
    assert rows[0].favorites is None


def test_live_avito_stats_client_accepts_avito_items_grouping_type():
    client = LiveAvitoStatsClient(access_token="token", base_url="https://api.avito.ru")

    rows = client._stats_for_items(
        RecordingAvitoStatsHttpClient(
            {
                "result": {
                    "dataTotalCount": 1,
                    "groupings": [
                        {
                            "id": 8226644604,
                            "type": "items",
                            "metrics": [
                                {"slug": "impressions", "value": 13168},
                                {"slug": "views", "value": 3562},
                                {"slug": "contacts", "value": 122},
                                {"slug": "favorites", "value": 317},
                            ],
                        }
                    ],
                }
            }
        ),
        AvitoStatsFetchRequest(dateFrom=date(2026, 6, 29), dateTo=date(2026, 7, 28)),
        [AvitoStatsAccount(accountId="365024549", accountName="Bless T", itemCount=0)],
        [
            {
                "itemId": "8226644604",
                "title": "Avito item",
                "accountId": "365024549",
                "accountName": "Bless T",
            }
        ],
    )

    assert rows[0].impressions == 13_168
    assert rows[0].views == 3_562
    assert rows[0].contacts == 122
    assert rows[0].favorites == 317
    assert rows[0].sourceStatus == "fresh"


def test_live_avito_stats_client_splits_v2_item_analytics_ranges_over_30_days():
    client = LiveAvitoStatsClient(access_token="token", base_url="https://api.avito.ru")
    http_client = SequencedAvitoStatsHttpClient(
        [
            {
                "result": {
                    "dataTotalCount": 1,
                    "groupings": [
                        {"id": 8098482225, "type": "items", "metrics": [{"slug": "views", "value": 40_000}]},
                    ],
                }
            },
            {
                "result": {
                    "dataTotalCount": 1,
                    "groupings": [
                        {"id": 8098482225, "type": "items", "metrics": [{"slug": "views", "value": 1_460}]},
                    ],
                }
            },
        ]
    )

    rows = client._stats_for_items(
        http_client,
        AvitoStatsFetchRequest(dateFrom=date(2026, 7, 4), dateTo=date(2026, 8, 4)),
        [AvitoStatsAccount(accountId="365024549", accountName="Bless T", itemCount=0)],
        [{"itemId": "8098482225", "title": "Avito item", "accountId": "365024549", "accountName": "Bless T"}],
    )

    assert [post["json"]["dateFrom"] for post in http_client.posts] == ["2026-07-04", "2026-08-03"]
    assert [post["json"]["dateTo"] for post in http_client.posts] == ["2026-08-02", "2026-08-04"]
    assert rows[0].views == 41_460
    assert rows[0].sourceStatus == "fresh"


def test_live_avito_stats_client_uses_totals_grouping_without_item_pages():
    client = LiveAvitoStatsClient(access_token="token", base_url="https://api.avito.ru")
    http_client = SequencedAvitoStatsHttpClient(
        [
            {
                "result": {
                    "dataTotalCount": 1,
                    "groupings": [
                        {
                            "type": "totals",
                            "metrics": [
                                {"slug": "views", "value": 40_659},
                                {"slug": "contacts", "value": 770},
                                {"slug": "favorites", "value": 5_746},
                                {"slug": "allSpending", "value": 11_671_300},
                            ],
                        },
                    ],
                }
            }
        ]
    )

    rows, daily = client._stats_totals(
        http_client,
        AvitoStatsFetchRequest(dateFrom=date(2026, 7, 4), dateTo=date(2026, 8, 4), grouping="totals"),
        [AvitoStatsAccount(accountId="365024549", accountName="Bless T", itemCount=0)],
    )

    assert len(http_client.posts) == 1
    assert http_client.posts[0]["json"]["dateFrom"] == "2026-07-04"
    assert http_client.posts[0]["json"]["dateTo"] == "2026-08-04"
    assert http_client.posts[0]["json"]["grouping"] == "totals"
    assert http_client.posts[0]["json"]["limit"] == 1
    assert rows[0].views == 40_659
    assert rows[0].contacts == 770
    assert rows[0].favorites == 5_746
    assert rows[0].spendKopecks == 11_671_300
    assert rows[0].sourceStatus == "fresh"
    assert daily == []


def test_live_avito_stats_client_sums_totals_when_avito_returns_date_groups():
    client = LiveAvitoStatsClient(access_token="token", base_url="https://api.avito.ru")
    http_client = SequencedAvitoStatsHttpClient(
        [
            {
                "result": {
                    "dataTotalCount": 7,
                    "groupings": [
                        {
                            "id": 1_754_352_000,
                            "type": "dates",
                            "metrics": [
                                {"slug": "views", "value": 100},
                                {"slug": "contacts", "value": 7},
                                {"slug": "allSpending", "value": 12_000},
                            ],
                        },
                        {
                            "id": 1_754_438_400,
                            "type": "dates",
                            "metrics": [
                                {"slug": "views", "value": 1_360},
                                {"slug": "contacts", "value": 6},
                                {"slug": "favorites", "value": 202},
                                {"slug": "allSpending", "value": 353_800},
                            ],
                        },
                    ],
                }
            }
        ]
    )

    rows, daily = client._stats_totals(
        http_client,
        AvitoStatsFetchRequest(dateFrom=date(2026, 7, 29), dateTo=date(2026, 8, 4), grouping="totals"),
        [AvitoStatsAccount(accountId="365024549", accountName="Bless T", itemCount=0)],
    )

    assert len(http_client.posts) == 1
    assert rows[0].views == 1_460
    assert rows[0].contacts == 13
    assert rows[0].favorites == 202
    assert rows[0].spendKopecks == 365_800
    assert rows[0].sourceStatus == "fresh"
    assert [point.views for point in daily] == [100, 1_360]
    assert [point.contacts for point in daily] == [7, 6]
    assert [point.favorites for point in daily] == [None, 202]


def test_live_avito_stats_client_paginates_v2_item_analytics_groups():
    client = LiveAvitoStatsClient(access_token="token", base_url="https://api.avito.ru")
    first_page = [
        {"id": index, "type": "items", "metrics": [{"slug": "views", "value": 1}]}
        for index in range(1, 1001)
    ]
    http_client = SequencedAvitoStatsHttpClient(
        [
            {"result": {"dataTotalCount": 1001, "groupings": first_page}},
            {
                "result": {
                    "dataTotalCount": 1001,
                    "groupings": [
                        {"id": 1001, "type": "items", "metrics": [{"slug": "views", "value": 77}]},
                    ],
                }
            },
        ]
    )

    rows = client._stats_for_items(
        http_client,
        AvitoStatsFetchRequest(dateFrom=date(2026, 7, 6), dateTo=date(2026, 8, 4)),
        [AvitoStatsAccount(accountId="365024549", accountName="Bless T", itemCount=0)],
        [{"itemId": "1001", "title": "Paged item", "accountId": "365024549", "accountName": "Bless T"}],
    )

    assert [post["json"]["offset"] for post in http_client.posts] == [0, 1000]
    assert rows[0].views == 77
    assert rows[0].sourceStatus == "fresh"


def test_live_avito_stats_client_metric_reader_uses_later_key_variants():
    assert LiveAvitoStatsClient._int_metric({"views": 9}, "uniqViews", "views") == 9


def test_live_avito_stats_client_paginates_items_with_avito_limit_below_100():
    http_client = RecordingAvitoItemsHttpClient(
        [
            {"resources": [{"id": index, "title": f"Item {index}"} for index in range(1, 100)]},
            {"resources": [{"id": 100, "title": "Item 100"}]},
        ]
    )
    client = LiveAvitoStatsClient(access_token="token", base_url="https://api.avito.ru")

    rows = client._items(http_client, [AvitoStatsAccount(accountId="365024549", accountName="Bless T", itemCount=0)])

    assert len(rows) == 100
    assert http_client.gets[0]["params"] == {"per_page": 99, "page": 1, "status": "active,removed,old"}
    assert http_client.gets[1]["params"] == {"per_page": 99, "page": 2, "status": "active,removed,old"}


def test_live_avito_stats_client_counts_active_and_inactive_items_from_core_statuses():
    client = LiveAvitoStatsClient(access_token="token", base_url="https://api.avito.ru")
    account = AvitoStatsAccount(accountId="365024549", accountName="Bless T", itemCount=0)

    rows = client._stats_for_items(
        RecordingAvitoStatsHttpClient(
            {
                "result": {
                    "groupings": [
                        {
                            "id": 8098482225,
                            "type": "items",
                            "metrics": [{"slug": "views", "value": 6}],
                        },
                        {
                            "id": 8098482191,
                            "type": "items",
                            "metrics": [{"slug": "views", "value": 4}],
                        },
                    ]
                }
            }
        ),
        AvitoStatsFetchRequest(dateFrom=date(2026, 7, 1), dateTo=date(2026, 7, 28)),
        [account],
        [
            {"itemId": "8098482225", "title": "Active item", "accountId": "365024549", "accountName": "Bless T", "status": "active"},
            {"itemId": "8098482191", "title": "Removed item", "accountId": "365024549", "accountName": "Bless T", "status": "removed"},
            {"itemId": "8098459618", "title": "Old item", "accountId": "365024549", "accountName": "Bless T", "status": "old"},
        ],
    )

    assert account.itemCount == 3
    assert account.activeItemCount == 1
    assert account.inactiveItemCount == 2
    assert len(rows) == 3


def test_avito_stats_endpoint_uses_saved_avito_credentials_and_caches_payload(monkeypatch):
    recording_client: RecordingAvitoStatsClient | None = None
    cached_payloads: list[tuple[int, str, dict]] = []

    def build_recording_client(*_args, **kwargs):
        nonlocal recording_client
        recording_client = RecordingAvitoStatsClient(access_token=kwargs["access_token"])
        return recording_client

    monkeypatch.setattr("app.routers.avito_stats.build_avito_stats_client", build_recording_client)
    monkeypatch.setattr(
        "app.routers.avito_stats.resolve_user_avito_access_token",
        lambda **_kwargs: "avito-live-bearer-token",
    )
    monkeypatch.setattr("app.routers.avito_stats.get_source_cache", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        "app.routers.avito_stats.save_source_cache",
        lambda organization_id, source_key, payload: cached_payloads.append((organization_id, source_key, payload)),
    )
    api = TestClient(create_app())
    headers = auth_headers(api, "viewer")
    put_credentials = api.put(
        "/api/v1/cabinet/avito-credentials",
        json={"clientId": "avito_client_0987654321", "clientSecret": "avito_secret_1234567890"},
        headers=headers,
    )
    assert put_credentials.status_code == 200

    response = api.get(
        "/api/v1/avito/stats",
        params={"dateFrom": "2026-07-01", "dateTo": "2026-07-28"},
        headers=headers,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["period"] == {"dateFrom": "2026-07-01", "dateTo": "2026-07-28", "days": 28}
    assert payload["summary"]["views"] == 7_950
    assert payload["summary"]["contacts"] == 88
    assert payload["summary"]["favorites"] == 653
    assert payload["summary"]["orders"] == 15
    assert payload["summary"]["buyouts"] == 11
    assert payload["summary"]["spendKopecks"] == 1_651_900
    assert payload["summary"]["conversionPct"] == 1.11
    assert payload["rows"][0]["itemId"] == "8098482225"
    assert payload["rows"][0]["contactConversionPct"] == 1.12
    assert payload["rows"][1]["controlFlags"] == ["no_contacts", "stale_source"]
    assert payload["source"]["diagnostics"]["status"] == 200
    assert payload["source"]["diagnostics"]["groupings"] == 2
    assert payload["source"]["diagnostics"]["dataTotalCount"] == 2
    assert payload["source"]["diagnostics"]["requestBody"]["metrics"] == EXPECTED_AVITO_ITEM_ANALYTICS_METRICS
    assert payload["source"]["diagnostics"]["itemsCount"] == 2
    assert payload["source"]["diagnostics"]["itemIdsSample"] == ["8098482225", "8098459618"]
    assert recording_client is not None
    assert recording_client.access_token == "avito-live-bearer-token"
    assert recording_client.requests[0].dateFrom == date(2026, 7, 1)
    assert recording_client.requests[0].dateTo == date(2026, 7, 28)
    assert cached_payloads
    assert cached_payloads[0][1] == "avito_stats:2026-07-01:2026-07-28:all"
    assert cached_payloads[0][2]["rows"][0]["itemId"] == "8098482225"


def test_avito_stats_endpoint_reports_missing_avito_credentials():
    api = TestClient(create_app())
    headers = auth_headers(api, "viewer")
    api.delete("/api/v1/cabinet/avito-credentials", headers=headers)

    response = api.get("/api/v1/avito/stats", headers=headers)

    assert response.status_code == 409
    assert response.json()["error"]["message"] == "AVITO_CREDENTIALS_REQUIRED"


def test_avito_stats_endpoint_returns_exact_period_cache_before_calling_avito(monkeypatch):
    cached_payload = {
        "status": "synced",
        "period": {"dateFrom": "2026-07-01", "dateTo": "2026-07-28", "days": 28},
        "summary": {
            "impressions": 10,
            "views": 7,
            "contacts": 1,
            "favorites": 0,
            "spendKopecks": 0,
            "orders": 0,
            "buyouts": 0,
            "conversionPct": 14.29,
            "orderConversionPct": 0,
            "buyoutPct": 0,
            "problemRows": 0,
        },
        "accounts": [],
        "rows": [{"itemId": "cached-1", "title": "Cached Avito row"}],
        "source": {"mode": "live", "cache": {"status": "fresh", "savedAt": "2026-07-28T00:00:00+00:00"}},
    }

    monkeypatch.setattr("app.routers.avito_stats.get_source_cache", lambda *_args, **_kwargs: cached_payload)

    def fail_if_called(**_kwargs):
        raise AssertionError("Avito OAuth must not be called while exact cached stats exist")

    monkeypatch.setattr("app.routers.avito_stats.resolve_user_avito_access_token", fail_if_called)
    api = TestClient(create_app())
    headers = auth_headers(api, "viewer")

    response = api.get(
        "/api/v1/avito/stats",
        params={"dateFrom": "2026-07-01", "dateTo": "2026-07-28"},
        headers=headers,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["rows"][0]["itemId"] == "cached-1"
    assert payload["source"]["cache"]["status"] == "hit"
