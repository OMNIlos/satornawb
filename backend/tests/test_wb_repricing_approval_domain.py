from __future__ import annotations

import ast
import inspect
from dataclasses import FrozenInstanceError
from datetime import datetime, timedelta, timezone
from typing import Callable

import pytest

from app.modules import wb_repricing
from app.modules.wb_repricing import (
    ApprovalConflictError,
    ApprovalStatus,
    ApprovalValidationError,
    PriceApprovalSnapshot,
    block_approval,
    build_action_key,
    claim_approval,
    record_apply_failure,
    record_apply_success,
    reject_approval,
)


CHECKSUM_A = "a" * 64
CHECKSUM_B = "b" * 64
CREATED_AT = datetime(2026, 9, 8, 9, 0, tzinfo=timezone.utc)
TRANSITION_AT = CREATED_AT + timedelta(minutes=1)


def _snapshot(
    status: ApprovalStatus = ApprovalStatus.pending,
    *,
    version: int = 0,
    organization_id: int = 1,
    marketplace_account_id: str = "account-1",
    approval_id: str = "approval-1",
    request_checksum: str = CHECKSUM_A,
    catalog_sku_id: str | None = "sku-1",
    nm_id: int = 123456,
    article_id: str = "FBBT_42",
    recommended_price_kopecks: int = 129_900,
    action_key: str | None = None,
    created_at: datetime = CREATED_AT,
    updated_at: datetime = CREATED_AT,
    **overrides: object,
) -> PriceApprovalSnapshot:
    metadata: dict[str, object | None] = {
        "claimed_by_membership_id": None,
        "decided_by_membership_id": None,
        "reason_code": None,
        "safe_error_code": None,
        "wb_upload_id": None,
        "result_code": None,
    }
    if status is ApprovalStatus.applying:
        metadata["claimed_by_membership_id"] = "membership-claim"
    elif status is ApprovalStatus.applied:
        metadata.update(
            claimed_by_membership_id="membership-claim",
            wb_upload_id="upload-1",
            result_code="WB_APPLY_ACCEPTED",
        )
    elif status in {ApprovalStatus.rejected, ApprovalStatus.blocked}:
        metadata.update(
            decided_by_membership_id="membership-decision",
            reason_code="MANUAL_DECISION",
        )
    elif status in {ApprovalStatus.failed, ApprovalStatus.ambiguous}:
        metadata.update(
            claimed_by_membership_id="membership-claim",
            safe_error_code="WB_APPLY_TIMEOUT",
        )
    metadata.update(overrides)
    return PriceApprovalSnapshot(
        organization_id=organization_id,
        marketplace_account_id=marketplace_account_id,
        approval_id=approval_id,
        catalog_sku_id=catalog_sku_id,
        nm_id=nm_id,
        article_id=article_id,
        recommended_price_kopecks=recommended_price_kopecks,
        request_checksum=request_checksum,
        status=status,
        version=version,
        action_key=action_key
        or build_action_key(
            organization_id,
            marketplace_account_id,
            approval_id,
            request_checksum,
        ),
        created_at=created_at,
        updated_at=updated_at,
        claimed_by_membership_id=metadata["claimed_by_membership_id"],  # type: ignore[arg-type]
        decided_by_membership_id=metadata["decided_by_membership_id"],  # type: ignore[arg-type]
        reason_code=metadata["reason_code"],  # type: ignore[arg-type]
        safe_error_code=metadata["safe_error_code"],  # type: ignore[arg-type]
        wb_upload_id=metadata["wb_upload_id"],  # type: ignore[arg-type]
        result_code=metadata["result_code"],  # type: ignore[arg-type]
    )


