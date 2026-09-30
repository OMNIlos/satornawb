from __future__ import annotations

from datetime import date, datetime, timezone
from io import BytesIO
from typing import Any, Callable
from urllib.parse import urlsplit
from xml.sax.saxutils import escape
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

import httpx

from app.avito.orders import AvitoOrderRow

HEADERS = [
    "Номер заказа",
    "№ задания",
    "Номер отправления",
    "Фото",
    "Бренд",
    "Наименование",
    "Кол-во",
    "Размер",
    "Цвет",
    "Артикул продавца",
    "Доставка",
    "Стикер",
    "Баркод",
]
RETURN_HEADERS = ["Место получения возврата", "Срок получения", "Код возврата"]


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
    # Reject XML 1.0-invalid input rather than emit a corrupt workbook or drop text.
    if any(
        not (
            code in (9, 10, 13)
            or 0x20 <= code <= 0xD7FF
            or 0xE000 <= code <= 0xFFFD
            or 0x10000 <= code <= 0x10FFFF
        )
        for code in map(ord, text)
    ):
        raise ValueError("Invalid XML character in XLSX text")
    if not text:
        return f'<c r="{ref}" s="{style}"/>'
    return f'<c r="{ref}" s="{style}" t="inlineStr"><is><t>{escape(text)}</t></is></c>'


def _row(row_index: int, values: list[Any], style: int = 2, *, image: bool = False) -> str:
    cells = [_cell(f"{_col_ref(column)}{row_index}", value, style) for column, value in enumerate(values, start=1)]
    height = ' ht="50" customHeight="1"' if image else ""
    return f'<row r="{row_index}"{height}>{"".join(cells)}</row>'


def _picking_rows(orders: list[AvitoOrderRow], *, returns: bool = False) -> list[tuple[list[Any], str | None]]:
    rows: list[tuple[list[Any], str | None]] = []
    for order in orders:
        for item in order.items:
            if item.quantity <= 0:
                continue
            values = [
                order.orderId,
                order.jobNumber or order.marketplaceId or "—",
                order.shipmentNumber or "—",
                "",
                item.brand or "—",
                item.title or "—",
                item.quantity,
                item.size or "—",
                item.color or "—",
                item.sellerArticle or "—",
                order.deliveryService or "—",
                order.stickerNumber or "—",
                item.barcode or "—",
            ]
            if returns:
                values += [order.returnPickupPlace or "—", order.returnPickupDeadline or "—", order.returnPickupCode or "—"]
            rows.append((values, item.imageUrl))
    return rows


def _load_image(url: str) -> tuple[bytes, str] | None:
    try:
        parsed = urlsplit(url)
        if parsed.scheme != "https" or parsed.username or parsed.password or parsed.port not in (None, 443):
            return None
        host = (parsed.hostname or "").lower()
        if host != "img.avito.st" and not host.endswith(".img.avito.st"):
            return None
        with httpx.Client(timeout=httpx.Timeout(5, connect=2), follow_redirects=False) as client:
            with client.stream("GET", url) as response:
                if response.status_code != 200:
                    return None
                content_type = response.headers.get("content-type", "").split(";")[0].lower()
                if content_type not in {"image/jpeg", "image/png"}:
                    return None
                content = bytearray()
                for chunk in response.iter_bytes():
                    content.extend(chunk)
                    if len(content) > 2_000_000:
                        return None
        data = bytes(content)
        if content_type == "image/png" and data.startswith(b"\x89PNG\r\n\x1a\n"):
            return data, "png"
        if content_type == "image/jpeg" and data.startswith(b"\xff\xd8\xff"):
            return data, "jpeg"
    except (httpx.HTTPError, ValueError):
        pass
    return None


