from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from sqlalchemy import Select, func, or_, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.infra.db import get_engine, get_session_factory
from app.source_registry.orm import BlockerCatalogRow, FormulaCatalogRow, SourceRegistryRow
from app.source_registry.schemas import BlockerCatalogItem, FormulaCatalogItem, SourceRegistryItem
from app.source_registry.seed_loader import (
    BlockerSeed,
    FormulaSeed,
    SourceRegistrySeed,
    _module_from_screen,
    load_blocker_seeds,
    load_formula_seeds,
    load_source_registry_seeds,
)


@dataclass(frozen=True)
class SourceRegistryFilters:
    screen: str | None = None
    status: str | None = None
    module: str | None = None
    blocker_id: str | None = None
    formula_id: str | None = None
    only_critical: bool | None = None


@dataclass(frozen=True)
class BlockerFilters:
    lifecycle_status: str | None = None
    blocker_id_prefix: str | None = None


@dataclass(frozen=True)
class FormulaFilters:
    status: str | None = None
    formula_id: str | None = None


def _seed_bundle() -> tuple[list[BlockerSeed], list[FormulaSeed], list[SourceRegistrySeed]]:
    blocker_seeds = load_blocker_seeds()
    formula_seeds = load_formula_seeds()
    source_seeds, formula_seeds = load_source_registry_seeds(formula_seeds)
    return blocker_seeds, formula_seeds, source_seeds


def _ensure_seeded(session: Session) -> None:
    blocker_seeds, formula_seeds, source_seeds = _seed_bundle()
    session.query(SourceRegistryRow).delete()
    session.query(FormulaCatalogRow).delete()
    session.query(BlockerCatalogRow).delete()
    session.flush()
    session.bulk_save_objects(
        [
            BlockerCatalogRow(
                blocker_id=seed.blocker_id,
                lifecycle_status=seed.lifecycle_status,
                question=seed.question,
                owner=seed.owner,
                impact_area=seed.impact_area,
                resolution_needed=seed.resolution_needed,
                source_ref=seed.source_ref,
            )
            for seed in blocker_seeds
        ]
    )
    session.bulk_save_objects(
        [
            FormulaCatalogRow(
                formula_id=seed.formula_id,
                formula_name=seed.formula_name,
                inputs=seed.inputs,
                output_units=seed.output_units,
                rule=seed.rule,
                rounding=seed.rounding,
                owner=seed.owner,
                status=seed.status,
                used_by=seed.used_by,
                blocker_ids=seed.blocker_ids,
                source_ref=seed.source_ref,
            )
            for seed in formula_seeds
        ]
    )
    session.bulk_save_objects(
        [
            SourceRegistryRow(
                screen=seed.screen,
                metric_action=seed.metric_action,
                module=seed.module,
                source_name=seed.source_name,
                source_field=seed.source_field,
                formula_text=seed.formula_text,
                formula_id=seed.formula_id,
                refresh_policy=seed.refresh_policy,
                fallback_policy=seed.fallback_policy,
                freshness_confidence=seed.freshness_confidence,
                status=seed.status,
                blocker_ids=seed.blocker_ids,
                critical_for_apply=seed.critical_for_apply,
                source_ref=seed.source_ref,
            )
            for seed in source_seeds
        ]
    )
    session.commit()


def _to_blocker_item(row: BlockerCatalogRow) -> BlockerCatalogItem:
    return BlockerCatalogItem(
        blockerId=row.blocker_id,
        lifecycleStatus=row.lifecycle_status,  # type: ignore[arg-type]
        question=row.question,
        owner=row.owner,
        impactArea=row.impact_area,
        resolutionNeeded=row.resolution_needed,
        sourceRef=row.source_ref,
    )


def _to_formula_item(row: FormulaCatalogRow) -> FormulaCatalogItem:
    return FormulaCatalogItem(
        formulaId=row.formula_id,
        formulaName=row.formula_name,
        inputs=row.inputs,
        outputUnits=row.output_units,
        rule=row.rule,
        rounding=row.rounding,
        owner=row.owner,
        status=row.status,  # type: ignore[arg-type]
        usedBy=row.used_by,
        blockerIds=row.blocker_ids,
        sourceRef=row.source_ref,
    )


