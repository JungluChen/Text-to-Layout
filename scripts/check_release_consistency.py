#!/usr/bin/env python3
"""Require release tag, package metadata, and dated changelog entry to agree."""

from __future__ import annotations

import argparse
import re
import sys
import tomllib
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENTRY_RE = re.compile(r"^## \[(?P<version>\d+\.\d+\.\d+)\] - (?P<date>\d{4}-\d{2}-\d{2})$", re.MULTILINE)


def validate_release(*, tag: str | None, root: Path = ROOT) -> list[str]:
    project = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    version = str(project["project"]["version"])
    entries = {
        match.group("version"): match.group("date")
        for match in ENTRY_RE.finditer((root / "CHANGELOG.md").read_text(encoding="utf-8"))
    }
    problems: list[str] = []
    if tag is not None and tag != f"v{version}":
        problems.append(f"release tag {tag!r} does not match package version v{version}")
    release_date = entries.get(version)
    if release_date is None:
        problems.append(f"CHANGELOG.md has no dated [{version}] release entry")
    else:
        try:
            parsed = date.fromisoformat(release_date)
        except ValueError:
            problems.append(f"CHANGELOG.md release date is invalid: {release_date!r}")
        else:
            if parsed > date.today():
                problems.append(f"CHANGELOG.md release date is in the future: {release_date}")
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tag")
    args = parser.parse_args(argv)
    problems = validate_release(tag=args.tag)
    if problems:
        for problem in problems:
            print(f"release consistency error: {problem}", file=sys.stderr)
        return 1
    print("Release tag/package/changelog consistency: pass")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
