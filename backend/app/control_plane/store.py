from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.control_plane.auth import ActorContext, has_permission
from app.control_plane.orm import AuditEventRow, SettingsVersionRow, SyncJobRow
from app.control_plane.schemas import (
    ActivateSettingsRequest,
    AuditEventView,
    NoopTickResponse,
    RepricerTypedSettings,
    SettingsVersionCreateRequest,
    SettingsVersionDiffField,
    SettingsVersionDiffResponse,
    SettingsVersionView,
    SyncJobCreateRequest,
    SyncJobView,
)
from app.infra.db import get_engine, get_session_factory


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _settings_diff(before: RepricerTypedSettings | None, after: RepricerTypedSettings) -> list[SettingsVersionDiffField]:
    before_data = before.model_dump() if before is not None else {}
    after_data = after.model_dump()
    keys = sorted(set(before_data.keys()) | set(after_data.keys()))
    diff: list[SettingsVersionDiffField] = []
    for key in keys:
        left = before_data.get(key)
        right = after_data.get(key)
        if left != right:
            diff.append(SettingsVersionDiffField(field=key, before=left, after=right))
    return diff


@dataclass
class _MemoryControlState:
    settings_versions: dict[int, SettingsVersionView] = field(default_factory=dict)
    audit_events: list[AuditEventView] = field(default_factory=list)
    sync_jobs: dict[int, SyncJobView] = field(default_factory=dict)
    next_audit_id: int = 1
    next_sync_job_id: int = 1


_MEMORY = _MemoryControlState()


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


def _to_settings_view(row: SettingsVersionRow) -> SettingsVersionView:
    return SettingsVersionView(
        version=row.version,
        status=row.status,  # type: ignore[arg-type]
        settings=RepricerTypedSettings(**row.settings_payload),
        createdById=row.created_by_id,
        createdByRole=row.created_by_role,
        reason=row.reason,
        approvalRef=row.approval_ref,
        createdAt=_as_utc(row.created_at),
    )


def _to_audit_view(row: AuditEventRow) -> AuditEventView:
    return AuditEventView(
        eventId=row.event_id,
        actorId=row.actor_id,
        actorRole=row.actor_role,
        action=row.action,
        objectType=row.object_type,
        objectId=row.object_id,
        beforeState=row.before_state,
        afterState=row.after_state,
        reason=row.reason,
        approvalRef=row.approval_ref,
        evidenceRefs=row.evidence_refs,
        createdAt=_as_utc(row.created_at),
    )


def _to_sync_job_view(row: SyncJobRow) -> SyncJobView:
    return SyncJobView(
        jobId=row.job_id,
        jobType=row.job_type,  # type: ignore[arg-type]
        source=row.source,
        period=row.period,
        status=row.status,  # type: ignore[arg-type]
        lastSuccessAt=_as_utc(row.last_success_at) if row.last_success_at else None,
        lastErrorCode=row.last_error_code,
        lastErrorMessage=row.last_error_message,
        retryCount=row.retry_count,
        nextRunAt=_as_utc(row.next_run_at) if row.next_run_at else None,
        staleAfter=_as_utc(row.stale_after) if row.stale_after else None,
        linkedRegistryRowId=row.linked_registry_row_id,
        createdAt=_as_utc(row.created_at),
        updatedAt=_as_utc(row.updated_at),
    )


def record_audit_event(
    actor: ActorContext,
    action: str,
    object_type: str,
    object_id: str,
    before_state: dict[str, Any] | None,
    after_state: dict[str, Any] | None,
    reason: str | None,
    approval_ref: str | None,
    evidence_refs: list[str],
) -> AuditEventView:
    def _db(session: Session) -> AuditEventView:
        row = AuditEventRow(
            actor_id=actor.actor_id,
            actor_role=actor.role,
            action=action,
            object_type=object_type,
            object_id=object_id,
            before_state=before_state,
            after_state=after_state,
            reason=reason,
            approval_ref=approval_ref,
            evidence_refs=evidence_refs,
        )
        session.add(row)
        session.commit()
        session.refresh(row)
        return _to_audit_view(row)

    result = _run_db(_db)
    if result is not None:
        return result

    event = AuditEventView(
        eventId=_MEMORY.next_audit_id,
        actorId=actor.actor_id,
        actorRole=actor.role,
        action=action,
        objectType=object_type,
        objectId=object_id,
        beforeState=before_state,
        afterState=after_state,
        reason=reason,
        approvalRef=approval_ref,
        evidenceRefs=evidence_refs,
        createdAt=_utc_now(),
    )
    _MEMORY.next_audit_id += 1
    _MEMORY.audit_events.append(event)
    return event


