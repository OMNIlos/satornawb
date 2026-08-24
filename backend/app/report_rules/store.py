from __future__ import annotations

import logging
from copy import deepcopy
from datetime import datetime, timezone
from typing import Callable, TypeVar

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.infra.db import get_engine, get_session_factory
from app.report_rules.orm import WbReportRuleProfileRow
from app.report_rules.presets import preset_config
from app.report_rules.schemas import PresetName, ReportRuleProfileView, ReportRulesConfig


logger = logging.getLogger(__name__)
T = TypeVar("T")
_MEMORY: dict[int, list[ReportRuleProfileView]] = {}


class ProfileVersionConflict(RuntimeError):
    def __init__(self, current_version: int):
        super().__init__(f"report rules version conflict: current={current_version}")
        self.current_version = current_version


def _run_db(callback: Callable[[Session], T]) -> T | None:
    try:
        engine = get_engine()
        with engine.connect() as connection:
            connection.exec_driver_sql("SELECT 1")
        with get_session_factory()() as session:
            return callback(session)
    except SQLAlchemyError:
        logger.exception("Report rules database operation failed")
        return None


def _view(row: WbReportRuleProfileRow) -> ReportRuleProfileView:
    return ReportRuleProfileView(
        profileId=row.profile_id,
        organizationId=row.organization_id,
        version=row.version,
        name=row.name,
        preset=row.preset,
        config=ReportRulesConfig.model_validate(row.config_json),
        createdByUserId=row.created_by_user_id,
        createdAt=row.created_at,
        isActive=row.is_active,
    )


def _default(organization_id: int) -> ReportRuleProfileView:
    return ReportRuleProfileView(
        profileId=None,
        organizationId=organization_id,
        version=1,
        name="Стандартный профиль",
        preset="standard",
        config=preset_config("standard"),
        createdByUserId=None,
        createdAt=None,
        isActive=True,
    )


def load_active_profile(organization_id: int) -> ReportRuleProfileView:
    def query(session: Session) -> ReportRuleProfileView | None:
        row = session.scalar(
            select(WbReportRuleProfileRow).where(
                WbReportRuleProfileRow.organization_id == organization_id,
                WbReportRuleProfileRow.is_active.is_(True),
            )
        )
        return _view(row) if row else None

    stored = _run_db(query)
    if stored is not None:
        return stored
    history = _MEMORY.get(organization_id, [])
    return history[0].model_copy(deep=True) if history else _default(organization_id)


def list_profile_history(organization_id: int, limit: int = 20) -> list[ReportRuleProfileView]:
    def query(session: Session) -> list[ReportRuleProfileView]:
        rows = session.scalars(
            select(WbReportRuleProfileRow)
            .where(WbReportRuleProfileRow.organization_id == organization_id)
            .order_by(WbReportRuleProfileRow.version.desc())
            .limit(limit)
        ).all()
        return [_view(row) for row in rows]

    stored = _run_db(query)
    if stored is not None:
        return stored
    return [item.model_copy(deep=True) for item in _MEMORY.get(organization_id, [])[:limit]]


def activate_profile(
    organization_id: int,
    user_id: str,
    expected_version: int,
    preset: PresetName,
    name: str,
    config: ReportRulesConfig,
) -> ReportRuleProfileView:
    payload = config.model_dump(mode="json")

    def write(session: Session) -> ReportRuleProfileView:
        current = session.scalar(
            select(WbReportRuleProfileRow)
            .where(WbReportRuleProfileRow.organization_id == organization_id, WbReportRuleProfileRow.is_active.is_(True))
            .with_for_update()
        )
        current_version = current.version if current else 1
        if current_version != expected_version:
            raise ProfileVersionConflict(current_version)
        if current:
            current.is_active = False
        row = WbReportRuleProfileRow(
            organization_id=organization_id,
            version=current_version + 1,
            name=name,
            preset=preset,
            config_json=payload,
            created_by_user_id=user_id,
            is_active=True,
        )
        session.add(row)
        session.commit()
        session.refresh(row)
        return _view(row)

    stored = _run_db(write)
    if stored is not None:
        return stored

    history = _MEMORY.setdefault(organization_id, [])
    current = history[0] if history else _default(organization_id)
    if current.version != expected_version:
        raise ProfileVersionConflict(current.version)
    for item in history:
        item.isActive = False
    saved = ReportRuleProfileView(
        profileId=-(len(history) + 1),
        organizationId=organization_id,
        version=current.version + 1,
        name=name,
        preset=preset,
        config=deepcopy(config),
        createdByUserId=user_id,
        createdAt=datetime.now(timezone.utc),
        isActive=True,
    )
    history.insert(0, saved)
    return saved.model_copy(deep=True)
