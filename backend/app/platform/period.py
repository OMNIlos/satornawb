from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from typing import Literal
from zoneinfo import ZoneInfo

MOSCOW = ZoneInfo("Europe/Moscow")
PeriodTemporalState = Literal["complete", "partial", "future"]


class PeriodValidationError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class Period:
    date_from: date
    date_to: date

    def __post_init__(self) -> None:
        if self.date_from > self.date_to:
            raise PeriodValidationError("dateFrom must be before or equal to dateTo")
        if self.days > 90:
            raise PeriodValidationError("date range must be between 1 and 90 days")

    @classmethod
    def resolve(
        cls,
        *,
        period_days: int,
        date_from: date | None = None,
        date_to: date | None = None,
        now: datetime | None = None,
    ) -> Period:
        if (date_from is None) != (date_to is None):
            raise PeriodValidationError("dateFrom and dateTo must both be provided")
        if date_from is not None and date_to is not None:
            return cls(date_from, date_to)
        if not 1 <= period_days <= 90:
            raise PeriodValidationError("periodDays must be between 1 and 90")
        today = _aware(now or datetime.now(timezone.utc)).astimezone(MOSCOW).date()
        return cls(today - timedelta(days=period_days - 1), today)

    @property
    def days(self) -> int:
        return (self.date_to - self.date_from).days + 1

    @property
    def start_at(self) -> datetime:
        return datetime.combine(self.date_from, time.min, MOSCOW).astimezone(
            timezone.utc
        )

    @property
    def end_exclusive_at(self) -> datetime:
        return datetime.combine(
            self.date_to + timedelta(days=1), time.min, MOSCOW
        ).astimezone(timezone.utc)

    @property
    def cache_key(self) -> str:
        return f"{self.date_from.isoformat()}_{self.date_to.isoformat()}"

    def temporal_state(self, now: datetime | None = None) -> PeriodTemporalState:
        today = _aware(now or datetime.now(timezone.utc)).astimezone(MOSCOW).date()
        if self.date_from > today:
            return "future"
        if self.date_to >= today:
            return "partial"
        return "complete"


def _aware(value: datetime) -> datetime:
    return (
        value
        if value.tzinfo is not None and value.utcoffset() is not None
        else value.replace(tzinfo=timezone.utc)
    )
