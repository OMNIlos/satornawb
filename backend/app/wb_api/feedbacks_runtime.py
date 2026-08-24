from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Literal

from app.wb_api.client import RateLimitedWbApiClient, WbApiRequest, build_wb_feedbacks_client


FeedbackOrder = Literal["dateDesc", "dateAsc"]


class WbFeedbacksFetchError(RuntimeError):
    def __init__(self, *, status_code: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message


@dataclass(frozen=True)
class WbFeedbackRow:
    feedback_id: str
    nm_id: int
    imt_id: int | None
    brand_name: str
    product_name: str
    created_date: datetime
    text: str
    pros: str
    cons: str
    answer_text: str | None
    is_answered: bool
    rating: int | None
    raw_payload: dict[str, Any]


def _payload(data: Any) -> Any:
    if not isinstance(data, dict):
        return data
    return data.get("data", data)


def _extract_feedback_items(node: Any) -> list[dict[str, Any]]:
    payload = _payload(node)
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        for key in ("feedbacks", "items", "data"):
            value = payload.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
        return [payload]
    return []


def _as_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _as_datetime(value: Any) -> datetime:
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
        except ValueError:
            pass
    return datetime.now(timezone.utc)


def _extract_rating(item: dict[str, Any]) -> int | None:
    for key in ("productValuation", "valuation", "rating"):
        rating = _as_int(item.get(key))
        if rating is not None:
            return rating
    product_details = item.get("productDetails")
    if isinstance(product_details, dict):
        for key in ("productValuation", "valuation", "rating"):
            rating = _as_int(product_details.get(key))
            if rating is not None:
                return rating
    return None


def _to_feedback_row(item: dict[str, Any]) -> WbFeedbackRow | None:
    feedback_id = str(item.get("id") or "").strip()
    product_details = item.get("productDetails")
    if not feedback_id or not isinstance(product_details, dict):
        return None
    nm_id = _as_int(product_details.get("nmId"))
    if nm_id is None:
        return None
    answer = item.get("answer") if isinstance(item.get("answer"), dict) else None
    answer_text = str(answer.get("text")).strip() if answer and answer.get("text") is not None else None
    return WbFeedbackRow(
        feedback_id=feedback_id,
        nm_id=nm_id,
        imt_id=_as_int(product_details.get("imtId")),
        brand_name=str(product_details.get("brandName") or "").strip(),
        product_name=str(product_details.get("productName") or "").strip(),
        created_date=_as_datetime(item.get("createdDate")),
        text=str(item.get("text") or "").strip(),
        pros=str(item.get("pros") or "").strip(),
        cons=str(item.get("cons") or "").strip(),
        answer_text=answer_text if answer_text else None,
        is_answered=bool(answer_text),
        rating=_extract_rating(item),
        raw_payload=item,
    )


def fetch_feedbacks(
    *,
    scenario: str = "complete",
    wb_token: str | None = None,
    is_answered: bool | None = None,
    nm_id: int | None = None,
    take: int = 5000,
    skip: int = 0,
    order: FeedbackOrder = "dateDesc",
    date_from_epoch: int | None = None,
    date_to_epoch: int | None = None,
) -> list[WbFeedbackRow]:
    client = RateLimitedWbApiClient(inner=build_wb_feedbacks_client(scenario=scenario, token_override=wb_token))
    query: dict[str, Any] = {
        "take": take,
        "skip": skip,
        "order": order,
    }
    if is_answered is not None:
        query["isAnswered"] = is_answered
    if nm_id is not None:
        query["nmId"] = nm_id
    if date_from_epoch is not None:
        query["dateFrom"] = date_from_epoch
    if date_to_epoch is not None:
        query["dateTo"] = date_to_epoch
    response = client.request(WbApiRequest(method="GET", path="/api/v1/feedbacks", query=query))
    if not response.ok:
        error = response.error
        raise WbFeedbacksFetchError(
            status_code=response.statusCode,
            code=error.code if error else "wb_request_failed",
            message=error.message if error else f"WB HTTP {response.statusCode}",
        )
    rows: list[WbFeedbackRow] = []
    for item in _extract_feedback_items(response.data):
        row = _to_feedback_row(item)
        if row is not None:
            rows.append(row)
    return rows


def fetch_feedback_by_id(*, feedback_id: str, scenario: str = "complete", wb_token: str | None = None) -> WbFeedbackRow | None:
    client = RateLimitedWbApiClient(inner=build_wb_feedbacks_client(scenario=scenario, token_override=wb_token))
    response = client.request(WbApiRequest(method="GET", path="/api/v1/feedback", query={"id": feedback_id}))
    if not response.ok:
        return None
    payload = _payload(response.data)
    if not isinstance(payload, dict):
        return None
    return _to_feedback_row(payload)
