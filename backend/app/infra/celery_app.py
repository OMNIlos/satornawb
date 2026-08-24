from __future__ import annotations

from datetime import timedelta
from functools import lru_cache

from celery import Celery

from app.config import get_settings

REPRICER_SCHEDULER_POLL_MINUTES = 5
REPORT_SNAPSHOTS_REFRESH_MINUTES = 180


@lru_cache(maxsize=1)
def get_celery_app() -> Celery:
    settings = get_settings()
    app = Celery(
        "vella_backend",
        broker=settings.celery_broker_url,
        backend=settings.celery_result_backend,
    )
    beat_schedule = {}
    if settings.repricer_wb_sync_enabled:
        beat_schedule["repricer-sync-wb-data"] = {
            "task": "repricer.sync_wb_data_all_orgs",
            "schedule": timedelta(minutes=REPRICER_SCHEDULER_POLL_MINUTES),
            "kwargs": {"scenario": "complete"},
            "options": {"queue": "vella.default"},
        }
        beat_schedule["repricer-sync-wb-nightly"] = {
            "task": "repricer.sync_wb_nightly_all_orgs",
            "schedule": timedelta(minutes=REPRICER_SCHEDULER_POLL_MINUTES),
            "kwargs": {"scenario": "complete"},
            "options": {"queue": "vella.default"},
        }
        beat_schedule["repricer-materialize-report-snapshots"] = {
            "task": "repricer.materialize_report_snapshots_all_orgs",
            "schedule": timedelta(minutes=REPORT_SNAPSHOTS_REFRESH_MINUTES),
            "options": {"queue": "vella.default"},
        }
    if settings.repricer_scheduler_enabled:
        beat_schedule["repricer-execute-assigned"] = {
            "task": "repricer.execute_assigned_all_orgs",
            "schedule": timedelta(minutes=REPRICER_SCHEDULER_POLL_MINUTES),
            "kwargs": {"scenario": "complete"},
            "options": {"queue": "vella.default"},
        }
        if getattr(settings, "avito_repricer_worker_enabled", True):
            beat_schedule["repricer-execute-avito"] = {
                "task": "repricer.execute_avito_all_orgs",
                "schedule": timedelta(minutes=REPRICER_SCHEDULER_POLL_MINUTES),
                "kwargs": {"scenario": "complete"},
                "options": {"queue": "vella.default"},
            }
        beat_schedule["reviews-sync-feedbacks"] = {
            "task": "reviews.sync_all_orgs",
            "schedule": timedelta(minutes=REPRICER_SCHEDULER_POLL_MINUTES),
            "kwargs": {"scenario": "complete"},
            "options": {"queue": "vella.default"},
        }
    if getattr(settings, "avito_returns_sync_enabled", True):
        beat_schedule["avito-sync-returns"] = {
            "task": "avito.sync_returns_all_orgs",
            "schedule": timedelta(minutes=1),
            "kwargs": {"scenario": "complete"},
            "options": {"queue": "vella.default"},
        }
    app.conf.update(
        task_default_queue="vella.default",
        task_serializer="json",
        result_serializer="json",
        accept_content=["json"],
        enable_utc=True,
        timezone="UTC",
        beat_schedule=beat_schedule,
    )
    return app


celery_app = get_celery_app()

import app.repricer_tasks  # noqa: F401, E402
import app.review_tasks  # noqa: F401, E402
import app.avito.returns_tasks  # noqa: F401, E402


@celery_app.task(name="infra.ping")
def infra_ping() -> str:
    """No-op task used to validate worker/beat wiring in Sprint A."""
    return "pong"
