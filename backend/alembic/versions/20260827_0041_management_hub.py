"""add manager home, departments, meetings and gamification

Revision ID: 20260827_0041
Revises: 20260827_0040

This revision follows the explicit merge of the production finance branch and
the FoundHub sales branch.
"""

import sqlalchemy as sa

from alembic import op

revision = "20260827_0041"
down_revision = "20260827_0040"
branch_labels = None
depends_on = None


def _timestamps() -> tuple[sa.Column, sa.Column]:
    return (
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )


def upgrade() -> None:
    created_at, updated_at = _timestamps()
    op.create_table(
        "team_departments",
        sa.Column("department_id", sa.String(32), primary_key=True),
        sa.Column(
            "organization_id",
            sa.Integer(),
            sa.ForeignKey("lk_organizations.organization_id"),
            nullable=False,
        ),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "manager_user_id",
            sa.String(64),
            sa.ForeignKey("lk_users.user_id"),
            nullable=True,
        ),
        sa.Column("active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column(
            "created_by_user_id",
            sa.String(64),
            sa.ForeignKey("lk_users.user_id"),
            nullable=False,
        ),
        created_at,
        updated_at,
        sa.UniqueConstraint(
            "organization_id", "name", name="uq_team_departments_org_name"
        ),
    )
    op.create_index(
        "ix_team_departments_org_active",
        "team_departments",
        ["organization_id", "active", "name"],
    )

    op.create_table(
        "team_department_members",
        sa.Column("membership_id", sa.String(32), primary_key=True),
        sa.Column(
            "organization_id",
            sa.Integer(),
            sa.ForeignKey("lk_organizations.organization_id"),
            nullable=False,
        ),
        sa.Column(
            "department_id",
            sa.String(32),
            sa.ForeignKey("team_departments.department_id"),
            nullable=False,
        ),
        sa.Column(
            "user_id", sa.String(64), sa.ForeignKey("lk_users.user_id"), nullable=False
        ),
        sa.Column("role", sa.String(16), server_default="member", nullable=False),
        sa.Column(
            "is_primary", sa.Boolean(), server_default=sa.false(), nullable=False
        ),
        sa.Column(
            "created_by_user_id",
            sa.String(64),
            sa.ForeignKey("lk_users.user_id"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "department_id", "user_id", name="uq_team_department_member"
        ),
        sa.CheckConstraint(
            "role IN ('member', 'manager')", name="ck_team_department_member_role"
        ),
    )
    op.create_index(
        "ix_team_department_members_org_user",
        "team_department_members",
        ["organization_id", "user_id"],
    )

    op.add_column(
        "team_tasks", sa.Column("department_id", sa.String(32), nullable=True)
    )
    op.create_foreign_key(
        "fk_team_tasks_department",
        "team_tasks",
        "team_departments",
        ["department_id"],
        ["department_id"],
    )
    op.create_index(
        "ix_team_tasks_org_department",
        "team_tasks",
        ["organization_id", "department_id", "archived"],
    )

    created_at, updated_at = _timestamps()
    op.create_table(
        "team_meetings",
        sa.Column("meeting_id", sa.String(32), primary_key=True),
        sa.Column(
            "organization_id",
            sa.Integer(),
            sa.ForeignKey("lk_organizations.organization_id"),
            nullable=False,
        ),
        sa.Column(
            "department_id",
            sa.String(32),
            sa.ForeignKey("team_departments.department_id"),
            nullable=True,
        ),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("location", sa.String(255), nullable=True),
        sa.Column("video_link", sa.String(500), nullable=True),
        sa.Column(
            "linked_task_id",
            sa.String(32),
            sa.ForeignKey("team_tasks.task_id"),
            nullable=True,
        ),
        sa.Column("status", sa.String(16), server_default="scheduled", nullable=False),
        sa.Column(
            "created_by_user_id",
            sa.String(64),
            sa.ForeignKey("lk_users.user_id"),
            nullable=False,
        ),
        created_at,
        updated_at,
        sa.CheckConstraint(
            "status IN ('scheduled', 'completed', 'cancelled')",
            name="ck_team_meetings_status",
        ),
        sa.CheckConstraint("ends_at > starts_at", name="ck_team_meetings_interval"),
    )
    op.create_index(
        "ix_team_meetings_org_start",
        "team_meetings",
        ["organization_id", "starts_at", "meeting_id"],
    )
    op.create_index(
        "ix_team_meetings_department_start",
        "team_meetings",
        ["department_id", "starts_at"],
    )

    op.create_table(
        "team_meeting_attendees",
        sa.Column("attendee_id", sa.String(32), primary_key=True),
        sa.Column(
            "organization_id",
            sa.Integer(),
            sa.ForeignKey("lk_organizations.organization_id"),
            nullable=False,
        ),
        sa.Column(
            "meeting_id",
            sa.String(32),
            sa.ForeignKey("team_meetings.meeting_id"),
            nullable=False,
        ),
        sa.Column(
            "user_id", sa.String(64), sa.ForeignKey("lk_users.user_id"), nullable=False
        ),
        sa.Column("response", sa.String(16), server_default="pending", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("meeting_id", "user_id", name="uq_team_meeting_attendee"),
        sa.CheckConstraint(
            "response IN ('pending', 'accepted', 'declined')",
            name="ck_team_meeting_attendee_response",
        ),
    )
    op.create_index(
        "ix_team_meeting_attendees_user",
        "team_meeting_attendees",
        ["organization_id", "user_id", "meeting_id"],
    )

    for table_name, id_name, amount_columns in (
        (
            "team_kpi_targets",
            "target_id",
            [
                "tasks_target",
                "sales_target_kopecks",
                "profit_target_kopecks",
                "bonus_kopecks",
            ],
        ),
        (
            "team_performance_actuals",
            "actual_id",
            ["sales_adjustment_kopecks", "profit_actual_kopecks"],
        ),
    ):
        created_at, updated_at = _timestamps()
        columns = [
            sa.Column(id_name, sa.String(32), primary_key=True),
            sa.Column(
                "organization_id",
                sa.Integer(),
                sa.ForeignKey("lk_organizations.organization_id"),
                nullable=False,
            ),
            sa.Column(
                "department_id",
                sa.String(32),
                sa.ForeignKey("team_departments.department_id"),
                nullable=True,
            ),
            sa.Column(
                "user_id",
                sa.String(64),
                sa.ForeignKey("lk_users.user_id"),
                nullable=False,
            ),
            sa.Column("period_start", sa.Date(), nullable=False),
        ]
        columns.extend(
            sa.Column(
                name,
                sa.BigInteger() if name != "tasks_target" else sa.Integer(),
                server_default="0",
                nullable=False,
            )
            for name in amount_columns
        )
        if table_name == "team_performance_actuals":
            columns.append(sa.Column("note", sa.Text(), nullable=True))
        columns.extend(
            [
                sa.Column(
                    "set_by_user_id",
                    sa.String(64),
                    sa.ForeignKey("lk_users.user_id"),
                    nullable=False,
                ),
                created_at,
                updated_at,
                sa.UniqueConstraint(
                    "organization_id",
                    "user_id",
                    "period_start",
                    name=f"uq_{table_name[:-1]}_user_period",
                ),
                sa.CheckConstraint(
                    " AND ".join(f"{name} >= 0" for name in amount_columns),
                    name=f"ck_{table_name}_non_negative",
                ),
            ]
        )
        op.create_table(table_name, *columns)
        op.create_index(
            f"ix_{table_name}_department_period",
            table_name,
            ["department_id", "period_start"],
        )

    created_at, updated_at = _timestamps()
    op.create_table(
        "team_department_rewards",
        sa.Column("reward_id", sa.String(32), primary_key=True),
        sa.Column(
            "organization_id",
            sa.Integer(),
            sa.ForeignKey("lk_organizations.organization_id"),
            nullable=False,
        ),
        sa.Column(
            "department_id",
            sa.String(32),
            sa.ForeignKey("team_departments.department_id"),
            nullable=False,
        ),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("title", sa.String(160), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("criteria", sa.String(500), nullable=True),
        sa.Column(
            "prize_value_kopecks", sa.BigInteger(), server_default="0", nullable=False
        ),
        sa.Column(
            "set_by_user_id",
            sa.String(64),
            sa.ForeignKey("lk_users.user_id"),
            nullable=False,
        ),
        created_at,
        updated_at,
        sa.UniqueConstraint(
            "organization_id",
            "department_id",
            "period_start",
            name="uq_team_department_reward_period",
        ),
        sa.CheckConstraint(
            "prize_value_kopecks >= 0", name="ck_team_department_reward_value"
        ),
    )


def downgrade() -> None:
    op.drop_table("team_department_rewards")
    for table_name in ("team_performance_actuals", "team_kpi_targets"):
        op.drop_index(f"ix_{table_name}_department_period", table_name=table_name)
        op.drop_table(table_name)
    op.drop_index("ix_team_meeting_attendees_user", table_name="team_meeting_attendees")
    op.drop_table("team_meeting_attendees")
    op.drop_index("ix_team_meetings_department_start", table_name="team_meetings")
    op.drop_index("ix_team_meetings_org_start", table_name="team_meetings")
    op.drop_table("team_meetings")
    op.drop_index("ix_team_tasks_org_department", table_name="team_tasks")
    op.drop_constraint("fk_team_tasks_department", "team_tasks", type_="foreignkey")
    op.drop_column("team_tasks", "department_id")
    op.drop_index(
        "ix_team_department_members_org_user", table_name="team_department_members"
    )
    op.drop_table("team_department_members")
    op.drop_index("ix_team_departments_org_active", table_name="team_departments")
    op.drop_table("team_departments")
