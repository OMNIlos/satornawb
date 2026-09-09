from dataclasses import replace
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.modules.orders import map_avito_status
from app.orders.read_assembly import freeze_orders_view
from app.orders.read_service import read_orders_snapshot
from app.platform.integrations.publication_guard import ExpectedAccountBinding
from tests.test_orders_projection_repository import item_fact
from tests.test_orders_publication_service import (
    authority as _authority_fixture,
)
from tests.test_orders_publication_service import (
    manifest,
    publish,
)
from tests.test_orders_read_service import ACCOUNTS
from tests.test_orders_read_service import prepared as _prepared_fixture
from tests.test_orders_read_service import read_db as _read_db_fixture
from tests.test_orders_schema_candidate import cluster  # noqa: F401

authority = _authority_fixture
prepared = _prepared_fixture
read_db = _read_db_fixture


def freeze(session, principal, run):
    return freeze_orders_view(
        session,
        principal=principal,
        accounts=ACCOUNTS,
        coverage_run_ids=(run,),
        query_checksum="a" * 64,
    )


def read(session, principal, snapshot):
    return read_orders_snapshot(
        session,
        principal=principal,
        accounts=ACCOUNTS,
        snapshot_id=snapshot,
        query_checksum="a" * 64,
    )


def test_view_includes_repeated_items_and_never_claims_provider_readiness(authority):
    _, runtime, principal, credential = authority
    row = item_fact()
    with Session(runtime) as session:
        result = publish(session, principal, credential, manifest(row), uuid4().hex)
        snapshot = freeze(session, principal, result.run_id)
        page = read(session, principal, snapshot)
        assert len(page.rows) == 2
        assert page.coverage_state == "partial"
        assert {r.item_identity for r in page.rows} == {i.identity for i in row.items}
        for entry in page.rows:
            assert "source_readiness_unproven" in entry.readiness_blockers
            assert "catalog_unmapped" in entry.readiness_blockers
            assert entry.deadlines == ()
        assert not session.in_transaction()


def test_partial_cancellation_blocks_old_projection_without_rewriting_history(
    authority,
):
    _, runtime, principal, credential = authority
    row = item_fact()
    with Session(runtime) as session:
        initial = publish(session, principal, credential, manifest(row), uuid4().hex)
        historical = freeze(session, principal, initial.run_id)
        cancelled = replace(row, status=map_avito_status("canceled"))
        partial = publish(
            session,
            principal,
            credential,
            manifest(cancelled, complete=False),
            uuid4().hex,
        )
        current = read(session, principal, freeze(session, principal, partial.run_id))
        selected = [r for r in current.rows if r.observation.identity == row.identity]
        assert len(selected) == 2
        assert all(
            "source_reconciliation_required" in r.readiness_blockers for r in selected
        )
        assert all(r.observation.status == row.status for r in selected)
        old = read(session, principal, historical)
        assert all(
            "source_reconciliation_required" not in r.readiness_blockers
            for r in old.rows
        )


def test_view_rejects_cross_account_coverage_and_rolls_back_snapshot(authority):
    owner, runtime, principal, credential = authority
    with owner.connect() as connection:
        before = connection.execute(
            text("SELECT count(*) FROM order_read_snapshots")
        ).scalar_one()
    with Session(runtime) as session:
        result = publish(
            session, principal, credential, manifest(item_fact()), uuid4().hex
        )
        with pytest.raises(ValueError, match="coverage"):
            freeze(session, principal, result.run_id + 1000000)
        assert not session.in_transaction()
    with owner.connect() as connection:
        assert (
            connection.execute(
                text("SELECT count(*) FROM order_read_snapshots")
            ).scalar_one()
            == before
        )


def test_rebound_account_cannot_relabel_previously_published_evidence(authority):
    owner, runtime, principal, credential = authority
    with Session(runtime) as session:
        result = publish(
            session, principal, credential, manifest(item_fact()), uuid4().hex
        )
    with owner.begin() as connection:
        connection.execute(
            text(
                "UPDATE marketplace_accounts SET external_account_id='synthetic-rebound' WHERE marketplace_account_id=91101"
            )
        )
    try:
        with (
            Session(runtime) as session,
            pytest.raises(ValueError, match="account binding"),
        ):
            freeze_orders_view(
                session,
                principal=principal,
                accounts=(
                    ExpectedAccountBinding(91101, "avito", "synthetic-rebound", None),
                ),
                coverage_run_ids=(result.run_id,),
                query_checksum="a" * 64,
            )
    finally:
        with owner.begin() as connection:
            connection.execute(
                text(
                    "UPDATE marketplace_accounts SET external_account_id='synthetic-a' WHERE marketplace_account_id=91101"
                )
            )


def test_broken_current_membership_is_not_silently_omitted(authority):
    owner, runtime, principal, credential = authority
    row = item_fact()
    with Session(runtime) as session:
        first = publish(session, principal, credential, manifest(row), uuid4().hex)
        other = publish(
            session, principal, credential, manifest(item_fact()), uuid4().hex
        )
    with owner.begin() as connection:
        connection.execute(
            text(
                "UPDATE marketplace_orders SET last_seen_sync_run_id=:run,version=version+1 WHERE external_order_id=:external"
            ),
            {"run": other.run_id, "external": row.identity.external_order_id},
        )
    try:
        with Session(runtime) as session, pytest.raises(ValueError, match="membership"):
            freeze(session, principal, other.run_id)
    finally:
        with owner.begin() as connection:
            connection.execute(
                text(
                    "UPDATE marketplace_orders SET last_seen_sync_run_id=:run,version=version+1 WHERE external_order_id=:external"
                ),
                {"run": first.run_id, "external": row.identity.external_order_id},
            )
