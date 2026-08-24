from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.infra.models import Base


class WbRepricerAlgorithmSettingsRow(Base):
    __tablename__ = "wb_repricer_algorithm_settings"

    organization_id: Mapped[int] = mapped_column(
        ForeignKey("lk_organizations.organization_id"),
        primary_key=True,
    )
    settings_payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class WbRepricerRuntimeStateRow(Base):
    __tablename__ = "wb_repricer_runtime_state"

    organization_id: Mapped[int] = mapped_column(
        ForeignKey("lk_organizations.organization_id"),
        primary_key=True,
    )
    state_payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class WbRepricerExecutionRunRow(Base):
    __tablename__ = "wb_repricer_execution_runs"

    run_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("lk_organizations.organization_id"), nullable=False)
    trigger: Mapped[str] = mapped_column(String(32), nullable=False, default="manual")
    report_payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class WbRepricerChangelogRow(Base):
    __tablename__ = "wb_repricer_changelog"
    __table_args__ = (
        UniqueConstraint("organization_id", "entry_id", name="uq_wb_repricer_changelog_org_entry"),
    )

    row_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("lk_organizations.organization_id"), nullable=False)
    entry_id: Mapped[str] = mapped_column(String(128), nullable=False)
    article_id: Mapped[str] = mapped_column(String(128), nullable=False)
    entry_payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
