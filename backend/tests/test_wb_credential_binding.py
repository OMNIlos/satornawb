from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.cabinet import store
from app.cabinet.orm import (
    LkAuditEventRow,
    LkOrganizationRow,
    LkUserRow,
    LkUserWbTokenRow,
)
from app.infra.models import Base
from app.platform.integrations import wb_credentials
from app.platform.integrations.orm import MarketplaceAccountRow


SELLER_ID = "64f8d3e5-3d25-4b5c-9f23-0fd3937af451"


@pytest.fixture
def binding_db():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    now = datetime.now(timezone.utc)
    with factory() as session:
        session.add_all(
            [
                LkOrganizationRow(organization_id=2, slug="two", name="Two"),
                LkUserRow(
                    user_id="owner-two",
                    organization_id=2,
                    email="owner-two@example.com",
                    password_hash="unused",
                    full_name="Owner Two",
                    permission_profile="admin",
                    is_active=True,
                ),
                LkUserWbTokenRow(
                    token_id=1,
                    user_id="owner-two",
                    organization_id=2,
                    wb_token="original-secret",
                    token_masked="***",
                ),
                MarketplaceAccountRow(
                    marketplace_account_id=2,
                    organization_id=2,
                    marketplace="wb",
                    external_account_id="legacy-org-2",
                    status="connected",
                    created_at=now,
                    updated_at=now,
                ),
            ]
        )
        session.commit()
    return engine, factory


def test_fetch_wb_seller_id_accepts_only_verified_uuid() -> None:
    client = SimpleNamespace(
        request=lambda request: SimpleNamespace(
            ok=True,
            statusCode=200,
            data={"sid": SELLER_ID},
        )
    )

    assert wb_credentials.fetch_wb_seller_id("secret", client=client) == SELLER_ID

    client.request = lambda request: SimpleNamespace(
        ok=True,
        statusCode=200,
        data={"sid": "not-a-wb-seller-id"},
    )
    with pytest.raises(wb_credentials.WbCredentialBindingError):
        wb_credentials.fetch_wb_seller_id("secret", client=client)


def test_bind_wb_credential_replaces_only_expected_legacy_id(
    binding_db, monkeypatch
) -> None:
    _engine, factory = binding_db
    monkeypatch.setattr(wb_credentials, "get_session_factory", lambda: factory)
    monkeypatch.setattr(wb_credentials, "fetch_wb_seller_id", lambda token: SELLER_ID)

    result = wb_credentials.bind_wb_credential(
        2,
        marketplace_account_id=2,
        token_id=1,
        expected_external_account_id="legacy-org-2",
    )

    assert result == {
        "marketplaceAccountId": 2,
        "credentialRef": "lk_user_wb_tokens:1",
        "sellerIdentityVerified": True,
    }
    with factory() as session:
        account = session.get(MarketplaceAccountRow, 2)
        assert account is not None
        assert account.external_account_id == SELLER_ID
        assert account.credential_ref == "lk_user_wb_tokens:1"
        audit = session.query(LkAuditEventRow).one()
        assert audit.action == "integration.wb_credential.bind"
        assert audit.details == {"sellerIdentityVerified": True, "tokenId": 1}


def test_bind_wb_credential_rejects_token_rotation_during_probe(
    binding_db, monkeypatch
) -> None:
    _engine, factory = binding_db
    monkeypatch.setattr(wb_credentials, "get_session_factory", lambda: factory)

    def rotate_token(_token: str) -> str:
        with factory() as session:
            row = session.get(LkUserWbTokenRow, 1)
            assert row is not None
            row.wb_token = "rotated-secret"
            session.commit()
        return SELLER_ID

    monkeypatch.setattr(wb_credentials, "fetch_wb_seller_id", rotate_token)

    with pytest.raises(wb_credentials.WbCredentialBindingError):
        wb_credentials.bind_wb_credential(
            2,
            marketplace_account_id=2,
            token_id=1,
            expected_external_account_id="legacy-org-2",
        )

    with factory() as session:
        account = session.get(MarketplaceAccountRow, 2)
        assert account is not None
        assert account.external_account_id == "legacy-org-2"
        assert account.credential_ref is None


def test_bind_wb_credential_never_replaces_a_different_verified_seller(
    binding_db, monkeypatch
) -> None:
    _engine, factory = binding_db
    other_seller_id = "5e2e5772-c32a-44ec-897a-485497d67585"
    with factory() as session:
        account = session.get(MarketplaceAccountRow, 2)
        assert account is not None
        account.external_account_id = other_seller_id
        session.commit()
    monkeypatch.setattr(wb_credentials, "get_session_factory", lambda: factory)
    monkeypatch.setattr(wb_credentials, "fetch_wb_seller_id", lambda token: SELLER_ID)

    with pytest.raises(wb_credentials.WbCredentialBindingError):
        wb_credentials.bind_wb_credential(
            2,
            marketplace_account_id=2,
            token_id=1,
            expected_external_account_id=other_seller_id,
        )


def test_token_rotation_and_delete_invalidate_credential_binding(
    binding_db, monkeypatch
) -> None:
    engine, factory = binding_db
    monkeypatch.setattr(store, "get_engine", lambda: engine)
    monkeypatch.setattr(store, "get_session_factory", lambda: factory)
    monkeypatch.setattr(store, "_append_audit_event", lambda **_kwargs: None)

    class TokenView(SimpleNamespace):
        def model_dump(self, **_kwargs):
            return vars(self)

    monkeypatch.setattr(store, "UserWbTokenView", TokenView)

    with factory() as session:
        account = session.get(MarketplaceAccountRow, 2)
        assert account is not None
        account.credential_ref = "lk_user_wb_tokens:1"
        session.commit()

    store.upsert_user_wb_token(
        user_id="owner-two",
        organization_id=2,
        actor_user_id="owner-two",
        wb_token="rotated-secret",
    )
    with factory() as session:
        assert session.get(MarketplaceAccountRow, 2).credential_ref is None
        session.get(MarketplaceAccountRow, 2).credential_ref = "lk_user_wb_tokens:1"
        session.commit()

    store.upsert_user_wb_token(
        user_id="owner-two",
        organization_id=2,
        actor_user_id="owner-two",
        wb_token="rotated-secret",
    )
    with factory() as session:
        assert session.get(MarketplaceAccountRow, 2).credential_ref == (
            "lk_user_wb_tokens:1"
        )

    store.delete_user_wb_token(
        user_id="owner-two",
        organization_id=2,
        actor_user_id="owner-two",
    )
    with factory() as session:
        assert session.get(MarketplaceAccountRow, 2).credential_ref is None
        assert session.get(LkUserWbTokenRow, 1) is None
