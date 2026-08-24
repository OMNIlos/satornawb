from app.reviews.schemas import ReviewDraftBatchGenerateItem, ReviewDraftGenerateRequest
from app.reviews.service import _merge_prompt_instruction


def test_review_draft_requests_accept_prompt_instruction():
    single = ReviewDraftGenerateRequest(
        feedbackId="feedback-1",
        brandVoiceId="wb-default",
        promptInstruction="Вариант промпта: отзыв 5* с текстом",
    )
    batch = ReviewDraftBatchGenerateItem(
        feedbackId="feedback-1",
        brandVoiceId="wb-default",
        promptInstruction="Вариант промпта: отзыв 5* с текстом",
    )

    assert single.promptInstruction == "Вариант промпта: отзыв 5* с текстом"
    assert batch.promptInstruction == "Вариант промпта: отзыв 5* с текстом"


def test_prompt_instruction_is_prepended_to_backend_template():
    merged = _merge_prompt_instruction(
        "Спасибо за отзыв о товаре.",
        "Вариант промпта: отзыв 5* с текстом\nИнструкция: поблагодарить за выбор бренда",
    )

    assert merged.startswith("Вариант промпта: отзыв 5* с текстом")
    assert "Backend template:" in merged
    assert "Спасибо за отзыв о товаре." in merged
