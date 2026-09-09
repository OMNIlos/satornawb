"""Dormant PostgreSQL repository, NOT a user/worker authorization boundary.

Caller must hold the platform publication guard through outer commit, with user
locks acquired before the account lock. No router/task uses this repository yet.
Standalone commands own savepoints only. Guarded callers explicitly disable them
and MUST roll back their entire root on any failure, never catch and commit a
partial command. No commits, provider I/O or fallback stores.
"""

import re
from contextlib import contextmanager, nullcontext
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import func, insert, select, text, update
from sqlalchemy.engine import Connection
from sqlalchemy.exc import SQLAlchemyError

from app.platform.integrations.orm import MarketplaceAccountRow
from app.reviews.canonical_contract import (
    ExternalReviewIdentity,
    ReviewNormalizationError,
    validate_review_source_run_id,
)
from app.reviews.canonical_orm import (
    CanonicalReviewFactRow,
    CanonicalReviewObservationRow,
    CanonicalReviewRunItemRow,
    CanonicalReviewRunRow,
)
from app.reviews.ingestion_contract import (
    ReviewRepositoryError,
    snapshot_manifest,
    timestamp,
)

RUN = CanonicalReviewRunRow.__table__
ACCOUNT = MarketplaceAccountRow.__table__
FACT = CanonicalReviewFactRow.__table__
OBS = CanonicalReviewObservationRow.__table__
ITEM = CanonicalReviewRunItemRow.__table__


@dataclass(frozen=True, slots=True, repr=False)
class ReviewOwner:
    organization_id: int
    marketplace_account_id: int
    marketplace: str
    external_account_id: str

    def __post_init__(self):
        if (
            type(self.organization_id) is not int
            or self.organization_id <= 0
            or type(self.marketplace_account_id) is not int
            or self.marketplace_account_id <= 0
            or self.marketplace not in ("wb", "avito")
            or not isinstance(self.external_account_id, str)
            or not self.external_account_id
        ):
            raise ReviewRepositoryError()


@dataclass(frozen=True, slots=True)
class ReviewRunReference:
    sync_run_id: UUID
    run_sequence: int


@dataclass(frozen=True, slots=True, repr=False)
class ReviewFactSnapshot:
    review_id: UUID
    version: int
    revision: int
    text: str | None
    can_answer: bool | None
    source_order_state: str
    last_source_run_sequence: int
    current_observation_id: UUID


