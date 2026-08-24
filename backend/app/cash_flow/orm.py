from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Date, DateTime, Index, Integer, JSON, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.infra.models import Base


class OneCCashFlowJobRow(Base):
    __tablename__ = "one_c_cash_flow_jobs"
    __table_args__ = (
        UniqueConstraint("organization_id", "period_from", "period_to", name="uq_one_c_cash_flow_job_period"),
        Index("ix_one_c_cash_flow_jobs_status_created", "status", "created_at"),
    )

    job_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    organization_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    job_type: Mapped[str] = mapped_column(String(32), nullable=False, default="cash_flow")
    period_from: Mapped[date] = mapped_column(Date, nullable=False)
    period_to: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    requested_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    rows_payload: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    balances_payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    raw_result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
