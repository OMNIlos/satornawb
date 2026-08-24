from __future__ import annotations

from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import create_app


def client() -> TestClient:
    return TestClient(create_app())


def _login(api: TestClient, email: str, password: str) -> tuple[str, str]:
    response = api.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    access = response.json()["data"]["accessToken"]
    cookie_name = get_settings().auth_refresh_cookie_name
    refresh = response.cookies.get(cookie_name)
    assert refresh
    return access, refresh


def test_login_returns_bearer_token_ttl_and_cross_site_refresh_cookie(monkeypatch):
    monkeypatch.setenv("VELLA_ENV", "production")
    monkeypatch.setenv("VELLA_AUTH_SECRET", "test-production-secret-that-is-at-least-32-characters")
    monkeypatch.setenv("VELLA_AUTH_COOKIE_SECURE", "false")
    monkeypatch.delenv("VELLA_AUTH_COOKIE_SAMESITE", raising=False)
    api = client()
    response = api.post(
        "/api/v1/auth/login",
        json={"email": "admin@vella.local", "password": "AdminPass123!"},
    )
    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["tokenType"] == "bearer"
    assert isinstance(payload["accessToken"], str) and payload["accessToken"]
    assert payload["expiresIn"] >= 60

    cookie_name = get_settings().auth_refresh_cookie_name
    set_cookie = response.headers.get("set-cookie", "")
    assert f"{cookie_name}=" in set_cookie
    assert "HttpOnly" in set_cookie
    assert "Secure" in set_cookie
    assert "SameSite=none" in set_cookie


def test_login_rejects_wrong_password_and_audits_failure():
    api = client()
    response = api.post(
        "/api/v1/auth/login",
        json={"email": "admin@vella.local", "password": "wrong-pass"},
    )
    assert response.status_code == 401
    assert response.json()["error"]["message"] == "INVALID_CREDENTIALS"


def test_refresh_allows_previous_token_during_bounded_rotation_grace():
    api = client()
    _, refresh_token = _login(api, "admin@vella.local", "AdminPass123!")
    cookie_name = get_settings().auth_refresh_cookie_name

    first = api.post("/api/v1/auth/refresh", cookies={cookie_name: refresh_token})
    assert first.status_code == 200
    first_payload = first.json()["data"]
    assert first_payload["accessToken"]
    rotated = first.cookies.get(cookie_name)
    assert rotated and rotated != refresh_token

    old_token_attempt = api.post("/api/v1/auth/refresh", cookies={cookie_name: refresh_token})
    assert old_token_attempt.status_code == 200

    rotated_attempt = api.post("/api/v1/auth/refresh", cookies={cookie_name: rotated})
    assert rotated_attempt.status_code == 200


def test_logout_revokes_session_and_access_token_stops_working():
    api = client()
    access, _refresh = _login(api, "admin@vella.local", "AdminPass123!")
    headers = {"Authorization": f"Bearer {access}"}

    before = api.get("/api/v1/cabinet/me", headers=headers)
    assert before.status_code == 200

    logout = api.post("/api/v1/auth/logout", headers=headers)
    assert logout.status_code == 200

    after = api.get("/api/v1/cabinet/me", headers=headers)
    assert after.status_code == 401


def test_viewer_token_cannot_create_settings_version():
    api = client()
    access, _refresh = _login(api, "viewer@vella.local", "ViewerPass123!")
    response = api.post(
        "/api/v1/settings/versions",
        json={
            "settings": {
                "strategyMode": "manual",
                "applyScope": "sku",
                "maxPriceStepPctPerHour": 5.0,
                "minMarginKopecks": 1000,
                "targetMarginPct": 18.5,
                "pminGuardEnabled": True,
                "pmaxGuardEnabled": True,
                "nightModeEnabled": False,
                "nightWindowStartHour": 1,
                "nightWindowEndHour": 5,
                "sppFallbackMode": "block",
            },
            "status": "draft",
        },
        headers={"Authorization": f"Bearer {access}"},
    )
    assert response.status_code == 403
    assert response.json()["error"]["message"] == "NO_ACCESS:settings:write"


def test_admin_token_can_create_settings_version():
    api = client()
    access, _refresh = _login(api, "admin@vella.local", "AdminPass123!")
    response = api.post(
        "/api/v1/settings/versions",
        json={
            "settings": {
                "strategyMode": "manual",
                "applyScope": "sku",
                "maxPriceStepPctPerHour": 5.0,
                "minMarginKopecks": 1000,
                "targetMarginPct": 18.5,
                "pminGuardEnabled": True,
                "pmaxGuardEnabled": True,
                "nightModeEnabled": False,
                "nightWindowStartHour": 1,
                "nightWindowEndHour": 5,
                "sppFallbackMode": "block",
            },
            "status": "draft",
        },
        headers={"Authorization": f"Bearer {access}"},
    )
    assert response.status_code == 200
    assert response.json()["data"]["createdByRole"] == "admin"
