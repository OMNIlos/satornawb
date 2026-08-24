from __future__ import annotations

from typing import Any

try:
    import httpx
except ImportError:  # pragma: no cover - optional dependency guard
    httpx = None


class LiveAvitoPriceClient:
    def __init__(self, access_token: str, base_url: str = "https://api.avito.ru", timeout_seconds: float = 20.0) -> None:
        self.access_token = access_token
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    def update_price(self, item_id: str, price_kopecks: int, http_client: Any | None = None) -> dict[str, Any]:
        if not item_id:
            raise ValueError("AVITO_ITEM_ID_REQUIRED")
        price_rubles = max(0, int(round(price_kopecks / 100)))
        client = http_client
        owns_client = client is None
        if client is None:
            if httpx is None:
                raise RuntimeError("httpx is required for LiveAvitoPriceClient")
            client = httpx.Client(timeout=self.timeout_seconds)
        try:
            response = client.post(
                f"{self.base_url}/core/v1/items/{item_id}/update_price",
                json={"price": price_rubles},
                headers={
                    "Authorization": f"Bearer {self.access_token}",
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
            )
            response.raise_for_status()
            payload = response.json() if hasattr(response, "json") else {}
            return {"status": "sent", "itemId": item_id, "priceKopecks": price_kopecks, "priceRubles": price_rubles, "response": payload}
        finally:
            if owns_client and hasattr(client, "close"):
                client.close()
