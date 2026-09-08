from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy.orm import Session

from app.platform.advertising.service import AdvertisingService, AdvertisingSnapshot
from app.platform.catalog.service import CatalogService
from app.platform.clock import utc_now
from app.platform.economics.costs import CostValue, CostsService
from app.platform.economics.policies import EconomicsPolicy, EconomicsService
from app.platform.finance.service import (
    FinanceNormalizationError,
    FinancePnlDailyBasis,
    FinancePnlFact,
    FinanceSnapshot,
    FinanceSourceState,
    FinanceService,
)
from app.platform.period import MOSCOW, Period

FORMULA_VERSION = "wb-abc-pnl-fullstats-loyalty-v1"


@dataclass(frozen=True, slots=True)
class AbcPnlRow:
    nm_id: int | None
    seller_article: str | None
    catalog_sku_id: int | None
    operation_count: int
    revenue_kopecks: int
    sales_revenue_kopecks: int
    returns_revenue_kopecks: int
    main_revenue_kopecks: int
    redemptions_revenue_kopecks: int
    late_correction_revenue_kopecks: int
    unknown_revenue_kopecks: int
    sales_units: int
    returns_units: int
    net_units: int
    commission_kopecks: int
    logistics_kopecks: int
    storage_kopecks: int
    acceptance_kopecks: int
    penalty_kopecks: int
    deduction_kopecks: int
    additional_payment_kopecks: int
    finance_other_expenses_kopecks: int
    compensation_kopecks: int
    acquiring_kopecks: int
    finance_expenses_kopecks: int
    cost_value_state: str
    cost_evidence_status: str | None
    cogs_kopecks: int | None
    settlement_profit_kopecks: int | None
    economics_value_state: str
    economics_evidence_status: str | None
    tax_kopecks: int | None
    other_expenses_kopecks: int | None
    profit_before_ads_and_loyalty_kopecks: int | None
    advertising_spend_kopecks: int | None
    profit_before_loyalty_kopecks: int | None
    cashback_amount_kopecks: int | None
    cashback_discount_kopecks: int | None
    cashback_commission_change_kopecks: int | None
    loyalty_net_cost_kopecks: int | None
    profit_after_loyalty_kopecks: int | None
    sales_class: str | None
    profit_class: None
    abc_code: None
    net_profit_kopecks: None
    blocker_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class AbcPnlSummary:
    operation_count: int
    sku_count: int
    revenue_kopecks: int
    sales_revenue_kopecks: int
    returns_revenue_kopecks: int
    sales_units: int
    returns_units: int
    net_units: int
    commission_kopecks: int
    logistics_kopecks: int
    storage_kopecks: int
    acceptance_kopecks: int
    penalty_kopecks: int
    deduction_kopecks: int
    finance_other_expenses_kopecks: int
    compensation_kopecks: int
    acquiring_kopecks: int
    finance_expenses_kopecks: int
    cogs_kopecks: int | None
    settlement_profit_kopecks: int | None
    tax_kopecks: int | None
    other_expenses_kopecks: int | None
    profit_before_ads_and_loyalty_kopecks: int | None
    advertising_spend_kopecks: int | None
    unattributed_advertising_spend_kopecks: int | None
    profit_before_loyalty_kopecks: int | None
    cashback_amount_kopecks: int | None
    cashback_discount_kopecks: int | None
    cashback_commission_change_kopecks: int | None
    loyalty_net_cost_kopecks: int | None
    profit_after_loyalty_kopecks: int | None
    net_profit_kopecks: None


@dataclass(frozen=True, slots=True)
class AbcPnlPage:
    state: FinanceSourceState
    period: Period
    snapshot: FinanceSnapshot | None
    advertising_snapshot: AdvertisingSnapshot | None
    formula_version: str
    cost_ledger_revision: int
    economics_revision: int
    blocker_ids: tuple[str, ...]
    summary: AbcPnlSummary
    items: list[AbcPnlRow]
    total: int
    limit: int
    offset: int


