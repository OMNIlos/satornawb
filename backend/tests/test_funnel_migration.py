from __future__ import annotations

import importlib
import runpy
from pathlib import Path

from alembic import op
from sqlalchemy import BigInteger, JSON

from app.infra.models import Base

MIGRATION = (
    Path(__file__).resolve().parents[1]
    / "alembic"
    / "versions"
    / "20260904_0059_canonical_funnel_daily.py"
)
TABLES = {"wb_funnel_sync_runs", "wb_funnel_daily"}


def _load_models() -> None:
    importlib.import_module("app.platform.funnel.orm")


def test_funnel_migration_creates_only_forced_rls_tables(monkeypatch) -> None:
    assert MIGRATION.exists()
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

    assert migration["revision"] == "20260904_0059"
    assert migration["down_revision"] == "20260903_0058"
    assert set(created) == TABLES
    for table in TABLES:
        assert f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY" in statements
        assert f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY" in statements
        assert any(
            f"CREATE POLICY tenant_isolation_{table}" in statement
            and "USING (organization_id = NULLIF(current_setting('app.organization_id', true), '')::integer)" in statement
            and "WITH CHECK (organization_id = NULLIF(current_setting('app.organization_id', true), '')::integer)" in statement
            for statement in statements
        )


def test_funnel_downgrade_is_guarded_and_drops_only_funnel_tables(
    monkeypatch,
) -> None:
    statements: list[str] = []
    dropped: list[str] = []
    monkeypatch.setattr(
        op, "execute", lambda statement: statements.append(str(statement))
    )
    monkeypatch.setattr(op, "drop_table", lambda table: dropped.append(table))

    migration = runpy.run_path(str(MIGRATION))
    migration["downgrade"]()

    guard_index = next(
        index for index, item in enumerate(statements) if "RAISE EXCEPTION" in item
    )
    guard = statements[guard_index]
    assert "wb_funnel_sync_runs" in guard
    assert set(statements[:guard_index]) == {
        f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY" for table in TABLES
    }
    assert dropped == ["wb_funnel_daily", "wb_funnel_sync_runs"]
    assert all("wb_advertising" not in statement for statement in statements)


def test_funnel_models_map_minimum_append_only_schema() -> None:
    _load_models()
    run = Base.metadata.tables["wb_funnel_sync_runs"]
    fact = Base.metadata.tables["wb_funnel_daily"]

    assert {
        "sync_run_id",
        "organization_id",
        "marketplace_account_id",
        "parent_sync_run_id",
        "date_from",
        "date_to",
        "source_reference",
        "snapshot_checksum",
        "raw_manifest",
        "raw_manifest_checksum",
        "expected_request_count",
        "completed_request_count",
        "normalizer_version",
        "fact_count",
        "captured_at",
        "last_observed_at",
        "created_at",
    } == set(run.c.keys())
    assert isinstance(run.c.raw_manifest.type, JSON)
    assert run.c.raw_manifest.nullable is False
    assert "status" not in run.c
    assert {
        "funnel_daily_id",
        "organization_id",
        "marketplace_account_id",
        "sync_run_id",
        "source_identity",
        "payload_checksum",
        "business_date",
        "nm_id",
        "currency",
        "open_count",
        "cart_count",
        "order_count",
        "order_amount_kopecks",
        "buyout_count",
        "buyout_amount_kopecks",
        "add_to_wishlist_count",
        "created_at",
    } == set(fact.c.keys())
    for name in (
        "nm_id",
        "open_count",
        "cart_count",
        "order_count",
        "order_amount_kopecks",
        "buyout_count",
        "buyout_amount_kopecks",
        "add_to_wishlist_count",
    ):
        assert isinstance(fact.c[name].type, BigInteger)
    assert all(
        fact.c[name].nullable
        for name in (
            "currency",
            "open_count",
            "cart_count",
            "order_count",
            "order_amount_kopecks",
            "buyout_count",
            "buyout_amount_kopecks",
            "add_to_wishlist_count",
        )
    )


def test_funnel_models_enforce_account_scoped_relationships_and_identity() -> None:
    _load_models()
    run = Base.metadata.tables["wb_funnel_sync_runs"]
    fact = Base.metadata.tables["wb_funnel_daily"]

    run_fks = {
        tuple(element.parent.name for element in constraint.elements)
        for constraint in run.foreign_key_constraints
    }
    assert ("organization_id", "marketplace_account_id") in run_fks
    assert (
        "organization_id",
        "marketplace_account_id",
        "parent_sync_run_id",
    ) in run_fks
    assert (
        "organization_id",
        "marketplace_account_id",
        "sync_run_id",
    ) in {
        tuple(element.parent.name for element in constraint.elements)
        for constraint in fact.foreign_key_constraints
    }

    assert {
        constraint.name for constraint in run.constraints if constraint.name
    } >= {
        "uq_wb_funnel_sync_runs_org_account_id",
        "uq_wb_funnel_sync_runs_snapshot",
        "ck_wb_funnel_sync_runs_period",
        "ck_wb_funnel_sync_runs_counts",
        "ck_wb_funnel_sync_runs_parent_not_self",
    }
    assert {
        constraint.name for constraint in fact.constraints if constraint.name
    } >= {
        "uq_wb_funnel_daily_source_identity",
        "ck_wb_funnel_daily_nm_id",
        "ck_wb_funnel_daily_metrics",
        "ck_wb_funnel_daily_has_metric",
    }
    assert {index.name for index in run.indexes} == {
        "ix_wb_funnel_sync_runs_exact",
        "ix_wb_funnel_sync_runs_parent",
    }
    assert {index.name for index in fact.indexes} == {
        "ix_wb_funnel_daily_product_date"
    }
