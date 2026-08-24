from app.avito.price_apply import LiveAvitoPriceClient


class _AvitoPriceHttpResponse:
    def __init__(self, payload=None, status_code=200):
        self._payload = payload or {"ok": True}
        self.status_code = status_code

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError("http error")


class _RecordingAvitoPriceHttpClient:
    def __init__(self):
        self.posts = []

    def post(self, url, **kwargs):
        self.posts.append({"url": url, **kwargs})
        return _AvitoPriceHttpResponse()


def test_live_avito_price_client_posts_update_price_in_rubles():
    http_client = _RecordingAvitoPriceHttpClient()
    client = LiveAvitoPriceClient(access_token="token", base_url="https://api.avito.ru")

    result = client.update_price("8098482225", 514500, http_client=http_client)

    assert result["status"] == "sent"
    assert http_client.posts[0]["url"] == "https://api.avito.ru/core/v1/items/8098482225/update_price"
    assert http_client.posts[0]["json"] == {"price": 5145}
    assert http_client.posts[0]["headers"]["Authorization"] == "Bearer token"
