"""Parent CAS primitive; service must first approve source progression and authority."""

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.modules.orders import OrderContractValidationError
from app.orders.ingestion import _integer
from app.orders.serialization import deserialize_observation, observation_checksum


class OrdersProjectionRepository:
    def __init__(
        self, session: Session, organization_id: int, marketplace_account_id: int
    ):
        _integer(organization_id)
        _integer(marketplace_account_id)
        self.session, self.org, self.account = (
            session,
            organization_id,
            marketplace_account_id,
        )

    def set_parent(
        self, run_id: int, observation_id: int, *, expected_version: int
    ) -> int:
        for value in (run_id, observation_id, expected_version):
            _integer(value)
        if not self.session.in_transaction():
            raise OrderContractValidationError("Caller transaction required")
        if self.session.execute(
            text("SELECT current_setting('app.organization_id',true)")
        ).scalar_one() != str(self.org):
            raise OrderContractValidationError("Transaction tenant context differs")
        params = {
            "org": self.org,
            "account": self.account,
            "run": run_id,
            "observation": observation_id,
        }
        run = (
            self.session.execute(
                text("""SELECT state,source_kind,adapter_version,mapping_version
            FROM order_sync_runs WHERE organization_id=:org AND marketplace_account_id=:account
            AND sync_run_id=:run FOR UPDATE"""),
                params,
            )
            .mappings()
            .one_or_none()
        )
        if run is None:
            raise OrderContractValidationError("Run membership scope missing")
        if run["state"] != "staging":
            raise OrderContractValidationError("Cannot project terminal run")
        record = (
            self.session.execute(
                text("""SELECT e.order_id,e.normalized_evidence,e.payload_checksum,
            o.external_order_id,o.marketplace FROM order_sync_memberships m
            JOIN order_observations e ON (e.organization_id,e.marketplace_account_id,e.observation_id)=
                (m.organization_id,m.marketplace_account_id,m.observation_id)
            JOIN marketplace_orders o ON (o.organization_id,o.marketplace_account_id,o.order_id)=
                (e.organization_id,e.marketplace_account_id,e.order_id)
            WHERE m.organization_id=:org AND m.marketplace_account_id=:account AND m.sync_run_id=:run
              AND m.observation_id=:observation AND m.order_item_id IS NULL AND e.order_item_id IS NULL"""),
                params,
            )
            .mappings()
            .one_or_none()
        )
        if record is None:
            raise OrderContractValidationError("Observation membership missing")
        row = deserialize_observation(record["normalized_evidence"])
        if (
            row.identity.organization_id,
            row.identity.marketplace_account_id,
            row.identity.external_order_id,
            row.identity.marketplace,
            row.source_kind,
            row.adapter_version,
            row.status.mapping_version,
            observation_checksum(row),
        ) != (
            self.org,
            self.account,
            record["external_order_id"],
            record["marketplace"],
            run["source_kind"],
            run["adapter_version"],
            run["mapping_version"],
            record["payload_checksum"],
        ):
            raise OrderContractValidationError(
                "Stored projection source binding changed"
            )
        params.update(
            order=record["order_id"],
            expected=expected_version,
            raw=row.status.raw_status,
            canonical=row.status.canonical_status,
            mapping=row.status.mapping_state,
            mapping_version=row.status.mapping_version,
            effective=row.effective_at,
        )
        version = self.session.execute(
            text("""UPDATE marketplace_orders SET raw_status=:raw,
            canonical_status=:canonical,mapping_state=:mapping,mapping_version=:mapping_version,
            source_updated_at=:effective,last_seen_sync_run_id=:run,version=version+1,updated_at=clock_timestamp()
            WHERE organization_id=:org AND marketplace_account_id=:account AND order_id=:order
            AND version=:expected RETURNING version"""),
            params,
        ).scalar_one_or_none()
        if version is None:
            raise OrderContractValidationError("Parent version conflict")
        return version
