from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal, Protocol

from pydantic import BaseModel, Field

try:
    import httpx
except Exception:  # pragma: no cover - live mode dependency
    httpx = None  # type: ignore[assignment]


class AvitoReviewsFetchRequest(BaseModel):
    limit: int = Field(default=50, ge=1, le=50)
    offset: int = Field(default=0, ge=0)


class AvitoRatingInfo(BaseModel):
    isEnabled: bool
    score: float | None = None
    reviewsCount: int | None = Field(default=None, ge=0)
    reviewsWithScoreCount: int | None = Field(default=None, ge=0)


class AvitoReviewAnswer(BaseModel):
    answerId: str = Field(min_length=1)
    text: str = ""
    status: Literal["moderation", "published", "rejected", "unknown"] = "unknown"
    createdAt: str | None = None
    rejectReasons: list[str] = Field(default_factory=list)


class AvitoReviewRow(BaseModel):
    reviewId: str = Field(min_length=1)
    score: int = Field(ge=1, le=5)
    stage: str
    text: str = ""
    usedInScore: bool
    canAnswer: bool
    createdAt: str | None = None
    buyerName: str = "Покупатель Авито"
    itemId: str | None = None
    itemTitle: str | None = None
    images: list[str] = Field(default_factory=list)
    answer: AvitoReviewAnswer | None = None
    sourceStatus: Literal["fresh", "partial"] = "fresh"


class AvitoReviewsError(BaseModel):
    code: str = Field(min_length=1)
    message: str = Field(min_length=1)
    retryable: bool
    blockerIds: list[str] = Field(default_factory=list)


class AvitoReviewsFetchResult(BaseModel):
    status: Literal["synced", "blocked"]
    rating: AvitoRatingInfo | None = None
    reviews: list[AvitoReviewRow] = Field(default_factory=list)
    total: int = Field(default=0, ge=0)
    diagnostics: dict[str, Any] | None = None
    error: AvitoReviewsError | None = None


class AvitoAnswerCreateResult(BaseModel):
    answerId: str = Field(min_length=1)
    createdAt: str | None = None


class AvitoReviewsUpstreamError(RuntimeError):
    def __init__(self, error: AvitoReviewsError, http_status: int) -> None:
        super().__init__(error.message)
        self.error = error
        self.http_status = http_status


class AvitoReviewsClient(Protocol):
    def fetch_reviews(self, request: AvitoReviewsFetchRequest) -> AvitoReviewsFetchResult:
        ...

    def create_answer(self, review_id: str, message: str) -> AvitoAnswerCreateResult:
        ...

    def delete_answer(self, answer_id: str) -> bool:
        ...


def _iso_from_unix(value: Any) -> str | None:
    try:
        timestamp = int(value)
    except (TypeError, ValueError):
        return None
    if timestamp <= 0:
        return None
    return datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat()


def _first_image_url(raw: dict[str, Any]) -> list[str]:
    images = raw.get("images") if isinstance(raw.get("images"), list) else []
    urls: list[str] = []
    for image in images:
        if not isinstance(image, dict):
            continue
        sizes = image.get("sizes") if isinstance(image.get("sizes"), list) else []
        best = next((size.get("url") for size in sizes if isinstance(size, dict) and size.get("url")), None)
        if best:
            urls.append(str(best))
    return urls


