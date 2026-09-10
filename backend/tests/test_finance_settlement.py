from datetime import date

import pytest

from app.platform.finance.orm import WbFinanceOperationRow, WbFinanceSyncRunRow
from app.platform.finance.service import FinanceService, normalize_operation
from app.platform.period import Period
from tests.test_finance_pnl_rollup import NOW, PERIOD, session, settlement_rows


@pytest.mark.parametrize("document,sign", [("Продажа", 1), ("Возврат", -1)])
def test_payable_is_preserved_with_document_direction(document, sign):
    raw = settlement_rows()[0] | {"docTypeName": document, "forPay": "863.00"}
    operation = normalize_operation(raw, 1, 31, PERIOD)

    assert getattr(operation, "payable_kopecks", None) == sign * 86_300
    assert operation.commission_kopecks == sign * 10_000  # Source evidence retained.


def test_pnl_reconciles_payable_in_exact_daily_and_raw_reads(session):
    rows = settlement_rows()
    rows[0]["forPay"] = "863.00"
    rows[1]["forPay"] = "172.60"
    service = FinanceService(session, 1, now=lambda: NOW)
    snapshot = service.ingest_snapshot(31, PERIOD, rows, observed_at=NOW)

    fact = service.get_pnl_source(31, PERIOD).facts[0]
    assert fact.commission_kopecks == 9_760
    assert fact.payable_kopecks == 69_040
    assert fact.revenue_kopecks - fact.commission_kopecks - fact.acquiring_kopecks == 69_040
    day = service.get_pnl_source(31, Period(date(2026, 8, 20), date(2026, 8, 20))).facts[0]
    assert (day.commission_kopecks, day.payable_kopecks) == (12_200, 86_300)

    run = session.get(WbFinanceSyncRunRow, snapshot.sync_run_id)
    run.is_pnl_rollup_materialized = run.is_daily_pnl_rollup_materialized = False
    session.commit()
    assert service.get_pnl_source(31, PERIOD).facts[0] == fact
    operation = session.query(WbFinanceOperationRow).filter_by(rrd_id=1).one()
    assert operation.commission_kopecks == 10_000
    assert operation.payable_kopecks == 86_300
    assert snapshot.formula_version == "wb-finance-v3"


def test_missing_payable_remains_unknown_and_zero_is_evidence(session):
    rows = settlement_rows()
    rows[0]["forPay"] = "0"
    service = FinanceService(session, 1, now=lambda: NOW)
    service.ingest_snapshot(31, PERIOD, rows, observed_at=NOW)

    total = service.get_pnl_source(31, PERIOD).facts[0]
    assert getattr(total, "payable_kopecks", "absent") is None
    day = service.get_pnl_source(31, Period(date(2026, 8, 20), date(2026, 8, 20))).facts[0]
    assert day.payable_kopecks == 0
    assert day.commission_kopecks == 98_500


def test_payable_correction_is_a_new_immutable_observation(session):
    rows = [settlement_rows()[0] | {"forPay": "863.00"}]
    service = FinanceService(session, 1, now=lambda: NOW)
    first = service.ingest_snapshot(31, PERIOD, rows, observed_at=NOW)
    second = service.ingest_snapshot(31, PERIOD, [rows[0] | {"forPay": "860.00"}], observed_at=NOW)

    assert first.sync_run_id != second.sync_run_id
    assert session.query(WbFinanceOperationRow).count() == 2
    assert {row.payable_kopecks for row in session.query(WbFinanceOperationRow)} == {86_300, 86_000}
    retry = service.ingest_snapshot(31, PERIOD, [rows[0] | {"forPay": "860.00"}], observed_at=NOW)
    assert retry.sync_run_id == second.sync_run_id
