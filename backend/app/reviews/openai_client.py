from __future__ import annotations

import json
from typing import Any

import httpx

from app.config import get_settings
from app.reviews.schemas import ReviewAiGenerationResult, ReviewFeedbackView, ReviewModerationDecision


REVIEW_REPLY_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["replyText", "riskLevel", "requiresApproval", "reasons", "matchedStopTopics"],
    "properties": {
        "replyText": {"type": "string", "minLength": 2, "maxLength": 5000},
        "riskLevel": {"type": "string", "enum": ["low", "medium", "high"]},
        "requiresApproval": {"type": "boolean"},
        "reasons": {"type": "array", "items": {"type": "string"}},
        "matchedStopTopics": {"type": "array", "items": {"type": "string"}},
    },
}

BATCH_REVIEW_REPLY_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["replies"],
    "properties": {
        "replies": {
            "type": "array",
            "minItems": 1,
            "maxItems": 25,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["feedbackId", "replyText", "riskLevel", "requiresApproval", "reasons", "matchedStopTopics"],
                "properties": {
                    "feedbackId": {"type": "string", "minLength": 1},
                    "replyText": {"type": "string", "minLength": 2, "maxLength": 5000},
                    "riskLevel": {"type": "string", "enum": ["low", "medium", "high"]},
                    "requiresApproval": {"type": "boolean"},
                    "reasons": {"type": "array", "items": {"type": "string"}},
                    "matchedStopTopics": {"type": "array", "items": {"type": "string"}},
                },
            },
        },
    },
}


def _extract_output_text(payload: dict[str, Any]) -> str | None:
    direct = payload.get("output_text")
    if isinstance(direct, str) and direct.strip():
        return direct
    output = payload.get("output")
    if not isinstance(output, list):
        return None
    for item in output:
        if not isinstance(item, dict):
            continue
        content = item.get("content")
        if not isinstance(content, list):
            continue
        for part in content:
            if not isinstance(part, dict):
                continue
            text = part.get("text")
            if isinstance(text, str) and text.strip():
                return text
    return None


def _build_input(
    feedback: ReviewFeedbackView,
    brand_voice_id: str,
    rating: int,
    moderation: ReviewModerationDecision,
    system_prompt: str,
    template_text: str,
) -> list[dict[str, str]]:
    user = {
        "brandVoiceId": brand_voice_id,
        "rating": rating,
        "productName": feedback.productName,
        "brandName": feedback.brandName,
        "text": feedback.text,
        "pros": feedback.pros,
        "cons": feedback.cons,
        "templateText": template_text,
        "moderation": moderation.model_dump(mode="json"),
    }
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": json.dumps(user, ensure_ascii=False, sort_keys=True)},
    ]


def _build_batch_input(items: list[dict[str, Any]], system_prompt: str) -> list[dict[str, str]]:
    payload = {
        "items": [
            {
                "feedbackId": item["feedback"].feedbackId,
                "brandVoiceId": item["brand_voice_id"],
                "rating": item["rating"],
                "productName": item["feedback"].productName,
                "brandName": item["feedback"].brandName,
                "text": item["feedback"].text,
                "pros": item["feedback"].pros,
                "cons": item["feedback"].cons,
                "templateText": item["template_text"],
                "moderation": item["moderation"].model_dump(mode="json"),
            }
            for item in items
        ]
    }
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": json.dumps(payload, ensure_ascii=False, sort_keys=True)},
    ]


