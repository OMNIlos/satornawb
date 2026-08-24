# WB Report Rules Engine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Persist one versioned WB report-rule profile per Satorna organization and make every supported report evaluate real rows with that active profile, producing confirmation-required recommendation drafts.

**Architecture:** A focused `app/report_rules` package owns schemas, presets, persistence, validation, preview tokens, and row evaluation. Existing report builders load one canonical profile and decorate their rows and summary counters; derived cache keys include the profile version. The active `/wb/reports/rules` parity island uses a typed frontend API module and renders backend state instead of the static HTML profile.

**Tech Stack:** Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2, Alembic, pytest, React 18, TypeScript, Vitest.

## Global Constraints

- Profile scope is exactly `organization_id`; there are no manager, brand, SKU, or multi-WB-account profile overrides.
- ABC sales and net-profit shares are always `20/30/50`, including for all presets and hostile requests.
- Rules create only `draft` recommendations with `requiresConfirmation: true`; they never send prices or advertising mutations to WB.
- Missing or untrusted metrics evaluate to `unknown` and must not create a negative recommendation.
- Built-in presets are `standard`, `conservative`, and `aggressive`; any manual edit is stored as `custom`.
- Preserve the existing uncommitted WoW changes in `app/repricer_tasks.py`, `app/routers/wb_reports_bff.py`, `app/wb_api/ads_runtime.py`, `tests/test_wb_ads_runtime.py`, and the frontend parity files.
- Run only the targeted tests listed in this plan; do not expand into a broad unrelated regression pass.

---

## File Structure

### Backend repository: `D:\ogni-elfs`

- Create `app/report_rules/__init__.py`: public package exports.
- Create `app/report_rules/orm.py`: append-only profile ORM row and active-row index.
- Create `app/report_rules/schemas.py`: Pydantic configuration, API, evaluation, and preview types.
- Create `app/report_rules/presets.py`: the three canonical built-in configurations and fixed ABC values.
- Create `app/report_rules/store.py`: database/in-memory persistence and optimistic version activation.
- Create `app/report_rules/service.py`: normalization, validation, preview signing, classification, and report-row decoration.
- Create `alembic/versions/20260716_0016_wb_report_rule_profiles.py`: profile table and indexes.
- Modify `alembic/env.py`: register report-rule ORM metadata.
- Modify `app/routers/wb_reports_bff.py`: rules API, row evaluation for BFF reports, rule-aware cache identity.
- Modify `app/wb_reports_sprint_d.py`: ABC, RNP, and P&L evaluation.
- Modify `app/repricer_tasks.py`: capture rules version in background job/cache payloads.
- Modify `app/contracts/vella_wb_19_05_generated.py`: expose optional rule evaluation fields on strict Sprint-D response models.
- Create `tests/test_report_rules_service.py`: validation and evaluation unit tests.
- Create `tests/test_report_rules_store.py`: versioned persistence tests.
- Create `tests/test_report_rules_api.py`: permissions, preview, activation, and history tests.
- Modify `tests/test_sprint_d_reports.py`: ABC/RNP/P&L rule integration tests.
- Modify `tests/test_wb_reports_bff.py`: stock/ads/WoW and cache-version tests.

### Frontend repository: `D:\ogni-frontend`

- Create `frontend/src/features/wb-reports/reportRulesApi.ts`: typed rules and manager-plan requests.
- Create `frontend/src/features/wb-reports/reportRulesApi.test.ts`: API request contract tests.
- Modify `frontend/src/features/wb-reports/types.ts`: canonical profile, preview, evaluation, and history types.
- Modify `frontend/src/features/vella-parity/VellaHtmlParityPage.tsx`: API-backed rules island, preview/save flow, editable automation mapping, manager plans, and report rule badges.
- Create `frontend/src/features/vella-parity/reportRulesIsland.test.tsx`: focused rules-island behavior tests.

---

### Task 1: Versioned profile persistence and canonical presets

**Files:**
- Create: `app/report_rules/__init__.py`
- Create: `app/report_rules/orm.py`
- Create: `app/report_rules/schemas.py`
- Create: `app/report_rules/presets.py`
- Create: `app/report_rules/store.py`
- Create: `alembic/versions/20260716_0016_wb_report_rule_profiles.py`
- Modify: `alembic/env.py`
- Test: `tests/test_report_rules_store.py`

**Interfaces:**
- Produces: `ReportRuleProfileView`, `ReportRulesConfig`, `PRESET_CONFIGS`, `load_active_profile(organization_id)`, `activate_profile(...)`, and `list_profile_history(...)`.
- Consumes: `app.infra.db.get_session_factory`, `app.infra.models.Base`, and `lk_organizations.organization_id`.

- [ ] **Step 1: Write the failing store tests**

