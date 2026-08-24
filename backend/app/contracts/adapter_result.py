from __future__ import annotations

from datetime import datetime, timezone
from typing import Generic, Literal, TypeVar

from pydantic import BaseModel, Field, model_validator

from app.contracts.envelopes import UtcDateTime


T = TypeVar("T")

AdapterStatus = Literal[
    "success",
    "partial",
    "empty",
    "stale",
    "not_authorized",
    "missing_capability",
    "blocked_by_guard",
    "rate_limited",
    "external_error",
    "unknown_error",
]

AdapterConfidence = Literal["high", "medium", "low", "unknown", "blocked"]


class AdapterWarning(BaseModel):
    code: str = Field(min_length=1)
    message: str = Field(min_length=1)


class AdapterError(BaseModel):
    code: str = Field(min_length=1)
    message: str = Field(min_length=1)
    retryable: bool
    retryAfterSeconds: int | None = Field(default=None, ge=0)
    rawRef: str | None = None


class AdapterFreshness(BaseModel):
    source: str = Field(min_length=1)
    fetchedAt: UtcDateTime = Field(default_factory=lambda: datetime.now(timezone.utc))
    staleAfter: UtcDateTime | None = None
    isStale: bool
    confidence: AdapterConfidence


class AdapterResult(BaseModel, Generic[T]):
    status: AdapterStatus
    data: T | None = None
    warnings: list[AdapterWarning] = Field(default_factory=list)
    error: AdapterError | None = None
    freshness: AdapterFreshness
    evidenceRefs: list[str] = Field(default_factory=list)
    nextValidActions: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_status_shape(self) -> AdapterResult[T]:
        error_statuses = {"rate_limited", "external_error", "unknown_error"}
        if self.status in error_statuses and self.error is None:
            raise ValueError("error details are required for error statuses")
        if self.status == "success" and self.data is None:
            raise ValueError("success status requires data")
        if self.status == "stale" and not self.freshness.isStale:
            raise ValueError("stale status requires freshness.isStale=true")
        return self

