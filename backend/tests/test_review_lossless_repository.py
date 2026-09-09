"""Exact0065 mixed-representation consumer acceptance, not schema installation."""

import json
from uuid import uuid4

import pytest

from app.reviews.ingestion_contract import ReviewRepositoryError
from tests import test_review_facts_repository as existing
from tests.test_orders_schema_candidate import scope

cluster = existing.cluster
db = existing.db


def byte_unit(connection, value, *, corrupt=False):
    fields = (
        "external_product_id",
        "text",
        "source_status",
        "source_schema_version",
        "normalization_version",
    )
    observation = {key: None for key in fields}
    observation.update(
        {
            key + "_utf8": None
            if getattr(value, key) is None
            else getattr(value, key).encode("utf-8")
            for key in fields
        }
    )
    observation.update(
        source_created_at=value.source_created_at,
        source_updated_at=value.source_updated_at,
        rating=value.rating,
        answered=value.answered,
        can_answer=value.can_answer,
        observed_at=value.observed_at,
        content_checksum="0" * 64 if corrupt else value.content_checksum,
    )
    schema = existing.schema
    run_id, sequence = schema.run(
        connection,
        source_run_id=None,
        source_run_id_utf8=value.source_run_id.encode("utf-8"),
        coverage=None,
        coverage_utf8=json.dumps(existing.COVERAGE).encode("utf-8"),
    )
    rid = schema.identity(
        connection,
        external_review_id=None,
        external_review_id_utf8=value.identity.external_review_id.encode("utf-8"),
    )
    oid = schema.observation(connection, rid, run_id, **observation)
    assert (
        schema.advance(
            connection,
            rid,
            oid,
            last_source_run_id=run_id,
            last_source_run_sequence=sequence,
        )
        == 1
    )
    schema.item(
        connection, rid, oid, run_id, content_checksum=observation["content_checksum"]
    )
    return {"review_sync_runs_v2": {"sync_run_id": run_id}}


@pytest.mark.parametrize("body", [None, "", "a\0е\u0301🚀"])
def test_decoder_reads_byte_observation_and_exact_nul_identity(db, body):
    key, source = uuid4().hex + "\0🚀", uuid4().hex + "\0run"
    value = existing.fact(key, source, body=body)
    with db[0].begin() as c:
        rows = byte_unit(c, value)
    with db[1].begin() as c:
        scope(c)
        repo = existing.repository(c)
        stored = repo.get_fact(key)
        assert stored is not None
        assert stored.text == body
        assert stored.version == 1
        ref = repo.reserve_run(
            source_run_id=source, request_checksum="a" * 64, started_at=existing.NOW
        )
        assert ref.sync_run_id == rows["review_sync_runs_v2"]["sync_run_id"]


def test_decoder_rejects_stored_observation_checksum_mismatch(db):
    key, source = uuid4().hex, uuid4().hex
    with db[0].begin() as c:
        byte_unit(c, existing.fact(key, source), corrupt=True)
    with db[1].begin() as c:
        scope(c)
        with pytest.raises(ReviewRepositoryError, match="^REVIEW_STORAGE_INVALID$"):
            existing.repository(c).get_fact(key)


def test_run_replay_rejects_duplicate_json_keys_admitted_by_sql(db):
    source = uuid4().hex
    encoded = b'{"from":null,"to":null,"streams":[],"pagesObserved":0,"pagesObserved":1,"providerEndReached":false}'
    with db[0].begin() as c:
        existing.schema.run(
            c,
            source_run_id=None,
            source_run_id_utf8=source.encode("utf-8"),
            coverage=None,
            coverage_utf8=encoded,
        )
    with db[1].begin() as c:
        scope(c)
        with pytest.raises(ReviewRepositoryError, match="^REVIEW_STORAGE_INVALID$"):
            existing.repository(c).reserve_run(
                source_run_id=source, request_checksum="a" * 64, started_at=existing.NOW
            )
