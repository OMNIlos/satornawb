from __future__ import annotations

from datetime import datetime, timezone
from time import sleep
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.wb_api.client import WbApiClient, WbApiRequest
from app.wb_api.price_units import kopecks_to_wb_price_rubles


ApplyState = Literal["blocked", "queued", "processing", "accepted", "requires_attention", "local_applied"]
SourceStatus = Literal["fresh", "partial", "blocked"]
ApplyMode = Literal["dry_run", "local_mock", "wb_api"]
StatusLabel = Literal["processing", "success", "canceled", "partial_errors", "all_failed", "unknown", "local_only"]


class PriceApplyRowRequest(BaseModel):
    nmId: int = Field(gt=0)
    priceKopecks: int = Field(gt=0)
    discountPct: int = Field(ge=0, le=99)
    sizeId: int | None = Field(default=None, gt=0)
    minPriceKopecks: int | None = Field(default=None, gt=0)


class PriceApplyRequest(BaseModel):
    scenario: str = "complete"
    dryRun: bool = False
    pollMaxAttempts: int = Field(default=6, ge=1, le=60)
    pollDelaySeconds: float = Field(default=0.0, ge=0.0, le=5.0)
    skipStatusPoll: bool = False
    rows: list[PriceApplyRowRequest] = Field(min_length=1)


class PriceApplyRowError(BaseModel):
    nmId: int | None = None
    sizeId: int | None = None
    wbStatus: int | None = None
    errorText: str


class PriceApplyResponse(BaseModel):
    sourceStatus: SourceStatus
    applyState: ApplyState
    blockerIds: list[str]
    wbUploadId: int | None = None
    wbStatus: int | None = None
    statusLabel: StatusLabel
    rowErrors: list[PriceApplyRowError] = Field(default_factory=list)
    pollAttempts: int = Field(ge=0)
    observedAt: datetime
    notes: list[str] = Field(default_factory=list)
    applyMode: ApplyMode = "wb_api"
    wbMutationSent: bool = False


def _status_label(value: int | None) -> Literal["processing", "success", "canceled", "partial_errors", "all_failed", "unknown"]:
    mapping = {
        1: "processing",
        3: "success",
        4: "canceled",
        5: "partial_errors",
        6: "all_failed",
    }
    return mapping.get(value, "unknown")


