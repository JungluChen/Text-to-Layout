"""The committed Palace benchmark evidence still describes its committed outputs.

This is a real Palace 0.16 run, retained as compact CSVs plus content hashes. The
evidence is a *projection* of those outputs: re-parsing them must reproduce it
exactly, or one of the two has drifted.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from textlayout.evidence import ConfidenceClass, EvidenceStatus
from textlayout.evidence.canonical import load_canonical

REPO_ROOT = Path(__file__).resolve().parents[2]
BENCH = REPO_ROOT / "examples" / "solver_benchmarks" / "palace_cavity_te101"
EVIDENCE = BENCH / "evidence"
CPW = REPO_ROOT / "examples" / "solver_benchmarks" / "palace_cpw_quarter_wave"

pytestmark = pytest.mark.skipif(
    not (EVIDENCE / "frequency_canonical.json").is_file(),
    reason="Palace benchmark artifacts are not present in this checkout",
)


@pytest.fixture(scope="module")
def frequency():
    return load_canonical(EVIDENCE / "frequency_canonical.json")


@pytest.fixture(scope="module")
def participation():
    return load_canonical(EVIDENCE / "participation_canonical.json")


class TestEvidenceIsCurrent:
    def test_regenerating_from_the_committed_outputs_reproduces_the_records(self) -> None:
        completed = subprocess.run(
            [sys.executable, str(REPO_ROOT / "scripts" / "build_palace_benchmark_evidence.py"), "--check"],
            cwd=REPO_ROOT, capture_output=True, text=True, check=False,
        )
        assert completed.returncode == 0, completed.stderr

    def test_every_referenced_output_hash_still_matches(self, frequency, participation) -> None:
        for record in (frequency, participation):
            assert record.verify_output_hashes(BENCH) == []


class TestFrequencyIsGenuinelyVerified:
    def test_a_real_solver_backs_the_claim(self, frequency) -> None:
        assert frequency.solver_name == "Palace"
        assert frequency.solver_version == "0.16.0-34-gea2e7b23"
        assert frequency.container_digest is not None
        # A container digest is a reproducible identity, so no gap is declared.
        assert frequency.provenance_gaps == []

    def test_it_reaches_physics_verified(self, frequency) -> None:
        assert frequency.status is EvidenceStatus.PHYSICS_VERIFIED
        assert frequency.confidence_class is ConfidenceClass.VERIFIED

    def test_the_target_is_a_closed_form_not_a_reference_run(self, frequency) -> None:
        assert frequency.target_value == 6.0
        assert "TE101" in (frequency.analytical_model or "")
        assert abs(frequency.error_percent) < frequency.tolerance_percent

    def test_convergence_used_at_least_three_levels(self, frequency) -> None:
        assert frequency.convergence is not None
        assert frequency.convergence.refinement_levels >= 3
        assert frequency.convergence.converged is True

    def test_element_count_and_dof_growth_are_recorded_checks(self, frequency) -> None:
        names = {check.name for check in frequency.sanity_checks}
        assert "element_count_increases_under_refinement" in names
        assert "degrees_of_freedom_increase_under_refinement" in names
        assert all(check.passed for check in frequency.sanity_checks)

    def test_the_gci_lives_in_convergence_not_in_sanity_checks(self, frequency) -> None:
        """A failed convergence criterion is not a failed sanity check.

        A sanity check says the output is not a physical field, and vetoes every
        solver-backed status. A convergence criterion says the answer is still
        moving -- the output is perfectly physical, just not yet trustworthy.
        """
        assert frequency.convergence is not None
        notes = " ".join(frequency.convergence.notes)
        assert "GCI" in notes and "below the 1% requirement" in notes
        assert not any(c.name.startswith("grid_convergence") for c in frequency.sanity_checks)

    def test_the_domain_size_limitation_is_stated_not_hidden(self, frequency) -> None:
        assert any("domain-size convergence is undefined" in w for w in frequency.warnings)

    def test_the_oom_killed_level_is_recorded_in_the_manifest(self) -> None:
        manifest = json.loads((BENCH / "mesh_manifest.json").read_text(encoding="utf-8"))
        killed = [lv for lv in manifest["levels"]["single_domain"] if not lv["completed"]]
        assert len(killed) == 1
        assert killed[0]["divisions"] == 48
        assert "OOM" in killed[0]["failure"]


class TestParticipationIsNotOverClaimed:
    def test_it_stops_at_simulation_executed(self, participation) -> None:
        """The eigenfrequency on this mesh oscillates; the participation cannot outrank it."""
        assert participation.status is EvidenceStatus.SIMULATION_EXECUTED
        assert participation.confidence_class is ConfidenceClass.SIMULATED

    def test_the_reason_it_is_not_verified_is_written_down(self, participation) -> None:
        assert any("oscillatory" in w for w in participation.warnings)

    def test_the_mode_was_tracked_by_field_overlap(self, participation) -> None:
        tracking = next(
            c for c in participation.sanity_checks if c.name == "modes_unambiguously_tracked"
        )
        assert tracking.passed
        overlap = next(
            c for c in participation.sanity_checks if c.name == "field_overlap_match_score_above_0p90"
        )
        assert overlap.passed

    def test_it_agrees_with_the_closed_form_within_tolerance(self, participation) -> None:
        assert abs(participation.error_percent) < 5.0
        assert participation.analytical_model is not None


@pytest.fixture(scope="module")
def cpw():
    return load_canonical(CPW / "evidence" / "frequency_canonical.json")


class TestTheCpwResonatorIsExecutedNotVerified:
    """A real Palace run on a real cQED device, and an honest refusal to verify it."""

    def test_a_real_solver_and_container_back_the_claim(self, cpw) -> None:
        assert cpw.solver_name == "Palace"
        assert cpw.container_digest is not None
        assert cpw.provenance_gaps == []

    def test_it_stops_at_simulation_executed(self, cpw) -> None:
        assert cpw.status is EvidenceStatus.SIMULATION_EXECUTED
        assert cpw.confidence_class is ConfidenceClass.SIMULATED
        assert cpw.convergence is not None and cpw.convergence.converged is False

    def test_the_observed_order_does_not_match_the_formal_order(self, cpw) -> None:
        """Non-nested meshes plus an edge singularity: no single power law."""
        assert any("observed convergence order" in w for w in cpw.warnings)
        assert any("Richardson extrapolation is withheld" in w for w in cpw.warnings)

    def test_the_target_is_declared_a_model_not_a_closed_form(self, cpw) -> None:
        assert "MODEL, not a closed form" in (cpw.analytical_model or "")
        assert any("the target is a model, not a closed form" in w for w in cpw.warnings)

    def test_the_mode_was_tracked_across_levels_by_field_overlap(self, cpw) -> None:
        tracking = next(c for c in cpw.sanity_checks if c.name == "modes_unambiguously_tracked")
        overlap = next(
            c for c in cpw.sanity_checks if c.name == "field_overlap_match_score_above_0p90"
        )
        assert tracking.passed and overlap.passed

    def test_three_levels_with_growing_elements_and_dofs(self, cpw) -> None:
        assert cpw.convergence is not None
        assert cpw.convergence.refinement_levels == 3
        for name in (
            "element_count_increases_under_refinement",
            "degrees_of_freedom_increase_under_refinement",
        ):
            assert next(c for c in cpw.sanity_checks if c.name == name).passed

    def test_no_convergence_criterion_is_recorded_as_a_sanity_check(self, cpw) -> None:
        """Otherwise an unconverged run would be reported as SIMULATION_INVALID."""
        names = {check.name for check in cpw.sanity_checks}
        assert not {n for n in names if "order" in n or "gci" in n or "frequency_change" in n}
        assert all(check.passed for check in cpw.sanity_checks)

    def test_the_domain_size_limitation_is_stated(self, cpw) -> None:
        assert any("domain-size convergence was not assessed" in w for w in cpw.warnings)

    def test_every_referenced_output_hash_still_matches(self, cpw) -> None:
        assert cpw.verify_output_hashes(CPW) == []
