"""Financial projection exclusive to the repricer product page.

Keep the legacy reports unchanged. Source completeness is a completed cursor
chain, not the number of days on which operations happen to exist.
"""
from contextvars import ContextVar
from datetime import date, datetime, timedelta
from functools import wraps
from inspect import signature
from hashlib import sha256
from decimal import Decimal
from typing import Any

page_projection: ContextVar[bool] = ContextVar("repricer_page_finance", default=False)
page_connection: ContextVar[str | None] = ContextVar("repricer_page_connection", default=None)
VERSION = "repricer-finance-1"


def connection_key(token: str) -> str:
    return sha256(token.encode()).hexdigest()[:24]


def save_operations(org: int, token: str, start: date, end: date, rows: list[dict[str, Any]]) -> dict[str, Any]:
    from app.repricer_cache.store import save_source_cache
    return save_source_cache(org, f"repricer_finance_{connection_key(token)}_{start}_{end}", {
        "operations": rows, "sourceComplete": True, "dateFrom": str(start), "dateTo": str(end),
        "projectionVersion": VERSION,
    }, strict=True)


def page_finance_revision(org: int) -> str:
    from app.repricer_cache.store import list_source_cache_ranges_by_prefix
    from app.cabinet.store import get_organization_wb_token_secret
    token = get_organization_wb_token_secret(org)
    key = page_connection.get() or (connection_key(token) if token else "missing")
    metas = list_source_cache_ranges_by_prefix(org, f"repricer_finance_{key}_", limit=100)
    return sha256(repr((key, sorted((m["sourceKey"], str(m.get("fetchedAt"))) for m in metas))).encode()).hexdigest()


def missing_page_ranges(org: int, token: str, start: date, end: date) -> list[tuple[date, date]]:
    from app.repricer_cache.store import list_source_cache_ranges_by_prefix, get_source_cache
    covered = set()
    for meta in list_source_cache_ranges_by_prefix(org, f"repricer_finance_{connection_key(token)}_", limit=100):
        cache = get_source_cache(org, meta["sourceKey"], slim=True) or {}
        if cache.get("sourceComplete") is not True:
            continue
        left, right = date.fromisoformat(str(meta["dateFrom"])[:10]), date.fromisoformat(str(meta["dateTo"])[:10])
        covered.update(left+timedelta(days=i) for i in range((right-left).days+1))
    missing = sorted(start+timedelta(days=i) for i in range((end-start).days+1) if start+timedelta(days=i) not in covered)
    ranges = []
    for day in missing:
        if ranges and day == ranges[-1][1]+timedelta(days=1):
            ranges[-1] = (ranges[-1][0], day)
        else:
            ranges.append((day, day))
    return ranges


def repricer_finance_scope(fn):
    @wraps(fn)
    def scoped(*args, **kwargs):
        marker = page_projection.set(True)
        connection_marker = page_connection.set(None)
        try:
            return fn(*args, **kwargs)
        finally:
            page_projection.reset(marker)
            page_connection.reset(connection_marker)
    scoped.__signature__ = signature(fn, eval_str=True)
    return scoped


