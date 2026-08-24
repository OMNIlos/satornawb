from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.contracts.envelopes import UtcDateTime


TemplateKeywordMode = Literal["any", "all"]
StopTopicAction = Literal["manual_review", "block_send"]
StopTopicMatch = Literal["contains", "exact"]
ModerationAction = Literal["allow", "manual_review", "block_send", "block_draft"]
ModerationCondition = Literal["low_rating", "contains_stop_topic", "already_answered", "contains_keyword", "empty_text"]
DraftModerationState = Literal["clean", "manual_review", "blocked"]
ReviewApprovalState = Literal["not_required", "required", "approved", "rejected", "expired"]
ReviewSendState = Literal["draft_only", "ready_to_send", "sent", "blocked"]
ReviewSendJobStatus = Literal["queued", "sent", "blocked", "failed"]
ReviewFeedbackOrder = Literal["dateDesc", "dateAsc"]
ReviewSyncTokenType = Literal["personal", "service", "base"]
ReviewSyncRunStatus = Literal["idle", "running", "completed", "failed", "skipped"]
ReviewSyncTrigger = Literal["manual", "scheduler"]
ReviewAutomationMode = Literal["draft-first", "auto-safe", "paused"]
ReviewThreeStarAction = Literal["manual", "draft", "auto-low"]
ReviewLowStarsAction = Literal["alert-block", "manual", "draft"]
ReviewQuoteMode = Literal["approved-search", "approved-only", "off"]


class ReviewAutomationSettings(BaseModel):
    automationMode: ReviewAutomationMode = "draft-first"
    replyDelayMinutes: int = Field(default=15, ge=0, le=1440)
    threeStarAction: ReviewThreeStarAction = "manual"
    lowStarsAction: ReviewLowStarsAction = "alert-block"
    anomieTone: str = "Молодежный/зумерский"
    blessTone: str = "Временно, на подтверждении"
    avitoTone: str = "Спокойный, уверенный тон продавца Avito"
    quoteMode: ReviewQuoteMode = "approved-search"
    validateName: bool = True
    recommendations30d: bool = True
    quotesApproval: bool = True
    candidateSearch: bool = True


class ReviewTemplateCreateRequest(BaseModel):
    brandVoiceId: str = Field(min_length=1)
    title: str = Field(min_length=1)
    bodyTemplate: str = Field(min_length=1)
    ratingFrom: int = Field(ge=1, le=5)
    ratingTo: int = Field(ge=1, le=5)
    keywords: list[str] = Field(default_factory=list)
    keywordMode: TemplateKeywordMode = "any"
    isActive: bool = True


class ReviewTemplateView(ReviewTemplateCreateRequest):
    templateId: str = Field(min_length=1)
    createdByActorId: str = Field(min_length=1)
    createdAt: UtcDateTime
    updatedAt: UtcDateTime


class ReviewStopTopicCreateRequest(BaseModel):
    brandVoiceId: str | None = None
    phrase: str = Field(min_length=1)
    matchType: StopTopicMatch = "contains"
    action: StopTopicAction = "manual_review"
    isActive: bool = True


class ReviewStopTopicView(ReviewStopTopicCreateRequest):
    stopTopicId: int = Field(ge=1)
    createdByActorId: str = Field(min_length=1)
    createdAt: UtcDateTime
    updatedAt: UtcDateTime


class ReviewModerationRuleCreateRequest(BaseModel):
    brandVoiceId: str | None = None
    name: str = Field(min_length=1)
    conditionType: ModerationCondition
    action: ModerationAction
    thresholdInt: int | None = None
    keywords: list[str] = Field(default_factory=list)
    isActive: bool = True


class ReviewModerationRuleView(ReviewModerationRuleCreateRequest):
    ruleId: int = Field(ge=1)
    createdByActorId: str = Field(min_length=1)
    createdAt: UtcDateTime
    updatedAt: UtcDateTime


class ReviewSettingsBundle(BaseModel):
    templates: list[ReviewTemplateView]
    stopTopics: list[ReviewStopTopicView]
    moderationRules: list[ReviewModerationRuleView]


class ReviewFeedbackDraftSummary(BaseModel):
    draftId: str = Field(min_length=1)
    rating: int = Field(ge=1, le=5)
    brandVoiceId: str = Field(min_length=1)
    templateId: str | None = None
    approvalState: ReviewApprovalState
    sendState: ReviewSendState
    generatedText: str = ""
    moderationState: DraftModerationState
    moderationReasons: list[str] = Field(default_factory=list)
    updatedAt: UtcDateTime


class ReviewFeedbackView(BaseModel):
    feedbackId: str = Field(min_length=1)
    nmId: int = Field(ge=1)
    imtId: int | None = Field(default=None, ge=1)
    brandName: str = Field(min_length=1)
    productName: str = Field(min_length=1)
    createdDate: UtcDateTime
    text: str = ""
    pros: str = ""
    cons: str = ""
    answerText: str | None = None
    isAnswered: bool
    rating: int | None = Field(default=None, ge=1, le=5)
    syncedAt: UtcDateTime
    sourceStatus: Literal["fresh", "partial", "blocked"] = "fresh"
    latestDraft: ReviewFeedbackDraftSummary | None = None


class ReviewFeedbackSyncRequest(BaseModel):
    scenario: str = "complete"
    isAnswered: bool | None = None
    nmId: int | None = Field(default=None, ge=1)
    take: int = Field(default=5000, ge=1, le=5000)
    skip: int = Field(default=0, ge=0)
    order: ReviewFeedbackOrder = "dateDesc"
    dateFrom: int | None = Field(default=None, ge=0)
    dateTo: int | None = Field(default=None, ge=0)