def assert_permission_or_audit(
    actor: ActorContext,
    permission: str,
    action: str,
    object_type: str,
    object_id: str,
    reason: str,
) -> None:
    if has_permission(actor, permission):
        return
    record_audit_event(
        actor=actor,
        action=f"blocked.{action}",
        object_type=object_type,
        object_id=object_id,
        before_state=None,
        after_state=None,
        reason=reason,
        approval_ref=None,
        evidence_refs=["permission_matrix"],
    )
    raise HTTPException(status_code=403, detail=f"NO_ACCESS:{permission}")


def create_settings_version(actor: ActorContext, request: SettingsVersionCreateRequest) -> SettingsVersionView:
    def _db(session: Session) -> SettingsVersionView:
        current_max = session.scalar(select(func.max(SettingsVersionRow.version))) or 0
        previous_row = session.get(SettingsVersionRow, current_max) if current_max else None
        row = SettingsVersionRow(
            version=current_max + 1,
            status=request.status,
            settings_payload=request.settings.model_dump(),
            created_by_id=actor.actor_id,
            created_by_role=actor.role,
            reason=request.reason,
            approval_ref=request.approvalRef,
        )
        session.add(row)
        session.flush()
        record = _to_settings_view(row)
        record_audit_event(
            actor=actor,
            action="settings.version.create",
            object_type="settings_version",
            object_id=str(record.version),
            before_state=previous_row.settings_payload if previous_row else None,
            after_state=row.settings_payload,
            reason=request.reason,
            approval_ref=request.approvalRef,
            evidence_refs=["cp_settings_versions"],
        )
        session.commit()
        return record

    result = _run_db(_db)
    if result is not None:
        return result

    previous = _MEMORY.settings_versions[max(_MEMORY.settings_versions)] if _MEMORY.settings_versions else None
    version = (max(_MEMORY.settings_versions) if _MEMORY.settings_versions else 0) + 1
    record = SettingsVersionView(
        version=version,
        status=request.status,
        settings=request.settings,
        createdById=actor.actor_id,
        createdByRole=actor.role,
        reason=request.reason,
        approvalRef=request.approvalRef,
        createdAt=_utc_now(),
    )
    _MEMORY.settings_versions[version] = record
    record_audit_event(
        actor=actor,
        action="settings.version.create",
        object_type="settings_version",
        object_id=str(version),
        before_state=previous.settings.model_dump() if previous else None,
        after_state=request.settings.model_dump(),
        reason=request.reason,
        approval_ref=request.approvalRef,
        evidence_refs=["memory_fallback"],
    )
    return record


def list_settings_versions(status: str | None = None) -> list[SettingsVersionView]:
    def _db(session: Session) -> list[SettingsVersionView]:
        stmt = select(SettingsVersionRow).order_by(SettingsVersionRow.version)
        if status:
            stmt = stmt.where(SettingsVersionRow.status == status)
        rows = session.scalars(stmt).all()
        return [_to_settings_view(row) for row in rows]

    result = _run_db(_db)
    if result is not None:
        return result

    rows = sorted(_MEMORY.settings_versions.values(), key=lambda row: row.version)
    if status:
        rows = [row for row in rows if row.status == status]
    return rows


def _get_settings_version(version: int) -> SettingsVersionView | None:
    rows = list_settings_versions()
    for row in rows:
        if row.version == version:
            return row
    return None


