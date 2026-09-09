"""Characterize accepted metadata before choosing a SQL representation amendment."""

from dataclasses import replace
from datetime import UTC, datetime

import pytest

from app.reviews.canonical_contract import normalize_avito_review, review_fact_checksum


@pytest.mark.parametrize(
    "field",
    [
        "source_status",
        "source_schema_version",
        "normalization_version",
        "source_run_id",
    ],
)
@pytest.mark.parametrize("value", ["\0", "prefix\0suffix", "версия-e\u0301-😀"])
def test_current_metadata_contract_preserves_nonempty_untrimmed_opaque_values(
    field, value
):
    now = datetime(2026, 9, 9, tzinfo=UTC)
    payload = {
        "id": "synthetic-review",
        "createdAt": now,
        "text": "synthetic text",
        "answered": False,
    }
    base = normalize_avito_review(payload, 1, 11, "synthetic-run", now)
    if field in {"source_status", "source_schema_version"}:
        payload[field] = value
        fact = normalize_avito_review(payload, 1, 11, "synthetic-run", now)
    elif field == "source_run_id":
        fact = normalize_avito_review(payload, 1, 11, value, now)
    else:
        # Factory uses its current version constant; DTO hydration admits historical versions.
        fact = replace(base, normalization_version=value, content_checksum="")
        fact = replace(fact, content_checksum=review_fact_checksum(fact))
    assert getattr(fact, field) == value
    assert fact.content_checksum == review_fact_checksum(fact)
    if field == "source_run_id":
        assert fact.content_checksum == base.content_checksum
    else:
        assert fact.content_checksum != base.content_checksum
