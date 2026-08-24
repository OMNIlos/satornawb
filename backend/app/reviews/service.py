from __future__ import annotations

import secrets
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from string import Formatter
from typing import Any, Iterable

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.config import get_settings
from app.control_plane.auth import ActorContext
from app.control_plane.store import record_audit_event
from app.infra.db import get_engine, get_session_factory
from app.reviews.orm import (
    ReviewDraftRow,
    ReviewFeedbackRow,
    ReviewModerationRuleRow,
    ReviewPromptTraceRow,
    ReviewSendJobRow,
    ReviewStopTopicRow,
    ReviewSyncRunRow,
    ReviewSyncSettingsRow,
    ReviewTemplateRow,
)
from app.reviews.openai_client import generate_openai_review_replies_batch, generate_openai_review_reply
from app.reviews.schemas import (
    DraftModerationState,
    ReviewApproveRequest,
    ReviewAutomationSettings,
    ReviewDraftBatchError,
    ReviewDraftBatchGenerateRequest,
    ReviewDraftBatchGenerateResponse,
    ReviewCacheMetrics,
    ReviewFeedbackDraftSummary,
    ReviewDraftGenerateRequest,
    ReviewDraftView,
    ReviewFeedbackSyncRequest,
    ReviewFeedbackSyncResponse,
    ReviewFeedbackView,
    ReviewModerationDecision,
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
from app.wb_api.feedbacks_runtime import WbFeedbackRow, WbFeedbacksFetchError, fetch_feedback_by_id, fetch_feedbacks


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _run_db(db_fn):
    try:
        engine = get_engine()
        with engine.connect() as connection:
            connection.exec_driver_sql("SELECT 1")
        session_factory = get_session_factory()
        with session_factory() as session:
            return db_fn(session)
    except SQLAlchemyError:
        return None


def _new_id(prefix: str) -> str:
    return f"{prefix}-{secrets.token_hex(8)}"


def _normalize_text(value: str | None) -> str:
    return (value or "").strip()


def _keyword_match(text: str, keywords: Iterable[str], mode: str) -> bool:
    phrases = [keyword.strip().lower() for keyword in keywords if keyword.strip()]
    if not phrases:
        return True
    haystack = text.lower()
    if mode == "all":
        return all(keyword in haystack for keyword in phrases)
    return any(keyword in haystack for keyword in phrases)


ALLOWED_TEMPLATE_FIELDS = {
    "brandName",
    "productName",
    "text",
    "pros",
    "cons",
    "rating",
    "feedbackId",
}


def _validate_template_fields(body_template: str) -> None:
    placeholders = {
        field_name
        for _literal, field_name, _format_spec, _conversion in Formatter().parse(body_template)
        if field_name
    }
    invalid = sorted(placeholders - ALLOWED_TEMPLATE_FIELDS)
    if invalid:
        raise HTTPException(status_code=400, detail=f"UNKNOWN_TEMPLATE_FIELDS:{','.join(invalid)}")


@dataclass
class _MemoryReviewState:
    templates: dict[str, ReviewTemplateView] = field(default_factory=dict)
    stop_topics: dict[int, ReviewStopTopicView] = field(default_factory=dict)
    moderation_rules: dict[int, ReviewModerationRuleView] = field(default_factory=dict)
    feedbacks: dict[str, ReviewFeedbackView] = field(default_factory=dict)
    drafts: dict[str, ReviewDraftView] = field(default_factory=dict)
    send_jobs: dict[str, ReviewSendJobView] = field(default_factory=dict)
    prompt_traces: dict[str, ReviewPromptTraceView] = field(default_factory=dict)
    sync_settings: dict[int, ReviewSyncSettingsView] = field(default_factory=dict)
    sync_runs: dict[int, ReviewSyncStatusView] = field(default_factory=dict)
    next_stop_topic_id: int = 1
    next_rule_id: int = 1


_MEMORY = _MemoryReviewState()


def _seed_templates() -> list[ReviewTemplateCreateRequest]:
    return [
        ReviewTemplateCreateRequest(
            brandVoiceId="wb-default",
            title="Positive 5-star",
            bodyTemplate="Спасибо за отзыв о {productName}. Очень рады, что вам понравилось.",
            ratingFrom=5,
            ratingTo=5,
            keywords=[],
            keywordMode="any",
            isActive=True,
        ),
        ReviewTemplateCreateRequest(
            brandVoiceId="wb-default",
            title="Neutral 4-star",
            bodyTemplate="Спасибо, что поделились впечатлением о {productName}. Учтем ваш отзыв и будем становиться лучше.",
            ratingFrom=4,
            ratingTo=4,
            keywords=[],
            keywordMode="any",
            isActive=True,
        ),
        ReviewTemplateCreateRequest(
            brandVoiceId="wb-default",
            title="Recovery low rating",
            bodyTemplate="Спасибо за обратную связь по {productName}. Нам жаль, что опыт оказался неидеальным. Мы уже передали замечание в команду.",
            ratingFrom=1,
            ratingTo=3,
            keywords=[],
            keywordMode="any",
            isActive=True,
        ),
    ]


def _seed_stop_topics() -> list[ReviewStopTopicCreateRequest]:
    return [
        ReviewStopTopicCreateRequest(
            brandVoiceId=None,
            phrase="компенсац",
            matchType="contains",
            action="manual_review",
            isActive=True,
        ),
        ReviewStopTopicCreateRequest(
            brandVoiceId=None,
            phrase="суд",
            matchType="contains",
            action="block_send",
            isActive=True,
        ),
    ]


def _seed_rules() -> list[ReviewModerationRuleCreateRequest]:
    return [
        ReviewModerationRuleCreateRequest(
            brandVoiceId=None,
            name="Low rating requires approval",
            conditionType="low_rating",
            action="manual_review",
            thresholdInt=3,
            keywords=[],
            isActive=True,
        ),
        ReviewModerationRuleCreateRequest(
            brandVoiceId=None,
            name="Already answered blocks send",
            conditionType="already_answered",
            action="block_send",
            thresholdInt=None,
            keywords=[],
            isActive=True,
        ),
        ReviewModerationRuleCreateRequest(
            brandVoiceId=None,
            name="Empty text needs manual review",
            conditionType="empty_text",
            action="manual_review",
            thresholdInt=None,
            keywords=[],
            isActive=True,
        ),
    ]


def _to_template_view(row: ReviewTemplateRow) -> ReviewTemplateView:
    return ReviewTemplateView(
        templateId=row.template_id,
        brandVoiceId=row.brand_voice_id,
        title=row.title,
        bodyTemplate=row.body_template,
        ratingFrom=row.rating_from,
        ratingTo=row.rating_to,
        keywords=list(row.keywords or []),
        keywordMode=row.keyword_mode,  # type: ignore[arg-type]
        isActive=row.is_active,
        createdByActorId=row.created_by_actor_id,
        createdAt=_as_utc(row.created_at),
        updatedAt=_as_utc(row.updated_at),
    )


def _to_stop_topic_view(row: ReviewStopTopicRow) -> ReviewStopTopicView:
    return ReviewStopTopicView(
        stopTopicId=row.stop_topic_id,
        brandVoiceId=row.brand_voice_id,
        phrase=row.phrase,
        matchType=row.match_type,  # type: ignore[arg-type]
        action=row.action,  # type: ignore[arg-type]
        isActive=row.is_active,
        createdByActorId=row.created_by_actor_id,
        createdAt=_as_utc(row.created_at),
        updatedAt=_as_utc(row.updated_at),
    )


def _to_rule_view(row: ReviewModerationRuleRow) -> ReviewModerationRuleView:
    return ReviewModerationRuleView(
        ruleId=row.rule_id,
        brandVoiceId=row.brand_voice_id,
        name=row.name,
        conditionType=row.condition_type,  # type: ignore[arg-type]
        action=row.action,  # type: ignore[arg-type]
        thresholdInt=row.threshold_int,
        keywords=list(row.keywords or []),
        isActive=row.is_active,
        createdByActorId=row.created_by_actor_id,
        createdAt=_as_utc(row.created_at),
        updatedAt=_as_utc(row.updated_at),
    )


def _to_feedback_draft_summary(row: ReviewDraftRow) -> ReviewFeedbackDraftSummary:
    return ReviewFeedbackDraftSummary(
        draftId=row.draft_id,
        rating=row.rating,
        brandVoiceId=row.brand_voice_id,
        templateId=row.template_id,
        approvalState=row.approval_state,  # type: ignore[arg-type]
        sendState=row.send_state,  # type: ignore[arg-type]
        generatedText=row.generated_text,
        moderationState=row.moderation_state,  # type: ignore[arg-type]
        moderationReasons=row.moderation_reasons,
        updatedAt=_as_utc(row.updated_at),
    )


def _to_feedback_view(row: ReviewFeedbackRow, latest_draft: ReviewDraftRow | None = None) -> ReviewFeedbackView:
    return ReviewFeedbackView(
        feedbackId=row.feedback_id,
        nmId=row.nm_id,
        imtId=row.imt_id,
        brandName=row.brand_name,
        productName=row.product_name,
        createdDate=_as_utc(row.created_date),
        text=row.text,
        pros=row.pros,
        cons=row.cons,
        answerText=row.answer_text,
        isAnswered=row.is_answered,
        rating=row.rating,
        syncedAt=_as_utc(row.synced_at),
        sourceStatus="fresh",
        latestDraft=_to_feedback_draft_summary(latest_draft) if latest_draft is not None else None,
    )


def _to_moderation_decision(row: ReviewDraftRow) -> ReviewModerationDecision:
    return ReviewModerationDecision(
        state=row.moderation_state,  # type: ignore[arg-type]
        reasons=list(row.moderation_reasons or []),
        matchedStopTopicIds=list(row.matched_stop_topic_ids or []),
        matchedRuleIds=list(row.matched_rule_ids or []),
    )


def _to_draft_view(row: ReviewDraftRow) -> ReviewDraftView:
    return ReviewDraftView(
        draftId=row.draft_id,
        feedbackId=row.feedback_id,
        rating=row.rating,
        brandVoiceId=row.brand_voice_id,
        templateId=row.template_id,
        approvalState=row.approval_state,  # type: ignore[arg-type]
        approvalActorId=row.approval_actor_id,
        approvedAt=_as_utc(row.approved_at) if row.approved_at else None,
        externalSendAllowed=row.external_send_allowed,
        sendState=row.send_state,  # type: ignore[arg-type]
        generatedText=row.generated_text,
        moderation=_to_moderation_decision(row),
        promptTraceId=row.prompt_trace_id,
        cacheMetrics=ReviewCacheMetrics.model_validate(row.cache_metrics) if row.cache_metrics else None,
        createdByActorId=row.created_by_actor_id,
        createdAt=_as_utc(row.created_at),
        updatedAt=_as_utc(row.updated_at),
    )


def _to_send_job_view(row: ReviewSendJobRow) -> ReviewSendJobView:
    return ReviewSendJobView(
        sendJobId=row.send_job_id,
        draftId=row.draft_id,
        feedbackId=row.feedback_id,
        status=row.status,  # type: ignore[arg-type]
        answerText=row.answer_text,
        externalRequestPath=row.external_request_path,
        resultMessage=row.result_message,
        requestedByActorId=row.requested_by_actor_id,
        requestedAt=_as_utc(row.requested_at),
        completedAt=_as_utc(row.completed_at) if row.completed_at else None,
    )


def _to_prompt_trace_view(row: ReviewPromptTraceRow) -> ReviewPromptTraceView:
    return ReviewPromptTraceView(
        draftId=row.draft_id,
        promptTraceId=row.prompt_trace_id,
        stablePrefixKeys=list(row.stable_prefix_keys or []),
        volatileSuffixKeys=list(row.volatile_suffix_keys or []),
        cacheMetrics=ReviewCacheMetrics.model_validate(row.cache_metrics) if row.cache_metrics else None,
        metadata=row.metadata_payload or {},
        createdAt=_as_utc(row.created_at),
    )


def _min_sync_interval_minutes(token_type: str) -> int:
    return 12 if token_type == "base" else 1


def _normalize_sync_settings_payload(payload: ReviewSyncSettingsUpdateRequest) -> ReviewSyncSettingsUpdateRequest:
    min_interval = _min_sync_interval_minutes(payload.tokenType)
    updates: dict[str, Any] = {
        "aiPrompt": payload.aiPrompt.strip(),
        "reviewSettings": ReviewAutomationSettings.model_validate(payload.reviewSettings.model_dump(mode="json")),
    }
    if payload.intervalMinutes < min_interval:
        updates["intervalMinutes"] = min_interval
    return payload.model_copy(update=updates)


def _default_sync_settings(organization_id: int, actor_id: str | None = None) -> ReviewSyncSettingsView:
    now = _utc_now()
    payload = ReviewSyncSettingsUpdateRequest()
    return ReviewSyncSettingsView(
        organizationId=organization_id,
        enabled=payload.enabled,
        intervalMinutes=payload.intervalMinutes,
        tokenType=payload.tokenType,
        unansweredOnly=payload.unansweredOnly,
        take=payload.take,
        lookbackDays=payload.lookbackDays,
        aiPrompt=payload.aiPrompt,
        reviewSettings=payload.reviewSettings,
        updatedByActorId=actor_id,
        createdAt=now,
        updatedAt=now,
        minIntervalMinutes=_min_sync_interval_minutes(payload.tokenType),
    )


def _to_sync_settings_view(row: ReviewSyncSettingsRow) -> ReviewSyncSettingsView:
    return ReviewSyncSettingsView(
        organizationId=row.organization_id,
        enabled=row.enabled,
        intervalMinutes=row.interval_minutes,
        tokenType=row.token_type,  # type: ignore[arg-type]
        unansweredOnly=row.unanswered_only,
        take=row.take,
        lookbackDays=row.lookback_days,
        aiPrompt=row.ai_prompt,
        reviewSettings=ReviewAutomationSettings.model_validate(row.settings_payload or {}),
        updatedByActorId=row.updated_by_actor_id,
        createdAt=_as_utc(row.created_at),
        updatedAt=_as_utc(row.updated_at),
        minIntervalMinutes=_min_sync_interval_minutes(row.token_type),
    )


def _to_sync_status_view(settings: ReviewSyncSettingsView, row: ReviewSyncRunRow | None = None) -> ReviewSyncStatusView:
    if row is None:
        last_completed_at = None
        status = "idle"
        synced_count = 0
        source_status = None
        error = None
        last_run_at = None
    else:
        last_completed_at = _as_utc(row.completed_at) if row.completed_at else None
        status = row.status
        synced_count = row.synced_count
        source_status = row.source_status
        error = row.error_message
        last_run_at = _as_utc(row.started_at)
    anchor = last_completed_at or settings.updatedAt
    next_run_at = anchor + timedelta(minutes=settings.intervalMinutes) if settings.enabled else None
    return ReviewSyncStatusView(
        organizationId=settings.organizationId,
        status=status,  # type: ignore[arg-type]
        enabled=settings.enabled,
        intervalMinutes=settings.intervalMinutes,
        nextRunAt=next_run_at,
        lastRunAt=last_run_at,
        lastCompletedAt=last_completed_at,
        lastSyncedCount=synced_count,
        lastSourceStatus=source_status,  # type: ignore[arg-type]
        lastError=error,
    )


def _feedback_from_runtime(row: WbFeedbackRow, source_status: str = "fresh") -> ReviewFeedbackView:
    return ReviewFeedbackView(
        feedbackId=row.feedback_id,
        nmId=row.nm_id,
        imtId=row.imt_id,
        brandName=row.brand_name or "Unknown",
        productName=row.product_name or "Unknown",
        createdDate=_as_utc(row.created_date),
        text=row.text,
        pros=row.pros,
        cons=row.cons,
        answerText=row.answer_text,
        isAnswered=row.is_answered,
        rating=row.rating,
        syncedAt=_utc_now(),
        sourceStatus=source_status,  # type: ignore[arg-type]
    )


def _with_memory_latest_draft(feedback: ReviewFeedbackView) -> ReviewFeedbackView:
    latest = max(
        (draft for draft in _MEMORY.drafts.values() if draft.feedbackId == feedback.feedbackId),
        key=lambda draft: draft.updatedAt,
        default=None,
    )
    if latest is None:
        return feedback
    return feedback.model_copy(
        update={
            "latestDraft": ReviewFeedbackDraftSummary(
                draftId=latest.draftId,
                rating=latest.rating,
                brandVoiceId=latest.brandVoiceId,
                templateId=latest.templateId,
                approvalState=latest.approvalState,
                sendState=latest.sendState,
                generatedText=latest.generatedText,
                moderationState=latest.moderation.state,
                moderationReasons=latest.moderation.reasons,
                updatedAt=latest.updatedAt,
            )
        }
    )


def _store_feedback(session: Session, view: ReviewFeedbackView, raw_payload: dict[str, Any] | None = None) -> ReviewFeedbackView:
    row = session.get(ReviewFeedbackRow, view.feedbackId)
    if row is None:
        row = ReviewFeedbackRow(
            feedback_id=view.feedbackId,
            nm_id=view.nmId,
            imt_id=view.imtId,
            brand_name=view.brandName,
            product_name=view.productName,
            created_date=view.createdDate,
            text=view.text,
            pros=view.pros,
            cons=view.cons,
            answer_text=view.answerText,
            is_answered=view.isAnswered,
            rating=view.rating,
            raw_payload=raw_payload or {},
            synced_at=view.syncedAt,
        )
        session.add(row)
    else:
        row.nm_id = view.nmId
        row.imt_id = view.imtId
        row.brand_name = view.brandName
        row.product_name = view.productName
        row.created_date = view.createdDate
        row.text = view.text
        row.pros = view.pros
        row.cons = view.cons
        row.answer_text = view.answerText
        row.is_answered = view.isAnswered
        row.rating = view.rating
        row.raw_payload = raw_payload or row.raw_payload
        row.synced_at = view.syncedAt
    session.flush()
    return _to_feedback_view(row)


def _ensure_default_settings_memory() -> None:
    if _MEMORY.templates and _MEMORY.stop_topics and _MEMORY.moderation_rules:
        return
    actor_id = "system-seed"
    now = _utc_now()
    for seed in _seed_templates():
        template_id = f"tpl-{len(_MEMORY.templates) + 1}"
        _MEMORY.templates[template_id] = ReviewTemplateView(
            templateId=template_id,
            brandVoiceId=seed.brandVoiceId,
            title=seed.title,
            bodyTemplate=seed.bodyTemplate,
            ratingFrom=seed.ratingFrom,
            ratingTo=seed.ratingTo,
            keywords=seed.keywords,
            keywordMode=seed.keywordMode,
            isActive=seed.isActive,
            createdByActorId=actor_id,
            createdAt=now,
            updatedAt=now,
        )
    for seed in _seed_stop_topics():
        stop_topic_id = _MEMORY.next_stop_topic_id
        _MEMORY.next_stop_topic_id += 1
        _MEMORY.stop_topics[stop_topic_id] = ReviewStopTopicView(
            stopTopicId=stop_topic_id,
            brandVoiceId=seed.brandVoiceId,
            phrase=seed.phrase,
            matchType=seed.matchType,
            action=seed.action,
            isActive=seed.isActive,
            createdByActorId=actor_id,
            createdAt=now,
            updatedAt=now,
        )
    for seed in _seed_rules():
        rule_id = _MEMORY.next_rule_id
        _MEMORY.next_rule_id += 1
        _MEMORY.moderation_rules[rule_id] = ReviewModerationRuleView(
            ruleId=rule_id,
            brandVoiceId=seed.brandVoiceId,
            name=seed.name,
            conditionType=seed.conditionType,
            action=seed.action,
            thresholdInt=seed.thresholdInt,
            keywords=seed.keywords,
            isActive=seed.isActive,
            createdByActorId=actor_id,
            createdAt=now,
            updatedAt=now,
        )


def _ensure_default_settings_db(session: Session) -> None:
    if session.scalar(select(ReviewTemplateRow.template_id).limit(1)) is not None:
        return
    actor_id = "system-seed"
    for index, seed in enumerate(_seed_templates(), start=1):
        session.add(
            ReviewTemplateRow(
                template_id=f"tpl-{index}",
                brand_voice_id=seed.brandVoiceId,
                title=seed.title,
                body_template=seed.bodyTemplate,
                rating_from=seed.ratingFrom,
                rating_to=seed.ratingTo,
                keywords=seed.keywords,
                keyword_mode=seed.keywordMode,
                is_active=seed.isActive,
                created_by_actor_id=actor_id,
            )
        )
    for seed in _seed_stop_topics():
        session.add(
            ReviewStopTopicRow(
                brand_voice_id=seed.brandVoiceId,
                phrase=seed.phrase,
                match_type=seed.matchType,
                action=seed.action,
                is_active=seed.isActive,
                created_by_actor_id=actor_id,
            )
        )
    for seed in _seed_rules():
        session.add(
            ReviewModerationRuleRow(
                brand_voice_id=seed.brandVoiceId,
                name=seed.name,
                condition_type=seed.conditionType,
                action=seed.action,
                threshold_int=seed.thresholdInt,
                keywords=seed.keywords,
                is_active=seed.isActive,
                created_by_actor_id=actor_id,
            )
        )
    session.commit()


def ensure_review_defaults() -> None:
    def _db(session: Session) -> bool:
        _ensure_default_settings_db(session)
        return True

    result = _run_db(_db)
    if result is not None:
        return
    _ensure_default_settings_memory()


def get_settings_bundle() -> ReviewSettingsBundle:
    ensure_review_defaults()

    def _db(session: Session) -> ReviewSettingsBundle:
        templates = session.scalars(select(ReviewTemplateRow).order_by(ReviewTemplateRow.template_id)).all()
        stop_topics = session.scalars(select(ReviewStopTopicRow).order_by(ReviewStopTopicRow.stop_topic_id)).all()
        rules = session.scalars(select(ReviewModerationRuleRow).order_by(ReviewModerationRuleRow.rule_id)).all()
        return ReviewSettingsBundle(
            templates=[_to_template_view(row) for row in templates],
            stopTopics=[_to_stop_topic_view(row) for row in stop_topics],
            moderationRules=[_to_rule_view(row) for row in rules],
        )

    result = _run_db(_db)
    if result is not None:
        return result

    return ReviewSettingsBundle(
        templates=sorted(_MEMORY.templates.values(), key=lambda row: row.templateId),
        stopTopics=sorted(_MEMORY.stop_topics.values(), key=lambda row: row.stopTopicId),
        moderationRules=sorted(_MEMORY.moderation_rules.values(), key=lambda row: row.ruleId),
    )


def get_sync_settings(organization_id: int, actor_id: str | None = None) -> ReviewSyncSettingsView:
    def _db(session: Session) -> ReviewSyncSettingsView:
        row = session.get(ReviewSyncSettingsRow, organization_id)
        if row is None:
            defaults = _default_sync_settings(organization_id, actor_id)
            row = ReviewSyncSettingsRow(
                organization_id=organization_id,
                enabled=defaults.enabled,
                interval_minutes=defaults.intervalMinutes,
                token_type=defaults.tokenType,
                unanswered_only=defaults.unansweredOnly,
                take=defaults.take,
                lookback_days=defaults.lookbackDays,
                ai_prompt=defaults.aiPrompt,
                settings_payload=defaults.reviewSettings.model_dump(mode="json"),
                updated_by_actor_id=actor_id,
            )
            session.add(row)
            session.commit()
            session.refresh(row)
        return _to_sync_settings_view(row)

    result = _run_db(_db)
    if result is not None:
        return result

    if organization_id not in _MEMORY.sync_settings:
        _MEMORY.sync_settings[organization_id] = _default_sync_settings(organization_id, actor_id)
    return _MEMORY.sync_settings[organization_id]


def update_sync_settings(actor: ActorContext, payload: ReviewSyncSettingsUpdateRequest) -> ReviewSyncSettingsView:
    normalized = _normalize_sync_settings_payload(payload)
    organization_id = actor.organization_id

    def _db(session: Session) -> ReviewSyncSettingsView:
        row = session.get(ReviewSyncSettingsRow, organization_id)
        if row is None:
            row = ReviewSyncSettingsRow(organization_id=organization_id)
            session.add(row)
        before = _to_sync_settings_view(row).model_dump(mode="json") if row.created_at else None
        row.enabled = normalized.enabled
        row.interval_minutes = normalized.intervalMinutes
        row.token_type = normalized.tokenType
        row.unanswered_only = normalized.unansweredOnly
        row.take = normalized.take
        row.lookback_days = normalized.lookbackDays
        row.ai_prompt = normalized.aiPrompt
        row.settings_payload = normalized.reviewSettings.model_dump(mode="json")
        row.updated_by_actor_id = actor.actor_id
        session.commit()
        session.refresh(row)
        view = _to_sync_settings_view(row)
        record_audit_event(
            actor=actor,
            action="reviews.sync_settings.update",
            object_type="review_sync_settings",
            object_id=str(organization_id),
            before_state=before,
            after_state=view.model_dump(mode="json"),
            reason="review sync settings updated",
            approval_ref=None,
            evidence_refs=["WB-16", "feedbacks-api-limits"],
        )
        return view

    result = _run_db(_db)
    if result is not None:
        return result

    current = _MEMORY.sync_settings.get(organization_id) or _default_sync_settings(organization_id, actor.actor_id)
    now = _utc_now()
    updated = ReviewSyncSettingsView(
        organizationId=organization_id,
        enabled=normalized.enabled,
        intervalMinutes=normalized.intervalMinutes,
        tokenType=normalized.tokenType,
        unansweredOnly=normalized.unansweredOnly,
        take=normalized.take,
        lookbackDays=normalized.lookbackDays,
        aiPrompt=normalized.aiPrompt,
        reviewSettings=normalized.reviewSettings,
        updatedByActorId=actor.actor_id,
        createdAt=current.createdAt,
        updatedAt=now,
        minIntervalMinutes=_min_sync_interval_minutes(normalized.tokenType),
    )
    _MEMORY.sync_settings[organization_id] = updated
    record_audit_event(
        actor=actor,
        action="reviews.sync_settings.update",
        object_type="review_sync_settings",
        object_id=str(organization_id),
        before_state=current.model_dump(mode="json"),
        after_state=updated.model_dump(mode="json"),
        reason="review sync settings updated",
        approval_ref=None,
        evidence_refs=["memory_fallback", "feedbacks-api-limits"],
    )
    return updated


def get_sync_status(organization_id: int, actor_id: str | None = None) -> ReviewSyncStatusView:
    settings = get_sync_settings(organization_id, actor_id)

    def _db(session: Session) -> ReviewSyncStatusView:
        row = session.scalar(
            select(ReviewSyncRunRow)
            .where(ReviewSyncRunRow.organization_id == organization_id)
            .order_by(ReviewSyncRunRow.started_at.desc())
        )
        return _to_sync_status_view(settings, row)

    result = _run_db(_db)
    if result is not None:
        return result

    return _MEMORY.sync_runs.get(organization_id) or _to_sync_status_view(settings)


def create_template(actor: ActorContext, payload: ReviewTemplateCreateRequest) -> ReviewTemplateView:
    ensure_review_defaults()
    _validate_template_fields(payload.bodyTemplate)

    def _db(session: Session) -> ReviewTemplateView:
        template_id = _new_id("tpl")
        row = ReviewTemplateRow(
            template_id=template_id,
            brand_voice_id=payload.brandVoiceId,
            title=payload.title,
            body_template=payload.bodyTemplate,
            rating_from=payload.ratingFrom,
            rating_to=payload.ratingTo,
            keywords=payload.keywords,
            keyword_mode=payload.keywordMode,
            is_active=payload.isActive,
            created_by_actor_id=actor.actor_id,
        )
        session.add(row)
        session.commit()
        session.refresh(row)
        return _to_template_view(row)

    result = _run_db(_db)
    if result is not None:
        record_audit_event(
            actor=actor,
            action="reviews.template.create",
            object_type="review_template",
            object_id=result.templateId,
            before_state=None,
            after_state=result.model_dump(mode="json"),
            reason="review template created",
            approval_ref=None,
            evidence_refs=["WB-16"],
        )
        return result

    now = _utc_now()
    view = ReviewTemplateView(
        templateId=_new_id("tpl"),
        brandVoiceId=payload.brandVoiceId,
        title=payload.title,
        bodyTemplate=payload.bodyTemplate,
        ratingFrom=payload.ratingFrom,
        ratingTo=payload.ratingTo,
        keywords=payload.keywords,
        keywordMode=payload.keywordMode,
        isActive=payload.isActive,
        createdByActorId=actor.actor_id,
        createdAt=now,
        updatedAt=now,
    )
    _MEMORY.templates[view.templateId] = view
    record_audit_event(
        actor=actor,
        action="reviews.template.create",
        object_type="review_template",
        object_id=view.templateId,
        before_state=None,
        after_state=view.model_dump(mode="json"),
        reason="review template created",
        approval_ref=None,
        evidence_refs=["memory_fallback", "WB-16"],
    )
    return view


def update_template(actor: ActorContext, template_id: str, payload: ReviewTemplateCreateRequest) -> ReviewTemplateView:
    ensure_review_defaults()
    _validate_template_fields(payload.bodyTemplate)

    def _db(session: Session) -> ReviewTemplateView:
        row = session.get(ReviewTemplateRow, template_id)
        if row is None:
            raise HTTPException(status_code=404, detail="REVIEW_TEMPLATE_NOT_FOUND")
        before = _to_template_view(row)
        row.brand_voice_id = payload.brandVoiceId
        row.title = payload.title
        row.body_template = payload.bodyTemplate
        row.rating_from = payload.ratingFrom
        row.rating_to = payload.ratingTo
        row.keywords = payload.keywords
        row.keyword_mode = payload.keywordMode
        row.is_active = payload.isActive
        session.commit()
        session.refresh(row)
        view = _to_template_view(row)
        record_audit_event(
            actor=actor,
            action="reviews.template.update",
            object_type="review_template",
            object_id=template_id,
            before_state=before.model_dump(mode="json"),
            after_state=view.model_dump(mode="json"),
            reason="review template updated",
            approval_ref=None,
            evidence_refs=["WB-16"],
        )
        return view

    result = _run_db(_db)
    if result is not None:
        return result

    current = _MEMORY.templates.get(template_id)
    if current is None:
        raise HTTPException(status_code=404, detail="REVIEW_TEMPLATE_NOT_FOUND")
    updated = current.model_copy(
        update={
            "brandVoiceId": payload.brandVoiceId,
            "title": payload.title,
            "bodyTemplate": payload.bodyTemplate,
            "ratingFrom": payload.ratingFrom,
            "ratingTo": payload.ratingTo,
            "keywords": payload.keywords,
            "keywordMode": payload.keywordMode,
            "isActive": payload.isActive,
            "updatedAt": _utc_now(),
        }
    )
    _MEMORY.templates[template_id] = updated
    record_audit_event(
        actor=actor,
        action="reviews.template.update",
        object_type="review_template",
        object_id=template_id,
        before_state=current.model_dump(mode="json"),
        after_state=updated.model_dump(mode="json"),
        reason="review template updated",
        approval_ref=None,
        evidence_refs=["memory_fallback", "WB-16"],
    )
    return updated


def create_stop_topic(actor: ActorContext, payload: ReviewStopTopicCreateRequest) -> ReviewStopTopicView:
    ensure_review_defaults()

    def _db(session: Session) -> ReviewStopTopicView:
        row = ReviewStopTopicRow(
            brand_voice_id=payload.brandVoiceId,
            phrase=payload.phrase,
            match_type=payload.matchType,
            action=payload.action,
            is_active=payload.isActive,
            created_by_actor_id=actor.actor_id,
        )
        session.add(row)
        session.commit()
        session.refresh(row)
        return _to_stop_topic_view(row)

    result = _run_db(_db)
    if result is not None:
        record_audit_event(
            actor=actor,
            action="reviews.stop_topic.create",
            object_type="review_stop_topic",
            object_id=str(result.stopTopicId),
            before_state=None,
            after_state=result.model_dump(mode="json"),
            reason="review stop topic created",
            approval_ref=None,
            evidence_refs=["WB-16"],
        )
        return result

    stop_topic_id = _MEMORY.next_stop_topic_id
    _MEMORY.next_stop_topic_id += 1
    now = _utc_now()
    view = ReviewStopTopicView(
        stopTopicId=stop_topic_id,
        brandVoiceId=payload.brandVoiceId,
        phrase=payload.phrase,
        matchType=payload.matchType,
        action=payload.action,
        isActive=payload.isActive,
        createdByActorId=actor.actor_id,
        createdAt=now,
        updatedAt=now,
    )
    _MEMORY.stop_topics[stop_topic_id] = view
    record_audit_event(
        actor=actor,
        action="reviews.stop_topic.create",
        object_type="review_stop_topic",
        object_id=str(view.stopTopicId),
        before_state=None,
        after_state=view.model_dump(mode="json"),
        reason="review stop topic created",
        approval_ref=None,
        evidence_refs=["memory_fallback", "WB-16"],
    )
    return view


def update_stop_topic(actor: ActorContext, stop_topic_id: int, payload: ReviewStopTopicCreateRequest) -> ReviewStopTopicView:
    ensure_review_defaults()

    def _db(session: Session) -> ReviewStopTopicView:
        row = session.get(ReviewStopTopicRow, stop_topic_id)
        if row is None:
            raise HTTPException(status_code=404, detail="REVIEW_STOP_TOPIC_NOT_FOUND")
        before = _to_stop_topic_view(row)
        row.brand_voice_id = payload.brandVoiceId
        row.phrase = payload.phrase
        row.match_type = payload.matchType
        row.action = payload.action
        row.is_active = payload.isActive
        session.commit()
        session.refresh(row)
        view = _to_stop_topic_view(row)
        record_audit_event(
            actor=actor,
            action="reviews.stop_topic.update",
            object_type="review_stop_topic",
            object_id=str(stop_topic_id),
            before_state=before.model_dump(mode="json"),
            after_state=view.model_dump(mode="json"),
            reason="review stop topic updated",
            approval_ref=None,
            evidence_refs=["WB-16"],
        )
        return view

    result = _run_db(_db)
    if result is not None:
        return result

    current = _MEMORY.stop_topics.get(stop_topic_id)
    if current is None:
        raise HTTPException(status_code=404, detail="REVIEW_STOP_TOPIC_NOT_FOUND")
    updated = current.model_copy(
        update={
            "brandVoiceId": payload.brandVoiceId,
            "phrase": payload.phrase,
            "matchType": payload.matchType,
            "action": payload.action,
            "isActive": payload.isActive,
            "updatedAt": _utc_now(),
        }
    )
    _MEMORY.stop_topics[stop_topic_id] = updated
    record_audit_event(
        actor=actor,
        action="reviews.stop_topic.update",
        object_type="review_stop_topic",
        object_id=str(stop_topic_id),
        before_state=current.model_dump(mode="json"),
        after_state=updated.model_dump(mode="json"),
        reason="review stop topic updated",
        approval_ref=None,
        evidence_refs=["memory_fallback", "WB-16"],
    )
    return updated


def create_rule(actor: ActorContext, payload: ReviewModerationRuleCreateRequest) -> ReviewModerationRuleView:
    ensure_review_defaults()

    def _db(session: Session) -> ReviewModerationRuleView:
        row = ReviewModerationRuleRow(
            brand_voice_id=payload.brandVoiceId,
            name=payload.name,
            condition_type=payload.conditionType,
            action=payload.action,
            threshold_int=payload.thresholdInt,
            keywords=payload.keywords,
            is_active=payload.isActive,
            created_by_actor_id=actor.actor_id,
        )
        session.add(row)
        session.commit()
        session.refresh(row)
        return _to_rule_view(row)

    result = _run_db(_db)
    if result is not None:
        record_audit_event(
            actor=actor,
            action="reviews.rule.create",
            object_type="review_rule",
            object_id=str(result.ruleId),
            before_state=None,
            after_state=result.model_dump(mode="json"),
            reason="review moderation rule created",
            approval_ref=None,
            evidence_refs=["WB-16"],
        )
        return result

    rule_id = _MEMORY.next_rule_id
    _MEMORY.next_rule_id += 1
    now = _utc_now()
    view = ReviewModerationRuleView(
        ruleId=rule_id,
        brandVoiceId=payload.brandVoiceId,
        name=payload.name,
        conditionType=payload.conditionType,
        action=payload.action,
        thresholdInt=payload.thresholdInt,
        keywords=payload.keywords,
        isActive=payload.isActive,
        createdByActorId=actor.actor_id,
        createdAt=now,
        updatedAt=now,
    )
    _MEMORY.moderation_rules[rule_id] = view
    record_audit_event(
        actor=actor,
        action="reviews.rule.create",
        object_type="review_rule",
        object_id=str(view.ruleId),
        before_state=None,
        after_state=view.model_dump(mode="json"),
        reason="review moderation rule created",
        approval_ref=None,
        evidence_refs=["memory_fallback", "WB-16"],
    )
    return view


def update_rule(actor: ActorContext, rule_id: int, payload: ReviewModerationRuleCreateRequest) -> ReviewModerationRuleView:
    ensure_review_defaults()

    def _db(session: Session) -> ReviewModerationRuleView:
        row = session.get(ReviewModerationRuleRow, rule_id)
        if row is None:
            raise HTTPException(status_code=404, detail="REVIEW_RULE_NOT_FOUND")
        before = _to_rule_view(row)
        row.brand_voice_id = payload.brandVoiceId
        row.name = payload.name
        row.condition_type = payload.conditionType
        row.action = payload.action
        row.threshold_int = payload.thresholdInt
        row.keywords = payload.keywords
        row.is_active = payload.isActive
        session.commit()
        session.refresh(row)
        view = _to_rule_view(row)
        record_audit_event(
            actor=actor,
            action="reviews.rule.update",
            object_type="review_rule",
            object_id=str(rule_id),
            before_state=before.model_dump(mode="json"),
            after_state=view.model_dump(mode="json"),
            reason="review moderation rule updated",
            approval_ref=None,
            evidence_refs=["WB-16"],
        )
        return view

    result = _run_db(_db)
    if result is not None:
        return result

    current = _MEMORY.moderation_rules.get(rule_id)
    if current is None:
        raise HTTPException(status_code=404, detail="REVIEW_RULE_NOT_FOUND")
    updated = current.model_copy(
        update={
            "brandVoiceId": payload.brandVoiceId,
            "name": payload.name,
            "conditionType": payload.conditionType,
            "action": payload.action,
            "thresholdInt": payload.thresholdInt,
            "keywords": payload.keywords,
            "isActive": payload.isActive,
            "updatedAt": _utc_now(),
        }
    )
    _MEMORY.moderation_rules[rule_id] = updated
    record_audit_event(
        actor=actor,
        action="reviews.rule.update",
        object_type="review_rule",
        object_id=str(rule_id),
        before_state=current.model_dump(mode="json"),
        after_state=updated.model_dump(mode="json"),
        reason="review moderation rule updated",
        approval_ref=None,
        evidence_refs=["memory_fallback", "WB-16"],
    )
    return updated


def _select_templates(brand_voice_id: str) -> list[ReviewTemplateView]:
    bundle = get_settings_bundle()
    rows = [
        row
        for row in bundle.templates
        if row.isActive and row.brandVoiceId == brand_voice_id
    ]
    if rows:
        return rows
    return [row for row in bundle.templates if row.isActive and row.brandVoiceId == "wb-default"]


def _select_stop_topics(brand_voice_id: str) -> list[ReviewStopTopicView]:
    bundle = get_settings_bundle()
    return [
        row
        for row in bundle.stopTopics
        if row.isActive and (row.brandVoiceId is None or row.brandVoiceId == brand_voice_id)
    ]


def _select_rules(brand_voice_id: str) -> list[ReviewModerationRuleView]:
    bundle = get_settings_bundle()
    return [
        row
        for row in bundle.moderationRules
        if row.isActive and (row.brandVoiceId is None or row.brandVoiceId == brand_voice_id)
    ]


def _find_feedback(feedback_id: str, scenario: str = "complete") -> ReviewFeedbackView:
    def _db(session: Session) -> ReviewFeedbackView | None:
        row = session.get(ReviewFeedbackRow, feedback_id)
        if row is None:
            return None
        latest_draft = session.scalar(
            select(ReviewDraftRow)
            .where(ReviewDraftRow.feedback_id == feedback_id)
            .order_by(ReviewDraftRow.updated_at.desc())
        )
        return _to_feedback_view(row, latest_draft)

    result = _run_db(_db)
    if result is not None:
        return result

    memory_value = _MEMORY.feedbacks.get(feedback_id)
    if memory_value is not None:
        return _with_memory_latest_draft(memory_value)

    runtime_row = fetch_feedback_by_id(feedback_id=feedback_id, scenario=scenario)
    if runtime_row is None:
        raise HTTPException(status_code=404, detail="REVIEW_FEEDBACK_NOT_FOUND")
    view = _feedback_from_runtime(runtime_row)
    _MEMORY.feedbacks[view.feedbackId] = view
    return view


def sync_feedbacks(actor: ActorContext, payload: ReviewFeedbackSyncRequest, wb_token: str | None = None) -> ReviewFeedbackSyncResponse:
    ensure_review_defaults()
    organization_id = actor.organization_id
    sync_run_id = _new_id("review-sync")
    started_at = _utc_now()
    token_override = wb_token if get_settings().wb_api_mode == "real" else None
    try:
        fetch_kwargs = {
            "scenario": payload.scenario,
            "wb_token": token_override,
            "nm_id": payload.nmId,
            "take": payload.take,
            "skip": payload.skip,
            "order": payload.order,
            "date_from_epoch": payload.dateFrom,
            "date_to_epoch": payload.dateTo,
        }
        if payload.isAnswered is None:
            rows = [
                *fetch_feedbacks(is_answered=False, **fetch_kwargs),
                *fetch_feedbacks(is_answered=True, **fetch_kwargs),
            ]
        else:
            rows = fetch_feedbacks(is_answered=payload.isAnswered, **fetch_kwargs)
    except WbFeedbacksFetchError as exc:
        now = _utc_now()

        def _db_failed(session: Session) -> bool:
            session.add(
                ReviewSyncRunRow(
                    sync_run_id=sync_run_id,
                    organization_id=organization_id,
                    trigger="manual",
                    status="failed",
                    scenario=payload.scenario,
                    synced_count=0,
                    source_status="blocked",
                    next_skip=payload.skip,
                    error_message=f"{exc.code}: {exc.message}",
                    started_at=started_at,
                    completed_at=now,
                )
            )
            session.commit()
            return True

        if _run_db(_db_failed) is None:
            settings = get_sync_settings(organization_id, actor.actor_id)
            _MEMORY.sync_runs[organization_id] = ReviewSyncStatusView(
                organizationId=organization_id,
                status="failed",
                enabled=settings.enabled,
                intervalMinutes=settings.intervalMinutes,
                nextRunAt=now + timedelta(minutes=settings.intervalMinutes),
                lastRunAt=started_at,
                lastCompletedAt=now,
                lastSyncedCount=0,
                lastSourceStatus="blocked",
                lastError=f"{exc.code}: {exc.message}",
            )
        raise HTTPException(status_code=502, detail=f"WB_FEEDBACKS_SYNC_FAILED:{exc.code}:{exc.message}") from exc
    now = _utc_now()
    source_status = "fresh" if rows or payload.scenario == "complete" else "blocked"

    def _db(session: Session) -> ReviewFeedbackSyncResponse:
        count = 0
        for row in rows:
            view = _feedback_from_runtime(row, source_status=source_status)
            _store_feedback(session, view, raw_payload=row.raw_payload)
            count += 1
        session.add(
            ReviewSyncRunRow(
                sync_run_id=sync_run_id,
                organization_id=organization_id,
                trigger="manual",
                status="completed",
                scenario=payload.scenario,
                synced_count=count,
                source_status=source_status,
                next_skip=payload.skip + count,
                error_message=None,
                started_at=started_at,
                completed_at=now,
            )
        )
        session.commit()
        return ReviewFeedbackSyncResponse(
            syncedCount=count,
            sourceStatus=source_status,  # type: ignore[arg-type]
            nextSkip=payload.skip + count,
            syncedAt=now,
        )

    result = _run_db(_db)
    if result is not None:
        record_audit_event(
            actor=actor,
            action="reviews.feedbacks.sync",
            object_type="review_feedback_sync",
            object_id=str(result.nextSkip),
            before_state=None,
            after_state=result.model_dump(mode="json"),
            reason="feedbacks synced from WB feedbacks API",
            approval_ref=None,
            evidence_refs=["WB-16", "feedbacks-api"],
        )
        return result

    for row in rows:
        view = _feedback_from_runtime(row, source_status=source_status)
        _MEMORY.feedbacks[view.feedbackId] = view
    response = ReviewFeedbackSyncResponse(
        syncedCount=len(rows),
        sourceStatus=source_status,  # type: ignore[arg-type]
        nextSkip=payload.skip + len(rows),
        syncedAt=now,
    )
    settings = get_sync_settings(organization_id, actor.actor_id)
    _MEMORY.sync_runs[organization_id] = ReviewSyncStatusView(
        organizationId=organization_id,
        status="completed",
        enabled=settings.enabled,
        intervalMinutes=settings.intervalMinutes,
        nextRunAt=now + timedelta(minutes=settings.intervalMinutes),
        lastRunAt=started_at,
        lastCompletedAt=now,
        lastSyncedCount=len(rows),
        lastSourceStatus=source_status,  # type: ignore[arg-type]
        lastError=None,
    )
    record_audit_event(
        actor=actor,
        action="reviews.feedbacks.sync",
        object_type="review_feedback_sync",
        object_id=str(response.nextSkip),
        before_state=None,
        after_state=response.model_dump(mode="json"),
        reason="feedbacks synced from WB feedbacks API",
        approval_ref=None,
        evidence_refs=["memory_fallback", "feedbacks-api"],
    )
    return response


def list_feedbacks(
    *,
    is_answered: bool | None = None,
    nm_id: int | None = None,
    limit: int = 100,
    offset: int = 0,
) -> tuple[list[ReviewFeedbackView], int]:
    ensure_review_defaults()

    def apply_filters(items: list[ReviewFeedbackView]) -> list[ReviewFeedbackView]:
        rows = items
        if is_answered is not None:
            rows = [row for row in rows if row.isAnswered == is_answered]
        if nm_id is not None:
            rows = [row for row in rows if row.nmId == nm_id]
        rows.sort(key=lambda row: row.createdDate, reverse=True)
        return rows

    def _db(session: Session) -> tuple[list[ReviewFeedbackView], int]:
        draft_by_feedback_id: dict[str, ReviewDraftRow] = {}
        for draft in session.scalars(select(ReviewDraftRow).order_by(ReviewDraftRow.updated_at.desc())).all():
            draft_by_feedback_id.setdefault(draft.feedback_id, draft)
        rows = [
            _to_feedback_view(row, draft_by_feedback_id.get(row.feedback_id))
            for row in session.scalars(select(ReviewFeedbackRow)).all()
        ]
        filtered = apply_filters(rows)
        return filtered[offset : offset + limit], len(filtered)

    result = _run_db(_db)
    if result is not None:
        return result

    filtered = apply_filters([_with_memory_latest_draft(row) for row in _MEMORY.feedbacks.values()])
    return filtered[offset : offset + limit], len(filtered)


def get_feedback(feedback_id: str) -> ReviewFeedbackView:
    return _find_feedback(feedback_id)


def _pick_template(feedback: ReviewFeedbackView, brand_voice_id: str, rating: int) -> ReviewTemplateView | None:
    candidates = _select_templates(brand_voice_id)
    combined = " ".join(part for part in [feedback.text, feedback.pros, feedback.cons, feedback.productName, feedback.brandName] if part).lower()
    ranked: list[tuple[int, ReviewTemplateView]] = []
    for row in candidates:
        if rating < row.ratingFrom or rating > row.ratingTo:
            continue
        if not _keyword_match(combined, row.keywords, row.keywordMode):
            continue
        score = len(row.keywords) + (1 if row.brandVoiceId == brand_voice_id else 0)
        ranked.append((score, row))
    if not ranked:
        return None
    ranked.sort(key=lambda item: item[0], reverse=True)
    return ranked[0][1]


def _render_template(template: ReviewTemplateView | None, feedback: ReviewFeedbackView, rating: int) -> str:
    if template is None:
        if rating < 4:
            return f"Спасибо за обратную связь по {feedback.productName}. Нам жаль, что опыт оказался неидеальным."
        return f"Спасибо за отзыв о {feedback.productName}. Очень ценим вашу обратную связь."
    return template.bodyTemplate.format(
        brandName=feedback.brandName,
        productName=feedback.productName,
        text=feedback.text,
        pros=feedback.pros,
        cons=feedback.cons,
        rating=rating,
        feedbackId=feedback.feedbackId,
    ).strip()


def _merge_prompt_instruction(template_text: str, prompt_instruction: str | None) -> str:
    prompt = (prompt_instruction or "").strip()
    if not prompt:
        return template_text
    return f"{prompt}\n\nBackend template:\n{template_text}"


def _match_stop_topics(feedback: ReviewFeedbackView, brand_voice_id: str) -> list[ReviewStopTopicView]:
    haystack = " ".join(part for part in [feedback.text, feedback.pros, feedback.cons] if part).lower()
    matches: list[ReviewStopTopicView] = []
    for row in _select_stop_topics(brand_voice_id):
        phrase = row.phrase.lower()
        if row.matchType == "exact":
            if haystack == phrase:
                matches.append(row)
        elif phrase in haystack:
            matches.append(row)
    return matches


def _moderate_feedback(
    feedback: ReviewFeedbackView,
    *,
    brand_voice_id: str,
    rating: int,
) -> ReviewModerationDecision:
    matched_stop_topics = _match_stop_topics(feedback, brand_voice_id)
    matched_stop_topic_ids = [row.stopTopicId for row in matched_stop_topics]
    matched_rule_ids: list[int] = []
    reasons: list[str] = []
    state: DraftModerationState = "clean"

    def escalate(new_state: DraftModerationState, reason: str) -> None:
        nonlocal state
        priority = {"clean": 0, "manual_review": 1, "blocked": 2}
        if priority[new_state] > priority[state]:
            state = new_state
        if reason not in reasons:
            reasons.append(reason)

    if matched_stop_topics:
        for topic in matched_stop_topics:
            if topic.action == "block_send":
                escalate("blocked", f"Stop topic matched: {topic.phrase}")
            else:
                escalate("manual_review", f"Stop topic matched: {topic.phrase}")

    combined = " ".join(part for part in [feedback.text, feedback.pros, feedback.cons] if part).lower()
    for rule in _select_rules(brand_voice_id):
        matched = False
        reason = rule.name
        if rule.conditionType == "low_rating":
            threshold = rule.thresholdInt or 3
            matched = rating <= threshold
            reason = f"Rating {rating} requires review"
        elif rule.conditionType == "already_answered":
            matched = feedback.isAnswered or bool(_normalize_text(feedback.answerText))
            reason = "Feedback already has seller answer"
        elif rule.conditionType == "contains_stop_topic":
            matched = bool(matched_stop_topics)
            reason = "Stop topic policy matched"
        elif rule.conditionType == "contains_keyword":
            matched = _keyword_match(combined, rule.keywords, "any")
            reason = f"Keyword rule matched: {rule.name}"
        elif rule.conditionType == "empty_text":
            matched = not combined.strip()
            reason = "Feedback text is empty"
        if not matched:
            continue
        matched_rule_ids.append(rule.ruleId)
        if rule.action == "block_send" or rule.action == "block_draft":
            escalate("blocked", reason)
        elif rule.action == "manual_review":
            escalate("manual_review", reason)

    if not reasons:
        reasons.append("No moderation blockers matched")

    return ReviewModerationDecision(
        state=state,
        reasons=reasons,
        matchedStopTopicIds=matched_stop_topic_ids,
        matchedRuleIds=matched_rule_ids,
    )


def _draft_state_from_moderation(
    moderation: ReviewModerationDecision,
    rating: int,
    review_settings: ReviewAutomationSettings | None = None,
) -> tuple[str, bool, str]:
    settings = review_settings or ReviewAutomationSettings()
    if settings.automationMode == "paused":
        return "required", False, "draft_only"
    if moderation.state == "blocked":
        return "required", False, "blocked"
    if rating <= 2 and settings.lowStarsAction == "alert-block":
        return "required", False, "blocked"
    if rating == 3 and settings.threeStarAction == "auto-low" and moderation.state == "clean":
        return "not_required", False, "draft_only"
    if moderation.state == "manual_review" or rating < 4:
        return "required", False, "draft_only"
    if settings.automationMode == "auto-safe":
        return "not_required", False, "ready_to_send"
    if settings.automationMode == "draft-first":
        return "required", False, "draft_only"
    return "not_required", False, "draft_only"


def _build_prompt_trace(
    draft_id: str,
    feedback: ReviewFeedbackView,
    brand_voice_id: str,
    template: ReviewTemplateView | None,
    request: ReviewDraftGenerateRequest,
) -> ReviewPromptTraceView:
    return ReviewPromptTraceView(
        draftId=draft_id,
        promptTraceId=request.promptTraceId or _new_id("prompt"),
        stablePrefixKeys=[
            f"brand_voice:{brand_voice_id}",
            f"template:{template.templateId if template else 'fallback'}",
            f"product:{feedback.nmId}",
        ],
        volatileSuffixKeys=[
            "feedback.text",
            "feedback.pros",
            "feedback.cons",
        ],
        cacheMetrics=request.cacheMetrics,
        metadata={
            "feedbackId": feedback.feedbackId,
            "brandName": feedback.brandName,
            "productName": feedback.productName,
            "promptInstruction": (request.promptInstruction or "").strip(),
        },
        createdAt=_utc_now(),
    )


def _save_generated_draft(
    actor: ActorContext,
    payload: ReviewDraftGenerateRequest,
    feedback: ReviewFeedbackView,
    rating: int,
    template: ReviewTemplateView | None,
    moderation: ReviewModerationDecision,
    generated_text: str,
    review_settings: ReviewAutomationSettings,
) -> ReviewDraftView:
    approval_state, external_send_allowed, send_state = _draft_state_from_moderation(moderation, rating, review_settings)
    draft_id = _new_id("draft")
    now = _utc_now()
    prompt_trace = _build_prompt_trace(draft_id, feedback, payload.brandVoiceId, template, payload)

    def _db(session: Session) -> ReviewDraftView:
        if payload.regenerate:
            existing = session.scalar(
                select(ReviewDraftRow)
                .where(ReviewDraftRow.feedback_id == feedback.feedbackId)
                .order_by(ReviewDraftRow.updated_at.desc())
            )
            if existing is not None:
                session.delete(existing)
                session.flush()
        row = ReviewDraftRow(
            draft_id=draft_id,
            feedback_id=feedback.feedbackId,
            rating=rating,
            brand_voice_id=payload.brandVoiceId,
            template_id=template.templateId if template else None,
            approval_state=approval_state,
            approval_actor_id=None,
            approved_at=None,
            external_send_allowed=external_send_allowed,
            send_state=send_state,
            generated_text=generated_text,
            moderation_state=moderation.state,
            moderation_reasons=moderation.reasons,
            matched_stop_topic_ids=moderation.matchedStopTopicIds,
            matched_rule_ids=moderation.matchedRuleIds,
            prompt_trace_id=prompt_trace.promptTraceId,
            cache_metrics=payload.cacheMetrics.model_dump(mode="json") if payload.cacheMetrics else None,
            created_by_actor_id=actor.actor_id,
            created_at=now,
            updated_at=now,
        )
        session.add(row)
        trace_row = ReviewPromptTraceRow(
            draft_id=draft_id,
            prompt_trace_id=prompt_trace.promptTraceId,
            stable_prefix_keys=prompt_trace.stablePrefixKeys,
            volatile_suffix_keys=prompt_trace.volatileSuffixKeys,
            cache_metrics=payload.cacheMetrics.model_dump(mode="json") if payload.cacheMetrics else None,
            metadata_payload=prompt_trace.metadata,
            created_at=prompt_trace.createdAt,
        )
        session.merge(trace_row)
        session.commit()
        session.refresh(row)
        return _to_draft_view(row)

    result = _run_db(_db)
    if result is not None:
        record_audit_event(
            actor=actor,
            action="reviews.draft.generate",
            object_type="review_draft",
            object_id=result.draftId,
            before_state=None,
            after_state=result.model_dump(mode="json"),
            reason="review draft generated",
            approval_ref=None,
            evidence_refs=["WB-16", "prompt-trace"],
        )
        return result

    if payload.regenerate:
        for existing_id, row in list(_MEMORY.drafts.items()):
            if row.feedbackId == feedback.feedbackId:
                _MEMORY.drafts.pop(existing_id, None)
                _MEMORY.prompt_traces.pop(existing_id, None)
    view = ReviewDraftView(
        draftId=draft_id,
        feedbackId=feedback.feedbackId,
        rating=rating,
        brandVoiceId=payload.brandVoiceId,
        templateId=template.templateId if template else None,
        approvalState=approval_state,  # type: ignore[arg-type]
        approvalActorId=None,
        approvedAt=None,
        externalSendAllowed=external_send_allowed,
        sendState=send_state,  # type: ignore[arg-type]
        generatedText=generated_text,
        moderation=moderation,
        promptTraceId=prompt_trace.promptTraceId,
        cacheMetrics=payload.cacheMetrics,
        createdByActorId=actor.actor_id,
        createdAt=now,
        updatedAt=now,
    )
    _MEMORY.drafts[draft_id] = view
    _MEMORY.prompt_traces[draft_id] = prompt_trace
    record_audit_event(
        actor=actor,
        action="reviews.draft.generate",
        object_type="review_draft",
        object_id=view.draftId,
        before_state=None,
        after_state=view.model_dump(mode="json"),
        reason="review draft generated",
        approval_ref=None,
        evidence_refs=["memory_fallback", "prompt-trace"],
    )
    return view


def generate_draft(actor: ActorContext, payload: ReviewDraftGenerateRequest) -> ReviewDraftView:
    ensure_review_defaults()
    feedback = _find_feedback(payload.feedbackId)
    sync_settings = get_sync_settings(actor.organization_id, actor.actor_id)
    ai_prompt = sync_settings.aiPrompt.strip()
    if not ai_prompt:
        raise HTTPException(status_code=409, detail="REVIEW_AI_PROMPT_REQUIRED")
    rating = payload.ratingOverride or feedback.rating or 5
    template = _pick_template(feedback, payload.brandVoiceId, rating)
    template_text = _merge_prompt_instruction(_render_template(template, feedback, rating), payload.promptInstruction)
    moderation = _moderate_feedback(feedback, brand_voice_id=payload.brandVoiceId, rating=rating)
    ai_result = generate_openai_review_reply(
        feedback=feedback,
        brand_voice_id=payload.brandVoiceId,
        rating=rating,
        template_text=template_text,
        moderation=moderation,
        system_prompt=(
            f"{ai_prompt}\n\n"
            "Настройки автоответов WB из интерфейса:\n"
            f"{sync_settings.reviewSettings.model_dump_json()}"
        ),
    )
    generated_text = ai_result.replyText
    if ai_result.requiresApproval and moderation.state == "clean":
        moderation = moderation.model_copy(
            update={
                "state": "manual_review",
                "reasons": list(dict.fromkeys([*moderation.reasons, *ai_result.reasons])),
            }
        )
    return _save_generated_draft(actor, payload, feedback, rating, template, moderation, generated_text, sync_settings.reviewSettings)


def generate_drafts_batch(actor: ActorContext, payload: ReviewDraftBatchGenerateRequest) -> ReviewDraftBatchGenerateResponse:
    ensure_review_defaults()
    sync_settings = get_sync_settings(actor.organization_id, actor.actor_id)
    ai_prompt = sync_settings.aiPrompt.strip()
    if not ai_prompt:
        raise HTTPException(status_code=409, detail="REVIEW_AI_PROMPT_REQUIRED")

    prepared: list[dict[str, Any]] = []
    errors: list[ReviewDraftBatchError] = []
    seen: set[str] = set()
    for item in payload.items:
        if item.feedbackId in seen:
            continue
        seen.add(item.feedbackId)
        try:
            feedback = _find_feedback(item.feedbackId)
            rating = item.ratingOverride or feedback.rating or 5
            request = ReviewDraftGenerateRequest(
                feedbackId=item.feedbackId,
                brandVoiceId=item.brandVoiceId,
                ratingOverride=item.ratingOverride,
                promptInstruction=item.promptInstruction,
                regenerate=payload.regenerate,
            )
            template = _pick_template(feedback, item.brandVoiceId, rating)
            template_text = _merge_prompt_instruction(_render_template(template, feedback, rating), item.promptInstruction)
            moderation = _moderate_feedback(feedback, brand_voice_id=item.brandVoiceId, rating=rating)
            prepared.append(
                {
                    "request": request,
                    "feedback": feedback,
                    "brand_voice_id": item.brandVoiceId,
                    "rating": rating,
                    "template": template,
                    "template_text": template_text,
                    "moderation": moderation,
                }
            )
        except Exception as exc:
            errors.append(ReviewDraftBatchError(feedbackId=item.feedbackId, message=str(exc)))

    drafts: list[ReviewDraftView] = []
    if prepared:
        ai_results = generate_openai_review_replies_batch(
            items=prepared,
            system_prompt=(
                f"{ai_prompt}\n\n"
                "Настройки автоответов WB из интерфейса:\n"
                f"{sync_settings.reviewSettings.model_dump_json()}\n\n"
                "Верните один элемент replies для каждого feedbackId из входного массива."
            ),
        )
        for item in prepared:
            feedback = item["feedback"]
            ai_result = ai_results.get(feedback.feedbackId)
            if ai_result is None:
                errors.append(ReviewDraftBatchError(feedbackId=feedback.feedbackId, message="OpenAI batch response missed feedbackId"))
                continue
            moderation: ReviewModerationDecision = item["moderation"]
            if ai_result.requiresApproval and moderation.state == "clean":
                moderation = moderation.model_copy(
                    update={
                        "state": "manual_review",
                        "reasons": list(dict.fromkeys([*moderation.reasons, *ai_result.reasons])),
                    }
                )
            try:
                drafts.append(
                    _save_generated_draft(
                        actor,
                        item["request"],
                        feedback,
                        item["rating"],
                        item["template"],
                        moderation,
                        ai_result.replyText,
                        sync_settings.reviewSettings,
                    )
                )
            except Exception as exc:
                errors.append(ReviewDraftBatchError(feedbackId=feedback.feedbackId, message=str(exc)))

    return ReviewDraftBatchGenerateResponse(
        requestedCount=len(payload.items),
        generatedCount=len(drafts),
        failedCount=len(errors),
        drafts=drafts,
        errors=errors,
    )


def get_draft(draft_id: str) -> ReviewDraftView:
    def _db(session: Session) -> ReviewDraftView | None:
        row = session.get(ReviewDraftRow, draft_id)
        return _to_draft_view(row) if row is not None else None

    result = _run_db(_db)
    if result is not None:
        return result

    view = _MEMORY.drafts.get(draft_id)
    if view is None:
        raise HTTPException(status_code=404, detail="REVIEW_DRAFT_NOT_FOUND")
    return view


def get_prompt_trace(draft_id: str) -> ReviewPromptTraceView:
    def _db(session: Session) -> ReviewPromptTraceView | None:
        row = session.get(ReviewPromptTraceRow, draft_id)
        return _to_prompt_trace_view(row) if row is not None else None

    result = _run_db(_db)
    if result is not None:
        return result

    view = _MEMORY.prompt_traces.get(draft_id)
    if view is None:
        raise HTTPException(status_code=404, detail="REVIEW_PROMPT_TRACE_NOT_FOUND")
    return view


def _set_draft_approval_fields(
    current: ReviewDraftView,
    *,
    approval_state: str,
    approval_actor_id: str | None,
    approved_at: datetime | None,
    external_send_allowed: bool,
    send_state: str,
) -> ReviewDraftView:
    return current.model_copy(
        update={
            "approvalState": approval_state,
            "approvalActorId": approval_actor_id,
            "approvedAt": approved_at,
            "externalSendAllowed": external_send_allowed,
            "sendState": send_state,
            "updatedAt": _utc_now(),
        }
    )


def approve_draft(actor: ActorContext, draft_id: str, payload: ReviewApproveRequest) -> ReviewDraftView:
    def _db(session: Session) -> ReviewDraftView:
        row = session.get(ReviewDraftRow, draft_id)
        if row is None:
            raise HTTPException(status_code=404, detail="REVIEW_DRAFT_NOT_FOUND")
        before = _to_draft_view(row)
        approved_at = _utc_now()
        row.approval_state = "approved"
        row.approval_actor_id = actor.actor_id
        row.approved_at = approved_at
        if row.send_state != "blocked":
            row.external_send_allowed = False
            row.send_state = "draft_only"
        session.commit()
        session.refresh(row)
        view = _to_draft_view(row)
        record_audit_event(
            actor=actor,
            action="reviews.draft.approve",
            object_type="review_draft",
            object_id=draft_id,
            before_state=before.model_dump(mode="json"),
            after_state=view.model_dump(mode="json"),
            reason=payload.reason or "review draft approved",
            approval_ref=payload.approvalRef,
            evidence_refs=["reviews:approve"],
        )
        return view

    result = _run_db(_db)
    if result is not None:
        return result

    current = get_draft(draft_id)
    updated = _set_draft_approval_fields(
        current,
        approval_state="approved",
        approval_actor_id=actor.actor_id,
        approved_at=_utc_now(),
        external_send_allowed=False,
        send_state="draft_only" if current.sendState != "blocked" else "blocked",
    )
    _MEMORY.drafts[draft_id] = updated
    record_audit_event(
        actor=actor,
        action="reviews.draft.approve",
        object_type="review_draft",
        object_id=draft_id,
        before_state=current.model_dump(mode="json"),
        after_state=updated.model_dump(mode="json"),
        reason=payload.reason or "review draft approved",
        approval_ref=payload.approvalRef,
        evidence_refs=["memory_fallback", "reviews:approve"],
    )
    return updated


def reject_draft(actor: ActorContext, draft_id: str, payload: ReviewRejectRequest) -> ReviewDraftView:
    def _db(session: Session) -> ReviewDraftView:
        row = session.get(ReviewDraftRow, draft_id)
        if row is None:
            raise HTTPException(status_code=404, detail="REVIEW_DRAFT_NOT_FOUND")
        before = _to_draft_view(row)
        row.approval_state = "rejected"
        row.approval_actor_id = actor.actor_id
        row.external_send_allowed = False
        row.send_state = "blocked"
        session.commit()
        session.refresh(row)
        view = _to_draft_view(row)
        record_audit_event(
            actor=actor,
            action="reviews.draft.reject",
            object_type="review_draft",
            object_id=draft_id,
            before_state=before.model_dump(mode="json"),
            after_state=view.model_dump(mode="json"),
            reason=payload.reason,
            approval_ref=None,
            evidence_refs=["reviews:approve"],
        )
        return view

    result = _run_db(_db)
    if result is not None:
        return result

    current = get_draft(draft_id)
    updated = _set_draft_approval_fields(
        current,
        approval_state="rejected",
        approval_actor_id=actor.actor_id,
        approved_at=None,
        external_send_allowed=False,
        send_state="blocked",
    )
    _MEMORY.drafts[draft_id] = updated
    record_audit_event(
        actor=actor,
        action="reviews.draft.reject",
        object_type="review_draft",
        object_id=draft_id,
        before_state=current.model_dump(mode="json"),
        after_state=updated.model_dump(mode="json"),
        reason=payload.reason,
        approval_ref=None,
        evidence_refs=["memory_fallback", "reviews:approve"],
    )
    return updated


def request_send(actor: ActorContext, draft_id: str, payload: ReviewSendRequest) -> ReviewSendJobView:
    draft = get_draft(draft_id)
    feedback = _find_feedback(draft.feedbackId)
    send_job_id = _new_id("send")
    now = _utc_now()

    status = "queued"
    result_message = "queued"
    external_request_path: str | None = None
    completed_at: datetime | None = None

    if get_settings().wb_feedbacks_send_enabled is False:
        status = "blocked"
        result_message = "Live WB feedback send is disabled; draft remains internal"
        completed_at = now
    elif draft.sendState == "blocked" or not draft.externalSendAllowed:
        status = "blocked"
        result_message = "External send blocked by moderation or approval gates"
        completed_at = now
    elif draft.approvalState == "required":
        status = "blocked"
        result_message = "Draft requires approval before send"
        completed_at = now
    elif draft.approvalState == "rejected":
        status = "blocked"
        result_message = "Rejected draft cannot be sent"
        completed_at = now
    else:
        status = "blocked"
        result_message = "WB feedback answer mutation path is not wired yet"
        completed_at = now

    def _db(session: Session) -> ReviewSendJobView:
        row = ReviewSendJobRow(
            send_job_id=send_job_id,
            draft_id=draft_id,
            feedback_id=feedback.feedbackId,
            status=status,
            answer_text=draft.generatedText,
            external_request_path=external_request_path,
            result_message=result_message,
            requested_by_actor_id=actor.actor_id,
            requested_at=now,
            completed_at=completed_at,
        )
        session.add(row)
        if status == "sent" and external_request_path == "dry-run":
            draft_row = session.get(ReviewDraftRow, draft_id)
            if draft_row is not None and not payload.dryRun:
                draft_row.send_state = "sent"
        session.commit()
        session.refresh(row)
        view = _to_send_job_view(row)
        record_audit_event(
            actor=actor,
            action="reviews.send.request",
            object_type="review_send_job",
            object_id=send_job_id,
            before_state=draft.model_dump(mode="json"),
            after_state=view.model_dump(mode="json"),
            reason=payload.reason or result_message,
            approval_ref=None,
            evidence_refs=["reviews:send", "feedbacks-api"],
        )
        return view

    result = _run_db(_db)
    if result is not None:
        return result

    view = ReviewSendJobView(
        sendJobId=send_job_id,
        draftId=draft_id,
        feedbackId=feedback.feedbackId,
        status=status,  # type: ignore[arg-type]
        answerText=draft.generatedText,
        externalRequestPath=external_request_path,
        resultMessage=result_message,
        requestedByActorId=actor.actor_id,
        requestedAt=now,
        completedAt=completed_at,
    )
    _MEMORY.send_jobs[send_job_id] = view
    if status == "sent" and not payload.dryRun:
        _MEMORY.drafts[draft_id] = draft.model_copy(update={"sendState": "sent", "updatedAt": _utc_now()})
    record_audit_event(
        actor=actor,
        action="reviews.send.request",
        object_type="review_send_job",
        object_id=send_job_id,
        before_state=draft.model_dump(mode="json"),
        after_state=view.model_dump(mode="json"),
        reason=payload.reason or result_message,
        approval_ref=None,
        evidence_refs=["memory_fallback", "reviews:send"],
    )
    return view


def get_send_job(send_job_id: str) -> ReviewSendJobView:
    def _db(session: Session) -> ReviewSendJobView | None:
        row = session.get(ReviewSendJobRow, send_job_id)
        return _to_send_job_view(row) if row is not None else None

    result = _run_db(_db)
    if result is not None:
        return result

    view = _MEMORY.send_jobs.get(send_job_id)
    if view is None:
        raise HTTPException(status_code=404, detail="REVIEW_SEND_JOB_NOT_FOUND")
    return view


def get_review_approval(review_id: str, rating: int) -> dict[str, Any]:
    draft: ReviewDraftView | None = None

    def _db(session: Session) -> ReviewDraftView | None:
        row = session.scalar(
            select(ReviewDraftRow)
            .where(ReviewDraftRow.feedback_id == review_id)
            .order_by(ReviewDraftRow.updated_at.desc())
        )
        return _to_draft_view(row) if row is not None else None

    result = _run_db(_db)
    if result is not None:
        draft = result
    else:
        for row in _MEMORY.drafts.values():
            if row.feedbackId == review_id:
                draft = row
                break

    if draft is None:
        approval_state = "required" if rating < 4 else "not_required"
        send_state = "draft_only" if rating < 4 else "ready_to_send"
        external_send_allowed = rating >= 4
        brand_voice_id = "wb-default"
        prompt_trace_id = None
        cache_metrics = ReviewCacheMetrics(cachedTokens=0, hitRatePct=0)
        draft_id = f"draft-{review_id}"
    else:
        approval_state = draft.approvalState
        send_state = draft.sendState
        external_send_allowed = draft.externalSendAllowed
        brand_voice_id = draft.brandVoiceId
        prompt_trace_id = draft.promptTraceId
        cache_metrics = draft.cacheMetrics or ReviewCacheMetrics(cachedTokens=0, hitRatePct=0)
        draft_id = draft.draftId

    return {
        "reviewId": review_id,
        "rating": rating,
        "draftId": draft_id,
        "approvalState": approval_state,
        "approvalActorId": draft.approvalActorId if draft else None,
        "approvedAt": draft.approvedAt if draft else None,
        "externalSendAllowed": external_send_allowed,
        "sendState": send_state,
        "brandVoiceId": brand_voice_id,
        "promptTraceId": prompt_trace_id,
        "cacheMetrics": cache_metrics.model_dump(mode="json"),
        "auditEvidence": [
            {
                "sourceId": "reviews-runtime-approval",
                "sourceType": "derived",
                "sourceName": "Reviews runtime approval projection",
                "lastSyncedAt": _utc_now(),
                "freshnessTtlMinutes": 60,
                "fieldsUsed": [
                    "approvalState",
                    "externalSendAllowed",
                    "sendState",
                    "promptTraceId",
                ],
            }
        ],
    }
