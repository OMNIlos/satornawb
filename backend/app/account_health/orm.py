from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.infra.models import Base


class WbAccountRow(Base):
    __tablename__ = "wb_accounts"

    account_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    source_status: Mapped[str] = mapped_column(String(16), nullable=False)
    auth_state: Mapped[str] = mapped_column(String(32), nullable=False)
    blocker_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    next_actions: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    last_checked_scenario: Mapped[str] = mapped_column(String(32), nullable=False)
    last_checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class WbAccountCapabilityRow(Base):
    __tablename__ = "wb_account_capabilities"

    capability_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    account_id: Mapped[str] = mapped_column(String(128), ForeignKey("wb_accounts.account_id"), nullable=False)
    capability: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    missing_scopes: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    blocker_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    evidence_ref: Mapped[str] = mapped_column(Text, nullable=False)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class WbAccountMissingScopeRow(Base):
    __tablename__ = "wb_account_missing_scopes"

    scope_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    account_id: Mapped[str] = mapped_column(String(128), ForeignKey("wb_accounts.account_id"), nullable=False)
    capability: Mapped[str] = mapped_column(String(64), nullable=False)
    scope: Mapped[str] = mapped_column(String(128), nullable=False)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class WbTokenHealthCheckRow(Base):
    __tablename__ = "wb_token_health_checks"

    check_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    account_id: Mapped[str] = mapped_column(String(128), ForeignKey("wb_accounts.account_id"), nullable=False)
    scenario: Mapped[str] = mapped_column(String(32), nullable=False)
    source_status: Mapped[str] = mapped_column(String(16), nullable=False)
    auth_state: Mapped[str] = mapped_column(String(32), nullable=False)
    blocker_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    next_actions: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    capability_snapshot: Mapped[list[dict]] = mapped_column(JSON, nullable=False, default=list)
    checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
