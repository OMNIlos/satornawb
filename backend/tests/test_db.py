from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.infra.db import set_tenant_context


def test_tenant_context_is_set_once_per_organization_and_transaction() -> None:
    calls: list[tuple[str, str, int]] = []
    engine = create_engine("sqlite://")
    with engine.connect() as connection:
        connection.connection.create_function(
            "set_config",
            3,
            lambda key, value, local: calls.append((key, value, local)) or value,
        )
    engine.dialect.name = "postgresql"

    with Session(engine) as session:
        set_tenant_context(session, 1)
        set_tenant_context(session, 1)
        set_tenant_context(session, 2)
        session.commit()
        set_tenant_context(session, 2)

    assert calls == [
        ("app.organization_id", "1", 1),
        ("app.organization_id", "2", 1),
        ("app.organization_id", "2", 1),
    ]
