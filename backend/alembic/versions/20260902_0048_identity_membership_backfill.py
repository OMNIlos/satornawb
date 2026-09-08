"""backfill canonical identity memberships

Revision ID: 20260902_0048
Revises: 20260901_0047
Create Date: 2026-09-02
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "20260902_0048"
down_revision = "20260901_0047"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        sa.text(
            """
            INSERT INTO iam_memberships (
                organization_id,
                user_id,
                role,
                permissions,
                scope_mode,
                allowed_account_ids,
                is_active
            )
            SELECT
                users.organization_id,
                users.user_id,
                users.permission_profile,
                COALESCE(
                    (
                        SELECT json_agg(user_permissions.permission ORDER BY user_permissions.permission)
                        FROM lk_user_permissions AS user_permissions
                        WHERE user_permissions.user_id = users.user_id
                    ),
                    '[]'::json
                ),
                'all',
                '[]'::json,
                users.is_active
            FROM lk_users AS users
            ON CONFLICT (organization_id, user_id) DO NOTHING
            """
        )
    )


def downgrade() -> None:
    # Preserve access assignments: 0046 owns the table and later edits may be intentional.
    pass
