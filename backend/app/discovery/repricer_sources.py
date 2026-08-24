from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, Field, model_validator

from app.wb23_runtime import wb23_freshness_policies


DiscoveryStatus = Literal["confirmed", "candidate", "blocked", "rejected"]
HttpMethod = Literal["GET", "POST", "PATCH", "PUT", "DELETE"]
RiskLevel = Literal["read_only", "write_candidate", "mutating_blocked"]


class CandidateEndpoint(BaseModel):
    blockerId: str = Field(min_length=1)
    method: HttpMethod
    path: str = Field(min_length=1)
    category: str = Field(min_length=1)
    sourceUrl: str = Field(min_length=1)
    evidenceRef: str = Field(min_length=1)
    status: DiscoveryStatus
    riskLevel: RiskLevel
    expectedFields: List[str]
    openQuestions: List[str]
    requiredTokenPath: List[str]
    canRunInReadOnlyDiscovery: bool

    @model_validator(mode="after")
    def validate_mutation_gates(self) -> CandidateEndpoint:
        if self.riskLevel != "read_only" and self.canRunInReadOnlyDiscovery:
            raise ValueError("Write or mutating candidates cannot run in read-only discovery")
        if self.status == "confirmed" and self.openQuestions:
            raise ValueError("Confirmed endpoint cannot carry unresolved open questions")
        return self


class FreshnessPolicy(BaseModel):
    sourceId: str = Field(min_length=1)
    blockerId: str = Field(min_length=1)
    maxAgeMinutes: int = Field(gt=0)
    staleAction: Literal["allow_partial", "block_auto_apply", "block_report_final"]
    confidenceWhenFresh: Literal["high", "medium", "low"]
    confidenceWhenStale: Literal["low", "blocked"]


class DiscoveryCluster(BaseModel):
    blockerId: str = Field(min_length=1)
    title: str = Field(min_length=1)
    status: DiscoveryStatus
    owner: str = Field(min_length=1)
    nextAction: str = Field(min_length=1)
    unblockCriteria: List[str]
    candidates: List[CandidateEndpoint]
    freshnessPolicies: List[FreshnessPolicy]

    @model_validator(mode="after")
    def validate_blocked_cluster(self) -> DiscoveryCluster:
        if self.status in {"blocked", "candidate"} and not self.unblockCriteria:
            raise ValueError("Blocked or candidate discovery cluster needs unblock criteria")
        return self


class RepricerDiscoveryMap(BaseModel):
    generatedFrom: List[str]
    overallStatus: Literal["blocked", "partial", "ready"]
    realPriceApplyEnabled: bool
    canUnblockPriceGuard: bool
    clusters: List[DiscoveryCluster]

    @model_validator(mode="after")
    def validate_safe_defaults(self) -> RepricerDiscoveryMap:
        if self.realPriceApplyEnabled:
            raise ValueError("Discovery map must not enable real price apply")
        if self.canUnblockPriceGuard and any(cluster.status != "confirmed" for cluster in self.clusters):
            raise ValueError("Price guard cannot unblock while any discovery cluster is unresolved")
        return self


class RepricerDiscoveryReadiness(BaseModel):
    canUnblockPriceGuard: bool
    realPriceApplyEnabled: bool
    blockingIds: List[str]
    nextProbeOrder: List[str]
    reason: str = Field(min_length=1)


METHODS_HANDOFF = "research/22-wb-api-developer-portal-2026-05/backend-brief/wb-api-methods-for-vella.md"
LIMITS_HANDOFF = "research/22-wb-api-developer-portal-2026-05/backend-brief/wb-api-limits-and-retry-policy.md"
OPEN_QUESTIONS = "docs/open-questions-current.md"


