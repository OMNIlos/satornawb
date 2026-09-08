from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import secrets
import shutil
import socket
import subprocess
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch
from uuid import UUID, uuid4

import pytest
from alembic import command
from alembic.config import Config
from fastapi.encoders import jsonable_encoder
from pydantic_core import to_json
from sqlalchemy import create_engine, event, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker

from app.platform.integrations import ingestion_tokens
from app.platform.integrations.credential_store import MarketplaceAccountCredentialOwner

ROOT = Path(__file__).resolve().parents[1]
RUNTIME_ROLE = "satorna_ingestion_test_runtime"
NOW = datetime(2026, 9, 8, 14, 0, tzinfo=timezone.utc)
CANARY = "synthetic-ingestion-secret-canary-b41d"


def _free_loopback_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


@pytest.fixture(scope="module")
def disposable_postgres(tmp_path_factory: pytest.TempPathFactory):
    required = ("initdb", "pg_ctl", "createdb")
    binaries = {name: shutil.which(name) for name in required}
    if any(path is None for path in binaries.values()):
        pytest.fail(
            "disposable PostgreSQL 16 binaries are required for ingestion-token tests"
        )
    root = tmp_path_factory.mktemp("avito-ingestion-token-postgres")
    data = root / "data"
    log = root / "postgres.log"
    port = _free_loopback_port()
    owner = "satorna_ingestion_test_owner"
    database = "satorna_ingestion_test"
    subprocess.run(
        [
            binaries["initdb"],
            "-D",
            str(data),
            "-A",
            "trust",
            "-U",
            owner,
            "--no-locale",
            "-E",
            "UTF8",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    options = f"-p {port} -h 127.0.0.1 -k /tmp -c fsync=off -c synchronous_commit=off"
    subprocess.run(
        [
            binaries["pg_ctl"],
            "-D",
            str(data),
            "-l",
            str(log),
            "-o",
            options,
            "-w",
            "start",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    try:
        subprocess.run(
            [
                binaries["createdb"],
                "-h",
                "127.0.0.1",
                "-p",
                str(port),
                "-U",
                owner,
                database,
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        owner_url = f"postgresql+psycopg://{owner}@127.0.0.1:{port}/{database}"
        owner_engine = create_engine(owner_url)
        with owner_engine.begin() as connection:
            connection.execute(text("""
                    CREATE TABLE lk_organizations (
                        organization_id INTEGER PRIMARY KEY,
                        slug VARCHAR(64) NOT NULL UNIQUE,
                        name VARCHAR(255) NOT NULL
                    );
                    CREATE TABLE lk_users (
                        user_id VARCHAR(128) PRIMARY KEY,
                        organization_id INTEGER NOT NULL REFERENCES lk_organizations(organization_id)
                    );
                    CREATE TABLE lk_audit_events (
                        event_id SERIAL PRIMARY KEY,
                        organization_id INTEGER NOT NULL REFERENCES lk_organizations(organization_id),
                        actor_user_id VARCHAR(128) REFERENCES lk_users(user_id),
                        action VARCHAR(128) NOT NULL,
                        object_type VARCHAR(64) NOT NULL,
                        object_id VARCHAR(128) NOT NULL,
                        details JSON,
                        before_state JSON,
                        after_state JSON,
                        reason TEXT,
                        ip_address VARCHAR(64),
                        user_agent VARCHAR(255),
                        created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
                    );
                    CREATE TABLE marketplace_accounts (
                        marketplace_account_id INTEGER PRIMARY KEY,
                        organization_id INTEGER NOT NULL REFERENCES lk_organizations(organization_id),
                        marketplace VARCHAR(16) NOT NULL,
                        external_account_id VARCHAR(128) NOT NULL,
                        status VARCHAR(32) NOT NULL,
                        credential_ref VARCHAR(255),
                        created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        CONSTRAINT uq_marketplace_accounts_org_id UNIQUE (organization_id, marketplace_account_id),
                        CONSTRAINT uq_marketplace_accounts_org_marketplace_external
                            UNIQUE (organization_id, marketplace, external_account_id)
                    );
                    """))
        config = Config(str(ROOT / "alembic.ini"))
        config.set_main_option("sqlalchemy.url", owner_url)
        with patch.dict(os.environ, {"VELLA_DATABASE_URL": owner_url}):
            command.stamp(config, "20260905_0060")
            command.upgrade(config, "20260908_0061")
            command.downgrade(config, "20260905_0060")
            command.upgrade(config, "20260908_0061")
        with owner_engine.begin() as connection:
            connection.execute(
                text(
                    f"CREATE ROLE {RUNTIME_ROLE} LOGIN NOSUPERUSER NOCREATEDB "
                    "NOCREATEROLE NOINHERIT NOREPLICATION NOBYPASSRLS"
                )
            )
            connection.execute(text(f"GRANT USAGE ON SCHEMA public TO {RUNTIME_ROLE}"))
            connection.execute(
                text(
                    f"GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {RUNTIME_ROLE}"
                )
            )
            connection.execute(
                text(
                    f"GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {RUNTIME_ROLE}"
                )
            )
            connection.execute(
                text(
                    "INSERT INTO lk_organizations VALUES (1, 'one', 'One'), (2, 'two', 'Two')"
                )
            )
            connection.execute(
                text("INSERT INTO lk_users VALUES ('actor-1', 1), ('actor-2', 2)")
            )
            connection.execute(text("""
                    INSERT INTO marketplace_accounts
                        (marketplace_account_id, organization_id, marketplace, external_account_id, status)
                    VALUES (101, 1, 'avito', 'avito-one-a', 'connected'),
                           (102, 1, 'avito', 'avito-one-b', 'connected'),
                           (103, 1, 'wb', 'wb-one', 'connected'),
                           (104, 1, 'avito', 'avito-disabled', 'disconnected'),
                           (202, 2, 'avito', 'avito-two', 'connected')
                    """))
        runtime_url = f"postgresql+psycopg://{RUNTIME_ROLE}@127.0.0.1:{port}/{database}"
        yield {
            "owner": owner_url,
            "runtime": runtime_url,
            "root": str(root),
            "port": str(port),
        }
        owner_engine.dispose()
    finally:
        subprocess.run(
            [binaries["pg_ctl"], "-D", str(data), "-m", "fast", "-w", "stop"],
            check=True,
            capture_output=True,
            text=True,
        )


@dataclass
class _Clock:
    value: datetime = NOW

    def now(self) -> datetime:
        return self.value


@pytest.fixture
def token_store(disposable_postgres, monkeypatch):
    owner_engine = create_engine(disposable_postgres["owner"])
    runtime_engine = create_engine(disposable_postgres["runtime"])
    factory = sessionmaker(bind=runtime_engine, expire_on_commit=False)
    with owner_engine.begin() as connection:
        connection.execute(text("DELETE FROM lk_audit_events"))
        connection.execute(text("DELETE FROM marketplace_account_ingestion_tokens"))
        connection.execute(
            text(
                "UPDATE marketplace_accounts SET status = CASE "
                "WHEN marketplace_account_id = 104 THEN 'disconnected' ELSE 'connected' END"
            )
        )
    clock = _Clock()
    monkeypatch.setattr(
        ingestion_tokens, "get_session_factory", lambda: factory, raising=False
    )
    monkeypatch.setattr(ingestion_tokens, "_utc_now", clock.now, raising=False)
    try:
        yield {
            "clock": clock,
            "factory": factory,
            "owner_engine": owner_engine,
            "runtime_engine": runtime_engine,
        }
    finally:
        runtime_engine.dispose()
        owner_engine.dispose()


def _owner(
    *, organization_id: int = 1, account_id: int = 101, provider: str = "avito"
) -> MarketplaceAccountCredentialOwner:
    return MarketplaceAccountCredentialOwner(organization_id, account_id, provider)


def _parts(raw_bearer: str) -> tuple[str, str, str, str]:
    prefix, organization_id, token_id, secret = raw_bearer.split(".")
    return prefix, organization_id, token_id, secret


def _wait_for_postgres_lock(owner_engine, backend_pid: int) -> None:
    deadline = time.monotonic() + 5
    with owner_engine.connect() as monitor:
        while time.monotonic() < deadline:
            wait_event_type = monitor.scalar(
                text("SELECT wait_event_type FROM pg_stat_activity WHERE pid = :pid"),
                {"pid": backend_pid},
            )
            if wait_event_type == "Lock":
                return
            time.sleep(0.01)
    pytest.fail("worker did not enter a PostgreSQL lock wait")


@contextmanager
def _pool_releasing_transaction_before_shutdown(transaction, pool):
    with pool as entered_pool:
        try:
            yield entered_pool
        finally:
            if transaction.is_active:
                transaction.rollback()


def _assert_invalid(raw_bearer: object) -> None:
    with pytest.raises(ingestion_tokens.IngestionTokenStoreError) as caught:
        ingestion_tokens.verify_ingestion_token(raw_bearer)  # type: ignore[arg-type]
    assert caught.value.code == "ingestion_token_invalid"
    assert CANARY not in str(caught.value)
    assert CANARY not in repr(caught.value)
    if isinstance(raw_bearer, str) and raw_bearer:
        assert raw_bearer not in str(caught.value)
        assert raw_bearer not in repr(caught.value)


def test_fixture_is_fresh_loopback_postgres_pinned_to_0061(disposable_postgres) -> None:
    assert disposable_postgres["root"].startswith(
        ("/private/var/", "/private/tmp/", "/tmp/")
    )
    assert disposable_postgres["runtime"].split("@")[1].startswith("127.0.0.1:")
    assert disposable_postgres["port"] != "5432"
    engine = create_engine(disposable_postgres["owner"])
    try:
        with engine.connect() as connection:
            assert (
                connection.scalar(text("SELECT version_num FROM alembic_version"))
                == "20260908_0061"
            )
            assert connection.execute(
                text(
                    "SELECT relrowsecurity, relforcerowsecurity FROM pg_class "
                    "WHERE relname = 'marketplace_account_ingestion_tokens'"
                )
            ).one() == (True, True)
    finally:
        engine.dispose()


def test_lock_guard_rolls_back_before_pool_exit_when_sync_assertion_fails() -> None:
    events: list[str] = []

    class FakeTransaction:
        is_active = True

        def rollback(self) -> None:
            events.append("rollback")
            self.is_active = False

    transaction = FakeTransaction()

    class FakeExecutor:
        def __enter__(self):
            return self

        def __exit__(self, _error_type, _error, _traceback) -> bool:
            events.append("pool_exit")
            assert not transaction.is_active
            return False

    with pytest.raises(AssertionError, match="injected synchronization failure"):
        with _pool_releasing_transaction_before_shutdown(transaction, FakeExecutor()):
            events.append("body")
            raise AssertionError("injected synchronization failure")

    assert events == ["body", "rollback", "pool_exit"]


def test_issue_uses_256_bit_secret_and_persists_only_sha256_verifier(
    token_store,
) -> None:
    with patch.object(
        secrets, "token_urlsafe", wraps=secrets.token_urlsafe
    ) as generate:
        issued = ingestion_tokens.issue_ingestion_token(
            _owner(), expires_at=NOW + timedelta(hours=1), actor_user_id="actor-1"
        )
    generate.assert_called_once_with(32)
    raw_bearer = issued.reveal()
    prefix, organization_id, public_id, secret = _parts(raw_bearer)

    assert prefix == "sat1"
    assert organization_id == "1"
    assert public_id == issued.metadata.token_id.hex
    assert UUID(hex=public_id) == issued.metadata.token_id
    assert len(secret) == 43
    assert issued.metadata.status == "active"
    assert issued.metadata.organization_id == 1
    assert issued.metadata.marketplace_account_id == 101
    assert issued.metadata.provider == "avito"
    assert issued.metadata.scope == "avito.browser_snapshot.write"

    with token_store["owner_engine"].connect() as connection:
        row = connection.execute(
            text(
                "SELECT verifier, scope, organization_id, marketplace_account_id, provider "
                "FROM marketplace_account_ingestion_tokens"
            )
        ).one()
        audit = connection.execute(
            text(
                "SELECT actor_user_id, action, object_type, object_id, details "
                "FROM lk_audit_events"
            )
        ).one()
    assert bytes(row.verifier) == hashlib.sha256(secret.encode("ascii")).digest()
    assert len(row.verifier) == 32
    assert row.scope == "avito.browser_snapshot.write"
    assert (row.organization_id, row.marketplace_account_id, row.provider) == (
        1,
        101,
        "avito",
    )
    persisted = repr((row, audit))
    assert raw_bearer not in persisted
    assert secret not in persisted
    assert audit.actor_user_id == "actor-1"
    assert audit.action == "integration.marketplace_ingestion_token.issue"
    assert audit.object_type == "marketplace_account_ingestion_token"
    assert audit.object_id == str(issued.metadata.token_id)
    assert set(audit.details) == {
        "marketplaceAccountId",
        "operation",
        "provider",
        "resultCode",
        "scope",
    }


def test_issue_wrapper_reveals_once_and_resists_common_serializers(
    token_store, caplog
) -> None:
    secret = "S" * 43
    with patch.object(ingestion_tokens.secrets, "token_urlsafe", return_value=secret):
        issued = ingestion_tokens.issue_ingestion_token(
            _owner(), expires_at=NOW + timedelta(hours=1)
        )
    raw_bearer = f"sat1.1.{issued.metadata.token_id.hex}.{secret}"

    assert raw_bearer not in repr(issued)
    assert raw_bearer not in str(issued)
    assert not hasattr(issued, "__dict__")
    serializers = (
        lambda: asdict(issued),
        lambda: json.dumps(issued),
        lambda: to_json(issued),
        lambda: jsonable_encoder(issued),
    )
    for serialize in serializers:
        with pytest.raises(Exception) as caught:
            serialize()
        assert raw_bearer not in str(caught.value)
        assert raw_bearer not in repr(caught.value)

    caplog.set_level(logging.WARNING)
    logging.getLogger("ingestion-token-test").warning("issued=%r", issued)
    assert raw_bearer not in caplog.text
    assert issued.reveal() == raw_bearer
    with pytest.raises(ingestion_tokens.IngestionTokenStoreError) as caught:
        issued.reveal()
    assert caught.value.code == "ingestion_token_already_revealed"
    assert raw_bearer not in str(caught.value)


def test_verify_returns_exact_owner_and_updates_last_used_only_on_success(
    token_store,
) -> None:
    issued = ingestion_tokens.issue_ingestion_token(
        _owner(account_id=102), expires_at=NOW + timedelta(hours=1)
    )
    raw_bearer = issued.reveal()
    token_store["clock"].value = NOW + timedelta(minutes=5)

    verified = ingestion_tokens.verify_ingestion_token(raw_bearer)

    assert verified.token_id == issued.metadata.token_id
    assert verified.owner == _owner(account_id=102)
    assert verified.scope == "avito.browser_snapshot.write"
    assert verified.expires_at == NOW + timedelta(hours=1)
    with token_store["owner_engine"].connect() as connection:
        last_used_at = connection.scalar(
            text(
                "SELECT last_used_at FROM marketplace_account_ingestion_tokens "
                "WHERE token_id = :token_id"
            ),
            {"token_id": issued.metadata.token_id},
        )
    assert last_used_at == NOW + timedelta(minutes=5)


@pytest.mark.parametrize(
    "raw_bearer",
    [
        None,
        "",
        CANARY,
        "sat2.1.00000000000040008000000000000000.AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
        "sat1.01.00000000000040008000000000000000.AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
        "sat1.0.00000000000040008000000000000000.AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
        "sat1.9223372036854775808.00000000000040008000000000000000.AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
        "sat1.2147483648.00000000000040008000000000000000.AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
        "sat1.1.0000000000004000800000000000000A.AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
        "sat1.1.00000000-0000-4000-8000-000000000000.AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
        "sat1.1.00000000000040008000000000000000.short",
        "sat1.1.00000000000040008000000000000000.AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
        "sat1.1.00000000000040008000000000000000.AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA!",
        "sat1.1.00000000000040008000000000000000.AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA.extra",
        "sat1.1.00000000000040008000000000000000.АAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
    ],
)
def test_malformed_bearers_have_one_safe_failure_without_database_lookup(
    token_store, raw_bearer
) -> None:
    statements: list[str] = []

    def capture(
        _connection, _cursor, statement, _parameters, _context, _executemany
    ) -> None:
        statements.append(statement)

    event.listen(token_store["runtime_engine"], "before_cursor_execute", capture)
    try:
        _assert_invalid(raw_bearer)
    finally:
        event.remove(token_store["runtime_engine"], "before_cursor_execute", capture)
    assert statements == []


def test_unknown_wrong_secret_cross_org_and_cross_account_are_uniform(
    token_store, monkeypatch
) -> None:
    first = ingestion_tokens.issue_ingestion_token(
        _owner(), expires_at=NOW + timedelta(hours=1)
    ).reveal()
    second = ingestion_tokens.issue_ingestion_token(
        _owner(account_id=102), expires_at=NOW + timedelta(hours=1)
    ).reveal()
    _, _, first_id, first_secret = _parts(first)
    _, _, second_id, _second_secret = _parts(second)
    failures = [
        f"sat1.1.{uuid4().hex}.{'A' * 43}",
        f"sat1.1.{first_id}.{'A' * 43}",
        f"sat1.2.{first_id}.{first_secret}",
        f"sat1.1.{second_id}.{first_secret}",
    ]
    compared: list[tuple[bytes, bytes]] = []
    real_compare = hmac.compare_digest

    def compare(left: bytes, right: bytes) -> bool:
        compared.append((left, right))
        return real_compare(left, right)

    monkeypatch.setattr(ingestion_tokens.hmac, "compare_digest", compare)
    for failure in failures:
        _assert_invalid(failure)
    assert compared
    assert all(len(left) == len(right) == 32 for left, right in compared)


def test_expired_and_revoked_tokens_are_uniform_and_do_not_update_last_used(
    token_store,
) -> None:
    expired_issue = ingestion_tokens.issue_ingestion_token(
        _owner(), expires_at=NOW + timedelta(minutes=1)
    )
    expired = expired_issue.reveal()
    token_store["clock"].value = NOW + timedelta(minutes=2)
    _assert_invalid(expired)
    expired_status = ingestion_tokens.get_ingestion_token_status(_owner())
    assert expired_status is not None
    assert expired_status.status == "expired"
    assert expired_status.last_used_at is None

    token_store["clock"].value = NOW + timedelta(minutes=3)
    revoked_issue = ingestion_tokens.issue_ingestion_token(
        _owner(account_id=102), expires_at=NOW + timedelta(hours=1)
    )
    revoked_raw = revoked_issue.reveal()
    revoked = ingestion_tokens.revoke_ingestion_tokens(
        _owner(account_id=102), "operator_revoked", actor_user_id="actor-1"
    )
    assert len(revoked) == 1
    assert revoked[0].status == "revoked"
    assert revoked[0].revocation_reason_code == "operator_revoked"
    assert revoked[0].last_used_at is None
    _assert_invalid(revoked_raw)


@pytest.mark.parametrize(
    "status", ["disconnected", "disabled", "inactive", "error", ""]
)
def test_nonconnected_account_blocks_issue_and_verify_but_can_revoke_permanently(
    token_store, status: str
) -> None:
    issued = ingestion_tokens.issue_ingestion_token(
        _owner(), expires_at=NOW + timedelta(hours=1)
    )
    raw_bearer = issued.reveal()
    with token_store["owner_engine"].begin() as connection:
        connection.execute(
            text(
                "UPDATE marketplace_accounts SET status = :status WHERE marketplace_account_id = 101"
            ),
            {"status": status},
        )
    _assert_invalid(raw_bearer)
    with pytest.raises(ingestion_tokens.IngestionTokenStoreError) as caught:
        ingestion_tokens.issue_ingestion_token(
            _owner(), expires_at=NOW + timedelta(hours=1)
        )
    assert caught.value.code == "ingestion_token_account_unavailable"

    lifecycle = ingestion_tokens.get_ingestion_token_status(_owner())
    assert lifecycle is not None
    assert lifecycle.status == "active"
    revoked = ingestion_tokens.revoke_ingestion_tokens(
        _owner(), "account_disconnected", actor_user_id="actor-1"
    )
    assert len(revoked) == 1
    assert revoked[0].status == "revoked"
    assert revoked[0].revocation_reason_code == "account_disconnected"
    lifecycle = ingestion_tokens.get_ingestion_token_status(_owner())
    assert lifecycle is not None
    assert lifecycle.status == "revoked"

    with token_store["owner_engine"].begin() as connection:
        connection.execute(
            text(
                "UPDATE marketplace_accounts SET status = 'connected' "
                "WHERE marketplace_account_id = 101"
            )
        )
    _assert_invalid(raw_bearer)


def test_owner_expiry_and_reason_contracts_fail_before_database_access(
    token_store,
) -> None:
    statements: list[str] = []

    def capture(
        _connection, _cursor, statement, _parameters, _context, _executemany
    ) -> None:
        statements.append(statement)

    event.listen(token_store["runtime_engine"], "before_cursor_execute", capture)
    invalid_calls = (
        lambda: ingestion_tokens.issue_ingestion_token(
            _owner(provider="wb"), expires_at=NOW + timedelta(hours=1)
        ),
        lambda: ingestion_tokens.issue_ingestion_token(
            _owner(organization_id=0), expires_at=NOW + timedelta(hours=1)
        ),
        lambda: ingestion_tokens.issue_ingestion_token(
            _owner(organization_id=True), expires_at=NOW + timedelta(hours=1)
        ),
        lambda: ingestion_tokens.issue_ingestion_token(
            _owner(organization_id=2_147_483_648),
            expires_at=NOW + timedelta(hours=1),
        ),
        lambda: ingestion_tokens.issue_ingestion_token(
            _owner(account_id=2_147_483_648),
            expires_at=NOW + timedelta(hours=1),
        ),
        lambda: ingestion_tokens.issue_ingestion_token(
            _owner(), expires_at=NOW.replace(tzinfo=None)
        ),
        lambda: ingestion_tokens.issue_ingestion_token(_owner(), expires_at=NOW),
    )
    try:
        for call in invalid_calls:
            with pytest.raises(ingestion_tokens.IngestionTokenStoreError) as caught:
                call()
            assert caught.value.code == "ingestion_token_contract_invalid"
        with pytest.raises(ingestion_tokens.IngestionTokenStoreError) as caught:
            ingestion_tokens.revoke_ingestion_tokens(_owner(), CANARY)
        assert caught.value.code == "ingestion_token_reason_invalid"
        assert CANARY not in str(caught.value)
    finally:
        event.remove(token_store["runtime_engine"], "before_cursor_execute", capture)
    assert statements == []


def test_status_and_revoke_are_redacted_and_revoke_is_idempotent(token_store) -> None:
    assert ingestion_tokens.get_ingestion_token_status(_owner()) is None
    issued = ingestion_tokens.issue_ingestion_token(
        _owner(), expires_at=NOW + timedelta(hours=1)
    )
    raw_bearer = issued.reveal()

    active = ingestion_tokens.get_ingestion_token_status(_owner())
    assert active == issued.metadata
    assert set(asdict(active)) == {
        "token_id",
        "organization_id",
        "marketplace_account_id",
        "provider",
        "scope",
        "issued_at",
        "expires_at",
        "revoked_at",
        "revocation_reason_code",
        "last_used_at",
        "status",
    }
    assert raw_bearer not in repr(active)
    assert "verifier" not in repr(active)

    revoked = ingestion_tokens.revoke_ingestion_tokens(_owner(), "security_incident")
    assert len(revoked) == 1
    assert revoked[0].status == "revoked"
    assert ingestion_tokens.revoke_ingestion_tokens(_owner(), "security_incident") == ()
    status = ingestion_tokens.get_ingestion_token_status(_owner())
    assert status is not None and status.status == "revoked"
    assert raw_bearer not in repr((revoked, status))


def test_concurrent_issue_serializes_rotation_to_one_active_token(token_store) -> None:
    barrier = threading.Barrier(2)

    def issue() -> str:
        barrier.wait(timeout=5)
        return ingestion_tokens.issue_ingestion_token(
            _owner(), expires_at=NOW + timedelta(hours=1)
        ).reveal()

    with ThreadPoolExecutor(max_workers=2) as pool:
        raw_bearers = list(pool.map(lambda _index: issue(), range(2)))

    with token_store["owner_engine"].connect() as connection:
        rows = connection.execute(
            text(
                "SELECT revoked_at, revocation_reason_code "
                "FROM marketplace_account_ingestion_tokens ORDER BY token_id"
            )
        ).all()
    assert len(rows) == 2
    assert sum(row.revoked_at is None for row in rows) == 1
    assert [row.revocation_reason_code for row in rows].count("token_rotated") == 1
    outcomes: list[str] = []
    for raw_bearer in raw_bearers:
        try:
            ingestion_tokens.verify_ingestion_token(raw_bearer)
        except ingestion_tokens.IngestionTokenStoreError as exc:
            outcomes.append(exc.code)
        else:
            outcomes.append("valid")
    assert sorted(outcomes) == ["ingestion_token_invalid", "valid"]


def test_verify_refreshes_expiry_after_waiting_for_account_lock(token_store) -> None:
    issued = ingestion_tokens.issue_ingestion_token(
        _owner(), expires_at=NOW + timedelta(minutes=1)
    )
    raw_bearer = issued.reveal()
    locator_read = threading.Event()
    worker_pid: list[int] = []

    def observe_locator_read(
        _connection, _cursor, statement, _parameters, _context, _executemany
    ) -> None:
        normalized = statement.upper()
        if (
            threading.current_thread().name.startswith("verify-expiry")
            and "MARKETPLACE_ACCOUNT_INGESTION_TOKENS" in normalized
            and normalized.lstrip().startswith("SELECT")
            and "FOR UPDATE" not in normalized
        ):
            worker_pid.append(_connection.connection.driver_connection.info.backend_pid)
            locator_read.set()

    lock_connection = token_store["owner_engine"].connect()
    lock_transaction = lock_connection.begin()
    lock_connection.execute(
        text(
            "SELECT marketplace_account_id FROM marketplace_accounts "
            "WHERE marketplace_account_id = 101 FOR UPDATE"
        )
    )
    event.listen(
        token_store["runtime_engine"], "after_cursor_execute", observe_locator_read
    )
    try:
        with _pool_releasing_transaction_before_shutdown(
            lock_transaction,
            ThreadPoolExecutor(max_workers=1, thread_name_prefix="verify-expiry"),
        ) as pool:
            future = pool.submit(ingestion_tokens.verify_ingestion_token, raw_bearer)
            assert locator_read.wait(timeout=5)
            _wait_for_postgres_lock(token_store["owner_engine"], worker_pid[0])
            token_store["clock"].value = NOW + timedelta(minutes=2)
            lock_transaction.commit()
            with pytest.raises(ingestion_tokens.IngestionTokenStoreError) as caught:
                future.result(timeout=5)
            assert caught.value.code == "ingestion_token_invalid"
    finally:
        lock_connection.close()
        event.remove(
            token_store["runtime_engine"],
            "after_cursor_execute",
            observe_locator_read,
        )
    status = ingestion_tokens.get_ingestion_token_status(_owner())
    assert status is not None
    assert status.status == "expired"
    assert status.last_used_at is None


def test_issue_rechecks_expiry_after_lock_and_preserves_prior_token(
    token_store,
) -> None:
    prior = ingestion_tokens.issue_ingestion_token(
        _owner(), expires_at=NOW + timedelta(hours=1)
    )
    prior_raw = prior.reveal()
    lock_attempted = threading.Event()
    worker_pid: list[int] = []

    def observe_account_lock(
        _connection, _cursor, statement, _parameters, _context, _executemany
    ) -> None:
        normalized = statement.upper()
        if (
            threading.current_thread().name.startswith("issue-expiry")
            and "MARKETPLACE_ACCOUNTS" in normalized
            and normalized.lstrip().startswith("SELECT")
            and "FOR UPDATE" in normalized
        ):
            worker_pid.append(_connection.connection.driver_connection.info.backend_pid)
            lock_attempted.set()

    lock_connection = token_store["owner_engine"].connect()
    lock_transaction = lock_connection.begin()
    lock_connection.execute(
        text(
            "SELECT marketplace_account_id FROM marketplace_accounts "
            "WHERE marketplace_account_id = 101 FOR UPDATE"
        )
    )
    event.listen(
        token_store["runtime_engine"], "before_cursor_execute", observe_account_lock
    )
    try:
        with _pool_releasing_transaction_before_shutdown(
            lock_transaction,
            ThreadPoolExecutor(max_workers=1, thread_name_prefix="issue-expiry"),
        ) as pool:
            future = pool.submit(
                ingestion_tokens.issue_ingestion_token,
                _owner(),
                expires_at=NOW + timedelta(minutes=1),
            )
            assert lock_attempted.wait(timeout=5)
            _wait_for_postgres_lock(token_store["owner_engine"], worker_pid[0])
            token_store["clock"].value = NOW + timedelta(minutes=2)
            lock_transaction.commit()
            with pytest.raises(ingestion_tokens.IngestionTokenStoreError) as caught:
                future.result(timeout=5)
            assert caught.value.code == "ingestion_token_contract_invalid"
    finally:
        lock_connection.close()
        event.remove(
            token_store["runtime_engine"],
            "before_cursor_execute",
            observe_account_lock,
        )

    verified = ingestion_tokens.verify_ingestion_token(prior_raw)
    assert verified.token_id == prior.metadata.token_id
    with token_store["owner_engine"].connect() as connection:
        rows = connection.execute(
            text(
                "SELECT token_id, revoked_at FROM marketplace_account_ingestion_tokens"
            )
        ).all()
    assert rows == [(prior.metadata.token_id, None)]


def test_verify_rechecks_revocation_after_account_lock_before_success(
    token_store,
) -> None:
    issued = ingestion_tokens.issue_ingestion_token(
        _owner(), expires_at=NOW + timedelta(hours=1)
    )
    raw_bearer = issued.reveal()
    first_lookup_complete = threading.Event()
    allow_verify_to_lock = threading.Event()
    paused = False

    def pause_after_initial_lookup(
        _connection, _cursor, statement, _parameters, _context, _executemany
    ) -> None:
        nonlocal paused
        normalized = statement.upper()
        if (
            not paused
            and threading.current_thread().name.startswith("verify-race")
            and "MARKETPLACE_ACCOUNT_INGESTION_TOKENS" in normalized
            and normalized.lstrip().startswith("SELECT")
            and "FOR UPDATE" not in normalized
        ):
            paused = True
            first_lookup_complete.set()
            assert allow_verify_to_lock.wait(timeout=5)

    event.listen(
        token_store["runtime_engine"],
        "after_cursor_execute",
        pause_after_initial_lookup,
    )
    try:
        with ThreadPoolExecutor(
            max_workers=1, thread_name_prefix="verify-race"
        ) as pool:
            future = pool.submit(ingestion_tokens.verify_ingestion_token, raw_bearer)
            assert first_lookup_complete.wait(timeout=5)
            revoked = ingestion_tokens.revoke_ingestion_tokens(
                _owner(), "operator_revoked"
            )
            assert len(revoked) == 1
            allow_verify_to_lock.set()
            with pytest.raises(ingestion_tokens.IngestionTokenStoreError) as caught:
                future.result(timeout=5)
            assert caught.value.code == "ingestion_token_invalid"
    finally:
        allow_verify_to_lock.set()
        event.remove(
            token_store["runtime_engine"],
            "after_cursor_execute",
            pause_after_initial_lookup,
        )
    status = ingestion_tokens.get_ingestion_token_status(_owner())
    assert status is not None
    assert status.status == "revoked"
    assert status.last_used_at is None


def test_failed_rotation_rolls_back_old_revocation_and_new_token(
    token_store, monkeypatch
) -> None:
    first = ingestion_tokens.issue_ingestion_token(
        _owner(), expires_at=NOW + timedelta(hours=1)
    )
    first_raw = first.reveal()

    def fail_audit(*_args, **_kwargs) -> None:
        raise SQLAlchemyError(CANARY)

    monkeypatch.setattr(ingestion_tokens, "_audit", fail_audit)
    with pytest.raises(ingestion_tokens.IngestionTokenStoreError) as caught:
        ingestion_tokens.issue_ingestion_token(
            _owner(), expires_at=NOW + timedelta(hours=2)
        )
    assert caught.value.code == "ingestion_token_unavailable"
    assert CANARY not in str(caught.value)
    verified = ingestion_tokens.verify_ingestion_token(first_raw)
    assert verified.token_id == first.metadata.token_id
    with token_store["owner_engine"].connect() as connection:
        rows = connection.execute(
            text(
                "SELECT token_id, revoked_at FROM marketplace_account_ingestion_tokens"
            )
        ).all()
    assert rows == [(first.metadata.token_id, None)]


def test_database_failures_are_safe_and_never_fall_back(
    token_store, monkeypatch
) -> None:
    issued = ingestion_tokens.issue_ingestion_token(
        _owner(), expires_at=NOW + timedelta(hours=1)
    )
    raw_bearer = issued.reveal()

    class BrokenFactory:
        def __call__(self):
            raise SQLAlchemyError(CANARY)

    monkeypatch.setattr(
        ingestion_tokens, "get_session_factory", lambda: BrokenFactory()
    )
    calls = (
        lambda: ingestion_tokens.issue_ingestion_token(
            _owner(), expires_at=NOW + timedelta(hours=1)
        ),
        lambda: ingestion_tokens.verify_ingestion_token(raw_bearer),
        lambda: ingestion_tokens.revoke_ingestion_tokens(_owner(), "operator_revoked"),
        lambda: ingestion_tokens.get_ingestion_token_status(_owner()),
    )
    for call in calls:
        with pytest.raises(ingestion_tokens.IngestionTokenStoreError) as caught:
            call()
        assert caught.value.code == "ingestion_token_unavailable"
        assert CANARY not in str(caught.value)
        assert CANARY not in repr(caught.value)
