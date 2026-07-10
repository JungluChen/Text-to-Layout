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
    record = QuantityEvidence(status=EvidenceStatus.PHYSICS_VERIFIED, **_solver_kwargs(str(real)))
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


def test_50_ohm_target_with_30_ohm_result_is_never_physics_verified(tmp_path: Path) -> None:
    """Regression: a CPW that badly misses its impedance target must not pass.

    This is the exact failure mode of the real showcase 02 run (openEMS
    extracted ~30.9 ohm against a 50 ohm target): the solver executed and the
    evidence is real, but the design missed -- the status must stay
    SIMULATION_EXECUTED, never PHYSICS_VERIFIED.
    """
    out = tmp_path / "cpw.s2p"
    out.write_text("# GHz S RI R 50", encoding="utf-8")
    record = compare_extracted_to_target(
        quantity="characteristic_impedance",
        target_value=50.0,
        target_unit="ohm",
        extracted_value=30.0,
        extracted_unit="ohm",
        tolerance_percent=5.0,
        solver="openEMS+scikit-rf",
        command="octave-cli openems_model.m",
        input_files=["openems_model.m"],
        output_files=[str(out)],
        parser="textlayout.simulation.runners.extract_z0_from_touchstone",
    )
    assert record.status is EvidenceStatus.SIMULATION_EXECUTED
    assert record.status is not EvidenceStatus.PHYSICS_VERIFIED
    assert "NOT physics verified" in record.summary_line()


# --- Non-finite solver output ------------------------------------------------
#
# NaN compares False against every bound, so an unguarded
# `error_percent > tolerance_percent` check *admits* NaN as PHYSICS_VERIFIED.
# These tests pin the structural rejection that closes that hole.


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf")])
def test_physics_verified_rejects_non_finite_extracted_value(tmp_path: Path, bad: float) -> None:
    out = tmp_path / "cap.txt"
    out.write_text("capacitance", encoding="utf-8")
    kwargs = _solver_kwargs(str(out))
    kwargs["extracted_value"] = bad
    kwargs["error_percent"] = bad
    with pytest.raises(ValidationError, match="must be a finite number"):
        QuantityEvidence(status=EvidenceStatus.PHYSICS_VERIFIED, **kwargs)


@pytest.mark.parametrize("field", ["target_value", "analytical_value", "tolerance_percent"])
def test_no_numeric_field_may_be_non_finite(tmp_path: Path, field: str) -> None:
    """Every numeric field rejects NaN.

    `tolerance_percent` is caught earlier by its own `gt=0` constraint (NaN is
    not > 0), hence the alternation -- what matters is that nothing gets through.
    """
    out = tmp_path / "cap.txt"
    out.write_text("capacitance", encoding="utf-8")
    kwargs = _solver_kwargs(str(out))
    kwargs[field] = float("nan")
    with pytest.raises(ValidationError, match="must be a finite number|greater than 0"):
        QuantityEvidence(status=EvidenceStatus.SIMULATION_EXECUTED, **kwargs)


@pytest.mark.parametrize("bad", [float("nan"), float("inf")])
def test_compare_classifies_non_finite_output_as_simulation_invalid(
    tmp_path: Path, bad: float
) -> None:
    """A solver emitting NaN/inf ran, but extracted nothing."""
    out = tmp_path / "cap.txt"
    out.write_text("garbage", encoding="utf-8")
    evidence = compare_extracted_to_target(
        quantity="capacitance",
        target_value=0.6,
        target_unit="pF",
        extracted_value=bad,
        extracted_unit="pF",
        tolerance_percent=5.0,
        solver="FasterCap",
        command="FasterCap idc.lst",
        input_files=["idc.lst"],
        output_files=[str(out)],
        parser="p.parse",
    )
    assert evidence.status is EvidenceStatus.SIMULATION_INVALID
    assert evidence.is_physics_verified is False
    # the rejected token is preserved for diagnosis, but never in a numeric field
    assert evidence.extracted_value is None
    assert any("non-finite" in note for note in evidence.notes)
    assert "SIMULATION_INVALID" in evidence.summary_line()


def test_rejected_statuses_require_a_solver_and_carry_no_value(tmp_path: Path) -> None:
    for status in (EvidenceStatus.SIMULATION_INVALID, EvidenceStatus.CONVERGENCE_FAILED):
        with pytest.raises(ValidationError, match="requires a named solver"):
            QuantityEvidence(quantity="q", status=status)
        with pytest.raises(ValidationError, match="must not carry an extracted value"):
            QuantityEvidence(
                quantity="q", status=status, solver="Palace", extracted_value=1.0
            )
        # the honest form is constructible
        record = QuantityEvidence(quantity="q", status=status, solver="Palace")
        assert record.is_physics_verified is False