```python
import pytest

from app.report_rules.presets import preset_config
from app.report_rules.store import ProfileVersionConflict, activate_profile, load_active_profile, list_profile_history


def test_missing_profile_reads_deterministic_standard_default(monkeypatch):
    monkeypatch.setattr("app.report_rules.store._run_db", lambda _fn: None)
    profile = load_active_profile(41)
    assert profile.organizationId == 41
    assert profile.version == 1
    assert profile.preset == "standard"
    assert profile.config.abc.salesShare.model_dump() == {"aPct": 20, "bPct": 30, "cPct": 50}


def test_activate_profile_appends_version_and_rejects_stale_writer(monkeypatch):
    monkeypatch.setattr("app.report_rules.store._run_db", lambda _fn: None)
    first = activate_profile(42, "user-1", 1, "standard", "Стандартный профиль", preset_config("standard"))
    second = activate_profile(42, "user-2", first.version, "aggressive", "Агрессивный профиль", preset_config("aggressive"))
    assert second.version == 3
    assert [row.version for row in list_profile_history(42, limit=10)] == [3, 2]
    with pytest.raises(ProfileVersionConflict):
        activate_profile(42, "user-1", 1, "standard", "Старый черновик", preset_config("standard"))
```

- [ ] **Step 2: Run the store tests to verify they fail**

Run: `pytest tests/test_report_rules_store.py -q`

Expected: collection fails with `ModuleNotFoundError: No module named 'app.report_rules'`.

- [ ] **Step 3: Add schemas and all canonical preset values**

Implement strict Pydantic models with these signatures:

```python
PresetName = Literal["standard", "conservative", "aggressive", "custom"]
AutomationAction = Literal["raise_price", "lower_price", "rnp", "liquidation", "stop_ads", "alert", "audit"]

class AbcShare(BaseModel):
    aPct: float = 20
    bPct: float = 30
    cPct: float = 50

class ReportRulesConfig(BaseModel):
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
    isActive: bool
```

Define complete presets in `presets.py`; all three use fixed ABC shares:

```python
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

DEFAULT_AUTOMATION = {
    "aaGood": "raise_price", "badCr": "rnp", "loss": "liquidation",
    "highDrr": "stop_ads", "oos": "alert", "cWeak": "audit",
}
```

- [ ] **Step 4: Add the ORM row and migration**

Create `WbReportRuleProfileRow` with a unique organization/version constraint and partial unique active index:

```python
class WbReportRuleProfileRow(Base):
    __tablename__ = "wb_report_rule_profiles"
    __table_args__ = (
        UniqueConstraint("organization_id", "version", name="uq_wb_report_rule_profile_org_version"),
        Index(
            "uq_wb_report_rule_profile_active_org",
            "organization_id",
            unique=True,
            postgresql_where=text("is_active"),
            sqlite_where=text("is_active = 1"),
        ),
    )

    profile_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("lk_organizations.organization_id"), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    preset: Mapped[str] = mapped_column(String(32), nullable=False)
    config_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_by_user_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
```

Migration revision is `20260716_0016`, with `down_revision = "20260716_0015"`. Import `app.report_rules.orm` from `alembic/env.py` so metadata discovery includes the table.

- [ ] **Step 5: Implement database and in-memory activation**

Use a module-local `dict[int, list[ReportRuleProfileView]]` only as the existing database-unavailable fallback. In the DB transaction, select the active row with `with_for_update()`, compare `expected_version`, deactivate it, insert `version + 1`, commit, and return the inserted view. Raise a typed `ProfileVersionConflict(current_version)` before changing any row.

The first activation uses the virtual default version `1`, so it inserts version `2`; history contains only persisted activations.

- [ ] **Step 6: Run the focused store and migration checks**

Run: `pytest tests/test_report_rules_store.py tests/test_infra_baseline.py -q`

Expected: all selected tests pass and the metadata test includes `wb_report_rule_profiles`.

- [ ] **Step 7: Commit Task 1**

```powershell
git add app/report_rules alembic/env.py alembic/versions/20260716_0016_wb_report_rule_profiles.py tests/test_report_rules_store.py
git commit -m "feat: persist versioned WB report rules"
```

---

### Task 2: Validation, classification, and recommendation drafts

**Files:**
- Create: `app/report_rules/service.py`
- Modify: `app/report_rules/schemas.py`
- Modify: `app/report_rules/__init__.py`
- Test: `tests/test_report_rules_service.py`

**Interfaces:**
- Consumes: `ReportRulesConfig`, `ReportRuleProfileView`, `PRESET_CONFIGS`.
- Produces: `normalize_config(config)`, `evaluate_metrics(metrics, profile)`, `evaluate_rows(rows, profile)`, `create_preview(...)`, `issue_preview_token(...)`, and `verify_preview_token(...)`.

- [ ] **Step 1: Write failing validation and trigger tests**

