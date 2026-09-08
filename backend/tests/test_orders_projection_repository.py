from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from threading import Barrier

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.modules.orders import map_avito_status
from app.orders.evidence_repository import OrdersEvidenceRepository
from app.orders.projection_repository import OrdersProjectionRepository
from tests.test_orders_evidence_repository import fact, new_run
from tests.test_orders_schema_candidate import cluster, scope  # noqa: F401
from tests.test_orders_schema_candidate import db as _db_fixture

projection_db = _db_fixture


def test_projection_uses_stored_fact_and_scoped_membership(projection_db):
    _, runtime = projection_db
    row = replace(fact(), status=map_avito_status("canceled"))
    with Session(runtime) as session, session.begin():
        scope(session)
        run = new_run(session, row)
        stored = OrdersEvidenceRepository(session, 91001, 91101).append(run, row)
        version = OrdersProjectionRepository(session, 91001, 91101).set_parent(
            run, stored.observation_id, expected_version=1
        )
        assert version == 2
        status = session.execute(
            text(
                "SELECT raw_status,canonical_status,last_seen_sync_run_id FROM marketplace_orders WHERE order_id=:id"
            ),
            {"id": stored.order_id},
        ).one()
        assert tuple(status) == ("canceled", "cancelled", run)
        with pytest.raises(ValueError, match="membership"):
            OrdersProjectionRepository(session, 91001, 91102).set_parent(
                run, stored.observation_id, expected_version=2
            )


def test_two_sessions_parent_cas_has_one_winner(projection_db):
    _, runtime = projection_db
    row = fact()
    with Session(runtime) as session, session.begin():
        scope(session)
        evidence = OrdersEvidenceRepository(session, 91001, 91101)
        runs = [new_run(session, row), new_run(session, row)]
        stored = [evidence.append(run, row) for run in runs]
    barrier = Barrier(2)

    def update(pair):
        run, record = pair
        with Session(runtime) as session, session.begin():
            scope(session)
            session.execute(text("SET LOCAL lock_timeout='5s'"))
            barrier.wait(timeout=5)
            try:
                return OrdersProjectionRepository(session, 91001, 91101).set_parent(
                    run, record.observation_id, expected_version=1
                )
            except ValueError as exc:
                assert "version" in str(exc)
                return "conflict"

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(update, zip(runs, stored, strict=True)))
    assert results.count(2) == results.count("conflict") == 1


def test_terminal_run_cannot_mutate_projection(projection_db):
    _, runtime = projection_db
    row = fact()
    with Session(runtime) as session, session.begin():
        scope(session)
        run = new_run(session, row)
        stored = OrdersEvidenceRepository(session, 91001, 91101).append(run, row)
        session.execute(
            text(
                "UPDATE order_sync_runs SET state='partial',completed_at=clock_timestamp() WHERE sync_run_id=:id"
            ),
            {"id": run},
        )
        with pytest.raises(ValueError, match="terminal"):
            OrdersProjectionRepository(session, 91001, 91101).set_parent(
                run, stored.observation_id, expected_version=1
            )


def test_projection_rolls_back_with_caller_transaction(projection_db):
    _, runtime = projection_db
    row = replace(fact(), status=map_avito_status("canceled"))
    with Session(runtime) as session, session.begin():
        scope(session)
        run = new_run(session, row)
        stored = OrdersEvidenceRepository(session, 91001, 91101).append(run, row)
    with Session(runtime) as session:
        with pytest.raises(RuntimeError), session.begin():
            scope(session)
            OrdersProjectionRepository(session, 91001, 91101).set_parent(
                run, stored.observation_id, expected_version=1
            )
            raise RuntimeError("synthetic publication failure")
        with session.begin():
            scope(session)
            current = session.execute(
                text(
                    "SELECT version,canonical_status,last_seen_sync_run_id FROM marketplace_orders WHERE order_id=:id"
                ),
                {"id": stored.order_id},
            ).one()
            assert tuple(current) == (1, None, None)
