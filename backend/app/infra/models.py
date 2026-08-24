from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Declarative base for Alembic and runtime models."""


class InfraRuntimeState(Base):
    """
    Minimal Sprint A table for infrastructure validation.

    This table is intentionally small and non-domain-specific: it helps us
    validate migration and DB connectivity flow before business entities are added.
    """

    __tablename__ = "infra_runtime_state"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