```python
from datetime import datetime, timezone

import pytest

from app.report_rules.presets import preset_config
from app.report_rules.schemas import ReportRuleProfileView
from app.report_rules.service import ReportRulesValidationError, evaluate_metrics, normalize_config


def profile_view(preset: str) -> ReportRuleProfileView:
    return ReportRuleProfileView(
        profileId=None,
        organizationId=1,
        version=1,
        name=f"{preset} profile",
        preset=preset,
        config=preset_config(preset),
        createdByUserId="test-user",
        createdAt=datetime.now(timezone.utc),
        isActive=True,
    )


def test_normalize_enforces_fixed_abc_and_rejects_inverted_bands():
    raw = preset_config("standard").model_copy(deep=True)
    raw.abc.salesShare.aPct = 99
    raw.qualityBands.marginPct.thinMin = 40
    with pytest.raises(ReportRulesValidationError) as exc:
        normalize_config(raw)
    assert exc.value.errors[0]["path"] == "qualityBands.marginPct"


@pytest.mark.parametrize(
    ("metrics", "reason", "action"),
    [
        ({"marginPct": -1}, "loss", "liquidation"),
        ({"drrPct": 20, "roiPct": 50}, "highDrr", "stop_ads"),
        ({"daysToOos": 3, "stockUnits": 30}, "oos", "alert"),
        ({"crPct": 1, "impressions": 800}, "badCr", "rnp"),
        ({"abcCode": "AA", "marginPct": 30}, "aaGood", "raise_price"),
        ({"abcCode": "CC", "marginPct": 20}, "cWeak", "audit"),
    ],
)
def test_rules_create_confirmation_required_drafts(metrics, reason, action):
    result = evaluate_metrics(metrics, profile_view("standard"))
    draft = next(item for item in result.recommendedActions if item.reason == reason)
    assert draft.type == action
    assert draft.state == "draft"
    assert draft.requiresConfirmation is True


def test_missing_metrics_are_unknown_and_do_not_create_negative_draft():
    result = evaluate_metrics({"crPct": None, "sourceTrusted": False}, profile_view("standard"))
    assert result.bands["crPct"] == "unknown"
    assert result.recommendedActions == []
```

- [ ] **Step 2: Run tests to verify failure**

Run: `pytest tests/test_report_rules_service.py -q`

Expected: import errors for the missing service functions.

- [ ] **Step 3: Implement normalization and band classification**

Implement explicit higher-is-good, lower-is-good, and below-is-bad helpers. Return `unknown` for `None`, non-finite, or untrusted values. Validate these exact relationships:

```python
checks = [
    (bands.ctrPct.goodMin > bands.ctrPct.averageMin, "qualityBands.ctrPct"),
    (bands.crPct.goodMin > bands.crPct.averageMin, "qualityBands.crPct"),
    (bands.cartToOrderPct.goodMin > bands.cartToOrderPct.averageMin, "qualityBands.cartToOrderPct"),
    (bands.buyoutPct.goodMin > bands.buyoutPct.averageMin, "qualityBands.buyoutPct"),
    (bands.marginPct.goodMin > bands.marginPct.thinMin > bands.marginPct.lossBelow, "qualityBands.marginPct"),
    (bands.drrPct.goodMax < bands.drrPct.warnMin, "qualityBands.drrPct"),
    (bands.roiPct.goodMin > bands.roiPct.warnBelow, "qualityBands.roiPct"),
]
```

Normalize both ABC shares to `{20, 30, 50}` after validation of all other fields.

- [ ] **Step 4: Implement composite evaluation in priority order**

Evaluate `loss`, `oos`, `highDrr`, `badCr`, `aaGood`, then `cWeak`. The bad-CR rule requires at least `500` trustworthy impressions. Map each matched rule through `profile.config.automationMapping`; return all matching band values, a stable top-level status, Russian reasons, and recommendation drafts. Deduplicate drafts by `(type, reason)`.

- [ ] **Step 5: Implement stateless preview tokens**

Use `get_settings().auth_secret` and HMAC-SHA256 over canonical JSON containing `organizationId`, `expectedVersion`, `configHash`, and `expiresAt`. Set lifetime to 15 minutes. `verify_preview_token` must reject a changed config, organization, version, signature, or expired time.

- [ ] **Step 6: Implement preview comparison**

`create_preview(rows, active_profile, draft_config)` evaluates every supplied row twice and returns affected count, per-report counts, recommendation impact, up to 20 changed samples, and the draft hash. Rows without trustworthy metrics remain in an unavailable count and never appear as false changes.

- [ ] **Step 7: Run the service tests**

Run: `pytest tests/test_report_rules_service.py -q`

Expected: all tests pass.

- [ ] **Step 8: Commit Task 2**

```powershell
git add app/report_rules tests/test_report_rules_service.py
git commit -m "feat: evaluate WB report rule profiles"
```

---

### Task 3: Rules API, permissions, preview, activation, and history

**Files:**
- Modify: `app/routers/wb_reports_bff.py`
- Modify: `app/report_rules/schemas.py`
- Test: `tests/test_report_rules_api.py`

