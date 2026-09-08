from __future__ import annotations

import importlib
import runpy
from pathlib import Path

from alembic import op
from sqlalchemy import BigInteger, DateTime, Integer, JSON

from app.infra.models import Base

MIGRATION = (
    Path(__file__).resolve().parents[1]
    / "alembic"
    / "versions"
    / "20260903_0057_canonical_advertising.py"
)
RAW_MIGRATION = (
    Path(__file__).resolve().parents[1]
    / "alembic"
    / "versions"
    / "20260903_0058_raw_advertising_evidence.py"
)
COMPATIBILITY_STAMP = (
    Path(__file__).resolve().parents[1]
    / "alembic"
    / "versions"
    / "20260903_0056_external_stamp.py"
)
TABLES = {"wb_advertising_sync_runs", "wb_advertising_facts"}
RAW_TABLES = {
    "wb_advertising_campaign_snapshots",
    "wb_advertising_spend_documents",
}


def _load_models() -> None:
    assert importlib.util.find_spec("app.platform.advertising.orm") is not None
    importlib.import_module("app.platform.advertising.orm")


def test_advertising_migration_creates_forced_rls_tables(monkeypatch) -> None:
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

    assert migration["revision"] == "20260903_0057"
    assert migration["down_revision"] == "20260903_0056"
    assert set(created) == TABLES
    for table in TABLES:
        assert f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY" in statements
        assert f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY" in statements
        assert any(
            f"CREATE POLICY tenant_isolation_{table}" in statement
            for statement in statements
        )


def test_external_0056_stamp_is_an_explicit_noop() -> None:
    assert COMPATIBILITY_STAMP.exists()
    migration = runpy.run_path(str(COMPATIBILITY_STAMP))

    assert migration["revision"] == "20260903_0056"
    assert migration["down_revision"] == "20260902_0055"
    assert migration["upgrade"]() is None
    assert migration["downgrade"]() is None


def test_advertising_fact_fk_contains_tenant_account_and_run() -> None:
    _load_models()
    table = Base.metadata.tables["wb_advertising_facts"]

    assert (
        "organization_id",
        "marketplace_account_id",
        "sync_run_id",
    ) in {
        tuple(element.parent.name for element in constraint.elements)
        for constraint in table.foreign_key_constraints
    }


def test_advertising_run_fk_contains_tenant_and_account() -> None:
    _load_models()
    table = Base.metadata.tables["wb_advertising_sync_runs"]

    assert ("organization_id", "marketplace_account_id") in {
        tuple(element.parent.name for element in constraint.elements)
        for constraint in table.foreign_key_constraints
    }


