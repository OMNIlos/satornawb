from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker

from app.cabinet.orm import LkOrganizationRow
from app.infra.models import Base
from app.platform.advertising import service
from app.platform.advertising.orm import WbAdvertisingFactRow
from app.platform.integrations.orm import MarketplaceAccountRow


def payload() -> dict[str, object]:
    metrics = {
        "adSpendKopecks": 12_300,
        "adImpressions": 100,
        "adClicks": 10,
        "adCartAdds": 3,
        "adOrders": 2,
        "adRevenueKopecks": 45_600,
    }
    return {
        "aggregates": {"453200669": dict(metrics)},
        "dailyAggregates": {"2026-08-20": {"453200669": dict(metrics)}},
        "totals": dict(metrics),
        "dateFrom": "2026-08-20",
        "dateTo": "2026-08-20",
    }


def test_shadow_ingest_requires_one_connected_wb_account(monkeypatch) -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as session:
        session.add_all(
            [
                LkOrganizationRow(organization_id=2, slug="two", name="Two"),
                MarketplaceAccountRow(
                    marketplace_account_id=31,
                    organization_id=2,
                    marketplace="wb",
                    external_account_id="wb-two",
                    status="connected",
                ),
                MarketplaceAccountRow(
                    marketplace_account_id=32,
                    organization_id=2,
                    marketplace="wb",
                    external_account_id="wb-disconnected",
                    status="disconnected",
                ),
            ]
        )
        session.commit()
    monkeypatch.setattr(service, "get_session_factory", lambda: factory)

    result = service.ingest_legacy_advertising_payload(
        2,
        payload(),
        source_kind="ads_fullstats",
        observed_at=datetime(2026, 8, 26, tzinfo=timezone.utc),
    )

    assert result["state"] == "ready"
    assert result["marketplaceAccountId"] == 31
    with factory() as session:
        assert (
            session.scalar(select(func.count()).select_from(WbAdvertisingFactRow)) == 1
        )
        session.add(
            MarketplaceAccountRow(
                marketplace_account_id=33,
                organization_id=2,
                marketplace="wb",
                external_account_id="wb-extra",
                status="connected",
            )
        )
        session.commit()

    skipped = service.ingest_legacy_advertising_payload(
        2, payload(), source_kind="ads_fullstats"
    )
    assert skipped == {
        "state": "skipped",
        "reason": "wb_account_ambiguous",
        "accountCount": 2,
    }
    with factory() as session:
        assert (
            session.scalar(select(func.count()).select_from(WbAdvertisingFactRow)) == 1
        )


def test_shadow_bridge_requires_enabled_organization(monkeypatch) -> None:
    calls: list[int] = []
    monkeypatch.setattr(
        service,
        "get_settings",
        lambda: type(
            "Settings",
            (),
            {
                "advertising_shadow_ingest_enabled": True,
                "advertising_shadow_ingest_organization_ids": (2,),
            },
        )(),
    )
    monkeypatch.setattr(
        service,
        "ingest_legacy_advertising_payload",
        lambda organization_id, *_args, **_kwargs: calls.append(organization_id)
        or {"state": "ready"},
    )

    assert service.shadow_ingest_legacy_advertising_payload(
        1, {}, source_kind="ads_fullstats"
    ) == {"state": "disabled"}
    assert service.shadow_ingest_legacy_advertising_payload(
        2, {}, source_kind="ads_fullstats"
    ) == {"state": "ready"}
    assert calls == [2]


def test_shadow_bridge_does_not_open_database_when_disabled(monkeypatch) -> None:
    monkeypatch.setattr(
        service,
        "get_settings",
        lambda: type("Settings", (), {"advertising_shadow_ingest_enabled": False})(),
    )
    monkeypatch.setattr(
        service,
        "ingest_legacy_advertising_payload",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("disabled bridge must not touch PostgreSQL")
        ),
    )

    assert service.shadow_ingest_legacy_advertising_payload(
        2, {}, source_kind="finance_promotion"
    ) == {"state": "disabled"}
