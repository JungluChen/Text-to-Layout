"""Simulation routing for verified Text-to-Layout geometry."""

from __future__ import annotations

from pathlib import Path

from textlayout.models import Geometry, Technology
from textlayout.schemas.dsl import LayoutSpec
from textlayout.simulation.fastercap import prepare_idc_fastercap, run_fastercap
from textlayout.simulation.models import SimulationResult


def simulate_layout(
    spec: LayoutSpec,
    geometry: Geometry,
    technology: Technology,
    output_dir: str | Path,
    *,
    solver: str = "auto",
    execute: bool = False,
    executable: str | None = None,
) -> SimulationResult:
    """Prepare or execute a supported open-source simulation."""
    selected = "fastercap" if solver == "auto" and spec.component == "IDC" else solver.lower()
    if spec.component == "IDC" and selected in {"fastcap", "fastercap"}:
        prepared = prepare_idc_fastercap(spec, geometry, technology, output_dir)
        return run_fastercap(prepared, executable=executable) if execute else prepared

    recommendations = {
        "CPW": "openEMS model preparation is blocked until explicit RF and ground-reference ports exist.",
        "SpiralInductor": "FastHenry preparation is blocked until a deterministic spiral generator exists.",
        "QuarterWaveResonator": "openEMS preparation is blocked until a benchmark-ready resonator topology exists.",
        "SQUID": "Electrostatic simulation is not signoff without a foundry-specific junction stack.",
    }
    return SimulationResult(
        status="planned",
        solver=selected,
        readiness_level=1,
        reason=recommendations.get(spec.component, "No open-source simulation adapter is registered."),
        output_dir=Path(output_dir),
    )
