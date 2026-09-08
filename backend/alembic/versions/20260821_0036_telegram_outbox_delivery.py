"""add durable delivery state to client Telegram outbox

Revision ID: 20260821_0036
Revises: 20260821_0035
"""

import sqlalchemy as sa

from alembic import op

revision = "20260821_0036"
down_revision = "20260821_0035"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint(
        "ck_client_telegram_outbox_status", "client_telegram_outbox", type_="check"
    )
    op.create_check_constraint(
        "ck_client_telegram_outbox_status",
        "client_telegram_outbox",
        "status IN ('pending', 'sending', 'retry', 'sent', 'skipped', 'failed')",
    )
    op.add_column(
        "client_telegram_outbox",
        sa.Column("attempt_count", sa.BigInteger(), nullable=False, server_default="0"),
    )
    op.add_column(
        "client_telegram_outbox",
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "client_telegram_outbox",
        sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "client_telegram_outbox",
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "client_telegram_outbox",
        sa.Column("last_error", sa.String(length=255), nullable=True),
    )
    op.create_index(
        "ix_client_telegram_outbox_delivery",
        "client_telegram_outbox",
        ["status", "next_attempt_at", "created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_client_telegram_outbox_delivery", table_name="client_telegram_outbox"
    )
    for column in (
        "last_error",
        "sent_at",
        "locked_at",
        "next_attempt_at",
        "attempt_count",
    ):
        op.drop_column("client_telegram_outbox", column)
    op.drop_constraint(
        "ck_client_telegram_outbox_status", "client_telegram_outbox", type_="check"
    )
    op.create_check_constraint(
        "ck_client_telegram_outbox_status",
        "client_telegram_outbox",
        "status = 'pending'",
    )
