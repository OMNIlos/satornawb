from __future__ import annotations

import ast
import copy
import hashlib
import json
import socket
import urllib.request
from dataclasses import fields, replace
from datetime import datetime, timezone
from pathlib import Path

import pytest

from app.avito.reviews import AvitoReviewAnswer, AvitoReviewRow
from app.reviews.canonical_contract import (
    AVITO_REVIEW_SOURCE_SCHEMA_VERSION,
    REVIEW_NORMALIZATION_VERSION,
    WB_REVIEW_SOURCE_SCHEMA_VERSION,
    ExternalReviewIdentity,
    NormalizedReviewFact,
    ReviewMarketplace,
    ReviewNormalizationError,
    ReviewSnapshotCompleteness,
    normalize_avito_review,
    normalize_wb_review,
    review_fact_checksum,
)
from app.wb_api.feedbacks_runtime import WbFeedbackRow

FIXTURES = Path(__file__).parent / "fixtures" / "reviews"
OBSERVED_AT = datetime(2026, 9, 8, 12, 0, tzinfo=timezone.utc)


def _fixture(name: str) -> dict[str, object]:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def _rfc3339_z(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _expected_checksum(fact: NormalizedReviewFact) -> str:
    material = {
        "answered": fact.answered,
        "can_answer": fact.can_answer,
        "external_product_id": fact.external_product_id,
        "identity": {
            "external_review_id": fact.identity.external_review_id,
            "marketplace": fact.identity.marketplace.value,
            "marketplace_account_id": fact.identity.marketplace_account_id,
            "organization_id": fact.identity.organization_id,
        },
        "normalization_version": fact.normalization_version,
        "rating": fact.rating,
        "source_created_at": _rfc3339_z(fact.source_created_at),
        "source_schema_version": fact.source_schema_version,
        "source_status": fact.source_status,
        "source_updated_at": _rfc3339_z(fact.source_updated_at),
        "text": fact.text,
    }
    encoded = json.dumps(
        material,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _with_expected_checksum(fact: NormalizedReviewFact) -> NormalizedReviewFact:
    return replace(fact, content_checksum=_expected_checksum(fact))


def test_contract_enums_and_versions_are_stable() -> None:
    assert [item.value for item in ReviewMarketplace] == ["wb", "avito"]
    assert [item.value for item in ReviewSnapshotCompleteness] == [
        "partial",
        "complete",
    ]
    assert REVIEW_NORMALIZATION_VERSION == "reviews-normalization-v1"
    assert [field.name for field in fields(NormalizedReviewFact)] == [
        "identity",
        "external_product_id",
        "source_created_at",
        "source_updated_at",
        "rating",
        "text",
        "answered",
        "can_answer",
        "source_status",
        "observed_at",
        "source_run_id",
        "source_schema_version",
        "normalization_version",
        "content_checksum",
    ]


def test_wb_normalization_matches_exact_expected_fact() -> None:
    payload = _fixture("wb_reviews_synthetic.json")["cases"]["unanswered"]

    actual = normalize_wb_review(payload, 11, 101, "test-run-wb-001", OBSERVED_AT)

    expected = _with_expected_checksum(
        NormalizedReviewFact(
            identity=ExternalReviewIdentity(
                organization_id=11,
                marketplace_account_id=101,
                marketplace=ReviewMarketplace.WB,
                external_review_id="test-wb-review-shared-001",
            ),
            external_product_id="71001",
            source_created_at=datetime(2026, 9, 1, 7, 15, 30, tzinfo=timezone.utc),
            source_updated_at=None,
            rating=5,
            text="[TEST] WB synthetic positive review",
            answered=False,
            can_answer=None,
            source_status="published",
            observed_at=OBSERVED_AT,
            source_run_id="test-run-wb-001",
            source_schema_version=WB_REVIEW_SOURCE_SCHEMA_VERSION,
            normalization_version=REVIEW_NORMALIZATION_VERSION,
            content_checksum="",
        )
    )
    assert actual == expected
    assert actual.content_checksum == review_fact_checksum(
        replace(actual, content_checksum="")
    )


def test_avito_normalization_matches_exact_expected_fact() -> None:
    payload = _fixture("avito_reviews_synthetic.json")["cases"][
        "can_answer_true_numeric_id"
    ]

    actual = normalize_avito_review(payload, 12, 202, "test-run-avito-001", OBSERVED_AT)

    expected = _with_expected_checksum(
        NormalizedReviewFact(
            identity=ExternalReviewIdentity(
                organization_id=12,
                marketplace_account_id=202,
                marketplace=ReviewMarketplace.AVITO,
                external_review_id="51001",
            ),
            external_product_id="61001",
            source_created_at=datetime(2026, 9, 1, 7, 10, 11, tzinfo=timezone.utc),
            source_updated_at=datetime(2026, 9, 1, 8, 15, tzinfo=timezone.utc),
            rating=4,
            text="[TEST] Avito synthetic positive review",
            answered=False,
            can_answer=True,
            source_status="published",
            observed_at=OBSERVED_AT,
            source_run_id="test-run-avito-001",
            source_schema_version=AVITO_REVIEW_SOURCE_SCHEMA_VERSION,
            normalization_version=REVIEW_NORMALIZATION_VERSION,
            content_checksum="",
        )
    )
    assert actual == expected


def test_received_wb_and_avito_dto_shapes_normalize_without_adapter_calls() -> None:
    wb_payload = copy.deepcopy(
        _fixture("wb_reviews_synthetic.json")["cases"]["unanswered"]
    )
    avito_payload = copy.deepcopy(
        _fixture("avito_reviews_synthetic.json")["cases"]["answered"]
    )
    wb_payload.pop("source_status")
    avito_payload.pop("updatedAt")
    wb_dto = WbFeedbackRow(
        feedback_id=wb_payload["feedback_id"],
        nm_id=wb_payload["nm_id"],
        imt_id=None,
        brand_name="Test brand",
        product_name="Test product",
        created_date=datetime.fromisoformat(wb_payload["created_date"]),
        text=wb_payload["text"],
        pros="",
        cons="",
        answer_text=None,
        is_answered=wb_payload["is_answered"],
        rating=wb_payload["rating"],
        raw_payload={},
    )
    avito_dto = AvitoReviewRow(
        reviewId=avito_payload["reviewId"],
        score=avito_payload["score"],
        stage=avito_payload["stage"],
        text=avito_payload["text"],
        usedInScore=True,
        canAnswer=avito_payload["canAnswer"],
        createdAt=avito_payload["createdAt"],
        itemId=avito_payload["itemId"],
        answer=AvitoReviewAnswer(
            answerId=avito_payload["answer"]["answerId"],
            text="[TEST] Avito synthetic marketplace answer",
        ),
    )

    wb_from_mapping = normalize_wb_review(
        wb_payload, 13, 203, "test-run-wb-mapping", OBSERVED_AT
    )
    wb_from_dto = normalize_wb_review(wb_dto, 13, 203, "test-run-wb-dto", OBSERVED_AT)
    avito_from_mapping = normalize_avito_review(
        avito_payload, 13, 204, "test-run-avito-mapping", OBSERVED_AT
    )
    avito_from_dto = normalize_avito_review(
        avito_dto, 13, 204, "test-run-avito-dto", OBSERVED_AT
    )

    assert wb_from_dto.content_checksum == wb_from_mapping.content_checksum
    assert avito_from_dto.content_checksum == avito_from_mapping.content_checksum
    assert "[TEST] Avito synthetic marketplace answer" not in repr(avito_from_dto)
    assert not hasattr(avito_from_dto, "answer")


def test_wb_answered_state_is_preserved_without_answer_content() -> None:
    payload = _fixture("wb_reviews_synthetic.json")["cases"]["answered"]

    fact = normalize_wb_review(payload, 14, 205, "test-run-wb-answered", OBSERVED_AT)

    assert fact.answered is True
    assert fact.can_answer is None
    assert fact.source_updated_at == datetime(2026, 9, 2, 6, 30, tzinfo=timezone.utc)


def test_avito_updated_source_fact_changes_current_semantics() -> None:
    cases = _fixture("avito_reviews_synthetic.json")["cases"]
    previous = normalize_avito_review(
        cases["can_answer_false_string_id"], 15, 206, "test-run-before", OBSERVED_AT
    )
    updated = normalize_avito_review(
        cases["updated_source_fact"], 15, 206, "test-run-after", OBSERVED_AT
    )

    assert previous.identity == updated.identity
    assert updated.answered is True
    assert updated.source_updated_at == datetime(2026, 9, 5, 11, 0, tzinfo=timezone.utc)
    assert updated.source_schema_version == "avito-review-row-v2"
    assert updated.content_checksum != previous.content_checksum


def test_same_external_id_is_scoped_by_organization_and_account() -> None:
    payload = _fixture("wb_reviews_synthetic.json")["cases"]["unanswered"]

    facts = [
        normalize_wb_review(payload, 11, 101, "test-run-1", OBSERVED_AT),
        normalize_wb_review(payload, 11, 102, "test-run-2", OBSERVED_AT),
        normalize_wb_review(payload, 12, 101, "test-run-3", OBSERVED_AT),
        normalize_wb_review(payload, 12, 102, "test-run-4", OBSERVED_AT),
    ]

    assert len({fact.identity for fact in facts}) == 4
    assert len({fact.content_checksum for fact in facts}) == 4


@pytest.mark.parametrize(
    ("fixture_name", "case_name", "normalizer"),
    [
        ("wb_reviews_synthetic.json", "answered", normalize_wb_review),
        ("avito_reviews_synthetic.json", "answered", normalize_avito_review),
    ],
)
def test_mapping_key_order_does_not_change_checksum(
    fixture_name, case_name, normalizer
) -> None:
    payload = _fixture(fixture_name)["cases"][case_name]
    reversed_payload = dict(reversed(list(payload.items())))

    first = normalizer(payload, 21, 301, "test-run-a", OBSERVED_AT)
    second = normalizer(reversed_payload, 21, 301, "test-run-b", OBSERVED_AT)

    assert first.content_checksum == second.content_checksum


def test_observation_metadata_is_excluded_from_checksum() -> None:
    payload = _fixture("avito_reviews_synthetic.json")["cases"]["answered"]
    first = normalize_avito_review(payload, 22, 302, "test-run-a", OBSERVED_AT)
    replay = normalize_avito_review(
        payload,
        22,
        302,
        "test-run-b",
        datetime(2026, 9, 9, 12, 0, tzinfo=timezone.utc),
    )

    assert first.source_run_id != replay.source_run_id
    assert first.observed_at != replay.observed_at
    assert first.content_checksum == replay.content_checksum


@pytest.mark.parametrize("change", ["text", "status", "answer", "source_version"])
def test_semantic_change_changes_checksum(change: str) -> None:
    payload = copy.deepcopy(
        _fixture("avito_reviews_synthetic.json")["cases"]["can_answer_false_string_id"]
    )
    original = normalize_avito_review(payload, 23, 303, "test-run-a", OBSERVED_AT)

    if change == "text":
        payload["text"] = "[TEST] Avito synthetic changed review"
    elif change == "status":
        payload["stage"] = "published"
    elif change == "answer":
        payload["answer"] = {"answerId": "test-avito-answer-change-001"}
    else:
        payload["sourceSchemaVersion"] = "avito-review-row-v2"

    changed = normalize_avito_review(payload, 23, 303, "test-run-b", OBSERVED_AT)
    assert changed.content_checksum != original.content_checksum


def test_missing_optional_fields_remain_null_and_answer_flags_stay_distinct() -> None:
    wb_payload = _fixture("wb_reviews_synthetic.json")["cases"]["missing_optional"]
    avito_payload = _fixture("avito_reviews_synthetic.json")["cases"]["can_answer_null"]

    wb = normalize_wb_review(wb_payload, 31, 401, "test-run-wb", OBSERVED_AT)
    avito = normalize_avito_review(
        avito_payload, 31, 402, "test-run-avito", OBSERVED_AT
    )

    assert (
        wb.external_product_id,
        wb.source_updated_at,
        wb.rating,
        wb.text,
        wb.can_answer,
        wb.source_status,
    ) == (None, None, None, None, None, None)
    assert wb.answered is False
    assert (
        avito.external_product_id,
        avito.source_updated_at,
        avito.rating,
        avito.text,
        avito.can_answer,
        avito.source_status,
    ) == (None, None, None, None, None, None)
    assert avito.answered is False


def test_avito_can_answer_false_and_answered_are_independent() -> None:
    cases = _fixture("avito_reviews_synthetic.json")["cases"]

    unanswered = normalize_avito_review(
        cases["can_answer_false_string_id"], 32, 403, "test-run-a", OBSERVED_AT
    )
    answered = normalize_avito_review(
        cases["answered"], 32, 403, "test-run-b", OBSERVED_AT
    )

    assert (unanswered.answered, unanswered.can_answer) == (False, False)
    assert (answered.answered, answered.can_answer) == (True, False)


@pytest.mark.parametrize(
    ("fixture_name", "case_name", "normalizer", "error_code"),
    [
        (
            "wb_reviews_synthetic.json",
            "float_id",
            normalize_wb_review,
            "invalid_external_id",
        ),
        (
            "wb_reviews_synthetic.json",
            "boolean_id",
            normalize_wb_review,
            "invalid_external_id",
        ),
        (
            "wb_reviews_synthetic.json",
            "exponent_id",
            normalize_wb_review,
            "invalid_external_id",
        ),
        (
            "wb_reviews_synthetic.json",
            "zero_rating",
            normalize_wb_review,
            "invalid_rating",
        ),
        (
            "wb_reviews_synthetic.json",
            "high_rating",
            normalize_wb_review,
            "invalid_rating",
        ),
        (
            "wb_reviews_synthetic.json",
            "naive_timestamp",
            normalize_wb_review,
            "invalid_timestamp",
        ),
        (
            "avito_reviews_synthetic.json",
            "float_id",
            normalize_avito_review,
            "invalid_external_id",
        ),
        (
            "avito_reviews_synthetic.json",
            "boolean_id",
            normalize_avito_review,
            "invalid_external_id",
        ),
        (
            "avito_reviews_synthetic.json",
            "exponent_id",
            normalize_avito_review,
            "invalid_external_id",
        ),
        (
            "avito_reviews_synthetic.json",
            "invalid_rating",
            normalize_avito_review,
            "invalid_rating",
        ),
        (
            "avito_reviews_synthetic.json",
            "malformed_timestamp",
            normalize_avito_review,
            "invalid_timestamp",
        ),
    ],
)
def test_invalid_source_values_raise_typed_safe_error(
    fixture_name, case_name, normalizer, error_code
) -> None:
    payload = _fixture(fixture_name)["invalid"][case_name]

    with pytest.raises(ReviewNormalizationError) as raised:
        normalizer(payload, 41, 501, "test-invalid-run", OBSERVED_AT)

    assert raised.value.code == error_code


def test_missing_review_id_never_falls_back_to_product_id() -> None:
    payload = {
        "itemId": 61003,
        "createdAt": "2026-09-03T07:00:00Z",
        "text": "[TEST] Avito synthetic missing review identity",
    }

    with pytest.raises(ReviewNormalizationError) as raised:
        normalize_avito_review(payload, 42, 502, "test-invalid-run", OBSERVED_AT)

    assert raised.value.code == "missing_external_review_id"


@pytest.mark.parametrize("external_id", [51001.0, "51001.0", ".5e2", "+51001"])
def test_numeric_like_non_decimal_external_ids_are_rejected(external_id) -> None:
    payload = {
        "reviewId": external_id,
        "createdAt": "2026-09-03T07:00:00Z",
    }

    with pytest.raises(ReviewNormalizationError) as raised:
        normalize_avito_review(payload, 42, 502, "test-invalid-run", OBSERVED_AT)

    assert raised.value.code == "invalid_external_id"


def test_naive_observation_timestamp_is_rejected() -> None:
    payload = _fixture("wb_reviews_synthetic.json")["cases"]["unanswered"]

    with pytest.raises(ReviewNormalizationError) as raised:
        normalize_wb_review(
            payload, 43, 503, "test-invalid-run", datetime(2026, 9, 8, 12, 0)
        )

    assert raised.value.code == "invalid_timestamp"
    assert raised.value.field == "observed_at"


def test_fact_and_error_representations_never_expose_review_text() -> None:
    marker = "[TEST] REDACTION-MARKER-4721"
    payload = {
        "feedback_id": "test-wb-review-redaction-001",
        "created_date": "2026-09-03T12:00:00Z",
        "rating": 5,
        "text": marker,
        "is_answered": False,
    }
    fact = normalize_wb_review(payload, 44, 504, "test-redaction-run", OBSERVED_AT)

    assert marker not in repr(fact)
    assert marker not in str(fact)
    assert "text=<redacted>" in repr(fact)

    payload["rating"] = 0
    with pytest.raises(ReviewNormalizationError) as raised:
        normalize_wb_review(payload, 44, 504, "test-redaction-run", OBSERVED_AT)
    assert marker not in str(raised.value)
    assert marker not in repr(raised.value)


def test_checksum_function_accepts_fact_mapping_and_excludes_observation_fields() -> (
    None
):
    payload = _fixture("avito_reviews_synthetic.json")["cases"]["answered"]
    fact = normalize_avito_review(payload, 45, 505, "test-run-a", OBSERVED_AT)
    as_mapping = {
        "identity": {
            "organization_id": fact.identity.organization_id,
            "marketplace_account_id": fact.identity.marketplace_account_id,
            "marketplace": fact.identity.marketplace.value,
            "external_review_id": fact.identity.external_review_id,
        },
        "external_product_id": fact.external_product_id,
        "source_created_at": fact.source_created_at,
        "source_updated_at": fact.source_updated_at,
        "rating": fact.rating,
        "text": fact.text,
        "answered": fact.answered,
        "can_answer": fact.can_answer,
        "source_status": fact.source_status,
        "observed_at": datetime(2030, 1, 1, tzinfo=timezone.utc),
        "source_run_id": "different-run",
        "source_schema_version": fact.source_schema_version,
        "normalization_version": fact.normalization_version,
    }

    assert review_fact_checksum(as_mapping) == fact.content_checksum


def test_completed_fact_rejects_non_string_checksum() -> None:
    payload = _fixture("wb_reviews_synthetic.json")["cases"]["unanswered"]
    fact = normalize_wb_review(payload, 46, 506, "test-run", OBSERVED_AT)

    with pytest.raises(ReviewNormalizationError) as raised:
        replace(fact, content_checksum=None)

    assert raised.value.code == "invalid_checksum"


def test_contract_source_has_no_runtime_framework_or_client_imports() -> None:
    source_path = (
        Path(__file__).parents[1] / "app" / "reviews" / "canonical_contract.py"
    )
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    imported_roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_roots.add(node.module.split(".")[0])

    assert imported_roots.isdisjoint(
        {"httpx", "requests", "openai", "celery", "sqlalchemy", "fastapi"}
    )


def test_normalization_makes_zero_external_calls(monkeypatch) -> None:
    calls = 0

    def forbidden_call(*_args, **_kwargs):
        nonlocal calls
        calls += 1
        raise AssertionError("external call attempted")

    monkeypatch.setattr(socket, "socket", forbidden_call)
    monkeypatch.setattr(urllib.request, "urlopen", forbidden_call)
    wb_payload = _fixture("wb_reviews_synthetic.json")["cases"]["unanswered"]
    avito_payload = _fixture("avito_reviews_synthetic.json")["cases"]["answered"]

    normalize_wb_review(wb_payload, 51, 601, "test-run-wb", OBSERVED_AT)
    normalize_avito_review(avito_payload, 51, 602, "test-run-avito", OBSERVED_AT)

    assert calls == 0
