from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any, Callable
from uuid import uuid4

from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.cash_flow.orm import OneCCashFlowJobRow
from app.infra.db import get_session_factory


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


def _as_job(row: OneCCashFlowJobRow) -> dict[str, Any]:
    return {
        "id": row.job_id,
        "organizationId": row.organization_id,
        "type": row.job_type,
        "periodFrom": row.period_from.isoformat(),
        "periodTo": row.period_to.isoformat(),
        "status": row.status,
        "attempts": row.attempts,
        "createdAt": _iso(row.created_at),
        "startedAt": _iso(row.started_at),
        "completedAt": _iso(row.completed_at),
        "error": row.error,
        "requestedBy": row.requested_by,
        "rows": row.rows_payload or [],
        "balances": row.balances_payload or {},
        "rawResult": row.raw_result,
    }


def _run_db(operation: Callable[[Session], Any], *, fallback_only: bool) -> tuple[bool, Any]:
    if fallback_only:
        return False, None
    try:
        session_factory = get_session_factory()
        with session_factory() as session:
            return True, operation(session)
    except SQLAlchemyError:
        # Never split a production queue across per-container JSON files.
        # JSON is used only when the caller explicitly selects the test/local fallback path.
        raise


def get_or_create_job(
    *,
    organization_id: int,
    period_from: date,
    period_to: date,
    requested_by: str | None,
    fallback_only: bool,
    fallback_get_or_create: Callable[[], dict[str, Any]],
) -> dict[str, Any]:
    def _db(session: Session) -> dict[str, Any]:
        row = session.scalar(
            select(OneCCashFlowJobRow).where(
                OneCCashFlowJobRow.organization_id == organization_id,
                OneCCashFlowJobRow.period_from == period_from,
                OneCCashFlowJobRow.period_to == period_to,
            )
        )
        if row is not None and row.status != "failed":
            return _as_job(row)
        now = _utc_now()
        if row is None:
            row = OneCCashFlowJobRow(
                job_id=f"cf_{uuid4().hex[:12]}",
                organization_id=organization_id,
                job_type="cash_flow",
                period_from=period_from,
                period_to=period_to,
                status="pending",
                attempts=0,
                requested_by=requested_by,
                rows_payload=[],
                balances_payload={},
                created_at=now,
                updated_at=now,
            )
            session.add(row)
        else:
            row.status = "pending"
            row.attempts = 0
            row.requested_by = requested_by
            row.started_at = None
            row.completed_at = None
            row.error = None
            row.rows_payload = []
            row.balances_payload = {}
            row.raw_result = None
            row.updated_at = now
        try:
            session.commit()
        except IntegrityError:
            session.rollback()
            row = session.scalar(
                select(OneCCashFlowJobRow).where(
                    OneCCashFlowJobRow.organization_id == organization_id,
                    OneCCashFlowJobRow.period_from == period_from,
                    OneCCashFlowJobRow.period_to == period_to,
                )
            )
            if row is None:
                raise
        session.refresh(row)
        return _as_job(row)

    used_db, job = _run_db(_db, fallback_only=fallback_only)
    return job if used_db else fallback_get_or_create()


def claim_jobs(
    *,
    limit: int,
    retry_after_seconds: int,
    fallback_only: bool,
    fallback_claim: Callable[[], list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    def _db(session: Session) -> list[dict[str, Any]]:
        now = _utc_now()
        stale_before = now - timedelta(seconds=retry_after_seconds)
        rows = list(
            session.scalars(
                select(OneCCashFlowJobRow)
                .where(
                    or_(
                        OneCCashFlowJobRow.status == "pending",
                        (OneCCashFlowJobRow.status == "processing")
                        & (or_(OneCCashFlowJobRow.started_at.is_(None), OneCCashFlowJobRow.started_at <= stale_before)),
                    )
                )
                .order_by(OneCCashFlowJobRow.created_at.asc())
                .with_for_update(skip_locked=True)
                .limit(limit)
            ).all()
        )
        for row in rows:
            row.status = "processing"
            row.started_at = now
            row.attempts += 1
            row.updated_at = now
        session.commit()
        return [_as_job(row) for row in rows]

    used_db, jobs = _run_db(_db, fallback_only=fallback_only)
    return jobs if used_db else fallback_claim()


def update_job_result(
    *,
    job_id: str,
    status: str,
    error: str | None,
    rows: list[dict[str, Any]],
    balances: dict[str, Any],
    raw_result: dict[str, Any],
    fallback_only: bool,
    fallback_update: Callable[[], dict[str, Any] | None],
) -> dict[str, Any] | None:
    def _db(session: Session) -> dict[str, Any] | None:
        row = session.scalar(select(OneCCashFlowJobRow).where(OneCCashFlowJobRow.job_id == job_id).with_for_update())
        if row is None:
            return None
        now = _utc_now()
        row.status = status
        row.completed_at = now
        row.error = error
        row.rows_payload = rows
        row.balances_payload = balances
        row.raw_result = raw_result
        row.updated_at = now
        session.commit()
        session.refresh(row)
        return _as_job(row)

    used_db, job = _run_db(_db, fallback_only=fallback_only)
    return job if used_db else fallback_update()
