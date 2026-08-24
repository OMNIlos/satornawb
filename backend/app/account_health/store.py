from __future__ import annotations

from sqlalchemy import delete
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.account_health.orm import (
    WbAccountCapabilityRow,
    WbAccountMissingScopeRow,
    WbAccountRow,
    WbTokenHealthCheckRow,
)
from app.account_health.schemas import WbAccountHealthResponse
from app.infra.db import get_engine, get_session_factory


def _run_db(db_fn):
    try:
        engine = get_engine()
        with engine.connect() as connection:
            connection.exec_driver_sql("SELECT 1")
        session_factory = get_session_factory()
        with session_factory() as session:
            return db_fn(session)
    except SQLAlchemyError:
        return None


def persist_account_health_snapshot(snapshot: WbAccountHealthResponse, scenario: str) -> None:
    def _db(session: Session) -> None:
        account = session.get(WbAccountRow, snapshot.accountId)
        if account is None:
            account = WbAccountRow(
                account_id=snapshot.accountId,
                source_status=snapshot.sourceStatus,
                auth_state=snapshot.authState,
                blocker_ids=snapshot.blockerIds,
                next_actions=snapshot.nextActions,
                last_checked_scenario=scenario,
                last_checked_at=snapshot.checkedAt,
            )
            session.add(account)
        else:
            account.source_status = snapshot.sourceStatus
            account.auth_state = snapshot.authState
            account.blocker_ids = snapshot.blockerIds
            account.next_actions = snapshot.nextActions
            account.last_checked_scenario = scenario
            account.last_checked_at = snapshot.checkedAt

        session.add(
            WbTokenHealthCheckRow(
                account_id=snapshot.accountId,
                scenario=scenario,
                source_status=snapshot.sourceStatus,
                auth_state=snapshot.authState,
                blocker_ids=snapshot.blockerIds,
                next_actions=snapshot.nextActions,
                capability_snapshot=[item.model_dump(mode="json") for item in snapshot.capabilities],
                checked_at=snapshot.checkedAt,
            )
        )

        session.execute(delete(WbAccountCapabilityRow).where(WbAccountCapabilityRow.account_id == snapshot.accountId))
        session.execute(delete(WbAccountMissingScopeRow).where(WbAccountMissingScopeRow.account_id == snapshot.accountId))

        for capability in snapshot.capabilities:
            session.add(
                WbAccountCapabilityRow(
                    account_id=snapshot.accountId,
                    capability=capability.capability,
                    status=capability.status,
                    missing_scopes=capability.missingScopes,
                    blocker_ids=capability.blockerIds,
                    evidence_ref=capability.evidenceRef,
                    observed_at=snapshot.checkedAt,
                )
            )
            for scope in capability.missingScopes:
                session.add(
                    WbAccountMissingScopeRow(
                        account_id=snapshot.accountId,
                        capability=capability.capability,
                        scope=scope,
                        observed_at=snapshot.checkedAt,
                    )
                )

        session.commit()

    _run_db(_db)
