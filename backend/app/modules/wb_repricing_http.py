"""Dormant bounded WB price transport. No scheduling, retry or outcome mutation.

Bootstrap must provide an account-wide durable quota admission callback and use
this POST only via DurableApprovalWorker's committed dispatch/before-I/O guard.
Admission is pacing, not authorization. The adapter cannot prove caller authority.
Official method contracts checked 2026-09-10: dev.wildberries.ru/docs/openapi/item-management.
"""

import json
import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from hashlib import sha256

import httpx

from app.modules.wb_repricing_dispatch import CanonicalApplyRequest
from app.modules.wb_repricing_worker import OriginalPricePostResponse
from app.platform.integrations.credential_store import ResolvedCredentialForFetch
from app.platform.integrations.repricer_job_contract import (
    integer,
    timestamp,
    upload_id,
)
from app.wb_live.provider import _retry_after


class PriceHttpError(ValueError):
    def __init__(self, *, next_not_before=None):
        self.next_not_before = next_not_before
        super().__init__("WB_PRICE_HTTP_UNAVAILABLE")


def _pairs(items):
    result = {}
    for key, value in items:
        if key in result:
            raise PriceHttpError()
        result[key] = value
    return result


def _invalid(value):
    raise PriceHttpError()


def _json(raw):
    try:
        return json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_pairs,
            parse_constant=_invalid,
            parse_float=_invalid,
        )
    except (ValueError, UnicodeError, RecursionError):
        pass
    raise PriceHttpError()


def _number(value, minimum=0):
    if type(value) is not int or value < minimum:
        raise PriceHttpError()
    return value


@dataclass(frozen=True, slots=True, repr=False)
class HistoryState:
    upload_id: str
    status: int
    total: int
    succeeded: int


@dataclass(frozen=True, slots=True, repr=False)
class HistoryGood:
    nm_id: int
    size_id: int | None
    article_id: str
    price_rubles: int | None
    discount_pct: int
    currency: str
    status: int
    has_error: bool


@dataclass(frozen=True, slots=True, repr=False)
class HistoryPage:
    upload_id: str
    offset: int
    limit: int
    goods: tuple[HistoryGood, ...]


@dataclass(frozen=True, slots=True, repr=False)
class HistoryObservation:
    organization_id: int
    marketplace_account_id: int
    path: str
    observed_at: datetime
    next_not_before: datetime
    raw_checksum: str
    result: HistoryState | HistoryPage


def matches_single_product_application(
    request, state_observation, goods_observation, *, receipt_upload_id
):
    """Strict positive evidence for the supported one-product operation only.

    False means insufficient/conflicting evidence, NEVER proof of nonacceptance.
    No domain transition: caller must persist evidence under the closing guard.
    """
    upload_id(receipt_upload_id)
    if type(request) is not CanonicalApplyRequest:
        raise PriceHttpError()
    if (
        type(state_observation) is not HistoryObservation
        or type(goods_observation) is not HistoryObservation
    ):
        raise PriceHttpError()
    for observation in (state_observation, goods_observation):
        if (observation.organization_id, observation.marketplace_account_id) != (
            request.scope.organization_id,
            request.scope.marketplace_account_id,
        ):
            raise PriceHttpError()
    state, page = state_observation.result, goods_observation.result
    if (
        type(state) is not HistoryState
        or type(page) is not HistoryPage
        or state_observation.path != "/api/v2/history/tasks"
        or goods_observation.path != "/api/v2/history/goods/task"
        or state.upload_id != page.upload_id
        or state.upload_id != receipt_upload_id
    ):
        raise PriceHttpError()
    if (
        request.size_id is not None
        or request.min_price_kopecks is not None
        or state.status != 3
        or (state.total, state.succeeded) != (1, 1)
        or page.offset != 0
        or page.limit <= 1
        or len(page.goods) != 1
    ):
        return False
    row = page.goods[0]
    expected = _json(request.provider_bytes)["data"][0]
    return (
        row.status == 2
        and not row.has_error
        and row.currency == "RUB"
        and row.size_id is None
        and row.nm_id == request.nm_id
        and row.article_id == request.article_id
        and row.price_rubles == expected["price"]
        and row.discount_pct == request.discount_pct
    )


def parse_history(raw, *, expected_upload_id, path, offset=0, limit=1000):
    """Identity-bound evidence only, never an applied decision or resend permit."""
    upload_id(expected_upload_id)
    data = _json(raw)
    if (
        type(data) is not dict
        or data.get("error", False) is not False
        or data.get("errorText", "") != ""
    ):
        raise PriceHttpError()
    data = data.get("data")
    if (
        type(data) is not dict
        or type(data.get("uploadID")) is not int
        or str(data["uploadID"]) != expected_upload_id
    ):
        raise PriceHttpError()
    if path == "/api/v2/history/tasks":
        status = _number(data.get("status"))
        total, succeeded = (
            _number(data.get("overAllGoodsNumber")),
            _number(data.get("successGoodsNumber")),
        )
        if status not in (3, 4, 5, 6) or succeeded > total:
            raise PriceHttpError()
        return HistoryState(expected_upload_id, status, total, succeeded)
    if (
        path != "/api/v2/history/goods/task"
        or type(limit) is not int
        or not 1 <= limit <= 1000
    ):
        raise PriceHttpError()
    _number(offset)
    rows = data.get("historyGoods")
    if type(rows) is not list or len(rows) > limit:
        raise PriceHttpError()
    goods, seen = [], set()
    for row in rows:
        if type(row) is not dict:
            raise PriceHttpError()
        nm = _number(row.get("nmID"), 1)
        size = row.get("sizeID")
        if size is not None:
            _number(size, 1)
        if (nm, size) in seen:
            raise PriceHttpError()
        seen.add((nm, size))
        price = row.get("price")
        if price is not None:
            _number(price, 1)
        discount, status = _number(row.get("discount")), _number(row.get("status"))
        article, currency, error = (
            row.get("vendorCode"),
            row.get("currencyIsoCode4217"),
            row.get("errorText"),
        )
        if (
            discount > 99
            or status not in (2, 3)
            or type(article) is not str
            or not article.strip()
            or currency != "RUB"
            or (error is not None and type(error) is not str)
        ):
            raise PriceHttpError()
        if status == 2 and error not in (None, ""):
            raise PriceHttpError()
        goods.append(
            HistoryGood(
                nm,
                size,
                article,
                price,
                discount,
                currency,
                status,
                bool(error) or status == 3,
            )
        )
    return HistoryPage(expected_upload_id, offset, limit, tuple(goods))


