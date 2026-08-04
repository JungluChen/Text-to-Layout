"""CI platform-support contract tests."""

from __future__ import annotations

from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]


def test_core_ci_covers_apple_silicon_and_supported_python_versions() -> None:
    workflow = yaml.safe_load((ROOT / ".github" / "workflows" / "ci.yml").read_text())
    matrix = workflow["jobs"]["test"]["strategy"]["matrix"]

    assert "macos-14" in matrix["os"]
    assert {"3.11", "3.12"} <= set(matrix["python"])
    assert workflow["jobs"]["test"]["strategy"]["fail-fast"] is False


def test_every_core_matrix_platform_runs_the_same_required_smokes() -> None:
    workflow = yaml.safe_load((ROOT / ".github" / "workflows" / "ci.yml").read_text())
    steps = workflow["jobs"]["test"]["steps"]
    commands = "\n".join(str(step.get("run", "")) for step in steps)
    for required in (
        "uv sync --dev",
        "validate_readme_claims.py",
        "check_namespace_boundary.py --check",
        "ruff check .",
        "mypy",
        "pytest --junit-xml=out/evidence/test_report.xml",
        "generate_project_status.py --check",
        "uv build",
        "textlayout --help",
        "textlayout doctor --json",
        "tests/textlayout_suite/test_api.py",
        "textlayout prompt",
    ):
        assert required in commands


def test_platform_records_preserve_the_certification_boundary() -> None:
    macos = (ROOT / "docs" / "platforms" / "macos_arm64.md").read_text(encoding="utf-8")
    wsl = (ROOT / "docs" / "platforms" / "wsl2_ubuntu.md").read_text(encoding="utf-8")

    assert "CORE CERTIFIED" in macos
    assert "1,871 passed; 13 skipped" in macos
    assert "external numerical solvers are not certified" in macos
    assert "NOT_TESTED_ON_PLATFORM" in wsl
    assert "explicit non-certification record" in wsl
