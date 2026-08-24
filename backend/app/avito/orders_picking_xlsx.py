from __future__ import annotations

from datetime import date
from io import BytesIO
from typing import Any
from xml.sax.saxutils import escape
from zipfile import ZIP_DEFLATED, ZipFile

from app.avito.orders import AvitoOrderRow


HEADERS = [
    "№ задания",
    "Фото",
    "Бренд",
    "Наименование",
    "Размер",
    "Цвет",
    "Артикул продавца",
    "Стикер",
    "Баркод",
]

SIZE_HINTS = ["4XL", "3XL", "2XL", "XXL", "XL", "XS", "S", "M", "L"]


def _xlsx_date(value: date) -> str:
    return value.strftime("%d.%m.%Y")


def _col_ref(index: int) -> str:
    result = ""
    while index:
        index, remainder = divmod(index - 1, 26)
        result = chr(65 + remainder) + result
    return result


def _cell(ref: str, value: Any, style: int = 2) -> str:
    text = "" if value is None else str(value)
    if not text:
        return f'<c r="{ref}" s="{style}"/>'
    return f'<c r="{ref}" s="{style}" t="inlineStr"><is><t>{escape(text)}</t></is></c>'


def _row(row_index: int, values: list[Any], style: int = 2) -> str:
    cells = [_cell(f"{_col_ref(column)}{row_index}", value, style) for column, value in enumerate(values, start=1)]
    return f'<row r="{row_index}">{"".join(cells)}</row>'


def _detect_size(title: str) -> str:
    normalized = f" {title.upper()} "
    for size in SIZE_HINTS:
        if f" {size} " in normalized or f"РАЗМЕР {size}" in normalized:
            return size
    return ""


def _picking_rows(orders: list[AvitoOrderRow]) -> list[list[Any]]:
    rows: list[list[Any]] = []
    for order in orders:
        for item in order.items:
            quantity = max(1, int(item.quantity or 1))
            for _ in range(quantity):
                title = item.title or ""
                rows.append(
                    [
                        order.marketplaceId or order.orderId,
                        "",
                        order.accountName or "Авито",
                        title,
                        item.size or _detect_size(title),
                        item.color or "",
                        item.sellerArticle or "",
                        order.trackNumber or "",
                        item.itemId or "",
                    ]
                )
    return rows


def build_avito_orders_picking_xlsx(orders: list[AvitoOrderRow], *, date_from: date) -> bytes:
    rows = _picking_rows(orders)
    sheet_rows = [
        _row(1, [f"Дата: {_xlsx_date(date_from)}"], style=5),
        _row(2, ["Лист подбора Авито"], style=4),
        '<row r="3"/>',
        _row(4, [f"Количество товаров: {len(rows)}"], style=5),
        _row(5, HEADERS, style=1),
    ]
    for offset, values in enumerate(rows, start=6):
        sheet_rows.append(_row(offset, values, style=2))

    sheet_xml = f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <dimension ref="A1:I{max(5, len(rows) + 5)}"/>
  <cols>
    <col min="1" max="1" width="9" customWidth="1"/>
    <col min="2" max="2" width="7.5" customWidth="1"/>
    <col min="3" max="3" width="8" customWidth="1"/>
    <col min="4" max="4" width="14" customWidth="1"/>
    <col min="5" max="5" width="8" customWidth="1"/>
    <col min="6" max="6" width="7" customWidth="1"/>
    <col min="7" max="7" width="10" customWidth="1"/>
    <col min="8" max="8" width="9" customWidth="1"/>
    <col min="9" max="9" width="8" customWidth="1"/>
  </cols>
  <sheetData>
    {"".join(sheet_rows)}
  </sheetData>
  <mergeCells count="4">
    <mergeCell ref="A1:C1"/>
    <mergeCell ref="A2:I2"/>
    <mergeCell ref="A4:D4"/>
    <mergeCell ref="E4:G4"/>
  </mergeCells>
</worksheet>'''

    workbook_xml = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <sheets><sheet name="Лист подбора" sheetId="1" r:id="rId1"/></sheets>
</workbook>'''
    workbook_rels = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
</Relationships>'''
    rels = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>'''
    content_types = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
  <Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
  <Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>
</Types>'''
    styles = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <fonts count="2"><font><sz val="11"/><name val="Calibri"/></font><font><b/><sz val="11"/><name val="Calibri"/></font></fonts>
  <fills count="3"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill><fill><patternFill patternType="solid"><fgColor rgb="FFE7E6E6"/></patternFill></fill></fills>
  <borders count="2"><border/><border><left style="thin"/><right style="thin"/><top style="thin"/><bottom style="thin"/></border></borders>
  <cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>
  <cellXfs count="6">
    <xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>
    <xf numFmtId="0" fontId="1" fillId="2" borderId="1" xfId="0" applyFont="1" applyFill="1" applyBorder="1" applyAlignment="1"><alignment horizontal="center" vertical="center" wrapText="1"/></xf>
    <xf numFmtId="0" fontId="0" fillId="0" borderId="1" xfId="0" applyBorder="1" applyAlignment="1"><alignment vertical="center" wrapText="1"/></xf>
    <xf numFmtId="0" fontId="0" fillId="0" borderId="1" xfId="0" applyBorder="1"/>
    <xf numFmtId="0" fontId="1" fillId="0" borderId="0" xfId="0" applyFont="1" applyAlignment="1"><alignment horizontal="center"/></xf>
    <xf numFmtId="0" fontId="1" fillId="0" borderId="0" xfId="0" applyFont="1"/>
  </cellXfs>
</styleSheet>'''

    buffer = BytesIO()
    with ZipFile(buffer, "w", ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", content_types)
        archive.writestr("_rels/.rels", rels)
        archive.writestr("xl/workbook.xml", workbook_xml)
        archive.writestr("xl/_rels/workbook.xml.rels", workbook_rels)
        archive.writestr("xl/worksheets/sheet1.xml", sheet_xml)
        archive.writestr("xl/styles.xml", styles)
    return buffer.getvalue()
