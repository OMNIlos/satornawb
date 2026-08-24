from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.infra.db import get_engine, get_session_factory
from app.wb_ads_cache.orm import (
    WbAdsCampaignBudgetSnapshotRow,
    WbAdsCampaignStatusSnapshotRow,
    WbAdsFullstatsDailyRow,
    WbAdsReportCacheRow,
    WbAdsSpendDocumentRow,
)

_MEMORY_REPORT_CACHE: dict[tuple[int, str, str, str], dict[str, Any]] = {}


def _run_db(db_fn):
    try:
        engine = get_engine()
        with engine.connect() as connection:
            connection.exec_driver_sql("SELECT 1")
        session_factory = get_session_factory()
        with session_factory() as session:
            return db_fn(session)
    except SQLAlchemyError:
        return None


def _cache_key(organization_id: int, date_from: date, date_to: date, group_by: str) -> tuple[int, str, str, str]:
    return (organization_id, date_from.isoformat(), date_to.isoformat(), group_by)


def get_ads_report_cache(
    *,
    organization_id: int,
    date_from: date,
    date_to: date,
    group_by: str,
) -> dict[str, Any] | None:
    def _db(session: Session) -> dict[str, Any] | None:
        row = session.scalar(
            select(WbAdsReportCacheRow).where(
                WbAdsReportCacheRow.organization_id == organization_id,
                WbAdsReportCacheRow.date_from == date_from,
                WbAdsReportCacheRow.date_to == date_to,
                WbAdsReportCacheRow.group_by == group_by,
            )
        )
        if row is None:
            return None
        payload = dict(row.payload or {})
        payload.setdefault("cache", {})
        payload["cache"].update(
            {
                "status": "hit",
                "fetchedAt": row.fetched_at.isoformat(),
                "dateFrom": row.date_from.isoformat(),
                "dateTo": row.date_to.isoformat(),
                "groupBy": row.group_by,
            }
        )
        return payload

    result = _run_db(_db)
    if result is not None:
        return result
    cached = _MEMORY_REPORT_CACHE.get(_cache_key(organization_id, date_from, date_to, group_by))
    if cached is None:
        return None
    payload = dict(cached)
    payload.setdefault("cache", {})
    payload["cache"] = dict(payload["cache"])
    payload["cache"]["status"] = "hit"
    return payload


def save_ads_report_cache(
    *,
    organization_id: int,
    date_from: date,
    date_to: date,
    group_by: str,
    payload: dict[str, Any],
    fetched_at: datetime | None = None,
) -> dict[str, Any]:
    now = fetched_at or datetime.now(timezone.utc)
    stored_payload = dict(payload)
    stored_payload.setdefault("cache", {})
    stored_payload["cache"].update(
        {
            "status": "refreshed",
            "fetchedAt": now.isoformat(),
            "dateFrom": date_from.isoformat(),
            "dateTo": date_to.isoformat(),
            "groupBy": group_by,
        }
    )

    def _db(session: Session) -> dict[str, Any]:
        row = session.scalar(
            select(WbAdsReportCacheRow).where(
                WbAdsReportCacheRow.organization_id == organization_id,
                WbAdsReportCacheRow.date_from == date_from,
                WbAdsReportCacheRow.date_to == date_to,
                WbAdsReportCacheRow.group_by == group_by,
            )
        )
        if row is None:
            row = WbAdsReportCacheRow(
                organization_id=organization_id,
                date_from=date_from,
                date_to=date_to,
                group_by=group_by,
                payload=stored_payload,
                fetched_at=now,
                updated_at=now,
            )
            session.add(row)
        else:
            row.payload = stored_payload
            row.fetched_at = now
            row.updated_at = now
        session.commit()
        return stored_payload

    result = _run_db(_db)
    if result is not None:
        return result
    _MEMORY_REPORT_CACHE[_cache_key(organization_id, date_from, date_to, group_by)] = stored_payload
    return stored_payload


