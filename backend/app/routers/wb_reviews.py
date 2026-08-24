from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request

from app.contracts.envelopes import DataEnvelope, PaginatedEnvelope
from app.control_plane.auth import actor_from_request
from app.control_plane.store import assert_permission_or_audit
from app.cabinet.store import get_user_wb_token_secret
from app.reviews.schemas import (
    ReviewApproveRequest,
    ReviewDraftBatchGenerateRequest,
    ReviewDraftBatchGenerateResponse,
    ReviewDraftGenerateRequest,
    ReviewDraftView,
    ReviewFeedbackSyncRequest,
    ReviewFeedbackSyncResponse,
    ReviewFeedbackView,
    ReviewModerationRuleCreateRequest,
    ReviewModerationRuleView,
    ReviewPromptTraceView,
    ReviewRejectRequest,
    ReviewSendJobView,
    ReviewSendRequest,
    ReviewSyncSettingsUpdateRequest,
    ReviewSyncSettingsView,
    ReviewSyncStatusView,
    ReviewSettingsBundle,
    ReviewStopTopicCreateRequest,
    ReviewStopTopicView,
    ReviewTemplateCreateRequest,
    ReviewTemplateView,
)
from app.reviews.service import (
    approve_draft,
    create_rule,
    create_stop_topic,
    create_template,
    generate_draft,
    generate_drafts_batch,
    get_draft,
    get_feedback,
    get_prompt_trace,
    get_review_approval,
    get_send_job,
    get_sync_settings,
    get_sync_status,
    get_settings_bundle,
    list_feedbacks,
    reject_draft,
    request_send,
    sync_feedbacks,
    update_sync_settings,
    update_rule,
    update_stop_topic,
    update_template,
)
from vella_wb_19_05 import AiReviewApproval


router = APIRouter(tags=["wb-reviews"])


@router.get("/api/v1/wb-reviews/{reviewId}/approval", response_model=AiReviewApproval)
def get_review_approval_endpoint(reviewId: str, rating: int = Query(ge=1, le=5)) -> AiReviewApproval:
    return AiReviewApproval.model_validate(get_review_approval(reviewId, rating))


@router.get("/api/v1/wb-reviews/settings", response_model=DataEnvelope[ReviewSettingsBundle])
def get_review_settings_endpoint(request: Request) -> DataEnvelope[ReviewSettingsBundle]:
    actor = actor_from_request(request)
    assert_permission_or_audit(
        actor=actor,
        permission="reviews:read",
        action="reviews.settings.get",
        object_type="review_settings",
        object_id="bundle",
        reason="actor cannot read review settings",
    )
    return DataEnvelope(data=get_settings_bundle())


@router.get("/api/v1/wb-reviews/sync-settings", response_model=DataEnvelope[ReviewSyncSettingsView])
def get_review_sync_settings_endpoint(request: Request) -> DataEnvelope[ReviewSyncSettingsView]:
    actor = actor_from_request(request)
    assert_permission_or_audit(
        actor=actor,
        permission="reviews:read",
        action="reviews.sync_settings.get",
        object_type="review_sync_settings",
        object_id=str(actor.organization_id),
        reason="actor cannot read review sync settings",
    )
    return DataEnvelope(data=get_sync_settings(actor.organization_id, actor.actor_id))


@router.put("/api/v1/wb-reviews/sync-settings", response_model=DataEnvelope[ReviewSyncSettingsView])
def update_review_sync_settings_endpoint(request: Request, payload: ReviewSyncSettingsUpdateRequest) -> DataEnvelope[ReviewSyncSettingsView]:
    actor = actor_from_request(request)
    assert_permission_or_audit(
        actor=actor,
        permission="reviews:write",
        action="reviews.sync_settings.update",
        object_type="review_sync_settings",
        object_id=str(actor.organization_id),
        reason="actor cannot update review sync settings",
    )
    return DataEnvelope(data=update_sync_settings(actor, payload))


@router.get("/api/v1/wb-reviews/sync-status", response_model=DataEnvelope[ReviewSyncStatusView])
def get_review_sync_status_endpoint(request: Request) -> DataEnvelope[ReviewSyncStatusView]:
    actor = actor_from_request(request)
    assert_permission_or_audit(
        actor=actor,
        permission="reviews:read",
        action="reviews.sync_status.get",
        object_type="review_sync_status",
        object_id=str(actor.organization_id),
        reason="actor cannot read review sync status",
    )
    return DataEnvelope(data=get_sync_status(actor.organization_id, actor.actor_id))


@router.post("/api/v1/wb-reviews/templates", response_model=DataEnvelope[ReviewTemplateView])
def create_review_template_endpoint(request: Request, payload: ReviewTemplateCreateRequest) -> DataEnvelope[ReviewTemplateView]:
    actor = actor_from_request(request)
    assert_permission_or_audit(
        actor=actor,
        permission="reviews:write",
        action="reviews.template.create",
        object_type="review_template",
        object_id="new",
        reason="actor cannot create review templates",
    )
    return DataEnvelope(data=create_template(actor, payload))


