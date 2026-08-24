from __future__ import annotations

from fastapi import APIRouter, Request

from app.contracts.envelopes import DataEnvelope
from app.control_plane.auth import actor_from_request
from app.control_plane.store import assert_permission_or_audit, record_audit_event
from app.repricer_sprint_c import (
    NightScheduleRequest,
    NightScheduleView,
    StrategyAssignmentRequest,
    StrategyAssignmentView,
    StrategyCatalogItem,
    StrategyDryRunRecord,
    StrategyDryRunReport,
    StrategyDryRunRequest,
    StrategyVersionCreateRequest,
    StrategyVersionView,
    create_strategy_assignment,
    create_strategy_version,
    get_night_schedule,
    list_strategy_assignments,
    list_strategy_catalog,
    list_strategy_dry_runs,
    list_strategy_versions,
    run_strategy_dry_run,
    update_night_schedule,
)
from app.wb_api.client import RateLimitedWbApiClient, build_wb_client


router = APIRouter(tags=["wb-repricer-sprint-c"])


@router.get("/api/v1/wb-repricer/strategies/catalog", response_model=DataEnvelope[list[StrategyCatalogItem]])
def get_strategy_catalog(request: Request) -> DataEnvelope[list[StrategyCatalogItem]]:
    actor = actor_from_request(request)
    assert_permission_or_audit(
        actor=actor,
        permission="settings:read",
        action="strategy.catalog.get",
        object_type="repricer_strategy",
        object_id="catalog",
        reason="actor cannot read strategy catalog",
    )
    return DataEnvelope(data=list_strategy_catalog())


@router.get("/api/v1/wb-repricer/strategies/{strategyId}/versions", response_model=DataEnvelope[list[StrategyVersionView]])
def get_strategy_versions(request: Request, strategyId: str) -> DataEnvelope[list[StrategyVersionView]]:
    actor = actor_from_request(request)
    assert_permission_or_audit(
        actor=actor,
        permission="settings:read",
        action="strategy.version.list",
        object_type="repricer_strategy",
        object_id=strategyId,
        reason="actor cannot read strategy versions",
    )
    return DataEnvelope(data=list_strategy_versions(strategyId))


@router.post("/api/v1/wb-repricer/strategies/{strategyId}/versions", response_model=DataEnvelope[StrategyVersionView])
def post_strategy_version(
    request: Request,
    strategyId: str,
    payload: StrategyVersionCreateRequest,
) -> DataEnvelope[StrategyVersionView]:
    actor = actor_from_request(request)
    assert_permission_or_audit(
        actor=actor,
        permission="settings:write",
        action="strategy.version.create",
        object_type="repricer_strategy",
        object_id=strategyId,
        reason="actor cannot create strategy versions",
    )
    before = list_strategy_versions(strategyId)[-1]
    created = create_strategy_version(
        strategy_id_raw=strategyId,
        actor_id=actor.actor_id,
        actor_role=actor.role,
        request=payload,
    )
    record_audit_event(
        actor=actor,
        action="strategy.version.create",
        object_type="repricer_strategy",
        object_id=f"{strategyId}:v{created.version}",
        before_state=before.model_dump(mode="json"),
        after_state=created.model_dump(mode="json"),
        reason=payload.reason,
        approval_ref=payload.approvalRef,
        evidence_refs=["SPRINT_C", "STRATEGY_VERSIONING", created.formulaVersion],
    )
    return DataEnvelope(data=created)


@router.post("/api/v1/wb-repricer/strategies/{strategyId}/dry-run", response_model=DataEnvelope[StrategyDryRunReport])
def post_strategy_dry_run(
    request: Request,
    strategyId: str,
    payload: StrategyDryRunRequest,
) -> DataEnvelope[StrategyDryRunReport]:
    actor = actor_from_request(request)
    assert_permission_or_audit(
        actor=actor,
        permission="price:send",
        action="strategy.dry_run.run",
        object_type="repricer_strategy",
        object_id=strategyId,
        reason="actor cannot run strategy dry-run",
    )
    client = RateLimitedWbApiClient(inner=build_wb_client(payload.scenario))
    report = run_strategy_dry_run(strategy_id_raw=strategyId, client=client, request=payload)
    record_audit_event(
        actor=actor,
        action="strategy.dry_run.run",
        object_type="repricer_strategy_run",
        object_id=report.runId,
        before_state=None,
        after_state=report.model_dump(mode="json"),
        reason="typed strategy dry-run",
        approval_ref=None,
        evidence_refs=["SPRINT_C", strategyId, report.formulaVersion],
    )
    return DataEnvelope(data=report)


