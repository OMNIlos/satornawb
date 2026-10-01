"""Opt-in local Avito OAuth and read endpoints. Provider mutations stay denied."""
import re
from urllib.parse import parse_qs


READ_PATHS = (
    r"/core/v1/accounts/self",
    r"/core/v1/items",
    r"/core/v1/items/[0-9]+/?",
    r"/core/v1/accounts/[0-9]+/items/[0-9]+/?",
    r"/order-management/1/orders",
    r"/ratings/v1/(?:info|reviews)",
    r"/messenger/v2/accounts/[0-9]+/chats",
    r"/messenger/v3/accounts/[0-9]+/chats/[A-Za-z0-9_~-]+/messages/?",
)


def allowed_request(request):
    url = request.url
    # Product images used by the offline picking workbook. Never carry account
    # credentials to the CDN, follow redirects, or allow arbitrary hosts.
    if (request.method == "GET" and url.scheme == "https" and url.port in (None, 443)
            and not url.username and not url.password
            and re.fullmatch(r"(?:[0-9]+\.)?img\.avito\.st", url.host)
            and "authorization" not in request.headers and "cookie" not in request.headers):
        return True
    if (url.scheme != "https" or url.host != "api.avito.ru"
            or url.port not in (None, 443) or url.username or url.password):
        return False
    if request.method == "GET":
        return any(re.fullmatch(pattern, url.path) for pattern in READ_PATHS)
    if request.method != "POST":
        return False
    if url.path == "/token":
        try:
            body = parse_qs(request.content.decode("utf-8"))
        except (ValueError, UnicodeError):
            return False
        return body.get("grant_type") == ["client_credentials"]
    # POST is the existing read-only statistics query, not a price/order action.
    return re.fullmatch(r"/stats/v2/accounts/[0-9]+/items", url.path) is not None
