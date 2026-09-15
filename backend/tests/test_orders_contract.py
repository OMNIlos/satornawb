from __future__ import annotations

import json
import re
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from app.modules.orders import (
    AVITO_ORDER_STATUS_MAPPING_VERSION,
    WB_STATISTICS_STATUS_MAPPING_VERSION,
    CanonicalOrderStatus,
    ExternalOrderIdentity,
    ExternalOrderItemIdentity,
    MappedMarketplaceStatus,
    MappingState,
    Marketplace,
    OrderContractValidationError,
    make_avito_source_line_key,
    make_wb_source_line_key,
    map_avito_status,
    map_wb_statistics_status,
)

FIXTURES = Path(__file__).parent / "fixtures" / "orders"


def _fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_contract_vocabularies_are_exact() -> None:
    assert {value.value for value in Marketplace} == {"wb", "avito"}
    assert {value.value for value in MappingState} == {
        "mapped",
        "unmapped",
        "ambiguous",
    }
    assert {value.value for value in CanonicalOrderStatus} == {
        "pending_confirmation",
        "accepted",
        "ready_for_fulfillment",
        "in_delivery",
        "delivered",
        "closed",
        "cancelled",
        "returning",
        "returned",
        "disputed",
    }


def test_mapping_versions_are_exact() -> None:
    assert AVITO_ORDER_STATUS_MAPPING_VERSION == "avito-order-status-v1"
    assert WB_STATISTICS_STATUS_MAPPING_VERSION == "wb-statistics-status-v1"


def test_avito_status_fixture_maps_exactly_and_preserves_raw_status() -> None:
    for row in _fixture("avito_orders_synthetic.json")["statuses"]:
        mapped = map_avito_status(row["rawStatus"])

        assert mapped.raw_status == row["rawStatus"]
        assert mapped.mapping_version == "avito-order-status-v1"
        assert mapped.evidence_source == "avito-order-management"
        assert mapped.canonical_status == row["canonicalStatus"]
        assert mapped.mapping_state is (
            MappingState.MAPPED
            if row["canonicalStatus"] is not None
            else MappingState.UNMAPPED
        )


@pytest.mark.parametrize(
    "raw_status",
    [None, "", " ", " ready_to_ship", "ready_to_ship ", "ready_to_ship\n"],
)
def test_avito_status_rejects_missing_empty_or_edge_whitespace(
    raw_status: object,
) -> None:
    with pytest.raises(OrderContractValidationError):
        map_avito_status(raw_status)  # type: ignore[arg-type]


def test_avito_status_is_exact_without_case_or_alias_fallbacks() -> None:
    for raw_status in ("READY_TO_SHIP", "ready", "awaiting_track"):
        mapped = map_avito_status(raw_status)

        assert mapped.raw_status == raw_status
        assert mapped.canonical_status is None
        assert mapped.mapping_state is MappingState.UNMAPPED


def test_wb_statistics_fixture_maps_only_proven_cancellation() -> None:
    rows = _fixture("wb_statistics_orders_synthetic.json")["orders"]
    mapped = [
        map_wb_statistics_status(
            row["rawStatus"],
            is_cancelled=row["isCancelled"],
            cancel_evidence_present=row["cancelEvidencePresent"],
        )
        for row in rows
    ]

    assert [item.canonical_status for item in mapped] == [
        CanonicalOrderStatus.CANCELLED,
        CanonicalOrderStatus.CANCELLED,
        None,
    ]
    assert [item.mapping_state for item in mapped] == [
        MappingState.MAPPED,
        MappingState.MAPPED,
        MappingState.UNMAPPED,
    ]
    assert [item.raw_status for item in mapped] == [
        None,
        "synthetic_cancel_marker_status",
        "synthetic_supplier_order_observed",
    ]
    assert all(item.mapping_version == "wb-statistics-status-v1" for item in mapped)
    assert all(
        item.evidence_source == "wb-statistics-supplier-orders" for item in mapped
    )


def test_wb_non_cancelled_row_never_becomes_fulfillment_ready() -> None:
    mapped = map_wb_statistics_status(
        "ready_to_ship",
        is_cancelled=False,
        cancel_evidence_present=False,
    )

    assert mapped.raw_status == "ready_to_ship"
    assert mapped.canonical_status is None
    assert mapped.mapping_state is MappingState.UNMAPPED


