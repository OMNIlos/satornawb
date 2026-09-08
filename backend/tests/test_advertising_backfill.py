from __future__ import annotations

import importlib
import json
from datetime import date, datetime, timezone

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.cabinet.orm import LkOrganizationRow
from app.infra.models import Base
from app.platform.advertising.orm import (
    WbAdvertisingFactRow,
    WbAdvertisingSyncRunRow,
)
from app.platform.integrations.orm import MarketplaceAccountRow
from app.platform.period import Period
from app.repricer_cache.orm import WbRepricerSourceCacheRow

NOW = datetime(2026, 8, 26, 3, 50, tzinfo=timezone.utc)
PERIOD = Period(date(2026, 8, 17), date(2026, 8, 23))


def _module():
    try:
        return importlib.import_module("app.platform.advertising.backfill")
    except ModuleNotFoundError:
        pytest.fail("canonical advertising backfill is missing")


def _fullstats_payload() -> dict[str, object]:
    metrics = {
        "adSpendKopecks": 111_076,
        "adImpressions": 1_000,
        "adClicks": 100,
        "adCartAdds": 30,
        "adOrders": 20,
        "adRevenueKopecks": 456_000,
    }
    return {
        "aggregates": {"453200669": dict(metrics)},
        "dailyAggregates": {
            day.isoformat(): ({"453200669": dict(metrics)} if day.day == 20 else {})
            for day in (
                date(2026, 8, 17),
                date(2026, 8, 18),
                date(2026, 8, 19),
                date(2026, 8, 20),
                date(2026, 8, 21),
                date(2026, 8, 22),
                date(2026, 8, 23),
            )
        },
        "totals": dict(metrics),
        "dateFrom": "2026-08-17",
        "dateTo": "2026-08-23",
    }


@pytest.fixture
def session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as db:
        db.add_all(
            [
                LkOrganizationRow(organization_id=1, slug="one", name="One"),
                MarketplaceAccountRow(
                    marketplace_account_id=31,
                    organization_id=1,
                    marketplace="wb",
                    external_account_id="wb-one",
                    status="connected",
                ),
                WbRepricerSourceCacheRow(
                    organization_id=1,
                    source_key=f"finance_{PERIOD.cache_key}",
                    payload={
                        "aggregates": {
                            "453200669": {"adSpendKopecks": 600_000},
                            "987654321": {"adSpendKopecks": 381_000},
                        },
                        "dateFrom": "2026-08-17",
                        "dateTo": "2026-08-23",
                    },
                    fetched_at=NOW,
                ),
                WbRepricerSourceCacheRow(
                    organization_id=1,
                    source_key=f"ads_{PERIOD.cache_key}",
                    payload=_fullstats_payload(),
                    fetched_at=NOW,
                ),
            ]
        )
        db.commit()
        yield db


def test_backfill_uses_retained_totals_without_allocating_finance(
    session: Session,
) -> None:
    module = _module()

    result = module.backfill_advertising(1, PERIOD, session=session)

    assert result.finance_total_kopecks == 981_000
    assert result.fullstats_total_kopecks == 111_076
    finance_run = session.scalar(
        select(WbAdvertisingSyncRunRow).where(
            WbAdvertisingSyncRunRow.source_kind == "finance_promotion"
        )
    )
    assert finance_run is not None
    assert finance_run.evidence_status == "aggregate_only"
    fullstats_run = session.scalar(
        select(WbAdvertisingSyncRunRow).where(
            WbAdvertisingSyncRunRow.source_kind == "ads_fullstats"
        )
    )
    assert fullstats_run is not None
    assert fullstats_run.evidence_status == "derived_legacy"
    facts = session.scalars(
        select(WbAdvertisingFactRow).where(
            WbAdvertisingFactRow.sync_run_id == finance_run.sync_run_id
        )
    ).all()
    assert [
        (fact.nm_id, fact.attribution_level, fact.spend_kopecks) for fact in facts
    ] == [(None, "unknown", 981_000)]


def test_backfill_is_idempotent(session: Session) -> None:
    module = _module()

    first = module.backfill_advertising(1, PERIOD, session=session)
    second = module.backfill_advertising(1, PERIOD, session=session)

    assert first.inserted_runs == 2
    assert second.inserted_runs == 0
    assert (
        session.scalar(select(func.count()).select_from(WbAdvertisingSyncRunRow)) == 2
    )


def test_backfill_refuses_non_exact_cache_keys(session: Session) -> None:
    module = _module()
    session.query(WbRepricerSourceCacheRow).delete()
    session.add_all(
        [
            WbRepricerSourceCacheRow(
                organization_id=1,
                source_key="finance_7",
                payload={"aggregates": {}},
                fetched_at=NOW,
            ),
            WbRepricerSourceCacheRow(
                organization_id=1,
                source_key="ads_7",
                payload=_fullstats_payload(),
                fetched_at=NOW,
            ),
        ]
    )
    session.commit()

    with pytest.raises(module.AdvertisingBackfillError, match="exact cache"):
        module.backfill_advertising(1, PERIOD, session=session)


def test_backfill_cli_emits_stable_json(monkeypatch, capsys) -> None:
    module = _module()
    monkeypatch.setattr(
        module,
        "backfill_advertising",
        lambda *_args, **_kwargs: module.AdvertisingBackfillResult(
            marketplace_account_id=31,
            inserted_runs=2,
            finance_total_kopecks=981_000,
            fullstats_total_kopecks=111_076,
        ),
    )

    exit_code = module.main(
        [
            "--organization-id",
            "1",
            "--date-from",
            "2026-08-17",
            "--date-to",
            "2026-08-23",
        ]
    )

    assert exit_code == 0
    assert json.loads(capsys.readouterr().out) == {
        "finance_total_kopecks": 981_000,
        "fullstats_total_kopecks": 111_076,
        "inserted_runs": 2,
        "marketplace_account_id": 31,
        "state": "ready",
    }
