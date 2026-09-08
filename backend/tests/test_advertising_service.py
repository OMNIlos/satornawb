from __future__ import annotations

import importlib
from datetime import date, datetime, timezone

import pytest
from sqlalchemy import create_engine, event, func, select
from sqlalchemy.orm import Session

from app.cabinet.orm import LkOrganizationRow
from app.infra.models import Base
from app.platform.advertising.orm import (
    WbAdvertisingFactRow,
    WbAdvertisingSyncRunRow,
)
from app.platform.integrations.orm import MarketplaceAccountRow
from app.platform.period import Period

NOW = datetime(2026, 9, 1, 12, tzinfo=timezone.utc)
LATER = datetime(2026, 9, 1, 13, tzinfo=timezone.utc)
PERIOD = Period(date(2026, 8, 17), date(2026, 8, 23))


def _service_module():
    try:
        return importlib.import_module("app.platform.advertising.service")
    except ModuleNotFoundError:
        pytest.fail("canonical advertising service is missing")


@pytest.fixture
def session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:")

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(dbapi_connection, _connection_record) -> None:
        dbapi_connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.add_all(
            [
                LkOrganizationRow(organization_id=1, slug="one", name="One"),
                LkOrganizationRow(organization_id=2, slug="two", name="Two"),
                MarketplaceAccountRow(
                    marketplace_account_id=31,
                    organization_id=1,
                    marketplace="wb",
                    external_account_id="wb-one",
                    status="connected",
                ),
                MarketplaceAccountRow(
                    marketplace_account_id=32,
                    organization_id=2,
                    marketplace="wb",
                    external_account_id="wb-two",
                    status="connected",
                ),
            ]
        )
        db.commit()
        yield db


def fullstats_payload(*, spend_kopecks: int = 12_300) -> dict[str, object]:
    metrics = {
        "adSpendKopecks": spend_kopecks,
        "adImpressions": 100,
        "adClicks": 10,
        "adCartAdds": 3,
        "adOrders": 2,
        "adRevenueKopecks": 45_600,
        "source": "wb_ads_fullstats",
    }
    daily = {
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
    }
    return {
        "aggregates": {"453200669": dict(metrics)},
        "dailyAggregates": daily,
        "totals": {
            "adSpendKopecks": spend_kopecks,
            "adImpressions": 100,
            "adClicks": 10,
            "adCartAdds": 3,
            "adOrders": 2,
            "adRevenueKopecks": 45_600,
        },
        "count": 1,
        "campaignCount": 7,
        "dateFrom": "2026-08-17",
        "dateTo": "2026-08-23",
        "source": "wb_ads_fullstats",
    }


def finance_payload(*, deduction: str, nm_id: int | None = None) -> dict[str, object]:
    row: dict[str, object] = {
        "rrdId": 7,
        "bonusTypeName": "WB Продвижение",
        "deduction": deduction,
        "rrDate": "2026-08-23",
    }
    if nm_id is not None:
        row["nmId"] = nm_id
    return {"rows": [row], "dateFrom": "2026-08-17", "dateTo": "2026-08-23"}


def test_finance_promotion_keeps_signed_unattributed_row() -> None:
    module = _service_module()

    facts, total = module.normalize_finance_promotion(
        PERIOD, finance_payload(deduction="-12.34")
    )

    assert total == -1_234
    assert len(facts) == 1
    assert facts[0].nm_id is None
    assert facts[0].attribution_level == "unknown"


def test_finance_promotion_rejects_boolean_product_id() -> None:
    module = _service_module()

    with pytest.raises(module.AdvertisingNormalizationError, match="nmId"):
        module.normalize_finance_promotion(
            PERIOD, finance_payload(deduction="12.34", nm_id=False)
        )


def test_fullstats_normalization_reconciles_daily_aggregate_and_total() -> None:
    module = _service_module()

    facts, total = module.normalize_fullstats(PERIOD, fullstats_payload())

    assert total == 12_300
    assert len(facts) == 1
    assert facts[0].business_date == date(2026, 8, 20)
    assert facts[0].nm_id == 453200669
    assert facts[0].clicks == 10


def test_fullstats_normalization_rejects_a_total_mismatch() -> None:
    module = _service_module()
    payload = fullstats_payload()
    payload["totals"]["adSpendKopecks"] = 12_299

    with pytest.raises(module.AdvertisingNormalizationError, match="totals"):
        module.normalize_fullstats(PERIOD, payload)


def test_fullstats_normalization_rejects_aggregate_daily_mismatch() -> None:
    module = _service_module()
    payload = fullstats_payload()
    payload["aggregates"]["453200669"]["adSpendKopecks"] = 12_299
    payload["totals"]["adSpendKopecks"] = 12_299

    with pytest.raises(module.AdvertisingNormalizationError, match="daily"):
        module.normalize_fullstats(PERIOD, payload)


def test_fullstats_normalization_requires_every_period_day() -> None:
    module = _service_module()
    payload = fullstats_payload()
    del payload["dailyAggregates"]["2026-08-17"]

    with pytest.raises(module.AdvertisingNormalizationError, match="coverage"):
        module.normalize_fullstats(PERIOD, payload)


