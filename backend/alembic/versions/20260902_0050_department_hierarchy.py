"""add department hierarchy

Revision ID: 20260902_0050
Revises: 20260902_0049
"""

import sqlalchemy as sa
from alembic import op

revision = "20260902_0050"
down_revision = "20260902_0049"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "team_departments",
        sa.Column("parent_department_id", sa.String(length=32), nullable=True),
    )
    op.create_foreign_key(
        "fk_team_departments_parent",
        "team_departments",
        "team_departments",
        ["parent_department_id"],
        ["department_id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_team_departments_parent", "team_departments", ["parent_department_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_team_departments_parent", table_name="team_departments")
    op.drop_constraint(
        "fk_team_departments_parent", "team_departments", type_="foreignkey"
    )
    op.drop_column("team_departments", "parent_department_id")
