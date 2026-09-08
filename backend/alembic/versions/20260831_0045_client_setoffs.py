"""add debit and credit client setoff documents

Revision ID: 20260831_0045
Revises: 20260830_0044
"""

import sqlalchemy as sa
from alembic import op

revision = "20260831_0045"
down_revision = "20260830_0044"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint(
        "ck_client_debt_ledger_semantics",
        "client_debt_ledger_entries",
        type_="check",
    )
    op.create_check_constraint(
        "ck_client_debt_ledger_semantics",
        "client_debt_ledger_entries",
        "(entry_type = 'charge' AND source_type IN ('billing', 'sale') AND delta_kopecks > 0) "
        "OR (entry_type = 'payment' AND source_type = 'payment' AND delta_kopecks < 0) "
        "OR (entry_type = 'adjustment' AND source_type = 'sale_cancel' AND delta_kopecks < 0) "
        "OR (entry_type = 'adjustment' AND source_type = 'setoff')",
    )
    op.create_table(
        "client_setoff_sequences",
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("last_number", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["lk_organizations.organization_id"]
        ),
        sa.PrimaryKeyConstraint("organization_id"),
    )
    op.create_table(
        "client_setoffs",
        sa.Column("setoff_id", sa.String(length=32), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("client_id", sa.String(length=32), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("payload_sha256", sa.String(length=64), nullable=False),
        sa.Column("document_number", sa.String(length=32), nullable=False),
        sa.Column("side", sa.String(length=8), nullable=False),
        sa.Column("amount_kopecks", sa.BigInteger(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column(
            "allow_credit", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
        sa.Column("created_by_user_id", sa.String(length=64), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "side IN ('debit', 'credit')", name="ck_client_setoffs_side"
        ),
        sa.CheckConstraint(
            "amount_kopecks > 0", name="ck_client_setoffs_amount_positive"
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "client_id"],
            ["client_accounts.organization_id", "client_accounts.client_id"],
            name="fk_client_setoffs_org_client",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["lk_organizations.organization_id"]
        ),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["lk_users.user_id"]),
        sa.PrimaryKeyConstraint("setoff_id"),
        sa.UniqueConstraint(
            "organization_id",
            "document_number",
            name="uq_client_setoffs_org_document",
        ),
        sa.UniqueConstraint(
            "organization_id",
            "idempotency_key",
            name="uq_client_setoffs_org_idempotency",
        ),
    )
    op.create_index(
        "ix_client_setoffs_org_client",
        "client_setoffs",
        ["organization_id", "client_id", "occurred_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_client_setoffs_org_client", table_name="client_setoffs")
    op.drop_table("client_setoffs")
    op.drop_table("client_setoff_sequences")
    op.drop_constraint(
        "ck_client_debt_ledger_semantics",
        "client_debt_ledger_entries",
        type_="check",
    )
    op.create_check_constraint(
        "ck_client_debt_ledger_semantics",
        "client_debt_ledger_entries",
        "(entry_type = 'charge' AND source_type IN ('billing', 'sale') AND delta_kopecks > 0) "
        "OR (entry_type = 'payment' AND source_type = 'payment' AND delta_kopecks < 0) "
        "OR (entry_type = 'adjustment' AND source_type = 'sale_cancel' AND delta_kopecks < 0)",
    )
