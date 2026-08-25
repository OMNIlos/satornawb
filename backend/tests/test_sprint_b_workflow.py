from __future__ import annotations

import os

from fastapi.testclient import TestClient

from app.main import create_app
from app import repricer_bff as repricer_bff_module
from app.repricer_sprint_b import (
    ApplyDraftRequest,
    ApproveDraftRequest,
    PriceDraftCreateRequest,
    _buyer_price_for_accounting,
    apply_approved_drafts,
    approve_draft,
    create_price_draft,
)
from app.wb_api.client import FakeWbApiClient
from tests.auth_helpers import auth_headers


def client() -> TestClient:
    return TestClient(create_app())


def _valid_draft_payload() -> dict:
    return {
        "scenario": "complete",
        "articleId": "FBBT_42",
        "nmId": 123456,
        "candidateSellerPriceKopecks": 129500,
        "minPriceKopecks": 100000,
        "pMaxKopecks": 180000,
        "economics": {
            "cogsKopecks": 59000,
            "commissionPct": 20,
            "logisticsKopecks": 5000,
            "storageKopecks": 1000,
            "taxKopecks": 2000,
            "buyoutPct": 85,
            "stockUnits": 12,
            "promoActive": False,
        },
        "reason": "manual correction",
    }


def test_recommendation_includes_formula_version_and_source_snapshot():
    response = client().post(
        "/api/v1/wb-repricer/recommendation",
        json={
            "scenario": "complete",
            "articleId": "FBBT_42",
            "nmId": 123456,
            "candidateSellerPriceKopecks": 123000,
            "minPriceKopecks": 100000,
            "economics": {
                "cogsKopecks": 60000,
                "commissionPct": 20,
                "logisticsKopecks": 5000,
                "storageKopecks": 1000,
                "taxKopecks": 2000,
                "buyoutPct": 80,
                "stockUnits": 10,
                "promoActive": False,
            },
        },
    )
    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["formulaVersion"] == "sprint-b-repricer-v1"
    assert payload["guardFormulaVersion"] == "sprint-b-guards-v1"
    assert payload["sourceSnapshot"]["snapshotVersion"] == "wb23-runtime-v1"
    assert payload["normalized"]["currentSppPct"] is not None


def test_candidate_buyer_price_can_include_configured_wallet():
    previous = dict(repricer_bff_module.ALGORITHM_SETTINGS_STATE)
    repricer_bff_module.ALGORITHM_SETTINGS_STATE.update({"sppAccountingMode": "spp_plus_wallet", "wbWalletType": 4})
    try:
        assert _buyer_price_for_accounting(100_000, 26) == 71_040
    finally:
        repricer_bff_module.ALGORITHM_SETTINGS_STATE.clear()
        repricer_bff_module.ALGORITHM_SETTINGS_STATE.update(previous)


def test_draft_blocks_when_required_inputs_are_missing():
    api = client()
    payload = _valid_draft_payload()
    payload["economics"]["cogsKopecks"] = None

    response = api.post("/api/v1/wb-repricer/drafts", json=payload, headers=auth_headers(api, "price_sender"))
    assert response.status_code == 200
    draft = response.json()["data"]
    assert draft["state"] == "blocked"
    assert draft["guardReport"]["canApply"] is False
    assert "WB-23" in draft["guardReport"]["blockers"]


def test_draft_approval_and_apply_flow_reaches_accepted_with_feature_flag_enabled():
    previous = os.environ.get("VELLA_REAL_PRICE_APPLY_ENABLED")
    os.environ["VELLA_REAL_PRICE_APPLY_ENABLED"] = "true"
    try:
        api = client()
        create_response = api.post("/api/v1/wb-repricer/drafts", json=_valid_draft_payload(), headers=auth_headers(api, "price_sender"))
        assert create_response.status_code == 200
        draft = create_response.json()["data"]
        assert draft["state"] == "draft"

        draft_id = draft["draftId"]
        approve = api.post(
            f"/api/v1/wb-repricer/drafts/{draft_id}/approve",
            json={"approvalRef": "APR-SPRINT-B-001", "reason": "price manager approval"},
            headers=auth_headers(api, "price_sender"),
        )
        assert approve.status_code == 200
        assert approve.json()["data"]["state"] == "approved"

        apply_response = api.post(
            f"/api/v1/wb-repricer/drafts/{draft_id}/apply",
            json={"scenario": "complete", "pollMaxAttempts": 3, "pollDelaySeconds": 0},
            headers=auth_headers(api, "price_sender"),
        )
        assert apply_response.status_code == 200
        job = apply_response.json()["data"]
        assert job["state"] == "accepted"
        assert job["wbUploadId"] is not None

    finally:
        if previous is None:
            os.environ.pop("VELLA_REAL_PRICE_APPLY_ENABLED", None)
        else:
            os.environ["VELLA_REAL_PRICE_APPLY_ENABLED"] = previous