def build_avito_orders_picking_xlsx(
    orders: list[AvitoOrderRow], *, date_from: date, as_of: str | None = None,
    returns: bool = False, image_loader: Callable[[str], tuple[bytes, str] | None] = _load_image,
) -> bytes:
    rows = _picking_rows(orders, returns=returns)
    headers = HEADERS + (RETURN_HEADERS if returns else [])
    title = "Лист возвратов Авито" if returns else "Лист подбора Авито"
    observed = as_of or datetime.now(timezone.utc).isoformat()
    sheet_rows = [
        _row(1, [f"Снимок: {observed}"], style=5),
        _row(2, [title], style=4),
        '<row r="3"/>',
        _row(4, [f"Количество позиций: {sum(int(values[6]) for values, _ in rows)}"], style=5),
        _row(5, headers, style=1),
    ]
    media: dict[str, tuple[int, bytes, str]] = {}
    anchors: list[str] = []
    for offset, (values, image_url) in enumerate(rows, start=6):
        if image_url and image_url not in media:
            try:
                loaded = image_loader(image_url)
            except Exception:
                loaded = None
            if loaded and loaded[1] in {"png", "jpeg"}:
                media[image_url] = (len(media) + 1, loaded[0], loaded[1])
        image_id = media.get(image_url or "", (0, b"", ""))[0]
        if image_id:
            anchors.append(f'''<xdr:oneCellAnchor><xdr:from><xdr:col>3</xdr:col><xdr:colOff>0</xdr:colOff><xdr:row>{offset - 1}</xdr:row><xdr:rowOff>0</xdr:rowOff></xdr:from><xdr:ext cx="571500" cy="571500"/><xdr:pic><xdr:nvPicPr><xdr:cNvPr id="{offset}" name="Photo {offset}"/><xdr:cNvPicPr/></xdr:nvPicPr><xdr:blipFill><a:blip r:embed="rId{image_id}"/><a:stretch><a:fillRect/></a:stretch></xdr:blipFill><xdr:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="571500" cy="571500"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom></xdr:spPr></xdr:pic><xdr:clientData/></xdr:oneCellAnchor>''')
        sheet_rows.append(_row(offset, values, style=2, image=bool(image_id)))

    sheet_xml = f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <dimension ref="A1:{_col_ref(len(headers))}{max(5, len(rows) + 5)}"/>
  <cols>
    <col min="1" max="{len(headers)}" width="18" customWidth="1"/>
    <col min="4" max="4" width="12" customWidth="1"/>
    <col min="6" max="6" width="36" customWidth="1"/>
  </cols>
  <sheetData>
    {"".join(sheet_rows)}
  </sheetData>
  <mergeCells count="3">
    <mergeCell ref="A1:F1"/>
    <mergeCell ref="A2:{_col_ref(len(headers))}2"/>
    <mergeCell ref="A4:F4"/>
  </mergeCells>
  {'<drawing r:id="rId1"/>' if anchors else ''}
</worksheet>'''

    workbook_xml = f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <sheets><sheet name="{'Возвраты' if returns else 'Лист подбора'}" sheetId="1" r:id="rId1"/></sheets>
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
    content_types = f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Default Extension="png" ContentType="image/png"/>
  <Default Extension="jpeg" ContentType="image/jpeg"/>
  <Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
  <Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
  <Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>
  {'<Override PartName="/xl/drawings/drawing1.xml" ContentType="application/vnd.openxmlformats-officedocument.drawing+xml"/>' if anchors else ''}
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
        parts = [
            ("[Content_Types].xml", content_types),
            ("_rels/.rels", rels),
            ("xl/workbook.xml", workbook_xml),
            ("xl/_rels/workbook.xml.rels", workbook_rels),
            ("xl/worksheets/sheet1.xml", sheet_xml),
            ("xl/styles.xml", styles),
        ]
        if anchors:
            parts.extend([
                ("xl/worksheets/_rels/sheet1.xml.rels", '''<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/drawing" Target="../drawings/drawing1.xml"/></Relationships>'''),
                ("xl/drawings/drawing1.xml", f'''<?xml version="1.0" encoding="UTF-8"?><xdr:wsDr xmlns:xdr="http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing" xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">{"".join(anchors)}</xdr:wsDr>'''),
                ("xl/drawings/_rels/drawing1.xml.rels", f'''<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">{"".join(f'<Relationship Id="rId{index}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="../media/image{index}.{extension}"/>' for index, _data, extension in media.values())}</Relationships>'''),
            ])
            parts.extend((f"xl/media/image{index}.{extension}", data) for index, data, extension in media.values())
        for name, content in parts:
            # Fixed ZIP epoch keeps retries byte-stable within the same renderer runtime.
            member = ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            member.compress_type = ZIP_DEFLATED
            archive.writestr(member, content)
    return buffer.getvalue()
