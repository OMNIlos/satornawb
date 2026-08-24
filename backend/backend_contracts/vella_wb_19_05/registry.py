from __future__ import annotations

from pydantic import BaseModel, Field


class BlockerRegistryEntry(BaseModel):
    blockerId: str = Field(min_length=1)
    status: str = Field(min_length=1)
    module: str = Field(min_length=1)
    surface: str = Field(min_length=1)
    sourceStatus: str = Field(min_length=1)
    confidence: str = Field(min_length=1)
    owner: str = Field(min_length=1)
    nextAction: str = Field(min_length=1)
    evidenceRef: str = Field(min_length=1)


BLOCKER_REGISTRY: dict[str, BlockerRegistryEntry] = {
    "WB-02": BlockerRegistryEntry(
        blockerId="WB-02",
        status="resolved",
        module="ads",
        surface="ads_rnp_abc_pnl",
        sourceStatus="fresh",
        confidence="high",
        owner="backend discovery",
        nextAction="Use WB Ads API chain promotion/count -> adverts -> fullstats with exact_sku/campaign_sku/campaign_only attribution.",
        evidenceRef="docs/open-questions-current.md#WB-02",
    ),
    "WB-03": BlockerRegistryEntry(
        blockerId="WB-03",
        status="blocked",
        module="reports",
        surface="field_mapping",
        sourceStatus="unknown",
        confidence="blocked",
        owner="backend discovery",
        nextAction="Confirm endpoint/export mapping for WB report fields",
        evidenceRef="docs/open-questions-current.md#WB-03",
    ),
    "WB-06": BlockerRegistryEntry(
        blockerId="WB-06",
        status="resolved",
        module="repricer",
        surface="price_guard",
        sourceStatus="fresh",
        confidence="high",
        owner="backend discovery",
        nextAction="Use Prices & Discounts API POST /api/v2/list/goods/filter as SPP-like source with clubDiscount fallback.",
        evidenceRef="docs/open-questions-current.md#WB-06",
    ),
    "WB-11": BlockerRegistryEntry(
        blockerId="WB-11",
        status="blocked",
        module="rnp",
        surface="formulas",
        sourceStatus="unknown",
        confidence="blocked",
        owner="client question",
        nextAction="Confirm DRR/ROI/ROMI formulas with Maria and Maksim",
        evidenceRef="docs/open-questions-current.md#WB-11",
    ),
    "WB-12": BlockerRegistryEntry(
        blockerId="WB-12",
        status="blocked",
        module="pnl",
        surface="manual_costs",
        sourceStatus="unknown",
        confidence="blocked",
        owner="client question",
        nextAction="Confirm storage and overhead allocation rules",
        evidenceRef="docs/open-questions-current.md#WB-12",
    ),
    "WB-13": BlockerRegistryEntry(
        blockerId="WB-13",
        status="blocked",
        module="pnl",
        surface="taxes",
        sourceStatus="unknown",
        confidence="blocked",
        owner="client question",
        nextAction="Confirm tax/VAT source and allocation rules",
        evidenceRef="docs/open-questions-current.md#WB-13",
    ),
    "WB-14A": BlockerRegistryEntry(
        blockerId="WB-14A",
        status="unknown",
        module="plan_fact",
        surface="brand_dimension",
        sourceStatus="unknown",
        confidence="blocked",
        owner="client question",
        nextAction="Confirm whether brand plan is a dimension, not a separate report",
        evidenceRef="docs/open-questions-current.md#WB-14A",
    ),
    "WB-19A": BlockerRegistryEntry(
        blockerId="WB-19A",
        status="unknown",
        module="abc",
        surface="locomotive_aggregates",
        sourceStatus="unknown",
        confidence="blocked",
        owner="client question",
        nextAction="Confirm first locomotive aggregate set",
        evidenceRef="docs/open-questions-current.md#WB-19A",
    ),
    "WB-22": BlockerRegistryEntry(
        blockerId="WB-22",
        status="resolved",
        module="repricer",
        surface="price_apply",
        sourceStatus="fresh",
        confidence="high",
        owner="backend discovery",
        nextAction="Keep upload/poll/details mapping synced with WB docs and monitor row-level error taxonomy",
        evidenceRef="docs/open-questions-current.md#WB-22",
    ),
    "WB-23": BlockerRegistryEntry(
        blockerId="WB-23",
        status="resolved",
        module="cross_cutting",
        surface="freshness_confidence",
        sourceStatus="fresh",
        confidence="high",
        owner="backend discovery",
        nextAction="Keep WB-23 freshness policy catalog in sync with repricer critical metrics",
        evidenceRef="docs/open-questions-current.md#WB-23",
    ),
}
