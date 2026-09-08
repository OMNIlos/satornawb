from __future__ import annotations

import json
from datetime import date

import pytest

import app.wb_api.raw_funnel as raw_module
from app.platform.funnel.raw import normalize_raw_funnel
from app.platform.period import Period
from app.wb_api.client import (
    RateLimitInfo,
    RateLimitedWbApiClient,
    WbApiRequest,
    WbApiResponseEnvelope,
    classify_wb_error,
)

PERIOD = Period(date(2026, 9, 2), date(2026, 9, 3))


class HistoryClient:
    def __init__(
        self,
        *,
        wrapper: bool = True,
        failures: int = 0,
        malformed: bool = False,
    ) -> None:
        self.wrapper = wrapper
        self.failures = failures
        self.malformed = malformed
        self.requests: list[WbApiRequest] = []

    def request(self, request: WbApiRequest) -> WbApiResponseEnvelope:
        self.requests.append(request)
        if len(self.requests) <= self.failures:
            rate_limit = RateLimitInfo(retryAfterSeconds=0)
            return WbApiResponseEnvelope(
                request=request,
                statusCode=429,
                ok=False,
                error=classify_wb_error(429, "do not expose", rate_limit),
                rateLimit=rate_limit,
                wbRequestId=f"failed-{len(self.requests)}",
            )
        rows = [
            {
                "product": {"nmId": nm_id},
                "history": [
                    {
                        "date": request.jsonBody["selectedPeriod"]["start"],
                        "openCount": nm_id,
                        "cartCount": 0,
                        "orderCount": 0,
                        "orderSum": 0,
                        "buyoutCount": 0,
                        "buyoutSum": 0,
                        "addToWishlistCount": 0,
                    }
                ],
                "currency": "RUB",
            }
            for nm_id in request.jsonBody["nmIds"]
        ]
        if self.malformed:
            data = {"data": rows, "error": "unexpected sibling"}
        else:
            data = {"data": rows} if self.wrapper else rows
        return WbApiResponseEnvelope(
            request=request,
            statusCode=200,
            ok=True,
            data=data,
            wbRequestId=f"request-{len(self.requests)}",
        )


def _execute(client: HistoryClient, ids: list[int], period: Period = PERIOD):
    return raw_module._execute_plan(RateLimitedWbApiClient(client), period, ids)


def test_funnel_fetch_uses_deterministic_twenty_sku_batches() -> None:
    fake = HistoryClient()

    result = _execute(fake, list(reversed(range(1, 22))))

    assert result.state == "ready"
    assert (result.expected_requests, result.completed_requests) == (2, 2)
    assert [request.path for request in fake.requests] == [
        "/api/analytics/v3/sales-funnel/products/history",
        "/api/analytics/v3/sales-funnel/products/history",
    ]
    assert [request.jsonBody for request in fake.requests] == [
        {
            "selectedPeriod": {"start": "2026-09-02", "end": "2026-09-03"},
            "nmIds": list(range(1, 21)),
            "skipDeletedNm": False,
            "aggregationLevel": "day",
        },
        {
            "selectedPeriod": {"start": "2026-09-02", "end": "2026-09-03"},
            "nmIds": [21],
            "skipDeletedNm": False,
            "aggregationLevel": "day",
        },
    ]
    assert all(request.method == "POST" and request.query == {} for request in fake.requests)


def test_funnel_fetch_collapses_input_duplicates() -> None:
    fake = HistoryClient()

    result = _execute(fake, [3, 1, 3, 2, 1])

    assert result.state == "ready"
    assert fake.requests[0].jsonBody["nmIds"] == [1, 2, 3]


@pytest.mark.parametrize("ids", [[], [0], [-1], [True], [1, "2"]])
def test_funnel_fetch_rejects_invalid_ids_before_io(ids) -> None:
    fake = HistoryClient()

    with pytest.raises(ValueError, match="nmIds"):
        _execute(fake, ids)

    assert fake.requests == []


def test_funnel_fetch_rejects_period_over_seven_days_before_io() -> None:
    fake = HistoryClient()

    with pytest.raises(ValueError, match="period"):
        _execute(fake, [1], Period(date(2026, 8, 27), date(2026, 9, 3)))

    assert fake.requests == []


@pytest.mark.parametrize("wrapper", [True, False])
def test_funnel_fetch_accepts_only_proven_response_shapes(wrapper: bool) -> None:
    fake = HistoryClient(wrapper=wrapper)

    result = _execute(fake, [1])

    assert result.state == "ready"
    assert len(result.bundle["pages"]) == 1
    assert len(normalize_raw_funnel(PERIOD, result.bundle).facts) == 1


def test_funnel_fetch_marks_malformed_success_partial() -> None:
    result = _execute(HistoryClient(malformed=True), [1])

    assert result.state == "partial"
    assert (result.expected_requests, result.completed_requests) == (1, 0)
    assert result.failure_codes == ("invalid_payload",)
    assert result.bundle["pages"] == []
    assert result.bundle["manifest"][0]["ok"] is False


def test_funnel_fetch_retries_429_then_completes(monkeypatch) -> None:
    fake = HistoryClient(failures=2)
    monkeypatch.setattr("app.wb_api.ads_runtime.time.sleep", lambda _seconds: None)

    result = _execute(fake, [1])

    assert result.state == "ready"
    assert len(fake.requests) == 3
    assert (result.expected_requests, result.completed_requests) == (1, 1)


def test_funnel_fetch_marks_exhausted_429_partial(monkeypatch) -> None:
    fake = HistoryClient(failures=3)
    monkeypatch.setattr("app.wb_api.ads_runtime.time.sleep", lambda _seconds: None)

    result = _execute(fake, [1])

    assert result.state == "partial"
    assert (result.expected_requests, result.completed_requests) == (1, 0)
    assert result.failure_codes == ("rate_limited",)
    assert result.bundle["pages"] == []


def test_funnel_fetch_and_snapshot_ignore_input_order() -> None:
    first = _execute(HistoryClient(), list(range(1, 22)))
    second = _execute(HistoryClient(), list(reversed(range(1, 22))))

    assert first.bundle == second.bundle
    assert (
        normalize_raw_funnel(PERIOD, first.bundle).snapshot_checksum
        == normalize_raw_funnel(PERIOD, second.bundle).snapshot_checksum
    )


def test_funnel_fetch_manifest_is_secret_free_and_auditable(monkeypatch) -> None:
    token = "never-emit-this-token"
    fake = HistoryClient()
    monkeypatch.setattr(raw_module, "build_wb_analytics_client", lambda *_args, **_kwargs: fake)

    result = raw_module.fetch_raw_funnel(PERIOD, [1], wb_token=token)

    encoded = json.dumps(result.bundle)
    assert token not in encoded
    assert result.bundle["manifest"][0]["wbRequestId"] == "request-1"
    assert len(result.bundle["manifest"][0]["responseChecksum"]) == 64
