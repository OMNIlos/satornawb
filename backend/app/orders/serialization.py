"""Versioned normalized storage payloads, not raw-provider or HTTP serializers."""

import hashlib
import json
from datetime import UTC, datetime

from app.modules.orders import (
    ExternalOrderIdentity,
    ExternalOrderItemIdentity,
    MappedMarketplaceStatus,
    OrderContractValidationError,
)
from app.orders.contracts import CatalogResolution, DeadlineEvidence, OrderReadRow
from app.orders.ingestion import ObservedOrderItem, OrderObservation

EVIDENCE_SCHEMA_VERSION = 1
READ_PAYLOAD_SCHEMA_VERSION = 1
OBSERVATION_CHECKSUM_VERSION = "orders-observation-v1"

# Explicit field lists keep future model additions out of an existing format.
_FIELDS = {
    ExternalOrderIdentity: (
        "organization_id",
        "marketplace_account_id",
        "marketplace",
        "external_order_id",
    ),
    ExternalOrderItemIdentity: (
        "order_identity",
        "source_line_key",
        "external_item_id",
        "occurrence_index",
    ),
    MappedMarketplaceStatus: (
        "raw_status",
        "canonical_status",
        "mapping_state",
        "mapping_version",
        "evidence_source",
    ),
    ObservedOrderItem: (
        "identity",
        "quantity",
        "stable_order_line_id",
        "stable_unit_id",
    ),
    OrderObservation: (
        "identity",
        "source_kind",
        "adapter_version",
        "source_revision",
        "effective_at",
        "observed_at",
        "status",
        "items",
        "wb_is_cancelled",
        "wb_cancel_evidence_present",
    ),
    CatalogResolution: (
        "state",
        "marketplace_product_id",
        "marketplace_offer_id",
        "catalog_sku_id",
        "evidence_version",
    ),
    DeadlineEvidence: (
        "kind",
        "source_at",
        "computed_at",
        "rule_id",
        "rule_version",
        "timezone",
        "evidence_source",
        "observed_at",
    ),
    OrderReadRow: (
        "observation",
        "item_identity",
        "row_version",
        "resolution",
        "readiness_blockers",
        "deadlines",
    ),
}


def _encode(value):
    if type(value) in _FIELDS:
        result = {name: _encode(getattr(value, name)) for name in _FIELDS[type(value)]}
        if type(value) is OrderObservation:
            result["items"].sort(key=lambda item: item["identity"]["source_line_key"])
        return result
    if value is None or type(value) in (bool, int):
        return value
    if isinstance(value, str):
        if "\x00" in value or any(0xD800 <= ord(char) <= 0xDFFF for char in value):
            raise OrderContractValidationError(
                "Text is not PostgreSQL JSONB compatible"
            )
        return str(value)
    if type(value) is datetime:
        if value.utcoffset() is None:
            raise OrderContractValidationError("Aware stored instant required")
        return value.astimezone(UTC).isoformat(timespec="microseconds")
    if type(value) is tuple:
        return [_encode(item) for item in value]
    raise OrderContractValidationError("Unsupported normalized payload type")


def serialize_observation(observation: OrderObservation) -> dict:
    if type(observation) is not OrderObservation:
        raise OrderContractValidationError("Exact normalized observation required")
    return {
        "evidence_schema_version": EVIDENCE_SCHEMA_VERSION,
        "observation": _encode(observation),
    }


def observation_checksum(observation: OrderObservation) -> str:
    payload = serialize_observation(observation)
    del payload["observation"]["observed_at"]
    payload["checksum_version"] = OBSERVATION_CHECKSUM_VERSION
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def serialize_read_row(row: OrderReadRow) -> dict:
    if type(row) is not OrderReadRow:
        raise OrderContractValidationError("Exact frozen read row required")
    return {"payload_schema_version": READ_PAYLOAD_SCHEMA_VERSION, "row": _encode(row)}
