"""Pure upload-ID projection from the original decoded POST response body.

Call before legacy `_as_int` or DTO coercion. Never pass a history query argument
or reconstructed PriceApplyResponse. This projection is not authentication,
committed-marker proof, raw JSON/duplicate-key validation or receipt persistence.
Caller-provided transport metadata is trusted adapter context, not a capability.
No current WB client or sending flow imports this module.
"""

import re
from decimal import Decimal


class UploadReceiptValidationError(ValueError):
    def __init__(self):
        super().__init__("invalid_upload_receipt")


def _upload_id(value):
    if type(value) is int and value > 0:
        return format(Decimal(value), "f")
    if type(value) is str and re.fullmatch(r"[1-9][0-9]*", value) is not None:
        return value
    raise UploadReceiptValidationError()


def extract_post_upload_id(
    payload, *, method, path, status_code, ok, apply_mode
) -> str:
    """Return only an exact positive decimal ID, never an applied status.

    Missing/invalid receipt after a marker is uncertainty, not proof of rejection
    and never permission to resend. No raw error text or payload is retained.
    """
    if (
        type(method) is not str
        or method != "POST"
        or type(path) is not str
        or path != "/api/v2/upload/task"
        or type(status_code) is not int
        or not 200 <= status_code < 300
        or ok is not True
        or type(apply_mode) is not str
        or apply_mode != "wb_api"
    ):
        raise UploadReceiptValidationError()
    if type(payload) is not dict:
        raise UploadReceiptValidationError()
    data = payload.get("data", payload)
    if type(data) is not dict:
        raise UploadReceiptValidationError()
    for row in (payload, data):
        if "error" in row and row["error"] is not False:
            raise UploadReceiptValidationError()
        if "errorText" in row and row["errorText"] != "":
            raise UploadReceiptValidationError()
    ids = [_upload_id(data[key]) for key in ("id", "uploadID") if key in data]
    if not ids or any(value != ids[0] for value in ids):
        raise UploadReceiptValidationError()
    return ids[0]
