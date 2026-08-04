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


def test_platform_records_preserve_the_certification_boundary() -> None:
    macos = (ROOT / "docs" / "platforms" / "macos_arm64.md").read_text(encoding="utf-8")
    wsl = (ROOT / "docs" / "platforms" / "wsl2_ubuntu.md").read_text(encoding="utf-8")

    assert "CORE CERTIFIED" in macos
    assert "1,871 passed; 13 skipped" in macos
    assert "external numerical solvers are not certified" in macos
    assert "NOT_TESTED_ON_PLATFORM" in wsl
    assert "explicit non-certification record" in wsl
