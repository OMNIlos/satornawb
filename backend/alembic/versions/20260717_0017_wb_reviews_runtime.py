from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "20260717_0017"
down_revision = "20260716_0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "rv_review_templates",
        sa.Column("template_id", sa.String(length=64), primary_key=True),
        sa.Column("brand_voice_id", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("body_template", sa.Text(), nullable=False),
        sa.Column("rating_from", sa.Integer(), nullable=False),
        sa.Column("rating_to", sa.Integer(), nullable=False),
        sa.Column("keywords", sa.JSON(), nullable=False),
        sa.Column("keyword_mode", sa.String(length=8), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_by_actor_id", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "rv_review_stop_topics",
        sa.Column("stop_topic_id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("brand_voice_id", sa.String(length=64), nullable=True),
        sa.Column("phrase", sa.String(length=255), nullable=False),
        sa.Column("match_type", sa.String(length=16), nullable=False),
        sa.Column("action", sa.String(length=32), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_by_actor_id", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "rv_review_moderation_rules",
        sa.Column("rule_id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("brand_voice_id", sa.String(length=64), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("condition_type", sa.String(length=64), nullable=False),
        sa.Column("action", sa.String(length=32), nullable=False),
        sa.Column("threshold_int", sa.Integer(), nullable=True),
        sa.Column("keywords", sa.JSON(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_by_actor_id", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "rv_review_feedbacks",
        sa.Column("feedback_id", sa.String(length=128), primary_key=True),
        sa.Column("nm_id", sa.BigInteger(), nullable=False),
        sa.Column("imt_id", sa.BigInteger(), nullable=True),
        sa.Column("brand_name", sa.String(length=255), nullable=False),
        sa.Column("product_name", sa.String(length=255), nullable=False),
        sa.Column("created_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("pros", sa.Text(), nullable=False),
        sa.Column("cons", sa.Text(), nullable=False),
        sa.Column("answer_text", sa.Text(), nullable=True),
        sa.Column("is_answered", sa.Boolean(), nullable=False),
        sa.Column("rating", sa.Integer(), nullable=True),
        sa.Column("raw_payload", sa.JSON(), nullable=False),
        sa.Column("synced_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "rv_review_drafts",
        sa.Column("draft_id", sa.String(length=64), primary_key=True),
        sa.Column("feedback_id", sa.String(length=128), nullable=False),
        sa.Column("rating", sa.Integer(), nullable=False),
        sa.Column("brand_voice_id", sa.String(length=64), nullable=False),
        sa.Column("template_id", sa.String(length=64), nullable=True),
        sa.Column("approval_state", sa.String(length=16), nullable=False),
        sa.Column("approval_actor_id", sa.String(length=128), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("external_send_allowed", sa.Boolean(), nullable=False),
        sa.Column("send_state", sa.String(length=16), nullable=False),
        sa.Column("generated_text", sa.Text(), nullable=False),
        sa.Column("moderation_state", sa.String(length=16), nullable=False),
        sa.Column("moderation_reasons", sa.JSON(), nullable=False),
        sa.Column("matched_stop_topic_ids", sa.JSON(), nullable=False),
        sa.Column("matched_rule_ids", sa.JSON(), nullable=False),
        sa.Column("prompt_trace_id", sa.String(length=128), nullable=True),
        sa.Column("cache_metrics", sa.JSON(), nullable=True),
        sa.Column("created_by_actor_id", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "rv_review_send_jobs",
        sa.Column("send_job_id", sa.String(length=64), primary_key=True),
        sa.Column("draft_id", sa.String(length=64), nullable=False),
        sa.Column("feedback_id", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("answer_text", sa.Text(), nullable=False),
        sa.Column("external_request_path", sa.String(length=255), nullable=True),
        sa.Column("result_message", sa.Text(), nullable=False),
        sa.Column("requested_by_actor_id", sa.String(length=128), nullable=False),
        sa.Column("requested_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_table(
        "rv_review_prompt_traces",
        sa.Column("draft_id", sa.String(length=64), primary_key=True),
        sa.Column("prompt_trace_id", sa.String(length=128), nullable=False),
        sa.Column("stable_prefix_keys", sa.JSON(), nullable=False),
        sa.Column("volatile_suffix_keys", sa.JSON(), nullable=False),
        sa.Column("cache_metrics", sa.JSON(), nullable=True),
        sa.Column("metadata_payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "rv_review_sync_settings",
        sa.Column("organization_id", sa.Integer(), primary_key=True),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("interval_minutes", sa.Integer(), nullable=False),
        sa.Column("token_type", sa.String(length=16), nullable=False),
        sa.Column("unanswered_only", sa.Boolean(), nullable=False),
        sa.Column("take", sa.Integer(), nullable=False),
        sa.Column("lookback_days", sa.Integer(), nullable=False),
        sa.Column("ai_prompt", sa.Text(), nullable=False, server_default=""),
        sa.Column("updated_by_actor_id", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "rv_review_sync_runs",
        sa.Column("sync_run_id", sa.String(length=64), primary_key=True),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("trigger", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("scenario", sa.String(length=64), nullable=False),
        sa.Column("synced_count", sa.Integer(), nullable=False),
        sa.Column("source_status", sa.String(length=16), nullable=False),
        sa.Column("next_skip", sa.Integer(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("rv_review_sync_runs")
    op.drop_table("rv_review_sync_settings")
    op.drop_table("rv_review_prompt_traces")
    op.drop_table("rv_review_send_jobs")
    op.drop_table("rv_review_drafts")
    op.drop_table("rv_review_feedbacks")
    op.drop_table("rv_review_moderation_rules")
    op.drop_table("rv_review_stop_topics")
    op.drop_table("rv_review_templates")
