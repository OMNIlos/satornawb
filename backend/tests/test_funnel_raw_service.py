from __future__ import annotations

import copy
import json
from datetime import date, datetime, timezone
from pathlib import Path

import pytest
from sqlalchemy import create_engine, event, func, select
from sqlalchemy.orm import Session

from app.cabinet.orm import LkOrganizationRow, LkUserRow, LkUserWbTokenRow
from app.infra.models import Base
from app.platform.catalog.orm import MarketplaceProductRow
from app.platform.funnel import raw_backfill as raw_backfill_module
from app.platform.funnel.orm import WbFunnelDailyRow, WbFunnelSyncRunRow
from app.platform.funnel.raw_backfill import (
    RawFunnelBackfillError,
    backfill_raw_funnel,
)
from app.platform.funnel.raw import (
    FunnelNormalizationError,
    _response_checksum,
)
from app.platform.funnel.service import FunnelAccountNotFound, FunnelService
from app.platform.integrations.orm import MarketplaceAccountRow
from app.platform.period import Period
from app.wb_api.raw_funnel import RawFunnelFetch

NOW = datetime(2026, 9, 4, 10, tzinfo=timezone.utc)
INTERMEDIATE = datetime(2026, 9, 4, 10, 30, tzinfo=timezone.utc)
LATER = datetime(2026, 9, 4, 11, tzinfo=timezone.utc)
PERIOD = Period(date(2026, 9, 2), date(2026, 9, 3))


@pytest.fixture
def session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:")

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(dbapi_connection, _connection_record) -> None:
        dbapi_connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as db:
        db.add_all(
            [
                LkOrganizationRow(organization_id=1, slug="one", name="One"),
                LkOrganizationRow(organization_id=2, slug="two", name="Two"),
                MarketplaceAccountRow(
                    marketplace_account_id=31,
                    organization_id=1,
                    marketplace="wb",
                    external_account_id="shared-wb-account",
                    status="connected",
                ),
                MarketplaceAccountRow(
                    marketplace_account_id=32,
                    organization_id=2,
                    marketplace="wb",
                    external_account_id="shared-wb-account",
                    status="connected",
                ),
                MarketplaceAccountRow(
                    marketplace_account_id=33,
                    organization_id=1,
                    marketplace="ozon",
                    external_account_id="other-marketplace",
                    status="connected",
                ),
            ]
        )
        db.commit()
        db.add_all(
            [
                MarketplaceProductRow(
                    marketplace_product_id=41,
                    organization_id=1,
                    marketplace_account_id=31,
                    external_product_id="1001",
                ),
                MarketplaceProductRow(
                    marketplace_product_id=42,
                    organization_id=1,
                    marketplace_account_id=31,
                    external_product_id="1002",
                ),
                MarketplaceProductRow(
                    marketplace_product_id=43,
                    organization_id=2,
                    marketplace_account_id=32,
                    external_product_id="1001",
                ),
            ]
        )
        db.commit()
        yield db


@pytest.fixture
def raw_bundle() -> dict[str, object]:
    return json.loads(
        (
            Path(__file__).parent / "fixtures/wb_funnel_history_daily_sanitized.json"
        ).read_text()
    )


def _counts(session: Session) -> tuple[int, int]:
    return (
        session.scalar(select(func.count()).select_from(WbFunnelSyncRunRow)) or 0,
        session.scalar(select(func.count()).select_from(WbFunnelDailyRow)) or 0,
    )


def _change_open_count(bundle: dict[str, object]) -> None:
    bundle["pages"][0]["payload"]["data"][0]["history"][0]["openCount"] += 1
    bundle["manifest"][0]["responseChecksum"] = _response_checksum(
        bundle["pages"][0]["payload"]
    )


def test_funnel_ingest_is_atomic_idempotent_and_parent_linked(
    session: Session, raw_bundle
) -> None:
    service = FunnelService(session, 1, now=lambda: NOW)
    first = service.ingest_raw_payload(
        31, PERIOD, raw_bundle, source_reference="wb_api:raw_backfill"
    )
    replay_bundle = copy.deepcopy(raw_bundle)
    replay_bundle["manifest"][0]["wbRequestId"] = "replay-request"
    replay = service.ingest_raw_payload(
        31,
        PERIOD,
        replay_bundle,
        source_reference="wb_api:ignored-on-replay",
        observed_at=LATER,
    )

    assert replay.sync_run_id == first.sync_run_id
    assert replay.last_observed_at == LATER
    assert (replay.expected_request_count, replay.completed_request_count) == (1, 1)
    assert _counts(session) == (1, 4)

    changed_bundle = copy.deepcopy(raw_bundle)
    _change_open_count(changed_bundle)
    changed = service.ingest_raw_payload(
        31,
        PERIOD,
        changed_bundle,
        source_reference="wb_api:raw_backfill",
        observed_at=INTERMEDIATE,
    )

    assert changed.sync_run_id != first.sync_run_id
    assert _counts(session) == (2, 8)
    child = session.get(WbFunnelSyncRunRow, changed.sync_run_id)
    assert child.parent_sync_run_id == first.sync_run_id
    assert child.fact_count == 4
    assert child.normalizer_version == "wb-funnel-history-v1"


