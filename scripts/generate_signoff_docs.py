#!/usr/bin/env python3
"""Generate/check signoff tables from ``textlayout.signoff.SIGNOFF_LEVELS``."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from textlayout.signoff import SIGNOFF_LEVELS

ROOT = Path(__file__).resolve().parents[1]
START = "<!-- SIGNOFF_LEVEL_TABLE_BEGIN -->"
END = "<!-- SIGNOFF_LEVEL_TABLE_END -->"


def table(*, include_no_geometry: bool) -> str:
    rows = [START, "| Level | Label | Requires |", "| ---: | --- | --- |"]
    for level, label, requirement in SIGNOFF_LEVELS:
        if level < 0 and not include_no_geometry:
            continue
        display_label = f"**{label}**" if level >= 5 else label
        rows.append(f"| {level} | {display_label} | {requirement} |")
    rows.append(END)
    return "\n".join(rows)


def replace_table(content: str, replacement: str) -> str:
    before, marker, remainder = content.partition(START)
    if not marker:
        raise ValueError(f"missing {START}")
    _, marker, after = remainder.partition(END)
    if not marker:
        raise ValueError(f"missing {END}")
    return before + replacement + after


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    targets = {
        ROOT / "SIGNOFF_CRITERIA.md": table(include_no_geometry=False),
        ROOT / "docs" / "signoff_levels.md": table(include_no_geometry=True),
    }
    stale: list[Path] = []
    for path, replacement in targets.items():
        current = path.read_text(encoding="utf-8")
        rendered = replace_table(current, replacement)
        if rendered == current:
            continue
        stale.append(path)
        if not args.check:
            path.write_text(rendered, encoding="utf-8")
    if stale and args.check:
        for path in stale:
            print(f"stale generated signoff table: {path.relative_to(ROOT)}", file=sys.stderr)
        return 1
    print("Signoff documentation tables: current")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