def activate_settings_version(actor: ActorContext, version: int, request: ActivateSettingsRequest) -> SettingsVersionView:
    target = _get_settings_version(version)
    if target is None:
        raise HTTPException(status_code=404, detail="SETTINGS_VERSION_NOT_FOUND")

    def _db(session: Session) -> SettingsVersionView:
        current_active = session.scalars(select(SettingsVersionRow).where(SettingsVersionRow.status == "active")).all()
        for row in current_active:
            row.status = "archived"
        target_row = session.get(SettingsVersionRow, version)
        if target_row is None:
            raise HTTPException(status_code=404, detail="SETTINGS_VERSION_NOT_FOUND")
        before = target_row.settings_payload
        target_row.status = "active"
        target_row.reason = request.reason or target_row.reason
        target_row.approval_ref = request.approvalRef or target_row.approval_ref
        session.flush()
        record_audit_event(
            actor=actor,
            action="settings.version.activate",
            object_type="settings_version",
            object_id=str(version),
            before_state=before,
            after_state=target_row.settings_payload,
            reason=request.reason,
            approval_ref=request.approvalRef,
            evidence_refs=["cp_settings_versions"],
        )
        session.commit()
        return _to_settings_view(target_row)

    result = _run_db(_db)
    if result is not None:
        return result

    for row in _MEMORY.settings_versions.values():
        if row.status == "active":
            _MEMORY.settings_versions[row.version] = row.model_copy(update={"status": "archived"})
    activated = target.model_copy(update={"status": "active", "reason": request.reason or target.reason, "approvalRef": request.approvalRef or target.approvalRef})
    _MEMORY.settings_versions[version] = activated
    record_audit_event(
        actor=actor,
        action="settings.version.activate",
        object_type="settings_version",
        object_id=str(version),
        before_state=target.settings.model_dump(),
        after_state=activated.settings.model_dump(),
        reason=request.reason,
        approval_ref=request.approvalRef,
        evidence_refs=["memory_fallback"],
    )
    return activated


def settings_diff(from_version: int, to_version: int) -> SettingsVersionDiffResponse:
    left = _get_settings_version(from_version)
    right = _get_settings_version(to_version)
    if left is None or right is None:
        raise HTTPException(status_code=404, detail="SETTINGS_VERSION_NOT_FOUND")
    return SettingsVersionDiffResponse(
        fromVersion=from_version,
        toVersion=to_version,
        changedFields=_settings_diff(left.settings, right.settings),
    )


def list_audit_events(action_prefix: str | None = None, object_type: str | None = None, limit: int = 100, offset: int = 0) -> tuple[list[AuditEventView], int]:
    def _db(session: Session) -> tuple[list[AuditEventView], int]:
        stmt = select(AuditEventRow).order_by(AuditEventRow.event_id.desc())
        if action_prefix:
            stmt = stmt.where(AuditEventRow.action.like(f"{action_prefix}%"))
        if object_type:
            stmt = stmt.where(AuditEventRow.object_type == object_type)
        rows = session.scalars(stmt).all()
        items = [_to_audit_view(row) for row in rows]
        total = len(items)
        return items[offset : offset + limit], total

    result = _run_db(_db)
    if result is not None:
        return result

    rows = sorted(_MEMORY.audit_events, key=lambda item: item.eventId, reverse=True)
    if action_prefix:
        rows = [row for row in rows if row.action.startswith(action_prefix)]
    if object_type:
        rows = [row for row in rows if row.objectType == object_type]
    total = len(rows)
    return rows[offset : offset + limit], total


def create_sync_job(actor: ActorContext, request: SyncJobCreateRequest) -> SyncJobView:
    now = _utc_now()
    stale_after = now + timedelta(minutes=request.staleAfterMinutes)

    def _db(session: Session) -> SyncJobView:
        row = SyncJobRow(
            job_type=request.jobType,
            source=request.source,
            period=request.period,
            status="queued",
            last_success_at=None,
            last_error_code=None,
            last_error_message=None,
            retry_count=0,
            next_run_at=now,
            stale_after=stale_after,
            linked_registry_row_id=request.linkedRegistryRowId,
        )
        session.add(row)
        session.flush()
        view = _to_sync_job_view(row)
        record_audit_event(
            actor=actor,
            action="sync.job.create",
            object_type="sync_job",
            object_id=str(view.jobId),
            before_state=None,
            after_state=view.model_dump(mode="json"),
            reason="create queued sync job",
            approval_ref=None,
            evidence_refs=["cp_sync_jobs"],
        )
        session.commit()
        return view

    result = _run_db(_db)
    if result is not None:
        return result

    job = SyncJobView(
        jobId=_MEMORY.next_sync_job_id,
        jobType=request.jobType,
        source=request.source,
        period=request.period,
        status="queued",
        lastSuccessAt=None,
        lastErrorCode=None,
        lastErrorMessage=None,
        retryCount=0,
        nextRunAt=now,
        staleAfter=stale_after,
        linkedRegistryRowId=request.linkedRegistryRowId,
        createdAt=now,
        updatedAt=now,
    )
    _MEMORY.next_sync_job_id += 1
    _MEMORY.sync_jobs[job.jobId] = job
    record_audit_event(
        actor=actor,
        action="sync.job.create",
        object_type="sync_job",
        object_id=str(job.jobId),
        before_state=None,
        after_state=job.model_dump(mode="json"),
        reason="create queued sync job",
        approval_ref=None,
        evidence_refs=["memory_fallback"],
    )
    return job


