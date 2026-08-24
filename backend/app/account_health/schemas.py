from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator


SourceStatus = Literal["ready", "partial", "blocked", "unknown"]
AuthState = Literal["token_ok", "missing_access", "scope_missing", "token_expired"]


class CapabilityHealth(BaseModel):
    capability: Literal["wb_marketplace_api", "wb_ads_api", "wb_price_apply_api", "wb_reviews_api"]
    status: SourceStatus
    missingScopes: list[str] = Field(default_factory=list)
    blockerIds: list[str] = Field(default_factory=list)
    evidenceRef: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_blocked_or_unknown(self) -> CapabilityHealth:
        if self.status in {"blocked", "unknown"} and not self.blockerIds and not self.missingScopes:
            raise ValueError("Blocked or unknown capability must reference blocker IDs or missing scopes")
        return self


class WbAccountHealthResponse(BaseModel):
    accountId: str = Field(min_length=1)
    sourceStatus: SourceStatus
    authState: AuthState
    checkedAt: datetime
    capabilities: list[CapabilityHealth]
    blockerIds: list[str] = Field(default_factory=list)
    nextActions: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_blocked_or_unknown(self) -> WbAccountHealthResponse:
        if self.sourceStatus in {"blocked", "unknown"}:
            has_capability_issue = any(cap.status in {"blocked", "unknown"} for cap in self.capabilities)
            if not self.blockerIds and not has_capability_issue:
                raise ValueError("Blocked or unknown account health must reference blockers or capability issues")
        return self