**Interfaces:**
- Consumes: store and service functions from Tasks 1-2, `actor_from_request`, `has_permission`, `assert_permission_or_audit`, `record_audit_event`.
- Produces: `GET /api/wb/reports/rules`, `POST /api/wb/reports/rules/preview`, `PUT /api/wb/reports/rules`, and `GET /api/wb/reports/rules/history`.

- [ ] **Step 1: Write failing API tests**

```python
from fastapi.testclient import TestClient

from app.main import create_app
from tests.auth_helpers import auth_headers


def client() -> TestClient:
    return TestClient(create_app())


def test_rules_get_returns_standard_profile_for_registered_account():
    api = client()
    response = api.get("/api/wb/reports/rules", headers=auth_headers(api, "viewer"))
    assert response.status_code == 200
    assert response.json()["profile"]["organizationId"] >= 1
    assert response.json()["profile"]["config"]["abc"]["salesShare"] == {"aPct": 20, "bPct": 30, "cPct": 50}
    assert response.json()["canWrite"] is False


def test_rules_save_requires_preview_and_settings_write():
    api = client()
    viewer = api.put("/api/wb/reports/rules", headers=auth_headers(api, "viewer"), json={})
    assert viewer.status_code == 403
    editor = api.put("/api/wb/reports/rules", headers=auth_headers(api, "settings_editor"), json={})
    assert editor.status_code == 422


def test_preview_then_save_increments_version_and_history():
    api = client()
    headers = auth_headers(api, "settings_editor")
    current = api.get("/api/wb/reports/rules", headers=headers).json()["profile"]
    draft = {"expectedVersion": current["version"], "name": "Осторожный профиль", "preset": "conservative", "config": current["config"]}
    preview = api.post("/api/wb/reports/rules/preview", headers=headers, json=draft)
    assert preview.status_code == 200
    saved = api.put("/api/wb/reports/rules", headers=headers, json={**draft, "previewToken": preview.json()["previewToken"]})
    assert saved.status_code == 200
    assert saved.json()["profile"]["version"] == current["version"] + 1
    history = api.get("/api/wb/reports/rules/history", headers=headers).json()["items"]
    assert history[0]["version"] == saved.json()["profile"]["version"]
```

- [ ] **Step 2: Run API tests to verify failure**

Run: `pytest tests/test_report_rules_api.py -q`

Expected: requests return `404`.

- [ ] **Step 3: Add request/response schemas**

Define `RulesDraftRequest(expectedVersion, name, preset, config)`, `RulesSaveRequest` extending it with `previewToken`, `RulesReadResponse(profile, presets, automationActions, canWrite)`, and `RulesPreviewResponse`.

- [ ] **Step 4: Add read and history routes before the dynamic `{report_id}` route**

Use `settings:read` for GET routes. Return canonical backend presets rather than frontend constants. Limit history to `1..100`, default `20`.

- [ ] **Step 5: Add preview route**

Require `settings:write`. Collect preview inputs only from existing source/report caches; do not call WB during preview. Return per-report availability when a cache is absent. Sign the normalized draft and active version into `previewToken`.

- [ ] **Step 6: Add activation route and audit event**

Verify the token first, activate with optimistic concurrency, then call:

```python
record_audit_event(
    actor=actor,
    action="reports.rules.activate",
    object_type="wb_report_rule_profile",
    object_id=f"{actor.organization_id}:{saved.version}",
    before_state={"version": active.version, "preset": active.preset},
    after_state={"version": saved.version, "preset": saved.preset, "changedPaths": changed_paths},
    reason="report rules activated after preview",
    approval_ref=preview_token_hash,
    evidence_refs=[f"rules-preview:{preview.configHash}"],
)
```

Translate `ProfileVersionConflict` and preview-token conflicts to HTTP `409`. Let Pydantic field failures return `422` with field locations.

- [ ] **Step 7: Run API tests**

Run: `pytest tests/test_report_rules_api.py tests/test_auth_permissions.py -q`

Expected: all selected tests pass.

- [ ] **Step 8: Commit Task 3**

```powershell
git add app/routers/wb_reports_bff.py app/report_rules/schemas.py tests/test_report_rules_api.py
git commit -m "feat: expose WB report rules API"
```

---

### Task 4: Apply rules to ABC, RNP, and P&L

**Files:**
- Modify: `app/wb_reports_sprint_d.py`
- Modify: `app/contracts/vella_wb_19_05_generated.py`
- Modify: `app/routers/wb_reports_sprint_d.py`
- Modify: `tests/test_sprint_d_reports.py`

**Interfaces:**
- Consumes: `load_active_profile`, `evaluate_metrics`, and `evaluate_rows`.
- Produces: Sprint-D responses with `rulesProfileVersion`, `bands`, `statusReasons`, and `recommendedActions`.

- [ ] **Step 1: Write one failing rule assertion per report family**

Add focused tests that monkeypatch `load_active_profile` to an aggressive or conservative profile and assert:

