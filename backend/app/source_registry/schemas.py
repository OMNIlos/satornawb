from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator


RegistryStatus = Literal[
    "confirmed",
    "needs_api_discovery",
    "needs_client",
    "manual_fallback",
    "requires_own_cache",
    "business_config",
    "blocked",
    "disabled",
]
BlockerLifecycle = Literal["BLOCKER", "CONFIRM", "LATER"]
FormulaStatus = Literal["confirmed", "needs_client", "needs_api_discovery", "draft", "disabled", "derived"]


class BlockerCatalogItem(BaseModel):
    blockerId: str = Field(min_length=1)
    lifecycleStatus: BlockerLifecycle
    question: str = Field(min_length=1)
    owner: str = Field(min_length=1)
    impactArea: str = Field(min_length=1)
    resolutionNeeded: str = Field(min_length=1)
    sourceRef: str = Field(min_length=1)


class FormulaCatalogItem(BaseModel):
    formulaId: str = Field(min_length=1)
    formulaName: str = Field(min_length=1)
    inputs: str = Field(min_length=1)
    outputUnits: str = Field(min_length=1)
    rule: str = Field(min_length=1)
    rounding: str = Field(min_length=1)
    owner: str = Field(min_length=1)
    status: FormulaStatus
    usedBy: str = Field(min_length=1)
    blockerIds: list[str]
    sourceRef: str = Field(min_length=1)


class SourceRegistryItem(BaseModel):
    rowId: int = Field(ge=1)
    screen: str = Field(min_length=1)
    metricAction: str = Field(min_length=1)
    module: str = Field(min_length=1)
    sourceName: str = Field(min_length=1)
    sourceField: str = Field(min_length=1)
    formulaText: str = Field(min_length=1)
    formulaId: str = Field(min_length=1)
    refreshPolicy: str = Field(min_length=1)
    fallbackPolicy: str = Field(min_length=1)
    freshnessConfidence: str = Field(min_length=1)
    status: RegistryStatus
    blockerIds: list[str]
    criticalForApply: bool
    sourceRef: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_confirmed_rows(self) -> SourceRegistryItem:
        if self.status != "confirmed":
            return self
        required = [
            self.sourceName,
            self.sourceField,
            self.formulaText,
            self.formulaId,
            self.refreshPolicy,
            self.fallbackPolicy,
            self.freshnessConfidence,
        ]
        if any(not item.strip() for item in required):
            raise ValueError("confirmed source registry row must include source/formula/fallback/freshness fields")
        return self