def _day_end(day: date) -> datetime:
    return datetime.combine(day + timedelta(days=1), time.min, MOSCOW).astimezone(
        timezone.utc
    ) - timedelta(microseconds=1)


def _sales_letter(rank_index: int, total: int) -> str:
    ratio = (rank_index + 1) / total
    return "A" if ratio <= 0.2 else "B" if ratio <= 0.5 else "C"


def _round_basis_points(amount_kopecks: int, basis_points: int) -> int:
    numerator = amount_kopecks * basis_points
    sign = -1 if numerator < 0 else 1
    quotient, remainder = divmod(abs(numerator), 10_000)
    if remainder > 5_000 or remainder == 5_000 and quotient % 2:
        quotient += 1
    return sign * quotient


def _empty_summary(
    advertising_total: int | None = None,
    unattributed_advertising: int | None = None,
    *,
    loyalty_complete: bool = False,
) -> AbcPnlSummary:
    return AbcPnlSummary(
        *(0 for _ in range(18)),
        *(None for _ in range(5)),
        advertising_total,
        unattributed_advertising,
        None,
        *((0 if loyalty_complete else None) for _ in range(4)),
        None,
        None,
    )


def _zero_finance_fact(nm_id: int) -> FinancePnlFact:
    return FinancePnlFact(
        nm_id=nm_id,
        seller_article=None,
        operation_count=0,
        revenue_kopecks=0,
        sales_revenue_kopecks=0,
        returns_revenue_kopecks=0,
        main_revenue_kopecks=0,
        redemptions_revenue_kopecks=0,
        late_correction_revenue_kopecks=0,
        unknown_revenue_kopecks=0,
        sales_units=0,
        returns_units=0,
        net_units=0,
        commission_kopecks=0,
        logistics_kopecks=0,
        storage_kopecks=0,
        acceptance_kopecks=0,
        penalty_kopecks=0,
        deduction_kopecks=0,
        additional_payment_kopecks=0,
        acquiring_kopecks=0,
        cashback_amount_kopecks=0,
        cashback_discount_kopecks=0,
        cashback_commission_change_kopecks=0,
    )


