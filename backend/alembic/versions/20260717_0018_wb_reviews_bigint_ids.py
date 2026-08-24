"""Use bigint for WB review article identifiers."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260717_0018"
down_revision = "20260717_0017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("rv_review_feedbacks", "nm_id", existing_type=sa.Integer(), type_=sa.BigInteger(), existing_nullable=False)
    op.alter_column("rv_review_feedbacks", "imt_id", existing_type=sa.Integer(), type_=sa.BigInteger(), existing_nullable=True)


def downgrade() -> None:
    op.alter_column("rv_review_feedbacks", "imt_id", existing_type=sa.BigInteger(), type_=sa.Integer(), existing_nullable=True)
    op.alter_column("rv_review_feedbacks", "nm_id", existing_type=sa.BigInteger(), type_=sa.Integer(), existing_nullable=False)