@router.get("/api/v1/wb-repricer/strategies/{strategyId}/dry-runs", response_model=DataEnvelope[list[StrategyDryRunRecord]])
def get_strategy_dry_runs(request: Request, strategyId: str) -> DataEnvelope[list[StrategyDryRunRecord]]:
    actor = actor_from_request(request)
    assert_permission_or_audit(
        actor=actor,
        permission="settings:read",
        action="strategy.dry_run.list",
        object_type="repricer_strategy",
        object_id=strategyId,
        reason="actor cannot read strategy dry-run history",
    )
    return DataEnvelope(data=list_strategy_dry_runs(strategyId))


@router.get("/api/v1/wb-repricer/night-schedule", response_model=DataEnvelope[NightScheduleView])
def get_night_schedule_endpoint(request: Request) -> DataEnvelope[NightScheduleView]:
    actor = actor_from_request(request)
    assert_permission_or_audit(
        actor=actor,
        permission="settings:read",
        action="strategy.night_schedule.get",
        object_type="repricer_strategy",
        object_id="night_price_mode",
        reason="actor cannot read night schedule",
    )
    return DataEnvelope(data=get_night_schedule())


@router.put("/api/v1/wb-repricer/night-schedule", response_model=DataEnvelope[StrategyVersionView])
def put_night_schedule(request: Request, payload: NightScheduleRequest) -> DataEnvelope[StrategyVersionView]:
    actor = actor_from_request(request)
    assert_permission_or_audit(
        actor=actor,
        permission="settings:write",
        action="strategy.night_schedule.update",
        object_type="repricer_strategy",
        object_id="night_price_mode",
        reason="actor cannot update night schedule",
    )
    before = get_night_schedule()
    created = update_night_schedule(
        actor_id=actor.actor_id,
        actor_role=actor.role,
        request=payload,
    )
    record_audit_event(
        actor=actor,
        action="strategy.night_schedule.update",
        object_type="repricer_strategy",
        object_id=f"night_price_mode:v{created.version}",
        before_state=before.model_dump(mode="json"),
        after_state=created.model_dump(mode="json"),
        reason=payload.reason,
        approval_ref=payload.approvalRef,
        evidence_refs=["SPRINT_C", "NIGHT_MODE", "SCHEDULE_AUDIT"],
    )
    return DataEnvelope(data=created)


@router.get("/api/v1/wb-repricer/strategy-assignments", response_model=DataEnvelope[list[StrategyAssignmentView]])
def get_strategy_assignments(request: Request) -> DataEnvelope[list[StrategyAssignmentView]]:
    actor = actor_from_request(request)
    assert_permission_or_audit(
        actor=actor,
        permission="settings:read",
        action="strategy.assignment.list",
        object_type="repricer_strategy_assignment",
        object_id="*",
        reason="actor cannot read strategy assignments",
    )
    return DataEnvelope(data=list_strategy_assignments())


@router.post("/api/v1/wb-repricer/strategy-assignments", response_model=DataEnvelope[StrategyAssignmentView])
def post_strategy_assignment(
    request: Request,
    payload: StrategyAssignmentRequest,
) -> DataEnvelope[StrategyAssignmentView]:
    actor = actor_from_request(request)
    assert_permission_or_audit(
        actor=actor,
        permission="settings:write",
        action="strategy.assignment.create",
        object_type="repricer_strategy_assignment",
        object_id=f"{payload.scope}:{payload.targetId}",
        reason="actor cannot assign strategy scope",
    )
    assignment = create_strategy_assignment(payload)
    action = "strategy.assignment.create"
    evidence_refs = ["SPRINT_C", payload.strategyId, "SKU_SCOPE_POLICY_V1"]
    if assignment.status == "blocked":
        action = "blocked.strategy.assignment.create"
    record_audit_event(
        actor=actor,
        action=action,
        object_type="repricer_strategy_assignment",
        object_id=assignment.assignmentId,
        before_state=None,
        after_state=assignment.model_dump(mode="json"),
        reason="create strategy assignment",
        approval_ref=None,
        evidence_refs=evidence_refs,
    )
    return DataEnvelope(data=assignment)
