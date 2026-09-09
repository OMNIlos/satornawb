from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from queue import Queue
from time import monotonic, sleep
from uuid import uuid4

import pytest
from sqlalchemy import event, text
from sqlalchemy.orm import Session

from app.cabinet.orm import LkSessionRow, LkUserRow
from app.orders.read_service import read_orders_snapshot
from app.orders.snapshot_repository import OrdersSnapshotRepository
from app.platform.identity.orm import IamMembershipRow
from app.platform.integrations.publication_guard import (
    ExpectedAccountBinding,
    PublicationGuardError,
    UserSessionPrincipal,
)
from tests.test_orders_exact_text_migration import db as _db_fixture
from tests.test_orders_schema_candidate import cluster, scope  # noqa: F401
from tests.test_orders_snapshot_repository import coverage, stored_rows

read_db = _db_fixture
ACCOUNTS = (ExpectedAccountBinding(91101, "avito", "synthetic-a", None),)


@pytest.fixture
def prepared(read_db):
    owner, runtime = read_db
    user, login = "synthetic-" + uuid4().hex, "synthetic-" + uuid4().hex
    now = datetime.now(UTC)
    with Session(owner) as session, session.begin():
        session.add(
            LkUserRow(
                user_id=user,
                organization_id=91001,
                email=user + "@example.invalid",
                password_hash="synthetic-unusable",
                full_name="Synthetic",
                permission_profile="custom",
            )
        )
        session.flush()
        membership = IamMembershipRow(
            organization_id=91001,
            user_id=user,
            role="custom",
            permissions=["cabinet:read"],
            scope_mode="selected",
            allowed_account_ids=[91101],
        )
        session.add(membership)
        session.add(
            LkSessionRow(
                session_id=login,
                user_id=user,
                issued_at=now,
                last_seen_at=now,
                expires_at=now + timedelta(hours=1),
            )
        )
        session.flush()
        principal = UserSessionPrincipal(91001, user, membership.membership_id, login)
    with Session(runtime) as session, session.begin():
        scope(session)
        rows = stored_rows(session)
        snapshot = OrdersSnapshotRepository(session, 91001).freeze(
            rows,
            coverage(),
            "synthetic-hwm",
            "a" * 64,
            parent_versions={rows[0].observation.identity: 2},
        )
    return owner, runtime, principal, snapshot


def read(session, principal, snapshot, **kwargs):
    return read_orders_snapshot(
        session,
        principal=principal,
        accounts=ACCOUNTS,
        snapshot_id=snapshot,
        query_checksum="a" * 64,
        **kwargs,
    )


def test_read_commits_guard_before_return_without_marketplace_credential(prepared):
    _, runtime, principal, snapshot = prepared
    with Session(runtime) as session:
        first = read(session, principal, snapshot, limit=1)
        assert len(first.rows) == 1
        assert first.next_position == 1
        assert not session.in_transaction()
        second = read(
            session, principal, snapshot, after_position=first.next_position, limit=1
        )
        assert len(second.rows) == 1 and second.next_position is None
        assert first.rows[0].item_identity != second.rows[0].item_identity


@pytest.mark.parametrize("change", ["membership", "permission", "scope", "logout"])
def test_next_page_rechecks_live_authority(prepared, change):
    owner, runtime, principal, snapshot = prepared
    with Session(runtime) as session:
        first = read(session, principal, snapshot, limit=1)
    statements = {
        "membership": "UPDATE iam_memberships SET is_active=false WHERE membership_id=:member",
        "permission": "UPDATE iam_memberships SET permissions='[]' WHERE membership_id=:member",
        "scope": "UPDATE iam_memberships SET allowed_account_ids='[91102]' WHERE membership_id=:member",
        "logout": "UPDATE lk_sessions SET revoked_at=clock_timestamp() WHERE session_id=:login",
    }
    with owner.begin() as connection:
        connection.execute(
            text(statements[change]),
            {"member": principal.membership_id, "login": principal.session_id},
        )
    with Session(runtime) as session:
        with pytest.raises(PublicationGuardError):
            read(
                session,
                principal,
                snapshot,
                after_position=first.next_position,
                limit=1,
            )
        assert not session.in_transaction()


def test_read_does_not_commit_callers_existing_transaction(prepared):
    _, runtime, principal, snapshot = prepared
    with Session(runtime) as session, session.begin():
        with pytest.raises(PublicationGuardError, match="publication_context_invalid"):
            read(session, principal, snapshot)
        assert session.in_transaction()


def test_final_commit_revalidation_prevents_returning_read_result(prepared):
    owner, runtime, principal, snapshot = prepared
    with Session(runtime) as session:

        def revoke_before_guard(session):
            session.execute(
                text(
                    "UPDATE iam_memberships SET is_active=false WHERE membership_id=:id"
                ),
                {"id": principal.membership_id},
            )

        event.listen(session, "before_commit", revoke_before_guard)
        with pytest.raises(PublicationGuardError):
            read(session, principal, snapshot)
        assert not session.in_transaction()
    with owner.connect() as connection:
        assert (
            connection.execute(
                text("SELECT is_active FROM iam_memberships WHERE membership_id=:id"),
                {"id": principal.membership_id},
            ).scalar_one()
            is True
        )


def test_read_waits_for_logout_then_denies(prepared):
    owner, runtime, principal, snapshot = prepared
    pids = Queue()

    def reader():
        with Session(runtime) as session:

            def identify(session, transaction, connection):
                pids.put(
                    connection.exec_driver_sql("SELECT pg_backend_pid()").scalar_one()
                )

            event.listen(session, "after_begin", identify)
            return read(session, principal, snapshot)

    with ThreadPoolExecutor(max_workers=1) as workers:
        with owner.begin() as connection:
            holder = connection.exec_driver_sql("SELECT pg_backend_pid()").scalar_one()
            connection.execute(
                text(
                    "UPDATE lk_sessions SET revoked_at=clock_timestamp() WHERE session_id=:id"
                ),
                {"id": principal.session_id},
            )
            future = workers.submit(reader)
            waiting = pids.get(timeout=5)
            assert waiting != holder
            deadline = monotonic() + 5
            while monotonic() < deadline:
                blocked = connection.execute(
                    text("SELECT :holder=ANY(pg_blocking_pids(:waiting))"),
                    {"holder": holder, "waiting": waiting},
                ).scalar_one()
                if blocked or future.done():
                    break
                sleep(0.01)
            assert blocked, "Read must wait for the authenticated session row"
        with pytest.raises(PublicationGuardError):
            future.result(timeout=5)
