from __future__ import annotations

from datetime import date, datetime, timezone

import pytest

from app.platform.period import Period, PeriodValidationError


def test_period_uses_inclusive_moscow_dates_and_exclusive_utc_end() -> None:
    now = datetime(2026, 9, 1, 20, 30, tzinfo=timezone.utc)

    period = Period.resolve(period_days=7, now=now)

    assert (period.date_from, period.date_to, period.days) == (
        date(2026, 8, 26),
        date(2026, 9, 1),
        7,
    )
    assert period.start_at == datetime(2026, 8, 25, 21, tzinfo=timezone.utc)
    assert period.end_exclusive_at == datetime(2026, 9, 1, 21, tzinfo=timezone.utc)
    assert period.cache_key == "2026-08-26_2026-09-01"
    assert period.temporal_state(now) == "partial"


def test_explicit_period_has_the_same_identity_and_complete_future_states() -> None:
    now = datetime(2026, 9, 1, 12, tzinfo=timezone.utc)
    explicit = Period.resolve(
        period_days=30,
        date_from=date(2026, 8, 26),
        date_to=date(2026, 9, 1),
        now=now,
    )

    assert explicit.cache_key == Period.resolve(period_days=7, now=now).cache_key
    assert (
        Period(date(2026, 8, 17), date(2026, 8, 23)).temporal_state(now) == "complete"
    )
    assert Period(date(2026, 9, 2), date(2026, 9, 3)).temporal_state(now) == "future"


@pytest.mark.parametrize(
    ("date_from", "date_to", "message"),
    [
        (date(2026, 9, 1), None, "both"),
        (date(2026, 9, 2), date(2026, 9, 1), "before"),
        (date(2026, 1, 1), date(2026, 4, 1), "90"),
    ],
)
def test_period_rejects_ambiguous_or_invalid_ranges(
    date_from: date | None,
    date_to: date | None,
    message: str,
) -> None:
    with pytest.raises(PeriodValidationError, match=message):
        Period.resolve(period_days=7, date_from=date_from, date_to=date_to)