def project_operations(rows: list[dict[str, Any]], start: date, end: date) -> dict[str, Any]:
    from app.repricer_bff import (
        aggregate_finance_report_rows, _date_from_any, _finance_seller_revenue_kopecks,
        _kopecks_from_rub,
    )

    projected = []
    buyer: dict[str, int] = {}
    compensation: dict[tuple[str, str], int] = {}
    adjustments: dict[tuple[str, str], int] = {}
    blockers = set()
    daily_buyer: dict[tuple[str, str], int] = {}
    seen: dict[str, dict[str, Any]] = {}
    # These charges are posting-day charges; logistics/penalties carry their
    # own service-operation date. Do not date all expense families by a sale.
    posting_fields = {"paidStorage", "paidAcceptance", "deduction", "paymentSchedule"}
    service_fields = {"deliveryService", "penalty", "additionalPayment",
                      "cashbackAmount", "cashbackDiscount", "cashbackCommissionChange"}
    for original in rows:
        identity = str(original.get("rrdId") or "")
        if not identity:
            raise ValueError("WB_FINANCE_INVALID_ROW_ID")
        if identity in seen:
            if seen[identity] != original:
                raise ValueError("WB_FINANCE_CONFLICTING_ROWS")
            continue
        seen[identity] = original
        doc = str(original.get("docTypeName") or "").strip().casefold()
        oper = str(original.get("sellerOperName") or "").strip().casefold()
        quantity = int(original.get("quantity") or 0)
        sale_day = _date_from_any(original.get("saleDt"))
        posting_day = _date_from_any(original.get("rrDate"))
        trade = ((doc, oper) in {("продажа", "продажа"), ("возврат", "возврат")}
                 and quantity > 0)
        if trade and original.get("retailPriceWithDisc") is None:
            raise ValueError("WB_FINANCE_INVALID_SELLER_PRICE")
        if trade and original.get("forPay") is None:
            raise ValueError("WB_FINANCE_MISSING_PAYABLE")
        nm = str(int(original.get("nmId") or 0))
        if trade and sale_day and start <= sale_day <= end:
            item = dict(original)
            for key in posting_fields | service_fields:
                item[key] = 0
            seller = _finance_seller_revenue_kopecks(original, quantity)
            # Derive commission from one consistent seller monetary basis.
            item["retailAmount"] = str(Decimal(seller) / 100)
            projected.append(item)
            sign = -1 if doc == "возврат" else 1
            buyer[nm] = buyer.get(nm, 0) + sign * _kopecks_from_rub(original.get("retailAmount") or 0)
            daily_key = (sale_day.isoformat(), nm)
            daily_buyer[daily_key] = daily_buyer.get(daily_key, 0) + sign * _kopecks_from_rub(original.get("retailAmount") or 0)
        # Non-merchandise payable is an adjustment, never sold units. Preserve
        # signed corrections separately from the trade's seller payout.
        if not trade and sale_day and start <= sale_day <= end:
            amount = _kopecks_from_rub(original.get("forPay") or 0)
            if amount:
                key = (sale_day.isoformat(), nm)
                signed = -amount if doc == "возврат" else amount
                adjustments[key] = adjustments.get(key, 0) + signed
                if "компенсац" in oper and "коррек" not in oper:
                    compensation[key] = compensation.get(key, 0) + signed
                elif "коррек" not in oper:
                    blockers.add("WB_FINANCE_UNCLASSIFIED_PAYABLE")
        for fields, day in ((posting_fields, posting_day), (service_fields, sale_day or posting_day)):
            if not day or not start <= day <= end:
                continue
            if not any(original.get(key) not in (None, 0, "0", "0.00") for key in fields):
                continue
            item = dict(original)
            item.update(docTypeName="", sellerOperName=original.get("sellerOperName"),
                        quantity=0, retailAmount=0, retailPriceWithDisc=0, forPay=0,
                        ppvzSalesCommission=0, acquiringFee=0,
                        saleDt=day.isoformat())
            for key in posting_fields | service_fields:
                item[key] = original.get(key, 0) if key in fields else 0
            projected.append(item)

    result = aggregate_finance_report_rows(
        projected, date_from=datetime.combine(start, datetime.min.time()),
        date_to=datetime.combine(end, datetime.min.time()))
    result.pop("rows", None)
    # Preserve the original buyer-payment metric; it is not the commission base.
    for nm, row in result["aggregates"].items():
        row["settlementPayableConfirmed"] = (
            row.get("commissionSource") == "buyerRevenueKopecks-payableKopecks-acquiringKopecks"
            or row.get("salesUnits") == row.get("returnsUnits") == row.get("payableKopecks") == 0
        )
        row["buyerRevenueKopecks"] = buyer.get(nm, 0)
        row["commissionSource"] = "sellerRevenueKopecks-tradePayableKopecks-acquiringKopecks"
    for day, daily_rows in result["dailyAggregates"].items():
        for nm, row in daily_rows.items():
            row["settlementPayableConfirmed"] = row.get("commissionSource") == "buyerRevenueKopecks-payableKopecks-acquiringKopecks" or row.get("salesUnits") == row.get("returnsUnits") == row.get("payableKopecks") == 0
            row["buyerRevenueKopecks"] = daily_buyer.get((day, nm), 0)
            row["commissionSource"] = "sellerRevenueKopecks-tradePayableKopecks-acquiringKopecks"
    for (day, nm), amount in adjustments.items():
        # Use a complete zero-operation row rather than injecting six revenue
        # fields into an otherwise missing SKU record.
        if nm == "0":
            raise ValueError("WB_FINANCE_UNALLOCATED_PAYABLE")
        if nm not in result["aggregates"] or nm not in result["dailyAggregates"].get(day, {}):
            seed = {"rrdId": f"adjustment-{day}-{nm}", "nmId": int(nm),
                    "quantity": 0, "docTypeName": "", "saleDt": day, "forPay": 0}
            empty = aggregate_finance_report_rows([seed], date_from=datetime.combine(start, datetime.min.time()),
                                                  date_to=datetime.combine(end, datetime.min.time()))
            result["aggregates"].setdefault(nm, empty["aggregates"][nm])
            result["dailyAggregates"].setdefault(day, {}).setdefault(nm, empty["dailyAggregates"][day][nm])
        result["aggregates"][nm]["additionalPaymentKopecks"] += amount
        result["dailyAggregates"][day][nm]["additionalPaymentKopecks"] += amount
    from app.repricer_bff import build_finance_diagnostics_from_aggregates
    # Retain raw account-level fees even when there are no product allocation
    # weights. They are cabinet expenses, never an invented product row.
    raw_expenses = result.get("diagnostics", {}).get("rawExpenseTotals")
    result["diagnostics"] = build_finance_diagnostics_from_aggregates(result["aggregates"])
    if isinstance(raw_expenses, dict):
        raw_expenses = dict(raw_expenses)
        raw_expenses["additionalPaymentKopecks"] = raw_expenses.get("additionalPaymentKopecks", 0) + sum(adjustments.values())
        result["diagnostics"]["rawExpenseTotals"] = raw_expenses
    result.update(projectionVersion=VERSION, compensationKopecks=sum(compensation.values()),
                  projectionBlockers=sorted(blockers))
    if blockers:
        for row in result["aggregates"].values():
            row["settlementComponentsConfirmed"] = False
    return result


