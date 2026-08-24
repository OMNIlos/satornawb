from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, JSON, String, UniqueConstraint, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.infra.models import Base


class WbReportRuleProfileRow(Base):
    __tablename__ = "wb_report_rule_profiles"
    __table_args__ = (
        UniqueConstraint("organization_id", "version", name="uq_wb_report_rule_profile_org_version"),
        Index(
            "uq_wb_report_rule_profile_active_org",
            "organization_id",
            unique=True,
            postgresql_where=text("is_active"),
            sqlite_where=text("is_active = 1"),
        ),
    )

    profile_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("lk_organizations.organization_id"), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    preset: Mapped[str] = mapped_column(String(32), nullable=False)
    config_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_by_user_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
