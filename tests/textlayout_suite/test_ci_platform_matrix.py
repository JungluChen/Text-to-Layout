"""CI platform-support contract tests."""

from __future__ import annotations

import json
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
    macos_json = json.loads(
        (ROOT / "out" / "platform" / "macos_arm64.json").read_text(encoding="utf-8")
    )
    wsl_json = json.loads(
        (ROOT / "out" / "platform" / "wsl2_ubuntu.json").read_text(encoding="utf-8")
    )

    assert "GENERATED_CURRENT_STATUS: scripts/platform/verify_platform.py" in macos
    assert macos_json["support_state"] in {"CORE_TESTED", "CORE_CERTIFIED"}
    assert f"**Support state:** `{macos_json['support_state']}`" in macos
    assert macos_json["real_execution"] is True
    assert isinstance(macos_json["core_pass"], bool)
    assert "GENERATED_CURRENT_STATUS: scripts/platform/verify_platform.py" in wsl
    assert wsl_json["support_state"] == "UNTESTED"
    assert wsl_json["real_execution"] is False
    assert "explicit non-certification record" in wsl


def test_wsl_certification_requires_a_real_self_hosted_wsl2_runner() -> None:
    workflow = yaml.safe_load(
        (ROOT / ".github" / "workflows" / "wsl2-certification.yml").read_text()
    )
    job = workflow["jobs"]["certify"]
    assert job["runs-on"] == ["self-hosted", "Windows", "X64", "wsl2"]
    commands = "\n".join(str(step.get("run", "")) for step in job["steps"])
    assert "cat /proc/version" in commands
    assert "lsb_release -a" in commands
    assert "scripts/platform/verify_wsl.sh" in commands
    assert "ubuntu-latest" not in str(job)
