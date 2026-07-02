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
from textlayout.simulation.runners import run_fasthenry, run_openems


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
        prepared = prepare_idc_fastercap(spec, geometry, technology, output_dir)
        if not execute:
            return prepared
        return run_fastercap(
            prepared,
            executable=executable,
            target_capacitance_pf=spec.target.get("capacitance_pf"),
        )

    if spec.component == "CPW" and selected in {"auto", "openems"}:
        prepared = prepare_cpw_openems(spec, geometry, technology, output_dir)
        return _maybe_run_openems(prepared, spec, execute, executable)
    if spec.component == "SpiralInductor" and selected in {"auto", "fasthenry", "fasthenry2"}:
        prepared = prepare_spiral_fasthenry(spec, geometry, technology, output_dir)
        if not execute:
            return prepared
        target_h = spec.target.get("inductance_h") or spec.target.get("inductance_nh")
        if target_h and spec.target.get("inductance_nh") and not spec.target.get("inductance_h"):
            target_h = float(target_h) * 1e-9
        return run_fasthenry(
            prepared, target_inductance_h=target_h, executable=executable
        )
    if spec.component == "QuarterWaveResonator" and selected in {"auto", "openems"}:
        prepared = prepare_resonator_openems(spec, geometry, technology, output_dir)
        return _maybe_run_openems(prepared, spec, execute, executable)
    if spec.component == "SQUID" and selected in {"auto", "fasthenry"}:
        return prepare_squid_plan(spec, geometry, output_dir)

    return SimulationResult(
        status="planned",
        solver=selected,
        readiness_level=1,
        reason=f"Solver {selected!r} is not registered for component {spec.component!r}.",
        output_dir=Path(output_dir),
    )


def _maybe_run_openems(
    prepared: SimulationResult,
    spec: LayoutSpec,
    execute: bool,
    executable: str | None,
) -> SimulationResult:
    """Return the prepared openEMS input, or post-process a Touchstone if asked."""
    if not execute:
        return prepared
    frequency_ghz = spec.target.get("frequency_ghz")
    return run_openems(
        prepared, target_frequency_ghz=frequency_ghz, executable=executable
    )