def test_bulk_apply_sends_all_prices_in_one_wb_upload():
    payloads = [
        _valid_draft_payload(),
        {
            **_valid_draft_payload(),
            "articleId": "HCBT_19",
            "nmId": 123457,
            "candidateSellerPriceKopecks": 250_000,
            "minPriceKopecks": 180_000,
            "pMaxKopecks": 350_000,
            "economics": {
                **_valid_draft_payload()["economics"],
                "cogsKopecks": 100_000,
            },
        },
    ]
    draft_ids: list[str] = []
    for index, payload in enumerate(payloads):
        current_price = int(payload["candidateSellerPriceKopecks"])
        draft = create_price_draft(
            actor_id="price_sender",
            actor_role="price_sender",
            client=FakeWbApiClient(),
            payload=PriceDraftCreateRequest.model_validate(payload),
            sku_row={
                "meta": {
                    "articleId": payload["articleId"],
                    "nmId": payload["nmId"],
                    "currentPriceKopecks": current_price,
                },
                "analytics": {
                    "buyerPriceNoWalletKopecks": round(current_price * 0.9),
                    "avgPriceWithSppKopecks": round(current_price * 0.9),
                    "sppPct": 10,
                },
            },
        )
        assert draft.state == "draft"
        draft_ids.append(draft.draftId)
        approve_draft(
            draft_id=draft.draftId,
            actor_id="price_sender",
            request=ApproveDraftRequest(approvalRef=f"APR-BULK-{index}"),
        )

    wb_client = FakeWbApiClient(fixtures={"/api/v2/upload/task": {"data": {"id": 777}}})
    jobs = apply_approved_drafts(
        draft_ids=draft_ids,
        client=wb_client,
        real_apply_enabled=True,
        local_apply_enabled=False,
        request=ApplyDraftRequest(skipStatusPoll=True),
    )

    assert [job.state for job in jobs] == ["sent", "sent"]
    assert len(wb_client.requests) == 1
    assert [row["nmID"] for row in wb_client.requests[0].jsonBody["data"]] == [123456, 123457]


def test_apply_failure_has_retry_and_retry_can_recover():
    previous = os.environ.get("VELLA_REAL_PRICE_APPLY_ENABLED")
    os.environ["VELLA_REAL_PRICE_APPLY_ENABLED"] = "true"
    try:
        api = client()
        created = api.post("/api/v1/wb-repricer/drafts", json=_valid_draft_payload(), headers=auth_headers(api, "price_sender"))
        assert created.status_code == 200
        draft_id = created.json()["data"]["draftId"]

        approved = api.post(
            f"/api/v1/wb-repricer/drafts/{draft_id}/approve",
            json={"approvalRef": "APR-SPRINT-B-002"},
            headers=auth_headers(api, "price_sender"),
        )
        assert approved.status_code == 200

        failed_apply = api.post(
            f"/api/v1/wb-repricer/drafts/{draft_id}/apply",
            json={"scenario": "server_error"},
            headers=auth_headers(api, "price_sender"),
        )
        assert failed_apply.status_code == 200
        failed_job = failed_apply.json()["data"]
        assert failed_job["state"] == "needs_attention"
        assert failed_job["retryCount"] == 1
        assert failed_job["nextRetryAt"] is not None

        retried = api.post(
            f"/api/v1/wb-repricer/jobs/{failed_job['jobId']}/retry",
            json={"scenario": "complete"},
            headers=auth_headers(api, "price_sender"),
        )
        assert retried.status_code == 200
        recovered = retried.json()["data"]
        assert recovered["state"] in {"accepted", "sent"}

    finally:
        if previous is None:
            os.environ.pop("VELLA_REAL_PRICE_APPLY_ENABLED", None)
        else:
            os.environ["VELLA_REAL_PRICE_APPLY_ENABLED"] = previous


def test_legacy_direct_apply_endpoint_is_blocked():
    api = client()
    response = api.post(
        "/api/v1/wb-repricer/actions/price-apply",
        json={
            "scenario": "complete",
            "dryRun": False,
            "rows": [{"nmId": 123456, "priceKopecks": 139000, "discountPct": 12}],
        },
        headers=auth_headers(api, "price_sender"),
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "HTTP_409"
