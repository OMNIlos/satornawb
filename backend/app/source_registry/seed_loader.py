from __future__ import annotations

import re
from dataclasses import dataclass
from difflib import get_close_matches
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OPEN_QUESTIONS_PATH = ROOT / "product-docs" / "docs" / "open-questions-current.md"
SOURCE_REGISTRY_PATH = ROOT / "product-docs" / "docs" / "handoffs" / "wb-backend-source-registry.md"
FORMULA_CATALOG_PATH = ROOT / "product-docs" / "docs" / "handoffs" / "wb-backend-formula-catalog.md"


@dataclass(frozen=True)
class BlockerSeed:
    blocker_id: str
    lifecycle_status: str
    question: str
    owner: str
    impact_area: str
    resolution_needed: str
    source_ref: str = "docs/open-questions-current.md"


@dataclass(frozen=True)
class FormulaSeed:
    formula_id: str
    formula_name: str
    inputs: str
    output_units: str
    rule: str
    rounding: str
    owner: str
    status: str
    used_by: str
    blocker_ids: list[str]
    source_ref: str = "docs/handoffs/wb-backend-formula-catalog.md"


@dataclass(frozen=True)
class SourceRegistrySeed:
    screen: str
    metric_action: str
    module: str
    source_name: str
    source_field: str
    formula_text: str
    formula_id: str
    refresh_policy: str
    fallback_policy: str
    freshness_confidence: str
    status: str
    blocker_ids: list[str]
    critical_for_apply: bool
    source_ref: str = "docs/handoffs/wb-backend-source-registry.md"


