from __future__ import annotations

from text_to_gds.simulation.solver_adapter import SolverResult


def test_solver_result_creation() -> None:
    result = SolverResult(
        status="success",
        reason="completed",
        solver="joSIM",
        output_path=None,
        parsed_data=None,
        execution_time_s=1.23,
    )
    assert result.status == "success"
    assert result.solver == "joSIM"
    assert result.execution_time_s == 1.23


def test_solver_result_skipped() -> None:
    result = SolverResult(
        status="skipped",
        reason="solver not installed",
        solver="ngspice",
        output_path=None,
        parsed_data=None,
        execution_time_s=0.0,
    )
    assert result.status == "skipped"
    assert result.execution_time_s == 0.0