class WbAbcPnlService:
    def __init__(
        self,
        session: Session,
        organization_id: int,
        *,
        now: Callable[[], datetime] = utc_now,
    ) -> None:
        self.session = session
        self.organization_id = organization_id
        self.now = now

    @staticmethod
    def _cost_result(
        fact: FinancePnlFact,
        *,
        catalog_sku_id: int | None,
        ambiguous: bool,
        daily: list[tuple[datetime, int]],
        costs: dict[tuple[int, datetime], CostValue],
    ) -> tuple[int | None, str, str | None, tuple[str, ...]]:
        if sum(units for _instant, units in daily) != fact.net_units:
            return None, "missing", None, ("WB_PNL_COST_DAILY_COVERAGE_MISMATCH",)
        if not daily:
            return 0, "configured", None, ()
        if fact.nm_id is None:
            return None, "missing", None, ("WB_PNL_COST_PRODUCT_UNATTRIBUTED",)
        if ambiguous:
            return None, "missing", None, ("WB_PNL_COST_MAPPING_AMBIGUOUS",)
        if catalog_sku_id is None:
            return None, "missing", None, ("WB_PNL_COST_MAPPING_MISSING",)

        values = [costs[(catalog_sku_id, instant)] for instant, _ in daily]
        if any(value.amount_kopecks is None for value in values):
            return None, "missing", None, ("WB_PNL_COST_MISSING",)

        cogs = sum(
            int(value.amount_kopecks or 0) * units
            for (_, units), value in zip(daily, values, strict=True)
        )
        assumed = any(value.value_state == "assumed" for value in values)
        evidence = {value.evidence_status for value in values}
        evidence_status = (
            "period_end_fallback"
            if "period_end_fallback" in evidence
            else "undated" if "undated" in evidence else "dated"
        )
        blockers: list[str] = []
        if assumed:
            blockers.append("WB_PNL_COST_ASSUMED")
        if evidence_status != "dated":
            blockers.append("WB_PNL_COST_EVIDENCE_UNDATED")
        return (
            cogs,
            "assumed" if assumed else "configured",
            evidence_status,
            tuple(blockers),
        )

    @staticmethod
    def _economics_result(
        fact: FinancePnlFact,
        *,
        catalog_sku_id: int | None,
        ambiguous: bool,
        daily: list[tuple[datetime, FinancePnlDailyBasis]],
        policies: dict[tuple[int, datetime], EconomicsPolicy],
    ) -> tuple[int | None, int | None, str, str | None, tuple[str, ...]]:
        if (
            sum(basis.revenue_kopecks for _day, basis in daily) != fact.revenue_kopecks
            or sum(basis.sales_units for _day, basis in daily) != fact.sales_units
        ):
            return (
                None,
                None,
                "missing",
                None,
                ("WB_PNL_ECONOMICS_DAILY_COVERAGE_MISMATCH",),
            )
        if not daily:
            return 0, 0, "configured", None, ()
        if fact.nm_id is None:
            return (
                None,
                None,
                "missing",
                None,
                ("WB_PNL_ECONOMICS_PRODUCT_UNATTRIBUTED",),
            )
        if ambiguous:
            return None, None, "missing", None, ("WB_PNL_ECONOMICS_MAPPING_AMBIGUOUS",)
        if catalog_sku_id is None:
            return None, None, "missing", None, ("WB_PNL_ECONOMICS_MAPPING_MISSING",)

        values = [policies.get((catalog_sku_id, instant)) for instant, _basis in daily]
        if any(
            policy is None
            or policy.value_state == "missing"
            or any(value is None for value in policy.amounts)
            for policy in values
        ):
            return None, None, "missing", None, ("WB_PNL_ECONOMICS_MISSING",)

        groups: dict[tuple[int, int, int], list[int]] = {}
        for (_day, basis), policy in zip(daily, values, strict=True):
            assert policy is not None
            key = tuple(int(value) for value in policy.amounts)
            totals = groups.setdefault(key, [0, 0])
            totals[0] += basis.revenue_kopecks
            totals[1] += basis.sales_units
        tax = sum(
            _round_basis_points(revenue, tax_basis_points)
            for (tax_basis_points, _other_basis_points, _per_sale), (
                revenue,
                _sales,
            ) in groups.items()
        )
        other = sum(
            _round_basis_points(revenue, other_basis_points) + sales * per_sale
            for (_tax_basis_points, other_basis_points, per_sale), (
                revenue,
                sales,
            ) in groups.items()
        )
        assumed = any(policy.value_state == "assumed" for policy in values)
        evidence = {policy.evidence_status for policy in values}
        evidence_status = (
            "period_end_fallback"
            if "period_end_fallback" in evidence
            else "undated" if "undated" in evidence else "dated"
        )
        blockers: list[str] = []
        if assumed:
            blockers.append("WB_PNL_ECONOMICS_ASSUMED")
        if evidence_status != "dated":
            blockers.append("WB_PNL_ECONOMICS_EVIDENCE_UNDATED")
        return (
            tax,
            other,
            "assumed" if assumed else "configured",
            evidence_status,
            tuple(blockers),
        )

    @staticmethod
    def _row(
        fact: FinancePnlFact,
        catalog_sku_id: int | None,
        cogs: int | None,
        cost_state: str,
        cost_evidence_status: str | None,
        tax: int | None,
        other_expenses: int | None,
        economics_state: str,
        economics_evidence_status: str | None,
        advertising_spend: int | None,
        loyalty_canonical: bool,
        sales_class: str | None,
        blockers: tuple[str, ...],
    ) -> AbcPnlRow:
        penalty = max(0, fact.penalty_kopecks)
        deduction = max(0, fact.deduction_kopecks)
        finance_other = max(0, -fact.additional_payment_kopecks)
        compensation = (
            max(0, fact.additional_payment_kopecks)
            + max(0, -fact.penalty_kopecks)
            + max(0, -fact.deduction_kopecks)
        )
        finance_expenses = (
            fact.commission_kopecks
            + fact.logistics_kopecks
            + fact.storage_kopecks
            + fact.acceptance_kopecks
            + penalty
            + deduction
            + finance_other
            + fact.acquiring_kopecks
            - compensation
        )
        settlement_profit = (
            None if cogs is None else fact.revenue_kopecks - cogs - finance_expenses
        )
        profit_before_ads_and_loyalty = (
            None
            if settlement_profit is None or tax is None or other_expenses is None
            else settlement_profit - tax - other_expenses
        )
        profit_before_loyalty = (
            None
            if profit_before_ads_and_loyalty is None or advertising_spend is None
            else profit_before_ads_and_loyalty - advertising_spend
        )
        cashback_amount = fact.cashback_amount_kopecks if loyalty_canonical else None
        cashback_discount = fact.cashback_discount_kopecks if loyalty_canonical else None
        cashback_commission_change = (
            fact.cashback_commission_change_kopecks if loyalty_canonical else None
        )
        loyalty_net_cost = fact.loyalty_net_cost_kopecks if loyalty_canonical else None
        profit_after_loyalty = (
            None
            if profit_before_loyalty is None or loyalty_net_cost is None
            else profit_before_loyalty - loyalty_net_cost
        )
        if loyalty_net_cost is None:
            blockers = (*blockers, "WB_PNL_LOYALTY_NOT_CANONICAL")
        return AbcPnlRow(
            fact.nm_id,
            fact.seller_article,
            catalog_sku_id,
            fact.operation_count,
            fact.revenue_kopecks,
            fact.sales_revenue_kopecks,
            fact.returns_revenue_kopecks,
            fact.main_revenue_kopecks,
            fact.redemptions_revenue_kopecks,
            fact.late_correction_revenue_kopecks,
            fact.unknown_revenue_kopecks,
            fact.sales_units,
            fact.returns_units,
            fact.net_units,
            fact.commission_kopecks,
            fact.logistics_kopecks,
            fact.storage_kopecks,
            fact.acceptance_kopecks,
            penalty,
            deduction,
            fact.additional_payment_kopecks,
            finance_other,
            compensation,
            fact.acquiring_kopecks,
            finance_expenses,
            cost_state,
            cost_evidence_status,
            cogs,
            settlement_profit,
            economics_state,
            economics_evidence_status,
            tax,
            other_expenses,
            profit_before_ads_and_loyalty,
            advertising_spend,
            profit_before_loyalty,
            cashback_amount,
            cashback_discount,
            cashback_commission_change,
            loyalty_net_cost,
            profit_after_loyalty,
            sales_class,
            None,
            None,
            None,
            blockers,
        )

    @staticmethod
    def _summary(
        rows: list[AbcPnlRow],
        advertising_total: int | None,
        unattributed_advertising: int | None,
        *,
        empty_loyalty_complete: bool = False,
    ) -> AbcPnlSummary:
        if not rows:
            return _empty_summary(
                advertising_total,
                unattributed_advertising,
                loyalty_complete=empty_loyalty_complete,
            )

        def total(name: str) -> int:
            return sum(int(getattr(row, name)) for row in rows)

        costs_complete = all(row.cogs_kopecks is not None for row in rows)
        economics_complete = all(
            row.tax_kopecks is not None and row.other_expenses_kopecks is not None
            for row in rows
        )
        profit_complete = all(
            row.profit_before_ads_and_loyalty_kopecks is not None for row in rows
        )
        profit_before_ads = (
            total("profit_before_ads_and_loyalty_kopecks") if profit_complete else None
        )
        profit_before_loyalty = (
            profit_before_ads - advertising_total
            if profit_before_ads is not None and advertising_total is not None
            else None
        )
        cashback_amount_complete = all(
            row.cashback_amount_kopecks is not None for row in rows
        )
        cashback_discount_complete = all(
            row.cashback_discount_kopecks is not None for row in rows
        )
        cashback_commission_complete = all(
            row.cashback_commission_change_kopecks is not None for row in rows
        )
        loyalty_complete = all(
            row.loyalty_net_cost_kopecks is not None for row in rows
        )
        loyalty_net_cost = (
            total("loyalty_net_cost_kopecks") if loyalty_complete else None
        )
        return AbcPnlSummary(
            total("operation_count"),
            sum(row.nm_id is not None for row in rows),
            total("revenue_kopecks"),
            total("sales_revenue_kopecks"),
            total("returns_revenue_kopecks"),
            total("sales_units"),
            total("returns_units"),
            total("net_units"),
            total("commission_kopecks"),
            total("logistics_kopecks"),
            total("storage_kopecks"),
            total("acceptance_kopecks"),
            total("penalty_kopecks"),
            total("deduction_kopecks"),
            total("finance_other_expenses_kopecks"),
            total("compensation_kopecks"),
            total("acquiring_kopecks"),
            total("finance_expenses_kopecks"),
            total("cogs_kopecks") if costs_complete else None,
            total("settlement_profit_kopecks") if costs_complete else None,
            total("tax_kopecks") if economics_complete else None,
            total("other_expenses_kopecks") if economics_complete else None,
            profit_before_ads,
            advertising_total,
            unattributed_advertising,
            profit_before_loyalty,
            total("cashback_amount_kopecks") if cashback_amount_complete else None,
            total("cashback_discount_kopecks") if cashback_discount_complete else None,
            (
                total("cashback_commission_change_kopecks")
                if cashback_commission_complete
                else None
            ),
            loyalty_net_cost,
            (
                profit_before_loyalty - loyalty_net_cost
                if profit_before_loyalty is not None and loyalty_net_cost is not None
                else None
            ),
            None,
        )

    def get_page(
        self,
        marketplace_account_id: int,
        period: Period,
        *,
        limit: int,
        offset: int,
    ) -> AbcPnlPage:
        if isinstance(limit, bool) or not 1 <= limit <= 500:
            raise FinanceNormalizationError("limit must be between 1 and 500")
        if isinstance(offset, bool) or offset < 0:
            raise FinanceNormalizationError("offset must be non-negative")

        source = FinanceService(
            self.session, self.organization_id, now=self.now
        ).get_pnl_source(marketplace_account_id, period)
        advertising = AdvertisingService(
            self.session, self.organization_id, now=self.now
        ).get_pnl_source(marketplace_account_id, period)
        facts = list(source.facts)
        finance_nm_ids = {fact.nm_id for fact in facts if fact.nm_id is not None}
        facts.extend(
            _zero_finance_fact(nm_id)
            for nm_id in advertising.spend_by_nm
            if nm_id not in finance_nm_ids
        )
        loyalty_canonical = (
            source.snapshot is not None
            and source.snapshot.formula_version == "wb-finance-v2"
        )
        loyalty_complete = (
            loyalty_canonical
            and all(fact.loyalty_net_cost_kopecks is not None for fact in source.facts)
        )
        advertising_complete = (
            advertising.state in {"ready", "empty"}
            and advertising.total_spend_kopecks is not None
            and advertising.unattributed_spend_kopecks == 0
            and not advertising.blocker_ids
        )
        source_blockers = advertising.blocker_ids
        if not loyalty_complete:
            source_blockers = (
                *source_blockers,
                "WB_PNL_LOYALTY_NOT_CANONICAL",
            )
        costs_service = CostsService(self.session, self.organization_id, now=self.now)
        economics_service = EconomicsService(self.session, self.organization_id)
        cost_revision = costs_service.revision()
        economics_revision = economics_service.revision()
        if not facts:
            return AbcPnlPage(
                source.state,
                period,
                source.snapshot,
                advertising.snapshot,
                FORMULA_VERSION,
                cost_revision,
                economics_revision,
                source_blockers,
                self._summary(
                    [],
                    advertising.total_spend_kopecks,
                    advertising.unattributed_spend_kopecks,
                    empty_loyalty_complete=loyalty_complete,
                ),
                [],
                0,
                limit,
                offset,
            )

        nm_ids = [fact.nm_id for fact in facts if fact.nm_id is not None]
        mapping, ambiguous = CatalogService(
            self.session, self.organization_id, now=self.now
        ).resolve_wb_product_skus(marketplace_account_id, nm_ids)
        days = {day for _nm_id, day in source.daily_net_units}
        days.update(day for _nm_id, day in source.daily_economics_basis)
        day_ends = {day: _day_end(day) for day in sorted(days)}
        daily_by_nm: dict[int | None, list[tuple[datetime, int]]] = {}
        for (nm_id, day), units in source.daily_net_units.items():
            daily_by_nm.setdefault(nm_id, []).append((day_ends[day], units))
        economics_daily_by_nm: dict[
            int | None, list[tuple[datetime, FinancePnlDailyBasis]]
        ] = {}
        for (nm_id, day), basis in source.daily_economics_basis.items():
            economics_daily_by_nm.setdefault(nm_id, []).append((day_ends[day], basis))
        costs = costs_service.get_costs_for_points(
            [
                (mapping[nm_id], instant)
                for nm_id, daily in daily_by_nm.items()
                if nm_id in mapping
                for instant, _units in daily
            ]
        )
        policies = economics_service.get_policies_for_points(
            [
                (mapping[nm_id], instant)
                for nm_id, daily in economics_daily_by_nm.items()
                if nm_id in mapping and nm_id not in ambiguous
                for instant, _basis in daily
            ]
        )
        ranked = sorted(
            (fact for fact in facts if fact.nm_id is not None),
            key=lambda fact: (
                -fact.revenue_kopecks,
                -fact.net_units,
                fact.nm_id or 0,
            ),
        )
        sales_classes = {
            fact.nm_id: _sales_letter(index, len(ranked))
            for index, fact in enumerate(ranked)
        }
        rows: list[AbcPnlRow] = []
        for fact in facts:
            sku_id = mapping.get(fact.nm_id) if fact.nm_id is not None else None
            cogs, cost_state, cost_evidence, cost_blockers = self._cost_result(
                fact,
                catalog_sku_id=sku_id,
                ambiguous=fact.nm_id in ambiguous,
                daily=daily_by_nm.get(fact.nm_id, []),
                costs=costs,
            )
            tax, other, economics_state, economics_evidence, economics_blockers = (
                self._economics_result(
                    fact,
                    catalog_sku_id=sku_id,
                    ambiguous=fact.nm_id in ambiguous,
                    daily=economics_daily_by_nm.get(fact.nm_id, []),
                    policies=policies,
                )
            )
            rows.append(
                self._row(
                    fact,
                    sku_id,
                    cogs,
                    cost_state,
                    cost_evidence,
                    tax,
                    other,
                    economics_state,
                    economics_evidence,
                    (
                        advertising.spend_by_nm.get(fact.nm_id, 0)
                        if advertising_complete
                        else None
                    ),
                    loyalty_canonical,
                    sales_classes.get(fact.nm_id),
                    (*cost_blockers, *economics_blockers),
                )
            )
        rows.sort(
            key=lambda row: (
                -row.revenue_kopecks,
                row.nm_id is None,
                row.nm_id or 0,
            )
        )
        upstream_blockers = tuple(
            dict.fromkeys(
                (
                    *source_blockers,
                    *(blocker for row in rows for blocker in row.blocker_ids),
                )
            )
        )
        page_blockers = (
            (*upstream_blockers, "WB_PNL_CLASSIFICATION_NOT_CANONICAL")
            if not upstream_blockers
            and all(row.profit_after_loyalty_kopecks is not None for row in rows)
            else upstream_blockers
        )
        state: FinanceSourceState = (
            source.state
            if source.state in {"future", "missing", "empty"}
            else "partial"
        )
        return AbcPnlPage(
            state,
            period,
            source.snapshot,
            advertising.snapshot,
            FORMULA_VERSION,
            cost_revision,
            economics_revision,
            page_blockers,
            self._summary(
                rows,
                advertising.total_spend_kopecks,
                advertising.unattributed_spend_kopecks,
            ),
            rows[offset : offset + limit],
            len(rows),
            limit,
            offset,
        )
