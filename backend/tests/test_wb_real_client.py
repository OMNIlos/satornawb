from __future__ import annotations

import json

import httpx
import pytest

from app.wb_api.client import RealWbApiClient, WbApiRequest, build_wb_client


def test_real_wb_api_client_parses_success_payload_with_headers():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == "token-value"
        assert request.headers["X-Client-Secret"] == "secret-value"
        body = {"data": {"id": 146567}}
        return httpx.Response(200, json=body, headers={"X-Ratelimit-Limit": "10", "X-Ratelimit-Remaining": "9"})

    transport = httpx.MockTransport(handler)
    client = RealWbApiClient(
        base_url="https://discounts-prices-api.wildberries.ru",
        token="token-value",
        client_secret="secret-value",
        transport=transport,
    )
    response = client.request(WbApiRequest(method="POST", path="/api/v2/upload/task", jsonBody={"data": []}))
    assert response.ok is True
    assert response.statusCode == 200
    assert response.data == {"data": {"id": 146567}}
    assert response.rateLimit is not None
    assert response.rateLimit.remaining == 9


def test_real_wb_api_client_maps_error_payload():
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(429, text=json.dumps({"errorText": "too many requests"}), headers={"Content-Type": "application/json"})

    transport = httpx.MockTransport(handler)
    client = RealWbApiClient(
        base_url="https://discounts-prices-api.wildberries.ru",
        token="token-value",
        transport=transport,
    )
    response = client.request(WbApiRequest(method="GET", path="/api/v2/history/tasks", query={"uploadID": 1}))
    assert response.ok is False
    assert response.error is not None
    assert response.error.code == "rate_limited"
    assert response.error.retryable is True


def test_real_wb_api_client_returns_transport_timeout_without_retry():
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        raise httpx.ConnectTimeout("_ssl.c:999: The handshake operation timed out", request=request)

    transport = httpx.MockTransport(handler)
    client = RealWbApiClient(
        base_url="https://discounts-prices-api.wildberries.ru",
        token="token-value",
        transport=transport,
    )
    response = client.request(WbApiRequest(method="POST", path="/api/v2/list/goods/filter", query={"limit": 100}))

    assert response.ok is False
    assert response.statusCode == 503
    assert attempts == 1


def test_build_wb_client_real_mode_requires_token(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("VELLA_WB_API_MODE", "real")
    monkeypatch.delenv("VELLA_WB_API_TOKEN", raising=False)
    with pytest.raises(RuntimeError):
        build_wb_client(scenario="complete", force_mode=None)
