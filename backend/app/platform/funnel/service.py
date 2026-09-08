from __future__ import annotations

import hashlib
import json
import uuid
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.infra.db import set_tenant_context
from app.platform.clock import utc_now
from app.platform.funnel.orm import WbFunnelDailyRow, WbFunnelSyncRunRow
from app.platform.funnel.raw import FunnelNormalizationError, normalize_raw_funnel
from app.platform.integrations.orm import MarketplaceAccountRow
from app.platform.period import Period

_ADVISORY_DOMAIN = "wb-funnel-history-v1"
_NORMALIZER_VERSION = "wb-funnel-history-v1"


class FunnelAccountNotFound(LookupError):
    pass


@dataclass(frozen=True, slots=True)
class FunnelSnapshot:
    sync_run_id: str
    marketplace_account_id: int
    period: Period
    snapshot_checksum: str
    normalizer_version: str
    fact_count: int
    expected_request_count: int
    completed_request_count: int
    captured_at: datetime
    last_observed_at: datetime


def _hash(payload: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            payload,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode()
    ).hexdigest()


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _lock_account(
    session: Session, organization_id: int, marketplace_account_id: int
) -> None:
    if session.get_bind().dialect.name != "postgresql":
        return
    key = int.from_bytes(
        hashlib.sha256(
            f"{_ADVISORY_DOMAIN}:{organization_id}:{marketplace_account_id}".encode()
        ).digest()[:8],
        "big",
        signed=True,
    )
    # ponytail: account-wide serialization; split by period only if measured contention appears.
    session.execute(text("SELECT pg_advisory_xact_lock(:lock_key)"), {"lock_key": key})


def _snapshot(row: WbFunnelSyncRunRow) -> FunnelSnapshot:
    return FunnelSnapshot(
        sync_run_id=row.sync_run_id,
        marketplace_account_id=row.marketplace_account_id,
        period=Period(row.date_from, row.date_to),
        snapshot_checksum=row.snapshot_checksum,
        normalizer_version=row.normalizer_version,
        fact_count=row.fact_count,
        expected_request_count=row.expected_request_count,
        completed_request_count=row.completed_request_count,
        captured_at=_utc(row.captured_at),
        last_observed_at=_utc(row.last_observed_at),
    )


class FunnelService:
    def __init__(
        self,
        session: Session,
        organization_id: int,
        *,
        now: Callable[[], datetime] = utc_now,
    ) -> None:
        if organization_id < 1:
            raise FunnelNormalizationError("organization must be positive")
        self.session = session
        self.organization_id = organization_id
        self.now = now

    def _prepare(self) -> None:
        set_tenant_context(self.session, self.organization_id)

    def _account(self, marketplace_account_id: int) -> MarketplaceAccountRow:
        self._prepare()
        account = self.session.scalar(
            select(MarketplaceAccountRow).where(
                MarketplaceAccountRow.organization_id == self.organization_id,
                MarketplaceAccountRow.marketplace_account_id == marketplace_account_id,
                MarketplaceAccountRow.marketplace == "wb",
                MarketplaceAccountRow.status == "connected",
            )
        )
        if account is None:
            raise FunnelAccountNotFound("connected WB marketplace account not found")
        return account

    def ingest_raw_payload(
        self,
        marketplace_account_id: int,
        period: Period,
        bundle: dict[str, Any],
        *,
        source_reference: str,
        observed_at: datetime | None = None,
    ) -> FunnelSnapshot:
        evidence = normalize_raw_funnel(period, bundle)
        if (
            not isinstance(source_reference, str)
            or not (source_ref := source_reference.strip())
            or len(source_ref) > 255
        ):
            raise FunnelNormalizationError("invalid source reference")
        observed = _utc(observed_at or self.now())
        try:
            self._account(marketplace_account_id)
            _lock_account(self.session, self.organization_id, marketplace_account_id)
            existing = self.session.scalar(
                select(WbFunnelSyncRunRow)
                .where(
                    WbFunnelSyncRunRow.organization_id == self.organization_id,
                    WbFunnelSyncRunRow.marketplace_account_id
                    == marketplace_account_id,
                    WbFunnelSyncRunRow.date_from == period.date_from,
                    WbFunnelSyncRunRow.date_to == period.date_to,
                    WbFunnelSyncRunRow.snapshot_checksum
                    == evidence.snapshot_checksum,
                )
                .execution_options(populate_existing=True)
            )
            if existing is not None:
                if _utc(existing.last_observed_at) < observed:
                    existing.last_observed_at = observed
                self.session.commit()
                self._prepare()
                return _snapshot(existing)

            parent = self.session.scalar(
                select(WbFunnelSyncRunRow)
                .where(
                    WbFunnelSyncRunRow.organization_id == self.organization_id,
                    WbFunnelSyncRunRow.marketplace_account_id
                    == marketplace_account_id,
                    WbFunnelSyncRunRow.date_from == period.date_from,
                    WbFunnelSyncRunRow.date_to == period.date_to,
                )
                .order_by(
                    WbFunnelSyncRunRow.last_observed_at.desc(),
                    WbFunnelSyncRunRow.captured_at.desc(),
                    WbFunnelSyncRunRow.sync_run_id.desc(),
                )
                .limit(1)
            )
            request_count = len(evidence.raw_manifest)
            run = WbFunnelSyncRunRow(
                sync_run_id=str(uuid.uuid4()),
                organization_id=self.organization_id,
                marketplace_account_id=marketplace_account_id,
                parent_sync_run_id=parent.sync_run_id if parent else None,
                date_from=period.date_from,
                date_to=period.date_to,
                source_reference=source_ref,
                snapshot_checksum=evidence.snapshot_checksum,
                raw_manifest=evidence.raw_manifest,
                raw_manifest_checksum=evidence.raw_manifest_checksum,
                expected_request_count=request_count,
                completed_request_count=request_count,
                normalizer_version=_NORMALIZER_VERSION,
                fact_count=len(evidence.facts),
                captured_at=observed,
                last_observed_at=observed,
            )
            self.session.add(run)
            self.session.flush()
            self.session.add_all(
                [
                    WbFunnelDailyRow(
                        funnel_daily_id=_hash(
                            {
                                "organization_id": self.organization_id,
                                "marketplace_account_id": marketplace_account_id,
                                "sync_run_id": run.sync_run_id,
                                "source_identity": fact.source_identity,
                            }
                        ),
                        organization_id=self.organization_id,
                        marketplace_account_id=marketplace_account_id,
                        sync_run_id=run.sync_run_id,
                        **asdict(fact),
                    )
                    for fact in evidence.facts
                ]
            )
            self.session.flush()
            stored_count = int(
                self.session.scalar(
                    select(func.count())
                    .select_from(WbFunnelDailyRow)
                    .where(
                        WbFunnelDailyRow.organization_id == self.organization_id,
                        WbFunnelDailyRow.marketplace_account_id
                        == marketplace_account_id,
                        WbFunnelDailyRow.sync_run_id == run.sync_run_id,
                    )
                )
                or 0
            )
            if stored_count != len(evidence.facts):
                raise FunnelNormalizationError("funnel snapshot reconciliation failed")
            self.session.commit()
            self._prepare()
            return _snapshot(run)
        except Exception:
            self.session.rollback()
            self._prepare()
            raise
