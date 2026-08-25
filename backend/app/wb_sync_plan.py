from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from math import ceil
from typing import Literal
from zoneinfo import ZoneInfo


SyncSource = Literal[
    "goods",
    "content",
    "promotions",
    "stocks",
    "period-stats",
    "finance",
    "ads",
    "baskets",
]

NIGHTLY_SYNC_TIMEZONE = "Europe/Moscow"
NIGHTLY_SYNC_START_HOUR = 23
NIGHTLY_SYNC_END_HOUR = 7


@dataclass(frozen=True)
class SalesFunnelEstimate:
    request_count: int
    estimated_seconds: int
    explanation: str


@dataclass(frozen=True)
class WbSyncProfile:
    profile_id: str
    label: str
    window_kind: str
    cadence_minutes: int | None
    date_from: date
    date_to: date
    sources: tuple[SyncSource, ...]
    baskets_daily_detail: bool = False
    notes: tuple[str, ...] = ()

    @property
    def period_days(self) -> int:
        return max(1, (self.date_to - self.date_from).days + 1)

    def as_status_meta(self, *, sku_count: int | None = None) -> dict[str, object]:
        estimate = estimate_profile(self, sku_count=sku_count or 0)
        return {
            "syncProfile": self.profile_id,
            "syncProfileLabel": self.label,
            "windowKind": self.window_kind,
            "cadenceMinutes": self.cadence_minutes,
            "dateFrom": self.date_from.isoformat(),
            "dateTo": self.date_to.isoformat(),
            "periodDays": self.period_days,
            "sources": list(self.sources),
            "basketsDailyDetail": self.baskets_daily_detail,
            "estimatedRequests": estimate.request_count,
            "estimatedSeconds": estimate.estimated_seconds,
            "estimateExplanation": estimate.explanation,
        }


def _profile(
    profile_id: str,
    label: str,
    window_kind: str,
    as_of: date,
    period_days: int,
    sources: tuple[SyncSource, ...],
    *,
    cadence_minutes: int | None = None,
    baskets_daily_detail: bool = False,
    notes: tuple[str, ...] = (),
) -> WbSyncProfile:
    return WbSyncProfile(
        profile_id=profile_id,
        label=label,
        window_kind=window_kind,
        cadence_minutes=cadence_minutes,
        date_from=as_of - timedelta(days=period_days - 1),
        date_to=as_of,
        sources=sources,
        baskets_daily_detail=baskets_daily_detail,
        notes=notes,
    )


def historical_sync_as_of(now: datetime | None = None) -> date:
    resolved_now = now or datetime.now(timezone.utc)
    if resolved_now.tzinfo is None:
        resolved_now = resolved_now.replace(tzinfo=timezone.utc)
    return resolved_now.astimezone(ZoneInfo(NIGHTLY_SYNC_TIMEZONE)).date() - timedelta(days=1)


def nightly_sync_window_state(now_utc: datetime | None = None) -> dict[str, object]:
    now = now_utc or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    local_now = now.astimezone(ZoneInfo(NIGHTLY_SYNC_TIMEZONE))
    start_hour = NIGHTLY_SYNC_START_HOUR
    end_hour = NIGHTLY_SYNC_END_HOUR
    active = start_hour <= local_now.hour < end_hour if start_hour < end_hour else local_now.hour >= start_hour or local_now.hour < end_hour
    if active:
        next_run = local_now
    elif local_now.hour < start_hour:
        next_run = local_now.replace(hour=start_hour, minute=0, second=0, microsecond=0)
    else:
        next_run = (local_now + timedelta(days=1)).replace(hour=start_hour, minute=0, second=0, microsecond=0)
    return {
        "active": active,
        "timezone": NIGHTLY_SYNC_TIMEZONE,
        "localNow": local_now.isoformat(),
        "windowStartHour": start_hour,
        "windowEndHour": end_hour,
        "nextRunAt": next_run.astimezone(timezone.utc),
    }


def next_nightly_sync_at(now_utc: datetime | None = None, *, not_before: datetime | None = None) -> datetime:
    now = now_utc or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    cursor = now
    if not_before is not None:
        cursor = max(cursor, not_before if not_before.tzinfo else not_before.replace(tzinfo=timezone.utc))
    state = nightly_sync_window_state(cursor)
    if state["active"]:
        return cursor.astimezone(timezone.utc)
    return state["nextRunAt"]  # type: ignore[return-value]


