"""add avito return item image url

Revision ID: 20260810_0023
Revises: 20260807_0022
Create Date: 2026-08-10 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260810_0023"
down_revision = "20260807_0022"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("avito_return_items", sa.Column("image_url", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("avito_return_items", "image_url")