def _candidate(
    blocker_id: str,
    method: HttpMethod,
    path: str,
    category: str,
    source_anchor: str,
    status: DiscoveryStatus,
    risk_level: RiskLevel,
    expected_fields: List[str],
    open_questions: List[str],
    required_token_path: Optional[List[str]] = None,
) -> CandidateEndpoint:
    return CandidateEndpoint(
        blockerId=blocker_id,
        method=method,
        path=path,
        category=category,
        sourceUrl=f"https://dev.wildberries.ru/swagger/{source_anchor}",
        evidenceRef=METHODS_HANDOFF,
        status=status,
        riskLevel=risk_level,
        expectedFields=expected_fields,
        openQuestions=open_questions,
        requiredTokenPath=required_token_path or ["Base Token + X-Client-Secret", "Service Token + X-Client-Secret"],
        canRunInReadOnlyDiscovery=risk_level == "read_only",
    )


def build_repricer_discovery_map() -> RepricerDiscoveryMap:
    clusters = [
        DiscoveryCluster(
            blockerId="WB-06",
            title="SPP source by SKU",
            status="confirmed",
            owner="backend discovery",
            nextAction="Use POST /api/v2/list/goods/filter as primary SPP-like source (clubDiscount + clubDiscountedPrice) with guard fallbacks.",
            unblockCriteria=[
                "POST /api/v2/list/goods/filter returns nmID, discount, clubDiscount and sizes[].clubDiscountedPrice.",
                "SPP-like percent is taken from clubDiscount or derived from discountedPrice and clubDiscountedPrice.",
                "If clubDiscount data is missing or stale, auto-apply remains blocked by guard.",
            ],
            candidates=[
                _candidate(
                    "WB-06",
                    "POST",
                    "/api/v2/list/goods/filter",
                    "Products / prices",
                    "products#post--api-v2-list-goods-filter",
                    "confirmed",
                    "read_only",
                    [
                        "nmID",
                        "discount",
                        "clubDiscount",
                        "sizes[].price",
                        "sizes[].discountedPrice",
                        "sizes[].clubDiscountedPrice",
                    ],
                    [],
                ),
                _candidate(
                    "WB-06",
                    "GET",
                    "/api/v2/list/goods/size/nm",
                    "Products / prices",
                    "products#get--api-v2-list-goods-size-nm",
                    "confirmed",
                    "read_only",
                    ["nmID", "sizes", "discount", "clubDiscount"],
                    [],
                ),
            ],
            freshnessPolicies=[
                FreshnessPolicy(
                    sourceId="wb-products-prices",
                    blockerId="WB-06",
                    maxAgeMinutes=60,
                    staleAction="block_auto_apply",
                    confidenceWhenFresh="high",
                    confidenceWhenStale="blocked",
                )
            ],
        ),
        DiscoveryCluster(
            blockerId="WB-22",
            title="Price apply, task status and row errors",
            status="confirmed",
            owner="backend discovery",
            nextAction="Use /api/v2/upload/task + /api/v2/history/tasks + /api/v2/history/goods/task for production apply lifecycle with audit gates.",
            unblockCriteria=[
                "Price upload endpoint payload is mapped for nmId/price/discount/minPrice.",
                "Upload lifecycle is mapped through processed state/detail endpoints.",
                "Task status/history endpoint maps row-level success and error states.",
                "Retry/backoff remains enforced by adapter + API rate policy.",
                "Manual approval/audit gate exists before enabling write mutations in production.",
            ],
            candidates=[
                _candidate(
                    "WB-22",
                    "POST",
                    "/api/v2/upload/task",
                    "Products / prices",
                    "products#post--api-v2-upload-task",
                    "confirmed",
                    "write_candidate",
                    ["nmId", "price", "discount", "minPrice"],
                    [],
                ),
                _candidate(
                    "WB-22",
                    "POST",
                    "/api/v2/upload/task/size",
                    "Products / prices",
                    "products#post--api-v2-upload-task-size",
                    "confirmed",
                    "write_candidate",
                    ["nmId", "sizeId", "price", "discount"],
                    [],
                ),
                _candidate(
                    "WB-22",
                    "GET",
                    "/api/v2/buffer/tasks",
                    "Products / prices",
                    "products#get--api-v2-buffer-tasks",
                    "confirmed",
                    "read_only",
                    ["uploadID", "status", "uploadDate", "activationDate", "overAllGoodsNumber", "successGoodsNumber"],
                    [],
                ),
                _candidate(
                    "WB-22",
                    "GET",
                    "/api/v2/buffer/goods/task",
                    "Products / prices",
                    "products#get--api-v2-buffer-goods-task",
                    "confirmed",
                    "read_only",
                    ["nmID", "sizeID", "price", "discount", "errors"],
                    [],
                ),
                _candidate(
                    "WB-22",
                    "GET",
                    "/api/v2/history/tasks",
                    "Products / prices",
                    "products#get--api-v2-history-tasks",
                    "confirmed",
                    "read_only",
                    ["uploadID", "status", "uploadDate", "activationDate", "overAllGoodsNumber", "successGoodsNumber"],
                    [],
                ),
                _candidate(
                    "WB-22",
                    "GET",
                    "/api/v2/history/goods/task",
                    "Products / prices",
                    "products#get--api-v2-history-goods-task",
                    "confirmed",
                    "read_only",
                    ["nmID", "sizeID", "price", "discount", "errors"],
                    [],
                ),
                _candidate(
                    "WB-22",
                    "GET",
                    "/api/v2/quarantine/goods",
                    "Products / prices",
                    "products#get--api-v2-quarantine-goods",
                    "confirmed",
                    "read_only",
                    ["nmId", "sizeId", "reason", "price", "discount"],
                    [],
                ),
            ],
            freshnessPolicies=[
                FreshnessPolicy(
                    sourceId="wb-price-task-history",
                    blockerId="WB-22",
                    maxAgeMinutes=15,
                    staleAction="block_auto_apply",
                    confidenceWhenFresh="high",
                    confidenceWhenStale="blocked",
                )
            ],
        ),
        DiscoveryCluster(
            blockerId="WB-23",
            title="Freshness/confidence registry for price-critical sources",
            status="confirmed",
            owner="backend discovery",
            nextAction="Use data-driven WB-23 freshness policy catalog in runtime guard and expose it via API.",
            unblockCriteria=[
                "Critical metrics expose TTL, stale action and confidence downgrade as runtime policy rows.",
                "Price before/after SPP, SPP percent, margin, p_min/p_max and apply status have explicit freshness behavior.",
                "Guard keeps auto-apply blocked when any critical metric is stale/blocked/unknown.",
            ],
            candidates=[
                _candidate(
                    "WB-23",
                    "GET",
                    "/api/v2/history/tasks",
                    "Products / prices",
                    "products#get--api-v2-history-tasks",
                    "confirmed",
                    "read_only",
                    ["uploadID", "status", "overAllGoodsNumber", "successGoodsNumber"],
                    [],
                ),
                _candidate(
                    "WB-23",
                    "POST",
                    "/api/v2/list/goods/filter",
                    "Products / prices",
                    "products#post--api-v2-list-goods-filter",
                    "confirmed",
                    "read_only",
                    ["nmID", "clubDiscount", "sizes[].discountedPrice", "sizes[].clubDiscountedPrice"],
                    [],
                ),
            ],
            freshnessPolicies=[
                FreshnessPolicy(
                    sourceId=policy.metricId,
                    blockerId="WB-23",
                    maxAgeMinutes=policy.ttlMinutes,
                    staleAction=policy.staleAction,
                    confidenceWhenFresh=policy.confidenceWhenFresh,
                    confidenceWhenStale=policy.confidenceWhenStale,
                )
                for policy in wb23_freshness_policies()
            ],
        ),
    ]
    return RepricerDiscoveryMap(
        generatedFrom=[METHODS_HANDOFF, LIMITS_HANDOFF, OPEN_QUESTIONS],
        overallStatus="ready",
        realPriceApplyEnabled=False,
        canUnblockPriceGuard=True,
        clusters=clusters,
    )


def build_repricer_discovery_readiness() -> RepricerDiscoveryReadiness:
    discovery_map = build_repricer_discovery_map()
    blocking_ids = [cluster.blockerId for cluster in discovery_map.clusters if cluster.status != "confirmed"]
    return RepricerDiscoveryReadiness(
        canUnblockPriceGuard=not blocking_ids,
        realPriceApplyEnabled=False,
        blockingIds=blocking_ids,
        nextProbeOrder=[],
        reason="SPP source, price apply lifecycle mapping and WB-23 freshness policies are configured.",
    )
