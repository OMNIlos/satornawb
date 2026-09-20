"""Run: PYTHONPATH=backend:backend/backend_contracts python backend/scripts/check_report_data_repair.py"""
from datetime import date
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import patch
from xml.sax.saxutils import escape
from zipfile import ZipFile

from app.wb_funnel_export import parse_funnel_export
from app.reports_history import ensure_daily_stock_history
from app.wb_api.rnp_runtime import _cached_funnel_rows
from app.routers.wb_reports_bff import _build_week_over_week_payload, _empty_background_report, _week_rows_from_abc_rows, _week_rows_with_funnel_metrics


def sheet(rows):
    def column(index):
        result = ''
        while index:
            index, remainder = divmod(index - 1, 26)
            result = chr(65 + remainder) + result
        return result
    body = ''.join('<row>' + ''.join(f'<c r="{column(c)}{r}" t="inlineStr"><is><t>{escape(str(value))}</t></is></c>' for c, value in enumerate(row, 1)) + '</row>' for r, row in enumerate(rows, 1))
    return f'<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>{body}</sheetData></worksheet>'


buffer = BytesIO()
with ZipFile(buffer, 'w') as z:
    z.writestr('xl/worksheets/sheet1.xml', sheet([
        ['Значение за текущий период', 'С 12-09-2026 по 18-09-2026'], ['Прошлый период', 'С 05-09-2026 по 11-09-2026']]))
    z.writestr('xl/worksheets/sheet3.xml', sheet([['Итого'], ['Показы', 'Показы (предыдущий период)'], [1000, 2000]]))
    z.writestr('xl/worksheets/sheet4.xml', sheet([['Товары'],
        ['Артикул WB', 'Показы', 'Показы (предыдущий период)', 'Переходы в карточку', 'Переходы в карточку (предыдущий период)', 'Положили в корзину', 'Заказали товаров, шт', 'Заказали на сумму, ₽', 'Предмет'],
        [1, 1000, 2000, 100, 200, 40, 10, '1000.50', 'Футболки']]))
current, previous = parse_funnel_export(buffer.getvalue())
assert current['aggregates']['1']['orderSumKopecks'] == 100050
assert current['aggregates']['1']['ctrPct'] == 10
assert current['aggregates']['1']['openCountDeltaPct'] == -50
with patch('app.wb_api.rnp_runtime._period_cache', return_value=current):
    rows, _, _ = _cached_funnel_rows(organization_id=2, date_from=date(2026, 9, 12), date_to=date(2026, 9, 18))
assert rows[0]['categoryName'] == 'Футболки' and rows[0]['openCountDeltaPct'] == -50

def cache(org, key):
    assert org == 2
    return {'aggregates': {'1': {'wbStockUnits': 8}}} if key.endswith('2026-09-18') else None
with patch('app.reports_history.get_source_cache', side_effect=cache):
    history = ensure_daily_stock_history(date(2026, 9, 18), [SimpleNamespace(nm_id=1)], organization_id=2)
assert len(history[1]) == 1 and history[1][0].snapshotDate == date(2026, 9, 18)

with patch('app.routers.wb_reports_bff._orders_sales_by_nm', return_value={1: {'orders_qty': 9, 'orders_revenue': 0, 'sales_qty': 5, 'sales_revenue': 50000}}), \
     patch('app.routers.wb_reports_bff._catalog_meta_by_nm', return_value={}), \
     patch('app.routers.wb_reports_bff.ensure_daily_stock_history', return_value={}), \
     patch('app.routers.wb_reports_bff._week_funnel_metrics_by_nm', return_value={'1': current['aggregates']['1']}):
    report = _build_week_over_week_payload({'from': '2026-09-12', 'to': '2026-09-18'}, SimpleNamespace(stocks=[], source_status='fresh'), organization_id=2)
row = report['rows'][0]
assert row['baskets']['units'] == 40 and row['price']['kopecks'] == 10005
assert row['stockAvailability7d'] == [] and row['wasOutOfStock'] is None
assert row['marginPct']['percent'] is None and row['stockSnapshotCoveragePct'] == 0
missing = _empty_background_report('week-over-week', {'from': '2026-09-12', 'to': '2026-09-18'}, 'sku', {'state': 'completed', 'cacheFresh': True})
assert missing['reportJob']['state'] == 'idle' and missing['reportJob']['cacheFresh'] is False
prior = {'nmId': 1, 'ordersComposite': {'units': 2, 'kopecks': 40000}, 'salesComposite': {'units': 2, 'kopecks': 40000}}
current = {**prior, 'ordersComposite': {'units': 2, 'kopecks': 20000}, 'salesComposite': {'units': 2, 'kopecks': 20000}, 'priceWithSppKopecks': 0, 'baskets': 20}
with patch('app.reports_history.get_source_cache', side_effect=cache):
    row = _week_rows_from_abc_rows([current], [prior], organization_id=2, snapshot_date=date(2026, 9, 18))[0]
assert row['price'] == {'kopecks': 10000, 'deltaPct': -50}
assert row['sales']['deltaPct'] == -50 and row['stockSnapshotCoveragePct'] == 14
assert row['stockAvailability7d'] == [True] and '1 из 7' in row['conclusion']
empty = _week_rows_with_funnel_metrics([current], {'1': {'cartCount': 0, 'orderCount': 0, 'orderSumKopecks': 0, 'buyoutCount': 0, 'buyoutSumKopecks': 0}})
assert empty[0]['baskets'] == 0 and empty[0]['ordersComposite']['units'] == 0
assert _week_rows_from_abc_rows(empty)[0]['price']['kopecks'] is None
print('Report data repair: OK')
