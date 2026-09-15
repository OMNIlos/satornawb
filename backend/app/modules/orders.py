from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TypeVar

AVITO_ORDER_STATUS_MAPPING_VERSION = "avito-order-status-v1"
WB_STATISTICS_STATUS_MAPPING_VERSION = "wb-statistics-status-v1"

AVITO_ORDER_STATUS_EVIDENCE_SOURCE = "avito-order-management"
WB_STATISTICS_STATUS_EVIDENCE_SOURCE = "wb-statistics-supplier-orders"


class OrderContractValidationError(ValueError):
    """A canonical order contract value is missing, malformed, or inconsistent."""


class Marketplace(StrEnum):
    WB = "wb"
    AVITO = "avito"


class MappingState(StrEnum):
    MAPPED = "mapped"
    UNMAPPED = "unmapped"
    AMBIGUOUS = "ambiguous"


class CanonicalOrderStatus(StrEnum):
    PENDING_CONFIRMATION = "pending_confirmation"
    ACCEPTED = "accepted"
    READY_FOR_FULFILLMENT = "ready_for_fulfillment"
    IN_DELIVERY = "in_delivery"
    DELIVERED = "delivered"
    CLOSED = "closed"
    CANCELLED = "cancelled"
    RETURNING = "returning"
    RETURNED = "returned"
    DISPUTED = "disputed"


_EnumT = TypeVar("_EnumT", bound=StrEnum)


def _enum_value(value: object, enum_type: type[_EnumT], field: str) -> _EnumT:
    try:
        return enum_type(value)
    except (TypeError, ValueError) as exc:
        allowed = ", ".join(item.value for item in enum_type)
        raise OrderContractValidationError(
            f"{field} must be one of: {allowed}"
        ) from exc


def _exact_text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise OrderContractValidationError(
            f"{field} must be a non-empty string without edge whitespace"
        )
    return value


def _optional_exact_text(value: object, field: str) -> str | None:
    if value is None:
        return None
    return _exact_text(value, field)


def _positive_int(value: object, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise OrderContractValidationError(f"{field} must be a positive integer")
    return value


def _occurrence_index(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise OrderContractValidationError(
            "occurrence_index must be a non-negative integer"
        )
    return value


def _strict_bool(value: object, field: str) -> bool:
    if not isinstance(value, bool):
        raise OrderContractValidationError(f"{field} must be a boolean")
    return value


@dataclass(frozen=True, slots=True)
class ExternalOrderIdentity:
    organization_id: int
    marketplace_account_id: int
    marketplace: Marketplace
    external_order_id: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "organization_id",
            _positive_int(self.organization_id, "organization_id"),
        )
        object.__setattr__(
            self,
            "marketplace_account_id",
            _positive_int(self.marketplace_account_id, "marketplace_account_id"),
        )
        object.__setattr__(
            self,
            "marketplace",
            _enum_value(self.marketplace, Marketplace, "marketplace"),
        )
        object.__setattr__(
            self,
            "external_order_id",
            _exact_text(self.external_order_id, "external_order_id"),
        )


@dataclass(frozen=True, slots=True)
class ExternalOrderItemIdentity:
    order_identity: ExternalOrderIdentity
    source_line_key: str
    external_item_id: str | None
    occurrence_index: int

    def __post_init__(self) -> None:
        if not isinstance(self.order_identity, ExternalOrderIdentity):
            raise OrderContractValidationError(
                "order_identity must be an ExternalOrderIdentity"
            )
        object.__setattr__(
            self,
            "source_line_key",
            _exact_text(self.source_line_key, "source_line_key"),
        )
        object.__setattr__(
            self,
            "external_item_id",
            _optional_exact_text(self.external_item_id, "external_item_id"),
        )
        object.__setattr__(
            self, "occurrence_index", _occurrence_index(self.occurrence_index)
        )


@dataclass(frozen=True, slots=True)
class MappedMarketplaceStatus:
    raw_status: str | None
    canonical_status: CanonicalOrderStatus | None
    mapping_state: MappingState
    mapping_version: str
    evidence_source: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "raw_status",
            _optional_exact_text(self.raw_status, "raw_status"),
        )
        canonical_status = (
            None
            if self.canonical_status is None
            else _enum_value(
                self.canonical_status,
                CanonicalOrderStatus,
                "canonical_status",
            )
        )
        mapping_state = _enum_value(self.mapping_state, MappingState, "mapping_state")
        if mapping_state is MappingState.MAPPED and canonical_status is None:
            raise OrderContractValidationError(
                "mapped status requires canonical_status"
            )
        if mapping_state is not MappingState.MAPPED and canonical_status is not None:
            raise OrderContractValidationError(
                "unmapped or ambiguous status cannot have canonical_status"
            )
        object.__setattr__(self, "canonical_status", canonical_status)
        object.__setattr__(self, "mapping_state", mapping_state)
        object.__setattr__(
            self,
            "mapping_version",
            _exact_text(self.mapping_version, "mapping_version"),
        )
        object.__setattr__(
            self,
            "evidence_source",
            _exact_text(self.evidence_source, "evidence_source"),
        )


