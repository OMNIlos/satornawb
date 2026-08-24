from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request

from app.contracts.envelopes import DataEnvelope, PaginatedEnvelope
from app.control_plane.auth import actor_from_request
from app.control_plane.schemas import (
    ActivateSettingsRequest,
    AuditEventView,
    NoopTickResponse,
    SettingsVersionCreateRequest,
    SettingsVersionDiffResponse,
    SettingsVersionView,
    SyncJobCreateRequest,
    SyncJobView,
)
from app.control_plane.store import (
    assert_permission_or_audit,
    create_settings_version,
    create_sync_job,
    list_audit_events,
    list_settings_versions,
    list_sync_jobs,
    noop_tick,
    record_audit_event,
    run_sync_job_noop,
    settings_diff,
    activate_settings_version,
)
from app.config import get_settings
from app.wb22_apply import PriceApplyRequest, PriceApplyResponse, run_price_apply
from app.wb_api.client import RateLimitedWbApiClient, build_wb_client


router = APIRouter(tags=["control-plane-a4"])


@router.post("/api/v1/settings/versions", response_model=DataEnvelope[SettingsVersionView])
def create_settings_version_endpoint(request: Request, payload: SettingsVersionCreateRequest) -> DataEnvelope[SettingsVersionView]:
    actor = actor_from_request(request)
    assert_permission_or_audit(
        actor=actor,
        permission="settings:write",
        action="settings.version.create",
        object_type="settings_version",
        object_id="new",
        reason="actor cannot create settings versions",
    )
    created = create_settings_version(actor, payload)
    return DataEnvelope(data=created)


@router.get("/api/v1/settings/versions", response_model=DataEnvelope[list[SettingsVersionView]])
def list_settings_versions_endpoint(request: Request, status: str | None = None) -> DataEnvelope[list[SettingsVersionView]]:
    actor = actor_from_request(request)
    assert_permission_or_audit(
        actor=actor,
        permission="settings:read",
        action="settings.version.list",
        object_type="settings_version",
        object_id="*",
        reason="actor cannot read settings versions",
    )
    return DataEnvelope(data=list_settings_versions(status=status))


@router.get("/api/v1/settings/versions/{version}", response_model=DataEnvelope[SettingsVersionView])
def get_settings_version_endpoint(request: Request, version: int) -> DataEnvelope[SettingsVersionView]:
    actor = actor_from_request(request)
    assert_permission_or_audit(
        actor=actor,
        permission="settings:read",
        action="settings.version.get",
        object_type="settings_version",
        object_id=str(version),
        reason="actor cannot read settings version",
    )
    rows = [row for row in list_settings_versions() if row.version == version]
    if not rows:
        raise HTTPException(status_code=404, detail="SETTINGS_VERSION_NOT_FOUND")
    return DataEnvelope(data=rows[0])


@router.get("/api/v1/settings/versions/{toVersion}/diff", response_model=DataEnvelope[SettingsVersionDiffResponse])
def get_settings_diff_endpoint(request: Request, toVersion: int, fromVersion: int = Query(ge=1)) -> DataEnvelope[SettingsVersionDiffResponse]:
    actor = actor_from_request(request)
    assert_permission_or_audit(
        actor=actor,
        permission="settings:read",
        action="settings.version.diff",
        object_type="settings_version",
        object_id=f"{fromVersion}->{toVersion}",
        reason="actor cannot view settings diff",
    )
    return DataEnvelope(data=settings_diff(fromVersion, toVersion))


@router.post("/api/v1/settings/versions/{version}/activate", response_model=DataEnvelope[SettingsVersionView])
def activate_settings_version_endpoint(
    request: Request,
    version: int,
    payload: ActivateSettingsRequest,
) -> DataEnvelope[SettingsVersionView]:
    actor = actor_from_request(request)
    assert_permission_or_audit(
        actor=actor,
        permission="settings:activate",
        action="settings.version.activate",
        object_type="settings_version",
        object_id=str(version),
        reason="actor cannot activate settings versions",
    )
    return DataEnvelope(data=activate_settings_version(actor, version, payload))


@router.get("/api/v1/audit/events", response_model=PaginatedEnvelope[AuditEventView])
def list_audit_events_endpoint(
    request: Request,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    actionPrefix: str | None = None,
    objectType: str | None = None,
) -> PaginatedEnvelope[AuditEventView]:
    actor = actor_from_request(request)
    assert_permission_or_audit(
        actor=actor,
        permission="audit:read",
        action="audit.event.list",
        object_type="audit_event",
        object_id="*",
        reason="actor cannot read audit events",
    )
    items, total = list_audit_events(action_prefix=actionPrefix, object_type=objectType, limit=limit, offset=offset)
    return PaginatedEnvelope(items=items, total=total, limit=limit, offset=offset)


