from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session

from app.cabinet.orm import LkOrganizationRow
from app.infra.models import Base
from app.platform.catalog.orm import (
    CatalogSkuRow,
    MarketplaceOfferRow,
    MarketplaceProductRow,
)
from app.platform.catalog.service import CatalogService
from app.platform.economics.costs import CostsService
from app.platform.integrations.orm import MarketplaceAccountRow

AT_20 = datetime(2026, 8, 20, 20, 59, 59, tzinfo=timezone.utc)
AT_21 = datetime(2026, 8, 21, 20, 59, 59, tzinfo=timezone.utc)


@pytest.fixture
def session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:")
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
                    marketplace_account_id=33,
                    organization_id=1,
                    marketplace="wb",
                    external_account_id="wb-one-extra",
                    status="connected",
                ),
                MarketplaceAccountRow(
                    marketplace_account_id=32,
                    organization_id=2,
                    marketplace="wb",
                    external_account_id="wb-two",
                    status="connected",
                ),
                CatalogSkuRow(catalog_sku_id=11, organization_id=1, code="SKU-11"),
                CatalogSkuRow(catalog_sku_id=12, organization_id=1, code="SKU-12"),
                CatalogSkuRow(catalog_sku_id=21, organization_id=2, code="SKU-21"),
                MarketplaceProductRow(
                    marketplace_product_id=1011,
                    organization_id=1,
                    marketplace_account_id=31,
                    external_product_id="101",
                ),
                MarketplaceProductRow(
                    marketplace_product_id=1021,
                    organization_id=1,
                    marketplace_account_id=31,
                    external_product_id="102",
                ),
                MarketplaceProductRow(
                    marketplace_product_id=1031,
                    organization_id=1,
                    marketplace_account_id=31,
                    external_product_id="103",
                ),
                MarketplaceProductRow(
                    marketplace_product_id=1013,
                    organization_id=1,
                    marketplace_account_id=33,
                    external_product_id="101",
                ),
                MarketplaceProductRow(
                    marketplace_product_id=1012,
                    organization_id=2,
                    marketplace_account_id=32,
                    external_product_id="101",
                ),
            ]
        )
        db.flush()
        db.add_all(
            [
                MarketplaceOfferRow(
                    marketplace_offer_id=2011,
                    organization_id=1,
                    marketplace_account_id=31,
                    marketplace_product_id=1011,
                    external_offer_key="SKU-11",
                    catalog_sku_id=11,
                ),
                MarketplaceOfferRow(
                    marketplace_offer_id=2021,
                    organization_id=1,
                    marketplace_account_id=31,
                    marketplace_product_id=1021,
                    external_offer_key="SKU-11",
                    catalog_sku_id=11,
                ),
                MarketplaceOfferRow(
                    marketplace_offer_id=2022,
                    organization_id=1,
                    marketplace_account_id=31,
                    marketplace_product_id=1021,
                    external_offer_key="SKU-12",
                    catalog_sku_id=12,
                ),
                MarketplaceOfferRow(
                    marketplace_offer_id=2031,
                    organization_id=1,
                    marketplace_account_id=31,
                    marketplace_product_id=1031,
                    external_offer_key="UNMAPPED",
                    catalog_sku_id=None,
                ),
                MarketplaceOfferRow(
                    marketplace_offer_id=2013,
                    organization_id=1,
                    marketplace_account_id=33,
                    marketplace_product_id=1013,
                    external_offer_key="SKU-12",
                    catalog_sku_id=12,
                ),
                MarketplaceOfferRow(
                    marketplace_offer_id=2012,
                    organization_id=2,
                    marketplace_account_id=32,
                    marketplace_product_id=1012,
                    external_offer_key="SKU-21",
                    catalog_sku_id=21,
                ),
            ]
        )
        db.commit()
        yield db


def test_wb_product_mapping_is_strictly_tenant_and_account_scoped(
    session: Session,
) -> None:
    service = CatalogService(session, organization_id=1)

    mapped, ambiguous = service.resolve_wb_product_skus(31, [101, 102, 103, 999])

    assert mapped == {101: 11}
    assert ambiguous == {102}
    assert service.resolve_wb_product_skus(33, [101]) == ({101: 12}, set())
    assert CatalogService(session, organization_id=2).resolve_wb_product_skus(
        32, [101]
    ) == ({101: 21}, set())


