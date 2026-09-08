from __future__ import annotations

import argparse
import json
from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.cabinet.store import get_organization_wb_token_secret
from app.infra.db import get_session_factory, set_tenant_context
from app.platform.advertising.raw import (
    AdvertisingNormalizationError as RawAdvertisingNormalizationError,
)
from app.platform.advertising.service import (
    AdvertisingAccountNotFound,
    AdvertisingNormalizationError,
    AdvertisingService,
)
from app.platform.integrations.wb_credentials import (
    WbCredentialBindingError,
    resolve_bound_wb_credential,
)
from app.platform.integrations.orm import MarketplaceAccountRow
from app.platform.period import Period, PeriodValidationError
from app.wb_api.raw_advertising import (
    RawAdvertisingFetchError,
    fetch_raw_advertising,
)


class RawAdvertisingBackfillError(ValueError):
    def __init__(self, error_code: str) -> None:
        self.error_code = error_code
        super().__init__(error_code)


def _connected_wb_account_id(
    session: Session,
    organization_id: int,
    marketplace_account_id: int | None = None,
    credential_ref: str | None = None,
    wb_token: str | None = None,
    *,
    lock: bool = False,
) -> int:
    if credential_ref is not None:
        try:
            return resolve_bound_wb_credential(
                session,
                organization_id,
                marketplace_account_id=marketplace_account_id,
                credential_ref=credential_ref,
                wb_token=wb_token,
                lock=lock,
            )[0]
        except WbCredentialBindingError:
            raise RawAdvertisingBackfillError("wb_credential_binding_invalid") from None
    set_tenant_context(session, organization_id)
    account_ids = session.scalars(
        select(MarketplaceAccountRow.marketplace_account_id).where(
            MarketplaceAccountRow.organization_id == organization_id,
            MarketplaceAccountRow.marketplace == "wb",
            MarketplaceAccountRow.status == "connected",
        )
    ).all()
    if len(account_ids) != 1:
        raise RawAdvertisingBackfillError(
            "wb_account_missing" if not account_ids else "wb_account_ambiguous"
        )
    account_id = int(account_ids[0])
    if marketplace_account_id is not None and account_id != marketplace_account_id:
        raise RawAdvertisingBackfillError("wb_account_changed")
    return account_id


def _backfill(
    session: Session,
    organization_id: int,
    period: Period,
    wb_token: str,
    marketplace_account_id: int | None,
    credential_ref: str | None,
) -> dict[str, Any]:
    with Session(bind=session.get_bind()) as lookup_session:
        account_id = _connected_wb_account_id(
            lookup_session,
            organization_id,
            marketplace_account_id,
            credential_ref,
            wb_token,
        )

    try:
        fetched = fetch_raw_advertising(period, wb_token=wb_token)
    except RawAdvertisingFetchError:
        raise RawAdvertisingBackfillError("wb_fetch_failed") from None
    if fetched.state != "ready":
        return {
            "state": "partial",
            "expectedRequests": fetched.expected_requests,
            "completedRequests": fetched.completed_requests,
            "failureCodes": list(fetched.failure_codes),
        }

    try:
        current_account_id = _connected_wb_account_id(
            session,
            organization_id,
            account_id,
            credential_ref,
            wb_token,
            lock=credential_ref is not None,
        )
        snapshot = AdvertisingService(session, organization_id).ingest_raw_payload(
            current_account_id,
            period,
            fetched.bundle,
            source_reference="wb_api:raw_backfill",
        )
        return {
            "state": "ready",
            "syncRunId": snapshot.sync_run_id,
            "snapshotChecksum": snapshot.snapshot_checksum,
            "marketplaceAccountId": snapshot.marketplace_account_id,
            "factCount": snapshot.fact_count,
            "campaignCount": snapshot.campaign_count,
            "spendDocumentCount": snapshot.spend_document_count,
            "sourceTotalSpendKopecks": snapshot.source_total_spend_kopecks,
            "documentTotalSpendKopecks": snapshot.document_total_spend_kopecks,
            "expectedRequests": snapshot.expected_request_count,
            "completedRequests": snapshot.completed_request_count,
        }
    finally:
        if session.in_transaction():
            session.rollback()


def backfill_raw_advertising(
    organization_id: int,
    period: Period,
    *,
    marketplace_account_id: int | None = None,
    credential_ref: str | None = None,
    wb_token: str | None = None,
    session: Session | None = None,
) -> dict[str, Any]:
    if session is not None and session.in_transaction():
        raise RawAdvertisingBackfillError("session_transaction_active")
    if organization_id < 1:
        raise RawAdvertisingBackfillError("invalid_organization")
    token = (wb_token or "").strip()
    if not token:
        token = (get_organization_wb_token_secret(organization_id) or "").strip()
    if not token:
        raise RawAdvertisingBackfillError("wb_token_missing")
    if session is not None:
        return _backfill(
            session,
            organization_id,
            period,
            token,
            marketplace_account_id,
            credential_ref,
        )
    with get_session_factory()() as owned_session:
        return _backfill(
            owned_session,
            organization_id,
            period,
            token,
            marketplace_account_id,
            credential_ref,
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Backfill raw canonical WB advertising"
    )
    parser.add_argument("--organization-id", type=int, required=True)
    parser.add_argument("--date-from", type=date.fromisoformat, required=True)
    parser.add_argument("--date-to", type=date.fromisoformat, required=True)
    args = parser.parse_args(argv)
    try:
        result = backfill_raw_advertising(
            args.organization_id, Period(args.date_from, args.date_to)
        )
    except RawAdvertisingBackfillError as exc:
        result = {"state": "failed", "errorCode": exc.error_code}
    except PeriodValidationError:
        result = {"state": "failed", "errorCode": "invalid_period"}
    except (
        AdvertisingAccountNotFound,
        AdvertisingNormalizationError,
        RawAdvertisingNormalizationError,
    ):
        result = {"state": "failed", "errorCode": "invalid_advertising_evidence"}
    print(json.dumps(result, sort_keys=True))
    return 0 if result["state"] == "ready" else 1


if __name__ == "__main__":
    raise SystemExit(main())
