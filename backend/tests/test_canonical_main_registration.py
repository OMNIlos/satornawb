"""Real application routing/envelopes; domain PostgreSQL gates run separately."""

from uuid import uuid4

import pytest
from fastapi import HTTPException
from fastapi.routing import iter_route_contexts
from fastapi.testclient import TestClient

from app import main
from app.config import Settings
from app.control_plane.auth import ActorContext
from app.orders import router as orders
from app.reviews import canonical_router as reviews


@pytest.fixture
def application(monkeypatch):
    monkeypatch.setattr(main, "get_settings", lambda: Settings())
    return main.create_app()


def test_real_domain_endpoints_are_registered_once_and_in_openapi(application):
    schema = application.openapi()
    for path, method, endpoint in (
        ("/api/v2/orders", "GET", orders.get_orders),
        ("/api/v2/reviews/wb/sync", "POST", reviews.canonical_review_sync),
    ):
        matches = [
            route for route in iter_route_contexts(application.routes)
            if getattr(route, "path", None) == path
            and method in (getattr(route, "methods", None) or ())
        ]
        assert len(matches) == 1
        assert matches[0].endpoint is endpoint
        assert method.lower() in schema["paths"][path]


@pytest.mark.parametrize(
    "path,method,code",
    [
        ("/api/v2/orders", "GET", "orders_authentication_required"),
        ("/api/v2/reviews/wb/sync", "POST", "REVIEW_SYNC_AUTHENTICATION_REQUIRED"),
    ],
)
def test_unauthenticated_requests_use_main_error_envelope(application, path, method, code):
    with TestClient(application) as client:
        response = client.request(method, path)
    assert response.status_code == 401
    assert response.json()["error"]["code"] == code
    assert "detail" not in response.json()


@pytest.mark.parametrize("status,code", [(401, "session_revoked"), (403, "account_denied")])
@pytest.mark.parametrize("domain", [orders, reviews])
def test_auth_dependency_denials_preserve_safe_main_envelope(application, domain, status, code):
    def deny():
        raise HTTPException(status, detail={"code": code})

    dependency = orders.get_orders_actor if domain is orders else reviews.get_review_actor
    application.dependency_overrides[dependency] = deny
    path = "/api/v2/orders" if domain is orders else "/api/v2/reviews/wb/sync"
    method = "GET" if domain is orders else "POST"
    with TestClient(application) as client:
        response = client.request(method, path)
    assert response.status_code == status
    assert response.json()["error"]["code"] == code


def test_review_default_off_never_reaches_provider(application, monkeypatch):
    from app.reviews import canonical_sync

    application.dependency_overrides[reviews.get_review_actor] = lambda: ActorContext(
        "synthetic", "synthetic", 7, "custom", frozenset(), session_id="synthetic"
    )
    application.dependency_overrides[reviews.get_review_engine] = lambda: None
    application.dependency_overrides[reviews.get_review_settings] = lambda: Settings()
    monkeypatch.setattr(canonical_sync, "fetch_feedbacks", lambda **kw: pytest.fail("provider"))
    with TestClient(application) as client:
        response = client.post("/api/v2/reviews/wb/sync", json={
            "marketplace_account_id": 7, "request_id": str(uuid4()), "is_answered": False,
        })
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "REVIEW_SYNC_DISABLED"


def test_review_validation_does_not_echo_sensitive_input(application):
    application.dependency_overrides[reviews.get_review_actor] = lambda: None
    application.dependency_overrides[reviews.get_review_engine] = lambda: None
    application.dependency_overrides[reviews.get_review_settings] = lambda: Settings()
    marker = "synthetic-private-value-never-return"
    with TestClient(application) as client:
        response = client.post("/api/v2/reviews/wb/sync", json={
            "marketplace_account_id": marker, "request_id": marker, "is_answered": marker,
        })
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    assert marker not in response.text
    for issue in response.json()["error"]["details"]["issues"]:
        assert "input" not in issue and "ctx" not in issue
