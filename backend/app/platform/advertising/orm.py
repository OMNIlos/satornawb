from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
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
    false,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.infra.models import Base
from app.platform.integrations import orm as _integration_models  # noqa: F401


class WbAdvertisingSyncRunRow(Base):
    __tablename__ = "wb_advertising_sync_runs"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "marketplace_account_id",
            "sync_run_id",
            name="uq_wb_advertising_sync_runs_org_account_id",
        ),
        UniqueConstraint(
            "organization_id",
            "marketplace_account_id",
            "source_kind",
            "date_from",
            "date_to",
            "snapshot_checksum",
            name="uq_wb_advertising_sync_runs_snapshot",
        ),
        ForeignKeyConstraint(
            ["organization_id", "marketplace_account_id"],
            [
                "marketplace_accounts.organization_id",
                "marketplace_accounts.marketplace_account_id",
            ],
            name="fk_wb_advertising_sync_runs_org_account",
        ),
        ForeignKeyConstraint(
            ["organization_id", "marketplace_account_id", "parent_sync_run_id"],
            [
                "wb_advertising_sync_runs.organization_id",
                "wb_advertising_sync_runs.marketplace_account_id",
                "wb_advertising_sync_runs.sync_run_id",
            ],
            name="fk_wb_advertising_sync_runs_parent",
        ),
        CheckConstraint(
            "source_kind IN ('finance_promotion', 'ads_fullstats')",
            name="ck_wb_advertising_sync_runs_source",
        ),
        CheckConstraint(
            "evidence_status IN ('raw', 'aggregate_only', 'derived_legacy')",
            name="ck_wb_advertising_sync_runs_evidence",
        ),
        CheckConstraint(
            "date_from <= date_to",
            name="ck_wb_advertising_sync_runs_period",
        ),
        CheckConstraint(
            "fact_count >= 0",
            name="ck_wb_advertising_sync_runs_fact_count",
        ),
        CheckConstraint(
            "parent_sync_run_id IS NULL OR parent_sync_run_id <> sync_run_id",
            name="ck_wb_advertising_sync_runs_parent_not_self",
        ),
        CheckConstraint(
            "campaign_count >= 0 AND spend_document_count >= 0",
            name="ck_wb_advertising_sync_runs_raw_counts",
        ),
        CheckConstraint(
            "(raw_manifest IS NULL AND raw_manifest_checksum IS NULL "
            "AND expected_request_count IS NULL AND completed_request_count IS NULL) OR "
            "(raw_manifest IS NOT NULL AND raw_manifest_checksum IS NOT NULL "
            "AND expected_request_count IS NOT NULL AND completed_request_count IS NOT NULL "
            "AND expected_request_count >= 0 AND completed_request_count >= 0 "
            "AND completed_request_count <= expected_request_count)",
            name="ck_wb_advertising_sync_runs_raw_coverage",
        ),
        Index(
            "ix_wb_advertising_sync_runs_exact",
            "organization_id",
            "marketplace_account_id",
            "date_from",
            "date_to",
            "source_kind",
            "is_materialized",
            "last_observed_at",
        ),
        Index(
            "ix_wb_advertising_sync_runs_parent",
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
    source_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    date_from: Mapped[date] = mapped_column(Date, nullable=False)
    date_to: Mapped[date] = mapped_column(Date, nullable=False)
    source_reference: Mapped[str] = mapped_column(String(255), nullable=False)
    snapshot_checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    raw_manifest: Mapped[list[dict[str, object]] | None] = mapped_column(
        JSON, nullable=True
    )
    raw_manifest_checksum: Mapped[str | None] = mapped_column(String(64), nullable=True)
    expected_request_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    completed_request_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    formula_version: Mapped[str] = mapped_column(String(32), nullable=False)
    source_total_spend_kopecks: Mapped[int] = mapped_column(BigInteger, nullable=False)
    fact_count: Mapped[int] = mapped_column(Integer, nullable=False)
    campaign_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    spend_document_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    document_total_spend_kopecks: Mapped[int | None] = mapped_column(
        BigInteger, nullable=True
    )
    evidence_status: Mapped[str] = mapped_column(String(32), nullable=False)
    is_materialized: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=false()
    )
    captured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    last_observed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class WbAdvertisingFactRow(Base):
    __tablename__ = "wb_advertising_facts"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "marketplace_account_id",
            "sync_run_id",
            "source_identity",
            name="uq_wb_advertising_facts_source_identity",
        ),
        ForeignKeyConstraint(
            ["organization_id", "marketplace_account_id", "sync_run_id"],
            [
                "wb_advertising_sync_runs.organization_id",
                "wb_advertising_sync_runs.marketplace_account_id",
                "wb_advertising_sync_runs.sync_run_id",
            ],
            name="fk_wb_advertising_facts_org_account_run",
            ondelete="CASCADE",
        ),
        CheckConstraint(
            "attribution_level IN "
            "('exact_sku', 'campaign_sku', 'campaign_only', 'unknown')",
            name="ck_wb_advertising_facts_attribution",
        ),
        CheckConstraint(
            "grain IN ('day', 'period')",
            name="ck_wb_advertising_facts_grain",
        ),
        CheckConstraint(
            "date_from <= date_to AND (grain <> 'day' OR date_from = date_to)",
            name="ck_wb_advertising_facts_period",
        ),
        CheckConstraint(
            "fact_scope IN ('account', 'campaign', 'source_sku')",
            name="ck_wb_advertising_facts_scope",
        ),
        CheckConstraint(
            "(fact_scope = 'account' AND campaign_id IS NULL AND nm_id IS NULL) OR "
            "(fact_scope = 'campaign' AND campaign_id IS NOT NULL AND nm_id IS NULL) OR "
            "(fact_scope = 'source_sku' AND nm_id IS NOT NULL)",
            name="ck_wb_advertising_facts_scope_identity",
        ),
        CheckConstraint(
            "(impressions IS NULL OR impressions >= 0) "
            "AND (clicks IS NULL OR clicks >= 0) "
            "AND (cart_adds IS NULL OR cart_adds >= 0) "
            "AND (order_count IS NULL OR order_count >= 0) "
            "AND (order_revenue_kopecks IS NULL OR order_revenue_kopecks >= 0) "
            "AND (cancel_count IS NULL OR cancel_count >= 0)",
            name="ck_wb_advertising_facts_metrics",
        ),
        Index(
            "ix_wb_advertising_facts_run",
            "organization_id",
            "marketplace_account_id",
            "sync_run_id",
        ),
        Index(
            "ix_wb_advertising_facts_product_date",
            "organization_id",
            "marketplace_account_id",
            "nm_id",
            "business_date",
        ),
        Index(
            "ix_wb_advertising_facts_campaign_period",
            "organization_id",
            "marketplace_account_id",
            "date_from",
            "date_to",
            "campaign_id",
            "fact_scope",
            "sync_run_id",
        ),
        Index(
            "ix_wb_advertising_facts_sku_period",
            "organization_id",
            "marketplace_account_id",
            "date_from",
            "date_to",
            "nm_id",
            "fact_scope",
            "sync_run_id",
        ),
    )

    advertising_fact_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    organization_id: Mapped[int] = mapped_column(
        ForeignKey("lk_organizations.organization_id"), nullable=False
    )
    marketplace_account_id: Mapped[int] = mapped_column(Integer, nullable=False)
    sync_run_id: Mapped[str] = mapped_column(String(36), nullable=False)
    source_identity: Mapped[str] = mapped_column(String(160), nullable=False)
    payload_checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    grain: Mapped[str] = mapped_column(String(16), nullable=False)
    date_from: Mapped[date] = mapped_column(Date, nullable=False)
    date_to: Mapped[date] = mapped_column(Date, nullable=False)
    business_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    campaign_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    fact_scope: Mapped[str] = mapped_column(String(16), nullable=False)
    app_type: Mapped[int | None] = mapped_column(Integer, nullable=True)
    nm_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    currency: Mapped[str | None] = mapped_column(String(8), nullable=True)
    attribution_level: Mapped[str] = mapped_column(String(24), nullable=False)
    spend_kopecks: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    impressions: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    clicks: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    cart_adds: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    order_count: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    order_revenue_kopecks: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    cancel_count: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class WbAdvertisingCampaignSnapshotRow(Base):
    __tablename__ = "wb_advertising_campaign_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "marketplace_account_id",
            "sync_run_id",
            "source_identity",
            name="uq_wb_advertising_campaign_snapshots_source_identity",
        ),
        ForeignKeyConstraint(
            ["organization_id", "marketplace_account_id", "sync_run_id"],
            [
                "wb_advertising_sync_runs.organization_id",
                "wb_advertising_sync_runs.marketplace_account_id",
                "wb_advertising_sync_runs.sync_run_id",
            ],
            name="fk_wb_advertising_campaign_snapshots_org_account_run",
            ondelete="CASCADE",
        ),
        CheckConstraint(
            "campaign_id > 0", name="ck_wb_advertising_campaign_snapshots_campaign"
        ),
        Index(
            "ix_wb_advertising_campaign_snapshots_campaign",
            "organization_id",
            "marketplace_account_id",
            "campaign_id",
            "sync_run_id",
        ),
    )

    campaign_snapshot_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    organization_id: Mapped[int] = mapped_column(
        ForeignKey("lk_organizations.organization_id"), nullable=False
    )
    marketplace_account_id: Mapped[int] = mapped_column(Integer, nullable=False)
    sync_run_id: Mapped[str] = mapped_column(String(36), nullable=False)
    source_identity: Mapped[str] = mapped_column(String(160), nullable=False)
    payload_checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    campaign_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    campaign_type: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[int | None] = mapped_column(Integer, nullable=True)
    payment_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    bid_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    member_nm_ids: Mapped[list[int]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class WbAdvertisingSpendDocumentRow(Base):
    __tablename__ = "wb_advertising_spend_documents"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "marketplace_account_id",
            "sync_run_id",
            "source_identity",
            name="uq_wb_advertising_spend_documents_source_identity",
        ),
        ForeignKeyConstraint(
            ["organization_id", "marketplace_account_id", "sync_run_id"],
            [
                "wb_advertising_sync_runs.organization_id",
                "wb_advertising_sync_runs.marketplace_account_id",
                "wb_advertising_sync_runs.sync_run_id",
            ],
            name="fk_wb_advertising_spend_documents_org_account_run",
            ondelete="CASCADE",
        ),
        CheckConstraint(
            "upd_num <> ''", name="ck_wb_advertising_spend_documents_upd_num"
        ),
        CheckConstraint(
            "campaign_id > 0", name="ck_wb_advertising_spend_documents_campaign"
        ),
        Index(
            "ix_wb_advertising_spend_documents_date_campaign",
            "organization_id",
            "marketplace_account_id",
            "business_date",
            "campaign_id",
            "sync_run_id",
        ),
        Index(
            "ix_wb_advertising_spend_documents_source",
            "organization_id",
            "marketplace_account_id",
            "upd_num",
            "campaign_id",
            "upd_time",
        ),
    )

    spend_document_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    organization_id: Mapped[int] = mapped_column(
        ForeignKey("lk_organizations.organization_id"), nullable=False
    )
    marketplace_account_id: Mapped[int] = mapped_column(Integer, nullable=False)
    sync_run_id: Mapped[str] = mapped_column(String(36), nullable=False)
    source_identity: Mapped[str] = mapped_column(String(160), nullable=False)
    payload_checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    upd_num: Mapped[str] = mapped_column(String(128), nullable=False)
    upd_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    business_date: Mapped[date] = mapped_column(Date, nullable=False)
    campaign_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    campaign_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    campaign_type: Mapped[int | None] = mapped_column(Integer, nullable=True)
    payment_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    campaign_status: Mapped[int | None] = mapped_column(Integer, nullable=True)
    currency: Mapped[str | None] = mapped_column(String(8), nullable=True)
    spend_kopecks: Mapped[int] = mapped_column(BigInteger, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
