from __future__ import annotations

from fastapi import APIRouter, Query

from app.contracts.envelopes import DataEnvelope, PaginatedEnvelope
from app.source_registry.schemas import BlockerCatalogItem, FormulaCatalogItem, SourceRegistryItem
from app.source_registry.service import (
    BlockerFilters,
    FormulaFilters,
    SourceRegistryFilters,
    get_unresolved_blocker_ids_for_entries,
    list_blockers,
    list_formulas,
    list_source_registry,
)


router = APIRouter(prefix="/api/v1/source-registry", tags=["source-registry"])


@router.get("/entries", response_model=DataEnvelope[list[SourceRegistryItem]])
def get_registry_entries(
    screen: str | None = None,
    status: str | None = None,
    module: str | None = None,
    blockerId: str | None = None,
    formulaId: str | None = None,
    onlyCritical: bool | None = None,
) -> DataEnvelope[list[SourceRegistryItem]]:
    items, _ = list_source_registry(
        SourceRegistryFilters(
            screen=screen,
            status=status,
            module=module,
            blocker_id=blockerId,
            formula_id=formulaId,
            only_critical=onlyCritical,
        )
    )
    return DataEnvelope(data=items)


@router.get("/entries/paginated", response_model=PaginatedEnvelope[SourceRegistryItem])
def get_registry_entries_paginated(
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    screen: str | None = None,
    status: str | None = None,
    module: str | None = None,
    blockerId: str | None = None,
    formulaId: str | None = None,
    onlyCritical: bool | None = None,
) -> PaginatedEnvelope[SourceRegistryItem]:
    items, total = list_source_registry(
        SourceRegistryFilters(
            screen=screen,
            status=status,
            module=module,
            blocker_id=blockerId,
            formula_id=formulaId,
            only_critical=onlyCritical,
        ),
        limit=limit,
        offset=offset,
    )
    return PaginatedEnvelope(items=items, total=total, limit=limit, offset=offset)


@router.get("/blockers/catalog", response_model=DataEnvelope[list[BlockerCatalogItem]])
def get_blocker_catalog(
    lifecycleStatus: str | None = None,
    blockerIdPrefix: str | None = None,
) -> DataEnvelope[list[BlockerCatalogItem]]:
    items, _ = list_blockers(
        BlockerFilters(
            lifecycle_status=lifecycleStatus,
            blocker_id_prefix=blockerIdPrefix,
        )
    )
    return DataEnvelope(data=items)


@router.get("/blockers/catalog/paginated", response_model=PaginatedEnvelope[BlockerCatalogItem])
def get_blocker_catalog_paginated(
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    lifecycleStatus: str | None = None,
    blockerIdPrefix: str | None = None,
) -> PaginatedEnvelope[BlockerCatalogItem]:
    items, total = list_blockers(
        BlockerFilters(
            lifecycle_status=lifecycleStatus,
            blocker_id_prefix=blockerIdPrefix,
        ),
        limit=limit,
        offset=offset,
    )
    return PaginatedEnvelope(items=items, total=total, limit=limit, offset=offset)


@router.get("/formulas", response_model=DataEnvelope[list[FormulaCatalogItem]])
def get_formula_catalog(
    status: str | None = None,
    formulaId: str | None = None,
) -> DataEnvelope[list[FormulaCatalogItem]]:
    items, _ = list_formulas(FormulaFilters(status=status, formula_id=formulaId))
    return DataEnvelope(data=items)


@router.get("/formulas/paginated", response_model=PaginatedEnvelope[FormulaCatalogItem])
def get_formula_catalog_paginated(
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    status: str | None = None,
    formulaId: str | None = None,
) -> PaginatedEnvelope[FormulaCatalogItem]:
    items, total = list_formulas(FormulaFilters(status=status, formula_id=formulaId), limit=limit, offset=offset)
    return PaginatedEnvelope(items=items, total=total, limit=limit, offset=offset)


@router.get("/entries/unresolved-blockers", response_model=DataEnvelope[list[str]])
def get_unresolved_blockers_for_registry() -> DataEnvelope[list[str]]:
    entries, _ = list_source_registry(SourceRegistryFilters())
    blockers, _ = list_blockers(BlockerFilters())
    return DataEnvelope(data=get_unresolved_blocker_ids_for_entries(entries, blockers))

