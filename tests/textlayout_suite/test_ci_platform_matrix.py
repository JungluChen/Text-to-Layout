"""CI platform-support contract tests."""

from __future__ import annotations

from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]


def test_core_ci_covers_apple_silicon_and_supported_python_versions() -> None:
    workflow = yaml.safe_load((ROOT / ".github" / "workflows" / "ci.yml").read_text())
    matrix = workflow["jobs"]["test"]["strategy"]["matrix"]

    assert "macos-15" in matrix["os"]
    assert {"3.11", "3.12"} <= set(matrix["python"])
    assert workflow["jobs"]["test"]["strategy"]["fail-fast"] is False
