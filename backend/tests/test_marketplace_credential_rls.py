from __future__ import annotations

import os
import shutil
import socket
import subprocess
from collections.abc import Iterator
from pathlib import Path
from unittest.mock import patch

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError, IntegrityError


ROOT = Path(__file__).resolve().parents[1]
RUNTIME_ROLE = "satorna_credential_test_runtime"


def _free_loopback_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


@pytest.fixture(scope="module")
def disposable_postgres(tmp_path_factory: pytest.TempPathFactory) -> Iterator[dict[str, str]]:
    required = ("initdb", "pg_ctl", "createdb")
    binaries = {name: shutil.which(name) for name in required}
    if any(path is None for path in binaries.values()):
        pytest.fail("disposable PostgreSQL 16 binaries are required for forced-RLS tests")
    root = tmp_path_factory.mktemp("marketplace-credential-postgres")
    data = root / "data"
    log = root / "postgres.log"
    port = _free_loopback_port()
    owner = "satorna_credential_test_owner"
    database = "satorna_credential_test"
    subprocess.run(
        [binaries["initdb"], "-D", str(data), "-A", "trust", "-U", owner, "--no-locale", "-E", "UTF8"],
        check=True,
        capture_output=True,
        text=True,
    )
    options = f"-p {port} -h 127.0.0.1 -k /tmp -c fsync=off -c synchronous_commit=off"
    subprocess.run(
        [binaries["pg_ctl"], "-D", str(data), "-l", str(log), "-o", options, "-w", "start"],
        check=True,
        capture_output=True,
        text=True,
    )
    try:
        subprocess.run(
            [binaries["createdb"], "-h", "127.0.0.1", "-p", str(port), "-U", owner, database],
            check=True,
            capture_output=True,
            text=True,
        )
        owner_url = f"postgresql+psycopg://{owner}@127.0.0.1:{port}/{database}"
        owner_engine = create_engine(owner_url)
        with owner_engine.begin() as connection:
            connection.execute(
                text(
                    """
                    CREATE TABLE lk_organizations (
                        organization_id INTEGER PRIMARY KEY,
                        slug VARCHAR(64) NOT NULL UNIQUE,
                        name VARCHAR(255) NOT NULL
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
                    """
                )
            )
        config = Config(str(ROOT / "alembic.ini"))
        config.set_main_option("sqlalchemy.url", owner_url)
        with patch.dict(os.environ, {"VELLA_DATABASE_URL": owner_url}):
            command.stamp(config, "20260905_0060")
            command.upgrade(config, "20260908_0061")
            command.downgrade(config, "20260905_0060")
            command.upgrade(config, "20260908_0061")
        with owner_engine.begin() as connection:
            connection.execute(text(f"CREATE ROLE {RUNTIME_ROLE} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOREPLICATION NOBYPASSRLS"))
            connection.execute(text(f"GRANT USAGE ON SCHEMA public TO {RUNTIME_ROLE}"))
            connection.execute(text(f"GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {RUNTIME_ROLE}"))
            connection.execute(text("INSERT INTO lk_organizations VALUES (1, 'one', 'One'), (2, 'two', 'Two')"))
            connection.execute(
                text(
                    """
                    INSERT INTO marketplace_accounts
                        (marketplace_account_id, organization_id, marketplace, external_account_id, status)
                    VALUES (101, 1, 'wb', 'wb-one', 'connected'),
                           (202, 2, 'avito', 'avito-two', 'connected')
                    """
                )
            )
        runtime_url = f"postgresql+psycopg://{RUNTIME_ROLE}@127.0.0.1:{port}/{database}"
        yield {"owner": owner_url, "runtime": runtime_url, "root": str(root), "port": str(port)}
        owner_engine.dispose()
    finally:
        subprocess.run(
            [binaries["pg_ctl"], "-D", str(data), "-m", "fast", "-w", "stop"],
            check=True,
            capture_output=True,
            text=True,
        )


def _credential_values(*, credential_id: str, organization_id: int, account_id: int, provider: str) -> dict[str, object]:
    return {
        "credential_id": credential_id,
        "organization_id": organization_id,
        "marketplace_account_id": account_id,
        "provider": provider,
        "credential_kind": "wb_api" if provider == "wb" else "avito_oauth_client",
        "algorithm": "AES-256-GCM",
        "key_version": 1,
        "aad_version": 1,
        "payload_schema_version": 1,
        "nonce": b"n" * 12,
        "ciphertext": b"c" * 32,
        "generation": 1,
    }