```python
assert abc.rows[0]["ruleEvaluation"]["recommendedActions"][0]["requiresConfirmation"] is True
assert rnp.rows[0].ruleEvaluation.bands["crPct"] in {"good", "average", "bad", "unknown"}
assert pnl.rows[0].ruleEvaluation.bands["marginPct"] in {"good", "average", "bad", "unknown"}
assert abc.rulesProfileVersion == profile.version
assert rnp.rulesProfileVersion == profile.version
assert pnl.rulesProfileVersion == profile.version
```

- [ ] **Step 2: Run the selected tests to verify failure**

Run: `pytest tests/test_sprint_d_reports.py -q -k "rules_profile or rule_evaluation"`

Expected: missing attributes/keys fail.

- [ ] **Step 3: Extend strict response contracts**

Add reusable contract models:

```python
class RuleRecommendation(BaseModel):
    type: str
    state: Literal["draft"]
    reason: str
    requiresConfirmation: Literal[True]

class RuleEvaluation(BaseModel):
    bands: dict[str, Literal["good", "average", "bad", "unknown"]]
    status: str
    statusReasons: list[str]
    recommendedActions: list[RuleRecommendation]
```

Add `ruleEvaluation: RuleEvaluation | None = None` to P&L, ads-performance, and RNP row models, and `rulesProfileVersion: int = 1` to their top-level response models plus `AbcReportResponse`.

- [ ] **Step 4: Decorate ABC rows after ABC codes are assigned**

Build metrics from each row's actual fields: `abcCode`, `marginPct`, `ctrPct`, `cartCrPct`, `buyoutPct`, `drrSalesPct`, `roiPct`, impressions, WB stock, and any trustworthy OOS/localization values. Store the evaluator result under `ruleEvaluation`, and derive `productStatus` from that result only when the evaluator has a non-neutral status.

- [ ] **Step 5: Decorate RNP and P&L rows**

RNP passes only present metrics; do not coerce absent CTR/CR/buyout to zero. P&L evaluates margin, loss, and buyout only. Set `rulesProfileVersion` on every returned response, including empty and partial responses.

- [ ] **Step 6: Verify Sprint-D integration**

Run: `pytest tests/test_sprint_d_reports.py -q -k "rules_profile or rule_evaluation or abc or rnp or pnl"`

Expected: selected tests pass.

- [ ] **Step 7: Commit Task 4**

```powershell
git add app/wb_reports_sprint_d.py app/contracts/vella_wb_19_05_generated.py app/routers/wb_reports_sprint_d.py tests/test_sprint_d_reports.py
git commit -m "feat: apply report rules to ABC RNP and PnL"
```

---

### Task 5: Apply rules to stock, advertising, and WoW; version background caches

**Files:**
- Modify: `app/routers/wb_reports_bff.py`
- Modify: `app/repricer_tasks.py`
- Modify: `tests/test_wb_reports_bff.py`

**Interfaces:**
- Consumes: active profile/evaluator and current BFF report builders.
- Produces: rule-aware BFF rows, summary counters, cache keys, and background job metadata.

- [ ] **Step 1: Write failing stock, ads, WoW, and cache-version tests**

```python
from datetime import datetime, timezone

from app.report_rules.presets import preset_config
from app.report_rules.schemas import ReportRuleProfileView


def profile_view(preset: str) -> ReportRuleProfileView:
    return ReportRuleProfileView(
        profileId=None,
        organizationId=7,
        version=2,
        name=f"{preset} profile",
        preset=preset,
        config=preset_config(preset),
        createdByUserId="test-user",
        createdAt=datetime.now(timezone.utc),
        isActive=True,
    )


def test_stock_oos_counter_uses_active_profile_threshold(monkeypatch):
    profile = profile_view("conservative")  # 10 days / 18 units
    monkeypatch.setattr("app.routers.wb_reports_bff.load_active_profile", lambda _org: profile)
    payload = _build_stock_report_payload(date_range, snapshot_with_stock(days_to_oos=9, units=30), organization_id=7, wb_token=None)
    assert next(k for k in payload["kpis"] if k["id"] == "oos_risk")["value"] == "1"
    assert payload["rows"][0]["ruleEvaluation"]["recommendedActions"][0]["reason"] == "oos"


def test_wow_missing_margin_is_unknown_not_loss(monkeypatch):
    monkeypatch.setattr("app.routers.wb_reports_bff.load_active_profile", lambda _org: profile_view("standard"))
    payload = _build_week_over_week_payload(date_range, snapshot_without_sales(), organization_id=7)
    row = payload["rows"][0]
    assert row["ruleEvaluation"]["bands"]["marginPct"] == "unknown"
    assert all(item["reason"] != "loss" for item in row["ruleEvaluation"]["recommendedActions"])


def test_report_cache_key_changes_with_rules_version():
    assert _report_cache_key("stock", START, END, "warehouse", "operational", rules_version=2) != _report_cache_key("stock", START, END, "warehouse", "operational", rules_version=3)
```