def _to_registry_item(row: SourceRegistryRow) -> SourceRegistryItem:
    normalized_module = row.module
    if not normalized_module or normalized_module == "wb":
        normalized_module = _module_from_screen(row.screen)
    return SourceRegistryItem(
        rowId=row.row_id,
        screen=row.screen,
        metricAction=row.metric_action,
        module=normalized_module,
        sourceName=row.source_name,
        sourceField=row.source_field,
        formulaText=row.formula_text,
        formulaId=row.formula_id,
        refreshPolicy=row.refresh_policy,
        fallbackPolicy=row.fallback_policy,
        freshnessConfidence=row.freshness_confidence,
        status=row.status,  # type: ignore[arg-type]
        blockerIds=row.blocker_ids,
        criticalForApply=row.critical_for_apply,
        sourceRef=row.source_ref,
    )


def _apply_blocker_filters(stmt: Select[tuple[BlockerCatalogRow]], filters: BlockerFilters) -> Select[tuple[BlockerCatalogRow]]:
    if filters.lifecycle_status:
        stmt = stmt.where(BlockerCatalogRow.lifecycle_status == filters.lifecycle_status)
    if filters.blocker_id_prefix:
        stmt = stmt.where(BlockerCatalogRow.blocker_id.like(f"{filters.blocker_id_prefix}%"))
    return stmt


def _apply_formula_filters(stmt: Select[tuple[FormulaCatalogRow]], filters: FormulaFilters) -> Select[tuple[FormulaCatalogRow]]:
    if filters.status:
        stmt = stmt.where(FormulaCatalogRow.status == filters.status)
    if filters.formula_id:
        stmt = stmt.where(FormulaCatalogRow.formula_id == filters.formula_id)
    return stmt


def _apply_registry_filters(stmt: Select[tuple[SourceRegistryRow]], filters: SourceRegistryFilters) -> Select[tuple[SourceRegistryRow]]:
    if filters.screen:
        stmt = stmt.where(SourceRegistryRow.screen == filters.screen)
    if filters.status:
        stmt = stmt.where(SourceRegistryRow.status == filters.status)
    if filters.module:
        stmt = stmt.where(
            or_(
                SourceRegistryRow.module == filters.module,
                SourceRegistryRow.screen.like(f"%/{filters.module}%"),
            )
        )
    if filters.formula_id:
        stmt = stmt.where(SourceRegistryRow.formula_id == filters.formula_id)
    if filters.only_critical is not None:
        stmt = stmt.where(SourceRegistryRow.critical_for_apply == filters.only_critical)
    return stmt


def _slice(items: list, limit: int | None, offset: int | None) -> list:
    if limit is None and offset is None:
        return items
    start = offset or 0
    end = start + limit if limit is not None else None
    return items[start:end]


def _fallback_blockers(filters: BlockerFilters) -> list[BlockerCatalogItem]:
    seeds = load_blocker_seeds()
    rows = [
        BlockerCatalogItem(
            blockerId=seed.blocker_id,
            lifecycleStatus=seed.lifecycle_status,  # type: ignore[arg-type]
            question=seed.question,
            owner=seed.owner,
            impactArea=seed.impact_area,
            resolutionNeeded=seed.resolution_needed,
            sourceRef=seed.source_ref,
        )
        for seed in seeds
    ]
    if filters.lifecycle_status:
        rows = [row for row in rows if row.lifecycleStatus == filters.lifecycle_status]
    if filters.blocker_id_prefix:
        rows = [row for row in rows if row.blockerId.startswith(filters.blocker_id_prefix)]
    return rows


def _fallback_formulas(filters: FormulaFilters) -> list[FormulaCatalogItem]:
    formula_seeds = load_formula_seeds()
    _, formula_seeds = load_source_registry_seeds(formula_seeds)
    rows = [
        FormulaCatalogItem(
            formulaId=seed.formula_id,
            formulaName=seed.formula_name,
            inputs=seed.inputs,
            outputUnits=seed.output_units,
            rule=seed.rule,
            rounding=seed.rounding,
            owner=seed.owner,
            status=seed.status,  # type: ignore[arg-type]
            usedBy=seed.used_by,
            blockerIds=seed.blocker_ids,
            sourceRef=seed.source_ref,
        )
        for seed in formula_seeds
    ]
    if filters.status:
        rows = [row for row in rows if row.status == filters.status]
    if filters.formula_id:
        rows = [row for row in rows if row.formulaId == filters.formula_id]
    return rows