def test_fullstats_normalization_rejects_boolean_metrics() -> None:
    module = _service_module()
    payload = fullstats_payload()
    payload["dailyAggregates"]["2026-08-20"]["453200669"]["adClicks"] = False
    payload["aggregates"]["453200669"]["adClicks"] = False
    payload["totals"]["adClicks"] = False

    with pytest.raises(module.AdvertisingNormalizationError, match="adClicks"):
        module.normalize_fullstats(PERIOD, payload)


def test_repeated_snapshot_only_updates_observation(session: Session) -> None:
    module = _service_module()
    service = module.AdvertisingService(session, 1, now=lambda: NOW)

    first = service.ingest_payload(
        31,
        PERIOD,
        "ads_fullstats",
        fullstats_payload(),
        source_reference="ads_fixture",
        observed_at=NOW,
    )
    second = service.ingest_payload(
        31,
        PERIOD,
        "ads_fullstats",
        fullstats_payload(),
        source_reference="ads_fixture",
        observed_at=LATER,
    )

    assert second.sync_run_id == first.sync_run_id
    assert second.last_observed_at == LATER
    assert second.evidence_status == "derived_legacy"
    assert (
        session.scalar(select(func.count()).select_from(WbAdvertisingFactRow))
        == first.fact_count
    )


def test_finance_and_derived_fullstats_are_not_operational_sources(
    session: Session,
) -> None:
    module = _service_module()
    service = module.AdvertisingService(session, 1, now=lambda: NOW)
    service.ingest_payload(
        31,
        PERIOD,
        "ads_fullstats",
        fullstats_payload(),
        source_reference="ads_fixture",
        observed_at=NOW,
    )
    service.ingest_payload(
        31,
        PERIOD,
        "finance_promotion",
        finance_payload(deduction="9810.00"),
        source_reference="finance_fixture",
        observed_at=LATER,
    )

    source = service.get_pnl_source(31, PERIOD)

    assert source.state == "missing"
    assert source.snapshot is None
    assert source.source_kind is None
    assert source.total_spend_kopecks is None
    assert source.spend_by_nm == {}
    assert source.unattributed_spend_kopecks is None
    assert source.blocker_ids == ("WB_PNL_ADS_NOT_CANONICAL",)


def test_zero_finance_promotion_never_promotes_derived_fullstats(
    session: Session,
) -> None:
    module = _service_module()
    service = module.AdvertisingService(session, 1, now=lambda: NOW)
    service.ingest_payload(
        31,
        PERIOD,
        "finance_promotion",
        finance_payload(deduction="0"),
        source_reference="finance_fixture",
        observed_at=LATER,
    )
    service.ingest_payload(
        31,
        PERIOD,
        "ads_fullstats",
        fullstats_payload(),
        source_reference="ads_fixture",
        observed_at=NOW,
    )

    source = service.get_pnl_source(31, PERIOD)

    assert source.state == "missing"
    assert source.snapshot is None
    assert source.source_kind is None
    assert source.total_spend_kopecks is None


def test_source_selection_is_exact_period_only(session: Session) -> None:
    module = _service_module()
    service = module.AdvertisingService(session, 1, now=lambda: NOW)
    service.ingest_payload(
        31,
        Period(date(2026, 8, 17), date(2026, 8, 24)),
        "ads_fullstats",
        {
            **fullstats_payload(),
            "dailyAggregates": {
                **fullstats_payload()["dailyAggregates"],
                "2026-08-24": {},
            },
            "dateTo": "2026-08-24",
        },
        source_reference="wider_ads_fixture",
        observed_at=NOW,
    )

    source = service.get_pnl_source(31, PERIOD)

    assert source.state == "missing"
    assert source.snapshot is None


def test_unpublished_run_is_invisible(session: Session) -> None:
    module = _service_module()
    session.add(
        WbAdvertisingSyncRunRow(
            sync_run_id="unpublished",
            organization_id=1,
            marketplace_account_id=31,
            source_kind="ads_fullstats",
            date_from=PERIOD.date_from,
            date_to=PERIOD.date_to,
            source_reference="interrupted",
            snapshot_checksum="0" * 64,
            formula_version="wb-advertising-v1",
            source_total_spend_kopecks=0,
            fact_count=0,
            evidence_status="raw",
            is_materialized=False,
            captured_at=NOW,
            last_observed_at=NOW,
        )
    )
    session.commit()

    source = module.AdvertisingService(session, 1, now=lambda: NOW).get_pnl_source(
        31, PERIOD
    )

    assert source.state == "missing"
    assert source.snapshot is None


def test_account_scope_and_future_state(session: Session) -> None:
    module = _service_module()
    service = module.AdvertisingService(session, 1, now=lambda: NOW)

    with pytest.raises(module.AdvertisingAccountNotFound):
        service.get_pnl_source(32, PERIOD)

    future = service.get_pnl_source(31, Period(date(2026, 9, 2), date(2026, 9, 3)))
    assert future.state == "future"
    assert future.snapshot is None
