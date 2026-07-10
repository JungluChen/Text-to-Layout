"""The mesh-convergence ladder: what a refinement study is allowed to claim.

A single solve produces a number. Only a refinement study can show the number
belongs to the device rather than to the discretisation, so nothing here may
reach SIMULATION_EXECUTED or PHYSICS_VERIFIED without one.
"""

from __future__ import annotations

import math
from pathlib import Path

import pytest

from textlayout.evidence import ConfidenceClass, EvidenceStatus
from textlayout.simulation.mesh_convergence import (
    MeshLevel,
    SolverIdentity,
    assess_convergence,
    mesh_convergence_evidence,
    sanity_checks,
)

DESIGN_HASH = "d" * 64
PALACE = SolverIdentity(
    name="Palace",
    version="0.13.0",
    container_digest="sha256:" + "c" * 64,
    command=["palace", "palace.json"],
)


@pytest.fixture
def outputs(tmp_path: Path) -> list[Path]:
    paths = []
    for index in range(3):
        path = tmp_path / f"level{index}.csv"
        path.write_text("m, f_GHz\n1, 6.0\n", encoding="utf-8")
        paths.append(path)
    return paths


def _levels(
    frequencies: list[float | None],
    outputs: list[Path] | None = None,
    lengths: list[float] | None = None,
) -> list[MeshLevel]:
    lengths = lengths or [20.0, 10.0, 5.0][: len(frequencies)]
    return [
        MeshLevel(
            characteristic_length_um=length,
            frequency_ghz=frequency,
            output_file=outputs[index] if outputs else None,
            runtime_seconds=12.0,
        )
        for index, (length, frequency) in enumerate(zip(lengths, frequencies))
    ]


def _evidence(levels: list[MeshLevel], tmp_path: Path, **overrides: object):
    kwargs: dict[str, object] = {
        "design_id": "05_quarter_wave_resonator_6ghz",
        "design_hash": DESIGN_HASH,
        "component": "quarter_wave_resonator",
        "analysis_scope": "resonator_eigenmode",
        "levels": levels,
        "solver": PALACE,
        "threshold_percent": 1.0,
        "output_root": tmp_path,
        "timestamp": "2026-07-10T00:00:00+00:00",
    }
    kwargs.update(overrides)
    return mesh_convergence_evidence(**kwargs)  # type: ignore[arg-type]


class TestSanityChecks:
    """Structural checks pass on garbage; physical assertions are what catch it."""

    def test_every_check_is_reported_even_when_passing(self, outputs) -> None:
        checks = sanity_checks(_levels([6.0, 6.01, 6.011], outputs))
        names = {check.name for check in checks}
        assert {"every_level_produced_a_frequency", "frequencies_finite",
                "frequencies_positive", "mesh_is_strictly_refined"} <= names
        assert all(check.passed for check in checks)

    def test_a_nan_frequency_is_caught(self, outputs) -> None:
        checks = sanity_checks(_levels([6.0, 6.01, math.nan], outputs))
        failed = {c.name for c in checks if not c.passed}
        assert "frequencies_finite" in failed

    def test_a_missing_frequency_is_caught(self, outputs) -> None:
        checks = sanity_checks(_levels([6.0, None, 6.01], outputs))
        failed = {c.name for c in checks if not c.passed}
        assert "every_level_produced_a_frequency" in failed

    def test_a_negative_frequency_is_caught(self, outputs) -> None:
        checks = sanity_checks(_levels([6.0, 6.01, -6.0], outputs))
        assert "frequencies_positive" in {c.name for c in checks if not c.passed}

    def test_an_unrefined_mesh_sequence_is_caught(self, outputs) -> None:
        """Identical lc at every level makes convergence a tautology."""
        levels = _levels([6.0, 6.0, 6.0], outputs, lengths=[10.0, 10.0, 10.0])
        assert "mesh_is_strictly_refined" in {c.name for c in sanity_checks(levels) if not c.passed}

    def test_an_eigenvalue_pinned_to_the_search_window_is_caught(self, outputs) -> None:
        """The solver echoing its own target back is not a resonance it found."""
        levels = _levels([6.0, 6.0, 6.0], outputs)
        checks = sanity_checks(levels, eigen_window_ghz=(6.0, 12.0))
        assert "resonance_not_at_search_window_edge" in {c.name for c in checks if not c.passed}

    def test_an_interior_resonance_is_accepted(self, outputs) -> None:
        levels = _levels([7.9, 8.0, 8.01], outputs)
        checks = sanity_checks(levels, eigen_window_ghz=(6.0, 12.0))
        assert all(check.passed for check in checks)

    def test_unnormalised_field_energy_is_caught(self, tmp_path: Path) -> None:
        levels = [
            MeshLevel(characteristic_length_um=lc, frequency_ghz=6.0, energy_normalization=energy)
            for lc, energy in ((20.0, 1.0), (10.0, 1.0), (5.0, 0.42))
        ]
        assert "field_energy_normalised" in {c.name for c in sanity_checks(levels) if not c.passed}


