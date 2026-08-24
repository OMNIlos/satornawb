from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Iterable, Literal

from app.wb_api.reports_sources_runtime import WbStockRow


HistorySource = Literal["captured", "backfilled"]


@dataclass(frozen=True)
class DailyStockSnapshot:
    snapshotDate: date
    nmId: int
    warehouseName: str
    availableUnits: int
    wasOutOfStock: bool
    source: HistorySource


@dataclass
class _ReportsHistoryState:
    daily_stock: dict[tuple[date, int, str], DailyStockSnapshot] = field(default_factory=dict)


_MEMORY = _ReportsHistoryState()


def _key(snapshot_date: date, nm_id: int, warehouse_name: str) -> tuple[date, int, str]:
    return snapshot_date, nm_id, warehouse_name


def capture_daily_stock_snapshot(snapshot_date: date, rows: Iterable[WbStockRow]) -> list[DailyStockSnapshot]:
    captured: list[DailyStockSnapshot] = []
    for row in rows:
        warehouse_name = row.warehouse_name or "unknown"
        snapshot = DailyStockSnapshot(
            snapshotDate=snapshot_date,
            nmId=row.nm_id,
            warehouseName=warehouse_name,
            availableUnits=row.available_units,
            wasOutOfStock=row.available_units <= 0,
            source="captured",
        )
        _MEMORY.daily_stock[_key(snapshot_date, row.nm_id, warehouse_name)] = snapshot
        captured.append(snapshot)
    return captured


def ensure_daily_stock_history(
    snapshot_date: date,
    rows: Iterable[WbStockRow],
    *,
    lookback_days: int = 7,
) -> dict[int, list[DailyStockSnapshot]]:
    current_rows = list(rows)
    capture_daily_stock_snapshot(snapshot_date, current_rows)

    history_by_nm: dict[int, list[DailyStockSnapshot]] = {}
    for row in current_rows:
        warehouse_name = row.warehouse_name or "unknown"
        per_nm: list[DailyStockSnapshot] = []
        for offset in range(lookback_days - 1, -1, -1):
            day = snapshot_date - timedelta(days=offset)
            stored = _MEMORY.daily_stock.get(_key(day, row.nm_id, warehouse_name))
            if stored is None:
                stored = DailyStockSnapshot(
                    snapshotDate=day,
                    nmId=row.nm_id,
                    warehouseName=warehouse_name,
                    availableUnits=row.available_units,
                    wasOutOfStock=row.available_units <= 0,
                    source="backfilled",
                )
                _MEMORY.daily_stock[_key(day, row.nm_id, warehouse_name)] = stored
            per_nm.append(stored)
        history_by_nm[row.nm_id] = per_nm
    return history_by_nm
