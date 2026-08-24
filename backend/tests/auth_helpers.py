from __future__ import annotations

from fastapi.testclient import TestClient


PROFILE_CREDENTIALS = {
    "viewer": ("viewer@vella.local", "ViewerPass123!"),
    "settings_editor": ("editor@vella.local", "EditorPass123!"),
    "price_sender": ("sender@vella.local", "SenderPass123!"),
    "finance_viewer": ("finance@vella.local", "FinancePass123!"),
    "admin": ("admin@vella.local", "AdminPass123!"),
}


def auth_headers(client: TestClient, profile: str) -> dict[str, str]:
    email, password = PROFILE_CREDENTIALS[profile]
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    token = response.json()["data"]["accessToken"]
    return {"Authorization": f"Bearer {token}"}
