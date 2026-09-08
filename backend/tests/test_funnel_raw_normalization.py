from __future__ import annotations

import copy
import hashlib
import json
from datetime import date
from pathlib import Path

import pytest

from app.platform.funnel.raw import FunnelNormalizationError, normalize_raw_funnel
from app.platform.period import Period

PERIOD = Period(date(2026, 9, 2), date(2026, 9, 3))


@pytest.fixture
def raw_bundle() -> dict[str, object]:
    return json.loads(
        (Path(__file__).parent / "fixtures/wb_funnel_history_daily_sanitized.json").read_text()
    )


def _encoded(value: object) -> str:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def _canonical(value: object) -> object:
    if isinstance(value, dict):
        return {key: _canonical(item) for key, item in value.items()}
    if isinstance(value, list):
        return sorted((_canonical(item) for item in value), key=_encoded)
    return value


def _refresh_response_checksum(bundle: dict[str, object]) -> None:
    page = bundle["pages"][0]
    manifest = bundle["manifest"][0]
    manifest["responseChecksum"] = hashlib.sha256(
        _encoded(_canonical(page["payload"])).encode()
    ).hexdigest()


def _fact(evidence, nm_id: int, business_date: date):
    return next(
        fact
        for fact in evidence.facts
        if fact.nm_id == nm_id and fact.business_date == business_date
    )


def test_funnel_history_preserves_daily_metrics_money_and_missing(raw_bundle):
    evidence = normalize_raw_funnel(PERIOD, raw_bundle)

    assert len(evidence.facts) == 4
    first = _fact(evidence, 1001, date(2026, 9, 2))
    assert (
        first.currency,
        first.open_count,
        first.cart_count,
        first.order_count,
        first.order_amount_kopecks,
        first.buyout_count,
        first.buyout_amount_kopecks,
        first.add_to_wishlist_count,
    ) == ("RUB", 10, 2, 1, 1234, 1, 1234, 0)
    explicit_zero = _fact(evidence, 1001, date(2026, 9, 3))
    assert explicit_zero.open_count == 0
    assert explicit_zero.order_amount_kopecks == 0
    assert explicit_zero.add_to_wishlist_count is None
    assert len(evidence.raw_manifest_checksum) == 64
    assert len(evidence.snapshot_checksum) == 64


def test_funnel_accepts_exact_live_wrapper_and_official_bare_list(raw_bundle):
    wrapped = normalize_raw_funnel(PERIOD, raw_bundle)
    raw_bundle["pages"][0]["payload"] = raw_bundle["pages"][0]["payload"]["data"]
    _refresh_response_checksum(raw_bundle)

    bare = normalize_raw_funnel(PERIOD, raw_bundle)

    assert bare.facts == wrapped.facts


def test_funnel_exact_duplicate_collapses_but_conflict_blocks(raw_bundle):
    duplicate = copy.deepcopy(raw_bundle["pages"][0]["payload"]["data"][0])
    raw_bundle["pages"][0]["payload"]["data"].append(duplicate)
    _refresh_response_checksum(raw_bundle)
    assert len(normalize_raw_funnel(PERIOD, raw_bundle).facts) == 4

    duplicate["history"][0]["openCount"] += 1
    _refresh_response_checksum(raw_bundle)
    with pytest.raises(FunnelNormalizationError, match="conflicting"):
        normalize_raw_funnel(PERIOD, raw_bundle)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda bundle: bundle["pages"][0]["payload"]["data"][0]["history"][0].update(date="2026-09-01"),
        lambda bundle: bundle["pages"][0]["payload"]["data"][0]["product"].update(nmId=True),
        lambda bundle: bundle["pages"][0]["payload"]["data"][0]["history"][0].update(openCount=-1),
        lambda bundle: bundle["pages"][0]["payload"]["data"][0]["history"][0].update(cartCount=1.5),
        lambda bundle: bundle["pages"][0]["payload"]["data"][0].update(currency="rub"),
        lambda bundle: bundle["pages"][0]["payload"]["data"][0]["history"][0].update(orderSum=0.001),
    ],
)
def test_funnel_rejects_invalid_source_values(raw_bundle, mutate):
    mutate(raw_bundle)
    _refresh_response_checksum(raw_bundle)

    with pytest.raises(FunnelNormalizationError, match="invalid|outside"):
        normalize_raw_funnel(PERIOD, raw_bundle)


def test_funnel_rejects_metricless_history_row(raw_bundle):
    row = raw_bundle["pages"][0]["payload"]["data"][0]["history"][0]
    for key in (
        "openCount",
        "cartCount",
        "orderCount",
        "orderSum",
        "buyoutCount",
        "buyoutSum",
        "addToWishlistCount",
    ):
        row.pop(key)
    _refresh_response_checksum(raw_bundle)

    with pytest.raises(FunnelNormalizationError, match="metrics"):
        normalize_raw_funnel(PERIOD, raw_bundle)


@pytest.mark.parametrize("manifest", [None, {}])
def test_funnel_rejects_missing_manifest(raw_bundle, manifest):
    raw_bundle["manifest"] = manifest

    with pytest.raises(FunnelNormalizationError, match="manifest"):
        normalize_raw_funnel(PERIOD, raw_bundle)


def test_funnel_rejects_partial_or_mismatched_manifest(raw_bundle):
    raw_bundle["manifest"][0]["ok"] = False

    with pytest.raises(FunnelNormalizationError, match="incomplete"):
        normalize_raw_funnel(PERIOD, raw_bundle)

    raw_bundle["manifest"][0]["ok"] = True
    raw_bundle["manifest"][0]["responseChecksum"] = "f" * 64
    with pytest.raises(FunnelNormalizationError, match="checksum"):
        normalize_raw_funnel(PERIOD, raw_bundle)


def test_funnel_rejects_manifest_secret_without_exposing_value(raw_bundle, caplog):
    raw_bundle["manifest"][0]["request"]["nested"] = {
        "Authorization": "never-persist-this-secret"
    }

    with pytest.raises(FunnelNormalizationError, match="manifest") as raised:
        normalize_raw_funnel(PERIOD, raw_bundle)

    assert "never-persist-this-secret" not in str(raised.value)
    assert "never-persist-this-secret" not in caplog.text


def test_funnel_snapshot_ignores_request_id_but_tracks_data_and_coverage(raw_bundle):
    first = normalize_raw_funnel(PERIOD, raw_bundle)

    request_id_only = copy.deepcopy(raw_bundle)
    request_id_only["manifest"][0]["wbRequestId"] = "different-request"
    replay = normalize_raw_funnel(PERIOD, request_id_only)
    assert replay.snapshot_checksum == first.snapshot_checksum
    assert replay.raw_manifest_checksum != first.raw_manifest_checksum

    changed = copy.deepcopy(raw_bundle)
    changed["pages"][0]["payload"]["data"][0]["history"][0]["openCount"] += 1
    _refresh_response_checksum(changed)
    assert normalize_raw_funnel(PERIOD, changed).snapshot_checksum != first.snapshot_checksum

    wider_request = copy.deepcopy(raw_bundle)
    wider_request["pages"][0]["request"]["nmIds"].append(1003)
    wider_request["manifest"][0]["request"]["nmIds"].append(1003)
    assert normalize_raw_funnel(PERIOD, wider_request).snapshot_checksum != first.snapshot_checksum