def test_action_key_is_stable_sha256_and_identity_scoped() -> None:
    baseline = build_action_key(1, "account-1", "approval-1", CHECKSUM_A)

    assert baseline == "f6c0ce55beef52c0e7e0be31ac15b5286524532a118c9fb052130be9c22c6507"
    assert build_action_key(1, "account-1", "approval-1", CHECKSUM_A) == baseline
    assert build_action_key(2, "account-1", "approval-1", CHECKSUM_A) != baseline
    assert build_action_key(1, "account-2", "approval-1", CHECKSUM_A) != baseline
    assert build_action_key(1, "account-1", "approval-2", CHECKSUM_A) != baseline
    assert build_action_key(1, "account-1", "approval-1", CHECKSUM_B) != baseline


def test_approval_status_exposes_the_exact_lowercase_contract() -> None:
    assert [status.name for status in ApprovalStatus] == [
        "pending",
        "applying",
        "applied",
        "rejected",
        "blocked",
        "failed",
        "ambiguous",
    ]


def test_claim_is_immutable_and_increments_version_once() -> None:
    pending = _snapshot(version=7)

    claimed = claim_approval(pending, 7, "membership-claim", TRANSITION_AT)

    assert pending.status is ApprovalStatus.pending
    assert pending.version == 7
    assert pending.claimed_by_membership_id is None
    assert claimed is not pending
    assert claimed.status is ApprovalStatus.applying
    assert claimed.version == 8
    assert claimed.claimed_by_membership_id == "membership-claim"
    assert claimed.updated_at == TRANSITION_AT
    assert claimed.request_checksum == pending.request_checksum
    assert claimed.action_key == pending.action_key
    with pytest.raises(FrozenInstanceError):
        claimed.version = 9  # type: ignore[misc]


def test_claimed_value_cannot_be_claimed_again_but_original_value_is_pure() -> None:
    pending = _snapshot()
    first = claim_approval(pending, 0, "membership-claim", TRANSITION_AT)

    with pytest.raises(ApprovalConflictError):
        claim_approval(first, 1, "membership-other", TRANSITION_AT)

    second_evaluation = claim_approval(pending, 0, "membership-claim", TRANSITION_AT)
    assert second_evaluation == first


def _claim(snapshot: PriceApprovalSnapshot, version: int) -> PriceApprovalSnapshot:
    return claim_approval(snapshot, version, "membership-claim", TRANSITION_AT)


def _reject(snapshot: PriceApprovalSnapshot, version: int) -> PriceApprovalSnapshot:
    return reject_approval(snapshot, version, "membership-decision", "MANUAL_REJECT", TRANSITION_AT)


def _block(snapshot: PriceApprovalSnapshot, version: int) -> PriceApprovalSnapshot:
    return block_approval(
        snapshot,
        version,
        "membership-decision",
        "PRICE_GUARD_BLOCKED",
        TRANSITION_AT,
    )


def _succeed(snapshot: PriceApprovalSnapshot, version: int) -> PriceApprovalSnapshot:
    return record_apply_success(snapshot, version, "upload-1", "WB_APPLY_ACCEPTED", TRANSITION_AT)


def _fail(snapshot: PriceApprovalSnapshot, version: int) -> PriceApprovalSnapshot:
    return record_apply_failure(snapshot, version, "WB_APPLY_TIMEOUT", False, TRANSITION_AT)


Command = Callable[[PriceApprovalSnapshot, int], PriceApprovalSnapshot]
COMMANDS: tuple[tuple[str, Command], ...] = (
    ("claim", _claim),
    ("reject", _reject),
    ("block", _block),
    ("success", _succeed),
    ("failure", _fail),
)


@pytest.mark.parametrize(
    ("command", "source_status"),
    [
        pytest.param(command, source_status, id=f"{name}-{source_status.value}")
        for name, command in COMMANDS
        for source_status in [
            ApprovalStatus.pending
            if name in {"success", "failure"}
            else ApprovalStatus.applying
        ]
    ],
)
def test_every_command_rejects_stale_expected_version(
    command: Command,
    source_status: ApprovalStatus,
) -> None:
    current = _snapshot(source_status, version=4)

    with pytest.raises(ApprovalConflictError):
        command(current, 3)