def test_wb_sales_return_text_is_not_an_order_returned_status() -> None:
    mapped = map_wb_statistics_status(
        "isReturn=true",
        is_cancelled=False,
        cancel_evidence_present=False,
    )

    assert mapped.raw_status == "isReturn=true"
    assert mapped.canonical_status is None
    assert mapped.mapping_state is MappingState.UNMAPPED


@pytest.mark.parametrize(
    ("is_cancelled", "cancel_evidence_present"),
    [(1, False), (False, 0), ("false", False), (False, None)],
)
def test_wb_cancellation_evidence_requires_strict_booleans(
    is_cancelled: object, cancel_evidence_present: object
) -> None:
    with pytest.raises(OrderContractValidationError):
        map_wb_statistics_status(
            None,
            is_cancelled=is_cancelled,  # type: ignore[arg-type]
            cancel_evidence_present=cancel_evidence_present,  # type: ignore[arg-type]
        )


@pytest.mark.parametrize("raw_status", ["", " ", "observed ", " observed", "x\t"])
def test_wb_present_raw_status_uses_exact_whitespace_rules(raw_status: str) -> None:
    with pytest.raises(OrderContractValidationError):
        map_wb_statistics_status(
            raw_status,
            is_cancelled=False,
            cancel_evidence_present=False,
        )


def test_external_order_identity_is_frozen_and_tenant_account_scoped() -> None:
    shared = _fixture("avito_orders_synthetic.json")["orders"]
    identities = {
        ExternalOrderIdentity(
            organization_id=row["organizationId"],
            marketplace_account_id=row["marketplaceAccountId"],
            marketplace=Marketplace.AVITO,
            external_order_id=row["externalOrderId"],
        )
        for row in shared
    }

    assert len(identities) == 2
    identity = next(iter(identities))
    with pytest.raises(FrozenInstanceError):
        identity.external_order_id = "synthetic-mutated"  # type: ignore[misc]


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("organization_id", 0),
        ("organization_id", True),
        ("marketplace_account_id", -1),
        ("marketplace_account_id", False),
        ("marketplace", "WB"),
        ("marketplace", " avito"),
        ("external_order_id", ""),
        ("external_order_id", " synthetic-order"),
    ],
)
def test_external_order_identity_rejects_invalid_required_fields(
    field: str, value: object
) -> None:
    kwargs = {
        "organization_id": 101,
        "marketplace_account_id": 1001,
        "marketplace": Marketplace.AVITO,
        "external_order_id": "synthetic-order",
    }
    kwargs[field] = value

    with pytest.raises(OrderContractValidationError):
        ExternalOrderIdentity(**kwargs)  # type: ignore[arg-type]


def test_avito_repeated_listing_occurrences_have_distinct_keys() -> None:
    row = _fixture("avito_orders_synthetic.json")["orders"][0]
    repeated = row["items"][:2]
    keys = [
        make_avito_source_line_key(
            row["externalOrderId"],
            item["externalItemId"],
            item["occurrenceIndex"],
        )
        for item in repeated
    ]

    assert len(set(keys)) == 2
    assert all(row["externalOrderId"] in key for key in keys)
    assert all(repeated[0]["externalItemId"] in key for key in keys)


def test_avito_stable_order_line_id_wins_over_listing_and_occurrence() -> None:
    first = make_avito_source_line_key(
        "synthetic-order",
        "synthetic-listing-a",
        0,
        stable_order_line_id="synthetic-stable-line",
    )
    second = make_avito_source_line_key(
        "synthetic-order",
        "synthetic-listing-b",
        9,
        stable_order_line_id="synthetic-stable-line",
    )

    assert first == second
    assert "synthetic-stable-line" in first
    assert "synthetic-listing" not in first


def test_avito_fallback_key_is_unambiguous_for_delimiter_like_ids() -> None:
    assert make_avito_source_line_key("a:b", "c", 1) != make_avito_source_line_key(
        "a", "b:c", 1
    )


@pytest.mark.parametrize(
    "kwargs",
    [
        {
            "external_order_id": "",
            "external_item_id": "synthetic-item",
            "occurrence_index": 0,
        },
        {
            "external_order_id": "synthetic-order ",
            "external_item_id": "synthetic-item",
            "occurrence_index": 0,
        },
        {
            "external_order_id": "synthetic-order",
            "external_item_id": " item",
            "occurrence_index": 0,
        },
        {
            "external_order_id": "synthetic-order",
            "external_item_id": None,
            "occurrence_index": -1,
        },
        {
            "external_order_id": "synthetic-order",
            "external_item_id": None,
            "occurrence_index": True,
        },
        {
            "external_order_id": "synthetic-order",
            "external_item_id": None,
            "occurrence_index": 0,
            "stable_order_line_id": "",
        },
    ],
)
def test_avito_source_line_key_rejects_invalid_identity_parts(kwargs: dict) -> None:
    with pytest.raises(OrderContractValidationError):
        make_avito_source_line_key(**kwargs)


