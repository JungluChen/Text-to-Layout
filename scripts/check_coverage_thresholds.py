#!/usr/bin/env python3
"""Enforce non-legacy product coverage and stricter changed critical modules."""

from __future__ import annotations

import argparse
import fnmatch
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

GLOBAL_LINE_MIN = 78.0
GLOBAL_BRANCH_MIN = 60.0
CHANGED_CRITICAL_LINE_MIN = 85.0
CHANGED_CRITICAL_BRANCH_MIN = 75.0
HIGH_ASSURANCE_LINE_MIN = 90.0
CRITICAL_PATTERNS = (
    "src/textlayout/evidence/*.py",
    "src/textlayout/signoff.py",
    "src/textlayout/solvers/**/capability.py",
    "src/textlayout/solvers/**/parser.py",
)
HIGH_ASSURANCE_PATTERNS = (
    "src/textlayout/evidence/*.py",
    "src/textlayout/signoff.py",
    "src/textlayout/solvers/**/capability.py",
    "src/textlayout/solvers/**/parser.py",
)


def _percentage(covered: int, total: int) -> float:
    return 100.0 if total == 0 else 100.0 * covered / total


def _matches(path: str, patterns: tuple[str, ...]) -> bool:
    return any(fnmatch.fnmatch(path, pattern) for pattern in patterns)


def evaluate(payload: dict[str, Any], *, changed_files: list[str]) -> list[str]:
    problems: list[str] = []
    files = payload["files"]
    legacy = sorted(path for path in files if path.startswith("src/textlayout/_legacy/"))
    if legacy:
        problems.append("coverage payload includes frozen legacy modules")
    totals = payload["totals"]
    line = _percentage(totals["covered_lines"], totals["num_statements"])
    branch = _percentage(totals["covered_branches"], totals["num_branches"])
    if line < GLOBAL_LINE_MIN:
        problems.append(f"product line coverage {line:.2f}% < {GLOBAL_LINE_MIN:.2f}%")
    if branch < GLOBAL_BRANCH_MIN:
        problems.append(f"product branch coverage {branch:.2f}% < {GLOBAL_BRANCH_MIN:.2f}%")

    for path in sorted(set(changed_files)):
        if not _matches(path, CRITICAL_PATTERNS):
            continue
        data = files.get(path)
        if data is None:
            problems.append(f"changed critical module is absent from coverage data: {path}")
            continue
        summary = data["summary"]
        module_line = _percentage(summary["covered_lines"], summary["num_statements"])
        module_branch = _percentage(summary["covered_branches"], summary["num_branches"])
        line_floor = (
            HIGH_ASSURANCE_LINE_MIN
            if _matches(path, HIGH_ASSURANCE_PATTERNS)
            else CHANGED_CRITICAL_LINE_MIN
        )
        if module_line < line_floor:
            problems.append(f"{path} line coverage {module_line:.2f}% < {line_floor:.2f}%")
        if module_branch < CHANGED_CRITICAL_BRANCH_MIN:
            problems.append(
                f"{path} branch coverage {module_branch:.2f}% "
                f"< {CHANGED_CRITICAL_BRANCH_MIN:.2f}%"
            )
    return problems


def _changed_files(base: str | None) -> list[str]:
    if base is None:
        return []
    completed = subprocess.run(
        ["git", "diff", "--name-only", f"{base}...HEAD"],
        capture_output=True,
        text=True,
        check=True,
    )
    return [line for line in completed.stdout.splitlines() if line]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("coverage_json", type=Path)
    parser.add_argument("--base")
    args = parser.parse_args(argv)
    payload = json.loads(args.coverage_json.read_text(encoding="utf-8"))
    problems = evaluate(payload, changed_files=_changed_files(args.base))
    if problems:
        for problem in problems:
            print(f"coverage error: {problem}", file=sys.stderr)
        return 1
    print("Non-legacy coverage thresholds: pass")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
