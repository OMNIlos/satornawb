from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Integer, JSON, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.infra.models import Base


class WbAdsReportCacheRow(Base):
    __tablename__ = "wb_ads_report_cache"
    __table_args__ = (
        UniqueConstraint("organization_id", "date_from", "date_to", "group_by", name="uq_wb_ads_report_cache_scope"),
    )

    cache_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("lk_organizations.organization_id"), nullable=False)
    date_from: Mapped[date] = mapped_column(Date(), nullable=False)
    date_to: Mapped[date] = mapped_column(Date(), nullable=False)
    group_by: Mapped[str] = mapped_column(String(32), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class WbAdsCampaignStatusSnapshotRow(Base):
    __tablename__ = "wb_ads_campaign_status_snapshots"
    __table_args__ = (
        UniqueConstraint("organization_id", "advert_id", "fetched_at", name="uq_wb_ads_status_snapshot"),
    )

    snapshot_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("lk_organizations.organization_id"), nullable=False)
    advert_id: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str | None] = mapped_column(String(64), nullable=True)
    advert_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    payment_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    change_time: Mapped[str | None] = mapped_column(String(64), nullable=True)
    raw_payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class WbAdsCampaignBudgetSnapshotRow(Base):
    __tablename__ = "wb_ads_campaign_budget_snapshots"
    __table_args__ = (
        UniqueConstraint("organization_id", "advert_id", "fetched_at", name="uq_wb_ads_budget_snapshot"),
    )

    snapshot_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("lk_organizations.organization_id"), nullable=False)
    advert_id: Mapped[int] = mapped_column(Integer, nullable=False)
    cash_kopecks: Mapped[int | None] = mapped_column(Integer, nullable=True)
    netting_kopecks: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_kopecks: Mapped[int | None] = mapped_column(Integer, nullable=True)
    raw_payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class WbAdsFullstatsDailyRow(Base):
    __tablename__ = "wb_ads_fullstats_daily_rows"

    row_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("lk_organizations.organization_id"), nullable=False)
    report_date: Mapped[date | None] = mapped_column(Date(), nullable=True)
    advert_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    app_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    nm_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    attribution_level: Mapped[str | None] = mapped_column(String(32), nullable=True)
    views: Mapped[int | None] = mapped_column(Integer, nullable=True)
    clicks: Mapped[int | None] = mapped_column(Integer, nullable=True)
    spend_kopecks: Mapped[int | None] = mapped_column(Integer, nullable=True)
    atbs: Mapped[int | None] = mapped_column(Integer, nullable=True)
    orders_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    orders_kopecks: Mapped[int | None] = mapped_column(Integer, nullable=True)
    raw_payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class WbAdsSpendDocumentRow(Base):
    __tablename__ = "wb_ads_spend_documents"

    row_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("lk_organizations.organization_id"), nullable=False)
    upd_num: Mapped[str | None] = mapped_column(String(128), nullable=True)
    upd_time: Mapped[str | None] = mapped_column(String(64), nullable=True)
    advert_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    campaign_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    campaign_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    payment_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    campaign_status: Mapped[str | None] = mapped_column(String(64), nullable=True)
    spend_kopecks: Mapped[int | None] = mapped_column(Integer, nullable=True)
    raw_payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