- [ ] **Step 2: Run the selected tests to verify failure**

Run: `pytest tests/test_wb_reports_bff.py -q -k "rules or oos_counter or cache_key_changes"`

Expected: missing `ruleEvaluation`/`rules_version` failures.

- [ ] **Step 3: Apply the stock profile consistently**

Load one profile at the start of `_build_stock_report_payload`. Evaluate each row with `daysToOos`, `availableUnits` as stock units, and `localizationPct`. Compute `oos_risk` from evaluator results containing reason `oos`, and build management-card text from the active numeric thresholds instead of the literal seven days.

- [ ] **Step 4: Apply advertising and WoW profiles**

Advertising rows pass real CTR, CR, DRR, ROI, impressions, margin, and availability fields only when sourced. WoW passes current-period metrics and keeps unavailable values as `None`. Both responses include `rulesProfileVersion`; WoW conclusion appends evaluator reasons without replacing source-history text.

- [ ] **Step 5: Add rules version to derived cache and job identity**

Change signatures to:

```python
def _report_cache_key(report_id, date_from, date_to, group_by, source, *, rules_version: int) -> str: ...
def _report_job_cache_key(report_id, date_from, date_to, group_by, *, rules_version: int) -> str: ...
```

Add `_active_rules_version(organization_id)` and pass it from GET, job start, job status, latest-cache lookup, and `build_report_for_org`. Include `rulesProfileVersion` in queued/running/completed job payloads and cached report envelopes. A worker captures the version before building and persists only under that version's keys.

- [ ] **Step 6: Preserve current WoW progress behavior while editing**

Do not change the existing `include_budgets=False` calls or the current scaled progress ranges. This task only adds rules-version capture and report decoration around those calls.

- [ ] **Step 7: Run targeted BFF/background tests**

Run: `pytest tests/test_wb_reports_bff.py tests/test_stock_report_cache_persistence.py tests/test_wb_ads_runtime.py -q -k "rules or stock or week_over_week or report_job_cache_key or include_budgets"`

Expected: selected tests pass.

- [ ] **Step 8: Commit Task 5**

```powershell
git add app/routers/wb_reports_bff.py app/repricer_tasks.py tests/test_wb_reports_bff.py
git commit -m "feat: apply rules to live WB reports"
```

---

### Task 6: Typed frontend rules API

**Files:**
- Create: `frontend/src/features/wb-reports/reportRulesApi.ts`
- Create: `frontend/src/features/wb-reports/reportRulesApi.test.ts`
- Modify: `frontend/src/features/wb-reports/types.ts`

**Interfaces:**
- Consumes: `apiRequest`, `authorizationHeaders`, and the backend API from Task 3.
- Produces: `getReportRules`, `previewReportRules`, `saveReportRules`, `getReportRulesHistory`, `getManagerPlan`, and `saveManagerPlan`.

- [ ] **Step 1: Write failing API request tests**

Mock `apiRequest` and assert exact methods and paths:

```typescript
await getReportRules('token')
expect(apiRequest).toHaveBeenCalledWith('/api/wb/reports/rules', expect.objectContaining({ headers: expect.anything() }))

await previewReportRules('token', draft)
expect(apiRequest).toHaveBeenCalledWith('/api/wb/reports/rules/preview', expect.objectContaining({ method: 'POST', body: JSON.stringify(draft) }))

await saveReportRules('token', { ...draft, previewToken: 'signed' })
expect(apiRequest).toHaveBeenCalledWith('/api/wb/reports/rules', expect.objectContaining({ method: 'PUT' }))

await getManagerPlan('token', '2026-07')
expect(apiRequest).toHaveBeenCalledWith('/api/wb/reports/digest/plan?month=2026-07', expect.anything())
```

- [ ] **Step 2: Run the API test to verify failure**

Run from `D:\ogni-frontend\frontend`: `npm test -- --run src/features/wb-reports/reportRulesApi.test.ts`

Expected: module-not-found failure.

- [ ] **Step 3: Align frontend types with backend canonical fields**

Change `ThresholdPreset` to include `custom`; add `RuleBandLevel`, `RuleRecommendation`, `RuleEvaluation`, `ReportRuleHistoryItem`, `ReportRulesReadResponse`, and `ReportRulesPreviewResponse`. Add optional `rulesProfileVersion` to report response types and optional `ruleEvaluation` to table rows without broadening unrelated values.

- [ ] **Step 4: Implement the API functions**

Each function uses `authorizationHeaders(accessToken)`. `previewReportRules` and `saveReportRules` send JSON. History uses `?limit=20`. Manager-plan functions retain the existing backend payload shape and convert no currency values in the transport layer.

- [ ] **Step 5: Run the API test**

Run: `npm test -- --run src/features/wb-reports/reportRulesApi.test.ts`