@router.put("/api/v1/wb-reviews/templates/{templateId}", response_model=DataEnvelope[ReviewTemplateView])
def update_review_template_endpoint(
    request: Request,
    templateId: str,
    payload: ReviewTemplateCreateRequest,
) -> DataEnvelope[ReviewTemplateView]:
    actor = actor_from_request(request)
    assert_permission_or_audit(
        actor=actor,
        permission="reviews:write",
        action="reviews.template.update",
        object_type="review_template",
        object_id=templateId,
        reason="actor cannot update review templates",
    )
    return DataEnvelope(data=update_template(actor, templateId, payload))


@router.post("/api/v1/wb-reviews/stop-topics", response_model=DataEnvelope[ReviewStopTopicView])
def create_review_stop_topic_endpoint(request: Request, payload: ReviewStopTopicCreateRequest) -> DataEnvelope[ReviewStopTopicView]:
    actor = actor_from_request(request)
    assert_permission_or_audit(
        actor=actor,
        permission="reviews:write",
        action="reviews.stop_topic.create",
        object_type="review_stop_topic",
        object_id="new",
        reason="actor cannot create review stop topics",
    )
    return DataEnvelope(data=create_stop_topic(actor, payload))


@router.put("/api/v1/wb-reviews/stop-topics/{stopTopicId}", response_model=DataEnvelope[ReviewStopTopicView])
def update_review_stop_topic_endpoint(
    request: Request,
    stopTopicId: int,
    payload: ReviewStopTopicCreateRequest,
) -> DataEnvelope[ReviewStopTopicView]:
    actor = actor_from_request(request)
    assert_permission_or_audit(
        actor=actor,
        permission="reviews:write",
        action="reviews.stop_topic.update",
        object_type="review_stop_topic",
        object_id=str(stopTopicId),
        reason="actor cannot update review stop topics",
    )
    return DataEnvelope(data=update_stop_topic(actor, stopTopicId, payload))


@router.post("/api/v1/wb-reviews/moderation-rules", response_model=DataEnvelope[ReviewModerationRuleView])
def create_review_rule_endpoint(request: Request, payload: ReviewModerationRuleCreateRequest) -> DataEnvelope[ReviewModerationRuleView]:
    actor = actor_from_request(request)
    assert_permission_or_audit(
        actor=actor,
        permission="reviews:write",
        action="reviews.rule.create",
        object_type="review_rule",
        object_id="new",
        reason="actor cannot create review rules",
    )
    return DataEnvelope(data=create_rule(actor, payload))


@router.put("/api/v1/wb-reviews/moderation-rules/{ruleId}", response_model=DataEnvelope[ReviewModerationRuleView])
def update_review_rule_endpoint(
    request: Request,
    ruleId: int,
    payload: ReviewModerationRuleCreateRequest,
) -> DataEnvelope[ReviewModerationRuleView]:
    actor = actor_from_request(request)
    assert_permission_or_audit(
        actor=actor,
        permission="reviews:write",
        action="reviews.rule.update",
        object_type="review_rule",
        object_id=str(ruleId),
        reason="actor cannot update review rules",
    )
    return DataEnvelope(data=update_rule(actor, ruleId, payload))


@router.post("/api/v1/wb-reviews/sync", response_model=DataEnvelope[ReviewFeedbackSyncResponse])
def sync_review_feedbacks_endpoint(request: Request, payload: ReviewFeedbackSyncRequest) -> DataEnvelope[ReviewFeedbackSyncResponse]:
    actor = actor_from_request(request)
    assert_permission_or_audit(
        actor=actor,
        permission="reviews:write",
        action="reviews.feedbacks.sync",
        object_type="review_feedback_sync",
        object_id=payload.scenario,
        reason="actor cannot sync review feedbacks",
    )
    wb_token = (get_user_wb_token_secret(actor.user_id) or "").strip()
    if not wb_token:
        raise HTTPException(status_code=409, detail="WB_TOKEN_REQUIRED")
    return DataEnvelope(data=sync_feedbacks(actor, payload, wb_token=wb_token))


@router.get("/api/v1/wb-reviews/feedbacks", response_model=PaginatedEnvelope[ReviewFeedbackView])
def list_review_feedbacks_endpoint(
    request: Request,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    isAnswered: bool | None = None,
    nmId: int | None = Query(default=None, ge=1),
) -> PaginatedEnvelope[ReviewFeedbackView]:
    actor = actor_from_request(request)
    assert_permission_or_audit(
        actor=actor,
        permission="reviews:read",
        action="reviews.feedbacks.list",
        object_type="review_feedback",
        object_id="*",
        reason="actor cannot read review feedbacks",
    )
    items, total = list_feedbacks(is_answered=isAnswered, nm_id=nmId, limit=limit, offset=offset)
    return PaginatedEnvelope(items=items, total=total, limit=limit, offset=offset)


@router.get("/api/v1/wb-reviews/feedbacks/{feedbackId}", response_model=DataEnvelope[ReviewFeedbackView])
def get_review_feedback_endpoint(request: Request, feedbackId: str) -> DataEnvelope[ReviewFeedbackView]:
    actor = actor_from_request(request)
    assert_permission_or_audit(
        actor=actor,
        permission="reviews:read",
        action="reviews.feedbacks.get",
        object_type="review_feedback",
        object_id=feedbackId,
        reason="actor cannot read review feedback",
    )
    return DataEnvelope(data=get_feedback(feedbackId))


