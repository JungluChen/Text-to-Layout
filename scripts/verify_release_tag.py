"""Require a release tag to match the package's declared version exactly."""

from __future__ import annotations

import re
import sys
import tomllib
from pathlib import Path


def verify(tag: str, project_file: Path) -> None:
    if not re.fullmatch(r"v[0-9]+\.[0-9]+\.[0-9]+", tag):
        raise ValueError("release tag must be vMAJOR.MINOR.PATCH")
    project = tomllib.loads(project_file.read_text(encoding="utf-8"))["project"]
    if tag != f"v{project['version']}":
        raise ValueError(f"release tag {tag} does not match project version {project['version']}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: verify_release_tag.py vMAJOR.MINOR.PATCH")
    verify(sys.argv[1], Path(__file__).resolve().parents[1] / "pyproject.toml")
    print(f"release tag {sys.argv[1]} matches pyproject.toml")
