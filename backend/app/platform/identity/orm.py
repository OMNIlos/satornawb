from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.cabinet import orm as _cabinet_models  # noqa: F401
from app.infra.models import Base


class IamMembershipRow(Base):
    __tablename__ = "iam_memberships"
    __table_args__ = (
        UniqueConstraint("organization_id", "user_id", name="uq_iam_memberships_org_user"),
        UniqueConstraint("organization_id", "membership_id", name="uq_iam_memberships_org_id"),
    )

    membership_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("lk_organizations.organization_id"), nullable=False)
    user_id: Mapped[str] = mapped_column(ForeignKey("lk_users.user_id"), nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False)
    permissions: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    scope_mode: Mapped[str] = mapped_column(String(16), nullable=False, default="all")
    allowed_account_ids: Mapped[list[int]] = mapped_column(JSON, nullable=False, default=list)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