Expected: test passes.

- [ ] **Step 6: Commit Task 6 in the frontend repository**

```powershell
git add frontend/src/features/wb-reports/reportRulesApi.ts frontend/src/features/wb-reports/reportRulesApi.test.ts frontend/src/features/wb-reports/types.ts
git commit -m "feat: add WB report rules client"
```

---

### Task 7: Replace the parity rules prototype with live React state

**Files:**
- Modify: `frontend/src/features/vella-parity/VellaHtmlParityPage.tsx`
- Create: `frontend/src/features/vella-parity/reportRulesIsland.test.tsx`

**Interfaces:**
- Consumes: Task 6 API functions and `useAuth()`.
- Produces: live `/wb/reports/rules` loading, preset, custom editing, preview, save, history, read-only, and manager-plan behavior.

- [ ] **Step 1: Write failing rules-island behavior tests**

Mock Task 6 functions and cover only these flows:

```typescript
it('loads the active backend profile and applies a complete preset', async () => {
  render(<ReportRulesIsland replacementKey="rules" />)
  expect(await screen.findByText(/версия 4/)).toBeInTheDocument()
  await user.click(screen.getByRole('button', { name: 'Осторожный' }))
  expect(screen.getByLabelText('CR Норма от')).toHaveValue(5)
})

it('requires a matching backend preview before save', async () => {
  render(<ReportRulesIsland replacementKey="rules" />)
  await user.clear(await screen.findByLabelText('OOS риск до'))
  await user.type(screen.getByLabelText('OOS риск до'), '10')
  expect(screen.getByRole('button', { name: 'Сохранить после проверки' })).toBeDisabled()
  await user.click(screen.getByRole('button', { name: 'Проверить влияние' }))
  expect(await screen.findByText('Затронуто')).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Сохранить после проверки' })).toBeEnabled()
})

it('renders read-only controls without settings write permission', async () => {
  mockGetReportRules.mockResolvedValue({ ...response, canWrite: false })
  render(<ReportRulesIsland replacementKey="rules" />)
  expect(await screen.findByText('Только просмотр')).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Проверить влияние' })).toBeDisabled()
})
```

- [ ] **Step 2: Run the island test to verify failure**

Run: `npm test -- --run src/features/vella-parity/reportRulesIsland.test.tsx`

Expected: current island does not call the API and assertions fail.

- [ ] **Step 3: Move rules island state fully into React**

Export `ReportRulesIsland` for the focused test, then add state for `loading`, `loadError`, `activeProfile`, `draft`, `preview`, `saving`, `history`, and `canWrite`. Load rules/history on mount when `accessToken` exists. Remove calls from this island to `window.onThresholdInput`, `window.setThresholdPreset`, `window.resetThresholdDraft`, and `window.openThresholdPreview`.

Use controlled inputs with accessible labels. Preset selection copies the complete server-returned preset, retains the active version as `expectedVersion`, and marks the draft preset. Any field or automation change sets `preset: 'custom'` and clears the previous preview token.

- [ ] **Step 4: Make preview and save operate on exact draft hashes**

Preview calls `previewReportRules` and stores both response and `JSON.stringify(draft.config)`. Enable save only when the current serialized config equals the previewed serialization. Save includes `previewToken`; on success replace active/draft state with the returned canonical profile and refresh history.

For HTTP `409`, keep the draft and show: `Профиль уже изменён другим пользователем. Перезагрузите действующую версию и повторите проверку.`

- [ ] **Step 5: Render every backend field and automation mapping**

Keep fixed ABC inputs disabled. Add the currently missing `qualityBands.roiPct.warnBelow` input. Render six controlled automation selects for `aaGood`, `badCr`, `loss`, `highDrr`, `oos`, and `cWeak`, using the backend's allowed action list and Russian labels. Do not expose a control that can directly send to WB.

- [ ] **Step 6: Replace static audit and manager-plan rows**

Render history from `getReportRulesHistory`. Add a month input defaulting to the current `YYYY-MM`, load plans through `getManagerPlan`, allow company/manager revenue and margin edits in rubles, convert to kopecks at save, and call `saveManagerPlan`. Reuse the same backend plan shape already used by `ManagerSignalPanelIsland`.

- [ ] **Step 7: Keep static HTML functions isolated**

The legacy static threshold functions may remain for snapshot compatibility, but the mounted React island must not invoke them or use their state. Remove `installThresholdPreviewReactBridge()` only if no other mounted island references it; otherwise leave the bridge dormant.

- [ ] **Step 8: Run focused frontend tests and typecheck**

Run:

```powershell
npm test -- --run src/features/vella-parity/reportRulesIsland.test.tsx src/features/wb-reports/reportRulesApi.test.ts
npm run typecheck
```

Expected: tests and typecheck pass.

- [ ] **Step 9: Commit Task 7 in the frontend repository**