@pytest.mark.parametrize("account_id", [32, 33, 999])
def test_funnel_ingest_requires_owned_connected_wb_account(
    session: Session, raw_bundle, account_id: int
) -> None:
    with pytest.raises(FunnelAccountNotFound):
        FunnelService(session, 1, now=lambda: NOW).ingest_raw_payload(
            account_id, PERIOD, raw_bundle, source_reference="wb_api:raw_backfill"
        )

    assert _counts(session) == (0, 0)


def test_funnel_ingest_rejects_disconnected_account(
    session: Session, raw_bundle
) -> None:
    session.get(MarketplaceAccountRow, 31).status = "disconnected"
    session.commit()

    with pytest.raises(FunnelAccountNotFound):
        FunnelService(session, 1, now=lambda: NOW).ingest_raw_payload(
            31, PERIOD, raw_bundle, source_reference="wb_api:raw_backfill"
        )

    assert _counts(session) == (0, 0)


def test_funnel_ingest_scopes_identical_source_ids_by_tenant(
    session: Session, raw_bundle
) -> None:
    one = FunnelService(session, 1, now=lambda: NOW).ingest_raw_payload(
        31, PERIOD, raw_bundle, source_reference="wb_api:raw_backfill"
    )
    two = FunnelService(session, 2, now=lambda: NOW).ingest_raw_payload(
        32, PERIOD, raw_bundle, source_reference="wb_api:raw_backfill"
    )

    assert one.sync_run_id != two.sync_run_id
    assert _counts(session) == (2, 8)
    assert set(
        session.execute(
            select(
                WbFunnelDailyRow.organization_id,
                WbFunnelDailyRow.marketplace_account_id,
            )
        )
    ) == {(1, 31), (2, 32)}


def test_funnel_ingest_rolls_back_run_when_fact_insert_fails(
    session: Session, raw_bundle
) -> None:
    engine = session.get_bind()

    def fail_fact_insert(
        _conn, _cursor, statement, _parameters, _context, _executemany
    ) -> None:
        if statement.lstrip().startswith("INSERT INTO wb_funnel_daily"):
            raise RuntimeError("injected funnel fact failure")

    event.listen(engine, "before_cursor_execute", fail_fact_insert)
    try:
        with pytest.raises(RuntimeError, match="injected funnel fact failure"):
            FunnelService(session, 1, now=lambda: NOW).ingest_raw_payload(
                31, PERIOD, raw_bundle, source_reference="wb_api:raw_backfill"
            )
    finally:
        event.remove(engine, "before_cursor_execute", fail_fact_insert)

    assert _counts(session) == (0, 0)


def test_postgresql_funnel_ingest_locks_after_account_before_run_lookup(
    session: Session, raw_bundle, monkeypatch
) -> None:
    service = FunnelService(session, 1, now=lambda: NOW)
    events: list[str] = []
    locks: list[dict[str, object]] = []
    original_account = service._account
    original_execute = session.execute
    original_scalar = session.scalar

    def account(marketplace_account_id: int):
        result = original_account(marketplace_account_id)
        events.append("account_validated")
        return result

    def execute(statement, params=None, **kwargs):
        sql = str(statement)
        if "set_config('app.organization_id'" in sql:
            return None
        if "pg_advisory_xact_lock" in sql:
            events.append("advisory_lock")
            locks.append(params)
            return None
        return original_execute(statement, params, **kwargs)

    def scalar(statement, *args, **kwargs):
        if "wb_funnel_sync_runs" in str(statement):
            events.append("run_lookup")
        return original_scalar(statement, *args, **kwargs)

    monkeypatch.setattr(session.get_bind().dialect, "name", "postgresql")
    monkeypatch.setattr(service, "_account", account)
    monkeypatch.setattr(session, "execute", execute)
    monkeypatch.setattr(session, "scalar", scalar)

    service.ingest_raw_payload(
        31, PERIOD, raw_bundle, source_reference="wb_api:raw_backfill"
    )

    assert events[:3] == ["account_validated", "advisory_lock", "run_lookup"]
    assert len(locks) == 1
    assert isinstance(locks[0]["lock_key"], int)