def test_raw_advertising_migration_extends_0057_and_forces_rls(monkeypatch) -> None:
    assert RAW_MIGRATION.exists()
    created: list[str] = []
    added: dict[str, dict[str, object]] = {}
    checks: dict[str, str] = {}
    statements: list[str] = []
    monkeypatch.setattr(
        op, "create_table", lambda name, *_args, **_kwargs: created.append(name)
    )
    monkeypatch.setattr(
        op,
        "add_column",
        lambda table, column: added.setdefault(table, {}).update({column.name: column}),
    )
    monkeypatch.setattr(op, "alter_column", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(op, "create_index", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(op, "create_foreign_key", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(op, "create_unique_constraint", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        op,
        "create_check_constraint",
        lambda name, _table, condition: checks.update({name: str(condition)}),
    )
    monkeypatch.setattr(op, "drop_constraint", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        op, "execute", lambda statement: statements.append(str(statement))
    )

    migration = runpy.run_path(str(RAW_MIGRATION))
    migration["upgrade"]()

    assert migration["revision"] == "20260903_0058"
    assert migration["down_revision"] == "20260903_0057"
    assert set(created) == RAW_TABLES
    run_columns = added["wb_advertising_sync_runs"]
    assert {
        "parent_sync_run_id",
        "raw_manifest",
        "raw_manifest_checksum",
        "expected_request_count",
        "completed_request_count",
        "campaign_count",
        "spend_document_count",
        "document_total_spend_kopecks",
    } <= set(run_columns)
    assert run_columns["raw_manifest"].nullable is True
    assert run_columns["expected_request_count"].nullable is True
    assert run_columns["completed_request_count"].nullable is True
    coverage = checks["ck_wb_advertising_sync_runs_raw_coverage"]
    assert "raw_manifest IS NULL" in coverage
    assert "raw_manifest_checksum IS NULL" in coverage
    assert "expected_request_count IS NULL" in coverage
    assert "completed_request_count IS NULL" in coverage
    assert "raw_manifest IS NOT NULL" in coverage
    assert "raw_manifest_checksum IS NOT NULL" in coverage
    assert "expected_request_count >= 0" in coverage
    assert "completed_request_count >= 0" in coverage
    assert "completed_request_count <= expected_request_count" in coverage
    backfill = next(
        item for item in statements if "UPDATE wb_advertising_facts AS fact" in item
    )
    assert "fact.business_date IS NULL THEN 'period' ELSE 'day'" in backfill
    assert "date_from = COALESCE(fact.business_date, run.date_from)" in backfill
    assert "date_to = COALESCE(fact.business_date, run.date_to)" in backfill
    assert "WHEN fact.nm_id IS NOT NULL THEN 'source_sku'" in backfill
    assert "WHEN fact.campaign_id IS NOT NULL THEN 'campaign'" in backfill
    assert "ELSE 'account'" in backfill
    duplicate_guard = next(item for item in statements if "RAISE EXCEPTION" in item)
    for table in TABLES:
        disable = f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY"
        enable = f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY"
        force = f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY"
        assert statements.index(disable) < statements.index(backfill)
        assert statements.index(duplicate_guard) < statements.index(enable)
        assert statements.index(enable) < statements.index(force)
    for table in RAW_TABLES:
        assert f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY" in statements
        assert f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY" in statements
        assert any(
            f"CREATE POLICY tenant_isolation_{table}" in statement
            for statement in statements
        )


def test_raw_advertising_downgrade_exposes_guard_and_restores_rls(
    monkeypatch,
) -> None:
    statements: list[str] = []
    monkeypatch.setattr(
        op, "execute", lambda statement: statements.append(str(statement))
    )
    for operation in (
        "drop_table",
        "drop_index",
        "drop_constraint",
        "create_unique_constraint",
        "create_check_constraint",
        "alter_column",
        "drop_column",
    ):
        monkeypatch.setattr(op, operation, lambda *_args, **_kwargs: None)

    migration = runpy.run_path(str(RAW_MIGRATION))
    migration["downgrade"]()

    raw_guard = next(
        item
        for item in statements
        if "formula_version = 'wb-advertising-raw-v1'" in item
    )
    for table in TABLES:
        disable = f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY"
        enable = f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY"
        force = f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY"
        assert statements.index(disable) < statements.index(raw_guard)
        assert statements.index(raw_guard) < statements.index(enable)
        assert statements.index(enable) < statements.index(force)


def test_raw_advertising_models_map_evidence_and_composite_children() -> None:
    _load_models()
    run = Base.metadata.tables["wb_advertising_sync_runs"]
    assert {
        "parent_sync_run_id",
        "raw_manifest",
        "raw_manifest_checksum",
        "expected_request_count",
        "completed_request_count",
        "campaign_count",
        "spend_document_count",
        "document_total_spend_kopecks",
    } <= set(run.c.keys())
    coverage = next(
        constraint
        for constraint in run.constraints
        if constraint.name == "ck_wb_advertising_sync_runs_raw_coverage"
    )
    assert "completed_request_count <= expected_request_count" in str(coverage.sqltext)
    assert isinstance(run.c.raw_manifest.type, JSON)
    assert isinstance(run.c.expected_request_count.type, Integer)
    assert isinstance(run.c.completed_request_count.type, Integer)

    fact = Base.metadata.tables["wb_advertising_facts"]
    assert {
        "grain",
        "date_from",
        "date_to",
        "fact_scope",
        "app_type",
        "currency",
        "cancel_count",
    } <= set(fact.c.keys())
    assert all(
        not fact.c[name].nullable
        for name in ("grain", "date_from", "date_to", "fact_scope")
    )
    assert fact.c.spend_kopecks.nullable is True

    expected_columns = {
        "wb_advertising_campaign_snapshots": {
            "source_identity",
            "payload_checksum",
            "campaign_id",
            "name",
            "campaign_type",
            "status",
            "payment_type",
            "bid_type",
            "member_nm_ids",
        },
        "wb_advertising_spend_documents": {
            "source_identity",
            "payload_checksum",
            "upd_num",
            "upd_time",
            "business_date",
            "campaign_id",
            "campaign_name",
            "campaign_type",
            "payment_type",
            "campaign_status",
            "currency",
            "spend_kopecks",
        },
    }
    for name, evidence_columns in expected_columns.items():
        table = Base.metadata.tables[name]
        assert evidence_columns <= set(table.c.keys())
        assert ("organization_id", "marketplace_account_id", "sync_run_id") in {
            tuple(element.parent.name for element in constraint.elements)
            for constraint in table.foreign_key_constraints
        }
    campaign = Base.metadata.tables["wb_advertising_campaign_snapshots"]
    document = Base.metadata.tables["wb_advertising_spend_documents"]
    assert isinstance(campaign.c.campaign_id.type, BigInteger)
    assert isinstance(campaign.c.member_nm_ids.type, JSON)
    assert isinstance(document.c.campaign_id.type, BigInteger)
    assert isinstance(document.c.spend_kopecks.type, BigInteger)
    assert isinstance(document.c.upd_time.type, DateTime)
    assert document.c.upd_time.type.timezone is True
