from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import Any

# WB Prices API returns integer rubles; internal contracts use kopecks.
# Test fixtures and some legacy payloads already use kopecks (e.g. 129_000).
_WB_GOODS_PRICE_ALREADY_KOPECKS_THRESHOLD = 100_000


def _number_or_none(raw: Any) -> float | None:
    if raw is None or raw == "":
        return None
    try:
        return float(str(raw).replace(",", "."))
    except (TypeError, ValueError):
        return None


def wb_goods_price_to_kopecks(raw: Any) -> int:
    value = _number_or_none(raw)
    if value is None or value <= 0:
        return 0
    if value >= _WB_GOODS_PRICE_ALREADY_KOPECKS_THRESHOLD:
        return int(round(value))
    return int(round(value * 100))


def kopecks_to_wb_price_rubles(kopecks: int | float | Decimal | None) -> int | None:
    if kopecks is None:
        return None
    value = Decimal(str(kopecks))
    if value <= 0:
        return None
    return int((value / Decimal("100")).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
