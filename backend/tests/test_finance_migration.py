from __future__ import annotations

import runpy
from pathlib import Path

from alembic import op
from sqlalchemy import BigInteger
from app.infra.models import Base
from app.platform.finance import orm as _finance_models  # noqa: F401

MIGRATION = (
    Path(__file__).resolve().parents[1]
    / "alembic"
    / "versions"
    / "20260901_0047_period_finance.py"
)
DELTA_MIGRATION = (
    Path(__file__).resolve().parents[1]
    / "alembic"
    / "versions"
    / "20260902_0049_finance_snapshot_deltas.py"
)
ROLLUP_MIGRATION = (
    Path(__file__).resolve().parents[1]
    / "alembic"
    / "versions"
    / "20260902_0052_finance_snapshot_rollups.py"
)
PNL_ROLLUP_MIGRATION = (
    Path(__file__).resolve().parents[1]
    / "alembic"
    / "versions"
    / "20260902_0053_finance_pnl_rollups.py"
)
DAILY_PNL_ROLLUP_MIGRATION = (
    Path(__file__).resolve().parents[1]
    / "alembic"
    / "versions"
    / "20260902_0054_finance_daily_pnl_rollups.py"
)
LOYALTY_MIGRATION = (
    Path(__file__).resolve().parents[1]
    / "alembic"
    / "versions"
    / "20260905_0060_finance_loyalty_evidence.py"
)
TABLES = {
    "wb_finance_sync_runs",
    "wb_finance_operations",
    "wb_finance_sync_run_operations",
}


def test_finance_migration_creates_tenant_tables_and_forces_rls(monkeypatch) -> None:
    created: list[str] = []
    statements: list[str] = []
    monkeypatch.setattr(
        op, "create_table", lambda name, *_args, **_kwargs: created.append(name)
    )
    monkeypatch.setattr(op, "create_index", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        op, "execute", lambda statement: statements.append(str(statement))
    )

    migration = runpy.run_path(str(MIGRATION))
    migration["upgrade"]()

    assert migration["down_revision"] == "20260901_0046"
    assert set(created) == TABLES
    for table in TABLES:
        assert f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY" in statements
        assert f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY" in statements
        assert any(
            f"CREATE POLICY tenant_isolation_{table}" in item for item in statements
        )


def test_finance_membership_foreign_keys_include_tenant_and_account() -> None:
    table = Base.metadata.tables["wb_finance_sync_run_operations"]
    actual = {
        tuple(element.parent.name for element in constraint.elements)
        for constraint in table.foreign_key_constraints
    }

    assert {
        ("organization_id", "marketplace_account_id", "sync_run_id"),
        ("organization_id", "marketplace_account_id", "operation_id"),
    } <= actual


def test_finance_delta_migration_adds_parent_and_membership_state(monkeypatch) -> None:
    columns: list[tuple[str, str]] = []
    foreign_keys: list[tuple[tuple[str, ...], tuple[str, ...]]] = []
    checks: list[str] = []
    indexes: list[tuple[str, tuple[str, ...]]] = []
    monkeypatch.setattr(
        op,
        "add_column",
        lambda table, column: columns.append((table, column.name)),
    )
    monkeypatch.setattr(
        op,
        "create_foreign_key",
        lambda _name, _source, _target, local, remote: foreign_keys.append(
            (tuple(local), tuple(remote))
        ),
    )
    monkeypatch.setattr(
        op,
        "create_check_constraint",
        lambda _name, _table, condition: checks.append(str(condition)),
    )
    monkeypatch.setattr(
        op,
        "create_index",
        lambda name, _table, fields: indexes.append((name, tuple(fields))),
    )

    migration = runpy.run_path(str(DELTA_MIGRATION))
    migration["upgrade"]()

    assert migration["down_revision"] == "20260902_0048"
    assert columns == [
        ("wb_finance_sync_runs", "parent_sync_run_id"),
        ("wb_finance_sync_runs", "is_materialized"),
        ("wb_finance_sync_run_operations", "is_present"),
    ]
    assert foreign_keys == [
        (
            ("organization_id", "marketplace_account_id", "parent_sync_run_id"),
            ("organization_id", "marketplace_account_id", "sync_run_id"),
        )
    ]
    assert checks == ["parent_sync_run_id IS NULL OR parent_sync_run_id <> sync_run_id"]
    assert indexes == [
        (
            "ix_wb_finance_sync_runs_parent",
            ("organization_id", "marketplace_account_id", "parent_sync_run_id"),
        )
    ]


def test_finance_rollup_migration_adds_atomic_tenant_projection(monkeypatch) -> None:
    columns: list[tuple[str, str]] = []
    tables: list[str] = []
    statements: list[str] = []
    monkeypatch.setattr(
        op,
        "add_column",
        lambda table, column: columns.append((table, column.name)),
    )
    monkeypatch.setattr(
        op,
        "create_table",
        lambda name, *_args, **_kwargs: tables.append(name),
    )
    monkeypatch.setattr(
        op,
        "execute",
        lambda statement: statements.append(str(statement)),
    )

    migration = runpy.run_path(str(ROLLUP_MIGRATION))
    migration["upgrade"]()

    assert migration["down_revision"] == "20260902_0051"
    assert columns == [("wb_finance_sync_runs", "is_rollup_materialized")]
    assert tables == ["wb_finance_sync_run_sku_rollups"]
    assert "ALTER TABLE wb_finance_sync_run_sku_rollups ENABLE ROW LEVEL SECURITY" in statements
    assert "ALTER TABLE wb_finance_sync_run_sku_rollups FORCE ROW LEVEL SECURITY" in statements
    assert any(
        "CREATE POLICY tenant_isolation_wb_finance_sync_run_sku_rollups" in statement
        for statement in statements
    )


