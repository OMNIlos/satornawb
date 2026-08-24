from __future__ import annotations

from io import BytesIO
from zipfile import ZIP_DEFLATED, ZipFile

from app.promotion_excel import normalized_filename, parse_promotion_excel
from app.routers.wb_repricer_bff import _find_promotion_for_file, _imported_promotion_from_excel


def _xlsx_bytes(rows: list[list[str]]) -> bytes:
    def col(index: int) -> str:
        value = ""
        index += 1
        while index:
            index, remainder = divmod(index - 1, 26)
            value = chr(65 + remainder) + value
        return value

    sheet_rows: list[str] = []
    for row_index, row in enumerate(rows, start=1):
        cells = [
            f'<c r="{col(col_index)}{row_index}" t="inlineStr"><is><t>{value}</t></is></c>'
            for col_index, value in enumerate(row)
        ]
        sheet_rows.append(f'<row r="{row_index}">{"".join(cells)}</row>')
    sheet = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f'<sheetData>{"".join(sheet_rows)}</sheetData>'
        "</worksheet>"
    )
    buffer = BytesIO()
    with ZipFile(buffer, "w", ZIP_DEFLATED) as archive:
        archive.writestr("xl/worksheets/sheet1.xml", sheet)
    return buffer.getvalue()


def test_parse_promotion_excel_extracts_thresholds_by_headers():
    parsed = parse_promotion_excel(
        _xlsx_bytes(
            [
                ["NmId", "Артикул продавца", "Текущая цена", "Цена для участия", "Скидка для участия"],
                ["123456", "FBBT_42", "1290", "1148", "18"],
            ]
        ),
        "Весенняя распродажа.xlsx",
    )

    assert parsed.status == "parsed"
    assert parsed.rows_parsed == 1
    assert parsed.thresholds[0]["nmId"] == 123456
    assert parsed.thresholds[0]["vendorCode"] == "FBBT_42"
    assert parsed.thresholds[0]["promoThresholdKopecks"] == 114_800


def test_parse_promotion_excel_reads_wb_auto_promo_export_prices():
    parsed = parse_promotion_excel(
        _xlsx_bytes(
            [
                [
                    "Товар уже участвует в акции",
                    "Бренд",
                    "Предмет",
                    "Наименование",
                    "Артикул поставщика",
                    "Артикул WB",
                    "Последний баркод",
                    "Количество дней на сайте",
                    "Оборачиваемость",
                    "Остаток товара на складах Wb (шт.)",
                    "Остаток товара на складе продавца Wb (шт.)",
                    "Плановая цена для акции",
                    "Текущая розничная цена",
                    "Валюта",
                    "Минимальная цена для применения скидки по автоакции",
                    "Минимальная цена: осталось дней",
                    "Блокировка применения скидки по автоакции",
                    "Блокировка изменения скидки для участия в автоакции: осталось дней",
                    "Текущая скидка на сайте, %",
                    "Загружаемая скидка для участия в акции",
                    "Статус",
                ],
                [
                    "Нет",
                    "Simple Club",
                    "Футболки",
                    "Футболка с принтом",
                    "Фч_sc_014",
                    "322322522",
                    "2042685835254",
                    "494",
                    "1",
                    "0",
                    "1916",
                    "1620",
                    "2533",
                    "RUB",
                    "",
                    "",
                    "Да",
                    "Бессрочно",
                    "33",
                    "37",
                    "Не участвует: стоит блокировка на снижение цены",
                ],
            ]
        ),
        "Товары_для_исключения_из_акции_Жаркие_скидки_автоматические_скидки.xlsx",
    )

    assert parsed.status == "parsed"
    assert parsed.rows_parsed == 1
    assert parsed.thresholds[0]["nmId"] == 322322522
    assert parsed.thresholds[0]["vendorCode"] == "Фч_sc_014"
    assert parsed.thresholds[0]["promoThresholdKopecks"] == 162_000
    assert parsed.thresholds[0]["currentPriceKopecks"] == 253_300
    assert parsed.thresholds[0]["promoThresholdDiscountPct"] == 37
    assert parsed.thresholds[0]["wbStatus"] == "Не участвует: стоит блокировка на снижение цены"


def test_normalized_filename_strips_wb_auto_promo_export_prefix():
    assert (
        normalized_filename("Товары_для_исключения_из_акции_Жаркие_скидки_автоматические_скидки.xlsx")
        == normalized_filename("Жаркие скидки автоматические скидки")
    )


def test_unmatched_valid_wb_excel_can_become_imported_promotion():
    parsed = parse_promotion_excel(
        _xlsx_bytes(
            [
                ["Артикул WB", "Плановая цена для акции", "Статус"],
                ["322322522", "1620", "Не участвует: стоит блокировка на снижение цены"],
            ]
        ),
        "Товары_для_исключения_из_акции_Жаркие_скидки_автоматические_скидки.xlsx",
    )
    promotions = [{"id": "1001", "name": "Весенняя распродажа"}]

    assert _find_promotion_for_file(promotions, parsed.original_filename) is None

    imported = _imported_promotion_from_excel(parsed)

    assert imported["id"].startswith("excel-")
    assert imported["name"] == "Жаркие скидки автоматические скидки"
    assert imported["eligibleSkuCount"] == 1
    assert imported["excelImportOnly"] is True
