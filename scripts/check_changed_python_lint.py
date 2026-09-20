"""Fail CI only for Ruff diagnostics on Python lines changed by this revision.

The repository has a documented pre-existing Ruff backlog. This gate keeps the
backlog visible in the quality job while preventing new violations from being
merged before the backlog is paid down. It intentionally matches changed lines
instead of ignoring Ruff rules or excluding directories.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HUNK = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@")


def run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )


def base_revision() -> str:
    configured = os.environ.get("CI_LINT_BASE_SHA", "").strip()
    if configured and configured != "0000000000000000000000000000000000000000":
        return configured

    result = run("git", "rev-parse", "HEAD^")
    if result.returncode:
        raise RuntimeError("CI_LINT_BASE_SHA is required when HEAD has no parent")
    return result.stdout.strip()


def changed_python_lines(base: str) -> dict[Path, set[int]]:
    result = run("git", "diff", "--unified=0", f"{base}...HEAD", "--", "*.py")
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or "Could not read Git diff")

    lines: dict[Path, set[int]] = defaultdict(set)
    current: Path | None = None
    for line in result.stdout.splitlines():
        if line.startswith("+++ b/"):
            current = ROOT / line.removeprefix("+++ b/")
            continue
        match = HUNK.match(line)
        if match and current is not None:
            start = int(match.group(1))
            count = int(match.group(2) or "1")
            lines[current.resolve()].update(range(start, start + count))
    return lines


def main() -> int:
    changed = changed_python_lines(base_revision())
    if not changed:
        print("No changed Python lines to lint.")
        return 0

    result = run(sys.executable, "-m", "ruff", "check", "--output-format=json", ".")
    try:
        diagnostics = json.loads(result.stdout or "[]")
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Ruff did not return JSON: {result.stdout}\n{result.stderr}") from exc

    introduced = [
        diagnostic
        for diagnostic in diagnostics
        if Path(diagnostic["filename"]).resolve() in changed
        and diagnostic["location"]["row"] in changed[Path(diagnostic["filename"]).resolve()]
    ]
    if not introduced:
        print("No Ruff diagnostics on changed Python lines.")
        return 0

    for diagnostic in introduced:
        location = diagnostic["location"]
        print(
            f"{diagnostic['filename']}:{location['row']}:{location['column']}: "
            f"{diagnostic['code']} {diagnostic['message']}"
        )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
