import pytest
from sqlalchemy import insert, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from alembic import command
from app.cabinet.orm import LkOrganizationRow
from app.platform.finance.orm import WbFinanceOperationRow
from app.platform.finance.service import normalize_operation, operation_values
from app.platform.integrations.orm import MarketplaceAccountRow
from tests.test_empty_database_migrations import cluster, database
from tests.test_finance_pnl_rollup import PERIOD, settlement_rows


def test_payable_migration_preserves_legacy_unknown_and_refuses_evidence_loss(database):
    config, engine = database
    command.upgrade(config, "20260910_0085")
    operation = normalize_operation(settlement_rows()[0], 1, 31, PERIOD)
    legacy = operation_values(operation)
    legacy.pop("payable_kopecks", None)
    with Session(engine) as session, session.begin():
        session.add(LkOrganizationRow(organization_id=1, slug="finance", name="Finance"))
        session.flush()
        session.add(MarketplaceAccountRow(
            organization_id=1, marketplace_account_id=31, marketplace="wb",
            external_account_id="synthetic-finance", status="connected",
        ))
        session.flush()
        session.execute(insert(WbFinanceOperationRow.__table__).values(**legacy))

    command.upgrade(config, "20260911_0086")
    with engine.begin() as connection:
        row = connection.execute(text(
            "SELECT payable_kopecks, commission_kopecks, payload_checksum FROM wb_finance_operations"
        )).one()
        assert tuple(row) == (None, 10_000, operation.payload_checksum)
    command.downgrade(config, "20260910_0085")
    command.upgrade(config, "20260911_0086")

    observed = normalize_operation(settlement_rows()[0] | {"forPay": "863.00"}, 1, 31, PERIOD)
    with engine.begin() as connection:
        connection.execute(insert(WbFinanceOperationRow.__table__).values(**operation_values(observed)))
    with pytest.raises(DBAPIError, match="cannot downgrade while canonical payable evidence exists"):
        command.downgrade(config, "20260910_0085")
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "20260911_0086"
        assert connection.scalar(text("SELECT sum(payable_kopecks) FROM wb_finance_operations")) == 86_300
