"""Fail CI when Ruff finds diagnostics on newly changed Python lines.

The repository has a documented legacy Ruff backlog. This script intentionally
keeps that backlog visible in the regular Ruff job while rejecting diagnostics
introduced by the current Git range. It never treats an unknown comparison
base as an empty change set.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
EMPTY_TREE_SHA = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"
ZERO_SHA = "0" * 40
HUNK = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@")


def run(*args: str) -> subprocess.CompletedProcess[str]:
    """Run Git or Ruff from the repository root without shell expansion."""
    # Arguments are passed as a fixed list and never through a shell.
    return subprocess.run(  # nosec B603
        args,
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )


def _verify_commit(revision: str, label: str) -> str:
    result = run("git", "rev-parse", "--verify", f"{revision}^{{commit}}")
    if result.returncode:
        raise RuntimeError(
            f"Unable to resolve {label} '{revision}'. Fetch the comparison base."
        )
    return result.stdout.strip()


def base_revision() -> str:
    """Resolve a real base commit, or the empty tree for an initial push."""
    configured = os.environ.get("CI_LINT_BASE_SHA", "").strip()
    if configured == ZERO_SHA:
        return EMPTY_TREE_SHA
    if configured:
        return _verify_commit(configured, "CI_LINT_BASE_SHA")

    result = run("git", "rev-parse", "--verify", "HEAD^")
    if result.returncode:
        raise RuntimeError(
            "CI_LINT_BASE_SHA is unavailable and HEAD has no parent; "
            "provide a base SHA or use the all-zero initial-push SHA."
        )
    return result.stdout.strip()


def _diff_command(base: str) -> tuple[str, ...]:
    if base == EMPTY_TREE_SHA:
        return ("git", "diff", "--unified=0", EMPTY_TREE_SHA, "HEAD", "--", "*.py")
    # `github.event.before` is the prior pushed commit, and the PR base is an
    # explicit commit. A direct range needs only that fetched object; `...`
    # additionally requires a merge base and failed in shallow CI checkouts.
    return ("git", "diff", "--unified=0", f"{base}..HEAD", "--", "*.py")


def changed_python_lines(base: str) -> dict[Path, set[int]]:
    """Return added or replaced line numbers keyed by their repository path."""
    result = run(*_diff_command(base))
    if result.returncode:
        raise RuntimeError(
            result.stderr.strip() or "Could not read the Python Git diff"
        )

    lines: dict[Path, set[int]] = defaultdict(set)
    current: Path | None = None
    for line in result.stdout.splitlines():
        if line.startswith("+++ b/"):
            current = (ROOT / line.removeprefix("+++ b/")).resolve()
            continue
        if line.startswith("+++"):
            current = None
            continue
        match = HUNK.match(line)
        if match is None or current is None:
            continue
        start = int(match.group(1))
        count = int(match.group(2) or "1")
        lines[current].update(range(start, start + count))
    return dict(lines)


def changed_diagnostics(
    diagnostics: list[dict[str, Any]], changed: dict[Path, set[int]]
) -> list[dict[str, Any]]:
    """Select Ruff diagnostics whose location is on a changed line."""
    changed_by_path = {path.resolve(): lines for path, lines in changed.items()}
    failures: list[dict[str, Any]] = []
    for diagnostic in diagnostics:
        filename = diagnostic.get("filename")
        location = diagnostic.get("location") or {}
        row = location.get("row")
        if not isinstance(filename, str) or not isinstance(row, int):
            continue
        path = Path(filename)
        resolved = path.resolve() if path.is_absolute() else (ROOT / path).resolve()
        if row in changed_by_path.get(resolved, set()):
            failures.append(diagnostic)
    return failures


def ruff_diagnostics() -> list[dict[str, Any]]:
    """Get machine-readable diagnostics without relying on Ruff's exit code."""
    result = run(sys.executable, "-m", "ruff", "check", ".", "--output-format=json")
    if result.returncode not in {0, 1}:
        raise RuntimeError(result.stderr.strip() or "Ruff could not run")
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Ruff did not produce valid JSON: {exc}") from exc
    if not isinstance(payload, list):
        raise TypeError("Ruff JSON output was not a diagnostic list")
    return payload


def _format_diagnostic(diagnostic: dict[str, Any]) -> str:
    location = diagnostic.get("location") or {}
    return "{filename}:{row}:{column}: {code} {message}".format(
        filename=diagnostic.get("filename", "<unknown>"),
        row=location.get("row", "?"),
        column=location.get("column", "?"),
        code=diagnostic.get("code", "RUFF"),
        message=diagnostic.get("message", "Ruff diagnostic"),
    )


def main() -> int:
    try:
        changed = changed_python_lines(base_revision())
        failures = changed_diagnostics(ruff_diagnostics(), changed)
    except RuntimeError as exc:
        print(f"error: changed-code Ruff gate failed: {exc}", file=sys.stderr)
        return 2

    if not failures:
        print("Changed-code Ruff gate passed.")
        return 0

    print("Ruff diagnostics on changed Python lines:", file=sys.stderr)
    for diagnostic in failures:
        print(_format_diagnostic(diagnostic), file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
