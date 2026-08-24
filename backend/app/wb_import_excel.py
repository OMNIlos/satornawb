from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Any

from app.promotion_excel import _find_column, _int_or_none, _money_kopecks, _normalize_header, _worksheet_rows


@dataclass(frozen=True)
class ParsedCostExcel:
    original_filename: str
    file_hash: str
    rows_total: int
    rows_parsed: int
    items: list[dict[str, Any]]
    status: str
    error_text: str | None = None


@dataclass(frozen=True)
class ParsedStockExcel:
    original_filename: str
    file_hash: str
    rows_total: int
    rows_parsed: int
    items: list[dict[str, Any]]
    status: str
    error_text: str | None = None


def _header_text(value: Any) -> str:
    return _normalize_header(value)


def _value(row: list[str], columns: dict[str, int | None], key: str) -> str:
    column = columns.get(key)
    if column is None or column >= len(row):
        return ""
    return row[column]


def _text_or_none(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _number_or_none(value: Any) -> int | None:
    text = str(value or "").replace("\u00a0", " ").strip()
    if not text:
        return None
    match = re.search(r"-?\d+(?:[\s.,]\d+)*", text)
    if not match:
        return None
    normalized = match.group(0).replace(" ", "").replace(",", ".")
    try:
        return int(round(float(normalized)))
    except ValueError:
        return None


def _find_header(rows: list[list[str]], aliases: dict[str, set[str]], required: set[str]) -> tuple[int, dict[str, int | None]]:
    for index, row in enumerate(rows[:50]):
        headers = [_header_text(value) for value in row]
        columns = {key: _find_column(headers, values) for key, values in aliases.items()}
        if all(columns.get(key) is not None for key in required):
            return index, columns
    return -1, {}


def parse_cost_excel(content: bytes, filename: str) -> ParsedCostExcel:
    file_hash = hashlib.sha256(content).hexdigest()
    try:
        rows = _worksheet_rows(content)
    except Exception as exc:
        return ParsedCostExcel(filename, file_hash, 0, 0, [], "error", f"XLSX не распознан: {exc}")

    aliases = {
        "nm_id": {"nmid", "артикулмп", "артикулмпnmid", "supsku"},
        "vendor_code": {"артпоставщика", "артикулпоставщика", "supplierarticle", "vendorcode", "артикулпродавца"},
        "brand": {"бренд", "brandname"},
        "subject": {"категория", "предмет", "subjectname"},
        "cost": {"себестоимость", "costprice"},
        "p_min": {"минцена", "minprice"},
        "p_max": {"базоваяцена", "максрц", "maxprice"},
        "stock_total": {"остатокшт", "stocktotal"},
    }
    header_index, columns = _find_header(rows, aliases, {"cost"})
    if header_index < 0:
        return ParsedCostExcel(
            filename,
            file_hash,
            max(0, len(rows) - 1),
            0,
            [],
            "error",
            "Не найдена колонка себестоимости",
        )

    items: list[dict[str, Any]] = []
    data_rows = rows[header_index + 1 :]
    for row in data_rows:
        cost = _money_kopecks(_value(row, columns, "cost"))
        p_min = _money_kopecks(_value(row, columns, "p_min"))
        p_max = _money_kopecks(_value(row, columns, "p_max"))
        stock_total = _number_or_none(_value(row, columns, "stock_total"))
        nm_id = _int_or_none(_value(row, columns, "nm_id"))
        vendor_code = _text_or_none(_value(row, columns, "vendor_code"))
        if not vendor_code and nm_id is None:
            continue
        if cost is None and p_min is None and p_max is None and stock_total is None:
            continue
        items.append(
            {
                "nmId": nm_id,
                "vendorCode": vendor_code,
                "brand": _text_or_none(_value(row, columns, "brand")),
                "subjectName": _text_or_none(_value(row, columns, "subject")),
                "cogsKopecks": cost,
                "pMinKopecks": p_min,
                "pMaxKopecks": p_max,
                "stockTotal": stock_total,
            }
        )

    return ParsedCostExcel(
        original_filename=filename,
        file_hash=file_hash,
        rows_total=len(data_rows),
        rows_parsed=len(items),
        items=items,
        status="parsed" if items else "error",
        error_text=None if items else "В файле не найдено строк с артикулом и себестоимостью",
    )


def parse_stock_excel(content: bytes, filename: str) -> ParsedStockExcel:
    file_hash = hashlib.sha256(content).hexdigest()
    try:
        rows = _worksheet_rows(content)
    except Exception as exc:
        return ParsedStockExcel(filename, file_hash, 0, 0, [], "error", f"XLSX не распознан: {exc}")

    aliases = {
        "brand": {"бренд"},
        "subject": {"предмет", "категория"},
        "vendor_code": {"артикулпродавца", "артпоставщика", "supplierarticle", "vendorcode"},
        "barcode": {"баркод", "barcode"},
        "size": {"размервещи", "размер", "techsizename"},
        "in_way_to_client": {"впутидополучателей", "inwaytoclient"},
        "in_way_from_client": {"впутивозвратынаскладwb", "inwayfromclient"},
        "stock_total": {"всегонаходитсянаскладах", "stocktotal", "quantity"},
    }
    header_index, columns = _find_header(rows, aliases, {"vendor_code", "stock_total"})
    if header_index < 0:
        return ParsedStockExcel(
            filename,
            file_hash,
            max(0, len(rows) - 1),
            0,
            [],
            "error",
            "Не найдены колонки артикула продавца и общего остатка",
        )

    headers = [_header_text(value) for value in rows[header_index]]
    fixed_columns = {column for column in columns.values() if column is not None}
    stock_total_column = columns["stock_total"] or 0
    warehouse_columns = [
        index
        for index, header in enumerate(headers)
        if index > stock_total_column and index not in fixed_columns and header
    ]

    aggregated: dict[str, dict[str, Any]] = {}
    data_rows = rows[header_index + 1 :]
    for row in data_rows:
        vendor_code = _text_or_none(_value(row, columns, "vendor_code"))
        if not vendor_code:
            continue
        stock_total = _number_or_none(_value(row, columns, "stock_total"))
        if stock_total is None:
            continue
        item = aggregated.setdefault(
            vendor_code,
            {
                "vendorCode": vendor_code,
                "brand": _text_or_none(_value(row, columns, "brand")),
                "subjectName": _text_or_none(_value(row, columns, "subject")),
                "barcodes": [],
                "sizes": [],
                "stockTotal": 0,
                "inWayToClient": 0,
                "inWayFromClient": 0,
                "warehouses": 0,
            },
        )
        barcode = _text_or_none(_value(row, columns, "barcode"))
        size = _text_or_none(_value(row, columns, "size"))
        if barcode:
            item["barcodes"].append(barcode)
        if size:
            item["sizes"].append(size)
        item["stockTotal"] += stock_total
        item["inWayToClient"] += _number_or_none(_value(row, columns, "in_way_to_client")) or 0
        item["inWayFromClient"] += _number_or_none(_value(row, columns, "in_way_from_client")) or 0
        item["warehouses"] += sum(1 for index in warehouse_columns if index < len(row) and (_number_or_none(row[index]) or 0) > 0)

    items = list(aggregated.values())
    for item in items:
        item["barcodes"] = sorted(set(item["barcodes"]))
        item["sizes"] = sorted(set(item["sizes"]))

    return ParsedStockExcel(
        original_filename=filename,
        file_hash=file_hash,
        rows_total=len(data_rows),
        rows_parsed=len(items),
        items=items,
        status="parsed" if items else "error",
        error_text=None if items else "В файле не найдено строк с артикулами и остатками",
    )