def test_funnel_replay_never_moves_last_observed_backwards(
    session: Session, raw_bundle
) -> None:
    service = FunnelService(session, 1, now=lambda: LATER)
    first = service.ingest_raw_payload(
        31, PERIOD, raw_bundle, source_reference="wb_api:raw_backfill"
    )

    replay = service.ingest_raw_payload(
        31,
        PERIOD,
        raw_bundle,
        source_reference="wb_api:raw_backfill",
        observed_at=NOW,
    )

    assert replay.sync_run_id == first.sync_run_id
    assert replay.last_observed_at == LATER


def test_funnel_ingest_rejects_partial_manifest_without_writes(
    session: Session, raw_bundle
) -> None:
    raw_bundle["manifest"][0]["ok"] = False

    with pytest.raises(FunnelNormalizationError, match="incomplete"):
        FunnelService(session, 1, now=lambda: NOW).ingest_raw_payload(
            31, PERIOD, raw_bundle, source_reference="wb_api:raw_backfill"
        )

    assert _counts(session) == (0, 0)


def test_funnel_ingest_rejects_invalid_source_reference_without_writes(
    session: Session, raw_bundle
) -> None:
    with pytest.raises(FunnelNormalizationError, match="source reference"):
        FunnelService(session, 1, now=lambda: NOW).ingest_raw_payload(
            31, PERIOD, raw_bundle, source_reference=""
        )

    assert _counts(session) == (0, 0)


def test_funnel_backfill_never_publishes_partial_fetch(
    session: Session, monkeypatch
) -> None:
    token = "never-emit-this-token"

    def fetch(period: Period, nm_ids: list[int], *, wb_token: str) -> RawFunnelFetch:
        assert not session.in_transaction()
        assert (period, nm_ids, wb_token) == (PERIOD, [1001, 1002], token)
        return RawFunnelFetch(
            "partial",
            {"raw": token},
            1,
            0,
            ("rate_limited",),
        )

    monkeypatch.setattr(raw_backfill_module, "fetch_raw_funnel", fetch)
    monkeypatch.setattr(
        FunnelService,
        "ingest_raw_payload",
        lambda *_args, **_kwargs: pytest.fail("partial evidence must not publish"),
    )

    result = backfill_raw_funnel(1, PERIOD, wb_token=f"  {token}  ", session=session)

    assert result == {
        "state": "partial",
        "expectedRequests": 1,
        "completedRequests": 0,
        "failureCodes": ["rate_limited"],
    }
    assert token not in json.dumps(result)
    assert not session.in_transaction()
    assert _counts(session) == (0, 0)


def test_funnel_backfill_resolves_token_and_publishes_ready_evidence(
    session: Session, raw_bundle, monkeypatch
) -> None:
    token = "resolved-secret-token"
    calls: list[tuple[Period, list[int], str]] = []

    monkeypatch.setattr(
        raw_backfill_module,
        "get_organization_wb_token_secret",
        lambda organization_id: f"  {token}  " if organization_id == 1 else None,
    )

    def fetch(period: Period, nm_ids: list[int], *, wb_token: str) -> RawFunnelFetch:
        assert not session.in_transaction()
        calls.append((period, nm_ids, wb_token))
        return RawFunnelFetch("ready", raw_bundle, 1, 1, ())

    monkeypatch.setattr(raw_backfill_module, "fetch_raw_funnel", fetch)

    result = backfill_raw_funnel(1, PERIOD, session=session)

    assert calls == [(PERIOD, [1001, 1002], token)]
    assert result | {"syncRunId": None, "snapshotChecksum": None} == {
        "state": "ready",
        "syncRunId": None,
        "snapshotChecksum": None,
        "marketplaceAccountId": 31,
        "factCount": 4,
        "expectedRequests": 1,
        "completedRequests": 1,
    }
    assert token not in json.dumps(result)
    assert not session.in_transaction()
    assert _counts(session) == (1, 4)


@pytest.mark.parametrize(
    ("organization_id", "token", "error_code"),
    [(0, "unused", "invalid_organization"), (1, "   ", "wb_token_missing")],
)
def test_funnel_backfill_validates_scope_before_fetch(
    session: Session,
    monkeypatch,
    organization_id: int,
    token: str,
    error_code: str,
) -> None:
    monkeypatch.setattr(
        raw_backfill_module,
        "get_organization_wb_token_secret",
        lambda _organization_id: token,
    )
    monkeypatch.setattr(
        raw_backfill_module,
        "fetch_raw_funnel",
        lambda *_args, **_kwargs: pytest.fail("invalid scope must not fetch"),
    )

    with pytest.raises(RawFunnelBackfillError) as raised:
        backfill_raw_funnel(organization_id, PERIOD, session=session)

    assert raised.value.error_code == error_code


def test_funnel_backfill_rejects_mismatched_explicit_account(
    session: Session, monkeypatch
) -> None:
    monkeypatch.setattr(
        raw_backfill_module,
        "fetch_raw_funnel",
        lambda *_args, **_kwargs: pytest.fail("mismatched account must not fetch"),
    )

    with pytest.raises(RawFunnelBackfillError) as raised:
        backfill_raw_funnel(
            1,
            PERIOD,
            marketplace_account_id=32,
            wb_token="secret",
            session=session,
        )

    assert raised.value.error_code == "wb_account_changed"


