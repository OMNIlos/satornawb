from __future__ import annotations

from fastapi import APIRouter

from app.contracts.adapter_result import AdapterFreshness, AdapterResult
from app.contracts.envelopes import DataEnvelope
from app.discovery.repricer_probes import (
    RepricerProbeRequest,
    RepricerProbeResponse,
    run_read_prices_probe,
    run_task_history_probe,
    run_upload_lifecycle_probe,
)
from app.discovery.repricer_sources import (
    RepricerDiscoveryMap,
    RepricerDiscoveryReadiness,
    build_repricer_discovery_map,
    build_repricer_discovery_readiness,
)
from app.wb_api.client import RateLimitedWbApiClient, build_wb_client


router = APIRouter(prefix="/api/v1/wb-discovery", tags=["wb-source-discovery"])


@router.get("/repricer/source-map", response_model=RepricerDiscoveryMap)
def get_repricer_source_map() -> RepricerDiscoveryMap:
    return build_repricer_discovery_map()


@router.get("/repricer/readiness", response_model=RepricerDiscoveryReadiness)
def get_repricer_readiness() -> RepricerDiscoveryReadiness:
    return build_repricer_discovery_readiness()


@router.get(
    "/repricer/readiness/adapter-result",
    response_model=DataEnvelope[AdapterResult[RepricerDiscoveryReadiness]],
)
def get_repricer_readiness_adapter_result() -> DataEnvelope[AdapterResult[RepricerDiscoveryReadiness]]:
    readiness = build_repricer_discovery_readiness()
    status = "success" if readiness.canUnblockPriceGuard else "blocked_by_guard"
    return DataEnvelope(
        data=AdapterResult[RepricerDiscoveryReadiness](
            status=status,
            data=readiness,
            freshness=AdapterFreshness(
                source="repricer_discovery_readiness",
                isStale=False,
                confidence="high",
            ),
            evidenceRefs=[
                "docs/open-questions-current.md#WB-22",
                "docs/handoffs/wb-backend-source-registry.md",
            ],
            nextValidActions=["run_probe_wb22", "approve_write_path", "enable_real_apply_after_audit"],
        )
    )


@router.post("/repricer/probes/read-prices", response_model=RepricerProbeResponse)
def probe_repricer_read_prices(request: RepricerProbeRequest) -> RepricerProbeResponse:
    client = RateLimitedWbApiClient(inner=build_wb_client(request.scenario))
    return run_read_prices_probe(client, request.articleId)


@router.post("/repricer/probes/task-history", response_model=RepricerProbeResponse)
def probe_repricer_task_history(request: RepricerProbeRequest) -> RepricerProbeResponse:
    client = RateLimitedWbApiClient(inner=build_wb_client(request.scenario))
    return run_task_history_probe(client, request.articleId)


@router.post("/repricer/probes/upload-lifecycle", response_model=RepricerProbeResponse)
def probe_repricer_upload_lifecycle(request: RepricerProbeRequest) -> RepricerProbeResponse:
    client = RateLimitedWbApiClient(inner=build_wb_client(request.scenario))
    return run_upload_lifecycle_probe(
        client,
        article_id=request.articleId,
        upload_id=request.uploadId,
        max_polls=request.maxPolls,
    )