class ReviewFeedbackSyncResponse(BaseModel):
    syncedCount: int = Field(ge=0)
    sourceStatus: Literal["fresh", "partial", "blocked"]
    nextSkip: int = Field(ge=0)
    syncedAt: UtcDateTime


class ReviewSyncSettingsUpdateRequest(BaseModel):
    enabled: bool = True
    intervalMinutes: int = Field(default=30, ge=1, le=1440)
    tokenType: ReviewSyncTokenType = "personal"
    unansweredOnly: bool = True
    take: int = Field(default=500, ge=1, le=5000)
    lookbackDays: int = Field(default=30, ge=1, le=180)
    aiPrompt: str = ""
    reviewSettings: ReviewAutomationSettings = Field(default_factory=ReviewAutomationSettings)


class ReviewSyncSettingsView(ReviewSyncSettingsUpdateRequest):
    organizationId: int = Field(ge=1)
    updatedByActorId: str | None = None
    createdAt: UtcDateTime
    updatedAt: UtcDateTime
    minIntervalMinutes: int = Field(ge=1)


class ReviewSyncStatusView(BaseModel):
    organizationId: int = Field(ge=1)
    status: ReviewSyncRunStatus
    enabled: bool
    intervalMinutes: int = Field(ge=1)
    nextRunAt: UtcDateTime | None = None
    lastRunAt: UtcDateTime | None = None
    lastCompletedAt: UtcDateTime | None = None
    lastSyncedCount: int = Field(ge=0)
    lastSourceStatus: Literal["fresh", "partial", "blocked"] | None = None
    lastError: str | None = None


class ReviewCacheMetrics(BaseModel):
    cachedTokens: int = Field(ge=0)
    hitRatePct: float = Field(ge=0, le=100)


class ReviewAiGenerationResult(BaseModel):
    replyText: str = Field(min_length=1)
    riskLevel: Literal["low", "medium", "high"]
    requiresApproval: bool
    reasons: list[str] = Field(default_factory=list)
    matchedStopTopics: list[str] = Field(default_factory=list)
    model: str | None = None
    generationSource: Literal["openai"]


class ReviewDraftGenerateRequest(BaseModel):
    feedbackId: str = Field(min_length=1)
    brandVoiceId: str = Field(min_length=1)
    ratingOverride: int | None = Field(default=None, ge=1, le=5)
    promptInstruction: str | None = Field(default=None, max_length=8000)
    promptTraceId: str | None = None
    cacheMetrics: ReviewCacheMetrics | None = None
    regenerate: bool = False


class ReviewDraftBatchGenerateItem(BaseModel):
    feedbackId: str = Field(min_length=1)
    brandVoiceId: str = Field(min_length=1)
    ratingOverride: int | None = Field(default=None, ge=1, le=5)
    promptInstruction: str | None = Field(default=None, max_length=8000)


class ReviewDraftBatchGenerateRequest(BaseModel):
    items: list[ReviewDraftBatchGenerateItem] = Field(min_length=1, max_length=25)
    regenerate: bool = True


class ReviewDraftBatchError(BaseModel):
    feedbackId: str = Field(min_length=1)
    message: str = Field(min_length=1)


class ReviewModerationDecision(BaseModel):
    state: DraftModerationState
    reasons: list[str]
    matchedStopTopicIds: list[int] = Field(default_factory=list)
    matchedRuleIds: list[int] = Field(default_factory=list)


class ReviewDraftView(BaseModel):
    draftId: str = Field(min_length=1)
    feedbackId: str = Field(min_length=1)
    rating: int = Field(ge=1, le=5)
    brandVoiceId: str = Field(min_length=1)
    templateId: str | None = None
    approvalState: ReviewApprovalState
    approvalActorId: str | None = None
    approvedAt: UtcDateTime | None = None
    externalSendAllowed: bool
    sendState: ReviewSendState
    generatedText: str = ""
    moderation: ReviewModerationDecision
    promptTraceId: str | None = None
    cacheMetrics: ReviewCacheMetrics | None = None
    createdByActorId: str = Field(min_length=1)
    createdAt: UtcDateTime
    updatedAt: UtcDateTime


class ReviewDraftBatchGenerateResponse(BaseModel):
    requestedCount: int = Field(ge=0)
    generatedCount: int = Field(ge=0)
    failedCount: int = Field(ge=0)
    drafts: list[ReviewDraftView] = Field(default_factory=list)
    errors: list[ReviewDraftBatchError] = Field(default_factory=list)


class ReviewApproveRequest(BaseModel):
    approvalRef: str = Field(min_length=1)
    reason: str | None = None


class ReviewRejectRequest(BaseModel):
    reason: str = Field(min_length=1)


class ReviewSendRequest(BaseModel):
    dryRun: bool = False
    reason: str | None = None


class ReviewSendJobView(BaseModel):
    sendJobId: str = Field(min_length=1)
    draftId: str = Field(min_length=1)
    feedbackId: str = Field(min_length=1)
    status: ReviewSendJobStatus
    answerText: str = ""
    externalRequestPath: str | None = None
    resultMessage: str = Field(min_length=1)
    requestedByActorId: str = Field(min_length=1)
    requestedAt: UtcDateTime
    completedAt: UtcDateTime | None = None


class ReviewPromptTraceView(BaseModel):
    draftId: str = Field(min_length=1)
    promptTraceId: str = Field(min_length=1)
    stablePrefixKeys: list[str]
    volatileSuffixKeys: list[str]
    cacheMetrics: ReviewCacheMetrics | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    createdAt: UtcDateTime