def test_pending_can_be_rejected_or_blocked() -> None:
    pending = _snapshot(version=2)

    rejected = reject_approval(
        pending,
        2,
        "membership-rejector",
        "MANUAL_REJECT",
        TRANSITION_AT,
    )
    blocked = block_approval(
        pending,
        2,
        "membership-blocker",
        "PRICE_GUARD_BLOCKED",
        TRANSITION_AT,
    )

    assert rejected.status is ApprovalStatus.rejected
    assert rejected.version == 3
    assert rejected.decided_by_membership_id == "membership-rejector"
    assert rejected.reason_code == "MANUAL_REJECT"
    assert blocked.status is ApprovalStatus.blocked
    assert blocked.version == 3
    assert blocked.decided_by_membership_id == "membership-blocker"
    assert blocked.reason_code == "PRICE_GUARD_BLOCKED"


def test_safe_reason_and_result_codes_may_use_existing_lowercase_style() -> None:
    rejected = reject_approval(
        _snapshot(),
        0,
        "membership-rejector",
        "manual_reject",
        TRANSITION_AT,
    )
    applied = record_apply_success(
        _snapshot(ApprovalStatus.applying),
        0,
        "upload-1",
        "accepted",
        TRANSITION_AT,
    )

    assert rejected.reason_code == "manual_reject"
    assert applied.result_code == "accepted"


@pytest.mark.parametrize(
    ("source_status", "command"),
    [
        pytest.param(ApprovalStatus.pending, _succeed, id="pending-success"),
        pytest.param(ApprovalStatus.pending, _fail, id="pending-failure"),
        pytest.param(ApprovalStatus.applying, _claim, id="applying-claim"),
        pytest.param(ApprovalStatus.applying, _reject, id="applying-reject"),
        pytest.param(ApprovalStatus.applying, _block, id="applying-block"),
        *[
            pytest.param(status, command, id=f"{status.value}-{name}")
            for status in (
                ApprovalStatus.applied,
                ApprovalStatus.rejected,
                ApprovalStatus.blocked,
                ApprovalStatus.failed,
                ApprovalStatus.ambiguous,
            )
            for name, command in COMMANDS
        ],
    ],
)
def test_invalid_and_terminal_transitions_conflict(
    source_status: ApprovalStatus,
    command: Command,
) -> None:
    current = _snapshot(source_status, version=5)

    with pytest.raises(ApprovalConflictError):
        command(current, 5)


def test_apply_success_requires_upload_id_and_sets_result_metadata() -> None:
    applying = _snapshot(ApprovalStatus.applying, version=1)

    with pytest.raises(ApprovalValidationError):
        record_apply_success(applying, 1, "  ", "WB_APPLY_ACCEPTED", TRANSITION_AT)

    applied = record_apply_success(
        applying,
        1,
        "upload-42",
        "WB_APPLY_ACCEPTED",
        TRANSITION_AT,
    )
    assert applied.status is ApprovalStatus.applied
    assert applied.version == 2
    assert applied.wb_upload_id == "upload-42"
    assert applied.result_code == "WB_APPLY_ACCEPTED"


def test_apply_failure_accepts_only_allowlisted_safe_code() -> None:
    applying = _snapshot(ApprovalStatus.applying, version=1)

    with pytest.raises(ApprovalValidationError):
        record_apply_failure(
            applying,
            1,
            "ReadTimeout: request body and credentials leaked",
            False,
            TRANSITION_AT,
        )

    failed = record_apply_failure(
        applying,
        1,
        "WB_APPLY_TIMEOUT",
        False,
        TRANSITION_AT,
    )
    assert failed.status is ApprovalStatus.failed
    assert failed.version == 2
    assert failed.safe_error_code == "WB_APPLY_TIMEOUT"
    assert failed.wb_upload_id is None
    assert failed.result_code is None


