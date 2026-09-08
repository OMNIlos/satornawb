from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any

from app.platform.period import Period

_ENDPOINT = "POST /api/analytics/v3/sales-funnel/products/history"
_NORMALIZER_VERSION = "wb-funnel-history-v1"
_SECRET_KEY_PARTS = ("token", "authorization", "secret")
_COUNT_FIELDS = {
    "open_count": "openCount",
    "cart_count": "cartCount",
    "order_count": "orderCount",
    "buyout_count": "buyoutCount",
    "add_to_wishlist_count": "addToWishlistCount",
}
_MONEY_FIELDS = {
    "order_amount_kopecks": "orderSum",
    "buyout_amount_kopecks": "buyoutSum",
}


class FunnelNormalizationError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class RawFunnelDailyFact:
    source_identity: str
    payload_checksum: str
    business_date: date
    nm_id: int
    currency: str | None
    open_count: int | None
    cart_count: int | None
    order_count: int | None
    order_amount_kopecks: int | None
    buyout_count: int | None
    buyout_amount_kopecks: int | None
    add_to_wishlist_count: int | None


@dataclass(frozen=True, slots=True)
class RawFunnelEvidence:
    facts: tuple[RawFunnelDailyFact, ...]
    raw_manifest: list[dict[str, Any]]
    raw_manifest_checksum: str
    snapshot_checksum: str


def normalize_raw_funnel(period: Period, bundle: dict[str, Any]) -> RawFunnelEvidence:
    if not isinstance(bundle, dict):
        raise FunnelNormalizationError("invalid funnel bundle")
    _validate_period(period, bundle.get("period"))
    pages = bundle.get("pages")
    if not isinstance(pages, list) or not pages:
        raise FunnelNormalizationError("funnel pages are incomplete")
    manifest = _canonical_manifest(bundle.get("manifest"))
    if len(manifest) != len(pages):
        raise FunnelNormalizationError("funnel manifest is incomplete")

    manifest_by_request: dict[str, dict[str, Any]] = {}
    for item in manifest:
        if (
            not isinstance(item, dict)
            or item.get("endpoint") != _ENDPOINT
            or item.get("statusCode") != 200
            or item.get("ok") is not True
        ):
            raise FunnelNormalizationError("funnel manifest is incomplete")
        request = _request(period, item.get("request"))
        key = _json(request)
        if key in manifest_by_request:
            raise FunnelNormalizationError("funnel manifest is ambiguous")
        checksum = item.get("responseChecksum")
        if not isinstance(checksum, str) or len(checksum) != 64:
            raise FunnelNormalizationError("invalid funnel manifest checksum")
        manifest_by_request[key] = item

    facts: list[RawFunnelDailyFact] = []
    seen_requests: set[str] = set()
    for page in pages:
        if not isinstance(page, dict):
            raise FunnelNormalizationError("invalid funnel page")
        request = _request(period, page.get("request"))
        request_key = _json(request)
        manifest_item = manifest_by_request.get(request_key)
        if manifest_item is None or request_key in seen_requests:
            raise FunnelNormalizationError("funnel manifest does not match pages")
        seen_requests.add(request_key)
        payload = page.get("payload")
        if manifest_item["responseChecksum"] != _response_checksum(payload):
            raise FunnelNormalizationError("funnel response checksum mismatch")
        requested_ids = set(request["nmIds"])
        facts.extend(_facts(period, payload, requested_ids))
    if seen_requests != set(manifest_by_request):
        raise FunnelNormalizationError("funnel manifest does not match pages")

    deduplicated = _dedupe(facts)
    logical_manifest = [
        {key: value for key, value in item.items() if key != "wbRequestId"}
        for item in manifest
    ]
    return RawFunnelEvidence(
        facts=deduplicated,
        raw_manifest=manifest,
        raw_manifest_checksum=_hash(manifest),
        snapshot_checksum=_hash(
            {
                "normalizerVersion": _NORMALIZER_VERSION,
                "period": {
                    "dateFrom": period.date_from,
                    "dateTo": period.date_to,
                },
                "facts": deduplicated,
                "logicalManifestChecksum": _hash(logical_manifest),
            }
        ),
    )


