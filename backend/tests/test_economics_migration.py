from __future__ import annotations

import runpy
from pathlib import Path

from alembic import op

from app.infra.models import Base
from app.platform.economics import orm as _economics_models  # noqa: F401

MIGRATION = (
    Path(__file__).resolve().parents[1]
    / "alembic"
    / "versions"
    / "20260902_0055_dated_economics.py"
)
TABLES = {
    "organization_economics_versions",
    "catalog_economics_override_versions",
}


def test_dated_economics_migration_creates_forced_rls_ledgers(monkeypatch) -> None:
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

    assert migration["revision"] == "20260902_0055"
    assert migration["down_revision"] == "20260902_0054"
    assert set(created) == TABLES
    for table in TABLES:
        assert f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY" in statements
        assert f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY" in statements
        assert any(
            f"CREATE POLICY tenant_isolation_{table}" in statement
            for statement in statements
        )


def test_dated_economics_orm_keys_keep_tenant_ownership() -> None:
    organization = Base.metadata.tables["organization_economics_versions"]
    override = Base.metadata.tables["catalog_economics_override_versions"]

    assert (
        "organization_id",
        "supersedes_organization_economics_version_id",
    ) in {
        tuple(element.parent.name for element in constraint.elements)
        for constraint in organization.foreign_key_constraints
    }
    override_foreign_keys = {
        tuple(element.parent.name for element in constraint.elements)
        for constraint in override.foreign_key_constraints
    }
    assert ("organization_id", "catalog_sku_id") in override_foreign_keys
    assert (
        "organization_id",
        "supersedes_catalog_economics_override_version_id",
    ) in override_foreign_keys
