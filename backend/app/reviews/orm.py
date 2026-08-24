from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, BigInteger, Boolean, DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.infra.models import Base


class ReviewTemplateRow(Base):
    __tablename__ = "rv_review_templates"

    template_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    brand_voice_id: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    body_template: Mapped[str] = mapped_column(Text, nullable=False)
    rating_from: Mapped[int] = mapped_column(Integer, nullable=False)
    rating_to: Mapped[int] = mapped_column(Integer, nullable=False)
    keywords: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    keyword_mode: Mapped[str] = mapped_column(String(8), nullable=False, default="any")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_by_actor_id: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class ReviewStopTopicRow(Base):
    __tablename__ = "rv_review_stop_topics"

    stop_topic_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    brand_voice_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    phrase: Mapped[str] = mapped_column(String(255), nullable=False)
    match_type: Mapped[str] = mapped_column(String(16), nullable=False)
    action: Mapped[str] = mapped_column(String(32), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_by_actor_id: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class ReviewModerationRuleRow(Base):
    __tablename__ = "rv_review_moderation_rules"

    rule_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    brand_voice_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    condition_type: Mapped[str] = mapped_column(String(64), nullable=False)
    action: Mapped[str] = mapped_column(String(32), nullable=False)
    threshold_int: Mapped[int | None] = mapped_column(Integer, nullable=True)
    keywords: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_by_actor_id: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class ReviewFeedbackRow(Base):
    __tablename__ = "rv_review_feedbacks"

    feedback_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    nm_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    imt_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    brand_name: Mapped[str] = mapped_column(String(255), nullable=False)
    product_name: Mapped[str] = mapped_column(String(255), nullable=False)
    created_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    pros: Mapped[str] = mapped_column(Text, nullable=False, default="")
    cons: Mapped[str] = mapped_column(Text, nullable=False, default="")
    answer_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_answered: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    rating: Mapped[int | None] = mapped_column(Integer, nullable=True)
    raw_payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    synced_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class ReviewDraftRow(Base):
    __tablename__ = "rv_review_drafts"

    draft_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    feedback_id: Mapped[str] = mapped_column(String(128), nullable=False)
    rating: Mapped[int] = mapped_column(Integer, nullable=False)
    brand_voice_id: Mapped[str] = mapped_column(String(64), nullable=False)
    template_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    approval_state: Mapped[str] = mapped_column(String(16), nullable=False)
    approval_actor_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    external_send_allowed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    send_state: Mapped[str] = mapped_column(String(16), nullable=False)
    generated_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    moderation_state: Mapped[str] = mapped_column(String(16), nullable=False)
    moderation_reasons: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    matched_stop_topic_ids: Mapped[list[int]] = mapped_column(JSON, nullable=False, default=list)
    matched_rule_ids: Mapped[list[int]] = mapped_column(JSON, nullable=False, default=list)
    prompt_trace_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    cache_metrics: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_by_actor_id: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class ReviewSendJobRow(Base):
    __tablename__ = "rv_review_send_jobs"

    send_job_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    draft_id: Mapped[str] = mapped_column(String(64), nullable=False)
    feedback_id: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    answer_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    external_request_path: Mapped[str | None] = mapped_column(String(255), nullable=True)
    result_message: Mapped[str] = mapped_column(Text, nullable=False)
    requested_by_actor_id: Mapped[str] = mapped_column(String(128), nullable=False)
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ReviewPromptTraceRow(Base):
    __tablename__ = "rv_review_prompt_traces"

    draft_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    prompt_trace_id: Mapped[str] = mapped_column(String(128), nullable=False)
    stable_prefix_keys: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    volatile_suffix_keys: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    cache_metrics: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    metadata_payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class ReviewSyncSettingsRow(Base):
    __tablename__ = "rv_review_sync_settings"

    organization_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    interval_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    token_type: Mapped[str] = mapped_column(String(16), nullable=False, default="personal")
    unanswered_only: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    take: Mapped[int] = mapped_column(Integer, nullable=False, default=500)
    lookback_days: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    ai_prompt: Mapped[str] = mapped_column(Text, nullable=False, default="")
    settings_payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    updated_by_actor_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class ReviewSyncRunRow(Base):
    __tablename__ = "rv_review_sync_runs"

    sync_run_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    organization_id: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    trigger: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    scenario: Mapped[str] = mapped_column(String(64), nullable=False, default="complete")
    synced_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    source_status: Mapped[str] = mapped_column(String(16), nullable=False, default="blocked")
    next_skip: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