def _validate_period(period: Period, payload: Any) -> None:
    if (period.date_to - period.date_from).days >= 7:
        raise FunnelNormalizationError("invalid funnel period")
    if not isinstance(payload, dict):
        raise FunnelNormalizationError("invalid funnel period")
    try:
        actual = (
            date.fromisoformat(str(payload["dateFrom"])),
            date.fromisoformat(str(payload["dateTo"])),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise FunnelNormalizationError("invalid funnel period") from exc
    if actual != (period.date_from, period.date_to):
        raise FunnelNormalizationError("funnel period mismatch")


def _request(period: Period, payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict) or set(payload) != {
        "selectedPeriod",
        "nmIds",
        "skipDeletedNm",
        "aggregationLevel",
    }:
        raise FunnelNormalizationError("invalid funnel request")
    selected_period = payload.get("selectedPeriod")
    if not isinstance(selected_period, dict) or set(selected_period) != {"start", "end"}:
        raise FunnelNormalizationError("invalid funnel request period")
    if selected_period != {
        "start": period.date_from.isoformat(),
        "end": period.date_to.isoformat(),
    }:
        raise FunnelNormalizationError("funnel request period mismatch")
    nm_ids = payload.get("nmIds")
    if (
        not isinstance(nm_ids, list)
        or not 1 <= len(nm_ids) <= 20
        or any(not _is_positive_integer(value) for value in nm_ids)
        or nm_ids != sorted(set(nm_ids))
        or payload.get("skipDeletedNm") is not False
        or payload.get("aggregationLevel") != "day"
    ):
        raise FunnelNormalizationError("invalid funnel request")
    return json.loads(_json(payload))


def _facts(
    period: Period, payload: Any, requested_ids: set[int]
) -> list[RawFunnelDailyFact]:
    if isinstance(payload, list):
        products = payload
    elif isinstance(payload, dict) and set(payload) == {"data"} and isinstance(payload["data"], list):
        products = payload["data"]
    else:
        raise FunnelNormalizationError("invalid funnel response payload")

    facts: list[RawFunnelDailyFact] = []
    for item in products:
        if not isinstance(item, dict):
            raise FunnelNormalizationError("invalid funnel product")
        product = item.get("product")
        history = item.get("history")
        if not isinstance(product, dict) or not isinstance(history, list):
            raise FunnelNormalizationError("invalid funnel product")
        nm_id = _positive_integer(product.get("nmId"), "nmId")
        if nm_id not in requested_ids:
            raise FunnelNormalizationError("funnel product was not requested")
        currency = _currency(item.get("currency"))
        for row in history:
            facts.append(_fact(period, nm_id, currency, row))
    return facts


def _fact(
    period: Period, nm_id: int, currency: str | None, row: Any
) -> RawFunnelDailyFact:
    if not isinstance(row, dict):
        raise FunnelNormalizationError("invalid funnel history row")
    try:
        business_date = date.fromisoformat(str(row["date"]))
    except (KeyError, TypeError, ValueError) as exc:
        raise FunnelNormalizationError("invalid funnel business date") from exc
    if not period.date_from <= business_date <= period.date_to:
        raise FunnelNormalizationError("funnel business date is outside period")

    values = {
        field: _nullable_count(row.get(source), source)
        for field, source in _COUNT_FIELDS.items()
    }
    values.update(
        {
            field: _nullable_money(row.get(source), source)
            for field, source in _MONEY_FIELDS.items()
        }
    )
    if all(value is None for value in values.values()):
        raise FunnelNormalizationError("funnel history row has no metrics")
    source_identity = f"funnel-history-v1|{business_date.isoformat()}|{nm_id}"
    payload = {
        "source_identity": source_identity,
        "business_date": business_date,
        "nm_id": nm_id,
        "currency": currency,
        **values,
    }
    return RawFunnelDailyFact(
        source_identity=source_identity,
        payload_checksum=_hash(payload),
        business_date=business_date,
        nm_id=nm_id,
        currency=currency,
        **values,
    )


def _nullable_count(raw: Any, field: str) -> int | None:
    if raw is None:
        return None
    if isinstance(raw, bool) or not isinstance(raw, int) or raw < 0:
        raise FunnelNormalizationError(f"invalid {field}")
    return raw


def _nullable_money(raw: Any, field: str) -> int | None:
    if raw is None:
        return None
    if isinstance(raw, bool) or not isinstance(raw, (int, float, str, Decimal)):
        raise FunnelNormalizationError(f"invalid {field}")
    try:
        value = Decimal(str(raw))
    except InvalidOperation as exc:
        raise FunnelNormalizationError(f"invalid {field}") from exc
    kopecks = value * 100
    if not value.is_finite() or value < 0 or kopecks != kopecks.to_integral_value():
        raise FunnelNormalizationError(f"invalid {field}")
    return int(kopecks)


def _currency(raw: Any) -> str | None:
    if raw is None:
        return None
    if not isinstance(raw, str) or len(raw) != 3 or not raw.isalpha() or raw != raw.upper():
        raise FunnelNormalizationError("invalid funnel currency")
    return raw


def _is_positive_integer(raw: Any) -> bool:
    return isinstance(raw, int) and not isinstance(raw, bool) and raw > 0


def _positive_integer(raw: Any, field: str) -> int:
    if not _is_positive_integer(raw):
        raise FunnelNormalizationError(f"invalid {field}")
    return raw


def _dedupe(facts: list[RawFunnelDailyFact]) -> tuple[RawFunnelDailyFact, ...]:
    unique: dict[str, RawFunnelDailyFact] = {}
    for fact in facts:
        previous = unique.get(fact.source_identity)
        if previous is not None and previous.payload_checksum != fact.payload_checksum:
            raise FunnelNormalizationError("conflicting funnel source identity")
        unique[fact.source_identity] = fact
    return tuple(sorted(unique.values(), key=lambda fact: fact.source_identity))


def _canonical_manifest(manifest: Any) -> list[dict[str, Any]]:
    if not isinstance(manifest, list) or not manifest:
        raise FunnelNormalizationError("funnel manifest is missing")
    if _contains_secret_key(manifest):
        raise FunnelNormalizationError("funnel manifest contains forbidden key")
    try:
        copied = json.loads(_json(manifest))
    except (TypeError, ValueError) as exc:
        raise FunnelNormalizationError("funnel manifest is invalid") from exc
    return sorted(copied, key=_json)


def _contains_secret_key(value: Any) -> bool:
    if isinstance(value, dict):
        return any(
            any(part in str(key).casefold() for part in _SECRET_KEY_PARTS)
            or _contains_secret_key(item)
            for key, item in value.items()
        )
    if isinstance(value, (list, tuple)):
        return any(_contains_secret_key(item) for item in value)
    return False


def _response_checksum(payload: Any) -> str:
    try:
        return hashlib.sha256(_json(_canonical_response(payload)).encode()).hexdigest()
    except (TypeError, ValueError) as exc:
        raise FunnelNormalizationError("invalid funnel response payload") from exc


def _canonical_response(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _canonical_response(item) for key, item in value.items()}
    if isinstance(value, list):
        items = [_canonical_response(item) for item in value]
        return sorted(items, key=_json)
    return value


def _hash(payload: Any) -> str:
    return hashlib.sha256(_json(payload).encode()).hexdigest()


def _json(payload: Any) -> str:
    return json.dumps(
        _jsonable(payload),
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def _jsonable(value: Any) -> Any:
    if isinstance(value, date):
        return value.isoformat()
    if hasattr(value, "__dataclass_fields__"):
        return _jsonable(asdict(value))
    if isinstance(value, tuple):
        return [_jsonable(item) for item in value]
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    return value
