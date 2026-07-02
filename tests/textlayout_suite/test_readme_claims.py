"""Phase 9 category 8 — README claim validation.

The validator must pass on the honest README as committed, and *fail* when a
false claim is injected. The doctored-copy tests are the permanent version of
the Phase 8 'add a false claim in a scratch branch' proof.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from validate_readme_claims import validate  # noqa: E402

README = ROOT / "README.md"


def test_committed_readme_has_no_unsupported_claims() -> None:
    errors = validate(README)
    assert errors == [], "README makes claims the repo cannot back:\n" + "\n".join(errors)


def _doctored(tmp_path: Path, old: str, new: str) -> Path:
    text = README.read_text(encoding="utf-8")
    assert old in text, f"fixture assumption broken: {old!r} not in README"
    fake = tmp_path / "README.md"
    fake.write_text(text.replace(old, new), encoding="utf-8")
    return fake


def test_false_solver_executed_claim_fails_validation(tmp_path: Path) -> None:
    fake = _doctored(
        tmp_path,
        "| IDC | yes | yes (Bahl/Alley) | yes (FasterCap/FastCap) | environment-dependent"
        " (runs when installed; honest skip otherwise) |",
        "| IDC | yes | yes (Bahl/Alley) | yes (FasterCap/FastCap) | yes |",
    )
    errors = validate(fake)
    assert any("Solver executed=yes" in e and "IDC" in e for e in errors), errors


def test_false_physics_verified_benchmark_claim_fails_validation(tmp_path: Path) -> None:
    fake = _doctored(
        tmp_path,
        "**SIMULATION INPUT PREPARED** (FasterCap/FastCap input exists; solver not executed)",
        "**PHYSICS VERIFIED** (extracted 0.6 pF)",
    )
    errors = validate(fake)
    assert any("claims solver execution" in e for e in errors), errors


def test_removed_limitation_statement_fails_validation(tmp_path: Path) -> None:
    fake = _doctored(
        tmp_path,
        "This project is not fabrication-ready by default.",
        "This project is ready to use.",
    )
    errors = validate(fake)
    assert any("limitation statement" in e for e in errors), errors