class ReviewFactsRepository:
    def __init__(
        self,
        connection: Connection,
        owner: ReviewOwner,
        *,
        command_savepoints: bool = True,
    ):
        if not isinstance(owner, ReviewOwner) or type(command_savepoints) is not bool:
            raise ReviewRepositoryError()
        self.connection = connection
        self.owner = owner
        self._command_savepoints = command_savepoints

    @property
    def _values(self):
        return {
            "organization_id": self.owner.organization_id,
            "marketplace_account_id": self.owner.marketplace_account_id,
            "marketplace": self.owner.marketplace,
        }

    def _scope(self, table):
        return tuple(table.c[key] == value for key, value in self._values.items())

    @contextmanager
    def _command(self):
        c = self.connection
        if c.dialect.name != "postgresql" or not c.in_transaction():
            raise ReviewRepositoryError("REVIEW_TRANSACTION_REQUIRED")
        if not self._command_savepoints and c.in_nested_transaction():
            raise ReviewRepositoryError("REVIEW_TRANSACTION_REQUIRED")
        try:
            with c.begin_nested() if self._command_savepoints else nullcontext():
                if (
                    c.exec_driver_sql("SHOW transaction_isolation").scalar_one()
                    != "read committed"
                ):
                    raise ReviewRepositoryError("REVIEW_TRANSACTION_REQUIRED")
                if c.execute(
                    text("SELECT current_setting('app.organization_id', true)")
                ).scalar_one() != str(self.owner.organization_id):
                    raise ReviewRepositoryError("REVIEW_SCOPE_DENIED")
                account = c.execute(
                    select(ACCOUNT.c.external_account_id, ACCOUNT.c.status)
                    .where(*self._scope(ACCOUNT))
                    .with_for_update()
                ).one_or_none()
                if (
                    account is None
                    or account.status != "connected"
                    or account.external_account_id != self.owner.external_account_id
                ):
                    raise ReviewRepositoryError("REVIEW_SCOPE_DENIED")
                yield
        except SQLAlchemyError:
            raise ReviewRepositoryError("REVIEW_STORAGE_UNAVAILABLE") from None

    def reserve_run(
        self, *, source_run_id: str, request_checksum: str, started_at: datetime
    ) -> ReviewRunReference:
        try:
            source_run_id = validate_review_source_run_id(source_run_id)
        except ReviewNormalizationError:
            raise ReviewRepositoryError() from None
        if (
            not isinstance(request_checksum, str)
            or re.fullmatch("[0-9a-f]{64}", request_checksum) is None
        ):
            raise ReviewRepositoryError()
        timestamp(started_at)
        with self._command():
            row = (
                self.connection.execute(
                    select(RUN).where(
                        *self._scope(RUN),
                        RUN.c.source_run_id.collate("C") == source_run_id,
                    )
                )
                .mappings()
                .one_or_none()
            )
            if row is not None:
                if row["request_checksum"] != request_checksum:
                    raise ReviewRepositoryError("REVIEW_REPLAY_CONFLICT")
                return ReviewRunReference(row["sync_run_id"], row["run_sequence"])
            # Explicit allowlist deliberately omits even DEFAULT for run_sequence.
            row = self.connection.execute(
                insert(RUN)
                .values(
                    **self._values,
                    sync_run_id=uuid4(),
                    source_run_id=source_run_id,
                    request_checksum=request_checksum,
                    status="running",
                    completeness="partial",
                    started_at=started_at,
                    completed_at=None,
                    observed_count=0,
                    manifest_checksum=None,
                    coverage={
                        "from": None,
                        "to": None,
                        "streams": [],
                        "pagesObserved": 0,
                        "providerEndReached": False,
                    },
                    error_code=None,
                )
                .returning(RUN.c.sync_run_id, RUN.c.run_sequence)
            ).one()
            return ReviewRunReference(*row)

    def _identity(self, external_review_id):
        return (
            self.connection.execute(
                select(FACT).where(
                    *self._scope(FACT),
                    FACT.c.external_review_id.collate("C") == external_review_id,
                )
            )
            .mappings()
            .one_or_none()
        )

    def _observation(self, review_id, observation_id):
        return (
            self.connection.execute(
                select(OBS).where(
                    *self._scope(OBS),
                    OBS.c.review_id == review_id,
                    OBS.c.observation_id == observation_id,
                )
            )
            .mappings()
            .one()
        )

    def get_fact(self, external_review_id: str) -> ReviewFactSnapshot | None:
        if not isinstance(external_review_id, str) or not external_review_id:
            raise ReviewRepositoryError()
        try:
            external_review_id = ExternalReviewIdentity(
                self.owner.organization_id,
                self.owner.marketplace_account_id,
                self.owner.marketplace,
                external_review_id,
            ).external_review_id
        except ReviewNormalizationError:
            raise ReviewRepositoryError() from None
        with self._command():
            row = self._identity(external_review_id)
            if row is None:
                return None
            observation = self._observation(
                row["review_id"], row["current_observation_id"]
            )
            return ReviewFactSnapshot(
                row["review_id"],
                row["version"],
                observation["revision"],
                observation["text"],
                observation["can_answer"],
                row["source_order_state"],
                row["last_source_run_sequence"],
                row["current_observation_id"],
            )

    def ingest(
        self,
        sync_run_id: UUID,
        *,
        facts: tuple,
        coverage: dict,
        completeness: str,
        completed_at: datetime,
        expected_versions: dict[str, int],
    ) -> str:
        if not isinstance(sync_run_id, UUID):
            raise ReviewRepositoryError()
        timestamp(completed_at)
        ordered, normalized_coverage, manifest = snapshot_manifest(
            facts, coverage, completeness, expected_versions
        )
        with self._command():
            run = (
                self.connection.execute(
                    select(RUN).where(
                        *self._scope(RUN), RUN.c.sync_run_id == sync_run_id
                    )
                )
                .mappings()
                .one_or_none()
            )
            if run is None:
                raise ReviewRepositoryError("REVIEW_SCOPE_DENIED")
            if completed_at < run["started_at"]:
                raise ReviewRepositoryError()
            for fact in ordered:
                if (
                    fact.identity.organization_id != self.owner.organization_id
                    or fact.identity.marketplace_account_id
                    != self.owner.marketplace_account_id
                    or fact.identity.marketplace.value != self.owner.marketplace
                    or fact.source_run_id != run["source_run_id"]
                ):
                    raise ReviewRepositoryError("REVIEW_SCOPE_DENIED")
            if run["status"] != "running":
                if (
                    run["status"] != completeness
                    or run["completeness"] != completeness
                    or run["manifest_checksum"] != manifest
                    or run["observed_count"] != len(ordered)
                    or run["coverage"] != normalized_coverage
                ):
                    raise ReviewRepositoryError("REVIEW_REPLAY_CONFLICT")
                return manifest
            for ordinal, fact in enumerate(ordered):
                self._ingest_fact(
                    run,
                    fact,
                    ordinal,
                    expected_versions[fact.identity.external_review_id],
                )
            count = self.connection.execute(
                select(func.count())
                .select_from(ITEM)
                .where(*self._scope(ITEM), ITEM.c.sync_run_id == sync_run_id)
            ).scalar_one()
            if count != len(ordered):
                raise ReviewRepositoryError("REVIEW_REPLAY_CONFLICT")
            changed = self.connection.execute(
                update(RUN)
                .where(
                    *self._scope(RUN),
                    RUN.c.sync_run_id == sync_run_id,
                    RUN.c.status == "running",
                )
                .values(
                    status=completeness,
                    completeness=completeness,
                    completed_at=completed_at,
                    observed_count=count,
                    manifest_checksum=manifest,
                    coverage=normalized_coverage,
                    error_code=None,
                )
            ).rowcount
            if changed != 1:
                raise ReviewRepositoryError("REVIEW_VERSION_CONFLICT")
            return manifest

    def _ingest_fact(self, run, fact, ordinal, expected_version):
        c = self.connection
        identity = self._identity(fact.identity.external_review_id)
        if (0 if identity is None else identity["version"]) != expected_version:
            raise ReviewRepositoryError("REVIEW_VERSION_CONFLICT")
        if identity is None:
            review_id = uuid4()
            c.execute(
                insert(FACT).values(
                    **self._values,
                    review_id=review_id,
                    external_review_id=fact.identity.external_review_id,
                    current_observation_id=None,
                    version=0,
                    last_source_run_id=None,
                    last_source_run_sequence=None,
                    source_order_state="current",
                    ambiguous_observation_id=None,
                    first_observed_at=fact.observed_at,
                    last_observed_at=fact.observed_at,
                )
            )
            identity = self._identity(fact.identity.external_review_id)
        review_id = identity["review_id"]
        current = (
            None
            if identity["current_observation_id"] is None
            else self._observation(review_id, identity["current_observation_id"])
        )
        if current is not None and current["content_checksum"] == fact.content_checksum:
            observation_id = current["observation_id"]
        else:
            revision = c.execute(
                select(func.coalesce(func.max(OBS.c.revision), 0) + 1).where(
                    *self._scope(OBS), OBS.c.review_id == review_id
                )
            ).scalar_one()
            observation_id = uuid4()
            c.execute(
                insert(OBS).values(
                    **self._values,
                    observation_id=observation_id,
                    review_id=review_id,
                    revision=revision,
                    source_run_id=run["sync_run_id"],
                    **{
                        key: getattr(fact, key)
                        for key in (
                            "external_product_id",
                            "source_created_at",
                            "source_updated_at",
                            "rating",
                            "text",
                            "answered",
                            "can_answer",
                            "source_status",
                            "observed_at",
                            "source_schema_version",
                            "normalization_version",
                            "content_checksum",
                        )
                    },
                )
            )
        c.execute(
            insert(ITEM).values(
                **self._values,
                sync_run_id=run["sync_run_id"],
                review_id=review_id,
                observation_id=observation_id,
                content_checksum=fact.content_checksum,
                ordinal=ordinal,
                observed_at=fact.observed_at,
            )
        )
        pointer = observation_id
        state = identity["source_order_state"]
        ambiguous_id = identity["ambiguous_observation_id"]
        watermark_id, watermark_sequence = run["sync_run_id"], run["run_sequence"]
        if current is not None:
            old_time, new_time = current["source_updated_at"], fact.source_updated_at
            equal_conflict = (
                old_time is not None
                and new_time == old_time
                and observation_id != current["observation_id"]
            )
            # Unknown-time current evidence must not erase previously observed
            # provider freshness. Immutable history is the durable known fence.
            known_time = c.execute(
                select(func.max(OBS.c.source_updated_at)).where(
                    *self._scope(OBS),
                    OBS.c.review_id == review_id,
                    OBS.c.observation_id != observation_id,
                )
            ).scalar_one()
            if (
                not equal_conflict
                and new_time is not None
                and known_time is not None
                and new_time < known_time
            ):
                return
            late = run["run_sequence"] <= identity["last_source_run_sequence"]
            if late:
                # Late data cannot advance the pointer/watermark, but a same-time
                # disagreement must still durably block an unambiguous read.
                if not equal_conflict:
                    return
                pointer = current["observation_id"]
                watermark_id = identity["last_source_run_id"]
                watermark_sequence = identity["last_source_run_sequence"]
                if state != "ambiguous":
                    state, ambiguous_id = "ambiguous", observation_id
            elif state == "ambiguous":
                ambiguous = self._observation(review_id, ambiguous_id)
                conflict_time = ambiguous["source_updated_at"]
                if (
                    old_time is not None
                    and conflict_time is not None
                    and new_time is not None
                    and new_time > old_time
                    and new_time > conflict_time
                    and (known_time is None or new_time > known_time)
                ):
                    state, ambiguous_id = "current", None
                else:
                    pointer = current["observation_id"]
                    # Preserve unknown-time conflicts; a later known timestamp
                    # cannot prove that it supersedes unknown evidence.
                    if (
                        observation_id != pointer
                        and conflict_time is not None
                        and (new_time is None or new_time >= conflict_time)
                    ):
                        ambiguous_id = observation_id
            elif equal_conflict:
                pointer = current["observation_id"]
                state, ambiguous_id = "ambiguous", observation_id
        changed = c.execute(
            update(FACT)
            .where(
                *self._scope(FACT),
                FACT.c.review_id == review_id,
                FACT.c.version == expected_version,
            )
            .values(
                current_observation_id=pointer,
                source_order_state=state,
                ambiguous_observation_id=ambiguous_id,
                version=expected_version + 1,
                last_source_run_id=watermark_id,
                last_source_run_sequence=watermark_sequence,
                last_observed_at=max(identity["last_observed_at"], fact.observed_at),
            )
        ).rowcount
        if changed != 1:
            raise ReviewRepositoryError("REVIEW_VERSION_CONFLICT")
