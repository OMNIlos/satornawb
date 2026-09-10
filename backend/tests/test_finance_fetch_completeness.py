from datetime import datetime, timezone

import pytest
from fastapi import HTTPException

from app import repricer_bff
from app.wb_api.client import FakeWbApiClient, WbApiRequest, WbApiResponseEnvelope


def row(identity=1, **changes):
    return {
        "rrdId": identity,
        "nmId": 101,
        "docTypeName": "Продажа",
        "quantity": 1,
        "retailAmount": "1",
        **changes,
    }


def fetch(monkeypatch, responses):
    requests = []

    class Client:
        def request(self, request):
            requests.append(request)
            assert responses, "fetch did not terminate at the provider boundary"
            status, payload = responses.pop(0)
            return WbApiResponseEnvelope(
                request=request,
                statusCode=status,
                ok=True,
                data={"data": payload},
            )

    monkeypatch.setattr(
        repricer_bff, "build_wb_finance_client", lambda *a, **kw: Client()
    )
    monkeypatch.setattr(repricer_bff, "RateLimitedWbApiClient", lambda inner: inner)
    monkeypatch.setattr(repricer_bff, "_FINANCE_REPORT_MIN_INTERVAL_S", 0)
    result = repricer_bff.fetch_finance_report_aggregates(
        "complete",
        date_from=datetime(2026, 8, 17, tzinfo=timezone.utc),
        date_to=datetime(2026, 8, 23, tzinfo=timezone.utc),
    )
    return result, [request.jsonBody["rrdId"] for request in requests]


@pytest.mark.parametrize("as_text", [False, True])
def test_short_pages_continue_until_204_without_rounding_large_ids(
    monkeypatch, as_text
):
    first = 9_007_199_254_740_992
    second = first + 1
    identities = [str(value) if as_text else value for value in (first, second)]
    result, cursors = fetch(
        monkeypatch,
        [(200, [row(identities[0])]), (200, [row(identities[1])]), (204, None)],
    )

    assert cursors == [0, first, second]
    assert result["rowsCount"] == 2
    assert result["aggregates"]["101"]["revenueGrossKopecks"] == 200
    assert [item["rrdId"] for item in result["rows"]] == identities


@pytest.mark.parametrize(
    "payload", [None, {}, {"data": "invalid"}, [None], [row(), False]]
)
def test_malformed_success_never_becomes_an_empty_or_partial_report(
    monkeypatch, payload
):
    with pytest.raises(HTTPException) as error:
        fetch(monkeypatch, [(200, payload)])
    assert error.value.status_code == 502


@pytest.mark.parametrize("identity", [None, 0, -1, True, 1.5, "bad"])
def test_invalid_finance_identity_cannot_prove_complete_pagination(
    monkeypatch, identity
):
    with pytest.raises(HTTPException) as error:
        fetch(monkeypatch, [(200, [row(identity)])])
    assert error.value.status_code == 502


@pytest.mark.parametrize("last", [1, 2])
def test_nonadvancing_cursor_does_not_publish_a_partial_report(monkeypatch, last):
    with pytest.raises(HTTPException) as error:
        fetch(monkeypatch, [(200, [row(2)]), (200, [row(last)])])
    assert error.value.status_code == 502


def test_repeated_identity_with_changed_money_is_not_silently_discarded(monkeypatch):
    with pytest.raises(HTTPException) as error:
        fetch(monkeypatch, [(200, [row()]), (200, [row(retailAmount="2"), row(2)])])
    assert error.value.status_code == 502


def test_identical_overlap_is_deduplicated_when_cursor_advances(monkeypatch):
    result, cursors = fetch(
        monkeypatch, [(200, [row(), row(2)]), (200, [row(2), row(3)]), (204, None)]
    )
    assert cursors == [0, 2, 3]
    assert result["rowsCount"] == 3
    assert result["duplicateRowsSkipped"] == 1


@pytest.mark.parametrize("response", [(204, None), (200, [])])
def test_explicit_empty_response_is_a_complete_zero(monkeypatch, response):
    result, cursors = fetch(monkeypatch, [response])
    assert result["rowsCount"] == 0
    assert cursors == [0]


def test_fake_finance_provider_models_cursor_pages_and_204():
    path = "/api/finance/v1/sales-reports/detailed"
    client = FakeWbApiClient({path: {"data": [row(), row(2)]}})
    responses = [
        client.request(
            WbApiRequest(
                method="POST", path=path, jsonBody={"rrdId": cursor, "limit": 1}
            )
        )
        for cursor in (0, 1, 2)
    ]
    assert [response.statusCode for response in responses] == [200, 200, 204]
    assert [response.data["data"] for response in responses] == [[row()], [row(2)], []]
    assert client.fixtures[path]["data"] == [row(), row(2)]
