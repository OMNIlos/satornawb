from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Generic, TypeVar

from pydantic import AfterValidator, AwareDatetime, BaseModel, Field, model_validator
from typing_extensions import Annotated


def _ensure_utc(dt: datetime) -> datetime:
    if dt.utcoffset() != timezone.utc.utcoffset(dt):
        raise ValueError("datetime must be UTC")
    return dt


UtcDateTime = Annotated[AwareDatetime, AfterValidator(_ensure_utc)]
MoneyKopecks = Annotated[int, Field(ge=0)]

T = TypeVar("T")


class ErrorEnvelopeItem(BaseModel):
    code: str = Field(min_length=1)
    message: str = Field(min_length=1)
    details: dict[str, Any] = Field(default_factory=dict)


class ErrorEnvelope(BaseModel):
    error: ErrorEnvelopeItem
    timestamp: UtcDateTime = Field(default_factory=lambda: datetime.now(timezone.utc))


class DataEnvelope(BaseModel, Generic[T]):
    data: T
    timestamp: UtcDateTime = Field(default_factory=lambda: datetime.now(timezone.utc))


class PaginatedEnvelope(BaseModel, Generic[T]):
    items: list[T]
    total: int = Field(ge=0)
    limit: int = Field(ge=1, le=500)
    offset: int = Field(ge=0)
    timestamp: UtcDateTime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @model_validator(mode="after")
    def validate_page_window(self) -> PaginatedEnvelope[T]:
        if len(self.items) > self.limit:
            raise ValueError("items count cannot exceed limit")
        if self.offset > self.total and self.total != 0:
            raise ValueError("offset cannot exceed total")
        return self

