from __future__ import annotations

from app.wb22_apply import PriceApplyRequest, PriceApplyRowRequest, _build_upload_payload, run_price_apply
from app.wb_api.client import FakeWbApiClient, WbApiRequest


class NoNetworkClient:
    def request(self, request: WbApiRequest):  # pragma: no cover - failure path only
        raise AssertionError(f"WB request must not be sent in local apply mode: {request.path}")


def test_upload_payload_converts_internal_kopecks_to_wb_rubles():
    payload = _build_upload_payload(
        [
            PriceApplyRowRequest(
                nmId=123456,
                priceKopecks=123_000,
                discountPct=7,
                minPriceKopecks=100_000,
            )
        ]
    )

    assert payload == {"data": [{"nmID": 123456, "price": 1230, "discount": 7, "minPrice": 1000}]}


def test_local_apply_mode_does_not_call_wb_and_marks_result_local():
    result = run_price_apply(
        client=NoNetworkClient(),
        payload=PriceApplyRequest(
            scenario="complete",
            rows=[PriceApplyRowRequest(nmId=123456, priceKopecks=123_000, discountPct=0)],
        ),
        real_apply_enabled=False,
        local_apply_enabled=True,
    )

    assert result.applyState == "local_applied"
    assert result.applyMode == "local_mock"
    assert result.wbMutationSent is False
    assert result.wbUploadId is None


def test_upload_rate_limit_returns_explicit_blocker():
    client = FakeWbApiClient(
        errors={"/api/v2/upload/task": 429},
        headers={"/api/v2/upload/task": {"Retry-After": "7"}},
    )

    result = run_price_apply(
        client=client,
        payload=PriceApplyRequest(
            scenario="complete",
            rows=[PriceApplyRowRequest(nmId=123456, priceKopecks=123_000, discountPct=0)],
        ),
        real_apply_enabled=True,
        local_apply_enabled=False,
    )

    assert result.applyState == "blocked"
    assert result.blockerIds == ["wb_rate_limited"]
    assert result.wbStatus == 429
    assert result.notes == ["WB price upload rate limit reached; retry after 7s"]
    assert [request.path for request in client.requests] == ["/api/v2/upload/task"]