class TestConvergenceAssessment:
    def test_delta_is_measured_across_the_two_finest_levels(self) -> None:
        metrics = assess_convergence(_levels([6.5, 6.05, 6.0]), threshold_percent=1.0)
        assert metrics.delta_percent == pytest.approx(abs(6.0 - 6.05) / 6.0 * 100)
        assert metrics.converged is True

    def test_a_moving_frequency_does_not_converge(self) -> None:
        metrics = assess_convergence(_levels([7.0, 6.5, 6.0]), threshold_percent=1.0)
        assert metrics.converged is False
        assert metrics.delta_percent is not None and metrics.delta_percent > 1.0

    def test_two_levels_cannot_evidence_convergence(self) -> None:
        metrics = assess_convergence(_levels([6.01, 6.0]), threshold_percent=1.0)
        assert metrics.converged is False
        assert "3 are required" in " ".join(metrics.notes)

    def test_the_declared_threshold_is_recorded(self) -> None:
        metrics = assess_convergence(_levels([6.5, 6.05, 6.0]), threshold_percent=0.25)
        assert metrics.threshold_percent == 0.25
        assert metrics.converged is False  # 0.83% > 0.25%

    def test_an_empty_study_is_a_programming_error(self) -> None:
        with pytest.raises(ValueError, match="at least one mesh level"):
            assess_convergence([], threshold_percent=1.0)

    def test_a_non_positive_threshold_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="must be positive"):
            assess_convergence(_levels([6.0]), threshold_percent=0.0)


