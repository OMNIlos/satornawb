from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.infra.models import Base


class WbRepricerGoodsCacheRow(Base):
    __tablename__ = "wb_repricer_goods_cache"
    __table_args__ = (
        UniqueConstraint("organization_id", "page_offset", "page_limit", name="uq_wb_repricer_goods_cache_page"),
    )

    cache_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("lk_organizations.organization_id"), nullable=False)
    page_offset: Mapped[int] = mapped_column(Integer, nullable=False)
    page_limit: Mapped[int] = mapped_column(Integer, nullable=False)
    goods_payload: Mapped[list[dict]] = mapped_column(JSON, nullable=False, default=list)
    wb_request_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class WbRepricerSourceCacheRow(Base):
    __tablename__ = "wb_repricer_source_cache"
    __table_args__ = (
        UniqueConstraint("organization_id", "source_key", name="uq_wb_repricer_source_cache_org_key"),
        Index("ix_wb_repricer_source_cache_org_key_fetched", "organization_id", "source_key", "fetched_at"),
    )

    cache_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("lk_organizations.organization_id"), nullable=False)
    source_key: Mapped[str] = mapped_column(String(255), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    revenue_basis: Mapped[str | None] = mapped_column(String(64), nullable=True)
    finance_schema_version: Mapped[str | None] = mapped_column(String(32), nullable=True)
    range_date_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    range_date_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    daily_detail_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    daily_detail_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    daily_detail_deferred_at: Mapped[str | None] = mapped_column(String(64), nullable=True)
    daily_detail_paused_at: Mapped[str | None] = mapped_column(String(64), nullable=True)
    daily_detail_failed_at: Mapped[str | None] = mapped_column(String(64), nullable=True)
    daily_detail_fetched_at: Mapped[str | None] = mapped_column(String(64), nullable=True)
    daily_detail_partial_at: Mapped[str | None] = mapped_column(String(64), nullable=True)
    daily_detail_preserved_at: Mapped[str | None] = mapped_column(String(64), nullable=True)
    daily_detail_preserved_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    daily_detail_requests_completed: Mapped[int | None] = mapped_column(Integer, nullable=True)
    daily_detail_requests_total: Mapped[int | None] = mapped_column(Integer, nullable=True)
    daily_aggregate_dates: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
