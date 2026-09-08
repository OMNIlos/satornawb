from datetime import date
from io import BytesIO
from xml.etree import ElementTree as ET
from zipfile import ZipFile

import pytest

from app.avito.orders import AvitoOrderItem, AvitoOrderRow
from app.avito.orders_picking_xlsx import build_avito_orders_picking_xlsx

NS = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}


def render(items):
    order = AvitoOrderRow(
        orderId="000synthetic-order",
        accountName="Синтетический магазин",
        status="synthetic_unknown_status",
        items=items,
    )
    before = order.model_dump()
    content = build_avito_orders_picking_xlsx([order], date_from=date(2026, 9, 8))
    assert order.model_dump() == before
    with ZipFile(BytesIO(content)) as archive:
        assert archive.testzip() is None
        root = ET.fromstring(archive.read("xl/worksheets/sheet1.xml"))
    cells = {cell.attrib["r"]: cell for cell in root.findall(".//x:c", NS)}
    return root, cells


def value(cells, key):
    return cells[key].findtext("x:is/x:t", namespaces=NS)


def test_quantity_expansion_keeps_repeated_listing_and_leading_zero_ids():
    root, cells = render(
        [
            AvitoOrderItem(
                itemId="000synthetic-listing", title="Синтетический товар А", quantity=2
            ),
            AvitoOrderItem(
                itemId="000synthetic-listing", title="Синтетический товар Б", quantity=3
            ),
        ]
    )
    assert root.find("x:dimension", NS).attrib["ref"] == "A1:I10"
    assert value(cells, "A4") == "Количество товаров: 5"
    assert [value(cells, f"D{i}") for i in range(6, 11)] == [
        "Синтетический товар А",
        "Синтетический товар А",
        "Синтетический товар Б",
        "Синтетический товар Б",
        "Синтетический товар Б",
    ]
    for i in range(6, 11):
        assert value(cells, f"A{i}") == "000synthetic-order"
        assert value(cells, f"I{i}") == "000synthetic-listing"
        assert cells[f"I{i}"].attrib["t"] == "inlineStr"


@pytest.mark.parametrize(
    "text", ["=1+1", "+1+1", "-1+1", "@SUM(1)", '<synthetic>&"Текст"']
)
def test_untrusted_cell_text_is_literal_and_xml_safe(text):
    root, cells = render([AvitoOrderItem(title=text, sellerArticle=text)])
    assert value(cells, "D6") == text
    assert value(cells, "G6") == text
    assert cells["D6"].attrib["t"] == "inlineStr"
    assert not root.findall(".//x:f", NS)


def test_more_than_48_rows_are_complete_and_headers_are_stable():
    root, cells = render([AvitoOrderItem(title="Синтетический товар", quantity=65)])
    assert root.find("x:dimension", NS).attrib["ref"] == "A1:I70"
    assert value(cells, "D70") == "Синтетический товар"
    assert value(cells, "A4") == "Количество товаров: 65"
    assert [value(cells, f"{column}5") for column in "ABCDEFGHI"] == [
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


def test_legacy_zero_quantity_currently_expands_to_one_row():
    _, cells = render([AvitoOrderItem(title="Синтетический товар", quantity=0)])
    assert value(cells, "A4") == "Количество товаров: 1"
    assert value(cells, "D6") == "Синтетический товар"


def test_empty_items_have_no_phantom_product_rows():
    root, cells = render([])
    assert root.find("x:dimension", NS).attrib["ref"] == "A1:I5"
    assert value(cells, "A4") == "Количество товаров: 0"
    assert "A6" not in cells
