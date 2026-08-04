"""Status documents declare a single current-evidence authority."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _text(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_manual_and_historical_documents_are_explicitly_classified() -> None:
    expected = {
        "README.md": "MANUAL_DOCUMENTATION",
        "AGENTS.md": "MANUAL_DOCUMENTATION",
        "CLAUDE.md": "MANUAL_DOCUMENTATION",
        "SIGNOFF_CRITERIA.md": "MANUAL_DOCUMENTATION",
        "SOLVER_EVIDENCE_CONTRACT.md": "MANUAL_DOCUMENTATION",
        "CURRENT_STATUS.md": "LEGACY_SCOPE",
        "CLEAN_ROOM_VERIFICATION.md": "HISTORICAL_RECORD",
        "PHYSICS_VALIDATION_REPORT.md": "HISTORICAL_RECORD",
    }
    for relative, classification in expected.items():
        assert f"Document class: {classification}" in _text(relative), relative


def test_generated_status_documents_identify_their_renderer() -> None:
    assert "GENERATED_CURRENT_STATUS: scripts/generate_project_status.py" in _text(
        "PROJECT_STATUS.md"
    )
    assert "GENERATED_CURRENT_STATUS: scripts/platform/verify_platform.py" in _text(
        "docs/platforms/macos_arm64.md"
    )
    assert "GENERATED_CURRENT_STATUS: scripts/platform/verify_platform.py" in _text(
        "docs/platforms/wsl2_ubuntu.md"
    )


def test_authority_map_names_every_status_class() -> None:
    authority = _text("docs/status_documentation.md")
    for classification in (
        "GENERATED_CURRENT_STATUS",
        "HISTORICAL_RECORD",
        "LEGACY_SCOPE",
        "MANUAL_DOCUMENTATION",
    ):
        assert classification in authority
