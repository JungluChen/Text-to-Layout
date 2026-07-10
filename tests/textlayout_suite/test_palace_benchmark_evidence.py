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

    def test_the_gci_is_below_one_percent(self, frequency) -> None:
        gci = next(c for c in frequency.sanity_checks if c.name.startswith("grid_convergence_index"))
        assert gci.passed

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