class TestEvidenceLadder:
    def test_absent_solver_skips_honestly(self, tmp_path: Path) -> None:
        record = _evidence([], tmp_path, solver=None, solver_absent_reason="Palace not on PATH")
        assert record.status is EvidenceStatus.SKIPPED_SOLVER_ABSENT
        assert record.extracted_value is None
        assert record.skip_reason == "Palace not on PATH"
        assert record.confidence_class is ConfidenceClass.NONE

    def test_a_failed_sanity_check_yields_simulation_invalid_and_no_value(
        self, tmp_path: Path, outputs
    ) -> None:
        record = _evidence(_levels([6.0, 6.01, math.nan], outputs), tmp_path)
        assert record.status is EvidenceStatus.SIMULATION_INVALID
        assert record.extracted_value is None
        assert "frequencies_finite" in (record.invalidation_reason or "")

    def test_an_unconverged_study_withdraws_its_number(self, tmp_path: Path, outputs) -> None:
        """The un-converged frequency is audit history, never an active claim."""
        record = _evidence(_levels([7.0, 6.5, 6.0], outputs), tmp_path)
        assert record.status is EvidenceStatus.CONVERGENCE_FAILED
        assert record.extracted_value is None
        assert record.superseded is not None
        assert record.superseded.extracted_value == 6.0
        assert record.convergence is not None and record.convergence.converged is False

    def test_two_levels_cannot_reach_simulation_executed(self, tmp_path: Path, outputs) -> None:
        record = _evidence(_levels([6.01, 6.0], outputs[:2]), tmp_path)
        assert record.status is EvidenceStatus.CONVERGENCE_FAILED

    def test_converged_without_a_target_is_simulation_executed(
        self, tmp_path: Path, outputs
    ) -> None:
        record = _evidence(_levels([6.5, 6.05, 6.0], outputs), tmp_path)
        assert record.status is EvidenceStatus.SIMULATION_EXECUTED
        assert record.extracted_value == 6.0
        assert record.confidence_class is ConfidenceClass.SIMULATED

    def test_converged_and_on_target_is_physics_verified(self, tmp_path: Path, outputs) -> None:
        record = _evidence(
            _levels([6.5, 6.05, 6.0], outputs), tmp_path, target_frequency_ghz=6.0
        )
        assert record.status is EvidenceStatus.PHYSICS_VERIFIED
        assert record.error_percent == pytest.approx(0.0)
        assert record.confidence_class is ConfidenceClass.VERIFIED

    def test_converged_but_off_target_stays_simulation_executed(
        self, tmp_path: Path, outputs
    ) -> None:
        """Convergence is not agreement: a well-resolved wrong answer is not verified."""
        record = _evidence(
            _levels([6.5, 6.05, 6.0], outputs), tmp_path,
            target_frequency_ghz=5.0, tolerance_percent=2.0,
        )
        assert record.status is EvidenceStatus.SIMULATION_EXECUTED
        assert record.error_percent == pytest.approx(20.0)

    def test_a_solver_backed_study_needs_at_least_one_level(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="at least one mesh level"):
            _evidence([], tmp_path)


class TestProvenance:
    def test_output_files_are_recorded_by_content_hash(self, tmp_path: Path, outputs) -> None:
        record = _evidence(_levels([6.5, 6.05, 6.0], outputs), tmp_path)
        assert len(record.output_file_hashes) == 3
        assert record.verify_output_hashes(tmp_path) == []

    def test_an_edited_output_is_detected(self, tmp_path: Path, outputs) -> None:
        record = _evidence(_levels([6.5, 6.05, 6.0], outputs), tmp_path)
        outputs[-1].write_text("m, f_GHz\n1, 9.9\n", encoding="utf-8")
        problems = record.verify_output_hashes(tmp_path)
        assert problems and "output changed after evidence was written" in problems[0]

    def test_a_container_digest_satisfies_reproducible_identity(
        self, tmp_path: Path, outputs
    ) -> None:
        record = _evidence(_levels([6.5, 6.05, 6.0], outputs), tmp_path)
        assert record.provenance_gaps == []
        assert record.container_digest is not None

    def test_an_unidentified_binary_must_declare_the_gap(self, tmp_path: Path, outputs) -> None:
        solver = SolverIdentity(name="Palace", version="0.13.0")
        assert solver.is_reproducible is False
        record = _evidence(_levels([6.5, 6.05, 6.0], outputs), tmp_path, solver=solver)
        assert record.provenance_gaps == ["solver_executable_hash_unrecorded"]

    def test_the_extraction_config_is_hashed(self, tmp_path: Path, outputs) -> None:
        """Two runs of one parser can disagree under a different threshold."""
        loose = _evidence(_levels([6.5, 6.05, 6.0], outputs), tmp_path, threshold_percent=1.0)
        strict = _evidence(_levels([6.5, 6.05, 6.0], outputs), tmp_path, threshold_percent=0.1)
        assert loose.extraction_config_hash != strict.extraction_config_hash
        assert loose.evidence_id != strict.evidence_id

    def test_the_evidence_id_is_deterministic(self, tmp_path: Path, outputs) -> None:
        first = _evidence(_levels([6.5, 6.05, 6.0], outputs), tmp_path)
        second = _evidence(_levels([6.5, 6.05, 6.0], outputs), tmp_path)
        assert first.evidence_id == second.evidence_id
