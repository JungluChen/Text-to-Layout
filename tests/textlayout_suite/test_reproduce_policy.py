"""The repository's reproduce-before-edit policy is a permanent QA contract."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
POLICY_PATH = "docs/development/reproduce_before_edit.md"
SEQUENCE = (
    "REPRODUCE → RERUN UNCHANGED → DIAGNOSE → EDIT → "
    "RERUN ORIGINAL COMMAND → RERUN AGAIN → REGRESSION"
)


def test_agent_instruction_files_mandate_the_canonical_policy() -> None:
    for filename in ("AGENTS.md", "CLAUDE.md"):
        text = (ROOT / filename).read_text(encoding="utf-8")
        assert POLICY_PATH in text
        assert SEQUENCE in text
        assert "mandatory, not advisory" in text


def test_canonical_policy_preserves_diagnostic_and_evidence_contract() -> None:
    text = (ROOT / POLICY_PATH).read_text(encoding="utf-8")
    for required in (
        "RERUN UNCHANGED",
        "STOP EDITING",
        "RERUN ORIGINAL COMMAND",
        "RERUN AGAIN",
        "REGRESSION",
        "complete stdout/stderr",
        "solver identity/version/path/SHA-256",
        "input hashes",
        "output hashes",
        "A single failure is not proof of a defect",
    ):
        assert required in text
