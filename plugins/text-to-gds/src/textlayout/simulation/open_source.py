"""Honest input preparation for openEMS and FastHenry benchmarks."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from textlayout.models import Geometry, Technology
from textlayout.schemas.dsl import LayoutSpec
from textlayout.simulation.models import SimulationResult


def prepare_cpw_openems(
    spec: LayoutSpec, geometry: Geometry, technology: Technology, output_dir: str | Path
) -> SimulationResult:
    return _prepare_openems(
        spec,
        geometry,
        technology,
        output_dir,
        expected=("Z0", "S11", "S21", "effective_permittivity"),
    )


def prepare_resonator_openems(
    spec: LayoutSpec, geometry: Geometry, technology: Technology, output_dir: str | Path
) -> SimulationResult:
    return _prepare_openems(
        spec,
        geometry,
        technology,
        output_dir,
        expected=("resonance_frequency", "loaded_Q", "S21"),
    )


def _prepare_openems(
    spec: LayoutSpec,
    geometry: Geometry,
    technology: Technology,
    output_dir: str | Path,
    *,
    expected: tuple[str, ...],
) -> SimulationResult:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    config = out / "openems_model.json"
    bbox = geometry.bbox()
    payload = {
        "status": "input_files_prepared",
        "solver": "openEMS",
        "component": spec.component,
        "technology": technology.name,
        "substrate_epsilon_r": technology.substrate_epsilon_r,
        "bbox_um": [bbox.xmin, bbox.ymin, bbox.xmax, bbox.ymax],
        "ports": [
            {
                "name": port.name,
                "center_um": list(port.center),
                "width_um": port.width,
                "orientation_deg": port.orientation,
                "layer": port.layer,
            }
            for port in geometry.ports
        ],
        "expected_outputs": list(expected),
        "execution": "not_run",
    }
    config.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    warnings = (
        "The JSON is a solver-input manifest, not a mesh or solver result.",
        "Port calibration, boundary placement, mesh convergence, and Touchstone output remain required.",
    )
    manifest = _write_manifest(out, "openEMS", spec.component, expected, warnings)
    return SimulationResult(
        status="input_files_prepared",
        solver="openEMS",
        readiness_level=2,
        reason="Verified geometry, material assumptions, ports, and expected outputs were serialized.",
        output_dir=out,
        artifacts={"model": str(config), "manifest": str(manifest)},
        warnings=warnings,
    )


def prepare_spiral_fasthenry(
    spec: LayoutSpec, geometry: Geometry, technology: Technology, output_dir: str | Path
) -> SimulationResult:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    points = geometry.metadata.get("centerline_points_um")
    if not isinstance(points, list) or len(points) < 2:
        return SimulationResult(
            status="failed",
            solver="FastHenry",
            readiness_level=1,
            reason="Continuous centerline metadata is missing.",
            output_dir=out,
        )
    width = float(geometry.metadata["trace_width_um"])
    thickness = float(geometry.metadata["thickness_um"])
    lines = [
        "* Text-to-Layout square spiral",
        ".units um",
        ".default sigma=5.8e4",
    ]
    for index, point in enumerate(points, 1):
        x, y = point
        lines.append(f"N{index} x={x:.9g} y={y:.9g} z=0")
    for index in range(1, len(points)):
        lines.append(
            f"E{index} N{index} N{index + 1} w={width:.9g} h={thickness:.9g}"
        )
    lines.extend((f".external N1 N{len(points)}", ".freq fmin=1e6 fmax=1e10 ndec=20", ".end"))
    input_path = out / "spiral.inp"
    input_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    warnings = (
        "FastHenry has not been executed; no inductance, resistance, or Q result is claimed.",
        "Conductor conductivity and thickness are generic and require process replacement.",
    )
    manifest = _write_manifest(
        out, "FastHenry", spec.component, ("inductance", "resistance", "Q"), warnings
    )
    return SimulationResult(
        status="input_files_prepared",
        solver="FastHenry",
        readiness_level=2,
        reason="A continuous centerline and conductor cross-section were written as FastHenry input.",
        output_dir=out,
        artifacts={"input": str(input_path), "manifest": str(manifest)},
        warnings=warnings,
    )


def prepare_squid_plan(
    spec: LayoutSpec, geometry: Geometry, output_dir: str | Path
) -> SimulationResult:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    warnings = (
        "The two JJ polygons are generic process placeholders.",
        "No loop-inductance or Josephson simulation is valid until a foundry stack, Ic, and thickness are supplied.",
    )
    manifest = _write_manifest(
        out, "planned:FastHenry+Josephson-circuit-solver", spec.component, (), warnings, level=1
    )
    return SimulationResult(
        status="planned",
        solver="FastHenry + Josephson circuit solver",
        readiness_level=1,
        reason="Geometry exists, but process-specific junction and conductor parameters are absent.",
        output_dir=out,
        artifacts={"manifest": str(manifest)},
        warnings=warnings,
    )


def _write_manifest(
    out: Path,
    solver: str,
    component: str,
    expected: tuple[str, ...],
    warnings: tuple[str, ...],
    *,
    level: int = 2,
) -> Path:
    target = out / "simulation_manifest.json"
    data: dict[str, Any] = {
        "status": "input_files_prepared" if level >= 2 else "planned",
        "solver": solver,
        "component": component,
        "readiness_level": level,
        "expected_outputs": list(expected),
        "warnings": list(warnings),
        "solver_executed": False,
    }
    target.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return target