```powershell
git add frontend/src/features/vella-parity/VellaHtmlParityPage.tsx frontend/src/features/vella-parity/reportRulesIsland.test.tsx
git commit -m "feat: connect report rules page to backend"
```

---

### Task 8: Render backend rule results in live reports and perform final targeted verification

**Files:**
- Modify: `frontend/src/features/vella-parity/VellaHtmlParityPage.tsx`
- Modify: `frontend/src/features/vella-parity/vellaBackendContracts.ts`
- Modify: `frontend/src/features/vella-parity/weekLiveSource.test.ts`
- Modify: `frontend/src/features/wb-reports/schemas.ts`
- Modify: `frontend/src/features/wb-reports/schemas.test.ts`

**Interfaces:**
- Consumes: `rulesProfileVersion` and `ruleEvaluation` returned by Tasks 4-5.
- Produces: visible status, reasons, draft recommendation chips, and profile-version trace on ABC/RNP/P&L/ads/stock/WoW views.

- [ ] **Step 1: Write failing schema and rendering assertions**

Add a representative live report row with:

```typescript
ruleEvaluation: {
  bands: { marginPct: 'bad' },
  status: 'risk',
  statusReasons: ['Маржа ниже loss-порога'],
  recommendedActions: [{ type: 'liquidation', state: 'draft', reason: 'loss', requiresConfirmation: true }],
}
```

Assert the parser preserves the object and the relevant report renderer shows `Черновик`, the reason text, and `Правила v5` when `rulesProfileVersion` is `5`.

- [ ] **Step 2: Run selected tests to verify failure**

Run: `npm test -- --run src/features/wb-reports/schemas.test.ts src/features/vella-parity/weekLiveSource.test.ts`

Expected: rule fields are dropped or not rendered.

- [ ] **Step 3: Extend live backend contracts without frontend reclassification**

Parse `rulesProfileVersion` and `ruleEvaluation` as returned. Do not call `createThresholdPreview`, `classifyBand`, or static `classifyRowsForProfile` for live rows. The frontend is a renderer; backend evaluation is authoritative.

- [ ] **Step 4: Render evaluation consistently across report tables**

For ABC, RNP, P&L, ads, stock, and WoW rows:

- show the evaluator status when present;
- show each reason in the existing status/recommendation area or tooltip;
- show recommendation type with `черновик` and no direct external-mutation handler;
- show `unknown` as `Недостаточно данных`, not as risk;
- show `Правила vN` in report metadata/trace.

- [ ] **Step 5: Run final targeted backend verification**

From `D:\ogni-elfs` run:

```powershell
pytest tests/test_report_rules_store.py tests/test_report_rules_service.py tests/test_report_rules_api.py tests/test_sprint_d_reports.py tests/test_wb_reports_bff.py tests/test_stock_report_cache_persistence.py tests/test_wb_ads_runtime.py -q -k "report_rules or rules_profile or rule_evaluation or stock or week_over_week or include_budgets"
```

Expected: selected tests pass.

- [ ] **Step 6: Run final targeted frontend verification**

From `D:\ogni-frontend\frontend` run:

```powershell
npm test -- --run src/features/wb-reports/reportRulesApi.test.ts src/features/vella-parity/reportRulesIsland.test.tsx src/features/wb-reports/schemas.test.ts src/features/vella-parity/weekLiveSource.test.ts
npm run typecheck
```

Expected: selected tests and typecheck pass.

- [ ] **Step 7: Confirm no automatic WB mutation path was added**

Run in both repositories:

```powershell
rg -n "recommendedActions.*(send|apply)|ruleEvaluation.*(price|campaign).*POST|reports.rules.*(price|advert)" app frontend/src
```

Expected: no route or handler sends a rule-generated draft to WB automatically.

- [ ] **Step 8: Commit Task 8 in the frontend repository**

```powershell
git add frontend/src/features/vella-parity/VellaHtmlParityPage.tsx frontend/src/features/vella-parity/vellaBackendContracts.ts frontend/src/features/vella-parity/weekLiveSource.test.ts frontend/src/features/wb-reports/schemas.ts frontend/src/features/wb-reports/schemas.test.ts
git commit -m "feat: show report rule recommendations"
```

---

## Completion Criteria

- Reloading `/wb/reports/rules` shows the saved organization profile, version, author, and history.
- Standard, conservative, and aggressive presets populate every field; manual edits become custom.
- Preview is server-side and save is impossible for a changed or unpreviewed draft.
- ABC remains fixed at `20/30/50` even for a crafted request.
- ABC, RNP, P&L, ads, stock, and WoW return and render the active `rulesProfileVersion` and real evaluations.
- Stock KPI/card counts use the same active thresholds as row status.
- Missing data yields `unknown` and no unsafe draft.
- Manager plans load/save through the real digest-plan API and affect plan-fact.
- Every recommendation is a confirmation-required draft; no price or ad mutation occurs automatically.
- Existing WoW `include_budgets=False` and progress behavior remain intact.
