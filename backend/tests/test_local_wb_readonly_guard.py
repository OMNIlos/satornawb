import importlib.util
from pathlib import Path

import httpx
import pytest

spec = importlib.util.spec_from_file_location(
    "local_wb_readonly", Path(__file__).parents[1] / "ops/load_local_wb_readonly.py"
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


@pytest.mark.parametrize("method,host,path", sorted(module.ALLOWED))
def test_explicit_reads_allowed(method, host, path):
    assert module.allowed_request(httpx.Request(method, f"https://{host}{path}"))


@pytest.mark.parametrize("method,url", [
    ("POST", "https://discounts-prices-api.wildberries.ru/api/v2/upload/task"),
    ("DELETE", "https://content-api.wildberries.ru/content/v2/get/cards/list"),
    ("GET", "https://example.com/api/v2/list/goods/filter"),
    ("GET", "http://discounts-prices-api.wildberries.ru/api/v2/list/goods/filter"),
    ("GET", "https://discounts-prices-api.wildberries.ru:444/api/v2/list/goods/filter"),
])
def test_writes_and_unapproved_destinations_denied(method, url):
    assert not module.allowed_request(httpx.Request(method, url))
