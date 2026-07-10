from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class OptimizationState:
    iteration: int
    parameters: dict[str, float]
    metrics: dict[str, float]
    errors: dict[str, float]


def _surrogate_metrics(parameters: dict[str, float]) -> dict[str, float]:
    cpw_length = max(parameters["cpw_length"], 1e-9)
    cpw_gap = max(parameters["cpw_gap"], 1e-9)
    cpw_width = max(parameters["cpw_trace_width"], 1e-9)
    area = max(parameters["junction_width"] * parameters["junction_height"], 1e-12)

    frequency_ghz = 5.0 * (210.0 / cpw_length) ** 0.5
    bandwidth_mhz = 500.0 * (cpw_gap / 6.0) * (10.0 / cpw_width) ** 0.5
    gain_db = 20.0 + 8.0 * (0.0484 / area - 1.0)
    return {
        "center_frequency_ghz": frequency_ghz,
        "bandwidth_mhz": bandwidth_mhz,
        "gain_db": gain_db,
    }


def optimize_ljpa_parameters(
    *,
    target_frequency_ghz: float = 5.0,
    target_bandwidth_mhz: float = 500.0,
    target_gain_db: float = 20.0,
    initial_parameters: dict[str, float] | None = None,
    max_iterations: int = 4,
) -> dict[str, Any]:
    """Run a deterministic local surrogate optimization for first-pass LJPA geometry."""
    parameters = {
        "cpw_length": 210.0,
        "cpw_trace_width": 10.0,
        "cpw_gap": 6.0,
        "junction_width": 0.22,
        "junction_height": 0.22,
        "flux_line_length": 120.0,
        "flux_line_width": 1.5,
        "inductor_segment_length": 24.0,
        "inductor_trace_width": 1.0,
        "inductor_pitch": 3.0,
    }
    parameters.update(initial_parameters or {})

    history: list[OptimizationState] = []
    for iteration in range(max_iterations):
        metrics = _surrogate_metrics(parameters)
        errors = {
            "center_frequency_ghz": target_frequency_ghz - metrics["center_frequency_ghz"],
            "bandwidth_mhz": target_bandwidth_mhz - metrics["bandwidth_mhz"],
            "gain_db": target_gain_db - metrics["gain_db"],
        }
        history.append(
            OptimizationState(
                iteration=iteration,
                parameters=dict(parameters),
                metrics=metrics,
                errors=errors,
            )
        )

        frequency_ratio = metrics["center_frequency_ghz"] / max(target_frequency_ghz, 1e-9)
        parameters["cpw_length"] = max(20.0, min(5000.0, parameters["cpw_length"] * frequency_ratio**2))

        bandwidth_ratio = target_bandwidth_mhz / max(metrics["bandwidth_mhz"], 1e-9)
        parameters["cpw_gap"] = max(1.0, min(30.0, parameters["cpw_gap"] * bandwidth_ratio**0.5))

        gain_error = target_gain_db - metrics["gain_db"]
        area_scale = 1.0 - gain_error / 80.0
        area_scale = max(0.5, min(1.8, area_scale))
        parameters["junction_width"] = max(0.10, min(1.50, parameters["junction_width"] * area_scale**0.5))
        parameters["junction_height"] = max(0.10, min(1.50, parameters["junction_height"] * area_scale**0.5))

    final_metrics = _surrogate_metrics(parameters)
    final_errors = {
        "center_frequency_ghz": target_frequency_ghz - final_metrics["center_frequency_ghz"],
        "bandwidth_mhz": target_bandwidth_mhz - final_metrics["bandwidth_mhz"],
        "gain_db": target_gain_db - final_metrics["gain_db"],
    }
    history.append(
        OptimizationState(
            iteration=max_iterations,
            parameters=dict(parameters),
            metrics=final_metrics,
            errors=final_errors,
        )
    )

    return {
        "schema": "text-to-gds.optimization.v0",
        "engine": "local_surrogate",
        "targets": {
            "center_frequency_ghz": target_frequency_ghz,
            "bandwidth_mhz": target_bandwidth_mhz,
            "gain_db": target_gain_db,
        },
        "final_parameters": parameters,
        "final_metrics": final_metrics,
        "final_errors": final_errors,
        "history": [asdict(state) for state in history],
        "notes": [
            "This is a deterministic local surrogate loop for first-pass geometry.",
            "Replace with JosephsonCircuits.jl/JoSIM/EM-backed optimization before signoff.",
        ],
    }
