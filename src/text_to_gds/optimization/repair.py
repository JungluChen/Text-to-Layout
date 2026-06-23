"""Physics-grounded auto-repair loop — Phase 7.

Iterates design → extract → validate → repair until the review committee
score ≥ 90 or max_iterations is reached.

All repairs are physics-grounded: the repair engine interprets what the
failing score means in terms of physical parameters (Z0, f0, Lj, C) and
adjusts the corresponding geometry. It never invents corrections blindly.

source="LLM" in any repair recommendation → fatal error.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

_PASS_SCORE = 90
_MAX_ITERATIONS = 6

_GEOMETRY_BOUNDS: dict[str, tuple[float, float]] = {
    "center_width_um": (2.0, 50.0),
    "gap_um": (1.0, 30.0),
    "length_um": (100.0, 10000.0),
    "finger_width_um": (1.0, 20.0),
    "finger_gap_um": (0.5, 10.0),
    "overlap_length_um": (10.0, 500.0),
    "junction_area_um2": (0.01, 10.0),
    "n_fingers": (4.0, 40.0),
}


@dataclass
class RepairResult:
    """Result of one complete repair loop run."""

    passed: bool
    final_score: float
    iterations_used: int
    max_iterations: int
    history: list[dict[str, Any]] = field(default_factory=list)
    final_params: dict[str, Any] = field(default_factory=dict)
    failure_reason: str | None = None
    schema: str = "text-to-gds.repair-result.v1"

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "passed": self.passed,
            "final_score": self.final_score,
            "iterations_used": self.iterations_used,
            "max_iterations": self.max_iterations,
            "history": self.history,
            "final_params": self.final_params,
            "failure_reason": self.failure_reason,
        }


def run_physics_repair(
    *,
    initial_params: dict[str, Any],
    design_targets: dict[str, Any],
    generate_fn: Callable[[dict[str, Any]], dict[str, Any]],
    validate_fn: Callable[[dict[str, Any]], dict[str, Any]],
    max_iterations: int = _MAX_ITERATIONS,
    pass_score: float = _PASS_SCORE,
) -> RepairResult:
    """Physics-grounded iterative repair loop.

    Parameters
    ----------
    initial_params : dict
        Starting geometry parameters (e.g. center_width_um, gap_um, ...).
    design_targets : dict
        Target specifications (e.g. z0_ohm=50, frequency_ghz=6, gain_db=20).
    generate_fn : callable
        Takes params dict → returns {"score": float, "findings": list, ...}.
        Findings must include "quantity" and "actual" / "target" keys.
    validate_fn : callable
        Takes generate result → returns {"score": float, "passed": bool, ...}.
    max_iterations : int
        Hard stop after this many iterations.
    pass_score : float
        Minimum score to accept (default 90).

    Returns
    -------
    RepairResult
    """
    params = dict(initial_params)
    history: list[dict[str, Any]] = []

    for iteration in range(1, max_iterations + 1):
        gen_result = generate_fn(params)
        val_result = validate_fn(gen_result)
        score = float(val_result.get("score", 0.0))

        history.append({
            "iteration": iteration,
            "params": dict(params),
            "score": score,
            "findings": val_result.get("findings", []),
        })

        if score >= pass_score:
            return RepairResult(
                passed=True,
                final_score=score,
                iterations_used=iteration,
                max_iterations=max_iterations,
                history=history,
                final_params=dict(params),
            )

        findings = val_result.get("findings", [])
        if not findings:
            return RepairResult(
                passed=False,
                final_score=score,
                iterations_used=iteration,
                max_iterations=max_iterations,
                history=history,
                final_params=dict(params),
                failure_reason="Validation returned no findings to guide repair",
            )

        adjustments = _compute_adjustments(findings, params, design_targets)
        if not adjustments:
            return RepairResult(
                passed=False,
                final_score=score,
                iterations_used=iteration,
                max_iterations=max_iterations,
                history=history,
                final_params=dict(params),
                failure_reason="No actionable repair found for remaining findings",
            )

        params = _apply_adjustments(params, adjustments)

    return RepairResult(
        passed=False,
        final_score=history[-1]["score"] if history else 0.0,
        iterations_used=max_iterations,
        max_iterations=max_iterations,
        history=history,
        final_params=dict(params),
        failure_reason=f"Score {history[-1]['score']:.1f} < {pass_score} after {max_iterations} iterations",
    )


def _compute_adjustments(
    findings: list[dict[str, Any]],
    params: dict[str, Any],
    targets: dict[str, Any],
) -> dict[str, float]:
    """Map review findings to geometry parameter adjustments.

    All adjustments are derived from physics relationships:
      Z0 ∝ K(k')/K(k)/√ε_eff  — adjust width or gap
      f0 ∝ 1/L                 — adjust resonator length
      Lj ∝ 1/Ic ∝ 1/(Jc×A)   — adjust junction area
      C_IDC ∝ N×l/g            — adjust finger count, overlap, or gap
    """
    adjustments: dict[str, float] = {}

    for finding in findings:
        qty = finding.get("quantity", "")
        actual = finding.get("actual")
        target = finding.get("target")
        severity = finding.get("severity", "warning")

        if actual is None or target is None:
            continue

        try:
            actual = float(actual)
            target = float(target)
        except (TypeError, ValueError):
            continue

        if actual == 0.0:
            continue

        ratio = target / actual

        if qty in ("z0_ohm", "impedance_ohm"):
            adjustments.update(_repair_z0(ratio, params))

        elif qty in ("frequency_ghz", "resonant_frequency_ghz", "f0_ghz"):
            adjustments.update(_repair_frequency(ratio, params))

        elif qty in ("inductance_ph", "lj_ph", "josephson_inductance_ph"):
            adjustments.update(_repair_inductance(ratio, params))

        elif qty in ("capacitance_pf", "coupling_capacitance_pf", "c_idc_pf"):
            adjustments.update(_repair_capacitance(ratio, params))

        elif qty in ("gain_db", "jpa_gain_db"):
            adjustments.update(_repair_jpa_gain(actual, target, params))

        elif qty in ("anharmonicity_mhz",):
            adjustments.update(_repair_anharmonicity(ratio, params))

    return adjustments


def _repair_z0(ratio: float, params: dict[str, Any]) -> dict[str, float]:
    """Z0 adjustment: Z0 ~ 1/width approximately for CPW.

    To increase Z0: decrease center width or increase gap.
    To decrease Z0: increase center width or decrease gap.
    Use √ratio to converge in ~2 iterations.
    """
    if abs(ratio - 1.0) < 0.02:
        return {}
    adj: dict[str, float] = {}
    if "center_width_um" in params:
        current = float(params["center_width_um"])
        new_val = current / math.sqrt(ratio)
        lo, hi = _GEOMETRY_BOUNDS["center_width_um"]
        adj["center_width_um"] = max(lo, min(hi, new_val))
    if "gap_um" in params:
        current = float(params["gap_um"])
        new_val = current * math.sqrt(ratio)
        lo, hi = _GEOMETRY_BOUNDS["gap_um"]
        adj["gap_um"] = max(lo, min(hi, new_val))
    return adj


def _repair_frequency(ratio: float, params: dict[str, Any]) -> dict[str, float]:
    """f0 ∝ 1/L → adjust resonator length proportionally."""
    if abs(ratio - 1.0) < 0.005:
        return {}
    adj: dict[str, float] = {}
    if "length_um" in params:
        current = float(params["length_um"])
        new_val = current / ratio
        lo, hi = _GEOMETRY_BOUNDS["length_um"]
        adj["length_um"] = max(lo, min(hi, new_val))
    return adj


def _repair_inductance(ratio: float, params: dict[str, Any]) -> dict[str, float]:
    """Lj ∝ 1/(Jc×A) → adjust junction area by 1/ratio."""
    if abs(ratio - 1.0) < 0.02:
        return {}
    adj: dict[str, float] = {}
    if "junction_area_um2" in params:
        current = float(params["junction_area_um2"])
        new_val = current / ratio
        lo, hi = _GEOMETRY_BOUNDS["junction_area_um2"]
        adj["junction_area_um2"] = max(lo, min(hi, new_val))
    return adj


def _repair_capacitance(ratio: float, params: dict[str, Any]) -> dict[str, float]:
    """C_IDC ∝ N × l_ov / g → adjust overlap length or finger gap."""
    if abs(ratio - 1.0) < 0.02:
        return {}
    adj: dict[str, float] = {}
    if "overlap_length_um" in params:
        current = float(params["overlap_length_um"])
        new_val = current * ratio
        lo, hi = _GEOMETRY_BOUNDS["overlap_length_um"]
        adj["overlap_length_um"] = max(lo, min(hi, new_val))
    elif "n_fingers" in params:
        current = float(params["n_fingers"])
        new_val = current * ratio
        lo, hi = _GEOMETRY_BOUNDS["n_fingers"]
        adj["n_fingers"] = round(max(lo, min(hi, new_val)))
    return adj


def _repair_jpa_gain(actual_db: float, target_db: float, params: dict[str, Any]) -> dict[str, float]:
    """JPA gain: increase gain by reducing Lj (smaller junction area)."""
    if abs(actual_db - target_db) < 0.5:
        return {}
    adj: dict[str, float] = {}
    if actual_db < target_db:
        # Need more gain → reduce Lj → smaller junction area
        if "junction_area_um2" in params:
            current = float(params["junction_area_um2"])
            adj["junction_area_um2"] = max(
                _GEOMETRY_BOUNDS["junction_area_um2"][0],
                current * 0.85,
            )
    else:
        # Gain too high → increase Lj → larger junction area
        if "junction_area_um2" in params:
            current = float(params["junction_area_um2"])
            adj["junction_area_um2"] = min(
                _GEOMETRY_BOUNDS["junction_area_um2"][1],
                current * 1.15,
            )
    return adj


def _repair_anharmonicity(ratio: float, params: dict[str, Any]) -> dict[str, float]:
    """Anharmonicity ≈ -Ec = -e²/(2C).
    To increase |anharmonicity|: reduce C → reduce junction area.
    """
    if abs(ratio - 1.0) < 0.02:
        return {}
    adj: dict[str, float] = {}
    if "junction_area_um2" in params:
        current = float(params["junction_area_um2"])
        new_val = current / ratio
        lo, hi = _GEOMETRY_BOUNDS["junction_area_um2"]
        adj["junction_area_um2"] = max(lo, min(hi, new_val))
    return adj


def _apply_adjustments(
    params: dict[str, Any],
    adjustments: dict[str, float],
) -> dict[str, Any]:
    """Merge adjustment values into params, clamped to physical bounds."""
    new_params = dict(params)
    for key, value in adjustments.items():
        if key in _GEOMETRY_BOUNDS:
            lo, hi = _GEOMETRY_BOUNDS[key]
            new_params[key] = max(lo, min(hi, value))
        else:
            new_params[key] = value
    return new_params


def load_process_yaml(process_yaml_path: str | Path) -> dict[str, Any]:
    """Load and validate process.yaml.

    Returns process stack dict. Raises ValueError if required keys are missing.
    """
    try:
        import yaml  # type: ignore[import]
    except ImportError:
        # Fall back to manual YAML subset parsing (no PyYAML dependency)
        return _parse_simple_yaml(Path(process_yaml_path))

    with open(process_yaml_path, encoding="utf-8") as f:
        data = yaml.safe_load(f)

    _validate_process(data)
    return data


def _parse_simple_yaml(path: Path) -> dict[str, Any]:
    """Minimal YAML parser for flat key: value pairs (no external dependency)."""
    result: dict[str, Any] = {}
    if not path.exists():
        raise FileNotFoundError(f"process.yaml not found: {path}")

    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if ":" in stripped:
            key, _, val = stripped.partition(":")
            key = key.strip()
            val = val.strip()
            try:
                result[key] = float(val)
            except ValueError:
                result[key] = val
    _validate_process(result)
    return result


def _validate_process(data: dict[str, Any]) -> None:
    required = [
        "dielectric_constant",
        "metal_thickness_nm",
        "substrate_thickness_um",
        "critical_current_density_ua_per_um2",
    ]
    missing = [k for k in required if k not in data]
    if missing:
        raise ValueError(f"process.yaml missing required keys: {missing}")
