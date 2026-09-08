from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

from app import repricer_bff
from app.cabinet.orm import LkOrganizationRow
from app.infra.models import Base
from app.platform.finance.orm import WbFinanceOperationRow
from app.platform.finance.service import (
    ingest_legacy_finance_payload,
    shadow_ingest_legacy_finance_payload,
)
from app.platform.integrations.orm import MarketplaceAccountRow
from app.wb_api.client import WbApiRequest, WbApiResponseEnvelope


def test_shadow_ingest_requires_one_wb_account_and_keeps_raw_operation(
    monkeypatch,
) -> None:
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
            ]
        )
        session.commit()
    monkeypatch.setattr(
        "app.platform.finance.service.get_session_factory", lambda: factory
    )
    payload = {
        "dateFrom": "2026-08-17",
        "dateTo": "2026-08-23",
        "rows": [
            {
                "rrdId": 101,
                "reportId": 820347930,
                "reportType": 1,
                "nmId": 453200669,
                "docTypeName": "Продажа",
                "quantity": 1,
                "retailAmount": "1208.00",
                "cashbackAmount": "10.00",
                "cashbackDiscount": "3.50",
                "cashbackCommissionChange": "-1.25",
                "saleDt": "2026-08-20",
                "rrDate": "2026-08-23",
            }
        ],
    }

    result = ingest_legacy_finance_payload(
        2,
        payload,
        observed_at=datetime(2026, 8, 26, tzinfo=timezone.utc),
    )

    assert result["state"] == "ready"
    assert result["marketplaceAccountId"] == 31
    with factory() as session:
        operation = session.scalar(select(WbFinanceOperationRow))
        assert operation is not None
        assert (operation.source_identity, operation.report_type) == ("rrd:101", "main")
        assert (
            operation.cashback_amount_kopecks,
            operation.cashback_discount_kopecks,
            operation.cashback_commission_change_kopecks,
        ) == (1_000, 350, -125)
        session.add(
            MarketplaceAccountRow(
                marketplace_account_id=33,
                organization_id=2,
                marketplace="wb",
                external_account_id="wb-two-extra",
                status="connected",
            )
        )
        session.commit()

    assert ingest_legacy_finance_payload(2, payload)["state"] == "skipped"
    with factory() as session:
        assert (
            session.scalar(select(func.count()).select_from(WbFinanceOperationRow)) == 1
        )


def test_finance_fetch_requests_canonical_identity_and_report_fields(
    monkeypatch,
) -> None:
    class FinanceClient:
        def __init__(self) -> None:
            self.requests: list[WbApiRequest] = []

        def request(self, request: WbApiRequest) -> WbApiResponseEnvelope:
            self.requests.append(request)
            return WbApiResponseEnvelope(
                request=request,
                statusCode=200,
                ok=True,
                data={"data": []},
            )

    client = FinanceClient()
    monkeypatch.setattr(repricer_bff, "_finance_report_last_request_at", 0.0)
    monkeypatch.setattr(
        "app.repricer_bff.build_wb_finance_client", lambda *_args, **_kwargs: client
    )

    repricer_bff.fetch_finance_report_aggregates(
        "complete",
        wb_token="token",
        date_from=datetime(2026, 8, 17, tzinfo=timezone.utc),
        date_to=datetime(2026, 8, 23, tzinfo=timezone.utc),
    )

    assert {"rrdId", "reportId", "reportType"} <= set(
        client.requests[0].jsonBody["fields"]
    )


def test_periodic_shadow_writer_is_disabled_until_rollout(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.platform.finance.service.get_settings",
        lambda: type("Settings", (), {"finance_shadow_ingest_enabled": False})(),
    )
    monkeypatch.setattr(
        "app.platform.finance.service.ingest_legacy_finance_payload",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("disabled writer must not touch PostgreSQL")
        ),
    )

    assert shadow_ingest_legacy_finance_payload(2, {}) == {"state": "disabled"}


def test_periodic_shadow_writer_is_limited_to_canary_organization(
    monkeypatch,
) -> None:
    calls: list[int] = []
    monkeypatch.setattr(
        "app.platform.finance.service.get_settings",
        lambda: type(
            "Settings",
            (),
            {
                "finance_shadow_ingest_enabled": True,
                "finance_shadow_ingest_organization_ids": (2,),
            },
        )(),
    )
    monkeypatch.setattr(
        "app.platform.finance.service.ingest_legacy_finance_payload",
        lambda organization_id, *_args, **_kwargs: calls.append(organization_id)
        or {"state": "ready"},
    )

    assert shadow_ingest_legacy_finance_payload(1, {}) == {"state": "disabled"}
    assert shadow_ingest_legacy_finance_payload(2, {}) == {"state": "ready"}
    assert calls == [2]