def test_funnel_backfill_revalidates_explicit_credential_after_fetch(
    session: Session, raw_bundle, monkeypatch
) -> None:
    account = session.get(MarketplaceAccountRow, 31)
    assert account is not None
    account.credential_ref = "lk_user_wb_tokens:21"
    session.add_all(
        [
            LkUserRow(
                user_id="user-one",
                organization_id=1,
                email="one@example.com",
                password_hash="unused",
                full_name="One",
                permission_profile="admin",
                is_active=True,
            ),
            LkUserWbTokenRow(
                token_id=21,
                user_id="user-one",
                organization_id=1,
                wb_token="secret",
                token_masked="***",
            ),
        ]
    )
    session.commit()

    def fetch(_period: Period, _nm_ids: list[int], *, wb_token: str) -> RawFunnelFetch:
        assert wb_token == "secret"
        with Session(session.get_bind()) as mutation_session:
            changed = mutation_session.get(MarketplaceAccountRow, 31)
            assert changed is not None
            changed.credential_ref = None
            mutation_session.commit()
        return RawFunnelFetch("ready", raw_bundle, 1, 1, ())

    monkeypatch.setattr(raw_backfill_module, "fetch_raw_funnel", fetch)
    monkeypatch.setattr(
        FunnelService,
        "ingest_raw_payload",
        lambda *_args, **_kwargs: pytest.fail("changed credential must not publish"),
    )

    with pytest.raises(RawFunnelBackfillError) as raised:
        backfill_raw_funnel(
            1,
            PERIOD,
            marketplace_account_id=31,
            credential_ref="lk_user_wb_tokens:21",
            wb_token="secret",
            session=session,
        )

    assert raised.value.error_code == "wb_credential_binding_invalid"
    assert not session.in_transaction()


def test_funnel_backfill_rejects_active_session_before_token_resolution(
    session: Session, monkeypatch
) -> None:
    session.begin()
    monkeypatch.setattr(
        raw_backfill_module,
        "get_organization_wb_token_secret",
        lambda _organization_id: pytest.fail("active session must fail first"),
    )

    with pytest.raises(RawFunnelBackfillError) as raised:
        backfill_raw_funnel(1, PERIOD, session=session)

    assert raised.value.error_code == "session_transaction_active"
    session.rollback()


@pytest.mark.parametrize(
    ("scope_change", "error_code"),
    [("disconnect", "wb_account_missing"), ("add", "wb_account_ambiguous")],
)
def test_funnel_backfill_revalidates_account_after_fetch(
    session: Session,
    raw_bundle,
    monkeypatch,
    scope_change: str,
    error_code: str,
) -> None:
    def fetch(_period: Period, _nm_ids: list[int], *, wb_token: str) -> RawFunnelFetch:
        assert wb_token == "secret"
        with Session(session.get_bind()) as mutation_session:
            if scope_change == "disconnect":
                mutation_session.get(MarketplaceAccountRow, 31).status = "disconnected"
            else:
                mutation_session.add(
                    MarketplaceAccountRow(
                        marketplace_account_id=34,
                        organization_id=1,
                        marketplace="wb",
                        external_account_id="second-wb-account",
                        status="connected",
                    )
                )
            mutation_session.commit()
        return RawFunnelFetch("ready", raw_bundle, 1, 1, ())

    monkeypatch.setattr(raw_backfill_module, "fetch_raw_funnel", fetch)
    monkeypatch.setattr(
        FunnelService,
        "ingest_raw_payload",
        lambda *_args, **_kwargs: pytest.fail("changed scope must not publish"),
    )

    with pytest.raises(RawFunnelBackfillError) as raised:
        backfill_raw_funnel(1, PERIOD, wb_token="secret", session=session)

    assert raised.value.error_code == error_code
    assert not session.in_transaction()
    assert _counts(session) == (0, 0)


def test_funnel_backfill_requires_numeric_account_products(
    session: Session, monkeypatch
) -> None:
    for index, product in enumerate(
        session.scalars(
            select(MarketplaceProductRow).where(
                MarketplaceProductRow.organization_id == 1
            )
        )
    ):
        product.external_product_id = f"not-a-wb-id-{index}"
    session.commit()
    monkeypatch.setattr(
        raw_backfill_module,
        "fetch_raw_funnel",
        lambda *_args, **_kwargs: pytest.fail("missing products must not fetch"),
    )

    with pytest.raises(RawFunnelBackfillError) as raised:
        backfill_raw_funnel(1, PERIOD, wb_token="secret", session=session)

    assert raised.value.error_code == "wb_products_missing"
