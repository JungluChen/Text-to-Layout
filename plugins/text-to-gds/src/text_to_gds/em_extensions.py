"""Solver comparison, convergence, rational fitting, caching, and EM feedback."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Any

import numpy as np

from text_to_gds.em_solvers import get_em_solver
from text_to_gds.extraction import layer_bounding_boxes_from_gds
from text_to_gds.pdk import load_pdk


def build_universal_3d_model(
    gds_path: str | Path, *, process_path: str | Path
) -> dict[str, Any]:
    """Convert GDS layers into a solver-neutral stack of extruded footprints."""
    pdk = load_pdk(process_path)
    boxes = layer_bounding_boxes_from_gds(gds_path)
    z_nm = 0.0
    elevations = {}
    for name, layer in pdk.layers.items():
        elevations[name] = [z_nm, z_nm + layer.thickness_nm]
        z_nm += layer.thickness_nm
    solids = []
    for box in boxes:
        layer = pdk.layer_for_gds(*box["layer"])
        solids.append(
            {
                "name": f"{layer.name}_{len(solids)}",
                "layer": layer.name,
                "material": layer.material,
                "bbox_um": box["bbox_um"],
                "z_um": [value / 1000.0 for value in elevations[layer.name]],
            }
        )
    return {
        "schema": "text-to-gds.universal-3d-model.v1",
        "source_gds": str(gds_path),
        "process": f"{pdk.process_id}@{pdk.version}",
        "solids": solids,
        "compatible_backends": ["HFSS", "openEMS", "Palace", "Sonnet", "Elmer", "FastHenry", "FastCap"],
    }


def compare_em_solvers(
    gds_path: str | Path,
    *,
    output_root: str | Path,
    sidecar: dict[str, Any],
    process_path: str | Path | None = None,
    solvers: tuple[str, ...] = ("HFSS", "openEMS", "Palace", "Sonnet"),
    setup_frequency_ghz: float = 6.0,
) -> dict[str, Any]:
    """Prepare identical geometry for multiple solvers and report availability."""
    root = Path(output_root)
    root.mkdir(parents=True, exist_ok=True)
    results = []
    for name in solvers:
        solver = get_em_solver(name)
        try:
            prepared = solver.prepare(
                gds_path,
                output_stem=root / name.lower(),
                sidecar=sidecar,
                process_path=process_path,
                setup_frequency_ghz=setup_frequency_ghz,
            )
            status = "prepared"
        except Exception as exc:
            prepared, status = {"error": str(exc)}, "unavailable_or_invalid"
        results.append({"solver": name, "available": solver.available(), "status": status, "result": prepared})
    return {"schema": "text-to-gds.em-solver-comparison.v1", "solvers": results}


def mesh_convergence_analysis(
    samples: list[dict[str, float]], *, metric: str = "frequency_ghz", tolerance_fraction: float = 1e-3
) -> dict[str, Any]:
    """Assess convergence from ordered mesh-size/metric samples."""
    if len(samples) < 2:
        raise ValueError("At least two mesh samples are required")
    ordered = sorted(samples, key=lambda item: float(item["mesh_size_um"]), reverse=True)
    values = np.asarray([float(item[metric]) for item in ordered])
    relative_changes = np.abs(np.diff(values) / np.maximum(np.abs(values[1:]), 1e-30))
    converged = bool(relative_changes[-1] <= tolerance_fraction)
    return {
        "schema": "text-to-gds.mesh-convergence.v1",
        "samples": ordered,
        "relative_changes": relative_changes.tolist(),
        "estimated_relative_error": float(relative_changes[-1]),
        "converged": converged,
        "recommended_mesh_size_um": float(ordered[-1]["mesh_size_um"]),
    }


def adaptive_mesh_plan(
    *, base_mesh_um: float, feature_sizes_um: list[float], field_gradient_scores: list[float] | None = None
) -> dict[str, Any]:
    if base_mesh_um <= 0.0 or not feature_sizes_um:
        raise ValueError("Positive base mesh and feature sizes are required")
    gradients = field_gradient_scores or [0.0] * len(feature_sizes_um)
    if len(gradients) != len(feature_sizes_um):
        raise ValueError("Gradient score count must match feature count")
    regions = []
    for index, (feature, gradient) in enumerate(zip(feature_sizes_um, gradients, strict=True)):
        mesh = min(base_mesh_um, feature / 5.0) / (1.0 + max(gradient, 0.0))
        regions.append({"region": index, "feature_size_um": feature, "gradient_score": gradient, "mesh_size_um": mesh})
    return {"base_mesh_um": base_mesh_um, "regions": regions, "minimum_mesh_um": min(row["mesh_size_um"] for row in regions)}


def em_error_estimate(*, discretization_error: float, port_error: float, material_error: float, convergence_error: float) -> dict[str, float]:
    terms = np.asarray([discretization_error, port_error, material_error, convergence_error], dtype=float)
    if np.any(terms < 0.0):
        raise ValueError("Error terms must be non-negative")
    return {"combined_relative_uncertainty": float(np.sqrt(np.sum(terms**2))), "worst_case_relative_uncertainty": float(np.sum(terms))}


def validate_em_result(result: dict[str, Any]) -> dict[str, Any]:
    checks = {
        "solver_identified": bool(result.get("solver") or result.get("engine")),
        "frequency_sweep_present": bool(result.get("frequencies_hz") or result.get("frequency_ghz") or result.get("samples")),
        "ports_present": bool(result.get("ports") or result.get("port_count")),
        "mesh_evidence_present": bool(result.get("mesh") or result.get("mesh_convergence")),
        "passivity_checked": result.get("passivity_checked") is True,
        "convergence_checked": result.get("converged") is True or result.get("mesh_convergence", {}).get("converged") is True,
    }
    return {"schema": "text-to-gds.em-validation.v1", "passed": all(checks.values()), "checks": checks, "missing": [key for key, value in checks.items() if not value]}


def vector_fit(
    frequencies_hz: list[float], response: list[complex], *, order: int = 4
) -> dict[str, Any]:
    """Least-squares fixed-pole rational fit suitable for passive-ROM seeding."""
    frequencies = np.asarray(frequencies_hz, dtype=float)
    values = np.asarray(response, dtype=complex)
    if frequencies.size != values.size or frequencies.size < order + 2:
        raise ValueError("Response length must match frequencies and exceed fit order")
    omega = 2.0 * np.pi * frequencies
    scale = float(np.max(omega))
    poles = -np.geomspace(max(scale / 1e4, 1.0), scale, order).astype(complex)
    matrix = np.column_stack([1.0 / (1j * omega - pole) for pole in poles] + [np.ones_like(omega), 1j * omega])
    coefficients = np.linalg.lstsq(matrix, values, rcond=None)[0]
    fitted = matrix @ coefficients
    error = np.linalg.norm(fitted - values) / max(np.linalg.norm(values), 1e-30)
    def encode(value: complex) -> list[float]:
        return [float(value.real), float(value.imag)]
    return {
        "schema": "text-to-gds.rational-model.v1",
        "poles": [encode(value) for value in poles],
        "residues": [encode(value) for value in coefficients[:order]],
        "direct": encode(coefficients[-2]),
        "proportional": encode(coefficients[-1]),
        "relative_rms_error": float(error),
        "stable": bool(np.all(np.real(poles) < 0.0)),
    }


def lumped_element_fit(frequencies_hz: list[float], impedance_ohm: list[complex]) -> dict[str, float]:
    """Fit series R/L/C from complex impedance over frequency."""
    frequency = np.asarray(frequencies_hz, dtype=float)
    impedance = np.asarray(impedance_ohm, dtype=complex)
    omega = 2.0 * np.pi * frequency
    resistance = float(np.median(impedance.real))
    # Im(Z) = omega*L - 1/(omega*C), linear in [omega, -1/omega].
    design = np.column_stack([omega, -1.0 / omega])
    inductance, inverse_capacitance = np.linalg.lstsq(design, impedance.imag, rcond=None)[0]
    capacitance = 1.0 / max(inverse_capacitance, 1e-30)
    fitted = resistance + 1j * (omega * inductance - 1.0 / (omega * capacitance))
    return {"resistance_ohm": resistance, "inductance_h": float(inductance), "capacitance_f": float(capacitance), "relative_error": float(np.linalg.norm(fitted - impedance) / max(np.linalg.norm(impedance), 1e-30))}


def reduced_order_model(rational_model: dict[str, Any]) -> dict[str, Any]:
    poles = [complex(*value) for value in rational_model["poles"]]
    residues = [complex(*value) for value in rational_model["residues"]]
    return {
        "schema": "text-to-gds.state-space-rom.v1",
        "A": [[[float(pole.real), float(pole.imag)] if row == column else [0.0, 0.0] for column in range(len(poles))] for row, pole in enumerate(poles)],
        "B": [[1.0, 0.0] for _ in poles],
        "C": [[float(value.real), float(value.imag)] for value in residues],
        "D": rational_model["direct"],
    }


def em_to_circuit_feedback(*, target_frequency_ghz: float, simulated_frequency_ghz: float, target_impedance_ohm: float, simulated_impedance_ohm: float) -> dict[str, float]:
    if min(target_frequency_ghz, simulated_frequency_ghz, target_impedance_ohm, simulated_impedance_ohm) <= 0.0:
        raise ValueError("Feedback values must be positive")
    return {"length_scale": simulated_frequency_ghz / target_frequency_ghz, "capacitance_scale": (simulated_frequency_ghz / target_frequency_ghz) ** 2, "gap_scale": target_impedance_ohm / simulated_impedance_ohm}


def initialize_em_cache(path: str | Path) -> Path:
    database = Path(path)
    database.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE IF NOT EXISTS em_results (key TEXT PRIMARY KEY, created_at TEXT DEFAULT CURRENT_TIMESTAMP, input_json TEXT NOT NULL, result_json TEXT NOT NULL)")
    return database


def cache_em_result(path: str | Path, inputs: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    database = initialize_em_cache(path)
    input_json = json.dumps(inputs, sort_keys=True, separators=(",", ":"))
    key = hashlib.sha256(input_json.encode()).hexdigest()
    with sqlite3.connect(database) as connection:
        connection.execute("INSERT OR REPLACE INTO em_results(key, input_json, result_json) VALUES (?, ?, ?)", (key, input_json, json.dumps(result)))
    return {"cache_key": key, "database_path": str(database)}


def get_cached_em_result(path: str | Path, inputs: dict[str, Any]) -> dict[str, Any] | None:
    input_json = json.dumps(inputs, sort_keys=True, separators=(",", ":"))
    key = hashlib.sha256(input_json.encode()).hexdigest()
    with sqlite3.connect(path) as connection:
        row = connection.execute("SELECT result_json FROM em_results WHERE key=?", (key,)).fetchone()
    return json.loads(row[0]) if row else None
