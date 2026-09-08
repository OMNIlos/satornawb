from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_runtime_database_role_is_isolated_from_migrations() -> None:
    compose = (ROOT / "docker-compose.yml").read_text()
    role_sql = (ROOT / "ops" / "runtime-db-role.sql").read_text()
    migrate = compose.split("  migrate:", 1)[1].split("  api:", 1)[0]
    api = compose.split("  api:", 1)[1].split("  worker:", 1)[0]

    assert "VELLA_MIGRATION_DATABASE_URL" in migrate
    assert "python -m alembic upgrade head" in migrate
    assert "service_completed_successfully" in api
    assert "python -m alembic upgrade head" not in api
    assert "python -m uvicorn app.main:app" in api

    for attribute in (
        "NOSUPERUSER",
        "NOCREATEDB",
        "NOCREATEROLE",
        "NOREPLICATION",
        "NOBYPASSRLS",
    ):
        assert attribute in role_sql
    assert "GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES" in role_sql
    assert "GRANT USAGE, SELECT, UPDATE ON ALL SEQUENCES" in role_sql
    assert "ALTER DEFAULT PRIVILEGES" in role_sql
    assert "REVOKE ALL ON TABLE public.alembic_version" in role_sql
    assert "wb_finance_sync_run_sku_rollups" in role_sql
    assert "wb_finance_sync_run_sku_pnl_rollups" in role_sql
    assert "wb_finance_sync_run_sku_daily_pnl_rollups" in role_sql
    assert "organization_economics_versions" in role_sql
    assert "catalog_economics_override_versions" in role_sql
    assert "relrowsecurity" in role_sql
    assert "relforcerowsecurity" in role_sql
