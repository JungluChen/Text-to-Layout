from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from text_to_gds.cpw_physics import synthesize_cpw
from text_to_gds.physics_compiler import PHI0_WB


class OptimizationIteration(BaseModel):
    model_config = ConfigDict(extra="forbid")

    iteration: int
    parameters: dict[str, float]
    metrics: dict[str, float]
    objective: float
    simulation: dict[str, Any]


class OptimizationReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema: str = "text-to-gds.optimization-loop.v1"
    status: Literal["ok", "failed"]
    device: str
    target: dict[str, float]
    final_parameters: dict[str, float]
    final_metrics: dict[str, float]
    history: list[OptimizationIteration]
    solver_status: str
    notes: list[str] = Field(default_factory=list)


def optimize_device(
    device: str,
    target: dict[str, float],
    *,
    initial_parameters: dict[str, float] | None = None,
    max_iterations: int = 40,
    output_path: str | Path | None = None,
) -> dict[str, Any]:
    """Optimize first-pass geometry from extracted/analytical metrics.

    This loop compares generated analytical/extracted metrics to targets. It
    does not claim solver success; EM solver integration remains explicit via
    ``solver_status='skipped'`` unless a real solver is wired by the caller.
    """
    d = device.lower().replace(" ", "_")
    if "cpw" in d or "resonator" in d:
        result = _optimize_cpw(target, initial_parameters or {}, max_iterations)
    elif "idc" in d or "capacitor" in d:
        result = _optimize_idc(target, initial_parameters or {}, max_iterations)
    elif "jj" in d or "junction" in d:
        result = _optimize_jj(target, initial_parameters or {}, max_iterations)
    else:
        raise ValueError("supported devices: cpw_resonator, idc_capacitor, josephson_junction")

    report = OptimizationReport(
        status="ok",
        device=d,
        target={k: float(v) for k, v in target.items()},
        final_parameters=result["final_parameters"],
        final_metrics=result["final_metrics"],
        history=result["history"],
        solver_status="skipped",
        notes=[
            "Geometry/extraction optimization complete.",
            "No EM solver was executed inside optimize_device; run openEMS/FastCap/FastHenry for signoff.",
        ],
    ).model_dump(mode="json")
    if output_path is not None:
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, indent=2), encoding="utf-8")
        report["report_path"] = str(out)
    return report


def _optimize_cpw(
    target: dict[str, float], initial: dict[str, float], max_iterations: int
) -> dict[str, Any]:
    target_z0 = float(target.get("z0_ohm", target.get("impedance_ohm", 50.0)))
    target_f = float(target.get("frequency_ghz", target.get("target_frequency_ghz", 6.0)))
    eps = float(initial.get("epsilon_r", target.get("epsilon_r", 6.2)))
    params = {
        "center_width_um": float(initial.get("center_width_um", 10.0)),
        "gap_um": float(initial.get("gap_um", 6.0)),
        "ground_width_um": float(initial.get("ground_width_um", 500.0)),
        "substrate_thickness_um": float(initial.get("substrate_thickness_um", 254.0)),
        "epsilon_r": eps,
    }

    def evaluate(p: dict[str, float]) -> dict[str, float]:
        cpw = synthesize_cpw(
            center_width_um=p["center_width_um"],
            gap_um=p["gap_um"],
            ground_width_um=p["ground_width_um"],
            epsilon_r=p["epsilon_r"],
            substrate_thickness_um=p["substrate_thickness_um"],
            frequency_ghz=target_f,
            target_impedance_ohm=target_z0,
            impedance_tolerance_ohm=1e9,
        )
        length_um = float(cpw["quarter_wave_length_um"])
        f0 = float(cpw["phase_velocity_m_per_s"]) / (4.0 * length_um * 1e-6) / 1e9
        return {"z0_ohm": float(cpw["impedance_ohm"]), "f0_ghz": f0, "length_um": length_um}

    return _coordinate_search(params, evaluate, {"z0_ohm": target_z0, "f0_ghz": target_f}, ["center_width_um", "gap_um"], max_iterations)


def _optimize_idc(
    target: dict[str, float], initial: dict[str, float], max_iterations: int
) -> dict[str, Any]:
    target_pf = float(target.get("capacitance_pf", target.get("c_pf", 0.6)))
    params = {
        "finger_count": float(initial.get("finger_count", 12.0)),
        "finger_length_um": float(initial.get("finger_length_um", 120.0)),
        "finger_gap_um": float(initial.get("finger_gap_um", 2.0)),
    }

    def evaluate(p: dict[str, float]) -> dict[str, float]:
        count = max(round(p["finger_count"]), 2)
        cap_pf = 1.5e-4 * (count - 1) * p["finger_length_um"] / max(p["finger_gap_um"], 0.1)
        return {"capacitance_pf": cap_pf, "finger_count": float(count)}

    return _coordinate_search(params, evaluate, {"capacitance_pf": target_pf}, ["finger_count", "finger_length_um", "finger_gap_um"], max_iterations)


def _optimize_jj(
    target: dict[str, float], initial: dict[str, float], max_iterations: int
) -> dict[str, Any]:
    target_ic = float(target.get("ic_ua", target.get("target_ic_ua", 0.1)))
    jc = float(target.get("jc_ua_per_um2", initial.get("jc_ua_per_um2", 2.0)))
    area = target_ic / jc
    side = math.sqrt(area)
    params = {
        "junction_width_um": float(initial.get("junction_width_um", side)),
        "junction_height_um": float(initial.get("junction_height_um", side)),
        "jc_ua_per_um2": jc,
    }

    def evaluate(p: dict[str, float]) -> dict[str, float]:
        area_um2 = p["junction_width_um"] * p["junction_height_um"]
        ic_ua = area_um2 * p["jc_ua_per_um2"]
        lj_h = PHI0_WB / (2.0 * math.pi * ic_ua * 1e-6)
        return {"area_um2": area_um2, "ic_ua": ic_ua, "lj_h": lj_h}

    return _coordinate_search(params, evaluate, {"ic_ua": target_ic}, ["junction_width_um", "junction_height_um"], max_iterations)


def _coordinate_search(
    params: dict[str, float],
    evaluate: Any,
    targets: dict[str, float],
    variables: list[str],
    max_iterations: int,
) -> dict[str, Any]:
    history: list[OptimizationIteration] = []
    steps = {name: max(abs(params[name]) * 0.25, 0.1) for name in variables}
    best_params = dict(params)
    best_metrics = evaluate(best_params)
    best_objective = _objective(best_metrics, targets)

    for iteration in range(max_iterations):
        improved = False
        for name in variables:
            for sign in (-1.0, 1.0):
                candidate = dict(best_params)
                candidate[name] = max(candidate[name] + sign * steps[name], 0.05)
                metrics = evaluate(candidate)
                obj = _objective(metrics, targets)
                if obj < best_objective:
                    best_params, best_metrics, best_objective = candidate, metrics, obj
                    improved = True
        history.append(
            OptimizationIteration(
                iteration=iteration,
                parameters=dict(best_params),
                metrics=dict(best_metrics),
                objective=best_objective,
                simulation={"status": "skipped", "reason": "no external solver executed"},
            )
        )
        if not improved:
            for key in steps:
                steps[key] *= 0.5
        if best_objective < 1e-6:
            break
    return {
        "final_parameters": best_params,
        "final_metrics": best_metrics,
        "history": history,
    }


def _objective(metrics: dict[str, float], targets: dict[str, float]) -> float:
    total = 0.0
    for key, target in targets.items():
        value = metrics[key]
        scale = max(abs(target), 1e-12)
        total += ((value - target) / scale) ** 2
    return total