INSERT_CREDENTIAL = text(
    """
    INSERT INTO marketplace_account_credentials
        (credential_id, organization_id, marketplace_account_id, provider,
         credential_kind, algorithm, key_version, aad_version,
         payload_schema_version, nonce, ciphertext, generation)
    VALUES
        (:credential_id, :organization_id, :marketplace_account_id, :provider,
         :credential_kind, :algorithm, :key_version, :aad_version,
         :payload_schema_version, :nonce, :ciphertext, :generation)
    """
)


def test_postgres_fixture_is_provably_disposable_and_loopback(disposable_postgres) -> None:
    assert disposable_postgres["root"].startswith("/private/var/") or disposable_postgres["root"].startswith("/tmp/")
    assert disposable_postgres["runtime"].split("@")[1].startswith("127.0.0.1:")
    assert disposable_postgres["port"] != "5432"


def test_migration_cycle_leaves_forced_rls_and_non_bypass_runtime(disposable_postgres) -> None:
    engine = create_engine(disposable_postgres["owner"])
    with engine.connect() as connection:
        rows = connection.execute(
            text(
                """
                SELECT relname, relrowsecurity, relforcerowsecurity
                FROM pg_class
                WHERE relname IN ('marketplace_account_credentials', 'marketplace_account_ingestion_tokens')
                ORDER BY relname
                """
            )
        ).all()
        assert rows == [
            ("marketplace_account_credentials", True, True),
            ("marketplace_account_ingestion_tokens", True, True),
        ]
        attributes = connection.execute(
            text("SELECT rolsuper, rolcreatedb, rolcreaterole, rolreplication, rolbypassrls FROM pg_roles WHERE rolname = :role"),
            {"role": RUNTIME_ROLE},
        ).one()
        assert attributes == (False, False, False, False, False)
    engine.dispose()


def test_no_context_and_wrong_org_cannot_read_update_or_delete(disposable_postgres) -> None:
    owner = create_engine(disposable_postgres["owner"])
    runtime = create_engine(disposable_postgres["runtime"])
    values = _credential_values(
        credential_id="10000000-0000-4000-8000-000000000001",
        organization_id=1,
        account_id=101,
        provider="wb",
    )
    with owner.begin() as connection:
        connection.execute(INSERT_CREDENTIAL, values)
    with runtime.begin() as connection:
        assert connection.scalar(text("SELECT count(*) FROM marketplace_account_credentials")) == 0
        assert connection.execute(text("UPDATE marketplace_account_credentials SET generation = generation + 1")).rowcount == 0
        assert connection.execute(text("DELETE FROM marketplace_account_credentials")).rowcount == 0
    no_context = _credential_values(
        credential_id="15000000-0000-4000-8000-000000000001",
        organization_id=1,
        account_id=101,
        provider="wb",
    )
    with pytest.raises(DBAPIError):
        with runtime.begin() as connection:
            connection.execute(INSERT_CREDENTIAL, no_context)
    with runtime.begin() as connection:
        connection.execute(text("SELECT set_config('app.organization_id', '2', true)"))
        assert connection.scalar(text("SELECT count(*) FROM marketplace_account_credentials")) == 0
        assert connection.execute(text("UPDATE marketplace_account_credentials SET generation = 2")).rowcount == 0
        assert connection.execute(text("DELETE FROM marketplace_account_credentials")).rowcount == 0
    with runtime.begin() as connection:
        connection.execute(text("SELECT set_config('app.organization_id', '1', true)"))
        assert connection.scalar(text("SELECT count(*) FROM marketplace_account_credentials")) == 1
    owner.dispose()
    runtime.dispose()


def test_wrong_org_insert_and_cross_tenant_update_are_denied(disposable_postgres) -> None:
    runtime = create_engine(disposable_postgres["runtime"])
    wrong = _credential_values(
        credential_id="20000000-0000-4000-8000-000000000002",
        organization_id=1,
        account_id=101,
        provider="wb",
    )
    with pytest.raises(DBAPIError):
        with runtime.begin() as connection:
            connection.execute(text("SELECT set_config('app.organization_id', '2', true)"))
            connection.execute(INSERT_CREDENTIAL, wrong)
    with pytest.raises(DBAPIError):
        with runtime.begin() as connection:
            connection.execute(text("SELECT set_config('app.organization_id', '1', true)"))
            connection.execute(
                text("UPDATE marketplace_account_credentials SET organization_id = 2 WHERE credential_id = '10000000-0000-4000-8000-000000000001'")
            )
    runtime.dispose()


