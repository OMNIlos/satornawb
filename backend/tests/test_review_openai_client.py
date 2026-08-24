from __future__ import annotations

from datetime import datetime, timezone

import httpx
import pytest

from app.reviews.openai_client import generate_openai_review_replies_batch, generate_openai_review_reply
from app.reviews.schemas import ReviewFeedbackView, ReviewModerationDecision


def _feedback(text: str = "Очень понравилась футболка") -> ReviewFeedbackView:
    return ReviewFeedbackView(
        feedbackId="safe-review-001",
        nmId=446312900,
        imtId=202307111,
        brandName="Satorna",
        productName="Футболка с принтом",
        createdDate=datetime(2026, 7, 17, tzinfo=timezone.utc),
        text=text,
        pros="Мягкая ткань",
        cons="",
        answerText=None,
        isAnswered=False,
        rating=5,
        syncedAt=datetime(2026, 7, 17, tzinfo=timezone.utc),
        sourceStatus="fresh",
    )


def test_openai_review_reply_requires_api_key():
    with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
        generate_openai_review_reply(
            feedback=_feedback(),
            brand_voice_id="wb-default",
            rating=5,
            template_text="Спасибо за отзыв о Футболка с принтом.",
            moderation=ReviewModerationDecision(state="clean", reasons=["No blockers"]),
            system_prompt="Отвечай на отзывы WB.",
            api_key=None,
        )


def test_openai_review_reply_parses_structured_response():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/responses"
        payload = request.read().decode("utf-8")
        assert "gpt-test" in payload
        return httpx.Response(
            200,
            json={
                "id": "resp_123",
                "output": [
                    {
                        "type": "message",
                        "content": [
                            {
                                "type": "output_text",
                                "text": '{"replyText":"Спасибо! Рады, что футболка понравилась.","riskLevel":"low","requiresApproval":false,"reasons":["positive review"],"matchedStopTopics":[]}',
                            }
                        ],
                    }
                ],
            },
        )

    client = httpx.Client(transport=httpx.MockTransport(handler), base_url="https://api.openai.com")

    result = generate_openai_review_reply(
        feedback=_feedback(),
        brand_voice_id="wb-default",
        rating=5,
        template_text="fallback",
        moderation=ReviewModerationDecision(state="clean", reasons=["No blockers"]),
        system_prompt="Отвечай на отзывы WB.",
        api_key="test-key",
        model="gpt-test",
        client=client,
    )

    assert result.generationSource == "openai"
    assert result.model == "gpt-test"
    assert result.replyText == "Спасибо! Рады, что футболка понравилась."
    assert result.riskLevel == "low"
    assert result.requiresApproval is False


def test_openai_review_reply_batch_parses_structured_response():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/responses"
        payload = request.read().decode("utf-8")
        assert '"items"' in payload
        assert "safe-review-001" in payload
        return httpx.Response(
            200,
            json={
                "id": "resp_batch_123",
                "output_text": (
                    '{"replies":[{"feedbackId":"safe-review-001","replyText":"Спасибо за отзыв!",'
                    '"riskLevel":"low","requiresApproval":false,"reasons":["positive"],"matchedStopTopics":[]}]}'
                ),
            },
        )

    client = httpx.Client(transport=httpx.MockTransport(handler), base_url="https://api.openai.com")
    feedback = _feedback()
    result = generate_openai_review_replies_batch(
        items=[
            {
                "feedback": feedback,
                "brand_voice_id": "wb-default",
                "rating": 5,
                "template_text": "fallback",
                "moderation": ReviewModerationDecision(state="clean", reasons=["No blockers"]),
            }
        ],
        system_prompt="Отвечай на отзывы WB.",
        api_key="test-key",
        model="gpt-test",
        client=client,
    )

    assert result[feedback.feedbackId].replyText == "Спасибо за отзыв!"
    assert result[feedback.feedbackId].model == "gpt-test"
