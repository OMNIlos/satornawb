"""add internal team tasks

Revision ID: 20260818_0030
Revises: 20260817_0029
Create Date: 2026-08-18 10:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "20260818_0030"
down_revision = "20260817_0029"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "team_tasks",
        sa.Column("task_id", sa.String(32), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("lk_organizations.organization_id"), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(24), nullable=False, server_default="new"),
        sa.Column("priority", sa.String(16), nullable=False, server_default="normal"),
        sa.Column("assignee_user_id", sa.String(64), sa.ForeignKey("lk_users.user_id"), nullable=True),
        sa.Column("created_by_user_id", sa.String(64), sa.ForeignKey("lk_users.user_id"), nullable=False),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("checklist", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("linked_entity_type", sa.String(64), nullable=True),
        sa.Column("linked_entity_id", sa.String(128), nullable=True),
        sa.Column("archived", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_team_tasks_org_status", "team_tasks", ["organization_id", "status", "archived", "due_at"])
    op.create_index("ix_team_tasks_org_assignee", "team_tasks", ["organization_id", "assignee_user_id", "archived"])
    op.create_index("ix_team_tasks_org_creator", "team_tasks", ["organization_id", "created_by_user_id", "archived"])
    op.create_table(
        "team_task_comments",
        sa.Column("comment_id", sa.String(32), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("lk_organizations.organization_id"), nullable=False),
        sa.Column("task_id", sa.String(32), sa.ForeignKey("team_tasks.task_id"), nullable=False),
        sa.Column("author_user_id", sa.String(64), sa.ForeignKey("lk_users.user_id"), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_team_task_comments_task", "team_task_comments", ["task_id", "created_at"])
    op.create_table(
        "team_task_activity",
        sa.Column("activity_id", sa.String(32), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("lk_organizations.organization_id"), nullable=False),
        sa.Column("task_id", sa.String(32), sa.ForeignKey("team_tasks.task_id"), nullable=False),
        sa.Column("actor_user_id", sa.String(64), sa.ForeignKey("lk_users.user_id"), nullable=True),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("details", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_team_task_activity_task", "team_task_activity", ["task_id", "created_at"])


def downgrade() -> None:
    op.drop_table("team_task_activity")
    op.drop_table("team_task_comments")
    op.drop_table("team_tasks")