def load_page_finance(org: int, start: date, end: date, *, projector=None) -> dict[str, Any]:
    from app.repricer_cache.store import get_source_cache, list_source_cache_ranges_by_prefix
    from app.repricer_bff import FINANCE_REVENUE_BASIS, FINANCE_SCHEMA_VERSION
    operations = {}
    covered: set[date] = set()
    observed = ""
    owned: set[str] = set()
    from app.cabinet.store import get_organization_wb_token_secret
    token = get_organization_wb_token_secret(org)
    key = page_connection.get() or (connection_key(token) if token else None)
    metas = list_source_cache_ranges_by_prefix(org, f"repricer_finance_{key}_", limit=100) if key else []
    for meta in sorted(metas, key=lambda m: str(m.get("fetchedAt") or ""), reverse=True):
        left, right = meta.get("dateFrom"), meta.get("dateTo")
        if not left or not right:
            continue
        left, right = date.fromisoformat(str(left)[:10]), date.fromisoformat(str(right)[:10])
        if right < start:
            continue
        payload = get_source_cache(org, meta["sourceKey"], slim=False) or {}
        if payload.get("sourceComplete") is not True or not isinstance(payload.get("operations"), list):
            continue
        days = {(left + timedelta(days=i)).isoformat() for i in range((right-left).days+1)}
        available = days-owned
        if not available:
            continue
        for row in payload["operations"]:
            posting = str(row.get("rrDate") or "")[:10]
            if posting in available:
                operations.setdefault(str(row["rrdId"]), row)
        owned.update(days)
        covered.update(left + timedelta(days=i) for i in range((right-left).days+1))
        observed = max(observed, str(payload.get("fetchedAt") or ""))
    wanted = {start + timedelta(days=i) for i in range((end-start).days+1)}
    result = (projector or project_operations)(list(operations.values()), start, end)
    result.update(sourceComplete=wanted <= covered, coverageState="ok" if wanted <= covered else "partial",
                  coveredDays=len(wanted & covered), requestedDays=len(wanted),
                  missingDates=sorted(day.isoformat() for day in wanted-covered),
                  dateFrom=start.isoformat(), dateTo=end.isoformat(), periodDays=len(wanted),
                  fetchedAt=observed or None, revenueBasis=FINANCE_REVENUE_BASIS,
                  financeSchemaVersion=FINANCE_SCHEMA_VERSION)
    if not result["sourceComplete"]:
        for row in result["aggregates"].values():
            row["settlementComponentsConfirmed"] = False
    return result