def list_sync_jobs(status: str | None = None, limit: int = 100, offset: int = 0) -> tuple[list[SyncJobView], int]:
    def _db(session: Session) -> tuple[list[SyncJobView], int]:
        stmt = select(SyncJobRow).order_by(SyncJobRow.job_id.desc())
        if status:
            stmt = stmt.where(SyncJobRow.status == status)
        rows = session.scalars(stmt).all()
        items = [_to_sync_job_view(row) for row in rows]
        total = len(items)
        return items[offset : offset + limit], total

    result = _run_db(_db)
    if result is not None:
        return result

    rows = sorted(_MEMORY.sync_jobs.values(), key=lambda row: row.jobId, reverse=True)
    if status:
        rows = [row for row in rows if row.status == status]
    total = len(rows)
    return rows[offset : offset + limit], total


def run_sync_job_noop(actor: ActorContext, job_id: int, reason: str | None = None) -> SyncJobView:
    now = _utc_now()

    def _db(session: Session) -> SyncJobView:
        row = session.get(SyncJobRow, job_id)
        if row is None:
            raise HTTPException(status_code=404, detail="SYNC_JOB_NOT_FOUND")
        before = _to_sync_job_view(row).model_dump(mode="json")
        row.status = "running"
        row.updated_at = now
        session.flush()
        row.status = "success"
        row.last_success_at = now
        row.last_error_code = None
        row.last_error_message = None
        row.next_run_at = now + timedelta(minutes=60)
        row.updated_at = now
        session.flush()
        view = _to_sync_job_view(row)
        record_audit_event(
            actor=actor,
            action="sync.job.run_noop",
            object_type="sync_job",
            object_id=str(job_id),
            before_state=before,
            after_state=view.model_dump(mode="json"),
            reason=reason or "noop run",
            approval_ref=None,
            evidence_refs=["infra.ping"],
        )
        session.commit()
        return view

    result = _run_db(_db)
    if result is not None:
        return result

    row = _MEMORY.sync_jobs.get(job_id)
    if row is None:
        raise HTTPException(status_code=404, detail="SYNC_JOB_NOT_FOUND")
    before = row.model_dump(mode="json")
    updated = row.model_copy(
        update={
            "status": "success",
            "lastSuccessAt": now,
            "lastErrorCode": None,
            "lastErrorMessage": None,
            "nextRunAt": now + timedelta(minutes=60),
            "updatedAt": now,
        }
    )
    _MEMORY.sync_jobs[job_id] = updated
    record_audit_event(
        actor=actor,
        action="sync.job.run_noop",
        object_type="sync_job",
        object_id=str(job_id),
        before_state=before,
        after_state=updated.model_dump(mode="json"),
        reason=reason or "noop run",
        approval_ref=None,
        evidence_refs=["memory_fallback"],
    )
    return updated


def noop_tick(actor: ActorContext, limit: int = 10) -> NoopTickResponse:
    jobs, _ = list_sync_jobs(status="queued", limit=limit, offset=0)
    processed: list[int] = []
    for job in jobs:
        run_sync_job_noop(actor, job.jobId, reason="scheduler noop tick")
        processed.append(job.jobId)
    return NoopTickResponse(processedJobIds=processed, totalProcessed=len(processed))

