#!/usr/bin/env python3
"""Fail on broken local links in maintained Markdown documentation.

Historical snapshots are deliberately excluded by an explicit allow-list. They
remain auditable records of the repository at the time they were written and
are not silently rewritten to resemble the current tree.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
HISTORICAL_PREFIXES = (
    "legacy/",
    "baselines/",
    "compose/",
)
HISTORICAL_FILES = frozenset({"improvement_registries.md"})
LINK_RE = re.compile(r"!?\[[^\]]*\]\((?P<target>[^)]+)\)")


def is_historical(relative: str) -> bool:
    return relative in HISTORICAL_FILES or relative.startswith(HISTORICAL_PREFIXES)


def maintained_documents(docs_root: Path = DOCS) -> list[Path]:
    return [
        path
        for path in sorted(docs_root.rglob("*.md"))
        if not is_historical(path.relative_to(docs_root).as_posix())
    ]


def _local_target(raw: str) -> str | None:
    target = raw.strip()
    if target.startswith("<") and target.endswith(">"):
        target = target[1:-1]
    # Optional Markdown titles follow whitespace after the URL.
    target = target.split(maxsplit=1)[0]
    if not target or target.startswith(("#", "http://", "https://", "mailto:")):
        return None
    return unquote(target.split("#", 1)[0].split("?", 1)[0])


def broken_links(docs_root: Path = DOCS) -> list[str]:
    problems: list[str] = []
    for source in maintained_documents(docs_root):
        relative_source = source.relative_to(docs_root).as_posix()
        for match in LINK_RE.finditer(source.read_text(encoding="utf-8")):
            target_text = _local_target(match.group("target"))
            if target_text is None:
                continue
            target = (source.parent / target_text).resolve()
            if target.is_dir():
                target = target / "index.md"
            if not target.exists():
                problems.append(f"{relative_source}: missing local link target {target_text!r}")
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--docs-root", type=Path, default=DOCS)
    args = parser.parse_args(argv)
    problems = broken_links(args.docs_root.resolve())
    if problems:
        print("Documentation link check failed:", file=sys.stderr)
        for problem in problems:
            print(f"- {problem}", file=sys.stderr)
        return 1
    historical_count = sum(
        1
        for path in args.docs_root.rglob("*.md")
        if is_historical(path.relative_to(args.docs_root).as_posix())
    )
    print(
        f"Documentation links valid across {len(maintained_documents(args.docs_root))} "
        f"maintained files ({historical_count} historical files explicitly excluded)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