def _split_markdown_row(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def _slugify(value: str) -> str:
    lowered = value.lower()
    cleaned = re.sub(r"[^a-z0-9]+", "-", lowered)
    return cleaned.strip("-")[:48] or "item"


def _extract_ids(cell: str) -> list[str]:
    return re.findall(r"[A-Z]{1,4}-\d+[A-Z]?", cell)


def _normalize_text(value: str) -> str:
    value = value.lower()
    value = value.replace("ё", "е")
    value = re.sub(r"[^\w\s]+", " ", value, flags=re.UNICODE)
    value = re.sub(r"\s+", " ", value).strip()
    return value


def _module_from_screen(screen: str) -> str:
    clean = screen.strip().strip("`")
    parts = [p for p in clean.strip("/").split("/") if p]
    if len(parts) >= 2 and parts[0] == "wb":
        return parts[1]
    if len(parts) >= 2:
        return parts[1]
    return parts[0] if parts else "unknown"


def _is_critical_for_apply(screen: str, metric_action: str) -> bool:
    text = _normalize_text(f"{screen} {metric_action}")
    keywords = (
        "price apply",
        "спп",
        "p_min",
        "p_max",
        "margin",
        "liquidation",
    )
    return any(keyword in text for keyword in keywords)


def load_blocker_seeds() -> list[BlockerSeed]:
    section: str | None = None
    seeds: list[BlockerSeed] = []
    for raw_line in OPEN_QUESTIONS_PATH.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if line.startswith("## BLOCKER"):
            section = "BLOCKER"
            continue
        if line.startswith("## CONFIRM"):
            section = "CONFIRM"
            continue
        if line.startswith("## LATER"):
            section = "LATER"
            continue
        if section is None or not line.startswith("|"):
            continue
        if re.match(r"^\|\s*ID\s*\|", line, flags=re.IGNORECASE):
            continue
        if re.match(r"^\|\s*---", line):
            continue
        cells = _split_markdown_row(line)
        if len(cells) < 5:
            continue
        blocker_id = cells[0]
        if not re.fullmatch(r"[A-Z]{1,4}-\d+[A-Z]?", blocker_id):
            continue
        seeds.append(
            BlockerSeed(
                blocker_id=blocker_id,
                lifecycle_status=section,
                question=cells[1],
                owner=cells[2],
                impact_area=cells[3],
                resolution_needed=cells[4],
            )
        )
    return seeds


def load_formula_seeds() -> list[FormulaSeed]:
    formulas: list[FormulaSeed] = []
    lines = FORMULA_CATALOG_PATH.read_text(encoding="utf-8").splitlines()
    i = 0
    seen: set[str] = set()
    while i < len(lines):
        line = lines[i].strip()
        if line.lower().startswith("| formula |"):
            i += 2
            while i < len(lines):
                row = lines[i].strip()
                if not row.startswith("|"):
                    break
                cells = _split_markdown_row(row)
                if len(cells) < 8:
                    i += 1
                    continue
                formula_name = cells[0]
                formula_id = f"frm-{_slugify(formula_name)}"
                if formula_id in seen:
                    formula_id = f"{formula_id}-{len(seen)+1}"
                seen.add(formula_id)
                owner_cell = cells[5]
                status_match = re.search(r"`([^`]+)`", owner_cell)
                status = status_match.group(1) if status_match else "draft"
                owner = owner_cell.split("/")[0].strip()
                formulas.append(
                    FormulaSeed(
                        formula_id=formula_id,
                        formula_name=formula_name,
                        inputs=cells[1],
                        output_units=cells[2],
                        rule=cells[3],
                        rounding=cells[4],
                        owner=owner,
                        status=status,
                        used_by=cells[6],
                        blocker_ids=_extract_ids(cells[7]),
                    )
                )
                i += 1
            continue
        i += 1
    return formulas


def _resolve_formula_id(metric_action: str, formula_text: str, formulas: list[FormulaSeed]) -> str | None:
    if not formulas:
        return None
    name_map = {formula.formula_name: formula.formula_id for formula in formulas}
    normalized_names = {_normalize_text(formula.formula_name): formula.formula_id for formula in formulas}
    target = _normalize_text(f"{metric_action} {formula_text}")
    for normalized_name, formula_id in normalized_names.items():
        if normalized_name and normalized_name in target:
            return formula_id
    close = get_close_matches(target, list(normalized_names.keys()), n=1, cutoff=0.62)
    if close:
        return normalized_names[close[0]]
    exact = name_map.get(formula_text)
    if exact is not None:
        return exact
    return None


def load_source_registry_seeds(formulas: list[FormulaSeed]) -> tuple[list[SourceRegistrySeed], list[FormulaSeed]]:
    rows: list[SourceRegistrySeed] = []
    lines = SOURCE_REGISTRY_PATH.read_text(encoding="utf-8").splitlines()
    in_table = False
    derived_formulas: dict[str, FormulaSeed] = {}
    next_row_id = 1

    for raw_line in lines:
        line = raw_line.strip()
        if line.startswith("| screen | metric/action |"):
            in_table = True
            continue
        if in_table and line.startswith("## "):
            break
        if not in_table or not line.startswith("|"):
            continue
        if re.match(r"^\|\s*---", line):
            continue
        cells = _split_markdown_row(line)
        if len(cells) < 10:
            continue
        screen, metric_action, source_name, source_field, formula_text, refresh, fallback, freshness_conf, status, blockers = cells[:10]
        formula_id = _resolve_formula_id(metric_action, formula_text, formulas)
        if formula_id is None:
            formula_id = f"frm-derived-{_slugify(formula_text)}"
            if formula_id not in derived_formulas:
                derived_formulas[formula_id] = FormulaSeed(
                    formula_id=formula_id,
                    formula_name=formula_text,
                    inputs="derived from source registry row",
                    output_units="mixed",
                    rule=formula_text,
                    rounding="n/a",
                    owner="source registry seed",
                    status="derived",
                    used_by=metric_action,
                    blocker_ids=_extract_ids(blockers),
                    source_ref="docs/handoffs/wb-backend-source-registry.md",
                )
        normalized_screen = screen.strip().strip("`")
        row = SourceRegistrySeed(
            screen=normalized_screen,
            metric_action=metric_action,
            module=_module_from_screen(normalized_screen),
            source_name=source_name,
            source_field=source_field,
            formula_text=formula_text,
            formula_id=formula_id,
            refresh_policy=refresh,
            fallback_policy=fallback,
            freshness_confidence=freshness_conf,
            status=status,
            blocker_ids=_extract_ids(blockers),
            critical_for_apply=_is_critical_for_apply(screen, metric_action),
        )
        rows.append(row)
        next_row_id += 1

    all_formulas = formulas + list(derived_formulas.values())
    return rows, all_formulas
