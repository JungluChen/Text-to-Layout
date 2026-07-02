"""Simulation routing for verified Text-to-Layout geometry."""

from __future__ import annotations

from pathlib import Path

from textlayout.models import Geometry, Technology
from textlayout.schemas.dsl import LayoutSpec
from textlayout.simulation.adapters import adapter_for
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
    """Prepare or (when ``execute``) run a supported open-source simulation.

    Execution is always graceful: a missing solver yields ``status="skipped"``
    (evidence stage ``solver_missing``), never an exception, and the prepared
    input files remain on disk.
    """
    selected = "fastercap" if solver == "auto" and spec.component == "IDC" else solver.lower()
    if spec.component == "IDC" and selected in {"fastcap", "fastercap"}:
        return _run_adapter(spec, geometry, technology, output_dir, execute, executable)

    if spec.component == "CPW" and selected in {"auto", "openems"}:
        return _run_adapter(spec, geometry, technology, output_dir, execute, executable)
    if spec.component == "SpiralInductor" and selected in {"auto", "fasthenry", "fasthenry2"}:
        return _run_adapter(spec, geometry, technology, output_dir, execute, executable)
    if spec.component == "QuarterWaveResonator" and selected in {"auto", "openems"}:
        return _run_adapter(spec, geometry, technology, output_dir, execute, executable)
    if spec.component == "SQUID" and selected in {"auto", "josim"}:
        return _run_adapter(spec, geometry, technology, output_dir, execute, executable)

    return SimulationResult(
        status="planned",
        solver=selected,
        readiness_level=1,
        reason=f"Solver {selected!r} is not registered for component {spec.component!r}.",
        output_dir=Path(output_dir),
    )


def _run_adapter(
    spec: LayoutSpec,
    geometry: Geometry,
    technology: Technology,
    output_dir: str | Path,
    execute: bool,
    executable: str | None,
) -> SimulationResult:
    """Apply the common prepare/execute lifecycle for every registered adapter."""
    adapter = adapter_for(spec)
    prepared = adapter.prepare(spec, geometry, technology, output_dir)
    if not execute or prepared.status != "input_files_prepared":
        return prepared
    return adapter.execute(prepared, executable=executable)
