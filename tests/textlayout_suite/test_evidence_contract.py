"""Phase 2 — the evidence contract makes false physics claims impossible.

Category (Phase 9): evidence-schema enforcement, solver-absent honesty.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from textlayout.evidence import (
    EvidenceStatus,
    QuantityEvidence,
    compare_extracted_to_target,
)


def _solver_kwargs(output_file: str) -> dict[str, object]:
    return {
        "quantity": "capacitance",
        "target_value": 0.6,
        "target_unit": "pF",
        "extracted_value": 0.598,
        "extracted_unit": "pF",
        "error_percent": 0.33,
        "tolerance_percent": 5.0,
        "solver": "FasterCap",
        "command": "FasterCap -b -a0.01 idc.lst",
        "input_files": ["idc.lst", "idc.qui"],
        "output_files": [output_file],
        "parser": "textlayout.simulation.fastercap._parse_capacitance_matrix_pf",
    }


def test_physics_verified_requires_existing_solver_output(tmp_path: Path) -> None:
    """PHYSICS_VERIFIED cannot be constructed when the output file is absent."""
    missing = tmp_path / "does_not_exist.txt"
    with pytest.raises(ValidationError, match="existing, non-empty solver output"):
        QuantityEvidence(status=EvidenceStatus.PHYSICS_VERIFIED, **_solver_kwargs(str(missing)))


def test_physics_verified_rejects_empty_output_file(tmp_path: Path) -> None:
    empty = tmp_path / "solver.stdout.txt"
    empty.write_text("", encoding="utf-8")
    with pytest.raises(ValidationError, match="existing, non-empty solver output"):
        QuantityEvidence(status=EvidenceStatus.PHYSICS_VERIFIED, **_solver_kwargs(str(empty)))


def test_physics_verified_rejects_missing_solver_or_parser(tmp_path: Path) -> None:
    real = tmp_path / "solver.stdout.txt"
    real.write_text("CAPACITANCE MATRIX, picofarads\n", encoding="utf-8")
    kwargs = _solver_kwargs(str(real))
    kwargs["solver"] = None
    with pytest.raises(ValidationError, match="requires a named solver"):
        QuantityEvidence(status=EvidenceStatus.PHYSICS_VERIFIED, **kwargs)
    kwargs = _solver_kwargs(str(real))
    kwargs["parser"] = None
    with pytest.raises(ValidationError, match="requires a named output parser"):
        QuantityEvidence(status=EvidenceStatus.PHYSICS_VERIFIED, **kwargs)


def test_physics_verified_rejects_out_of_tolerance(tmp_path: Path) -> None:
    real = tmp_path / "solver.stdout.txt"
    real.write_text("output", encoding="utf-8")
    kwargs = _solver_kwargs(str(real))
    kwargs["error_percent"] = 12.5
    with pytest.raises(ValidationError, match="error <= tolerance"):
        QuantityEvidence(status=EvidenceStatus.PHYSICS_VERIFIED, **kwargs)


def test_physics_verified_accepts_real_evidence(tmp_path: Path) -> None:
    real = tmp_path / "solver.stdout.txt"
    real.write_text("CAPACITANCE MATRIX, picofarads\n1 P1 0.9 -0.598\n", encoding="utf-8")
    record = QuantityEvidence(
        status=EvidenceStatus.PHYSICS_VERIFIED, **_solver_kwargs(str(real))
    )
    assert record.is_physics_verified
    assert "PHYSICS_VERIFIED" in record.summary_line()


def test_analytical_only_cannot_claim_solver() -> None:
    with pytest.raises(ValidationError, match="must not claim a solver"):
        QuantityEvidence(
            quantity="capacitance",
            analytical_value=0.63,
            analytical_model="Bahl 2003",
            status=EvidenceStatus.ANALYTICAL_ONLY,
            solver="FasterCap",
        )


def test_skipped_and_prepared_cannot_carry_extracted_values() -> None:
    for status in (
        EvidenceStatus.SKIPPED_SOLVER_ABSENT,
        EvidenceStatus.SIMULATION_INPUT_PREPARED,
    ):
        with pytest.raises(ValidationError, match="must not carry an extracted value"):
            QuantityEvidence(quantity="capacitance", status=status, extracted_value=0.6)


def test_compare_computes_status_never_takes_it(tmp_path: Path) -> None:
    """The comparison helper derives the status from the numbers alone."""
    out = tmp_path / "solver.stdout.txt"
    out.write_text("matrix", encoding="utf-8")
    common = {
        "quantity": "capacitance",
        "target_value": 0.6,
        "target_unit": "pF",
        "extracted_unit": "pF",
        "tolerance_percent": 5.0,
        "solver": "FasterCap",
        "command": "FasterCap -b idc.lst",
        "input_files": ["idc.lst"],
        "output_files": [str(out)],
        "parser": "textlayout.simulation.fastercap._parse_capacitance_matrix_pf",
    }
    good = compare_extracted_to_target(extracted_value=0.598, **common)
    assert good.status is EvidenceStatus.PHYSICS_VERIFIED
    bad = compare_extracted_to_target(extracted_value=0.75, **common)
    assert bad.status is EvidenceStatus.SIMULATION_EXECUTED
    assert "NOT physics verified" in bad.summary_line()