def onboarding_sync_profiles(*, as_of: date) -> tuple[WbSyncProfile, ...]:
    onboarding_sources: tuple[SyncSource, ...] = (
        "goods",
        "content",
        "stocks",
        "period-stats",
        "finance",
        "ads",
        "baskets",
    )
    return (
        _profile(
            "onboarding-7d",
            "Первичная загрузка 7 дней",
            "onboarding",
            as_of,
            7,
            onboarding_sources,
            baskets_daily_detail=True,
            notes=("Fast first usable repricer/report cache.",),
        ),
        _profile(
            "onboarding-30d",
            "Первичная загрузка 30 дней",
            "onboarding",
            as_of,
            30,
            onboarding_sources,
            baskets_daily_detail=True,
            notes=("Main working analytical window.",),
        ),
    )


def periodic_sync_profiles(*, as_of: date) -> tuple[WbSyncProfile, ...]:
    return (
        _profile(
            "hourly-operational",
            "Оперативные заказы и продажи",
            "incremental",
            as_of,
            2,
            ("goods", "period-stats"),
            cadence_minutes=60,
        ),
        _profile(
            "sales-funnel-incremental",
            "Воронка продаж сегодня и вчера",
            "incremental",
            as_of,
            2,
            ("baskets",),
            cadence_minutes=120,
        ),
        _profile(
            "stock-ads-incremental",
            "Остатки и реклама",
            "incremental",
            as_of,
            3,
            ("stocks", "ads"),
            cadence_minutes=180,
        ),
        _profile(
            "finance-recent",
            "Финансы за 7 дней",
            "incremental",
            as_of,
            7,
            ("finance",),
            cadence_minutes=360,
        ),
    )


def nightly_reconciliation_profile(*, as_of: date) -> WbSyncProfile:
    return _profile(
        "nightly-30d-reconcile",
        "Ночная сверка 30 дней",
        "nightly",
        as_of,
        30,
        ("period-stats", "finance", "ads", "baskets"),
        cadence_minutes=1440,
        notes=("Runs outside user interaction; daily detail can be queued separately.",),
    )


def nightly_baskets_detail_profiles(*, as_of: date, chunk_days: int = 15) -> tuple[WbSyncProfile, ...]:
    base = nightly_reconciliation_profile(as_of=as_of)
    safe_chunk_days = max(1, int(chunk_days))
    profiles: list[WbSyncProfile] = []
    cursor = base.date_from
    index = 1
    while cursor <= base.date_to:
        chunk_to = min(cursor + timedelta(days=safe_chunk_days - 1), base.date_to)
        profiles.append(
            WbSyncProfile(
                profile_id=f"nightly-30d-baskets-detail-{index}",
                label=f"Ночная детализация корзин {index}",
                window_kind="nightly",
                cadence_minutes=base.cadence_minutes,
                date_from=cursor,
                date_to=chunk_to,
                sources=("baskets",),
                baskets_daily_detail=True,
                notes=("Loads daily basket detail in smaller nightly chunks.",),
            )
        )
        cursor = chunk_to + timedelta(days=1)
        index += 1
    return tuple(profiles)


def estimate_sales_funnel(
    *,
    sku_count: int,
    period_days: int,
    include_daily_detail: bool,
    batch_size: int = 1000,
    request_interval_seconds: int = 18,
) -> SalesFunnelEstimate:
    batches = max(1, ceil(max(0, sku_count) / batch_size))
    windows = 1 + (max(1, period_days) if include_daily_detail else 0)
    request_count = batches * windows
    detail = f" + {period_days} daily detail windows" if include_daily_detail else ""
    return SalesFunnelEstimate(
        request_count=request_count,
        estimated_seconds=request_count * request_interval_seconds,
        explanation=f"{batches} SKU batches * (1 aggregate{detail})",
    )


def estimate_profile(profile: WbSyncProfile, *, sku_count: int = 0) -> SalesFunnelEstimate:
    if "baskets" not in profile.sources:
        return SalesFunnelEstimate(request_count=0, estimated_seconds=0, explanation="No Sales Funnel requests")
    return estimate_sales_funnel(
        sku_count=sku_count,
        period_days=profile.period_days,
        include_daily_detail=profile.baskets_daily_detail,
    )
