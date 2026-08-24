from __future__ import annotations

from app.repricer_settings import get_repricer_guard_limits, is_auto_strategy_execution_allowed


def test_auto_execution_allowed_without_active_settings():
    assert is_auto_strategy_execution_allowed(force=False) is True


def test_guard_limits_defaults_when_settings_missing():
    limits = get_repricer_guard_limits()
    assert limits.per_update_step_pct == 6.0
    assert limits.per_day_step_pct == 20.0
