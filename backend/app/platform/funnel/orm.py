from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    JSON,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.infra.models import Base
from app.platform.integrations import orm as _integration_models  # noqa: F401


class WbFunnelSyncRunRow(Base):
    __tablename__ = "wb_funnel_sync_runs"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "marketplace_account_id",
            "sync_run_id",
            name="uq_wb_funnel_sync_runs_org_account_id",
        ),
        UniqueConstraint(
            "organization_id",
            "marketplace_account_id",
            "date_from",
            "date_to",
            "snapshot_checksum",
            name="uq_wb_funnel_sync_runs_snapshot",
        ),
        ForeignKeyConstraint(
            ["organization_id", "marketplace_account_id"],
            [
                "marketplace_accounts.organization_id",
                "marketplace_accounts.marketplace_account_id",
            ],
            name="fk_wb_funnel_sync_runs_org_account",
        ),
        ForeignKeyConstraint(
            ["organization_id", "marketplace_account_id", "parent_sync_run_id"],
            [
                "wb_funnel_sync_runs.organization_id",
                "wb_funnel_sync_runs.marketplace_account_id",
                "wb_funnel_sync_runs.sync_run_id",
            ],
            name="fk_wb_funnel_sync_runs_parent",
        ),
        CheckConstraint(
            "date_from <= date_to", name="ck_wb_funnel_sync_runs_period"
        ),
        CheckConstraint(
            "expected_request_count > 0 "
            "AND completed_request_count = expected_request_count "
            "AND fact_count >= 0",
            name="ck_wb_funnel_sync_runs_counts",
        ),
        CheckConstraint(
            "parent_sync_run_id IS NULL OR parent_sync_run_id <> sync_run_id",
            name="ck_wb_funnel_sync_runs_parent_not_self",
        ),
        Index(
            "ix_wb_funnel_sync_runs_exact",
            "organization_id",
            "marketplace_account_id",
            "date_from",
            "date_to",
            "last_observed_at",
        ),
        Index(
            "ix_wb_funnel_sync_runs_parent",
            "organization_id",
            "marketplace_account_id",
            "parent_sync_run_id",
        ),
    )

    sync_run_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    organization_id: Mapped[int] = mapped_column(
        ForeignKey("lk_organizations.organization_id"), nullable=False
    )
    marketplace_account_id: Mapped[int] = mapped_column(Integer, nullable=False)
    parent_sync_run_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    date_from: Mapped[date] = mapped_column(Date, nullable=False)
    date_to: Mapped[date] = mapped_column(Date, nullable=False)
    source_reference: Mapped[str] = mapped_column(String(255), nullable=False)
    snapshot_checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    raw_manifest: Mapped[list[dict[str, object]]] = mapped_column(JSON, nullable=False)
    raw_manifest_checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    expected_request_count: Mapped[int] = mapped_column(Integer, nullable=False)
    completed_request_count: Mapped[int] = mapped_column(Integer, nullable=False)
    normalizer_version: Mapped[str] = mapped_column(String(32), nullable=False)
    fact_count: Mapped[int] = mapped_column(Integer, nullable=False)
    captured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    last_observed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class WbFunnelDailyRow(Base):
    __tablename__ = "wb_funnel_daily"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "marketplace_account_id",
            "sync_run_id",
            "source_identity",
            name="uq_wb_funnel_daily_source_identity",
        ),
        ForeignKeyConstraint(
            ["organization_id", "marketplace_account_id", "sync_run_id"],
            [
                "wb_funnel_sync_runs.organization_id",
                "wb_funnel_sync_runs.marketplace_account_id",
                "wb_funnel_sync_runs.sync_run_id",
            ],
            name="fk_wb_funnel_daily_org_account_run",
            ondelete="CASCADE",
        ),
        CheckConstraint("nm_id > 0", name="ck_wb_funnel_daily_nm_id"),
        CheckConstraint(
            "(open_count IS NULL OR open_count >= 0) "
            "AND (cart_count IS NULL OR cart_count >= 0) "
            "AND (order_count IS NULL OR order_count >= 0) "
            "AND (order_amount_kopecks IS NULL OR order_amount_kopecks >= 0) "
            "AND (buyout_count IS NULL OR buyout_count >= 0) "
            "AND (buyout_amount_kopecks IS NULL OR buyout_amount_kopecks >= 0) "
            "AND (add_to_wishlist_count IS NULL OR add_to_wishlist_count >= 0)",
            name="ck_wb_funnel_daily_metrics",
        ),
        CheckConstraint(
            "open_count IS NOT NULL OR cart_count IS NOT NULL "
            "OR order_count IS NOT NULL OR order_amount_kopecks IS NOT NULL "
            "OR buyout_count IS NOT NULL OR buyout_amount_kopecks IS NOT NULL "
            "OR add_to_wishlist_count IS NOT NULL",
            name="ck_wb_funnel_daily_has_metric",
        ),
        Index(
            "ix_wb_funnel_daily_product_date",
            "organization_id",
            "marketplace_account_id",
            "business_date",
            "nm_id",
            "sync_run_id",
        ),
    )

    funnel_daily_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    organization_id: Mapped[int] = mapped_column(
        ForeignKey("lk_organizations.organization_id"), nullable=False
    )
    marketplace_account_id: Mapped[int] = mapped_column(Integer, nullable=False)
    sync_run_id: Mapped[str] = mapped_column(String(36), nullable=False)
    source_identity: Mapped[str] = mapped_column(String(160), nullable=False)
    payload_checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    business_date: Mapped[date] = mapped_column(Date, nullable=False)
    nm_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str | None] = mapped_column(String(8), nullable=True)
    open_count: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    cart_count: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    order_count: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    order_amount_kopecks: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    buyout_count: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    buyout_amount_kopecks: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    add_to_wishlist_count: Mapped[int | None] = mapped_column(
        BigInteger, nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