class LiveAvitoReviewsClient:
    def __init__(self, access_token: str, base_url: str = "https://api.avito.ru", timeout_seconds: float = 20.0) -> None:
        if httpx is None:
            raise RuntimeError("httpx is required for LiveAvitoReviewsClient")
        self.access_token = access_token
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.access_token}", "Accept": "application/json", "Content-Type": "application/json"}

    def fetch_reviews(self, request: AvitoReviewsFetchRequest, http_client: Any | None = None) -> AvitoReviewsFetchResult:
        try:
            if http_client is not None:
                return self._fetch_reviews_with_client(request, http_client)
            with httpx.Client(timeout=self.timeout_seconds) as client:
                return self._fetch_reviews_with_client(request, client)
        except httpx.HTTPStatusError as exc:
            return AvitoReviewsFetchResult(status="blocked", error=self._http_error(exc))
        except Exception as exc:
            return AvitoReviewsFetchResult(
                status="blocked",
                error=AvitoReviewsError(code="transport_error", message=str(exc), retryable=True, blockerIds=["AVITO_REVIEWS"]),
            )

    def _fetch_reviews_with_client(self, request: AvitoReviewsFetchRequest, client: Any) -> AvitoReviewsFetchResult:
        rating_payload = self._get_json(client, "/ratings/v1/info")
        reviews_payload = self._get_json(client, "/ratings/v1/reviews", params={"limit": min(request.limit, 50), "offset": request.offset})
        reviews = [self._review_row(row) for row in reviews_payload.get("reviews", []) if isinstance(row, dict)]
        return AvitoReviewsFetchResult(
            status="synced",
            rating=self._rating_info(rating_payload),
            reviews=reviews,
            total=int(reviews_payload.get("total") or len(reviews)),
            diagnostics={
                "ratingKeys": sorted(str(key) for key in rating_payload.keys()),
                "reviewsCount": len(reviews),
                "rawTotal": reviews_payload.get("total"),
            },
        )

    def _get_json(self, client: Any, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        response = client.get(f"{self.base_url}{path}", params=params, headers=self._headers())
        response.raise_for_status()
        payload = response.json()
        return payload if isinstance(payload, dict) else {}

    def _rating_info(self, payload: dict[str, Any]) -> AvitoRatingInfo:
        rating = payload.get("rating") if isinstance(payload.get("rating"), dict) else {}
        return AvitoRatingInfo(
            isEnabled=bool(payload.get("isEnabled")),
            score=float(rating["score"]) if rating.get("score") is not None else None,
            reviewsCount=int(rating["reviewsCount"]) if rating.get("reviewsCount") is not None else None,
            reviewsWithScoreCount=int(rating["reviewsWithScoreCount"]) if rating.get("reviewsWithScoreCount") is not None else None,
        )

    def _review_row(self, raw: dict[str, Any]) -> AvitoReviewRow:
        item = raw.get("item") if isinstance(raw.get("item"), dict) else {}
        sender = raw.get("sender") if isinstance(raw.get("sender"), dict) else {}
        return AvitoReviewRow(
            reviewId=str(raw.get("id") or ""),
            score=max(1, min(5, int(raw.get("score") or 5))),
            stage=str(raw.get("stage") or "unknown"),
            text=str(raw.get("text") or ""),
            usedInScore=bool(raw.get("usedInScore")),
            canAnswer=bool(raw.get("canAnswer")),
            createdAt=_iso_from_unix(raw.get("createdAt")),
            buyerName=str(sender.get("name") or "Покупатель Авито"),
            itemId=str(item.get("id")) if item.get("id") is not None else None,
            itemTitle=item.get("title"),
            images=_first_image_url(raw),
            answer=self._answer(raw.get("answer")),
        )

    def _answer(self, raw: Any) -> AvitoReviewAnswer | None:
        if not isinstance(raw, dict) or raw.get("id") is None:
            return None
        reasons = raw.get("reject_reasons") if isinstance(raw.get("reject_reasons"), list) else []
        status = str(raw.get("status") or "unknown")
        if status not in {"moderation", "published", "rejected"}:
            status = "unknown"
        return AvitoReviewAnswer(
            answerId=str(raw.get("id")),
            text=str(raw.get("text") or ""),
            status=status,  # type: ignore[arg-type]
            createdAt=_iso_from_unix(raw.get("createdAt")),
            rejectReasons=[str(reason.get("title")) for reason in reasons if isinstance(reason, dict) and reason.get("title")],
        )

    def create_answer(self, review_id: str, message: str, http_client: Any | None = None) -> AvitoAnswerCreateResult:
        body = {"reviewId": int(review_id), "message": message}
        try:
            if http_client is not None:
                response = http_client.post(f"{self.base_url}/ratings/v1/answers", json=body, headers=self._headers())
            else:
                with httpx.Client(timeout=self.timeout_seconds) as client:
                    response = client.post(f"{self.base_url}/ratings/v1/answers", json=body, headers=self._headers())
            response.raise_for_status()
            payload = response.json()
            return AvitoAnswerCreateResult(answerId=str(payload.get("id") or ""), createdAt=_iso_from_unix(payload.get("createdAt")))
        except httpx.HTTPStatusError as exc:
            raise AvitoReviewsUpstreamError(self._http_error(exc), exc.response.status_code) from exc

    def delete_answer(self, answer_id: str, http_client: Any | None = None) -> bool:
        try:
            if http_client is not None:
                response = http_client.delete(f"{self.base_url}/ratings/v1/answers/{answer_id}", headers=self._headers())
            else:
                with httpx.Client(timeout=self.timeout_seconds) as client:
                    response = client.delete(f"{self.base_url}/ratings/v1/answers/{answer_id}", headers=self._headers())
            response.raise_for_status()
            payload = response.json()
            return bool(payload.get("success", True)) if isinstance(payload, dict) else True
        except httpx.HTTPStatusError as exc:
            raise AvitoReviewsUpstreamError(self._http_error(exc), exc.response.status_code) from exc

    @staticmethod
    def _http_error(exc: Any) -> AvitoReviewsError:
        status_code = exc.response.status_code
        if status_code == 401:
            return AvitoReviewsError(code="auth_required", message="Avito HTTP 401", retryable=False, blockerIds=["AVITO_AUTH"])
        if status_code == 403:
            return AvitoReviewsError(code="forbidden_scope", message="Avito HTTP 403", retryable=False, blockerIds=["AVITO_RATINGS_SCOPE"])
        if status_code == 429:
            return AvitoReviewsError(code="rate_limited", message="Avito HTTP 429", retryable=True, blockerIds=["AVITO_RATE_LIMIT"])
        return AvitoReviewsError(code="avito_reviews_failed", message=f"Avito HTTP {status_code}", retryable=status_code >= 500, blockerIds=["AVITO_REVIEWS"])


def build_avito_reviews_client(access_token: str, base_url: str = "https://api.avito.ru", timeout_seconds: float = 20.0) -> AvitoReviewsClient:
    return LiveAvitoReviewsClient(access_token=access_token, base_url=base_url, timeout_seconds=timeout_seconds)
