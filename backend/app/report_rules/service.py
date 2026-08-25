from __future__ import annotations

import base64
import hashlib
import hmac
import json
import math
import time
from copy import deepcopy
from typing import Any

from app.config import get_settings
from app.report_rules.presets import FIXED_ABC
from app.report_rules.schemas import BandLevel, ReportRuleProfileView, ReportRulesConfig, RuleEvaluation, RuleRecommendation


class ReportRulesValidationError(ValueError):
    def __init__(self, errors: list[dict[str, str]]):
        super().__init__("invalid report rules")
        self.errors = errors


class PreviewTokenError(ValueError):
    pass


def normalize_config(config: ReportRulesConfig | dict[str, Any]) -> ReportRulesConfig:
    normalized = ReportRulesConfig.model_validate(config).model_copy(deep=True)
    bands = normalized.qualityBands
    checks = [
        (bands.ctrPct.goodMin > bands.ctrPct.averageMin, "qualityBands.ctrPct"),
        (bands.crPct.goodMin > bands.crPct.averageMin, "qualityBands.crPct"),
        (bands.cartToOrderPct.goodMin > bands.cartToOrderPct.averageMin, "qualityBands.cartToOrderPct"),
        (bands.buyoutPct.goodMin > bands.buyoutPct.averageMin, "qualityBands.buyoutPct"),
        (bands.marginPct.goodMin > bands.marginPct.thinMin > bands.marginPct.lossBelow, "qualityBands.marginPct"),
        (bands.drrPct.goodMax < bands.drrPct.warnMin, "qualityBands.drrPct"),
        (bands.roiPct.goodMin > bands.roiPct.warnBelow, "qualityBands.roiPct"),
    ]
    errors = [{"path": path, "message": "Нарушен порядок порогов"} for valid, path in checks if not valid]
    if errors:
        raise ReportRulesValidationError(errors)
    normalized.abc = normalized.abc.model_validate(FIXED_ABC)
    return normalized