def test_finance_pnl_rollup_migration_adds_rollback_safe_projection(
    monkeypatch,
) -> None:
    columns: list[tuple[str, str]] = []
    tables: list[str] = []
    statements: list[str] = []
    monkeypatch.setattr(
        op,
        "add_column",
        lambda table, column: columns.append((table, column.name)),
    )
    monkeypatch.setattr(
        op,
        "create_table",
        lambda name, *_args, **_kwargs: tables.append(name),
    )
    monkeypatch.setattr(
        op,
        "execute",
        lambda statement: statements.append(str(statement)),
    )

    migration = runpy.run_path(str(PNL_ROLLUP_MIGRATION))
    migration["upgrade"]()

    assert migration["revision"] == "20260902_0053"
    assert migration["down_revision"] == "20260902_0052"
    assert columns == [("wb_finance_sync_runs", "is_pnl_rollup_materialized")]
    assert tables == ["wb_finance_sync_run_sku_pnl_rollups"]
    assert (
        "ALTER TABLE wb_finance_sync_run_sku_pnl_rollups ENABLE ROW LEVEL SECURITY"
        in statements
    )
    assert (
        "ALTER TABLE wb_finance_sync_run_sku_pnl_rollups FORCE ROW LEVEL SECURITY"
        in statements
    )
    assert any(
        "CREATE POLICY tenant_isolation_wb_finance_sync_run_sku_pnl_rollups"
        in statement
        for statement in statements
    )


def test_finance_pnl_rollup_orm_key_contains_tenant_account_and_snapshot() -> None:
    table = Base.metadata.tables["wb_finance_sync_run_sku_pnl_rollups"]

    assert tuple(column.name for column in table.primary_key.columns) == (
        "organization_id",
        "marketplace_account_id",
        "sync_run_id",
        "nm_id",
    )
    assert {
        tuple(element.parent.name for element in constraint.elements)
        for constraint in table.foreign_key_constraints
    } == {("organization_id", "marketplace_account_id", "sync_run_id")}


def test_finance_daily_pnl_migration_adds_period_acceleration(monkeypatch) -> None:
    columns: list[tuple[str, str]] = []
    tables: list[str] = []
    statements: list[str] = []
    monkeypatch.setattr(
        op,
        "add_column",
        lambda table, column: columns.append((table, column.name)),
    )
    monkeypatch.setattr(
        op,
        "create_table",
        lambda name, *_args, **_kwargs: tables.append(name),
    )
    monkeypatch.setattr(op, "execute", lambda statement: statements.append(str(statement)))

    migration = runpy.run_path(str(DAILY_PNL_ROLLUP_MIGRATION))
    migration["upgrade"]()

    table = "wb_finance_sync_run_sku_daily_pnl_rollups"
    assert migration["revision"] == "20260902_0054"
    assert migration["down_revision"] == "20260902_0053"
    assert columns == [("wb_finance_sync_runs", "is_daily_pnl_rollup_materialized")]
    assert tables == [table]
    assert f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY" in statements
    assert f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY" in statements


def test_finance_daily_pnl_orm_key_contains_period_dimension() -> None:
    table = Base.metadata.tables["wb_finance_sync_run_sku_daily_pnl_rollups"]

    assert tuple(column.name for column in table.primary_key.columns) == (
        "organization_id",
        "marketplace_account_id",
        "sync_run_id",
        "business_date",
        "nm_id",
    )


def test_finance_loyalty_migration_adds_nullable_money_evidence(
    monkeypatch,
) -> None:
    added: list[tuple[str, str, bool, bool]] = []
    dropped: list[tuple[str, str]] = []
    statements: list[str] = []
    monkeypatch.setattr(
        op,
        "add_column",
        lambda table, column: added.append(
            (table, column.name, column.nullable, isinstance(column.type, BigInteger))
        ),
    )
    monkeypatch.setattr(
        op, "drop_column", lambda table, column: dropped.append((table, column))
    )
    monkeypatch.setattr(
        op, "execute", lambda statement: statements.append(str(statement))
    )

    migration = runpy.run_path(str(LOYALTY_MIGRATION))
    migration["upgrade"]()
    migration["downgrade"]()

    tables = (
        "wb_finance_operations",
        "wb_finance_sync_run_sku_pnl_rollups",
        "wb_finance_sync_run_sku_daily_pnl_rollups",
    )
    columns = (
        "cashback_amount_kopecks",
        "cashback_discount_kopecks",
        "cashback_commission_change_kopecks",
    )
    expected = [(table, column) for table in tables for column in columns]
    assert migration["revision"] == "20260905_0060"
    assert migration["down_revision"] == "20260904_0059"
    assert [(table, column) for table, column, _nullable, _bigint in added] == expected
    assert all(nullable and bigint for _table, _column, nullable, bigint in added)
    assert set(dropped) == set(expected)
    guard_index = next(
        index for index, statement in enumerate(statements) if "RAISE EXCEPTION" in statement
    )
    guard = statements[guard_index]
    assert all(table in guard for table in tables)
    assert "cannot downgrade while canonical loyalty evidence exists" in guard
    for table in tables:
        disable = f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY"
        enable = f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY"
        force = f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY"
        assert statements.index(disable) < guard_index
        assert guard_index < statements.index(enable) < statements.index(force)
