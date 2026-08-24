from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from app.cabinet.store import get_organization_wb_token_secret
from app.control_plane.auth import ActorContext
from app.infra.celery_app import celery_app
from app.reviews.schemas import ReviewFeedbackSyncRequest
from app.reviews.service import get_sync_settings, get_sync_status, sync_feedbacks


def _scheduler_actor(organization_id: int) -> ActorContext:
    return ActorContext(
        actor_id="reviews-scheduler",
        user_id="reviews-scheduler",
        organization_id=organization_id,
        permission_profile="admin",
        permissions=frozenset({"reviews:read", "reviews:write"}),
        email=None,
        session_id=None,
    )


def sync_reviews_for_org(*, organization_id: int, scenario: str = "complete", force: bool = False) -> dict[str, Any]:
    status = get_sync_status(organization_id, "reviews-scheduler")
    now = datetime.now(timezone.utc)
    if not status.enabled:
        return {"organizationId": organization_id, "skipped": True, "reason": "review_sync_disabled"}
    if not force and status.nextRunAt is not None and status.nextRunAt > now:
        return {
            "organizationId": organization_id,
            "skipped": True,
            "reason": "review_sync_interval_not_due",
            "nextRunAt": status.nextRunAt.isoformat(),
        }
    settings = get_sync_settings(organization_id, "reviews-scheduler")
    wb_token = (get_organization_wb_token_secret(organization_id) or "").strip()
    if not wb_token:
        return {"organizationId": organization_id, "skipped": True, "reason": "no_cabinet_wb_token"}
    actor = _scheduler_actor(organization_id)
    date_from = int((now - timedelta(days=settings.lookbackDays)).timestamp())
    response = sync_feedbacks(
        actor,
        ReviewFeedbackSyncRequest(
            scenario=scenario,
            isAnswered=False if settings.unansweredOnly else None,
            take=settings.take,
            skip=0,
            order="dateDesc",
            dateFrom=date_from,
        ),
        wb_token=wb_token,
    )
    return {
        "organizationId": organization_id,
        "skipped": False,
        "syncedCount": response.syncedCount,
        "sourceStatus": response.sourceStatus,
        "nextSkip": response.nextSkip,
    }


def sync_reviews_all_orgs(*, scenario: str = "complete") -> dict[str, Any]:
    result = sync_reviews_for_org(organization_id=1, scenario=scenario)
    return {"processedOrganizations": 1, "results": [result]}


@celery_app.task(name="reviews.sync_for_org", max_retries=0)
def sync_reviews_for_org_task(organization_id: int, scenario: str = "complete", force: bool = False) -> dict[str, Any]:
    return sync_reviews_for_org(organization_id=organization_id, scenario=scenario, force=force)


@celery_app.task(name="reviews.sync_all_orgs", max_retries=0)
def sync_reviews_all_orgs_task(scenario: str = "complete") -> dict[str, Any]:
    return sync_reviews_all_orgs(scenario=scenario)