def generate_openai_review_reply(
    *,
    feedback: ReviewFeedbackView,
    brand_voice_id: str,
    rating: int,
    template_text: str,
    moderation: ReviewModerationDecision,
    system_prompt: str,
    api_key: str | None = None,
    model: str | None = None,
    client: httpx.Client | None = None,
) -> ReviewAiGenerationResult:
    settings = get_settings()
    resolved_api_key = api_key if api_key is not None else settings.openai_api_key
    resolved_model = model or settings.openai_review_model
    requires_approval = moderation.state != "clean" or rating < 4
    if not resolved_api_key:
        raise RuntimeError("OPENAI_API_KEY or VELLA_OPENAI_API_KEY is required for review draft generation")

    close_client = False
    if client is None:
        client = httpx.Client(base_url=settings.openai_api_base_url, timeout=settings.openai_review_timeout_seconds)
        close_client = True
    try:
        responses_path = "/responses" if str(client.base_url).rstrip("/").endswith("/v1") else "/v1/responses"
        response = client.post(
            responses_path,
            headers={"Authorization": f"Bearer {resolved_api_key}", "Content-Type": "application/json"},
            json={
                "model": resolved_model,
                "input": _build_input(feedback, brand_voice_id, rating, moderation, system_prompt, template_text),
                "text": {
                    "format": {
                        "type": "json_schema",
                        "name": "wb_review_reply",
                        "strict": True,
                        "schema": REVIEW_REPLY_SCHEMA,
                    }
                },
            },
        )
        response.raise_for_status()
        output_text = _extract_output_text(response.json())
        if output_text is None:
            raise RuntimeError("OpenAI response did not contain output text")
        parsed = json.loads(output_text)
        result = ReviewAiGenerationResult.model_validate({**parsed, "model": resolved_model, "generationSource": "openai"})
        if requires_approval and not result.requiresApproval:
            return result.model_copy(update={"requiresApproval": True, "riskLevel": "medium", "reasons": list(result.reasons) + moderation.reasons})
        return result
    finally:
        if close_client:
            client.close()


def generate_openai_review_replies_batch(
    *,
    items: list[dict[str, Any]],
    system_prompt: str,
    api_key: str | None = None,
    model: str | None = None,
    client: httpx.Client | None = None,
) -> dict[str, ReviewAiGenerationResult]:
    settings = get_settings()
    resolved_api_key = api_key if api_key is not None else settings.openai_api_key
    resolved_model = model or settings.openai_review_model
    if not resolved_api_key:
        raise RuntimeError("OPENAI_API_KEY or VELLA_OPENAI_API_KEY is required for review draft generation")
    if len(items) < 1 or len(items) > 25:
        raise ValueError("review batch size must be between 1 and 25")

    close_client = False
    if client is None:
        client = httpx.Client(base_url=settings.openai_api_base_url, timeout=settings.openai_review_timeout_seconds)
        close_client = True
    try:
        responses_path = "/responses" if str(client.base_url).rstrip("/").endswith("/v1") else "/v1/responses"
        response = client.post(
            responses_path,
            headers={"Authorization": f"Bearer {resolved_api_key}", "Content-Type": "application/json"},
            json={
                "model": resolved_model,
                "input": _build_batch_input(items, system_prompt),
                "text": {
                    "format": {
                        "type": "json_schema",
                        "name": "wb_review_reply_batch",
                        "strict": True,
                        "schema": BATCH_REVIEW_REPLY_SCHEMA,
                    }
                },
            },
        )
        response.raise_for_status()
        output_text = _extract_output_text(response.json())
        if output_text is None:
            raise RuntimeError("OpenAI response did not contain output text")
        parsed = json.loads(output_text)
        replies = parsed.get("replies")
        if not isinstance(replies, list):
            raise RuntimeError("OpenAI batch response did not contain replies")
        by_feedback_id: dict[str, ReviewAiGenerationResult] = {}
        item_by_id = {item["feedback"].feedbackId: item for item in items}
        for reply in replies:
            if not isinstance(reply, dict):
                continue
            feedback_id = str(reply.get("feedbackId") or "")
            item = item_by_id.get(feedback_id)
            if item is None:
                continue
            result = ReviewAiGenerationResult.model_validate({**reply, "model": resolved_model, "generationSource": "openai"})
            requires_approval = item["moderation"].state != "clean" or item["rating"] < 4
            if requires_approval and not result.requiresApproval:
                result = result.model_copy(update={"requiresApproval": True, "riskLevel": "medium", "reasons": list(result.reasons) + item["moderation"].reasons})
            by_feedback_id[feedback_id] = result
        return by_feedback_id
    finally:
        if close_client:
            client.close()
