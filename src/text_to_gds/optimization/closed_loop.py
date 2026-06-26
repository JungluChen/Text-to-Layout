"""Closed-loop geometry/simulation optimization flow."""

from __future__ import annotations

from typing import Any, Callable

from text_to_gds.synthesis import synthesize_jpa


def optimize_jpa_closed_loop(
    *,
    frequency_ghz: float = 6.0,
    gain_db: float = 20.0,
    bandwidth_mhz: float = 200.0,
    simulate: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
    maxiter: int = 12,
) -> dict[str, Any]:
    """Run a bounded JPA optimization loop.

    The loop only reports numerical convergence when the supplied ``simulate``
    callback returns real metrics. Without that callback, it prepares the
    synthesized starting point and reports skipped solver execution.
    """
    initial = synthesize_jpa(
        frequency_ghz=frequency_ghz,
        target_gain_db=gain_db,
        bandwidth_mhz=bandwidth_mhz,
    )
    if simulate is None:
        return {
            "schema": "text-to-gds.closed-loop.jpa.v1",
            "status": "skipped",
            "reason": "SKIPPED - no EM/circuit solver callback supplied",
            "initial_design": initial,
        }

    try:
        from scipy.optimize import minimize
    except Exception as exc:  # noqa: BLE001
        return {
            "schema": "text-to-gds.closed-loop.jpa.v1",
            "status": "skipped",
            "reason": f"SKIPPED - scipy optimizer unavailable: {exc}",
            "initial_design": initial,
        }

    history: list[dict[str, Any]] = []

    def objective(x: list[float]) -> float:
        candidate = {
            **initial,
            "capacitance_ff": float(x[0]),
            "squid_array_inductance_ph": float(x[1]),
        }
        result = simulate(candidate)
        history.append({"candidate": candidate, "result": result})
        if result.get("status") != "executed":
            return 1e9
        return (
            abs(float(result["frequency_ghz"]) - frequency_ghz)
            + abs(float(result.get("gain_db", gain_db)) - gain_db) / 10.0
            + abs(float(result.get("bandwidth_mhz", bandwidth_mhz)) - bandwidth_mhz) / 100.0
        )

    optimum = minimize(
        objective,
        [initial["capacitance_ff"], initial["squid_array_inductance_ph"]],
        method="Nelder-Mead",
        options={"maxiter": maxiter},
    )
    return {
        "schema": "text-to-gds.closed-loop.jpa.v1",
        "status": "executed" if history and history[-1]["result"].get("status") == "executed" else "failed",
        "success": bool(optimum.success),
        "initial_design": initial,
        "optimized_parameters": {
            "capacitance_ff": float(optimum.x[0]),
            "squid_array_inductance_ph": float(optimum.x[1]),
        },
        "history": history,
    }
