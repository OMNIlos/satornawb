from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from datetime import date
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.infra.db import get_session_factory, set_tenant_context
from app.platform.advertising.orm import WbAdvertisingSyncRunRow
from app.platform.advertising.service import AdvertisingService
from app.platform.integrations.orm import MarketplaceAccountRow
from app.platform.period import Period, PeriodValidationError
from app.repricer_cache.orm import WbRepricerSourceCacheRow


class AdvertisingBackfillError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class AdvertisingBackfillResult:
    marketplace_account_id: int
    inserted_runs: int
    finance_total_kopecks: int
    fullstats_total_kopecks: int


def _cache(
    session: Session, organization_id: int, source_key: str
) -> WbRepricerSourceCacheRow:
    row = session.scalar(
        select(WbRepricerSourceCacheRow).where(
            WbRepricerSourceCacheRow.organization_id == organization_id,
            WbRepricerSourceCacheRow.source_key == source_key,
        )
    )
    if row is None or not isinstance(row.payload, dict):
        raise AdvertisingBackfillError(f"exact cache {source_key} is missing")
    return row


def _validate_period(payload: dict[str, Any], period: Period) -> None:
    if (
        str(payload.get("dateFrom"))[:10] != period.date_from.isoformat()
        or str(payload.get("dateTo"))[:10] != period.date_to.isoformat()
    ):
        raise AdvertisingBackfillError("exact cache period mismatch")


def _signed_integer(value: Any) -> int:
    if isinstance(value, bool):
        raise AdvertisingBackfillError("invalid finance advertising total")
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.strip().lstrip("-").isdigit():
        return int(value)
    raise AdvertisingBackfillError("invalid finance advertising total")


def _finance_total(payload: dict[str, Any]) -> int:
    aggregates = payload.get("aggregates")
    if not isinstance(aggregates, dict):
        raise AdvertisingBackfillError("finance aggregates are missing")
    total = 0
    for row in aggregates.values():
        if not isinstance(row, dict):
            raise AdvertisingBackfillError("invalid finance aggregate")
        total += _signed_integer(row.get("adSpendKopecks", 0))
    return total


def _run_backfill(
    session: Session, organization_id: int, period: Period
) -> AdvertisingBackfillResult:
    set_tenant_context(session, organization_id)
    account_ids = session.scalars(
        select(MarketplaceAccountRow.marketplace_account_id).where(
            MarketplaceAccountRow.organization_id == organization_id,
            MarketplaceAccountRow.marketplace == "wb",
            MarketplaceAccountRow.status == "connected",
        )
    ).all()
    if len(account_ids) != 1:
        raise AdvertisingBackfillError(
            "connected WB account is missing"
            if not account_ids
            else "connected WB account is ambiguous"
        )
    account_id = int(account_ids[0])
    finance_key = f"finance_{period.cache_key}"
    ads_key = f"ads_{period.cache_key}"
    finance_cache = _cache(session, organization_id, finance_key)
    ads_cache = _cache(session, organization_id, ads_key)
    finance_payload = dict(finance_cache.payload)
    ads_payload = dict(ads_cache.payload)
    _validate_period(finance_payload, period)
    _validate_period(ads_payload, period)
    finance_total = _finance_total(finance_payload)
    before = int(
        session.scalar(
            select(func.count())
            .select_from(WbAdvertisingSyncRunRow)
            .where(
                WbAdvertisingSyncRunRow.organization_id == organization_id,
                WbAdvertisingSyncRunRow.marketplace_account_id == account_id,
            )
        )
        or 0
    )

    service = AdvertisingService(session, organization_id)
    service.ingest_finance_aggregate_only(
        account_id,
        period,
        finance_total,
        source_reference=f"legacy_cache:{finance_key}",
        observed_at=finance_cache.fetched_at,
    )
    ads_snapshot = service.ingest_payload(
        account_id,
        period,
        "ads_fullstats",
        ads_payload,
        source_reference=f"legacy_cache:{ads_key}",
        observed_at=ads_cache.fetched_at,
    )
    after = int(
        session.scalar(
            select(func.count())
            .select_from(WbAdvertisingSyncRunRow)
            .where(
                WbAdvertisingSyncRunRow.organization_id == organization_id,
                WbAdvertisingSyncRunRow.marketplace_account_id == account_id,
            )
        )
        or 0
    )
    return AdvertisingBackfillResult(
        marketplace_account_id=account_id,
        inserted_runs=after - before,
        finance_total_kopecks=finance_total,
        fullstats_total_kopecks=ads_snapshot.source_total_spend_kopecks,
    )


def backfill_advertising(
    organization_id: int,
    period: Period,
    *,
    session: Session | None = None,
) -> AdvertisingBackfillResult:
    if organization_id < 1:
        raise AdvertisingBackfillError("organization must be positive")
    if session is not None:
        return _run_backfill(session, organization_id, period)
    with get_session_factory()() as owned_session:
        return _run_backfill(owned_session, organization_id, period)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Backfill canonical WB advertising")
    parser.add_argument("--organization-id", type=int, required=True)
    parser.add_argument("--date-from", type=date.fromisoformat, required=True)
    parser.add_argument("--date-to", type=date.fromisoformat, required=True)
    args = parser.parse_args(argv)
    try:
        result = backfill_advertising(
            args.organization_id, Period(args.date_from, args.date_to)
        )
    except (AdvertisingBackfillError, PeriodValidationError) as exc:
        print(
            json.dumps(
                {"state": "failed", "errorCode": type(exc).__name__},
                sort_keys=True,
            )
        )
        return 1
    print(json.dumps({"state": "ready", **asdict(result)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
