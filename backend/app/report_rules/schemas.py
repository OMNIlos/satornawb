from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


PresetName = Literal["standard", "conservative", "aggressive", "custom"]
AutomationAction = Literal["raise_price", "lower_price", "rnp", "liquidation", "stop_ads", "alert", "audit"]
BandLevel = Literal["good", "average", "bad", "unknown"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AbcShare(StrictModel):
    aPct: float = 20
    bPct: float = 30
    cPct: float = 50


class AbcConfig(StrictModel):
    salesShare: AbcShare
    netProfitShare: AbcShare


class HigherBand(StrictModel):
    goodMin: float
    averageMin: float


class MarginBand(StrictModel):
    goodMin: float
    thinMin: float
    lossBelow: float


class DrrBand(StrictModel):
    goodMax: float
    warnMin: float


class RoiBand(StrictModel):
    goodMin: float
    warnBelow: float


class WarnBelowBand(StrictModel):
    warnBelow: float = Field(ge=0)


class CriticalBelowBand(StrictModel):
    criticalBelow: float = Field(ge=0)


class BadBelowBand(StrictModel):
    badBelow: float = Field(ge=0, le=100)


class QualityBands(StrictModel):
    ctrPct: HigherBand
    crPct: HigherBand
    cartToOrderPct: HigherBand
    buyoutPct: HigherBand
    marginPct: MarginBand
    drrPct: DrrBand
    roiPct: RoiBand
    daysToOos: WarnBelowBand
    stockUnits: CriticalBelowBand
    localizationPct: BadBelowBand


class AutomationMapping(StrictModel):
    aaGood: AutomationAction
    badCr: AutomationAction
    loss: AutomationAction
    highDrr: AutomationAction
    oos: AutomationAction
    cWeak: AutomationAction


class ReportRulesConfig(StrictModel):
    abc: AbcConfig
    qualityBands: QualityBands
    automationMapping: AutomationMapping


class ReportRuleProfileView(BaseModel):
    profileId: int | None
    organizationId: int
    version: int
    name: str
    preset: PresetName
    config: ReportRulesConfig
    createdByUserId: str | None
    createdAt: datetime | None
    isActive: bool = True


class RuleRecommendation(BaseModel):
    type: AutomationAction
    state: Literal["draft"] = "draft"
    reason: str
    requiresConfirmation: Literal[True] = True


class RuleEvaluation(BaseModel):
    bands: dict[str, BandLevel]
    status: str
    statusReasons: list[str]
    recommendedActions: list[RuleRecommendation]


class RulesDraftRequest(StrictModel):
    expectedVersion: int = Field(ge=1)
    name: str = Field(min_length=1, max_length=128)
    preset: PresetName
    config: ReportRulesConfig


class RulesSaveRequest(RulesDraftRequest):
    previewToken: str = Field(min_length=20)
