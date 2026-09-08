from dataclasses import replace

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.modules.orders import ExternalOrderItemIdentity, make_avito_source_line_key
from app.orders.contracts import AccountCoverage, CatalogResolution, OrderReadRow
from app.orders.evidence_repository import OrdersEvidenceRepository
from app.orders.ingestion import ObservedOrderItem
from app.orders.snapshot_repository import OrdersSnapshotRepository
from tests.test_orders_evidence_repository import fact, new_run
from tests.test_orders_schema_candidate import cluster, scope  # noqa: F401
from tests.test_orders_schema_candidate import db as _db_fixture

snapshot_db = _db_fixture


def stored_rows(session):
    source = fact()
    items = tuple(
        ObservedOrderItem(
            ExternalOrderItemIdentity(
                source.identity,
                make_avito_source_line_key(
                    source.identity.external_order_id, "synthetic-listing", index
                ),
                "synthetic-listing",
                index,
            ),
            2,
        )
        for index in range(2)
    )
    source = replace(source, items=items)
    record = OrdersEvidenceRepository(session, 91001, 91101).append(
        new_run(session, source), source
    )
    rows = []
    for item in items:
        session.execute(
            text("""INSERT INTO marketplace_order_items
          (organization_id,marketplace_account_id,order_id,source_line_key,external_item_id,
           occurrence_index,quantity,resolution_version)
          VALUES (91001,91101,:order,:key,'synthetic-listing',:occurrence,2,'synthetic-v1')"""),
            {
                "order": record.order_id,
                "key": item.identity.source_line_key,
                "occurrence": item.identity.occurrence_index,
            },
        )
        rows.append(
            OrderReadRow(
                source,
                item.identity,
                1,
                CatalogResolution("unmapped", None, None, None, "synthetic-v1"),
                ("unmapped",),
            )
        )
    return tuple(rows)


def coverage():
    return (
        AccountCoverage(
            91101,
            "avito-order-management",
            "synthetic-adapter-v1",
            "complete",
            "synthetic-snapshot",
            None,
            None,
        ),
    )


def test_snapshot_pages_are_frozen_after_current_item_changes(snapshot_db):
    _, runtime = snapshot_db
    with Session(runtime) as session, session.begin():
        scope(session)
        rows = stored_rows(session)
        snapshot = OrdersSnapshotRepository(session, 91001).freeze(
            rows, coverage(), "synthetic-hwm", "a" * 64
        )
    with Session(runtime) as session, session.begin():
        scope(session)
        session.execute(
            text(
                "UPDATE marketplace_order_items SET quantity=9,version=version+1 WHERE source_line_key=:key"
            ),
            {"key": rows[0].item_identity.source_line_key},
        )
    with Session(runtime) as session, session.begin():
        scope(session)
        repo = OrdersSnapshotRepository(session, 91001)
        first = repo.read(snapshot, (91101,), "a" * 64, limit=1)
        assert first.rows == rows[:1]
        assert first.account_coverage == coverage()
        assert first.coverage_state == "complete"
        assert first.next_position == 1
        second = repo.read(
            snapshot, (91101,), "a" * 64, after_position=first.next_position, limit=1
        )
        assert second.rows == rows[1:]
        assert second.next_position is None


def test_freeze_rejects_stale_version_before_creating_header(snapshot_db):
    _, runtime = snapshot_db
    with Session(runtime) as session, session.begin():
        scope(session)
        rows = stored_rows(session)
        with pytest.raises(ValueError, match="projection"):
            OrdersSnapshotRepository(session, 91001).freeze(
                (replace(rows[0], row_version=2),),
                coverage(),
                "synthetic-hwm",
                "a" * 64,
            )


def test_read_rejects_different_query_or_account_scope(snapshot_db):
    _, runtime = snapshot_db
    with Session(runtime) as session, session.begin():
        scope(session)
        repo = OrdersSnapshotRepository(session, 91001)
        snapshot = repo.freeze(
            stored_rows(session), coverage(), "synthetic-hwm", "a" * 64
        )
        with pytest.raises(ValueError, match="scope"):
            repo.read(snapshot, (91102,), "a" * 64)
        with pytest.raises(ValueError, match="scope"):
            repo.read(snapshot, (91101,), "b" * 64)
