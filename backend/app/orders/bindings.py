"""Read provenance fingerprints, never substitutes for live authorization."""

import hashlib
import hmac
import json
import re

from app.modules.orders import OrderContractValidationError


def account_binding_checksum(organization_id, accounts):
    value = [
        organization_id,
        sorted(
            [
                [
                    account.marketplace_account_id,
                    account.provider,
                    account.external_account_id,
                    account.credential_ref,
                ]
                for account in accounts
            ],
            key=lambda account: account[0],
        ),
    ]
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=True, separators=(",", ":")).encode("ascii")
    ).hexdigest()


def bound_high_water_mark(content_checksum, organization_id, accounts):
    if type(content_checksum) is not str or not re.fullmatch(
        r"[0-9a-f]{64}", content_checksum
    ):
        raise OrderContractValidationError("Invalid snapshot content checksum")
    return (
        "orders-view-v2:"
        + content_checksum
        + ":"
        + account_binding_checksum(organization_id, accounts)
    )


def validate_snapshot_binding(mark, organization_id, accounts):
    if type(mark) is not str or not re.fullmatch(
        r"orders-view-v2:[0-9a-f]{64}:[0-9a-f]{64}", mark
    ):
        raise OrderContractValidationError("Snapshot binding missing")
    if not hmac.compare_digest(
        mark.rsplit(":", 1)[1], account_binding_checksum(organization_id, accounts)
    ):
        raise OrderContractValidationError("Snapshot binding changed")
