from __future__ import annotations

from datetime import datetime, timezone, timedelta

from fastapi.testclient import TestClient
from pydantic import BaseModel, ValidationError

from app.contracts.envelopes import MoneyKopecks, PaginatedEnvelope
from app.main import create_app
from tests.auth_helpers import auth_headers


def client() -> TestClient:
    return TestClient(create_app())


class MoneyPayload(BaseModel):
    amountKopecks: MoneyKopecks


def test_money_is_integer_kopecks_and_non_negative():
    payload = MoneyPayload(amountKopecks=45_000)
    assert payload.amountKopecks == 45_000

    try:
        MoneyPayload(amountKopecks=-1)
        assert False, "negative amount must fail validation"
    except ValidationError:
        pass


def test_paginated_blockers_endpoint_uses_common_envelope():
    response = client().get("/api/v1/source-registry/blockers/paginated", params={"limit": 3, "offset": 0})

    assert response.status_code == 200
    body = response.json()
    assert body["limit"] == 3
    assert body["offset"] == 0
    assert body["total"] >= 3
    assert len(body["items"]) == 3
    assert body["items"][0]["blockerId"].startswith("WB-")
    assert body["timestamp"].endswith("Z") or body["timestamp"].endswith("+00:00")


def test_adapter_result_endpoint_uses_shared_status_model():
    response = client().get("/api/v1/wb-discovery/repricer/readiness/adapter-result")

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["status"] in {"success", "blocked_by_guard"}
    assert payload["freshness"]["confidence"] in {"high", "medium", "low", "unknown", "blocked"}
    assert payload["data"]["blockingIds"] == []


def test_validation_error_is_returned_as_error_envelope():
    api = client()
    response = api.get("/api/v1/wb-reports/pnl", params={"groupBy": "not-a-group"}, headers=auth_headers(api, "viewer"))

    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert "issues" in body["error"]["details"]


def test_envelope_timestamp_requires_utc():
    class EnvelopeProbe(BaseModel):
        payload: PaginatedEnvelope[int]

    with_timezone_plus_five = datetime.now(timezone(timedelta(hours=5)))
    try:
        EnvelopeProbe(
            payload=PaginatedEnvelope[int](
                items=[1],
                total=1,
                limit=10,
                offset=0,
                timestamp=with_timezone_plus_five,
            )
        )
        assert False, "non-UTC timestamp must fail validation"
    except ValidationError:
        pass
