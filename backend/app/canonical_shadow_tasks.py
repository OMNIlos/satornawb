from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import date, datetime, timedelta, timezone
from typing import Any

from redis.exceptions import RedisError
from app.config import get_settings
from app.infra.celery_app import celery_app
from app.infra.db import get_session_factory
from app.infra.redis_client import get_redis_client
from app.platform.advertising.raw_backfill import backfill_raw_advertising
from app.platform.funnel.raw_backfill import backfill_raw_funnel
from app.platform.integrations.wb_credentials import (
    WbCredentialBindingError,
    resolve_bound_wb_credential,
)
from app.platform.period import MOSCOW, Period

_LOCK_SECONDS = 6 * 60 * 60
_RETRY_SECONDS = 30 * 60
# ponytail: renew this lock only if a measured collection approaches six hours.
_SAFE_RESULT_FIELDS = (
    "state",
    "syncRunId",
    "snapshotChecksum",
    "factCount",
    "campaignCount",
    "spendDocumentCount",
    "expectedRequests",
    "completedRequests",
    "failureCodes",
    "errorCode",
)

CanonicalShadowCredentialError = WbCredentialBindingError


def _last_closed_day() -> date:
    return datetime.now(timezone.utc).astimezone(MOSCOW).date() - timedelta(days=1)


def _closed_period(value: str | None) -> Period:
    business_date = date.fromisoformat(value) if value else _last_closed_day()
    if business_date > _last_closed_day():
        raise ValueError("business date is not closed")
    return Period(business_date, business_date)


def _bound_wb_credential(organization_id: int) -> tuple[int, str, str]:
    with get_session_factory()() as session:
        return resolve_bound_wb_credential(session, organization_id)


def _safe_result(operation: Callable[[], Mapping[str, Any]]) -> dict[str, Any]:
    try:
        result = operation()
        if not isinstance(result, Mapping):
            return {"state": "failed", "errorCode": "invalid_result"}
        safe = {key: result[key] for key in _SAFE_RESULT_FIELDS if key in result}
    except Exception:
        return {"state": "failed", "errorCode": "unexpected_failure"}
    if safe.get("state") not in {"ready", "partial", "failed"}:
        return {"state": "failed", "errorCode": "invalid_result"}
    return safe


@celery_app.task(name="canonical.collect_shadow_for_org", bind=True, max_retries=2)
def collect_canonical_shadow_for_org(
    self, organization_id: int, business_date: str | None = None
) -> dict[str, Any]:
    settings = get_settings()
    if not settings.canonical_shadow_collection_enabled:
        return {
            "organizationId": organization_id,
            "skipped": True,
            "reason": "canonical_shadow_disabled",
        }
    if organization_id < 1 or organization_id not in set(
        settings.canonical_shadow_collection_organization_ids
    ):
        return {
            "organizationId": organization_id,
            "skipped": True,
            "reason": "organization_not_enabled",
        }
    try:
        period = _closed_period(business_date)
    except (TypeError, ValueError):
        return {
            "organizationId": organization_id,
            "state": "failed",
            "errorCode": "invalid_business_date",
        }

    try:
        lock = get_redis_client().lock(
            f"satorna:canonical-shadow:{organization_id}",
            timeout=_LOCK_SECONDS,
            blocking=False,
        )
        acquired = lock.acquire(blocking=False)
    except Exception:
        return self.retry(
            exc=RuntimeError("canonical_shadow_lock_unavailable"),
            countdown=_RETRY_SECONDS,
        )
    if not acquired:
        return {
            "organizationId": organization_id,
            "businessDate": period.date_from.isoformat(),
            "skipped": True,
            "reason": "collection_in_progress",
        }

    try:
        try:
            account_id, credential_ref, token = _bound_wb_credential(organization_id)
        except CanonicalShadowCredentialError as exc:
            result = {
                "organizationId": organization_id,
                "businessDate": period.date_from.isoformat(),
                "state": "failed",
                "errorCode": exc.error_code,
            }
        except Exception:
            result = {
                "organizationId": organization_id,
                "businessDate": period.date_from.isoformat(),
                "state": "failed",
                "errorCode": "credential_lookup_failed",
            }
        else:
            credentials = {
                "marketplace_account_id": account_id,
                "credential_ref": credential_ref,
                "wb_token": token,
            }
            advertising = _safe_result(
                lambda: backfill_raw_advertising(organization_id, period, **credentials)
            )
            funnel = _safe_result(
                lambda: backfill_raw_funnel(organization_id, period, **credentials)
            )
            states = {advertising.get("state"), funnel.get("state")}
            state = (
                "failed"
                if "failed" in states
                else "partial"
                if "partial" in states
                else "ready"
            )
            result = {
                "organizationId": organization_id,
                "businessDate": period.date_from.isoformat(),
                "state": state,
                "advertising": advertising,
                "funnel": funnel,
            }
    finally:
        try:
            lock.release()
        except RedisError:
            pass
    if result["state"] != "ready":
        return self.retry(
            exc=RuntimeError("canonical_shadow_incomplete"),
            countdown=_RETRY_SECONDS,
        )
    return result


@celery_app.task(name="canonical.collect_shadow_all_orgs")
def collect_canonical_shadow_all_orgs(
    business_date: str | None = None,
) -> dict[str, Any]:
    settings = get_settings()
    if not settings.canonical_shadow_collection_enabled:
        return {
            "processedOrganizations": 0,
            "skipped": True,
            "reason": "canonical_shadow_disabled",
        }
    try:
        resolved_date = _closed_period(business_date).date_from.isoformat()
    except (TypeError, ValueError):
        return {
            "processedOrganizations": 0,
            "state": "failed",
            "errorCode": "invalid_business_date",
        }

    tasks = []
    for organization_id in sorted(
        {
            value
            for value in settings.canonical_shadow_collection_organization_ids
            if value > 0
        }
    ):
        result = collect_canonical_shadow_for_org.apply_async(
            args=(organization_id, resolved_date), queue="vella.canonical-shadow"
        )
        tasks.append({"organizationId": organization_id, "taskId": result.id})
    return {
        "businessDate": resolved_date,
        "processedOrganizations": len(tasks),
        "tasks": tasks,
    }
