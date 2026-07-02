"""Phase 9 category 2 — closed-loop IDC optimization.

Convergence on distinct targets, safe failure on impossible constraints, and
the guarantee that analytical results are never labelled as solver results.
"""

from __future__ import annotations

import pytest

from textlayout.optimization import optimize_idc
from textlayout.research import formulas as F

EPS_R_SILICON = 11.9


@pytest.mark.parametrize("target_pf", [0.2, 0.6, 1.5])
def test_converges_on_distinct_targets(target_pf: float) -> None:
    result = optimize_idc(
        target_capacitance_pf=target_pf,
        substrate_epsilon_r=EPS_R_SILICON,
        tolerance_percent=5.0,
    )
    assert result.converged, result.notes
    assert result.error_percent <= 5.0
    # The reported estimate must be reproducible from the cited formula.
    check = F.idc_capacitance_pf(
        int(result.final_parameters["finger_pairs"]),
        float(result.final_parameters["overlap_um"]),
        EPS_R_SILICON,
    )
    # estimated_capacitance_pf is rounded to 6 decimal places on the record.
    assert check == pytest.approx(result.estimated_capacitance_pf, abs=1e-6)


def test_result_is_physically_valid() -> None:
    result = optimize_idc(
        target_capacitance_pf=0.6,
        substrate_epsilon_r=EPS_R_SILICON,
        min_finger_width_um=2.0,
        min_gap_um=2.0,
    )
    params = result.final_parameters
    assert params["finger_pairs"] >= 2
    assert params["finger_width_um"] >= 2.0
    assert params["gap_um"] >= 2.0
    assert 20.0 <= params["overlap_um"] <= 2000.0


def test_user_fixed_parameters_are_honoured() -> None:
    result = optimize_idc(
        target_capacitance_pf=0.6,
        substrate_epsilon_r=EPS_R_SILICON,
        initial_parameters={"finger_pairs": 22},
    )
    assert result.final_parameters["finger_pairs"] == 22
    assert "finger_pairs" in result.fixed_parameters
    assert result.converged  # overlap alone can absorb the difference


def test_impossible_constraints_fail_safely() -> None:
    # Both knobs pinned to values that cannot reach the target.
    result = optimize_idc(
        target_capacitance_pf=50.0,
        substrate_epsilon_r=EPS_R_SILICON,
        initial_parameters={"finger_pairs": 2, "overlap_um": 20.0},
    )
    assert not result.converged
    assert any("Did not converge" in note for note in result.notes)


def test_invalid_inputs_raise() -> None:
    with pytest.raises(ValueError, match="positive"):
        optimize_idc(target_capacitance_pf=-1.0, substrate_epsilon_r=EPS_R_SILICON)
    with pytest.raises(ValueError, match="positive"):
        optimize_idc(
            target_capacitance_pf=0.6,
            substrate_epsilon_r=EPS_R_SILICON,
            tolerance_percent=0,
        )


def test_analytical_results_are_never_labelled_as_solver_results() -> None:
    result = optimize_idc(target_capacitance_pf=0.6, substrate_epsilon_r=EPS_R_SILICON)
    assert "ANALYTICAL_ONLY" in result.method
    payload = result.model_dump()
    assert "PHYSICS_VERIFIED" not in str(payload)
    assert "extracted" not in str(payload).lower()
