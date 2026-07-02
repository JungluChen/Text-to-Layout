"""Physics-fit acceptance tests (examples/acceptance/).

These check the project's hardest promise: the layout either meets the physical
requirement or the system correctly refuses an infeasible one — and a geometry
pass is never confused with a physics claim.
"""

from __future__ import annotations

import json
import math
import tempfile
from pathlib import Path

import pytest

from textlayout.acceptance import (
    AcceptanceResult,
    evaluate_idc_autosize,
    evaluate_lc_resonator_feasibility,
    evaluate_quarter_wave_resonator,
)

REPO = Path(__file__).resolve().parents[2]
ACCEPTANCE = REPO / "examples" / "acceptance"


# --- Acceptance Test A: infeasible 5 MHz LC resonator ------------------------
def test_5mhz_lc_is_infeasible_and_unfaked() -> None:
    a = evaluate_lc_resonator_feasibility(5e6)
    assert a.verdict == "INFEASIBLE"
    # No fake layout: nothing on the geometry/artifact rungs.
    assert a.geometry_generated is False
    assert a.artifact_generated is False
    assert a.physics_verified is False
    assert a.fabrication_ready is False


def test_5mhz_lc_first_principles_numbers() -> None:
    a = evaluate_lc_resonator_feasibility(5e6)
    est = a.analytical_estimate
    # Required LC = 1/(2*pi*f)^2 ≈ 1.013e-15 s^2.
    assert est["required_LC_product_s2"] == pytest.approx(1.013e-15, rel=1e-3)
    # L = 10 nH, C = 100 pF resonates at ~159 MHz, not 5 MHz.
    assert est["best_comfortable_on_chip_f0_hz"] == pytest.approx(159e6, rel=1e-2)
    # C = 100 pF would need L ≈ 10.13 uH (not nH).
    assert est["required_L_for_C_100pF_H"] == pytest.approx(10.13e-6, rel=1e-2)
    assert est["best_comfortable_on_chip_f0_hz"] > 5e6 * 30  # >30x above target


def test_5mhz_lc_lists_alternatives() -> None:
    a = evaluate_lc_resonator_feasibility(5e6)
    joined = " ".join(a.alternatives).lower()
    assert "off-chip" in joined
    assert "crystal" in joined or "ceramic" in joined
    assert "gyrator" in joined or "gm-c" in joined


# --- Acceptance Test B: feasible 6 GHz quarter-wave CPW resonator ------------
def test_6ghz_resonator_length_from_phase_velocity() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        b = evaluate_quarter_wave_resonator(6.0, work_dir=Path(tmp))
    est = b.analytical_estimate
    # L = v_p/(4f); on eps_r=11.9 silicon eps_eff=6.45 -> ~4918 um.
    eps_eff = (1 + 11.9) / 2
    v_p = 299_792_458.0 / math.sqrt(eps_eff)
    expected_um = v_p / (4 * 6e9) * 1e6
    assert est["predicted_quarter_wave_length_um"] == pytest.approx(expected_um, rel=1e-3)
    assert est["predicted_quarter_wave_length_um"] == pytest.approx(4918.5, rel=1e-3)


def test_6ghz_resonator_geometry_passes_but_not_physics_verified() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        b = evaluate_quarter_wave_resonator(6.0, work_dir=Path(tmp))
    assert b.verdict == "GEOMETRY_PASS"
    assert b.geometry_generated is True
    assert b.analytical_estimate["port_count"] >= 2  # signal + ground references
    assert b.solver_input_prepared is True
    # No solver was executed -> must NOT be physics-verified.
    assert b.solver_executed is False
    assert b.physics_verified is False


# --- Acceptance Test C: IDC auto-sizing reduces capacitance error ------------
def test_idc_autosize_beats_fixed_22_pairs() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        c = evaluate_idc_autosize(0.6, work_dir=Path(tmp))
    est = c.analytical_estimate
    # Auto-sizing must strictly reduce |error| vs the prompt's 22 pairs.
    assert abs(est["chosen_error_pct"]) < abs(est["reference_error_pct"])
    assert est["chosen_finger_pairs"] != 22
    assert est["error_improvement_pct_points"] > 0


def test_idc_autosize_is_analytical_not_em_verified() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        c = evaluate_idc_autosize(0.6, work_dir=Path(tmp))
    assert c.solver_executed is False
    assert c.physics_verified is False
    assert c.target_comparison is not None
    assert c.target_comparison["method"] == "analytical"


# --- Cross-cutting honesty invariants ----------------------------------------
@pytest.fixture(scope="module")
def all_results() -> list[AcceptanceResult]:
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        return [
            evaluate_lc_resonator_feasibility(5e6),
            evaluate_quarter_wave_resonator(6.0, work_dir=work / "b"),
            evaluate_idc_autosize(0.6, work_dir=work / "c"),
        ]


def test_physics_verified_implies_solver_executed(all_results: list[AcceptanceResult]) -> None:
    for r in all_results:
        if r.physics_verified:
            assert r.solver_executed and r.target_comparison is not None, r.name


def test_no_acceptance_result_is_fabrication_ready(all_results: list[AcceptanceResult]) -> None:
    for r in all_results:
        assert r.fabrication_ready is False, r.name


def test_evidence_ladder_extraction_requires_solver(all_results: list[AcceptanceResult]) -> None:
    for r in all_results:
        ladder = r.to_dict()["evidence_ladder"]
        if ladder["extracted_and_compared"]:
            assert ladder["solver_executed"], r.name


# --- Committed packets match a fresh evaluation (regeneration consistency) ----
def test_committed_acceptance_packets_match_evaluation() -> None:
    for name, result in (("A_infeasible_5mhz_lc", evaluate_lc_resonator_feasibility(5e6)),):
        committed = json.loads((ACCEPTANCE / name / "result.json").read_text(encoding="utf-8"))
        assert committed["verdict"] == result.verdict
        assert committed["analytical_estimate"]["required_LC_product_s2"] == pytest.approx(
            result.analytical_estimate["required_LC_product_s2"]
        )


def test_acceptance_folders_exist() -> None:
    for name in ("A_infeasible_5mhz_lc", "B_feasible_6ghz_resonator", "C_idc_autosize_0p6pf"):
        folder = ACCEPTANCE / name
        assert (folder / "prompt.md").is_file(), name
        assert (folder / "result.json").is_file(), name
        assert (folder / "evidence.md").is_file(), name
