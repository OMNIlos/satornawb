"""Legacy behavior fixtures for the future immutable calculation-context move.

These tests call calculation/guard functions only. They do not approve the
business formulas or invoke draft/apply, routes, workers, storage, or providers.
"""

from copy import deepcopy
from dataclasses import replace
import socket
from types import SimpleNamespace

import pytest


@pytest.fixture
def legacy(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("characterization must not perform I/O")

    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket.socket, "connect_ex", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    from app import repricer_execution as execution
    from app import repricer_sprint_b as sprint
    from app.repricer_settings import RepricerGuardLimits

    monkeypatch.setattr(execution, "ALGORITHM_SETTINGS_STATE", {})
    monkeypatch.setattr(execution, "get_repricer_guard_limits", RepricerGuardLimits)
    monkeypatch.setattr(sprint, "get_repricer_guard_limits", RepricerGuardLimits)
    monkeypatch.setattr(sprint, "_daily_reference_price", lambda article, fallback: fallback)
    monkeypatch.setattr(sprint, "build_repricer_discovery_readiness", lambda: SimpleNamespace(
        canUnblockPriceGuard=True, blockingIds=[],
    ))
    for name in ("apply_approved_draft", "approve_draft", "create_price_draft",
                 "get_source_cache", "save_source_cache", "append_execution_run",
                 "upsert_pending_price_approvals"):
        monkeypatch.setattr(execution, name, forbidden)
    monkeypatch.setattr(sprint, "run_price_apply", forbidden)
    return execution, sprint


@pytest.mark.parametrize("completion,want", [
    (0, 70000), (9.99, 70000), (10, 85000), (20, 87000), (30, 90000),
    (40, 92000), (50, 94000), (60, 96000), (70, 97000), (80, 98000),
    (90, 99000), (100, 100000), (109.99, 100000), (110, 101000),
    (120, 102000), (130, 105000), (140, 110000),
])
def test_plan_fact_band_boundaries_preserve_exact_kopecks(legacy, completion, want):
    execution, _ = legacy
    price, _ = execution._plan_fact_price_from_completion(
        100000, 70000, completion, label="synthetic",
    )
    assert price == want


@pytest.mark.parametrize("current,delta,want", [
    (100005, 10, 110006), (100005, -10, 90004), (1, -99, 1),
])
def test_legacy_percentage_rounding_preserves_half_even_and_positive_floor(
    legacy, current, delta, want,
):
    assert legacy[0]._apply_pct(current, delta) == want


@pytest.mark.parametrize("candidate,current,settings,want", [
    (201300, 190000, {}, 201300),
    (201300, 190000, {"beautyPriceEnabled": True}, 199000),
    (201300, 200000, {"beautyPriceEnabled": True}, 201300),
    (201300, 190000, {"beautyPriceEnabled": True, "beautyPriceMaxChangeKopecks": 2000}, 201300),
    (201300, 190000, {"beautyPriceEnabled": True, "beautyPriceMaxChangePct": 1}, 201300),
    (201300, 190000, {"beautyPriceEnabled": True, "beautyPriceTemplate": "x99"}, 199900),
])
def test_pretty_price_limits_do_not_reverse_an_increase(legacy, candidate, current, settings, want):
    original = deepcopy(settings)
    assert legacy[0]._apply_price_rounding(candidate, current=current, settings=settings)[0] == want
    assert settings == original


@pytest.mark.parametrize("candidate,minimum,maximum,want", [
    (120000, 70000, None, 106000), (80000, 70000, None, 94000),
    (95000, 97000, None, 97000), (105000, 70000, 103000, 103000),
    (100000, 70000, None, 100000),
])
def test_clamp_preserves_update_step_and_price_bounds(legacy, candidate, minimum, maximum, want):
    assert legacy[0]._clamp_candidate_price(
        current=100000, recommended=candidate, min_price=minimum, p_max=maximum,
    )[0] == want


def test_day_cap_is_applied_after_update_cap(legacy, monkeypatch):
    execution, _ = legacy
    limits = execution.get_repricer_guard_limits()
    monkeypatch.setattr(execution, "get_repricer_guard_limits", lambda: replace(
        limits, per_update_step_pct=10, per_day_step_pct=3,
    ))
    assert execution._clamp_candidate_price(
        current=100000, recommended=120000, min_price=70000, p_max=None,
    )[0] == 103000


@pytest.mark.parametrize("baskets,want", [(0, 97000), (5, 97000), (6, 100000), (29, 100000), (30, 103000)])
def test_basket_thresholds_preserve_explicit_zero_and_boundaries(legacy, baskets, want):
    execution, _ = legacy
    execution.ALGORITHM_SETTINGS_STATE.update({"cartHighBasketsThreshold": 30, "cartLowBasketsThreshold": 5})
    row = {"meta": {"currentPriceKopecks": 100000, "basketsLast7d": 100},
           "analytics": {"baskets": baskets}}
    original = deepcopy(row)
    assert execution._basket_threshold_recommended_price(row)[0] == want
    assert row == original


def test_period_scaling_uses_selected_fact_period_without_mutating_row(legacy):
    execution, _ = legacy
    execution.ALGORITHM_SETTINGS_STATE.update({"basketNormPeriodDays": 7})
    row = {"meta": {"basketNorm": 70, "currentPriceKopecks": 100000},
           "analytics": {"ordersUnits": 140, "periodDays": 14}}
    original = deepcopy(row)
    assert execution._plan_fact_pct(row) == 100
    assert execution._daily_plan_orders(row) == 10
    assert row == original


def normalized(sprint, **changes):
    values = dict(articleId="synthetic-sku", nmId=123, currentSellerPriceKopecks=100000,
                  currentSppPct=20, candidateSellerPriceKopecks=100000,
                  cogsKopecks=40000, commissionPct=20, logisticsKopecks=5000,
                  buyoutPct=80, stockUnits=10, minPriceKopecks=70000,
                  predictedMarginKopecks=30000)
    values.update(changes)
    return sprint.NormalizedEconomics(**values)


def guard(sprint, value, *, source="fresh", pmin_valid=True, margin="fresh"):
    return sprint._evaluate_guards(
        value.articleId, SimpleNamespace(), SimpleNamespace(sourceStatus=source), value,
        SimpleNamespace(isValid=pmin_valid, reasons=[]), SimpleNamespace(sourceStatus=margin),
    )


@pytest.mark.parametrize("field,value,code", [
    ("currentSppPct", None, "spp_missing"), ("cogsKopecks", None, "cogs_missing"),
    ("commissionPct", None, "commission_missing"), ("logisticsKopecks", None, "logistics_missing"),
    ("buyoutPct", None, "buyout_missing"), ("stockUnits", None, "stock_missing"),
    ("stockUnits", 0, "stock_oos"), ("predictedMarginKopecks", -1, "negative_margin"),
    ("candidateSellerPriceKopecks", 106001, "per_update_step_exceeded"),
])
def test_guard_missing_inputs_and_unsafe_outcomes_block(legacy, field, value, code):
    _, sprint = legacy
    report = guard(sprint, normalized(sprint, **{field: value}))
    assert report.canApply is False
    assert "WB-23" in report.blockers
    assert code in {trigger.code for trigger in report.triggers}


@pytest.mark.parametrize("source", ["stale", "blocked"])
def test_stale_or_blocked_sources_prevent_apply(legacy, source):
    sprint = legacy[1]
    report = guard(sprint, normalized(sprint), source=source)
    assert not report.canApply
    assert "source_stale_or_blocked" in {trigger.code for trigger in report.triggers}


def test_exact_update_limit_is_allowed_but_daily_history_still_blocks(legacy, monkeypatch):
    sprint = legacy[1]
    value = normalized(sprint, candidateSellerPriceKopecks=106000)
    assert guard(sprint, value).canApply
    monkeypatch.setattr(sprint, "_daily_reference_price", lambda article, fallback: 80000)
    report = guard(sprint, value)
    assert not report.canApply
    assert {trigger.code for trigger in report.triggers} == {"per_day_step_exceeded"}


def test_promo_requires_minimum_and_candidate_must_respect_it(legacy):
    sprint = legacy[1]
    report = guard(sprint, normalized(sprint, promoActive=True, minPriceKopecks=None))
    assert not report.canApply
    assert "promo_min_price_missing" in {trigger.code for trigger in report.triggers}
    report = guard(sprint, normalized(sprint, minPriceKopecks=101000))
    assert not report.canApply
    assert "candidate_below_min_price" in {trigger.code for trigger in report.triggers}


def test_discovery_pmin_and_margin_blockers_are_preserved(legacy, monkeypatch):
    sprint = legacy[1]
    monkeypatch.setattr(sprint, "build_repricer_discovery_readiness", lambda: SimpleNamespace(
        canUnblockPriceGuard=False, blockingIds=["WB-22", "WB-23"],
    ))
    report = guard(sprint, normalized(sprint), pmin_valid=False, margin="blocked")
    assert not report.canApply
    assert report.blockers == ["WB-22", "WB-23"]
    assert {trigger.code for trigger in report.triggers} == {
        "discovery_not_ready", "pmin_pmax_block", "margin_preview_blocked",
    }


def test_legacy_margin_characterization_does_not_add_tax_to_existing_formula(legacy):
    sprint = legacy[1]
    economics = sprint.DraftEconomicsInput(
        cogsKopecks=40000, commissionPct=20, logisticsKopecks=5000,
        storageKopecks=1000, taxKopecks=9000,
    )
    assert sprint._predict_margin(80000, economics) == (18000, 22.5)
    assert sprint._predict_margin(None, economics) == (None, None)
