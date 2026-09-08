"""Real PostgreSQL regression tests; never consume an inherited database URL."""

from pathlib import Path
import shutil
import socket
import subprocess
import sys
from uuid import uuid4

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import DBAPIError

from ops.release_gate import run_migration_roundtrip, safe_environment


ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def postgres_cluster(tmp_path_factory):
    binaries = {name: shutil.which(name) for name in ("initdb", "pg_ctl", "createdb")}
    if not all(binaries.values()):
        pytest.fail("Local PostgreSQL binaries are required for migration regression tests")
    root = tmp_path_factory.mktemp("empty-database-migrations")
    data = root / "data"
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    owner = "migration_test_owner"
    def run(args):
        subprocess.run(args, check=True, capture_output=True, text=True)
    run([binaries["initdb"], "-D", str(data), "-A", "trust", "-U", owner,
         "--no-locale", "-E", "UTF8"])
    run([binaries["pg_ctl"], "-D", str(data), "-l", str(root / "postgres.log"),
         "-o", f"-p {port} -h 127.0.0.1 -k /tmp -c fsync=off", "-w", "start"])
    try:
        yield binaries, port, owner
    finally:
        run([binaries["pg_ctl"], "-D", str(data), "-m", "fast", "-w", "stop"])


@pytest.fixture
def database(postgres_cluster, monkeypatch):
    binaries, port, owner = postgres_cluster
    name = "migration_" + uuid4().hex
    subprocess.run([binaries["createdb"], "-h", "127.0.0.1", "-p", str(port),
                    "-U", owner, name], check=True, capture_output=True, text=True)
    url = f"postgresql+psycopg://{owner}@127.0.0.1:{port}/{name}"
    monkeypatch.setenv("VELLA_DATABASE_URL", url)
    config = Config(str(ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(ROOT / "alembic"))
    config.set_main_option("sqlalchemy.url", url)
    engine = create_engine(url)
    try:
        yield config, engine
    finally:
        engine.dispose()


def prompt_column(engine):
    return next(column for column in inspect(engine).get_columns("rv_review_sync_settings")
                if column["name"] == "ai_prompt")


def insert_settings(engine, prompt="Operator prompt — preserve me"):
    with engine.begin() as connection:
        connection.execute(text("""
            INSERT INTO rv_review_sync_settings
                (organization_id, enabled, interval_minutes, token_type,
                 unanswered_only, take, lookback_days, ai_prompt)
            VALUES (1, false, 60, 'personal', true, 10, 7, :prompt)
        """), {"prompt": prompt})


def read_prompt(engine):
    with engine.connect() as connection:
        return connection.execute(text(
            "SELECT ai_prompt FROM rv_review_sync_settings WHERE organization_id = 1"
        )).scalar_one()


def test_empty_database_upgrades_to_head_without_stamp(database):
    config, engine = database
    completed = []
    environment = safe_environment()
    environment["VELLA_DATABASE_URL"] = engine.url.render_as_string(hide_password=False)
    run_migration_roundtrip(sys.executable, environment, completed)
    assert completed == ["migration_upgrade_head", "migration_downgrade_one", "migration_reupgrade_head"]
    with engine.connect() as connection:
        assert connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == (
            ScriptDirectory.from_config(config).get_current_head()
        )
    column = prompt_column(engine)
    assert column["nullable"] is False
    assert column["default"] == "''::text"


def test_0019_roundtrip_preserves_column_owned_by_0017_and_prompt(database):
    config, engine = database
    command.upgrade(config, "20260717_0018")
    insert_settings(engine)
    before = prompt_column(engine)
    command.upgrade(config, "20260717_0019")
    command.downgrade(config, "20260717_0018")
    assert read_prompt(engine) == "Operator prompt — preserve me"
    assert str(prompt_column(engine)["type"]) == str(before["type"])
    assert prompt_column(engine)["nullable"] == before["nullable"]
    assert prompt_column(engine)["default"] == before["default"]
    command.upgrade(config, "20260717_0019")
    assert read_prompt(engine) == "Operator prompt — preserve me"


def test_0019_repairs_legacy_schema_without_prompt(database):
    config, engine = database
    command.upgrade(config, "20260717_0018")
    insert_settings(engine)
    with engine.begin() as connection:
        connection.execute(text("ALTER TABLE rv_review_sync_settings DROP COLUMN ai_prompt"))
    command.upgrade(config, "20260717_0019")
    assert read_prompt(engine) == ""
    assert prompt_column(engine)["nullable"] is False
    command.downgrade(config, "20260717_0018")
    assert read_prompt(engine) == ""


def test_0019_downgrade_of_already_stamped_database_preserves_prompt(database):
    config, engine = database
    command.upgrade(config, "20260717_0018")
    insert_settings(engine)
    # Represents an existing deployment; only this compatibility test stamps.
    command.stamp(config, "20260717_0019")
    command.downgrade(config, "20260717_0018")
    assert read_prompt(engine) == "Operator prompt — preserve me"


def test_0019_rejects_incompatible_existing_column_without_changing_data(database):
    config, engine = database
    command.upgrade(config, "20260717_0018")
    insert_settings(engine)
    with engine.begin() as connection:
        connection.execute(text("ALTER TABLE rv_review_sync_settings ALTER COLUMN ai_prompt DROP NOT NULL"))
    with pytest.raises(DBAPIError, match="incompatible rv_review_sync_settings.ai_prompt schema"):
        command.upgrade(config, "20260717_0019")
    assert read_prompt(engine) == "Operator prompt — preserve me"
    with engine.connect() as connection:
        assert connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == "20260717_0018"