@router.post("/api/v1/sync-jobs", response_model=DataEnvelope[SyncJobView])
def create_sync_job_endpoint(request: Request, payload: SyncJobCreateRequest) -> DataEnvelope[SyncJobView]:
    actor = actor_from_request(request)
    assert_permission_or_audit(
        actor=actor,
        permission="sync:write",
        action="sync.job.create",
        object_type="sync_job",
        object_id="new",
        reason="actor cannot create sync jobs",
    )
    return DataEnvelope(data=create_sync_job(actor, payload))


@router.get("/api/v1/sync-jobs", response_model=PaginatedEnvelope[SyncJobView])
def list_sync_jobs_endpoint(
    request: Request,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    status: str | None = None,
) -> PaginatedEnvelope[SyncJobView]:
    actor = actor_from_request(request)
    assert_permission_or_audit(
        actor=actor,
        permission="sync:read",
        action="sync.job.list",
        object_type="sync_job",
        object_id="*",
        reason="actor cannot read sync jobs",
    )
    items, total = list_sync_jobs(status=status, limit=limit, offset=offset)
    return PaginatedEnvelope(items=items, total=total, limit=limit, offset=offset)


@router.post("/api/v1/sync-jobs/{jobId}/run-noop", response_model=DataEnvelope[SyncJobView])
def run_sync_job_noop_endpoint(request: Request, jobId: int) -> DataEnvelope[SyncJobView]:
    actor = actor_from_request(request)
    assert_permission_or_audit(
        actor=actor,
        permission="sync:run",
        action="sync.job.run_noop",
        object_type="sync_job",
        object_id=str(jobId),
        reason="actor cannot run sync jobs",
    )
    return DataEnvelope(data=run_sync_job_noop(actor, jobId))


@router.post("/api/v1/sync-jobs/noop-tick", response_model=DataEnvelope[NoopTickResponse])
def run_noop_tick_endpoint(request: Request, limit: int = Query(default=10, ge=1, le=100)) -> DataEnvelope[NoopTickResponse]:
    actor = actor_from_request(request)
    assert_permission_or_audit(
        actor=actor,
        permission="sync:run",
        action="sync.noop_tick",
        object_type="sync_job",
        object_id="queued",
        reason="actor cannot run noop scheduler tick",
    )
    return DataEnvelope(data=noop_tick(actor, limit=limit))


@router.post("/api/v1/wb-repricer/actions/price-apply-placeholder", response_model=DataEnvelope[dict[str, str]])
def blocked_price_apply_placeholder(request: Request, articleId: str) -> DataEnvelope[dict[str, str]]:
    actor = actor_from_request(request)
    assert_permission_or_audit(
        actor=actor,
        permission="price:send",
        action="price.apply.attempt",
        object_type="price_apply",
        object_id=articleId,
        reason="actor cannot send prices",
    )
    record_audit_event(
        actor=actor,
        action="blocked.price.apply",
        object_type="price_apply",
        object_id=articleId,
        before_state=None,
        after_state=None,
        reason="legacy placeholder endpoint is blocked; use /api/v1/wb-repricer/actions/price-apply",
        approval_ref=None,
        evidence_refs=["price_apply_placeholder_deprecated"],
    )
    raise HTTPException(status_code=409, detail="PRICE_APPLY_BLOCKED_BY_SPRINT_A_GATES")


@router.post("/api/v1/wb-repricer/actions/price-apply", response_model=DataEnvelope[PriceApplyResponse])
def run_price_apply_action(
    request: Request,
    payload: PriceApplyRequest,
) -> DataEnvelope[PriceApplyResponse]:
    actor = actor_from_request(request)
    assert_permission_or_audit(
        actor=actor,
        permission="price:send",
        action="price.apply.run",
        object_type="price_apply",
        object_id="batch",
        reason="actor cannot send prices",
    )
    if not payload.dryRun:
        record_audit_event(
            actor=actor,
            action="blocked.price.apply.direct_commit",
            object_type="price_apply",
            object_id="batch",
            before_state={"rowsCount": len(payload.rows), "dryRun": payload.dryRun},
            after_state=None,
            reason="direct apply endpoint is blocked; use draft -> approve -> /api/v1/wb-repricer/drafts/{draftId}/apply",
            approval_ref=None,
            evidence_refs=["sprint_b_guardrail"],
        )
        raise HTTPException(status_code=409, detail="DIRECT_APPLY_BLOCKED_USE_DRAFT_WORKFLOW")
    settings = get_settings()
    try:
        client = RateLimitedWbApiClient(inner=build_wb_client(payload.scenario))
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=f"WB_ADAPTER_NOT_READY:{exc}") from exc
    result = run_price_apply(
        client=client,
        payload=payload,
        real_apply_enabled=settings.real_price_apply_enabled,
        local_apply_enabled=False,
    )
    record_audit_event(
        actor=actor,
        action="price.apply.run",
        object_type="price_apply",
        object_id=str(result.wbUploadId or "pending"),
        before_state={"rowsCount": len(payload.rows), "dryRun": payload.dryRun},
        after_state=result.model_dump(mode="json"),
        reason="wb price apply attempt executed",
        approval_ref=None,
        evidence_refs=["WB-22"],
    )
    return DataEnvelope(data=result)
