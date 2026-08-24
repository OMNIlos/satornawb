from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from app.contracts.envelopes import UtcDateTime


SettingsStatus = Literal["draft", "pending", "active", "archived"]
SyncJobStatus = Literal["queued", "running", "success", "failed"]
SyncJobType = Literal["source_poll", "reports_rollup", "price_probe"]


class RepricerTypedSettings(BaseModel):
    strategyMode: Literal["manual", "strategy_4599", "strategy_4600"] = "manual"
    applyScope: Literal["sku", "category", "brand"] = "sku"
    maxPriceStepPctPerHour: float = Field(ge=0, lt=19)
    minMarginKopecks: int = Field(ge=0)
    targetMarginPct: float = Field(ge=0, le=100)
    pminGuardEnabled: bool = True
    pmaxGuardEnabled: bool = True
    nightModeEnabled: bool = False
    nightWindowStartHour: int = Field(ge=0, le=23)
    nightWindowEndHour: int = Field(ge=0, le=23)
    sppFallbackMode: Literal["block", "manual_only", "last_known_with_warning"] = "block"

    @model_validator(mode="after")
    def validate_night_window(self) -> RepricerTypedSettings:
        if self.nightModeEnabled and self.nightWindowStartHour == self.nightWindowEndHour:
            raise ValueError("night mode requires a non-zero window")
        return self


class SettingsVersionCreateRequest(BaseModel):
    settings: RepricerTypedSettings
    status: SettingsStatus = "draft"
    reason: str | None = None
    approvalRef: str | None = None


class SettingsVersionView(BaseModel):
    version: int = Field(ge=1)
    status: SettingsStatus
    settings: RepricerTypedSettings
    createdById: str = Field(min_length=1)
    createdByRole: str = Field(min_length=1)
    reason: str | None = None
    approvalRef: str | None = None
    createdAt: UtcDateTime


class SettingsVersionDiffField(BaseModel):
    field: str = Field(min_length=1)
    before: Any = None
    after: Any = None


class SettingsVersionDiffResponse(BaseModel):
    fromVersion: int = Field(ge=1)
    toVersion: int = Field(ge=1)
    changedFields: list[SettingsVersionDiffField]


class ActivateSettingsRequest(BaseModel):
    reason: str | None = None
    approvalRef: str | None = None


class AuditEventView(BaseModel):
    eventId: int = Field(ge=1)
    actorId: str = Field(min_length=1)
    actorRole: str = Field(min_length=1)
    action: str = Field(min_length=1)
    objectType: str = Field(min_length=1)
    objectId: str = Field(min_length=1)
    beforeState: dict[str, Any] | None = None
    afterState: dict[str, Any] | None = None
    reason: str | None = None
    approvalRef: str | None = None
    evidenceRefs: list[str]
    createdAt: UtcDateTime


class SyncJobCreateRequest(BaseModel):
    jobType: SyncJobType
    source: str = Field(min_length=1)
    period: str = Field(min_length=1)
    linkedRegistryRowId: int | None = Field(default=None, ge=1)
    staleAfterMinutes: int = Field(default=60, ge=1, le=24 * 60)


class SyncJobView(BaseModel):
    jobId: int = Field(ge=1)
    jobType: SyncJobType
    source: str = Field(min_length=1)
    period: str = Field(min_length=1)
    status: SyncJobStatus
    lastSuccessAt: UtcDateTime | None = None
    lastErrorCode: str | None = None
    lastErrorMessage: str | None = None
    retryCount: int = Field(ge=0)
    nextRunAt: UtcDateTime | None = None
    staleAfter: UtcDateTime | None = None
    linkedRegistryRowId: int | None = None
    createdAt: UtcDateTime
    updatedAt: UtcDateTime


class NoopTickResponse(BaseModel):
    processedJobIds: list[int]
    totalProcessed: int = Field(ge=0)

