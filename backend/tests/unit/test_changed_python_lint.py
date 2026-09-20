"""Regression tests for the CI changed-code Ruff gate."""

from __future__ import annotations

import importlib.util
import subprocess
from pathlib import Path

import pytest


def _load_lint_gate():
    path = (
        Path(__file__).resolve().parents[3] / "scripts" / "check_changed_python_lint.py"
    )
    spec = importlib.util.spec_from_file_location("changed_python_lint", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def lint_gate():
    return _load_lint_gate()


def _completed(*args: str, output: str = "", returncode: int = 0):
    return subprocess.CompletedProcess(
        args, returncode, stdout=output, stderr="base missing"
    )


def test_changed_python_file_without_ruff_diagnostics_passes(lint_gate) -> None:
    changed = {Path("/repo/backend/app/new_code.py"): {2, 3}}

    assert lint_gate.changed_diagnostics([], changed) == []


def test_violation_on_changed_line_is_reported(lint_gate) -> None:
    changed = {Path("/repo/backend/app/new_code.py"): {2}}
    diagnostics = [
        {
            "filename": "/repo/backend/app/new_code.py",
            "location": {"row": 2, "column": 1},
            "code": "F401",
            "message": "unused import",
        }
    ]

    assert lint_gate.changed_diagnostics(diagnostics, changed) == diagnostics


def test_legacy_violation_on_unchanged_line_is_not_reported(lint_gate) -> None:
    changed = {Path("/repo/backend/app/legacy.py"): {8}}
    diagnostics = [
        {
            "filename": "/repo/backend/app/legacy.py",
            "location": {"row": 2, "column": 1},
            "code": "F401",
            "message": "legacy unused import",
        }
    ]

    assert lint_gate.changed_diagnostics(diagnostics, changed) == []


def test_new_file_and_filename_with_spaces_are_parsed(lint_gate, monkeypatch) -> None:
    monkeypatch.setattr(
        lint_gate,
        "run",
        lambda *args: _completed(
            *args,
            output="""diff --git a/backend/app/old.py b/backend/app/new file.py
new file mode 100644
--- /dev/null
+++ b/backend/app/new file.py
@@ -0,0 +1,2 @@
+import os
+print(os.name)
""",
        ),
    )

    changed = lint_gate.changed_python_lines("base")

    assert changed == {lint_gate.ROOT / "backend/app/new file.py": {1, 2}}


def test_deleted_file_does_not_produce_changed_lines(lint_gate, monkeypatch) -> None:
    monkeypatch.setattr(
        lint_gate,
        "run",
        lambda *args: _completed(
            *args,
            output="""diff --git a/backend/app/deleted.py b/backend/app/deleted.py
deleted file mode 100644
--- a/backend/app/deleted.py
+++ /dev/null
@@ -1,2 +0,0 @@
-import os
-print(os.name)
""",
        ),
    )

    assert lint_gate.changed_python_lines("base") == {}


def test_push_or_pull_request_base_uses_a_direct_git_diff(lint_gate) -> None:
    """A fetched base commit must not require a merge-base lookup in CI."""

    assert lint_gate._diff_command("base-sha") == (
        "git",
        "diff",
        "--unified=0",
        "base-sha..HEAD",
        "--",
        "*.py",
    )


def test_missing_base_sha_falls_back_to_parent_for_a_non_initial_push(
    lint_gate, monkeypatch
) -> None:
    monkeypatch.delenv("CI_LINT_BASE_SHA", raising=False)
    monkeypatch.setattr(
        lint_gate,
        "run",
        lambda *args: _completed(*args, output="parent-sha\n"),
    )

    assert lint_gate.base_revision() == "parent-sha"


def test_initial_push_uses_the_empty_tree(lint_gate, monkeypatch) -> None:
    monkeypatch.setenv("CI_LINT_BASE_SHA", "0" * 40)

    assert lint_gate.base_revision() == lint_gate.EMPTY_TREE_SHA


def test_git_commands_decode_utf8_output(lint_gate, monkeypatch) -> None:
    captured = {}

    def fake_run(*args, **kwargs):
        captured.update(kwargs)
        return _completed(*args)

    monkeypatch.setattr(lint_gate.subprocess, "run", fake_run)

    lint_gate.run("git", "diff", "HEAD")

    assert captured["encoding"] == "utf-8"
    assert captured["errors"] == "replace"


def test_unresolvable_base_sha_fails_clearly(lint_gate, monkeypatch) -> None:
    monkeypatch.setenv("CI_LINT_BASE_SHA", "missing-base")
    monkeypatch.setattr(lint_gate, "run", lambda *args: _completed(*args, returncode=1))

    with pytest.raises(RuntimeError, match="Unable to resolve CI_LINT_BASE_SHA"):
        lint_gate.base_revision()
