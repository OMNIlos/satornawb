from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from app.platform.funnel.raw import (
    FunnelNormalizationError,
    _response_checksum,
    normalize_raw_funnel,
)
from app.platform.period import Period
from app.wb_api.ads_runtime import _request_with_retry
from app.wb_api.client import (
    RateLimitedWbApiClient,
    WbApiRequest,
    build_wb_analytics_client,
)

_PATH = "/api/analytics/v3/sales-funnel/products/history"


class RawFunnelFetchError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class RawFunnelFetch:
    state: Literal["ready", "partial"]
    bundle: dict[str, Any]
    expected_requests: int
    completed_requests: int
    failure_codes: tuple[str, ...]


def fetch_raw_funnel(
    period: Period,
    nm_ids: list[int],
    *,
    wb_token: str,
    scenario: str = "complete",
) -> RawFunnelFetch:
    if not wb_token.strip():
        raise ValueError("WB token is required")
    client = RateLimitedWbApiClient(
        inner=build_wb_analytics_client(scenario, token_override=wb_token)
    )
    return _execute_plan(client, period, nm_ids)


def _execute_plan(
    client: RateLimitedWbApiClient, period: Period, nm_ids: list[int]
) -> RawFunnelFetch:
    if (period.date_to - period.date_from).days >= 7:
        raise ValueError("funnel period must not exceed seven days")
    if not isinstance(nm_ids, list) or not nm_ids or any(
        not _is_positive_integer(value) for value in nm_ids
    ):
        raise ValueError("funnel nmIds must be positive integers")

    period_payload = {
        "dateFrom": period.date_from.isoformat(),
        "dateTo": period.date_to.isoformat(),
    }
    pages: list[dict[str, Any]] = []
    manifest: list[dict[str, Any]] = []
    failures: list[str] = []
    completed = 0

    for chunk in _chunks(sorted(set(nm_ids)), 20):
        body = {
            "selectedPeriod": {
                "start": period.date_from.isoformat(),
                "end": period.date_to.isoformat(),
            },
            "nmIds": chunk,
            "skipDeletedNm": False,
            "aggregationLevel": "day",
        }
        request = WbApiRequest(method="POST", path=_PATH, jsonBody=body)
        response = _request_with_retry(client, request)
        try:
            checksum = _response_checksum(response.data)
        except FunnelNormalizationError:
            checksum = None
        valid = response.ok and checksum is not None and _valid_payload(response.data)
        item = {
            "endpoint": f"POST {_PATH}",
            "request": body,
            "statusCode": response.statusCode,
            "ok": valid,
            "wbRequestId": response.wbRequestId,
            "responseChecksum": checksum,
        }
        page = {"request": body, "payload": response.data}
        if valid:
            try:
                normalize_raw_funnel(
                    period,
                    {
                        "period": period_payload,
                        "pages": [page],
                        "manifest": [item],
                    },
                )
            except FunnelNormalizationError:
                valid = item["ok"] = False
        if valid:
            completed += 1
            pages.append(page)
        else:
            code = (
                response.error.code
                if not response.ok and response.error is not None
                else "invalid_payload"
            )
            if code not in failures:
                failures.append(code)
        manifest.append(item)

    bundle = {"period": period_payload, "pages": pages, "manifest": manifest}
    if not failures:
        try:
            normalize_raw_funnel(period, bundle)
        except FunnelNormalizationError:
            failures.append("invalid_payload")
    return RawFunnelFetch(
        state="partial" if failures else "ready",
        bundle=bundle,
        expected_requests=len(manifest),
        completed_requests=completed,
        failure_codes=tuple(failures),
    )


def _valid_payload(payload: Any) -> bool:
    return isinstance(payload, list) or (
        isinstance(payload, dict)
        and set(payload) == {"data"}
        and isinstance(payload["data"], list)
    )


def _is_positive_integer(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def _chunks(items: list[int], size: int) -> list[list[int]]:
    return [items[index : index + size] for index in range(0, len(items), size)]