def test_external_order_item_identity_is_frozen_and_keeps_occurrence() -> None:
    order = ExternalOrderIdentity(101, 1001, Marketplace.AVITO, "synthetic-order")
    first = ExternalOrderItemIdentity(
        order_identity=order,
        source_line_key=make_avito_source_line_key(
            order.external_order_id, "synthetic-listing", 0
        ),
        external_item_id="synthetic-listing",
        occurrence_index=0,
    )
    second = ExternalOrderItemIdentity(
        order_identity=order,
        source_line_key=make_avito_source_line_key(
            order.external_order_id, "synthetic-listing", 1
        ),
        external_item_id="synthetic-listing",
        occurrence_index=1,
    )

    assert first != second
    with pytest.raises(FrozenInstanceError):
        first.occurrence_index = 2  # type: ignore[misc]


def test_external_order_item_identity_keeps_tenant_and_account_scope() -> None:
    source_line_key = make_avito_source_line_key(
        "synthetic-order-shared", "synthetic-listing-shared", 0
    )
    items = {
        ExternalOrderItemIdentity(
            order_identity=ExternalOrderIdentity(
                organization_id=organization_id,
                marketplace_account_id=account_id,
                marketplace=Marketplace.AVITO,
                external_order_id="synthetic-order-shared",
            ),
            source_line_key=source_line_key,
            external_item_id="synthetic-listing-shared",
            occurrence_index=0,
        )
        for organization_id, account_id in ((101, 1001), (202, 2002))
    }

    assert len(items) == 2


def test_external_order_item_identity_validates_all_parts() -> None:
    order = ExternalOrderIdentity(101, 1001, Marketplace.WB, "synthetic-order")

    with pytest.raises(OrderContractValidationError):
        ExternalOrderItemIdentity(order, " synthetic-key", None, 0)
    with pytest.raises(OrderContractValidationError):
        ExternalOrderItemIdentity(order, "synthetic-key", "item ", 0)
    with pytest.raises(OrderContractValidationError):
        ExternalOrderItemIdentity(order, "synthetic-key", None, -1)
    with pytest.raises(OrderContractValidationError):
        ExternalOrderItemIdentity(object(), "synthetic-key", None, 0)  # type: ignore[arg-type]


def test_wb_source_line_key_requires_proven_stable_unit_id() -> None:
    assert make_wb_source_line_key("synthetic-srid-unit-1").endswith(
        "synthetic-srid-unit-1"
    )

    for missing_or_unstable in (None, "", " ", " synthetic-srid", "synthetic-srid "):
        with pytest.raises(OrderContractValidationError):
            make_wb_source_line_key(missing_or_unstable)


def test_mapped_status_model_rejects_inconsistent_states() -> None:
    with pytest.raises(OrderContractValidationError):
        MappedMarketplaceStatus(
            raw_status="synthetic",
            canonical_status=None,
            mapping_state=MappingState.MAPPED,
            mapping_version="synthetic-version",
            evidence_source="synthetic-source",
        )
    with pytest.raises(OrderContractValidationError):
        MappedMarketplaceStatus(
            raw_status="synthetic",
            canonical_status=CanonicalOrderStatus.CLOSED,
            mapping_state=MappingState.UNMAPPED,
            mapping_version="synthetic-version",
            evidence_source="synthetic-source",
        )


def test_fixtures_are_explicitly_synthetic_and_contain_no_pii_fields() -> None:
    forbidden_keys = {
        "buyerName",
        "buyerPhone",
        "address",
        "recipientName",
        "token",
        "clientSecret",
    }
    phone_like = re.compile(r"(?:\+7|8)\d{10}")

    def inspect(value: object) -> None:
        if isinstance(value, dict):
            assert forbidden_keys.isdisjoint(value)
            for child in value.values():
                inspect(child)
        elif isinstance(value, list):
            for child in value:
                inspect(child)
        elif isinstance(value, str):
            assert not phone_like.search(value)
            if "Id" in value or "id" in value or "unit" in value or "order" in value:
                assert "synthetic" in value

    inspect(_fixture("avito_orders_synthetic.json"))
    inspect(_fixture("wb_statistics_orders_synthetic.json"))
