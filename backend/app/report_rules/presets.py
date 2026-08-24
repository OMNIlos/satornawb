from __future__ import annotations

from copy import deepcopy

from app.report_rules.schemas import ReportRulesConfig


FIXED_ABC = {
    "salesShare": {"aPct": 20, "bPct": 30, "cPct": 50},
    "netProfitShare": {"aPct": 20, "bPct": 30, "cPct": 50},
}
DEFAULT_AUTOMATION = {
    "aaGood": "raise_price",
    "badCr": "rnp",
    "loss": "liquidation",
    "highDrr": "stop_ads",
    "oos": "alert",
    "cWeak": "audit",
}
PRESET_BANDS = {
    "standard": {
        "ctrPct": {"goodMin": 10, "averageMin": 6},
        "crPct": {"goodMin": 4, "averageMin": 2},
        "cartToOrderPct": {"goodMin": 45, "averageMin": 25},
        "buyoutPct": {"goodMin": 80, "averageMin": 60},
        "marginPct": {"goodMin": 25, "thinMin": 10, "lossBelow": 0},
        "drrPct": {"goodMax": 9, "warnMin": 14},
        "roiPct": {"goodMin": 250, "warnBelow": 100},
        "daysToOos": {"warnBelow": 7},
        "stockUnits": {"criticalBelow": 12},
        "localizationPct": {"badBelow": 60},
    },
    "conservative": {
        "ctrPct": {"goodMin": 12, "averageMin": 7},
        "crPct": {"goodMin": 5, "averageMin": 2.5},
        "cartToOrderPct": {"goodMin": 50, "averageMin": 30},
        "buyoutPct": {"goodMin": 84, "averageMin": 65},
        "marginPct": {"goodMin": 30, "thinMin": 14, "lossBelow": 2},
        "drrPct": {"goodMax": 8, "warnMin": 12},
        "roiPct": {"goodMin": 300, "warnBelow": 130},
        "daysToOos": {"warnBelow": 10},
        "stockUnits": {"criticalBelow": 18},
        "localizationPct": {"badBelow": 68},
    },
    "aggressive": {
        "ctrPct": {"goodMin": 8, "averageMin": 4.5},
        "crPct": {"goodMin": 3.2, "averageMin": 1.5},
        "cartToOrderPct": {"goodMin": 38, "averageMin": 20},
        "buyoutPct": {"goodMin": 76, "averageMin": 55},
        "marginPct": {"goodMin": 20, "thinMin": 7, "lossBelow": -3},
        "drrPct": {"goodMax": 11, "warnMin": 18},
        "roiPct": {"goodMin": 180, "warnBelow": 70},
        "daysToOos": {"warnBelow": 5},
        "stockUnits": {"criticalBelow": 8},
        "localizationPct": {"badBelow": 52},
    },
}


def preset_config(name: str) -> ReportRulesConfig:
    selected = name if name in PRESET_BANDS else "standard"
    return ReportRulesConfig.model_validate(
        {"abc": deepcopy(FIXED_ABC), "qualityBands": deepcopy(PRESET_BANDS[selected]), "automationMapping": deepcopy(DEFAULT_AUTOMATION)}
    )


PRESET_CONFIGS = {name: preset_config(name) for name in PRESET_BANDS}
