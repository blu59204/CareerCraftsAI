"""Tests for the narrow changed-code Black policy."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load_gate():
    script = Path(__file__).resolve().parents[3] / "scripts" / "check_changed_python_format.py"
    spec = importlib.util.spec_from_file_location("format_gate", script)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(script.parent))
    try:
        spec.loader.exec_module(module)
    finally:
        sys.path.pop(0)
    return module


def test_changed_files_exclude_only_documented_legacy_baseline(monkeypatch) -> None:
    gate = _load_gate()

    class Result:
        returncode = 0
        stderr = ""
        stdout = "backend/app/agents/job_search.py\nbackend/app/integrations/nango.py\n"

    monkeypatch.setattr(gate, "run", lambda *args: Result())
    monkeypatch.setattr(gate.Path, "is_file", lambda _: True)

    assert gate.changed_python_files("base") == [Path("backend/app/integrations/nango.py")]


def test_initial_push_uses_the_empty_tree_as_two_diff_arguments(monkeypatch) -> None:
    gate = _load_gate()
    captured: list[str] = []

    class Result:
        returncode = 0
        stderr = ""
        stdout = ""

    def fake_run(*args):
        captured.extend(args)
        return Result()

    monkeypatch.setattr(gate, "run", fake_run)

    assert gate.changed_python_files(gate.EMPTY_TREE_SHA) == []
    assert captured[4:6] == [gate.EMPTY_TREE_SHA, "HEAD"]


def test_backend_files_use_the_backend_black_configuration(monkeypatch) -> None:
    gate = _load_gate()
    commands: list[tuple[str, ...]] = []

    class Result:
        returncode = 0
        stderr = ""
        stdout = ""

    def fake_run(*args):
        commands.append(args)
        return Result()

    monkeypatch.setattr(gate, "run", fake_run)

    assert (
        gate.check_black([Path("backend/app/integrations/nango.py"), Path("scripts/tool.py")]) == 0
    )
    assert "backend/pyproject.toml" in commands[0]
    assert "backend/pyproject.toml" not in commands[1]
