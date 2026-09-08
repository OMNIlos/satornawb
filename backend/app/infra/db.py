from __future__ import annotations

from collections.abc import Generator
from functools import lru_cache

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings
from app.infra.models import Base


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    settings = get_settings()
    return create_engine(settings.database_url, pool_pre_ping=True)


@lru_cache(maxsize=1)
def get_session_factory() -> sessionmaker[Session]:
    return sessionmaker(
        bind=get_engine(),
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
    )


def get_db_session() -> Generator[Session, None, None]:
    session = get_session_factory()()
    try:
        yield session
    finally:
        session.close()


def set_tenant_context(session: Session, organization_id: int) -> None:
    if organization_id < 1:
        raise ValueError("organization_id must be positive")
    if session.get_bind().dialect.name == "postgresql":
        transaction = session.get_nested_transaction() or session.get_transaction()
        marker = (transaction, organization_id)
        if (
            transaction is not None
            and session.info.get("satorna_tenant_context") == marker
        ):
            return
        session.execute(
            text("SELECT set_config('app.organization_id', :organization_id, true)"),
            {"organization_id": str(organization_id)},
        )
        session.info["satorna_tenant_context"] = (
            session.get_nested_transaction() or session.get_transaction(),
            organization_id,
        )


def create_all_for_local_dev() -> None:
    """Bootstrap helper for local experiments outside Alembic."""
    Base.metadata.create_all(bind=get_engine())
