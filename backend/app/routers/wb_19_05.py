from __future__ import annotations

from fastapi import APIRouter, Query

from app.contracts.envelopes import PaginatedEnvelope
from vella_wb_19_05.registry import BLOCKER_REGISTRY, BlockerRegistryEntry
from vella_wb_19_05.router import router as reference_router


router = APIRouter(tags=["wb-19-05-runtime-boundary"])


@router.get("/api/v1/source-registry", response_model=list[BlockerRegistryEntry])
def list_blockers_for_demo(
    module: str | None = None,
    status: str | None = None,
) -> list[BlockerRegistryEntry]:
    rows = list(BLOCKER_REGISTRY.values())
    if module is not None and module != "wb":
        rows = [row for row in rows if row.module == module]
    if status is not None:
        rows = [row for row in rows if row.status == status]
    return rows


@router.get(
    "/api/v1/source-registry/blockers/paginated",
    response_model=PaginatedEnvelope[BlockerRegistryEntry],
)
def list_blockers_paginated(
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    module: str | None = None,
    status: str | None = None,
) -> PaginatedEnvelope[BlockerRegistryEntry]:
    rows = list(BLOCKER_REGISTRY.values())
    if module is not None:
        rows = [row for row in rows if row.module == module]
    if status is not None:
        rows = [row for row in rows if row.status == status]
    return PaginatedEnvelope[BlockerRegistryEntry](
        items=rows[offset : offset + limit],
        total=len(rows),
        limit=limit,
        offset=offset,
    )


router.include_router(reference_router)
