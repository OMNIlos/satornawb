from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Query, Request

from app.account_health.schemas import CapabilityHealth, WbAccountHealthResponse
from app.account_health.store import persist_account_health_snapshot
from app.control_plane.auth import actor_from_request
from app.control_plane.store import record_audit_event


router = APIRouter(tags=["wb-account-health-a5"])


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _build_account_health_stub(scenario: str) -> WbAccountHealthResponse:
    if scenario == "missing_token":
        return WbAccountHealthResponse(
            accountId="wb-main",
            sourceStatus="unknown",
            authState="missing_access",
            checkedAt=_now_utc(),
            blockerIds=[],
            nextActions=["request_live_wb_token", "run_token_health_check"],
            capabilities=[
                CapabilityHealth(
                    capability="wb_marketplace_api",
                    status="unknown",
                    missingScopes=["marketplace:read"],
                    blockerIds=[],
                    evidenceRef="docs/open-questions-current.md#WB-23",
                ),
                CapabilityHealth(
                    capability="wb_ads_api",
                    status="unknown",
                    missingScopes=["ads:read"],
                    blockerIds=[],
                    evidenceRef="docs/open-questions-current.md#WB-02",
                ),
                CapabilityHealth(
                    capability="wb_price_apply_api",
                    status="blocked",
                    missingScopes=["prices:write"],
                    blockerIds=[],
                    evidenceRef="docs/open-questions-current.md#WB-22",
                ),
                CapabilityHealth(
                    capability="wb_reviews_api",
                    status="unknown",
                    missingScopes=["reviews:read", "reviews:write"],
                    blockerIds=[],
                    evidenceRef="docs/open-questions-current.md#WB-23",
                ),
            ],
        )

    if scenario == "missing_scope":
        return WbAccountHealthResponse(
            accountId="wb-main",
            sourceStatus="partial",
            authState="scope_missing",
            checkedAt=_now_utc(),
            blockerIds=[],
            nextActions=["request_missing_wb_scopes", "rerun_scope_probe"],
            capabilities=[
                CapabilityHealth(
                    capability="wb_marketplace_api",
                    status="ready",
                    missingScopes=[],
                    blockerIds=[],
                    evidenceRef="docs/open-questions-current.md#WB-23",
                ),
                CapabilityHealth(
                    capability="wb_ads_api",
                    status="blocked",
                    missingScopes=["ads:read"],
                    blockerIds=[],
                    evidenceRef="docs/open-questions-current.md#WB-02",
                ),
                CapabilityHealth(
                    capability="wb_price_apply_api",
                    status="blocked",
                    missingScopes=["prices:write"],
                    blockerIds=[],
                    evidenceRef="docs/open-questions-current.md#WB-22",
                ),
                CapabilityHealth(
                    capability="wb_reviews_api",
                    status="partial",
                    missingScopes=["reviews:write"],
                    blockerIds=[],
                    evidenceRef="docs/open-questions-current.md#WB-23",
                ),
            ],
        )

    if scenario == "expired":
        return WbAccountHealthResponse(
            accountId="wb-main",
            sourceStatus="blocked",
            authState="token_expired",
            checkedAt=_now_utc(),
            blockerIds=[],
            nextActions=["rotate_wb_token", "rerun_token_health_check"],
            capabilities=[
                CapabilityHealth(
                    capability="wb_marketplace_api",
                    status="blocked",
                    missingScopes=["token_expired"],
                    blockerIds=[],
                    evidenceRef="docs/open-questions-current.md#WB-23",
                ),
                CapabilityHealth(
                    capability="wb_ads_api",
                    status="blocked",
                    missingScopes=["token_expired"],
                    blockerIds=[],
                    evidenceRef="docs/open-questions-current.md#WB-02",
                ),
                CapabilityHealth(
                    capability="wb_price_apply_api",
                    status="blocked",
                    missingScopes=["token_expired"],
                    blockerIds=[],
                    evidenceRef="docs/open-questions-current.md#WB-22",
                ),
                CapabilityHealth(
                    capability="wb_reviews_api",
                    status="blocked",
                    missingScopes=["token_expired"],
                    blockerIds=[],
                    evidenceRef="docs/open-questions-current.md#WB-23",
                ),
            ],
        )

    return WbAccountHealthResponse(
        accountId="wb-main",
        sourceStatus="ready",
        authState="token_ok",
        checkedAt=_now_utc(),
        blockerIds=[],
        nextActions=["monitor_ads_sync_rate_limits", "monitor_wb_apply_and_freshness"],
        capabilities=[
            CapabilityHealth(
                capability="wb_marketplace_api",
                status="ready",
                missingScopes=[],
                blockerIds=[],
                evidenceRef="docs/open-questions-current.md#WB-23",
            ),
            CapabilityHealth(
                capability="wb_ads_api",
                status="ready",
                missingScopes=[],
                blockerIds=[],
                evidenceRef="docs/open-questions-current.md#WB-02",
            ),
            CapabilityHealth(
                capability="wb_price_apply_api",
                status="ready",
                missingScopes=[],
                blockerIds=[],
                evidenceRef="docs/open-questions-current.md#WB-22",
            ),
            CapabilityHealth(
                capability="wb_reviews_api",
                status="partial",
                missingScopes=[],
                blockerIds=[],
                evidenceRef="docs/open-questions-current.md#WB-23",
            ),
        ],
    )


@router.get("/api/v1/wb/account/health", response_model=WbAccountHealthResponse)
def get_wb_account_health(
    request: Request,
    scenario: Literal["ok", "missing_token", "missing_scope", "expired"] = Query(default="ok"),
) -> WbAccountHealthResponse:
    response = _build_account_health_stub(scenario)
    persist_account_health_snapshot(response, scenario)

    actor = actor_from_request(request)
    record_audit_event(
        actor=actor,
        action="wb.token_health.check",
        object_type="wb_account",
        object_id=response.accountId,
        before_state=None,
        after_state={
            "scenario": scenario,
            "sourceStatus": response.sourceStatus,
            "authState": response.authState,
            "blockerIds": response.blockerIds,
            "capabilities": [cap.model_dump(mode="json") for cap in response.capabilities],
        },
        reason="token health check executed",
        approval_ref=None,
        evidence_refs=["WB-02_CLOSED_2026-06-01", "WB-22", "WB-23", "wb_token_health_checks"],
    )
    return response
