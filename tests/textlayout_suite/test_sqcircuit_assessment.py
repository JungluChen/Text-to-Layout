"""Use retained real worker data; corruption cases are explicitly synthetic."""

import json
from pathlib import Path

import pytest

from textlayout.external.sqcircuit_assessment import assess_sqcircuit_lc
from textlayout.external.sqcircuit_lc import SQcircuitLCPlan

ROOT = Path(__file__).resolve().parents[2] / "docs/progress/evidence/2026-10-11-154025"


def packet():
    return (
        SQcircuitLCPlan.model_validate_json((ROOT / "request.json").read_text()),
        json.loads((ROOT / "sqc-worker-first.json").read_text())["rows"],
    )


def test_real_retained_worker_packet() -> None:
    plan, rows = packet()
    assert assess_sqcircuit_lc(plan, rows).numerical_checks_passed


@pytest.mark.parametrize("fault", ["nan", "zero_vector", "missing_row", "order", "ragged"])
def test_malformed_raw_data_rejected(fault: str) -> None:
    plan, rows = packet()
    if fault == "nan":
        rows[0]["eigenvalues_rad_s"][1] = float("nan")
    elif fault == "zero_vector":
        for row in rows[0]["eigenvectors_real"]:
            row[0] = 0.0
    elif fault == "missing_row":
        rows.pop()
    elif fault == "order":
        rows.reverse()
    else:
        rows[0]["hamiltonian_rad_s_real"][0].pop()
    with pytest.raises(ValueError):
        assess_sqcircuit_lc(plan, rows)


@pytest.mark.parametrize("fault", ["capacitance", "spectrum", "normalization", "matrix"])
def test_finite_disagreement_does_not_pass(fault: str) -> None:
    plan, rows = packet()
    if fault == "capacitance":
        rows[0]["resolved_capacitance_f"] = plan.request.capacitance_f
    elif fault == "spectrum":
        rows[0]["eigenvalues_rad_s"][1] += 10000.0
    elif fault == "normalization":
        rows[0]["eigenvectors_real"][0][0] *= 2
    else:
        rows[0]["hamiltonian_rad_s_real"][0][1] = 1e9
    assert not assess_sqcircuit_lc(plan, rows).numerical_checks_passed


def test_scalar_imaginary_component_cannot_broadcast_into_valid_matrix() -> None:
    plan, rows = packet()
    rows[0]["hamiltonian_rad_s_imag"] = 0.0
    with pytest.raises(ValueError):
        assess_sqcircuit_lc(plan, rows)
