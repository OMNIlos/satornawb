from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from pydantic import BaseModel, Field

from app.cabinet.store import AvitoCredentialsSecret, cache_user_avito_access_token

try:
    import httpx
except ImportError:  # pragma: no cover - optional dependency guard
    httpx = None


class AvitoOAuthToken(BaseModel):
    accessToken: str = Field(min_length=1)
    tokenType: str = "Bearer"
    expiresAt: datetime


class AvitoOAuthClient:
    def __init__(self, base_url: str = "https://api.avito.ru", timeout_seconds: float = 20.0) -> None:
        if httpx is None:
            raise RuntimeError("httpx is required for AvitoOAuthClient")
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    def fetch_client_credentials_token(self, client_id: str, client_secret: str) -> AvitoOAuthToken:
        response = httpx.post(
            f"{self.base_url}/token",
            data={
                "grant_type": "client_credentials",
                "client_id": client_id,
                "client_secret": client_secret,
            },
            headers={"Accept": "application/json"},
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        payload: Any = response.json()
        access_token = str(payload.get("access_token") or "")
        expires_in = int(payload.get("expires_in") or 86_400)
        token_type = str(payload.get("token_type") or "Bearer")
        if not access_token:
            raise ValueError("AVITO_OAUTH_TOKEN_EMPTY")
        return AvitoOAuthToken(
            accessToken=access_token,
            tokenType=token_type,
            expiresAt=datetime.now(timezone.utc) + timedelta(seconds=max(60, expires_in - 60)),
        )


def _token_is_fresh(expires_at: datetime | None) -> bool:
    if expires_at is None:
        return False
    now = datetime.now(timezone.utc)
    comparable = expires_at if expires_at.tzinfo else expires_at.replace(tzinfo=timezone.utc)
    return comparable > now + timedelta(minutes=5)


def resolve_user_avito_access_token(
    *,
    user_id: str,
    credentials: AvitoCredentialsSecret,
    base_url: str,
    timeout_seconds: float,
) -> str:
    if credentials.cached_access_token and _token_is_fresh(credentials.access_token_expires_at):
        return credentials.cached_access_token
    token = AvitoOAuthClient(base_url=base_url, timeout_seconds=timeout_seconds).fetch_client_credentials_token(
        credentials.client_id,
        credentials.client_secret,
    )
    cache_user_avito_access_token(user_id, token.accessToken, token.expiresAt)
    return token.accessToken
