from dataclasses import replace

import pytest

from app.orders.bindings import bound_high_water_mark, validate_snapshot_binding
from app.platform.integrations.publication_guard import ExpectedAccountBinding

ACCOUNT = ExpectedAccountBinding(1, "avito", "synthetic-external", None)


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
