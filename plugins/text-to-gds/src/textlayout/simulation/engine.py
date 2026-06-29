"""Simulation routing for verified Text-to-Layout geometry."""

from __future__ import annotations

from pathlib import Path

from textlayout.models import Geometry, Technology
from textlayout.schemas.dsl import LayoutSpec
from textlayout.simulation.fastercap import prepare_idc_fastercap, run_fastercap
from textlayout.simulation.models import SimulationResult
from textlayout.simulation.open_source import (
    prepare_cpw_openems,
    prepare_resonator_openems,
    prepare_spiral_fasthenry,
    prepare_squid_plan,
)


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

    if spec.component == "CPW" and selected in {"auto", "openems"}:
        return prepare_cpw_openems(spec, geometry, technology, output_dir)
    if spec.component == "SpiralInductor" and selected in {"auto", "fasthenry", "fasthenry2"}:
        return prepare_spiral_fasthenry(spec, geometry, technology, output_dir)
    if spec.component == "QuarterWaveResonator" and selected in {"auto", "openems"}:
        return prepare_resonator_openems(spec, geometry, technology, output_dir)
    if spec.component == "SQUID" and selected in {"auto", "fasthenry"}:
        return prepare_squid_plan(spec, geometry, output_dir)

    return SimulationResult(
        status="planned",
        solver=selected,
        readiness_level=1,
        reason=f"Solver {selected!r} is not registered for component {spec.component!r}.",
        output_dir=Path(output_dir),
    )
