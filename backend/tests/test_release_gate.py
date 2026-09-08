from pathlib import Path
from subprocess import CompletedProcess

import pytest

from ops.release_gate import (
    GateFailure,
    cleanup_container,
    compare_failure_sets,
    junit_failure_ids,
    run_steps,
)


def test_release_gate_happy_path_runs_every_step() -> None:
    completed: list[str] = []
    seen: list[str] = []
    steps = tuple((name, (name,), Path(".")) for name in ("compile", "test", "build"))

    run_steps(steps, lambda command, _cwd: seen.append(command[0]) or 0, completed)

    assert seen == completed == ["compile", "test", "build"]


def test_release_gate_stops_at_first_failure() -> None:
    completed: list[str] = []
    seen: list[str] = []
    steps = tuple((name, (name,), Path(".")) for name in ("compile", "test", "build"))

    with pytest.raises(GateFailure, match="test failed"):
        run_steps(
            steps,
            lambda command, _cwd: (
                seen.append(command[0]) or (1 if command[0] == "test" else 0)
            ),
            completed,
        )

    assert seen == ["compile", "test"]
    assert completed == ["compile"]


def test_release_gate_reports_changed_baseline() -> None:
    comparison = compare_failure_sets({"test_a", "test_b"}, {"test_a", "test_c"}, set())

    assert comparison["status"] == "changed"
    assert comparison["added_ids"] == ["test_c"]
    assert comparison["missing_ids"] == ["test_b"]


def test_release_gate_reads_failure_and_error_ids(tmp_path: Path) -> None:
    junit = tmp_path / "junit.xml"
    junit.write_text(
        '<testsuite><testcase classname="tests.test_one" name="test_failure" '
        'file="tests/test_one.py"><failure /></testcase>'
        '<testcase classname="tests.test_two.TestCase" name="test_error" '
        'file="tests/test_two.py"><error /></testcase></testsuite>',
        encoding="utf-8",
    )

    assert junit_failure_ids(junit) == (
        {"tests/test_one.py::test_failure"},
        {"tests/test_two.py::TestCase::test_error"},
    )


def test_release_gate_cleanup_targets_only_created_container() -> None:
    calls: list[list[str]] = []

    def fake_run(command: list[str], **_kwargs: object) -> CompletedProcess[str]:
        calls.append(command)
        return CompletedProcess(command, 0)

    assert cleanup_container(None, fake_run)
    assert cleanup_container("satorna-gate-123-postgres", fake_run)
    assert calls == [["docker", "rm", "-f", "satorna-gate-123-postgres"]]