class WbPriceHttpAdapter:
    def __init__(
        self,
        *,
        organization_id,
        marketplace_account_id,
        admit_request,
        max_response_bytes,
        transport=None,
        clock=None,
    ):
        integer(organization_id)
        integer(marketplace_account_id)
        if (
            not callable(admit_request)
            or type(max_response_bytes) is not int
            or not 1 <= max_response_bytes <= 4 * 1024 * 1024
        ):
            raise PriceHttpError()
        self._org, self._account = organization_id, marketplace_account_id
        self._admit, self._budget, self._transport = (
            admit_request,
            max_response_bytes,
            transport,
        )
        self._clock = clock or (lambda: datetime.now(UTC))

    def _request(self, *, method, path, credential, body=None, params=None):
        if type(credential) is not ResolvedCredentialForFetch or (
            credential.binding.owner.organization_id,
            credential.binding.owner.marketplace_account_id,
            credential.binding.owner.provider,
            credential.binding.credential_identity.credential_kind,
        ) != (self._org, self._account, "wb", "wb_api"):
            raise PriceHttpError()
        # Reserve the shared category budget BEFORE I/O, even if the process dies.
        # Conservative base entitlement; no JWT decoding or in-memory limiter.
        if self._admit(self._org, self._account, method, path, 900) is not True:
            raise PriceHttpError()
        result = None
        try:
            with httpx.Client(
                transport=self._transport,
                timeout=httpx.Timeout(20, connect=10),
                trust_env=False,
                follow_redirects=False,
            ) as client:
                started = time.monotonic()
                with client.stream(
                    method,
                    "https://discounts-prices-api.wildberries.ru" + path,
                    content=body,
                    params=params,
                    headers={
                        "Authorization": credential.secret.reveal()["token"],
                        "Accept": "application/json",
                        "Content-Type": "application/json",
                    },
                ) as response:
                    raw = bytearray()
                    for chunk in response.iter_bytes(chunk_size=16384):
                        if (
                            len(raw) + len(chunk) > self._budget
                            or time.monotonic() - started > 30
                        ):
                            raise PriceHttpError()
                        raw.extend(chunk)
                    if time.monotonic() - started > 30:
                        raise PriceHttpError()
                    now = timestamp(self._clock())
                    result = (
                        bytes(raw),
                        response.status_code,
                        now,
                        max(900, _retry_after(response.headers, now)),
                    )
        except Exception:  # noqa: BLE001 -- do not retain transport request/headers or raw exception context.
            result = None
        if result is None:
            raise PriceHttpError()
        return result

    def post_price_once(self, *, body, credential):
        if type(body) is not bytes or not 1 <= len(body) <= 4096:
            raise PriceHttpError()
        payload = _json(body)
        if (
            type(payload) is not dict
            or set(payload) != {"data"}
            or type(payload["data"]) is not list
            or len(payload["data"]) != 1
        ):
            raise PriceHttpError()
        row = payload["data"][0]
        # Existing kernel can encode size/minPrice, but this endpoint cannot be
        # assumed to honor them. Never strip them or silently reroute the intent.
        if type(row) is not dict or set(row) != {"nmID", "price", "discount"}:
            raise PriceHttpError()
        _number(row["nmID"], 1)
        _number(row["price"], 1)
        if _number(row["discount"]) > 99:
            raise PriceHttpError()
        raw, status, now, _ = self._request(
            method="POST", path="/api/v2/upload/task", credential=credential, body=body
        )
        return OriginalPricePostResponse(raw, status, 200 <= status < 300, now)

    def read_history_once(
        self, *, credential, expected_upload_id, details=False, offset=0, limit=1000
    ):
        upload_id(expected_upload_id)
        if (
            type(details) is not bool
            or type(limit) is not int
            or not 1 <= limit <= 1000
        ):
            raise PriceHttpError()
        _number(offset)
        path = "/api/v2/history/goods/task" if details else "/api/v2/history/tasks"
        params = {"uploadID": expected_upload_id}
        if details:
            params.update(offset=offset, limit=limit)
        raw, status, now, delay = self._request(
            method="GET", path=path, credential=credential, params=params
        )
        if status != 200:
            raise PriceHttpError(next_not_before=now + timedelta(seconds=delay))
        result = parse_history(
            raw,
            expected_upload_id=expected_upload_id,
            path=path,
            offset=offset,
            limit=limit,
        )
        return HistoryObservation(
            self._org,
            self._account,
            path,
            now,
            now + timedelta(seconds=delay),
            sha256(raw).hexdigest(),
            result,
        )