@router.post("/api/v1/wb-reviews/drafts/generate", response_model=DataEnvelope[ReviewDraftView])
def generate_review_draft_endpoint(request: Request, payload: ReviewDraftGenerateRequest) -> DataEnvelope[ReviewDraftView]:
    actor = actor_from_request(request)
    assert_permission_or_audit(
        actor=actor,
        permission="reviews:write",
        action="reviews.draft.generate",
        object_type="review_draft",
        object_id=payload.feedbackId,
        reason="actor cannot generate review drafts",
    )
    return DataEnvelope(data=generate_draft(actor, payload))


@router.post("/api/v1/wb-reviews/drafts/generate-batch", response_model=DataEnvelope[ReviewDraftBatchGenerateResponse])
def generate_review_drafts_batch_endpoint(request: Request, payload: ReviewDraftBatchGenerateRequest) -> DataEnvelope[ReviewDraftBatchGenerateResponse]:
    actor = actor_from_request(request)
    assert_permission_or_audit(
        actor=actor,
        permission="reviews:write",
        action="reviews.draft.generate_batch",
        object_type="review_draft",
        object_id=f"batch:{len(payload.items)}",
        reason="actor cannot generate review drafts",
    )
    return DataEnvelope(data=generate_drafts_batch(actor, payload))


@router.get("/api/v1/wb-reviews/drafts/{draftId}", response_model=DataEnvelope[ReviewDraftView])
def get_review_draft_endpoint(request: Request, draftId: str) -> DataEnvelope[ReviewDraftView]:
    actor = actor_from_request(request)
    assert_permission_or_audit(
        actor=actor,
        permission="reviews:read",
        action="reviews.draft.get",
        object_type="review_draft",
        object_id=draftId,
        reason="actor cannot read review drafts",
    )
    return DataEnvelope(data=get_draft(draftId))


@router.get("/api/v1/wb-reviews/drafts/{draftId}/prompt-trace", response_model=DataEnvelope[ReviewPromptTraceView])
def get_review_prompt_trace_endpoint(request: Request, draftId: str) -> DataEnvelope[ReviewPromptTraceView]:
    actor = actor_from_request(request)
    assert_permission_or_audit(
        actor=actor,
        permission="reviews:read",
        action="reviews.prompt_trace.get",
        object_type="review_prompt_trace",
        object_id=draftId,
        reason="actor cannot read prompt trace",
    )
    return DataEnvelope(data=get_prompt_trace(draftId))


@router.post("/api/v1/wb-reviews/drafts/{draftId}/approve", response_model=DataEnvelope[ReviewDraftView])
def approve_review_draft_endpoint(request: Request, draftId: str, payload: ReviewApproveRequest) -> DataEnvelope[ReviewDraftView]:
    actor = actor_from_request(request)
    assert_permission_or_audit(
        actor=actor,
        permission="reviews:approve",
        action="reviews.draft.approve",
        object_type="review_draft",
        object_id=draftId,
        reason="actor cannot approve review drafts",
    )
    return DataEnvelope(data=approve_draft(actor, draftId, payload))


@router.post("/api/v1/wb-reviews/drafts/{draftId}/reject", response_model=DataEnvelope[ReviewDraftView])
def reject_review_draft_endpoint(request: Request, draftId: str, payload: ReviewRejectRequest) -> DataEnvelope[ReviewDraftView]:
    actor = actor_from_request(request)
    assert_permission_or_audit(
        actor=actor,
        permission="reviews:approve",
        action="reviews.draft.reject",
        object_type="review_draft",
        object_id=draftId,
        reason="actor cannot reject review drafts",
    )
    return DataEnvelope(data=reject_draft(actor, draftId, payload))


@router.post("/api/v1/wb-reviews/drafts/{draftId}/send", response_model=DataEnvelope[ReviewSendJobView])
def send_review_draft_endpoint(request: Request, draftId: str, payload: ReviewSendRequest) -> DataEnvelope[ReviewSendJobView]:
    actor = actor_from_request(request)
    assert_permission_or_audit(
        actor=actor,
        permission="reviews:send",
        action="reviews.send.request",
        object_type="review_send_job",
        object_id=draftId,
        reason="actor cannot send review replies",
    )
    return DataEnvelope(data=request_send(actor, draftId, payload))


@router.get("/api/v1/wb-reviews/send-jobs/{sendJobId}", response_model=DataEnvelope[ReviewSendJobView])
def get_review_send_job_endpoint(request: Request, sendJobId: str) -> DataEnvelope[ReviewSendJobView]:
    actor = actor_from_request(request)
    assert_permission_or_audit(
        actor=actor,
        permission="reviews:read",
        action="reviews.send_job.get",
        object_type="review_send_job",
        object_id=sendJobId,
        reason="actor cannot read review send jobs",
    )
    return DataEnvelope(data=get_send_job(sendJobId))
