import json
from types import SimpleNamespace

from app.avito.orders import AvitoOrdersBrowserSnapshot
from app.avito.orders_ai import enrich_avito_orders_snapshot_with_ai


class FakeResponse:
    def __init__(self, output: dict):
        self.output = output

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return {
            "output": [
                {
                    "type": "message",
                    "content": [{"type": "output_text", "text": json.dumps(self.output, ensure_ascii=False)}],
                }
            ]
        }


class RecordingClient:
    base_url = "https://api.openai.com/v1"

    def __init__(self, output: dict):
        self.output = output
        self.posts: list[dict] = []

    def post(self, url: str, **kwargs):
        self.posts.append({"url": url, **kwargs})
        return FakeResponse(self.output)


def snapshot_with_two_sizes() -> AvitoOrdersBrowserSnapshot:
    return AvitoOrdersBrowserSnapshot.model_validate(
        {
            "collector": {
                "options": {
                    "sizeMode": "chat_ai",
                    "colorFromDescription": False,
                    "articleFromDescription": False,
                }
            },
            "orders": [
                {
                    "orderId": "order-1",
                    "items": [
                        {
                            "title": "Свитшот",
                            "chatText": "Сначала M\nНет, тогда L\nДа, фиксируем L",
                            "descriptionSize": "54 (XL)",
                        },
                        {
                            "title": "Футболка",
                            "chatText": "Какой размер есть?",
                            "descriptionSize": "46 (M)",
                        },
                    ],
                }
            ],
        }
    )


def settings(api_key: str | None):
    return SimpleNamespace(
        openai_api_key=api_key,
        openai_api_base_url="https://api.openai.com/v1",
        openai_review_model="gpt-4o-mini",
        openai_review_timeout_seconds=20.0,
    )


def test_ai_size_wins_and_all_items_use_one_request(monkeypatch):
    monkeypatch.setattr("app.avito.orders_ai.get_settings", lambda: settings("test-key"))
    client = RecordingClient(
        {
            "items": [
                {
                    "key": "0:0",
                    "size": "L",
                    "color": None,
                    "sellerArticle": None,
                    "confidence": "high",
                    "notes": "final confirmation",
                },
                {
                    "key": "0:1",
                    "size": "S",
                    "color": None,
                    "sellerArticle": None,
                    "confidence": "low",
                    "notes": "uncertain guess",
                },
            ]
        }
    )

    snapshot, meta = enrich_avito_orders_snapshot_with_ai(snapshot_with_two_sizes(), client=client)

    assert len(client.posts) == 1
    assert snapshot.orders[0].items[0].size == "L"
    assert snapshot.orders[0].items[0].sources["size"] == "chat_ai"
    assert snapshot.orders[0].items[1].size == "46 (M)"
    assert snapshot.orders[0].items[1].sources["size"] == "description_fallback"
    assert meta["aiSizeCount"] == 1
    assert meta["descriptionFallbackCount"] == 1
    assert meta["missingFinalSizeCount"] == 0


def test_missing_openai_key_still_applies_description_fallback(monkeypatch):
    monkeypatch.setattr("app.avito.orders_ai.get_settings", lambda: settings(None))
    snapshot = snapshot_with_two_sizes()

    enriched, meta = enrich_avito_orders_snapshot_with_ai(snapshot)

    assert [item.size for item in enriched.orders[0].items] == ["54 (XL)", "46 (M)"]
    assert meta["status"] == "skipped"
    assert meta["descriptionFallbackCount"] == 2
    assert meta["missingFinalSizeCount"] == 0


class FailingClient:
    base_url = "https://api.openai.com/v1"

    def post(self, *_args, **_kwargs):
        raise TimeoutError("timeout")


def test_failed_ai_request_still_applies_description_fallback(monkeypatch):
    monkeypatch.setattr("app.avito.orders_ai.get_settings", lambda: settings("test-key"))
    enriched, meta = enrich_avito_orders_snapshot_with_ai(snapshot_with_two_sizes(), client=FailingClient())

    assert [item.size for item in enriched.orders[0].items] == ["54 (XL)", "46 (M)"]
    assert meta["status"] == "failed"
    assert meta["descriptionFallbackCount"] == 2


class MalformedResponse:
    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return {"output": []}


class MalformedClient:
    base_url = "https://api.openai.com/v1"

    def post(self, *_args, **_kwargs):
        return MalformedResponse()


def test_malformed_ai_output_still_applies_description_fallback(monkeypatch):
    monkeypatch.setattr("app.avito.orders_ai.get_settings", lambda: settings("test-key"))
    enriched, meta = enrich_avito_orders_snapshot_with_ai(snapshot_with_two_sizes(), client=MalformedClient())

    assert [item.size for item in enriched.orders[0].items] == ["54 (XL)", "46 (M)"]
    assert meta["status"] == "failed"
    assert meta["descriptionFallbackCount"] == 2