def _as_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _extract_data(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {}
    data = payload.get("data")
    if isinstance(data, dict):
        return data
    return payload


def _build_upload_payload(rows: list[PriceApplyRowRequest]) -> dict[str, Any]:
    payload_rows: list[dict[str, Any]] = []
    for row in rows:
        price_rubles = kopecks_to_wb_price_rubles(row.priceKopecks)
        if price_rubles is None:
            continue
        item: dict[str, Any] = {
            "nmID": row.nmId,
            "price": price_rubles,
            "discount": row.discountPct,
        }
        if row.sizeId is not None:
            item["sizeID"] = row.sizeId
        if row.minPriceKopecks is not None:
            min_price_rubles = kopecks_to_wb_price_rubles(row.minPriceKopecks)
            if min_price_rubles is not None:
                item["minPrice"] = min_price_rubles
        payload_rows.append(item)
    return {"data": payload_rows}


def run_price_apply(
    client: WbApiClient,
    payload: PriceApplyRequest,
    real_apply_enabled: bool,
    local_apply_enabled: bool = False,
) -> PriceApplyResponse:
    now = datetime.now(timezone.utc)
    if payload.dryRun:
        return PriceApplyResponse(
            sourceStatus="partial",
            applyState="queued",
            blockerIds=[],
            wbUploadId=None,
            wbStatus=None,
            statusLabel="unknown",
            rowErrors=[],
            pollAttempts=0,
            observedAt=now,
            notes=["Dry-run mode: WB upload is skipped"],
            applyMode="dry_run",
            wbMutationSent=False,
        )

    if not real_apply_enabled:
        if local_apply_enabled:
            return PriceApplyResponse(
                sourceStatus="partial",
                applyState="local_applied",
                blockerIds=[],
                wbUploadId=None,
                wbStatus=None,
                statusLabel="local_only",
                rowErrors=[],
                pollAttempts=0,
                observedAt=now,
                notes=["Local repricer test mode: WB upload is skipped and price is applied only to local runtime state"],
                applyMode="local_mock",
                wbMutationSent=False,
            )
        return PriceApplyResponse(
            sourceStatus="blocked",
            applyState="blocked",
            blockerIds=[],
            wbUploadId=None,
            wbStatus=None,
            statusLabel="unknown",
            rowErrors=[],
            pollAttempts=0,
            observedAt=now,
            notes=["Real price apply is disabled by VELLA_REAL_PRICE_APPLY_ENABLED=false"],
            applyMode="wb_api",
            wbMutationSent=False,
        )

    upload = client.request(
        WbApiRequest(
            method="POST",
            path="/api/v2/upload/task",
            jsonBody=_build_upload_payload(payload.rows),
        )
    )
    if not upload.ok:
        error_code = upload.error.code if upload.error else "unknown_error"
        blocker_ids = ["wb_rate_limited"] if upload.statusCode == 429 or error_code == "rate_limited" else [error_code]
        error_message = upload.error.message if upload.error and upload.error.message else ""
        notes = [f"Upload request failed: {error_code}" + (f" ({error_message})" if error_message else "")]
        if "wb_rate_limited" in blocker_ids:
            retry_after = upload.rateLimit.retryAfterSeconds if upload.rateLimit is not None else None
            notes = [
                "WB price upload rate limit reached"
                + (f"; retry after {retry_after}s" if retry_after is not None else "")
            ]
        return PriceApplyResponse(
            sourceStatus="blocked",
            applyState="blocked" if "wb_rate_limited" in blocker_ids else "requires_attention",
            blockerIds=blocker_ids,
            wbUploadId=None,
            wbStatus=upload.statusCode,
            statusLabel="unknown",
            rowErrors=[],
            pollAttempts=0,
            observedAt=now,
            notes=notes,
            applyMode="wb_api",
            wbMutationSent=False,
        )

    upload_data = _extract_data(upload.data)
    upload_id = _as_int(upload_data.get("id")) or _as_int(upload_data.get("uploadID"))
    if upload_id is None:
        return PriceApplyResponse(
            sourceStatus="blocked",
            applyState="requires_attention",
            blockerIds=[],
            wbUploadId=None,
            wbStatus=None,
            statusLabel="unknown",
            rowErrors=[],
            pollAttempts=0,
            observedAt=now,
            notes=["WB upload response does not contain upload id"],
            applyMode="wb_api",
            wbMutationSent=True,
        )

    if payload.skipStatusPoll:
        return PriceApplyResponse(
            sourceStatus="partial",
            applyState="processing",
            blockerIds=[],
            wbUploadId=upload_id,
            wbStatus=None,
            statusLabel="processing",
            rowErrors=[],
            pollAttempts=0,
            observedAt=datetime.now(timezone.utc),
            notes=["WB accepted the price upload; status check is deferred"],
            applyMode="wb_api",
            wbMutationSent=True,
        )

    attempts = 0
    last_status: int | None = None
    status_rate_limited = False
    for _ in range(payload.pollMaxAttempts):
        attempts += 1
        state = client.request(
            WbApiRequest(
                method="GET",
                path="/api/v2/history/tasks",
                query={"uploadID": upload_id},
            )
        )
        if not state.ok:
            status_rate_limited = state.statusCode == 429 or (state.error is not None and state.error.code == "rate_limited")
            break
        state_data = _extract_data(state.data)
        last_status = _as_int(state_data.get("status"))
        if last_status in {3, 4, 5, 6}:
            break
        if payload.pollDelaySeconds > 0:
            sleep(payload.pollDelaySeconds)

    row_errors: list[PriceApplyRowError] = []
    details_status_code: int | None = None
    if not status_rate_limited:
        details = client.request(
            WbApiRequest(
                method="GET",
                path="/api/v2/history/goods/task",
                query={"uploadID": upload_id, "limit": 100, "offset": 0},
            )
        )
        details_status_code = details.statusCode
        if not details.ok:
            status_rate_limited = details.statusCode == 429 or (details.error is not None and details.error.code == "rate_limited")
        else:
            details_data = _extract_data(details.data)
            history_rows = details_data.get("historyGoods") if isinstance(details_data.get("historyGoods"), list) else []
            for row in history_rows:
                if not isinstance(row, dict):
                    continue
                error_text = None
                errors = row.get("errors")
                if isinstance(errors, list) and errors:
                    error_text = str(errors[0])
                elif isinstance(row.get("errorText"), str) and row.get("errorText"):
                    error_text = row.get("errorText")
                if error_text:
                    row_errors.append(
                        PriceApplyRowError(
                            nmId=_as_int(row.get("nmID")),
                            sizeId=_as_int(row.get("sizeID")),
                            wbStatus=_as_int(row.get("status")),
                            errorText=error_text,
                        )
                    )

    if status_rate_limited:
        return PriceApplyResponse(
            sourceStatus="partial",
            applyState="processing",
            blockerIds=["wb_status_rate_limited"],
            wbUploadId=upload_id,
            wbStatus=429,
            statusLabel="processing",
            rowErrors=[],
            pollAttempts=attempts,
            observedAt=datetime.now(timezone.utc),
            notes=[
                "WB accepted the price upload, but status check is temporarily rate-limited; verify upload later",
                f"uploadID {upload_id}",
            ],
            applyMode="wb_api",
            wbMutationSent=True,
        )

    label = _status_label(last_status)
    if label == "success" and not row_errors:
        return PriceApplyResponse(
            sourceStatus="fresh",
            applyState="accepted",
            blockerIds=[],
            wbUploadId=upload_id,
            wbStatus=last_status,
            statusLabel=label,
            rowErrors=[],
            pollAttempts=attempts,
            observedAt=datetime.now(timezone.utc),
            notes=["WB upload lifecycle completed successfully"],
            applyMode="wb_api",
            wbMutationSent=True,
        )

    apply_state: ApplyState = "processing" if label == "processing" else "requires_attention"
    return PriceApplyResponse(
        sourceStatus="partial",
        applyState=apply_state,
        blockerIds=[],
        wbUploadId=upload_id,
        wbStatus=last_status,
        statusLabel=label,
        rowErrors=row_errors,
        pollAttempts=attempts,
        observedAt=datetime.now(timezone.utc),
        notes=["Upload finished with non-success status or row-level errors"],
        applyMode="wb_api",
        wbMutationSent=True,
    )
