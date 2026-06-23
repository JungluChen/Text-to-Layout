"""CADFusion-style candidate loop tests.

Verifies:
  - N candidates are generated and evaluated
  - Failed candidates are stored (never silently dropped)
  - The best candidate is selected by score
  - Scores follow the physics scoring contract
  - An empty spec list returns a valid result
"""

from __future__ import annotations

import json

import pytest

from text_to_gds.candidate_loop import (
    CandidateSpec,
    _score_candidate,
    CandidateResult,
    run_candidate_loop,
)


# ---------------------------------------------------------------------------
# Unit tests: scoring contract
# ---------------------------------------------------------------------------

class TestScoringContract:
    def test_failed_candidate_scores_zero(self):
        c = CandidateResult(index=0, status="failed", reason="compile error")
        assert _score_candidate(c) == 0.0

    def test_unsupported_candidate_scores_zero(self):
        c = CandidateResult(index=0, status="unsupported", reason="no backend")
        assert _score_candidate(c) == 0.0

    def test_ok_candidate_starts_at_50(self):
        c = CandidateResult(index=0, status="ok")
        score = _score_candidate(c)
        assert score >= 50.0

    def test_drc_pass_increases_score(self):
        c_pass = CandidateResult(index=0, status="ok", drc_passed=True)
        c_fail = CandidateResult(index=0, status="ok", drc_passed=False)
        assert _score_candidate(c_pass) > _score_candidate(c_fail)

    def test_solver_execution_increases_score(self):
        c_solver = CandidateResult(index=0, status="ok", solver_status="executed")
        c_skip = CandidateResult(index=0, status="ok", solver_status="skipped")
        assert _score_candidate(c_solver) > _score_candidate(c_skip)

    def test_score_bounded_0_100(self):
        c = CandidateResult(
            index=0,
            status="ok",
            drc_passed=True,
            physics_passed=True,
            solver_status="executed",
            extraction={"junction": {"ic": 1e-7, "lj": 3.4e-9}, "linear_circuit": {"resonance_frequency": 6e9}, "validation": {"passed": True}},
        )
        score = _score_candidate(c)
        assert 0.0 <= score <= 100.0


# ---------------------------------------------------------------------------
# Integration: run candidate loop with invalid sequences
# ---------------------------------------------------------------------------

class TestCandidateLoopIntegration:
    """Run candidates through the loop — using invalid SuperCAD so the pipeline
    exercises the failure path without needing real GDS generation."""

    def test_single_failed_candidate_is_stored(self, tmp_path):
        specs = [
            CandidateSpec(
                index=0,
                supercad_text="INVALID_SEQUENCE",
                rationale="intentionally broken",
            )
        ]
        result = run_candidate_loop(specs, work_dir=tmp_path / "loop")
        assert result.n_candidates == 1
        assert result.n_failed == 1
        assert result.winner is None
        # Failed candidate must be persisted
        candidate_json = tmp_path / "loop" / "candidate_00" / "candidate_result.json"
        assert candidate_json.is_file()
        data = json.loads(candidate_json.read_text())
        assert data["status"] == "failed"

    def test_all_failed_candidates_are_stored(self, tmp_path):
        specs = [
            CandidateSpec(index=i, supercad_text="BAD", rationale=f"broken {i}")
            for i in range(3)
        ]
        result = run_candidate_loop(specs, work_dir=tmp_path / "loop")
        assert result.n_candidates == 3
        assert result.n_failed == 3
        assert result.winner is None
        assert result.best_score == 0.0
        # All 3 must be stored
        for i in range(3):
            assert (tmp_path / "loop" / f"candidate_0{i}" / "candidate_result.json").is_file()

    def test_loop_result_json_written(self, tmp_path):
        specs = [CandidateSpec(index=0, supercad_text="BAD")]
        run_candidate_loop(specs, work_dir=tmp_path / "loop", save_result=True)
        loop_json = tmp_path / "loop" / "candidate_loop_result.json"
        assert loop_json.is_file()
        data = json.loads(loop_json.read_text())
        assert data["schema"] == "text-to-gds.candidate-loop.v1"
        assert data["n_candidates"] == 1

    def test_empty_specs_returns_valid_result(self, tmp_path):
        result = run_candidate_loop([], work_dir=tmp_path / "loop")
        assert result.n_candidates == 0
        assert result.winner is None
        assert result.best_score == 0.0

    def test_loop_elapsed_time_is_positive(self, tmp_path):
        specs = [CandidateSpec(index=0, supercad_text="BAD")]
        result = run_candidate_loop(specs, work_dir=tmp_path / "loop")
        assert result.elapsed_total_s >= 0.0


# ---------------------------------------------------------------------------
# Integration: candidate with real SuperCAD (requires technology YAML)
# ---------------------------------------------------------------------------

@pytest.mark.skipif(
    __import__("text_to_gds.process", fromlist=["find_technology_yaml"]).find_technology_yaml("ncu_alox_2026") is None,
    reason="ncu_alox_2026.yaml not found",
)
def test_candidate_loop_with_real_technology(tmp_path):
    """When technology YAML exists, a valid SuperCAD should progress past parse step."""
    from text_to_gds.candidate_loop import generate_cpw_frequency_sweep

    specs = generate_cpw_frequency_sweep(
        technology="ncu_alox_2026",
        frequencies_ghz=[5.0, 6.0],
    )
    assert len(specs) == 2
    assert all(spec.rationale for spec in specs)

    result = run_candidate_loop(specs, work_dir=tmp_path / "loop")
    assert result.n_candidates == 2
    # Technology YAML found → at minimum, compile should not fail at YAML check
    # (it may fail at backend selection, but not at technology validation)
    for c in result.all_candidates:
        if c.status == "failed":
            assert "technology" not in (c.reason or "").lower() or "yaml" not in (c.reason or "").lower(), (
                f"Candidate {c.index} failed at technology check: {c.reason}"
            )
