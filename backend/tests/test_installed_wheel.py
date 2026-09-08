from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import zipfile

PROJECT_ROOT = Path(__file__).resolve().parents[1]

EXPECTED_RUNTIME_FILES = {
    "app/cash_flow/__init__.py",
    "app/platform/funnel/__init__.py",
    "app/report_rules/presets.py",
    "app/wb_ads_cache/__init__.py",
    "app/security/__init__.py",
    "app/platform/integrations/__init__.py",
    "app/reviews/canonical_contract.py",
    "vella_wb_19_05/models.py",
}

REPRESENTATIVE_IMPORTS = (
    "app.cash_flow",
    "app.platform.funnel",
    "app.report_rules.presets",
    "app.wb_ads_cache",
    "app.security",
    "app.platform.integrations",
    "app.reviews.canonical_contract",
    "vella_wb_19_05.models",
)


def _run(*args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, *args],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    )


def test_built_wheel_contains_and_imports_runtime_packages(tmp_path: Path) -> None:
    wheelhouse = tmp_path / "wheelhouse"
    wheelhouse.mkdir()
    _run(
        "-m",
        "pip",
        "wheel",
        ".",
        "--wheel-dir",
        str(wheelhouse),
        "--no-build-isolation",
        "--no-deps",
        "--no-index",
        "--no-cache-dir",
        "--disable-pip-version-check",
        cwd=PROJECT_ROOT,
    )

    wheels = list(wheelhouse.glob("*.whl"))
    assert len(wheels) == 1
    wheel = wheels[0]
    with zipfile.ZipFile(wheel) as archive:
        installed_files = set(archive.namelist())
    assert EXPECTED_RUNTIME_FILES <= installed_files, (
        "built wheel is missing runtime files: "
        f"{sorted(EXPECTED_RUNTIME_FILES - installed_files)}"
    )

    target = tmp_path / "installed"
    _run(
        "-m",
        "pip",
        "install",
        str(wheel),
        "--target",
        str(target),
        "--no-index",
        "--no-deps",
        "--no-cache-dir",
        "--disable-pip-version-check",
        cwd=tmp_path,
    )

    outside_checkout = tmp_path / "outside-checkout"
    outside_checkout.mkdir()
    import_probe = """
import importlib
import json
from pathlib import Path
import sys

target = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(target))
origins = {}
for module_name in json.loads(sys.argv[2]):
    module = importlib.import_module(module_name)
    origin = Path(module.__file__).resolve()
    if not origin.is_relative_to(target):
        raise AssertionError(f"{module_name} loaded outside install target: {origin}")
    origins[module_name] = str(origin)
print(json.dumps(origins, sort_keys=True))
"""
    probe = _run(
        "-I",
        "-c",
        import_probe,
        str(target),
        json.dumps(REPRESENTATIVE_IMPORTS),
        cwd=outside_checkout,
    )
    origins = json.loads(probe.stdout)
    assert set(origins) == set(REPRESENTATIVE_IMPORTS)
    print(f"wheel={wheel}")
    print(json.dumps(origins, indent=2, sort_keys=True))