_AVITO_STATUS_MAP = {
    "on_confirmation": CanonicalOrderStatus.PENDING_CONFIRMATION,
    "ready_to_ship": CanonicalOrderStatus.READY_FOR_FULFILLMENT,
    "in_transit": CanonicalOrderStatus.IN_DELIVERY,
    "delivered": CanonicalOrderStatus.DELIVERED,
    "closed": CanonicalOrderStatus.CLOSED,
    "canceled": CanonicalOrderStatus.CANCELLED,
    "on_return": CanonicalOrderStatus.RETURNING,
    "in_dispute": CanonicalOrderStatus.DISPUTED,
}


def map_avito_status(raw_status: str) -> MappedMarketplaceStatus:
    raw_status = _exact_text(raw_status, "raw_status")
    canonical_status = _AVITO_STATUS_MAP.get(raw_status)
    return MappedMarketplaceStatus(
        raw_status=raw_status,
        canonical_status=canonical_status,
        mapping_state=(
            MappingState.MAPPED
            if canonical_status is not None
            else MappingState.UNMAPPED
        ),
        mapping_version=AVITO_ORDER_STATUS_MAPPING_VERSION,
        evidence_source=AVITO_ORDER_STATUS_EVIDENCE_SOURCE,
    )


def map_wb_statistics_status(
    raw_status: str | None,
    is_cancelled: bool,
    cancel_evidence_present: bool,
) -> MappedMarketplaceStatus:
    raw_status = _optional_exact_text(raw_status, "raw_status")
    is_cancelled = _strict_bool(is_cancelled, "is_cancelled")
    cancel_evidence_present = _strict_bool(
        cancel_evidence_present, "cancel_evidence_present"
    )
    canonical_status = (
        CanonicalOrderStatus.CANCELLED
        if is_cancelled or cancel_evidence_present
        else None
    )
    return MappedMarketplaceStatus(
        raw_status=raw_status,
        canonical_status=canonical_status,
        mapping_state=(
            MappingState.MAPPED
            if canonical_status is not None
            else MappingState.UNMAPPED
        ),
        mapping_version=WB_STATISTICS_STATUS_MAPPING_VERSION,
        evidence_source=WB_STATISTICS_STATUS_EVIDENCE_SOURCE,
    )


def _length_prefixed(value: str) -> str:
    return f"{len(value)}:{value}"


def make_avito_source_line_key(
    external_order_id: str,
    external_item_id: str | None,
    occurrence_index: int,
    stable_order_line_id: str | None = None,
) -> str:
    external_order_id = _exact_text(external_order_id, "external_order_id")
    external_item_id = _optional_exact_text(external_item_id, "external_item_id")
    occurrence_index = _occurrence_index(occurrence_index)
    stable_order_line_id = _optional_exact_text(
        stable_order_line_id, "stable_order_line_id"
    )
    if stable_order_line_id is not None:
        return f"avito:line:{_length_prefixed(stable_order_line_id)}"
    item_part = (
        "none" if external_item_id is None else _length_prefixed(external_item_id)
    )
    return (
        f"avito:order:{_length_prefixed(external_order_id)}:"
        f"item:{item_part}:occurrence:{occurrence_index}"
    )


def make_wb_source_line_key(stable_unit_id: str | None) -> str:
    stable_unit_id = _optional_exact_text(stable_unit_id, "stable_unit_id")
    if stable_unit_id is None:
        raise OrderContractValidationError(
            "stable_unit_id is required; synthetic WB line identity is forbidden"
        )
    return f"wb:unit:{_length_prefixed(stable_unit_id)}"


__all__ = [
    "AVITO_ORDER_STATUS_MAPPING_VERSION",
    "WB_STATISTICS_STATUS_MAPPING_VERSION",
    "CanonicalOrderStatus",
    "ExternalOrderIdentity",
    "ExternalOrderItemIdentity",
    "MappedMarketplaceStatus",
    "MappingState",
    "Marketplace",
    "OrderContractValidationError",
    "make_avito_source_line_key",
    "make_wb_source_line_key",
    "map_avito_status",
    "map_wb_statistics_status",
]
