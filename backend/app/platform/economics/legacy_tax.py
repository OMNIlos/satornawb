"""Read-only dated tax bridge for legacy WB factual rows and summaries."""
from datetime import date, timedelta
import hashlib
import json
from typing import Any

from sqlalchemy import func, select, text
from sqlalchemy.exc import SQLAlchemyError

from app.infra.db import get_session_factory, set_tenant_context
from app.modules.wb_reports.abc_pnl import _day_end, _round_basis_points
from app.platform.catalog.orm import CatalogSkuRow, MarketplaceOfferRow, MarketplaceProductRow
from app.platform.catalog.service import CatalogService
from app.platform.economics.orm import CatalogEconomicsOverrideVersionRow, OrganizationEconomicsVersionRow
from app.platform.economics.policies import EconomicsService
from app.platform.economics.costs import CostsService
from app.platform.economics.orm import CatalogCostVersionRow
from app.platform.integrations.orm import MarketplaceAccountRow
from app.platform.period import Period
from app.repricer_cache.store import finance_cache_uses_current_revenue_basis


def _missing(reason: str) -> dict[str, Any]:
    return {"taxKopecks": None, "factTaxState": "missing", "factTaxReason": reason}


def _revenue(row: dict[str, Any]) -> int | None:
    for key in ("sellerRevenueKopecks", "revenueGrossKopecks", "revenueKopecks", "buyerRevenueKopecks"):
        value = row.get(key)
        if value is not None:
            return value if type(value) is int else None
    return None


def _confirmed(policy: Any) -> bool:
    return bool(policy is not None and policy.tax_basis_points is not None
                and policy.tax_value_state == "configured" and policy.tax_evidence_status == "dated")


def _prepare_read(session: Any, organization_id: int) -> None:
    if session.get_bind().dialect.name == "postgresql":
        session.execute(text("SET TRANSACTION READ ONLY"))
    set_tenant_context(session, organization_id)


