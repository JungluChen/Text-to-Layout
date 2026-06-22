"""Phase 1 tests: open-solver routing, manager, and the agreement engine."""

from __future__ import annotations

from text_to_gds.open_solver_manager import SolverManager, route, select_backends
from text_to_gds.solver_agreement import cross_validate


# --- Solver Agreement Engine ---

def test_agreement_three_sources_pass():
    result = cross_validate(
        [
            {"source": "openEMS", "value": 6.05e9},
            {"source": "Palace", "value": 6.00e9},
            {"source": "theory", "value": 5.93e9},
        ],
        quantity="frequency_hz",
        tolerance_pct=5.0,
    )
    assert result["passed"] is True
    assert result["verdict"] == "agree"
    assert result["reference_value"] == 6.00e9  # median
    assert 0.0 < result["confidence_pct"] <= 100.0
    assert result["n_sources"] == 3


def test_agreement_single_source_is_never_trusted():
    result = cross_validate([{"source": "openEMS", "value": 6.0e9}], quantity="frequency_hz")
    assert result["passed"] is False
    assert result["confidence_pct"] == 0.0
    assert result["verdict"] == "insufficient_sources"


def test_agreement_disagreement_fails():
    result = cross_validate(
        [{"source": "a", "value": 5.0e9}, {"source": "b", "value": 6.0e9}],
        tolerance_pct=5.0,
    )
    assert result["passed"] is False
    assert result["verdict"] == "disagree"
    assert result["max_relative_error_pct"] > 5.0


def test_agreement_ignores_missing_values():
    result = cross_validate(
        [
            {"source": "openEMS", "value": 6.0e9},
            {"source": "Palace", "value": 6.01e9},
            {"source": "Elmer", "value": None},
        ]
    )
    assert result["n_sources"] == 2
    assert result["passed"] is True


# --- Open backend routing ---

def test_route_cpw_uses_openems_and_palace():
    plan = route("CPW resonator")
    assert plan["em_backends"] == ["openEMS", "Palace"]
    assert plan["required_agreement"] == 1
    assert plan["validation_backends"] == []


def test_route_jpa_publication_requires_two_and_adds_circuit_companion():
    plan = route("JPA", target_accuracy="publication")
    assert "openEMS" in plan["em_backends"]
    assert "JosephsonCircuits.jl" in plan["companion_backends"]
    assert plan["required_agreement"] == 2


def test_route_qubit_uses_palace_and_scqubits():
    plan = route("transmon qubit")
    assert plan["em_backends"] == ["Palace"]
    assert plan["companion_backends"] == ["scqubits"]


def test_route_validation_only_when_requested():
    assert route("CPW")["validation_backends"] == []
    assert route("CPW", validation=True)["validation_backends"] == ["HFSS", "Sonnet"]


def test_select_backends_default():
    assert select_backends("something_unmapped")["device_class"] == "default"


# --- Solver manager ---

def test_manager_solve_routes_skips_and_excludes_commercial(tmp_path):
    gds = tmp_path / "cap.gds"
    gds.write_bytes(b"fixture")
    result = SolverManager().solve(
        gds,
        device="interdigital_capacitor",
        target_accuracy="publication",
        output_stem=tmp_path / "cap",
    )
    assert result["plan"]["device_class"] == "interdigital"
    run_backends = {run["backend"] for run in result["runs"]}
    # Companion (FastCap) is deferred; commercial solvers never appear in runs.
    assert "FastCap" in run_backends
    assert "HFSS" not in run_backends and "Sonnet" not in run_backends
    assert result["validation_runs"] == []


def test_manager_solve_lists_commercial_only_under_validation(tmp_path):
    gds = tmp_path / "cpw.gds"
    gds.write_bytes(b"fixture")
    result = SolverManager().solve(
        gds, device="cpw", output_stem=tmp_path / "cpw", validation=True
    )
    validation_backends = {run["backend"] for run in result["validation_runs"]}
    assert validation_backends == {"HFSS", "Sonnet"}
    assert all(run["role"] == "validation_only" for run in result["validation_runs"])
