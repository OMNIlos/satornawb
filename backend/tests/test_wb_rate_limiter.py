from __future__ import annotations

from app.wb_api.client import (
    FakeWbApiClient,
    RateLimitedWbApiClient,
    WbApiRequest,
    WbRateLimitPolicy,
)


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0
        self.sleeps: list[float] = []

    def monotonic(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds


def test_prices_rate_limiter_waits_before_requests():
    clock = FakeClock()
    inner = FakeWbApiClient(fixtures={"/api/v2/list/goods/filter": {"data": {"listGoods": [{"nmID": 1}]}}})
    client = RateLimitedWbApiClient(inner=inner, monotonic_now=clock.monotonic, sleep_fn=clock.sleep)

    client.request(WbApiRequest(method="POST", path="/api/v2/list/goods/filter"))
    client.request(WbApiRequest(method="POST", path="/api/v2/list/goods/filter"))

    assert clock.sleeps == [0.6]


def test_prices_rate_limiter_waits_for_header_retry_before_next_request():
    clock = FakeClock()
    inner = FakeWbApiClient(
        fixtures={"/api/v2/list/goods/filter": {"data": {"listGoods": [{"nmID": 1}]}}},
        errors={"/api/v2/list/goods/filter": 429},
        headers={
            "/api/v2/list/goods/filter": {
                "X-Ratelimit-Limit": "10",
                "X-Ratelimit-Remaining": "0",
                "X-Ratelimit-Retry": "1",
            }
        },
    )
    client = RateLimitedWbApiClient(inner=inner, monotonic_now=clock.monotonic, sleep_fn=clock.sleep)

    response = client.request(WbApiRequest(method="POST", path="/api/v2/list/goods/filter"))
    client.request(WbApiRequest(method="POST", path="/api/v2/list/goods/filter"))

    assert response.statusCode == 429
    assert response.rateLimit is not None
    assert response.rateLimit.retryAfterSeconds == 1
    assert clock.sleeps == [1.0]


def test_marketplace_409_penalty_waits_before_next_request():
    clock = FakeClock()
    policy = WbRateLimitPolicy(
        category="marketplace",
        periodSeconds=5,
        limit=5,
        intervalMs=0,
        burst=5,
        defaultRequestCost=1,
        status409Cost=5,
    )
    inner = FakeWbApiClient(
        fixtures={"/api/v1/marketplace/test": {"ok": True}},
        errors={"/api/v1/marketplace/test": 409},
    )
    client = RateLimitedWbApiClient(
        inner=inner,
        policies={"marketplace": policy},
        monotonic_now=clock.monotonic,
        sleep_fn=clock.sleep,
    )

    client.request(WbApiRequest(method="GET", path="/api/v1/marketplace/test"))
    client.request(WbApiRequest(method="GET", path="/api/v1/marketplace/test"))

    assert clock.sleeps == [1.0]


def test_sales_funnel_policy_uses_conservative_gap():
    clock = FakeClock()
    inner = FakeWbApiClient(fixtures={"/api/analytics/v3/sales-funnel/products": {"data": {"products": []}}})
    client = RateLimitedWbApiClient(inner=inner, monotonic_now=clock.monotonic, sleep_fn=clock.sleep)

    client.request(WbApiRequest(method="POST", path="/api/analytics/v3/sales-funnel/products"))
    client.request(WbApiRequest(method="POST", path="/api/analytics/v3/sales-funnel/products"))

    assert clock.sleeps == [22.0]
