"""WB product-report monetary definition, separate from repricer pricing math."""
from datetime import date
from collections import OrderedDict
from copy import deepcopy
from threading import RLock

from app.repricer_page_finance import project_operations
from app.repricer_bff import _date_from_any, _kopecks_from_rub

VERSION = "wb-product-report-v1"
_projections = OrderedDict()
_projection_lock = RLock()


def load_report_finance(organization_id, start, end):
    """Reuse only an identical account/connection/raw-source revision, bounded to four ranges."""
    from app.cabinet.store import get_organization_wb_token_secret
    from app.repricer_page_finance import load_page_finance, connection_key, page_connection, VERSION as BASE_VERSION
    from app.repricer_cache.store import list_source_cache_ranges_by_prefix
    token = get_organization_wb_token_secret(organization_id)
    connection = page_connection.get() or (connection_key(token) if token else None)
    if not connection:
        return load_page_finance(organization_id, start, end, projector=project_report_operations)
    def revision():
        metas = list_source_cache_ranges_by_prefix(organization_id, f"repricer_finance_{connection}_", limit=100)
        return tuple(sorted((str(m.get("sourceKey")), str(m.get("fetchedAt"))) for m in metas))
    before = revision()
    key = (organization_id, connection, start, end, VERSION, BASE_VERSION, before)
    with _projection_lock:
        if key in _projections:
            _projections.move_to_end(key)
            return deepcopy(_projections[key])
    marker = page_connection.set(connection)
    try:
        result = load_page_finance(organization_id, start, end, projector=project_report_operations)
    finally:
        page_connection.reset(marker)
    if before == revision():
        with _projection_lock:
            _projections[key] = deepcopy(result)
            while len(_projections) > 4:
                _projections.popitem(last=False)
    return result


def project_report_operations(rows: list[dict], start: date, end: date) -> dict:
    result = project_operations(rows, start, end)
    seen = set()
    adjustments = {}
    for row in rows:
        identity = str(row.get("rrdId"))
        if identity in seen:
            continue
        seen.add(identity)
        day = _date_from_any(row.get("saleDt"))
        if not day or not start <= day <= end:
            continue
        operation = str(row.get("sellerOperName") or "").strip().casefold()
        # These exact operation families reconcile to WB's product export.
        # Other reimbursements remain separate; never subtract all credits.
        if operation not in {"добровольная компенсация при возврате", "коррекция продаж"}:
            continue
        amount = _kopecks_from_rub(row.get("forPay") or 0)
        if str(row.get("docTypeName") or "").strip().casefold() == "возврат":
            amount = -amount
        if not amount:
            continue
        key = (day.isoformat(), str(int(row.get("nmId") or 0)), operation)
        adjustments[key] = adjustments.get(key, 0) + amount
    correction = 0
    revenue_adjustment = 0
    for (day, nm, operation), amount in adjustments.items():
        for aggregate in (result["aggregates"][nm], result["dailyAggregates"][day][nm]):
            aggregate["commissionKopecks"] -= amount
            if operation == "добровольная компенсация при возврате":
                for field in ("sellerRevenueKopecks", "revenueGrossKopecks", "grossSalesKopecks"):
                    aggregate[field] -= amount
            else:
                # Already included as a reduced commission, not a second credit.
                aggregate["additionalPaymentKopecks"] -= amount
        if operation == "коррекция продаж":
            correction += amount
        else:
            revenue_adjustment += amount
    raw = result.get("diagnostics", {}).get("rawExpenseTotals") or {}
    if "additionalPaymentKopecks" in raw:
        raw["additionalPaymentKopecks"] -= correction
    if "commissionKopecks" in raw:
        raw["commissionKopecks"] -= correction + revenue_adjustment
    result["reportMetricVersion"] = VERSION
    result["reportRevenueAdjustmentKopecks"] = revenue_adjustment
    return result
