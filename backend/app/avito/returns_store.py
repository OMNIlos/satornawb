from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.avito.returns import AvitoReturnCandidate
from app.avito.returns_orm import AvitoReturnItemRow
from app.infra.db import get_session_factory


def _run_db(db_fn):
    try:
        session_factory = get_session_factory()
        with session_factory() as session:
            return db_fn(session)
    except SQLAlchemyError:
        return None


def _norm_identity_part(value: str | None) -> str:
    text = str(value or "").strip().lower().replace("ё", "е")
    text = re.sub(r"[^\w\s]+", " ", text, flags=re.U)
    return re.sub(r"\s+", " ", text).strip()


def return_candidate_identity_key(candidate: AvitoReturnCandidate) -> str:
    account = _norm_identity_part(candidate.accountId)
    item_identity = _norm_identity_part(candidate.itemId)
    if not item_identity:
        item_identity = "|".join(
            part
            for part in (
                _norm_identity_part(candidate.sellerArticle),
                _norm_identity_part(candidate.title),
                _norm_identity_part(candidate.size),
                _norm_identity_part(candidate.color),
            )
            if part
        )
    return "|".join(
        part
        for part in (
            account or "account:none",
            _norm_identity_part(candidate.returnOrderId),
            item_identity or "item:none",
        )
        if part
    )


def _candidate_from_row(row: AvitoReturnItemRow) -> AvitoReturnCandidate:
    last_seen_at = row.last_seen_at.isoformat() if row.last_seen_at else None
    return AvitoReturnCandidate(
        returnOrderId=row.order_id,
        marketplaceId=row.marketplace_id,
        accountId=row.account_id,
        accountName=row.account_name,
        itemId=row.item_id,
        title=row.title,
        sellerArticle=row.seller_article,
        size=row.size,
        color=row.color,
        imageUrl=row.image_url,
        quantity=row.quantity,
        status=row.status,
        returnStatus=row.return_status,
        sourceUpdatedAt=row.source_updated_at,
        lastSeenAt=last_seen_at,
    )


def _apply_candidate(row: AvitoReturnItemRow, candidate: AvitoReturnCandidate, *, now: datetime) -> None:
    row.account_id = candidate.accountId
    row.account_name = candidate.accountName
    row.order_id = candidate.returnOrderId
    row.marketplace_id = candidate.marketplaceId
    row.item_id = candidate.itemId
    row.title = candidate.title
    row.seller_article = candidate.sellerArticle
    row.size = candidate.size
    row.color = candidate.color
    row.image_url = candidate.imageUrl
    row.quantity = candidate.quantity
    row.status = candidate.status
    row.return_status = candidate.returnStatus
    row.source_updated_at = candidate.sourceUpdatedAt
    row.last_payload = candidate.model_dump(mode="json")
    row.last_seen_at = now
    row.updated_at = now


def upsert_return_candidates(organization_id: int, candidates: list[AvitoReturnCandidate]) -> dict[str, int]:
    now = datetime.now(timezone.utc)

    def _db(session: Session) -> dict[str, int]:
        inserted = 0
        updated = 0
        for candidate in candidates:
            identity_key = return_candidate_identity_key(candidate)
            row = session.scalar(
                select(AvitoReturnItemRow).where(
                    AvitoReturnItemRow.organization_id == organization_id,
                    AvitoReturnItemRow.identity_key == identity_key,
                )
            )
            if row is None:
                row = AvitoReturnItemRow(
                    organization_id=organization_id,
                    identity_key=identity_key,
                    account_id=candidate.accountId,
                    account_name=candidate.accountName,
                    order_id=candidate.returnOrderId,
                    marketplace_id=candidate.marketplaceId,
                    item_id=candidate.itemId,
                    title=candidate.title,
                    seller_article=candidate.sellerArticle,
                    size=candidate.size,
                    color=candidate.color,
                    image_url=candidate.imageUrl,
                    quantity=candidate.quantity,
                    status=candidate.status,
                    return_status=candidate.returnStatus,
                    source_updated_at=candidate.sourceUpdatedAt,
                    last_payload=candidate.model_dump(mode="json"),
                    first_seen_at=now,
                    last_seen_at=now,
                    updated_at=now,
                )
                session.add(row)
                inserted += 1
            else:
                _apply_candidate(row, candidate, now=now)
                updated += 1
        session.commit()
        return {"inserted": inserted, "updated": updated}

    return _run_db(_db) or {"inserted": 0, "updated": 0}


def enrich_existing_return_candidates(organization_id: int, candidates: list[AvitoReturnCandidate]) -> dict[str, int]:
    now = datetime.now(timezone.utc)

    def _matches_existing(row: AvitoReturnItemRow, candidate: AvitoReturnCandidate) -> bool:
        if _norm_identity_part(row.account_id) != _norm_identity_part(candidate.accountId):
            return False
        if _norm_identity_part(row.order_id) != _norm_identity_part(candidate.returnOrderId):
            return False
        if row.item_id and candidate.itemId:
            return _norm_identity_part(row.item_id) == _norm_identity_part(candidate.itemId)
        if row.seller_article and candidate.sellerArticle:
            return _norm_identity_part(row.seller_article) == _norm_identity_part(candidate.sellerArticle)
        return bool(row.title and candidate.title and _norm_identity_part(row.title) == _norm_identity_part(candidate.title))

    def _db(session: Session) -> dict[str, int]:
        updated = 0
        for candidate in candidates:
            row = session.scalar(
                select(AvitoReturnItemRow).where(
                    AvitoReturnItemRow.organization_id == organization_id,
                    AvitoReturnItemRow.identity_key == return_candidate_identity_key(candidate),
                )
            )
            if row is None:
                possible_rows = list(
                    session.scalars(
                        select(AvitoReturnItemRow).where(
                            AvitoReturnItemRow.organization_id == organization_id,
                            AvitoReturnItemRow.order_id == candidate.returnOrderId,
                        )
                    ).all()
                )
                row = next((possible for possible in possible_rows if _matches_existing(possible, candidate)), None)
            if row is None:
                continue
            changed = False
            if candidate.itemId and not row.item_id:
                row.item_id = candidate.itemId
                changed = True
            if candidate.title and (not row.title or row.title in {"Товар", "Товар Авито"}):
                row.title = candidate.title
                changed = True
            if candidate.sellerArticle and not row.seller_article:
                row.seller_article = candidate.sellerArticle
                changed = True
            if candidate.size and row.size != candidate.size:
                row.size = candidate.size
                changed = True
            if candidate.color and row.color != candidate.color:
                row.color = candidate.color
                changed = True
            if candidate.imageUrl and row.image_url != candidate.imageUrl:
                row.image_url = candidate.imageUrl
                changed = True
            if changed:
                payload = dict(row.last_payload or {})
                payload.update(candidate.model_dump(mode="json", exclude_none=True))
                row.last_payload = payload
                row.updated_at = now
                updated += 1
        session.commit()
        return {"updated": updated}

    return _run_db(_db) or {"updated": 0}


def list_active_return_candidates(organization_id: int, limit: int = 500) -> list[AvitoReturnCandidate]:
    safe_limit = max(1, min(2000, int(limit)))

    def _db(session: Session) -> list[AvitoReturnCandidate]:
        rows = list(
            session.scalars(
                select(AvitoReturnItemRow)
                .where(AvitoReturnItemRow.organization_id == organization_id)
                .order_by(AvitoReturnItemRow.last_seen_at.desc())
                .limit(safe_limit)
            ).all()
        )
        return [_candidate_from_row(row) for row in rows]

    return _run_db(_db) or []
