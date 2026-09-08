from __future__ import annotations

from types import SimpleNamespace

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.cabinet import store
from app.cabinet.orm import LkUserRow
from app.cabinet.permissions import permissions_from_profile
from app.infra.models import Base
from app.platform.identity.orm import IamMembershipRow


def test_db_user_lifecycle_keeps_canonical_memberships_in_sync(monkeypatch) -> None:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    monkeypatch.setattr(store, "get_engine", lambda: engine)
    monkeypatch.setattr(store, "get_session_factory", lambda: factory)
    monkeypatch.setattr(
        store,
        "_team_user_view",
        lambda **row: SimpleNamespace(
            userId=row["user_id"],
            organizationId=row["organization_id"],
            email=row["email"],
            permissionProfile=row["permission_profile"],
        ),
    )
    monkeypatch.setattr(store, "OrganizationView", SimpleNamespace)
    monkeypatch.setattr(store, "_append_audit_event", lambda **_kwargs: None)

    organization, owner = store.register_organization_owner(
        email="canonical-owner@example.local",
        password_hash="unused",
        full_name="Canonical Owner",
        company_name="Canonical Company",
    )
    team_user = store.create_team_user(
        organization_id=organization.organizationId,
        email="canonical-team@example.local",
        password_hash="unused",
        full_name="Canonical Team",
        permission_profile="viewer",
        actor_user_id=owner.userId,
    )
    store.update_team_user_permission_profile(
        organization_id=organization.organizationId,
        user_id=team_user.userId,
        permission_profile="price_sender",
        actor_user_id=owner.userId,
        reason="test",
        ip_address=None,
        user_agent=None,
    )

    with factory() as session:
        assert session.scalar(select(func.count()).select_from(LkUserRow)) == session.scalar(
            select(func.count()).select_from(IamMembershipRow)
        )
        owner_membership = session.scalar(
            select(IamMembershipRow).where(IamMembershipRow.user_id == owner.userId)
        )
        team_membership = session.scalar(
            select(IamMembershipRow).where(IamMembershipRow.user_id == team_user.userId)
        )

    assert owner_membership is not None
    assert owner_membership.scope_mode == "all"
    assert owner_membership.permissions == sorted(permissions_from_profile("admin"))
    assert team_membership is not None
    assert team_membership.role == "price_sender"
    assert team_membership.permissions == sorted(permissions_from_profile("price_sender"))