def save_ads_history_snapshots(
    *,
    organization_id: int,
    rows: list[dict[str, Any]],
    daily_rows: list[dict[str, Any]] | None = None,
    spend_documents: list[dict[str, Any]] | None = None,
    fetched_at: datetime | None = None,
) -> None:
    now = fetched_at or datetime.now(timezone.utc)
    status_rows: dict[int, dict[str, Any]] = {}
    budget_rows: dict[int, dict[str, Any]] = {}
    for row in rows:
        try:
            advert_id = int(row.get("campaignId") or 0)
        except (TypeError, ValueError):
            continue
        if advert_id <= 0:
            continue
        status_rows[advert_id] = {
            "status": row.get("campaignStatus"),
            "advert_type": row.get("campaignType"),
            "payment_type": row.get("paymentType"),
            "change_time": row.get("campaignChangeTime"),
            "raw_payload": {
                "campaignName": row.get("campaignName"),
                "campaignStatus": row.get("campaignStatus"),
                "campaignType": row.get("campaignType"),
                "paymentType": row.get("paymentType"),
                "campaignChangeTime": row.get("campaignChangeTime"),
            },
        }
        if row.get("budgetTotalKopecks") is not None or row.get("budgetCashKopecks") is not None or row.get("budgetNettingKopecks") is not None:
            budget_rows[advert_id] = {
                "cash_kopecks": row.get("budgetCashKopecks"),
                "netting_kopecks": row.get("budgetNettingKopecks"),
                "total_kopecks": row.get("budgetTotalKopecks"),
                "raw_payload": {
                    "cashKopecks": row.get("budgetCashKopecks"),
                    "nettingKopecks": row.get("budgetNettingKopecks"),
                    "totalKopecks": row.get("budgetTotalKopecks"),
                },
            }

    def _db(session: Session) -> None:
        for advert_id, item in status_rows.items():
            session.add(
                WbAdsCampaignStatusSnapshotRow(
                    organization_id=organization_id,
                    advert_id=advert_id,
                    status=str(item["status"]) if item["status"] is not None else None,
                    advert_type=str(item["advert_type"]) if item["advert_type"] is not None else None,
                    payment_type=str(item["payment_type"]) if item["payment_type"] is not None else None,
                    change_time=str(item["change_time"]) if item["change_time"] is not None else None,
                    raw_payload=item["raw_payload"],
                    fetched_at=now,
                )
            )
        for advert_id, item in budget_rows.items():
            session.add(
                WbAdsCampaignBudgetSnapshotRow(
                    organization_id=organization_id,
                    advert_id=advert_id,
                    cash_kopecks=item["cash_kopecks"],
                    netting_kopecks=item["netting_kopecks"],
                    total_kopecks=item["total_kopecks"],
                    raw_payload=item["raw_payload"],
                    fetched_at=now,
                )
            )
        for item in daily_rows or []:
            if not isinstance(item, dict):
                continue
            try:
                advert_id = int(item.get("campaignId")) if item.get("campaignId") is not None else None
            except (TypeError, ValueError):
                advert_id = None
            try:
                nm_id = int(item.get("skuId")) if item.get("skuId") is not None else None
            except (TypeError, ValueError):
                nm_id = None
            try:
                report_date = date.fromisoformat(str(item.get("date"))) if item.get("date") else None
            except ValueError:
                report_date = None
            session.add(
                WbAdsFullstatsDailyRow(
                    organization_id=organization_id,
                    report_date=report_date,
                    advert_id=advert_id,
                    app_type=str(item.get("appType")) if item.get("appType") is not None else None,
                    nm_id=nm_id,
                    attribution_level=str(item.get("attributionLevel")) if item.get("attributionLevel") is not None else None,
                    views=item.get("impressions"),
                    clicks=item.get("clicks"),
                    spend_kopecks=item.get("adSpendKopecks"),
                    atbs=item.get("cartAdds"),
                    orders_count=item.get("ordersCount"),
                    orders_kopecks=item.get("ordersKopecks"),
                    raw_payload=item,
                    fetched_at=now,
                )
            )
        for item in spend_documents or []:
            if not isinstance(item, dict):
                continue
            try:
                advert_id = int(item.get("campaignId")) if item.get("campaignId") is not None else None
            except (TypeError, ValueError):
                advert_id = None
            session.add(
                WbAdsSpendDocumentRow(
                    organization_id=organization_id,
                    upd_num=str(item.get("updNum")) if item.get("updNum") is not None else None,
                    upd_time=str(item.get("updTime")) if item.get("updTime") is not None else None,
                    advert_id=advert_id,
                    campaign_name=str(item.get("campaignName")) if item.get("campaignName") is not None else None,
                    campaign_type=str(item.get("campaignType")) if item.get("campaignType") is not None else None,
                    payment_type=str(item.get("paymentType")) if item.get("paymentType") is not None else None,
                    campaign_status=str(item.get("campaignStatus")) if item.get("campaignStatus") is not None else None,
                    spend_kopecks=item.get("adSpendKopecks"),
                    raw_payload=item,
                    fetched_at=now,
                )
            )
        session.commit()

    if status_rows or budget_rows or daily_rows or spend_documents:
        _run_db(_db)