def get_legacy_finance_taxes(
    organization_id: int, finance_cache: dict[str, Any], period: Period,
    *, include_costs: bool = False,
) -> dict[str, dict[str, Any]]:
    source = finance_cache.get("aggregates")
    aggregates = {str(key): value for key, value in source.items() if isinstance(value, dict)} if isinstance(source, dict) else {}
    if not aggregates:
        return {}
    result = {key: _missing("tax_policy_unavailable") for key in aggregates}
    if not finance_cache_uses_current_revenue_basis(finance_cache):
        return {key: _missing("tax_revenue_basis_unconfirmed") for key in aggregates}
    dates = [period.date_from + timedelta(days=offset) for offset in range(period.days)]
    instants = {day: _day_end(day) for day in dates}
    nm_ids = {key: int(key) for key in aggregates if key.isdigit() and int(key) > 0}
    daily: dict[str, list[tuple[date, dict[str, Any]]]] = {}
    has_daily = isinstance(finance_cache.get("dailyAggregates"), dict)
    if has_daily:
        for day in dates:
            values = finance_cache["dailyAggregates"].get(day.isoformat()) or {}
            if isinstance(values, dict):
                for key, value in values.items():
                    if isinstance(value, dict):
                        daily.setdefault(str(key), []).append((day, value))
    try:
        with get_session_factory()() as session:
            _prepare_read(session, organization_id)
            account_ids = session.scalars(select(MarketplaceAccountRow.marketplace_account_id).where(
                MarketplaceAccountRow.organization_id == organization_id,
                MarketplaceAccountRow.marketplace == "wb", MarketplaceAccountRow.status == "connected",
            )).all()
            if len(account_ids) != 1:
                reason = "tax_account_missing" if not account_ids else "tax_account_ambiguous"
                return {key: _missing(reason) for key in aggregates}
            mapping, ambiguous = CatalogService(session, organization_id).resolve_wb_product_skus(account_ids[0], list(nm_ids.values()))
            policies = EconomicsService(session, organization_id).get_policies_for_points([
                (sku_id, instant) for sku_id in set(mapping.values()) for instant in instants.values()
            ])
            costs = CostsService(session, organization_id).get_costs_for_points([
                (sku_id, point) for sku_id in set(mapping.values()) for instant in instants.values()
                for point in (instant, instant - timedelta(days=1) + timedelta(microseconds=1))
            ]) if include_costs else {}
            for key, fact in aggregates.items():
                nm_id = nm_ids.get(key)
                sku_id = mapping.get(nm_id)
                if nm_id in ambiguous or sku_id is None:
                    result[key] = _missing("tax_mapping_ambiguous" if nm_id in ambiguous else "tax_mapping_missing")
                    continue
                revenue = _revenue(fact)
                if revenue is None:
                    result[key] = _missing("tax_revenue_basis_unconfirmed")
                    continue
                entries = daily.get(key, [])
                if has_daily:
                    unit_fields = ("salesUnits", "returnsUnits")
                    if (not entries
                        or any(type(row.get(field)) is not int for row in [fact, *(row for _, row in entries)] for field in unit_fields)
                        or any(_revenue(row) is None for _, row in entries)
                        or sum(_revenue(row) for _, row in entries) != revenue
                        or any(sum(row[field] for _, row in entries) != fact[field] for field in unit_fields)):
                        result[key] = _missing("tax_daily_coverage_mismatch")
                        continue
                    bases = [(policies.get((sku_id, instants[day])), _revenue(row)) for day, row in entries]
                else:
                    values = [policies.get((sku_id, instant)) for instant in instants.values()]
                    if not all(_confirmed(policy) for policy in values):
                        result[key] = _missing("tax_policy_unconfirmed")
                        continue
                    if len({policy.tax_basis_points for policy in values}) != 1:
                        result[key] = _missing("tax_daily_basis_missing")
                        continue
                    bases = [(values[0], revenue)]
                if not all(_confirmed(policy) for policy, _ in bases):
                    result[key] = _missing("tax_policy_unconfirmed")
                    continue
                grouped: dict[int, int] = {}
                for policy, amount in bases:
                    rate = policy.tax_basis_points
                    grouped[rate] = grouped.get(rate, 0) + amount
                result[key] = {
                    "taxKopecks": sum(_round_basis_points(amount, rate) for rate, amount in grouped.items()),
                    "factTaxState": "configured", "factTaxReason": None,
                }
                if include_costs:
                    points = [(instants[day], row) for day, row in entries] if has_daily else [
                        (instants[dates[0]], fact)
                    ]
                    values = [costs.get((sku_id, instant)) for instant, _ in points]
                    confirmed = all(value is not None and value.value_state == "configured"
                                    and value.evidence_status == "dated" and type(value.amount_kopecks) is int
                                    for value in values)
                    # Daily units cannot be split around an intraday edit.
                    # Confirm only if the version was already active at day start.
                    confirmed = confirmed and all(
                        (opening := costs.get((sku_id, instant - timedelta(days=1) + timedelta(microseconds=1)))) is not None
                        and opening.cost_version_id == value.cost_version_id
                        for value, (instant, _) in zip(values, points)
                    )
                    if not has_daily:
                        all_values = [costs.get((sku_id, instant)) for instant in instants.values()]
                        confirmed = confirmed and all(value is not None and value.value_state == "configured"
                            and value.evidence_status == "dated" and value.amount_kopecks == values[0].amount_kopecks
                            for value in all_values)
                    confirmed = confirmed and all(type(row.get(field)) is int
                        for _, row in points for field in ("salesUnits", "returnsUnits"))
                    result[key].update(
                        settlementCogsKopecks=sum(value.amount_kopecks * (row["salesUnits"] - row["returnsUnits"])
                            for value, (_, row) in zip(values, points)) if confirmed else None,
                        settlementCogsReason=None if confirmed else "dated_cost_missing_or_daily_basis_incomplete",
                    )
            session.rollback()
    except SQLAlchemyError:
        return {key: _missing("tax_policy_unavailable") for key in aggregates}
    return result


def legacy_finance_tax_revision(organization_id: int) -> str:
    """One metadata query; no financial payload or credentials are read."""
    models = (OrganizationEconomicsVersionRow, CatalogEconomicsOverrideVersionRow, CatalogCostVersionRow,
              CatalogSkuRow, MarketplaceAccountRow, MarketplaceProductRow, MarketplaceOfferRow)
    statements = []
    for model in models:
        statements.append(select(func.count()).select_from(model).where(model.organization_id == organization_id).scalar_subquery())
        if hasattr(model, "updated_at"):
            statements.append(select(func.max(model.updated_at)).where(model.organization_id == organization_id).scalar_subquery())
    try:
        with get_session_factory()() as session:
            _prepare_read(session, organization_id)
            revision = list(session.execute(select(*statements)).one())
            session.rollback()
    except SQLAlchemyError:
        return "unavailable"
    return hashlib.sha256(json.dumps(revision, default=str, separators=(",", ":")).encode()).hexdigest()