def test_provider_fk_and_one_active_constraint_are_enforced(disposable_postgres) -> None:
    owner = create_engine(disposable_postgres["owner"])
    mismatch = _credential_values(
        credential_id="30000000-0000-4000-8000-000000000003",
        organization_id=1,
        account_id=101,
        provider="avito",
    )
    with pytest.raises(IntegrityError):
        with owner.begin() as connection:
            connection.execute(INSERT_CREDENTIAL, mismatch)
    duplicate = _credential_values(
        credential_id="40000000-0000-4000-8000-000000000004",
        organization_id=1,
        account_id=101,
        provider="wb",
    )
    with pytest.raises(IntegrityError):
        with owner.begin() as connection:
            connection.execute(INSERT_CREDENTIAL, duplicate)
    with owner.begin() as connection:
        connection.execute(
            text(
                "UPDATE marketplace_account_credentials SET revoked_at = CURRENT_TIMESTAMP, revocation_reason_code = 'credential_replaced' WHERE credential_id = '10000000-0000-4000-8000-000000000001'"
            )
        )
        connection.execute(INSERT_CREDENTIAL, duplicate)
    owner.dispose()


def test_ingestion_tokens_are_tenant_scoped(disposable_postgres) -> None:
    owner = create_engine(disposable_postgres["owner"])
    runtime = create_engine(disposable_postgres["runtime"])
    with owner.begin() as connection:
        connection.execute(
            text(
                """
                INSERT INTO marketplace_account_ingestion_tokens
                    (token_id, organization_id, marketplace_account_id, provider,
                     verifier, scope, issued_at, expires_at)
                VALUES ('50000000-0000-4000-8000-000000000005', 2, 202, 'avito',
                        :verifier, 'avito.browser_snapshot.write', CURRENT_TIMESTAMP,
                        CURRENT_TIMESTAMP + INTERVAL '1 hour')
                """
            ),
            {"verifier": b"v" * 32},
        )
    with runtime.begin() as connection:
        assert connection.scalar(text("SELECT count(*) FROM marketplace_account_ingestion_tokens")) == 0
        assert connection.execute(text("UPDATE marketplace_account_ingestion_tokens SET last_used_at = CURRENT_TIMESTAMP")).rowcount == 0
        assert connection.execute(text("DELETE FROM marketplace_account_ingestion_tokens")).rowcount == 0
    with pytest.raises(DBAPIError):
        with runtime.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO marketplace_account_ingestion_tokens
                        (token_id, organization_id, marketplace_account_id, provider,
                         verifier, scope, issued_at, expires_at)
                    VALUES ('55000000-0000-4000-8000-000000000005', 2, 202, 'avito',
                            :verifier, 'avito.browser_snapshot.write', CURRENT_TIMESTAMP,
                            CURRENT_TIMESTAMP + INTERVAL '1 hour')
                    """
                ),
                {"verifier": b"w" * 32},
            )
    with runtime.begin() as connection:
        connection.execute(text("SELECT set_config('app.organization_id', '1', true)"))
        assert connection.scalar(text("SELECT count(*) FROM marketplace_account_ingestion_tokens")) == 0
        assert connection.execute(text("UPDATE marketplace_account_ingestion_tokens SET last_used_at = CURRENT_TIMESTAMP")).rowcount == 0
        assert connection.execute(text("DELETE FROM marketplace_account_ingestion_tokens")).rowcount == 0
    with pytest.raises(DBAPIError):
        with runtime.begin() as connection:
            connection.execute(text("SELECT set_config('app.organization_id', '1', true)"))
            connection.execute(
                text(
                    """
                    INSERT INTO marketplace_account_ingestion_tokens
                        (token_id, organization_id, marketplace_account_id, provider,
                         verifier, scope, issued_at, expires_at)
                    VALUES ('56000000-0000-4000-8000-000000000005', 2, 202, 'avito',
                            :verifier, 'avito.browser_snapshot.write', CURRENT_TIMESTAMP,
                            CURRENT_TIMESTAMP + INTERVAL '1 hour')
                    """
                ),
                {"verifier": b"x" * 32},
            )
    with runtime.begin() as connection:
        connection.execute(text("SELECT set_config('app.organization_id', '2', true)"))
        assert connection.scalar(text("SELECT count(*) FROM marketplace_account_ingestion_tokens")) == 1
    owner.dispose()
    runtime.dispose()
