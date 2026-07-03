"""Phase 9 category 8 — README claim validation.

The validator must pass on the honest README as committed, and *fail* when a
false claim is injected. The doctored-copy tests are the permanent version of
the Phase 8 'add a false claim in a scratch branch' proof.
"""

from __future__ import annotations

import re
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


def test_stale_no_verified_benchmark_claim_fails_validation(tmp_path: Path) -> None:
    fake = tmp_path / "README.md"
    fake.write_text(
        README.read_text(encoding="utf-8")
        + "\nNo benchmark in this repository is currently PHYSICS VERIFIED.\n",
        encoding="utf-8",
    )
    errors = validate(fake)
    assert any("stale release claim" in e for e in errors), errors


def test_showcase_absolute_path_fails_validation(tmp_path: Path) -> None:
    artifact = ROOT / "examples/showcase/06_research_test_chip/path-regression.json"
    artifact.write_text('{"path":"C:\\\\Users\\\\example\\\\artifact"}\n', encoding="utf-8")
    try:
        errors = validate(README)
    finally:
        artifact.unlink(missing_ok=True)
    assert any("absolute user path" in e for e in errors), errors


def test_showcase_number_mismatch_fails_validation(tmp_path: Path) -> None:
    fake = _doctored(tmp_path, "0.598641 pF", "0.599999 pF")
    errors = validate(fake)
    assert any("does not match simulation.json" in e for e in errors), errors


def test_showcase_row_without_fabrication_status_fails_validation(tmp_path: Path) -> None:
    fake = _doctored(
        tmp_path,
        "no full-tile EM solve. **NOT_FABRICATION_READY** |",
        "no full-tile EM solve. |",
    )
    errors = validate(fake)
    assert any("showcase row must state NOT_FABRICATION_READY" in e for e in errors), errors


def test_fast_henry_number_mismatch_fails_validation(tmp_path: Path) -> None:
    fake = _doctored(tmp_path, "2.751264 nH", "2.900000 nH")
    errors = validate(fake)
    assert any("04_spiral_inductor_3nh" in e and "does not match" in e for e in errors), errors


def test_full_tile_solver_overclaim_fails_validation(tmp_path: Path) -> None:
    fake = _doctored(
        tmp_path,
        "ANALYTICAL_ONLY for the full tile",
        "PHYSICS_VERIFIED FOR THE FULL TILE",
    )
    errors = validate(fake)
    assert any("full tile-level solve" in e for e in errors), errors


def test_committed_repo_has_no_local_absolute_paths() -> None:
    errors = validate(README)
    assert not any("local absolute machine path" in e for e in errors), errors


def test_new_absolute_path_leak_in_json_fails_validation(tmp_path: Path) -> None:
    leaky = ROOT / "docs" / "path-leak-regression.json"
    leaky.write_text('{"path": "C:\\\\Users\\\\realuser\\\\Desktop\\\\artifact"}\n', encoding="utf-8")
    try:
        errors = validate(README)
    finally:
        leaky.unlink(missing_ok=True)
    assert any(
        "local absolute machine path" in e and "path-leak-regression.json" in e for e in errors
    ), errors


def test_placeholder_path_in_docs_does_not_fail_validation(tmp_path: Path) -> None:
    placeholder = ROOT / "docs" / "path-placeholder-regression.md"
    placeholder.write_text("cd /mnt/c/Users/<you>/Desktop/Layout/text-to-gds\n", encoding="utf-8")
    try:
        errors = validate(README)
    finally:
        placeholder.unlink(missing_ok=True)
    assert not any("path-placeholder-regression.md" in e for e in errors), errors


def test_inductance_report_with_capacitance_language_fails_validation(tmp_path: Path) -> None:
    report = ROOT / "examples/showcase/04_spiral_inductor_3nh/report.md"
    original = report.read_text(encoding="utf-8")
    assert "Analytical inductance" in original
    try:
        report.write_text(
            original.replace("Analytical inductance", "Analytical capacitance"),
            encoding="utf-8",
        )
        errors = validate(README)
    finally:
        report.write_text(original, encoding="utf-8")
    assert any(
        "04_spiral_inductor_3nh" in e and "capacitance/pF language" in e for e in errors
    ), errors


def test_tile_map_without_report_summary_fails_validation(tmp_path: Path) -> None:
    report = ROOT / "examples/showcase/06_research_test_chip/report.md"
    readme = ROOT / "examples/showcase/06_research_test_chip/README.md"
    original_report = report.read_text(encoding="utf-8")
    original_readme = readme.read_text(encoding="utf-8")
    try:
        stripped = re.sub(
            r"\n## Tile sub-block evidence.*?(?=\n## Limitations)",
            "\n",
            original_report,
            flags=re.DOTALL,
        )
        report.write_text(stripped, encoding="utf-8")
        stripped_readme = re.sub(
            r"\n## Tile sub-block evidence.*?(?=\n## Limitation)",
            "\n",
            original_readme,
            flags=re.DOTALL,
        )
        readme.write_text(stripped_readme, encoding="utf-8")
        errors = validate(README)
    finally:
        report.write_text(original_report, encoding="utf-8")
        readme.write_text(original_readme, encoding="utf-8")
    assert any(
        "06_research_test_chip" in e and "full-tile status" in e for e in errors
    ), errors


def test_collapsed_showcase_table_row_fails_validation(tmp_path: Path) -> None:
    text = README.read_text(encoding="utf-8")
    section = re.search(r"## Six research-grade examples\s*\n(.*?)(?:\n## |\Z)", text, re.DOTALL)
    assert section is not None
    rows = [
        line
        for line in section.group(1).splitlines()
        if line.strip().startswith("|") and "examples/showcase/" in line
    ]
    assert len(rows) >= 2
    collapsed = rows[0] + rows[1]
    fake = _doctored(tmp_path, rows[0] + "\n" + rows[1], collapsed)
    errors = validate(fake)
    assert any("collapsed onto a single Markdown line" in e for e in errors), errors