def config_hash(config: ReportRulesConfig) -> str:
    raw = json.dumps(normalize_config(config).model_dump(mode="json"), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _number(metrics: dict[str, Any], key: str) -> float | None:
    if metrics.get("sourceTrusted") is False:
        return None
    value = metrics.get(key)
    if isinstance(value, bool) or value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _higher(value: float | None, good: float, average: float) -> BandLevel:
    if value is None:
        return "unknown"
    if value >= good:
        return "good"
    if value >= average:
        return "average"
    return "bad"


def _lower(value: float | None, good: float, warn: float) -> BandLevel:
    if value is None:
        return "unknown"
    if value <= good:
        return "good"
    if value >= warn:
        return "bad"
    return "average"


def _margin(value: float | None, good: float, thin: float, loss: float) -> BandLevel:
    if value is None:
        return "unknown"
    if value >= good:
        return "good"
    if value >= thin:
        return "average"
    return "bad" if value < loss else "average"


def evaluate_metrics(metrics: dict[str, Any], profile: ReportRuleProfileView) -> RuleEvaluation:
    b = profile.config.qualityBands
    values = {key: _number(metrics, key) for key in (
        "ctrPct", "crPct", "cartToOrderPct", "buyoutPct", "marginPct", "drrPct", "roiPct", "daysToOos", "stockUnits", "localizationPct", "impressions"
    )}
    bands: dict[str, BandLevel] = {
        "ctrPct": _higher(values["ctrPct"], b.ctrPct.goodMin, b.ctrPct.averageMin),
        "crPct": _higher(values["crPct"], b.crPct.goodMin, b.crPct.averageMin),
        "cartToOrderPct": _higher(values["cartToOrderPct"], b.cartToOrderPct.goodMin, b.cartToOrderPct.averageMin),
        "buyoutPct": _higher(values["buyoutPct"], b.buyoutPct.goodMin, b.buyoutPct.averageMin),
        "marginPct": _margin(values["marginPct"], b.marginPct.goodMin, b.marginPct.thinMin, b.marginPct.lossBelow),
        "drrPct": _lower(values["drrPct"], b.drrPct.goodMax, b.drrPct.warnMin),
        "roiPct": _higher(values["roiPct"], b.roiPct.goodMin, b.roiPct.warnBelow),
        "daysToOos": "unknown" if values["daysToOos"] is None else ("bad" if values["daysToOos"] <= b.daysToOos.warnBelow else "good"),
        "stockUnits": "unknown" if values["stockUnits"] is None else ("bad" if values["stockUnits"] < b.stockUnits.criticalBelow else "good"),
        "localizationPct": "unknown" if values["localizationPct"] is None else ("bad" if values["localizationPct"] < b.localizationPct.badBelow else "good"),
    }
    reasons: list[str] = []
    drafts: list[RuleRecommendation] = []
    mapping = profile.config.automationMapping

    def add(reason: str, action: str, message: str) -> None:
        if any(item.reason == reason and item.type == action for item in drafts):
            return
        reasons.append(message)
        drafts.append(RuleRecommendation(type=action, reason=reason))

    margin = values["marginPct"]
    if margin is not None and margin < b.marginPct.lossBelow:
        add("loss", mapping.loss, f"Маржа {margin:g}% ниже loss-порога {b.marginPct.lossBelow:g}%")
    oos = bands["daysToOos"] == "bad" or bands["stockUnits"] == "bad"
    if oos:
        add("oos", mapping.oos, "Остаток или покрытие ниже OOS-порога")
    if bands["drrPct"] == "bad" and values["roiPct"] is not None and values["roiPct"] < b.roiPct.warnBelow:
        add("highDrr", mapping.highDrr, "ДРР выше warn-порога, ROI ниже warn-порога")
    if (
        bands["crPct"] == "bad" or bands["cartToOrderPct"] == "bad"
    ) and (values["impressions"] or 0) >= 500:
        add("badCr", mapping.badCr, "Конверсия ниже порога при достаточном числе показов")
    abc_code = str(metrics.get("abcCode") or "")
    if abc_code == "AA" and margin is not None and margin >= b.marginPct.goodMin:
        add("aaGood", mapping.aaGood, "AA и маржа выше good-порога")
    if "C" in abc_code or (margin is not None and margin < b.marginPct.thinMin):
        add("cWeak", mapping.cWeak, "C-класс или маржа ниже thin-порога")

    if drafts:
        status = "risk" if any(item.reason in {"loss", "oos", "highDrr", "badCr"} for item in drafts) else "opportunity"
    elif any(level != "unknown" for level in bands.values()):
        status = "normal"
    else:
        status = "unknown"
    return RuleEvaluation(bands=bands, status=status, statusReasons=reasons, recommendedActions=drafts)


def evaluate_rows(rows: list[dict[str, Any]], profile: ReportRuleProfileView) -> list[dict[str, Any]]:
    return [{**row, "ruleEvaluation": evaluate_metrics(row, profile).model_dump(mode="json")} for row in rows]


def issue_preview_token(organization_id: int, expected_version: int, config: ReportRulesConfig, ttl_seconds: int = 900) -> str:
    payload = {"organizationId": organization_id, "expectedVersion": expected_version, "configHash": config_hash(config), "expiresAt": int(time.time()) + ttl_seconds}
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    encoded = base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")
    signature = hmac.new(get_settings().auth_secret.encode("utf-8"), encoded.encode("ascii"), hashlib.sha256).hexdigest()
    return f"{encoded}.{signature}"


def verify_preview_token(token: str, organization_id: int, expected_version: int, config: ReportRulesConfig) -> dict[str, Any]:
    try:
        encoded, signature = token.split(".", 1)
        expected = hmac.new(get_settings().auth_secret.encode("utf-8"), encoded.encode("ascii"), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected):
            raise PreviewTokenError("Подпись preview недействительна")
        padding = "=" * ((4 - len(encoded) % 4) % 4)
        payload = json.loads(base64.urlsafe_b64decode(encoded + padding))
    except (ValueError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise PreviewTokenError("Preview token повреждён") from exc
    if payload.get("organizationId") != organization_id or payload.get("expectedVersion") != expected_version:
        raise PreviewTokenError("Preview относится к другой версии профиля")
    if payload.get("configHash") != config_hash(config):
        raise PreviewTokenError("Настройки изменились после preview")
    if int(payload.get("expiresAt") or 0) < int(time.time()):
        raise PreviewTokenError("Preview устарел")
    return payload


def create_preview(rows: list[dict[str, Any]], active: ReportRuleProfileView, draft_config: ReportRulesConfig) -> dict[str, Any]:
    draft = active.model_copy(deep=True)
    draft.config = normalize_config(draft_config)
    samples: list[dict[str, Any]] = []
    impact: dict[str, int] = {"rnp": 0, "liquidation": 0, "alerts": 0, "stopAds": 0, "audit": 0, "raisePrice": 0}
    affected = status_changes = 0
    for row in rows:
        before = evaluate_metrics(row, active)
        after = evaluate_metrics(row, draft)
        before_dump = before.model_dump(mode="json")
        after_dump = after.model_dump(mode="json")
        if before_dump == after_dump:
            continue
        affected += 1
        if before.status != after.status:
            status_changes += 1
        for item in after.recommendedActions:
            key = {"rnp": "rnp", "liquidation": "liquidation", "alert": "alerts", "stop_ads": "stopAds", "audit": "audit", "raise_price": "raisePrice"}.get(item.type)
            if key:
                impact[key] += 1
        if len(samples) < 20:
            samples.append({"sku": str(row.get("sku") or row.get("rowId") or row.get("nmId") or "—"), "before": before_dump, "after": after_dump})
    return {"affectedSkuCount": affected, "statusChanges": status_changes, "automationImpact": impact, "sampleRows": samples, "warnings": []}
