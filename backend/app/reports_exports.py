from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field

from app.control_plane.auth import ActorContext
from app.control_plane.schemas import SyncJobCreateRequest
from app.control_plane.store import create_sync_job, run_sync_job_noop


ReportExportId = Literal["digest", "abc", "rnp", "pnl", "ads", "stock", "week-over-week"]
ReportExportStatus = Literal["queued", "success", "failed"]


class ReportExportJobView(BaseModel):
    exportId: str = Field(min_length=1)
    reportId: ReportExportId
    status: ReportExportStatus
    jobId: int = Field(ge=1)
    fileName: str | None = None
    rows: int = Field(ge=0)
    emptySourceNote: str | None = None
    requestedAt: datetime
    completedAt: datetime | None = None
    downloadUrl: str | None = None


@dataclass
class _ReportsExportState:
    jobs: dict[str, ReportExportJobView] = field(default_factory=dict)


_MEMORY = _ReportsExportState()


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _file_name(report_id: ReportExportId, file_stamp: str) -> str:
    return f"wb-{report_id}-{file_stamp}.xlsx"


def request_report_export(
    *,
    actor: ActorContext,
    report_id: ReportExportId,
    preset: str,
    from_raw: str | None,
    to_raw: str | None,
    row_count: int = 0,
) -> ReportExportJobView:
    now = _utc_now()
    sync_job = create_sync_job(
        actor,
        SyncJobCreateRequest(
            jobType="reports_rollup",
            source=f"wb-report-export:{report_id}",
            period=f"preset={preset};from={from_raw or ''};to={to_raw or ''}",
            staleAfterMinutes=60,
        ),
    )
    export = ReportExportJobView(
        exportId=f"exp_{uuid4().hex}",
        reportId=report_id,
        status="queued",
        jobId=sync_job.jobId,
        fileName=None,
        rows=row_count,
        emptySourceNote=None,
        requestedAt=now,
        completedAt=None,
        downloadUrl=None,
    )
    _MEMORY.jobs[export.exportId] = export
    return export


def materialize_report_export(
    *,
    actor: ActorContext,
    export_id: str,
    row_count: int = 0,
) -> ReportExportJobView:
    current = get_report_export_or_none(export_id)
    if current is None:
        raise KeyError(export_id)
    if current.status == "success":
        return current

    run_sync_job_noop(actor, current.jobId, reason=f"materialize report export {current.reportId}")
    file_stamp = _utc_now().strftime("%Y%m%dT%H%M%SZ")
    updated = current.model_copy(
        update={
            "status": "success",
            "fileName": _file_name(current.reportId, file_stamp),
            "rows": row_count,
            "completedAt": _utc_now(),
            "downloadUrl": f"/api/wb/reports/export/jobs/{current.exportId}/download",
        }
    )
    _MEMORY.jobs[export_id] = updated
    return updated


def get_report_export_or_none(export_id: str) -> ReportExportJobView | None:
    return _MEMORY.jobs.get(export_id)


def list_report_exports() -> list[ReportExportJobView]:
    return list(_MEMORY.jobs.values())
