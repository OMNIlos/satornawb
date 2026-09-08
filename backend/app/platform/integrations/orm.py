from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.cabinet import orm as _cabinet_models  # noqa: F401
from app.infra.models import Base


class MarketplaceAccountRow(Base):
    __tablename__ = "marketplace_accounts"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "marketplace",
            "external_account_id",
            name="uq_marketplace_accounts_org_marketplace_external",
        ),
        UniqueConstraint("organization_id", "marketplace_account_id", name="uq_marketplace_accounts_org_id"),
    )

    marketplace_account_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("lk_organizations.organization_id"), nullable=False)
    marketplace: Mapped[str] = mapped_column(String(16), nullable=False)
    external_account_id: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="disconnected")
    credential_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