def test_costs_resolve_all_requested_dates_without_losing_state(
    session: Session,
) -> None:
    service = CostsService(session, organization_id=1)
    service.set_cost(
        catalog_sku_id=11,
        amount_kopecks=20_000,
        value_state="configured",
        effective_from=datetime(2026, 8, 19, 21, tzinfo=timezone.utc),
        source="fixture",
        source_reference="sku-11-v1",
        evidence_status="dated",
    )
    service.set_cost(
        catalog_sku_id=11,
        amount_kopecks=25_000,
        value_state="assumed",
        effective_from=datetime(2026, 8, 20, 21, tzinfo=timezone.utc),
        source="fixture",
        source_reference="sku-11-v2",
        evidence_status="undated",
    )
    service.set_cost(
        catalog_sku_id=12,
        amount_kopecks=0,
        value_state="configured",
        effective_from=datetime(2026, 8, 19, 21, tzinfo=timezone.utc),
        source="fixture",
        source_reference="sku-12-v1",
        evidence_status="dated",
    )

    costs = service.get_costs_on_dates([11, 12, 999], [AT_20, AT_21])

    assert costs[(11, AT_20)].amount_kopecks == 20_000
    assert costs[(11, AT_20)].value_state == "configured"
    assert costs[(11, AT_21)].amount_kopecks == 25_000
    assert costs[(11, AT_21)].value_state == "assumed"
    assert costs[(11, AT_21)].evidence_status == "undated"
    assert costs[(12, AT_20)].amount_kopecks == 0
    assert costs[(12, AT_20)].value_state == "configured"
    assert costs[(999, AT_20)].amount_kopecks is None
    assert costs[(999, AT_20)].value_state == "missing"
    assert service.revision() == 3


def test_costs_resolve_only_requested_sku_date_points(session: Session) -> None:
    service = CostsService(session, organization_id=1)
    service.set_cost(
        catalog_sku_id=11,
        amount_kopecks=20_000,
        value_state="configured",
        effective_from=datetime(2026, 8, 19, 21, tzinfo=timezone.utc),
        source="fixture",
        source_reference="point-sku-11",
        evidence_status="dated",
    )
    service.set_cost(
        catalog_sku_id=12,
        amount_kopecks=25_000,
        value_state="configured",
        effective_from=datetime(2026, 8, 20, 21, tzinfo=timezone.utc),
        source="fixture",
        source_reference="point-sku-12",
        evidence_status="dated",
    )
    points = [(11, AT_20), (12, AT_21), (999, AT_20)]

    costs = service.get_costs_for_points(points)

    assert set(costs) == set(points)
    assert costs[(11, AT_20)].amount_kopecks == 20_000
    assert costs[(12, AT_21)].amount_kopecks == 25_000
    assert costs[(999, AT_20)].value_state == "missing"


def test_unchanged_cost_version_reuses_immutable_projection(session: Session) -> None:
    service = CostsService(session, organization_id=1)
    service.set_cost(
        catalog_sku_id=11,
        amount_kopecks=20_000,
        value_state="configured",
        effective_from=datetime(2026, 8, 19, 21, tzinfo=timezone.utc),
        source="fixture",
        source_reference="stable-cost",
        evidence_status="dated",
    )

    costs = service.get_costs_for_points([(11, AT_20), (11, AT_21)])

    assert costs[(11, AT_20)] is costs[(11, AT_21)]


def test_bulk_cost_resolution_normalizes_each_instant_once(
    session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.platform.economics import costs as costs_module

    calls: list[datetime] = []
    original = costs_module._aware_utc

    def observed(value: datetime) -> datetime:
        calls.append(value)
        return original(value)

    monkeypatch.setattr(costs_module, "_aware_utc", observed)

    CostsService(session, organization_id=1).get_costs_for_points(
        [(11, AT_20), (12, AT_20), (11, AT_21)]
    )

    assert calls == [AT_20, AT_21]


def test_bulk_cost_resolution_does_not_track_ledger_rows(session: Session) -> None:
    from app.platform.economics.orm import CatalogCostVersionRow

    service = CostsService(session, organization_id=1)
    service.set_cost(
        catalog_sku_id=11,
        amount_kopecks=20_000,
        value_state="configured",
        effective_from=datetime(2026, 8, 19, 21, tzinfo=timezone.utc),
        source="fixture",
        source_reference="untracked-cost",
        evidence_status="dated",
    )
    session.expunge_all()
    loaded: list[CatalogCostVersionRow] = []

    def track(_session: Session, instance: object) -> None:
        if isinstance(instance, CatalogCostVersionRow):
            loaded.append(instance)

    event.listen(session, "loaded_as_persistent", track)
    try:
        service.get_costs_for_points([(11, AT_20), (11, AT_21)])
    finally:
        event.remove(session, "loaded_as_persistent", track)

    assert loaded == []
