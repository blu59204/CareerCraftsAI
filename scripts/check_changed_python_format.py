"""Require Black formatting for branch changes while retaining one legacy baseline."""

from __future__ import annotations

import sys
from pathlib import Path

from check_changed_python_lint import EMPTY_TREE_SHA, ROOT, base_revision, run

# This file predates the branch and has unrelated local work. Keep it explicit
# so all other changed Python files remain subject to Black in CI.
LEGACY_FORMAT_BASELINE = {Path("backend/app/agents/job_search.py")}


def changed_python_files(base: str) -> list[Path]:
    range_args = (
        (EMPTY_TREE_SHA, "HEAD") if base == EMPTY_TREE_SHA else (f"{base}..HEAD",)
    )
    result = run(
        "git", "diff", "--name-only", "--diff-filter=ACMR", *range_args, "--", "*.py"
    )
    if result.returncode:
        raise RuntimeError(
            result.stderr.strip() or "Could not read the Python Git diff"
        )

    files = [Path(path) for path in result.stdout.splitlines() if path]
    return [
        path
        for path in files
        if path not in LEGACY_FORMAT_BASELINE and (ROOT / path).is_file()
    ]


def main() -> int:
    try:
        files = changed_python_files(base_revision())
    except RuntimeError as exc:
        print(
            f"Changed-code Black gate could not determine its base: {exc}",
            file=sys.stderr,
        )
        return 2

    if not files:
        print("Changed-code Black gate passed (no non-baseline Python files).")
        return 0

    result = run(sys.executable, "-m", "black", "--check", *map(str, files))
    if result.stdout:
        print(result.stdout, end="")
    if result.stderr:
        print(result.stderr, end="", file=sys.stderr)
    if result.returncode:
        return result.returncode
    print("Changed-code Black gate passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
