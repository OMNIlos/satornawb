import json
from dataclasses import replace
from pathlib import Path

import pytest

from app.orders.bindings import (
    ACCOUNT_BINDING_SCHEMA_VERSION,
    account_binding_checksum,
    bound_high_water_mark,
    deserialize_account_bindings,
    serialize_account_bindings,
    validate_snapshot_binding,
)
from app.platform.integrations.publication_guard import ExpectedAccountBinding

ACCOUNT = ExpectedAccountBinding(1, "avito", "synthetic-external", None)


@pytest.mark.parametrize(
    "vector",
    json.loads(
        (
            Path(__file__).parent / "fixtures/orders/account_binding_golden_v1.json"
        ).read_text()
    )["vectors"],
)
def test_binding_golden_bytes_checksum_and_roundtrip(vector):
    accounts = tuple(ExpectedAccountBinding(*account) for account in vector["accounts"])
    raw = vector["canonical_ascii"].encode("ascii")
    assert serialize_account_bindings(vector["organization_id"], accounts) == raw
    assert (
        account_binding_checksum(vector["organization_id"], accounts)
        == vector["sha256"]
    )
    assert deserialize_account_bindings(raw) == (
        vector["organization_id"],
        tuple(sorted(accounts, key=lambda account: account.marketplace_account_id)),
    )


def test_binding_codec_preserves_existing_v1_checksum_bytes():
    expected = b'[1,[[1,"avito","synthetic-external",null]]]'
    assert ACCOUNT_BINDING_SCHEMA_VERSION == 1
    assert serialize_account_bindings(1, (ACCOUNT,)) == expected
    assert deserialize_account_bindings(expected) == (1, (ACCOUNT,))


@pytest.mark.parametrize(
    "payload",
    [
        b'[true,[[1,"avito","synthetic-external",null]]]',
        b'[1,[[true,"avito","synthetic-external",null]]]',
        b"[1,[]]",
        b'[1,[[1,"avito","synthetic-external",null]]] ',
        b'[1,[[1,"avito","synthetic-external",null],[1,"avito","synthetic-external",null]]]',
        b'[1,[[1,"avito","synthetic-external",""]]]',
    ],
)
def test_binding_codec_rejects_noncanonical_or_invalid_metadata(payload):
    with pytest.raises(ValueError):
        deserialize_account_bindings(payload)


def test_bound_mark_is_order_independent_and_contains_no_raw_binding():
    other = replace(
        ACCOUNT, marketplace_account_id=2, credential_ref="synthetic-private-ref"
    )
    first = bound_high_water_mark("a" * 64, 1, (ACCOUNT, other))
    assert first == bound_high_water_mark("a" * 64, 1, (other, ACCOUNT))
    assert "synthetic" not in first
    validate_snapshot_binding(first, 1, (other, ACCOUNT))


@pytest.mark.parametrize(
    "mark",
    [
        "synthetic-legacy",
        "orders-view-v1:" + "a" * 64,
        "orders-view-v2:" + "a" * 64,
        None,
    ],
)
def test_unbound_marks_are_not_accepted(mark):
    with pytest.raises(ValueError, match="binding"):
        validate_snapshot_binding(mark, 1, (ACCOUNT,))


@pytest.mark.parametrize(
    "change",
    [
        {"provider": "wb"},
        {"external_account_id": "synthetic-new"},
        {"credential_ref": "synthetic-reference"},
        {"marketplace_account_id": 2},
    ],
)
def test_binding_change_invalidates_frozen_mark(change):
    mark = bound_high_water_mark("a" * 64, 1, (ACCOUNT,))
    with pytest.raises(ValueError, match="binding changed"):
        validate_snapshot_binding(mark, 1, (replace(ACCOUNT, **change),))


def test_org_and_extra_mark_segments_cannot_be_substituted():
    mark = bound_high_water_mark("a" * 64, 1, (ACCOUNT,))
    with pytest.raises(ValueError, match="binding"):
        validate_snapshot_binding(mark, 2, (ACCOUNT,))
    with pytest.raises(ValueError, match="binding"):
        validate_snapshot_binding(mark + ":extra", 1, (ACCOUNT,))