def _fallback_registry(filters: SourceRegistryFilters) -> list[SourceRegistryItem]:
    formula_seeds = load_formula_seeds()
    source_seeds, _ = load_source_registry_seeds(formula_seeds)
    rows = [
        SourceRegistryItem(
            rowId=index + 1,
            screen=seed.screen,
            metricAction=seed.metric_action,
            module=seed.module,
            sourceName=seed.source_name,
            sourceField=seed.source_field,
            formulaText=seed.formula_text,
            formulaId=seed.formula_id,
            refreshPolicy=seed.refresh_policy,
            fallbackPolicy=seed.fallback_policy,
            freshnessConfidence=seed.freshness_confidence,
            status=seed.status,  # type: ignore[arg-type]
            blockerIds=seed.blocker_ids,
            criticalForApply=seed.critical_for_apply,
            sourceRef=seed.source_ref,
        )
        for index, seed in enumerate(source_seeds)
    ]
    if filters.screen:
        rows = [row for row in rows if row.screen == filters.screen]
    if filters.status:
        rows = [row for row in rows if row.status == filters.status]
    if filters.module:
        rows = [row for row in rows if row.module == filters.module or f"/{filters.module}" in row.screen.strip("`")]
    if filters.formula_id:
        rows = [row for row in rows if row.formulaId == filters.formula_id]
    if filters.only_critical is not None:
        rows = [row for row in rows if row.criticalForApply == filters.only_critical]
    if filters.blocker_id:
        rows = [row for row in rows if filters.blocker_id in row.blockerIds]
    return rows


def _run_db_query(
    query_fn,
):
    try:
        engine = get_engine()
        with engine.connect() as connection:
            connection.exec_driver_sql("SELECT 1")
        session_factory = get_session_factory()
        with session_factory() as session:
            _ensure_seeded(session)
            return query_fn(session)
    except SQLAlchemyError:
        return None


def list_blockers(filters: BlockerFilters, limit: int | None = None, offset: int | None = None) -> tuple[list[BlockerCatalogItem], int]:
    def _query(session: Session) -> tuple[list[BlockerCatalogItem], int]:
        stmt = _apply_blocker_filters(select(BlockerCatalogRow).order_by(BlockerCatalogRow.blocker_id), filters)
        rows = session.scalars(stmt).all()
        items = [_to_blocker_item(row) for row in rows]
        return _slice(items, limit, offset), len(items)

    result = _run_db_query(_query)
    if result is not None:
        return result
    fallback = _fallback_blockers(filters)
    return _slice(fallback, limit, offset), len(fallback)


def list_formulas(filters: FormulaFilters, limit: int | None = None, offset: int | None = None) -> tuple[list[FormulaCatalogItem], int]:
    def _query(session: Session) -> tuple[list[FormulaCatalogItem], int]:
        stmt = _apply_formula_filters(select(FormulaCatalogRow).order_by(FormulaCatalogRow.formula_id), filters)
        rows = session.scalars(stmt).all()
        items = [_to_formula_item(row) for row in rows]
        return _slice(items, limit, offset), len(items)

    result = _run_db_query(_query)
    if result is not None:
        return result
    fallback = _fallback_formulas(filters)
    return _slice(fallback, limit, offset), len(fallback)


def list_source_registry(filters: SourceRegistryFilters, limit: int | None = None, offset: int | None = None) -> tuple[list[SourceRegistryItem], int]:
    def _query(session: Session) -> tuple[list[SourceRegistryItem], int]:
        stmt = _apply_registry_filters(select(SourceRegistryRow).order_by(SourceRegistryRow.row_id), filters)
        rows = session.scalars(stmt).all()
        items = [_to_registry_item(row) for row in rows]
        if filters.module:
            items = [item for item in items if item.module == filters.module or f"/{filters.module}" in item.screen.strip("`")]
        if filters.blocker_id:
            items = [item for item in items if filters.blocker_id in item.blockerIds]
        return _slice(items, limit, offset), len(items)

    result = _run_db_query(_query)
    if result is not None:
        return result
    fallback = _fallback_registry(filters)
    return _slice(fallback, limit, offset), len(fallback)


def get_unresolved_blocker_ids_for_entries(entries: Iterable[SourceRegistryItem], blockers: Iterable[BlockerCatalogItem]) -> list[str]:
    blocker_status = {item.blockerId: item.lifecycleStatus for item in blockers}
    unresolved: set[str] = set()
    for entry in entries:
        for blocker_id in entry.blockerIds:
            if blocker_status.get(blocker_id) == "BLOCKER":
                unresolved.add(blocker_id)
    return sorted(unresolved)
