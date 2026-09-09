"""Current schema limitation: normalized NUL must not leave partial durable facts.

This characterizes safe rollback, not lossless text parity. Replace with a
round-trip acceptance test when the schema owner supplies lossless storage.
"""

from uuid import uuid4

import pytest
from sqlalchemy import text

from app.reviews.canonical_repository import ReviewRepositoryError
from tests import test_review_facts_repository as repository_tests
from tests.test_orders_schema_candidate import scope

cluster = repository_tests.cluster
db = repository_tests.db


def test_unsupported_nul_text_rolls_back_without_partial_facts(db):
    source, key = uuid4().hex, uuid4().hex
    normalized = repository_tests.fact(key, source, body="synthetic\0review")
    assert normalized.text == "synthetic\0review"
    with db[1].begin() as connection:
        scope(connection)
        repo = repository_tests.repository(connection)
        run = repo.reserve_run(
            source_run_id=source,
            request_checksum="a" * 64,
            started_at=repository_tests.NOW,
        )
        with pytest.raises(ReviewRepositoryError, match="REVIEW_STORAGE_UNAVAILABLE"):
            repository_tests.ingest(repo, run, [normalized], {key: 0})
        assert repo.get_fact(key) is None
        assert (
            connection.execute(
                text("SELECT status FROM review_sync_runs_v2 WHERE sync_run_id=:run"),
                {"run": run.sync_run_id},
            ).scalar_one()
            == "running"
        )
        assert (
            connection.execute(
                text(
                    "SELECT count(*) FROM review_sync_run_items WHERE sync_run_id=:run"
                ),
                {"run": run.sync_run_id},
            ).scalar_one()
            == 0
        )
        # Same identity/run and transaction work once the unsupported byte is absent.
        plain = repository_tests.fact(key, source, body="synthetic review")
        repository_tests.ingest(repo, run, [plain], {key: 0})
        assert repo.get_fact(key).text == "synthetic review"
