from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infra.models import Base


class BlockerCatalogRow(Base):
    __tablename__ = "source_registry_blockers"

    blocker_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    lifecycle_status: Mapped[str] = mapped_column(String(16), nullable=False)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    owner: Mapped[str] = mapped_column(String(255), nullable=False)
    impact_area: Mapped[str] = mapped_column(String(255), nullable=False)
    resolution_needed: Mapped[str] = mapped_column(Text, nullable=False)
    source_ref: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class FormulaCatalogRow(Base):
    __tablename__ = "source_registry_formulas"

    formula_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    formula_name: Mapped[str] = mapped_column(String(255), nullable=False)
    inputs: Mapped[str] = mapped_column(Text, nullable=False)
    output_units: Mapped[str] = mapped_column(String(255), nullable=False)
    rule: Mapped[str] = mapped_column(Text, nullable=False)
    rounding: Mapped[str] = mapped_column(String(255), nullable=False)
    owner: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    used_by: Mapped[str] = mapped_column(Text, nullable=False)
    blocker_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    source_ref: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class SourceRegistryRow(Base):
    __tablename__ = "source_registry_entries"

    row_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    screen: Mapped[str] = mapped_column(String(128), nullable=False)
    metric_action: Mapped[str] = mapped_column(String(255), nullable=False)
    module: Mapped[str] = mapped_column(String(64), nullable=False)
    source_name: Mapped[str] = mapped_column(Text, nullable=False)
    source_field: Mapped[str] = mapped_column(Text, nullable=False)
    formula_text: Mapped[str] = mapped_column(Text, nullable=False)
    formula_id: Mapped[str] = mapped_column(String(64), ForeignKey("source_registry_formulas.formula_id"), nullable=False)
    refresh_policy: Mapped[str] = mapped_column(String(255), nullable=False)
    fallback_policy: Mapped[str] = mapped_column(Text, nullable=False)
    freshness_confidence: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    blocker_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    critical_for_apply: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    source_ref: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    formula: Mapped[FormulaCatalogRow] = relationship()