@pytest.mark.parametrize("price", [1299.0, 0, -1, True])
def test_price_must_be_a_positive_non_boolean_integer(price: object) -> None:
    with pytest.raises(ApprovalValidationError):
        _snapshot(recommended_price_kopecks=price)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("marketplace_account_id", " "),
        ("approval_id", ""),
        ("catalog_sku_id", "  "),
        ("article_id", ""),
        ("nm_id", 0),
    ],
)
def test_blank_or_invalid_identity_is_rejected(field: str, value: object) -> None:
    with pytest.raises(ApprovalValidationError):
        _snapshot(**{field: value})


@pytest.mark.parametrize("checksum", ["", "A" * 64, "a" * 63, "g" * 64])
def test_request_checksum_must_be_lowercase_sha256_hex(checksum: str) -> None:
    with pytest.raises(ApprovalValidationError):
        _snapshot(request_checksum=checksum)


def test_snapshot_rejects_action_key_that_does_not_match_ownership() -> None:
    with pytest.raises(ApprovalValidationError):
        _snapshot(action_key="0" * 64)


def test_naive_datetime_and_blank_command_metadata_are_rejected() -> None:
    naive = datetime(2026, 9, 8, 9, 1)

    with pytest.raises(ApprovalValidationError):
        _snapshot(updated_at=naive)
    with pytest.raises(ApprovalValidationError):
        claim_approval(_snapshot(), 0, " ", TRANSITION_AT)
    with pytest.raises(ApprovalValidationError):
        reject_approval(_snapshot(), 0, "membership", " ", TRANSITION_AT)
    with pytest.raises(ApprovalValidationError):
        block_approval(_snapshot(), 0, "membership", " ", TRANSITION_AT)


@pytest.mark.parametrize(
    "overrides",
    [
        {
            "status": ApprovalStatus.applied,
            "claimed_by_membership_id": "membership",
            "wb_upload_id": None,
        },
        {"wb_upload_id": "upload-on-pending"},
        {"safe_error_code": "WB_APPLY_TIMEOUT"},
        {"result_code": "WB_APPLY_ACCEPTED"},
    ],
)
def test_snapshot_rejects_inconsistent_result_metadata(overrides: dict[str, object]) -> None:
    with pytest.raises(ApprovalValidationError):
        _snapshot(**overrides)


def test_ambiguous_outcome_is_terminal_and_cannot_be_applied_or_retried() -> None:
    applying = _snapshot(ApprovalStatus.applying, version=8)
    ambiguous = record_apply_failure(
        applying,
        8,
        "WB_APPLY_TIMEOUT",
        True,
        TRANSITION_AT,
    )

    assert ambiguous.status is ApprovalStatus.ambiguous
    assert ambiguous.version == 9
    with pytest.raises(ApprovalConflictError):
        record_apply_success(
            ambiguous,
            9,
            "upload-late",
            "WB_APPLY_ACCEPTED",
            TRANSITION_AT + timedelta(minutes=1),
        )
    with pytest.raises(ApprovalConflictError):
        record_apply_failure(
            ambiguous,
            9,
            "WB_APPLY_TIMEOUT",
            False,
            TRANSITION_AT + timedelta(minutes=1),
        )


def test_module_has_no_framework_or_current_repricer_imports() -> None:
    source = inspect.getsource(wb_repricing)
    tree = ast.parse(source)
    imported_modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.add(node.module)

    forbidden = {
        "celery",
        "fastapi",
        "sqlalchemy",
        "app.repricer_bff",
        "app.repricer_execution",
        "app.repricer_sprint_b",
        "app.repricer_tasks",
        "app.wb_api",
    }
    assert not {
        imported
        for imported in imported_modules
        if any(imported == prefix or imported.startswith(f"{prefix}.") for prefix in forbidden)
    }


def test_module_has_no_mutable_module_level_containers() -> None:
    source = inspect.getsource(wb_repricing)
    tree = ast.parse(source)

    mutable_assignments = [
        node
        for node in tree.body
        if isinstance(node, (ast.Assign, ast.AnnAssign))
        and isinstance(node.value, (ast.Dict, ast.List, ast.Set))
    ]

    assert mutable_assignments == []
