"""Simulation routing for verified Text-to-Layout geometry."""

from __future__ import annotations

from pathlib import Path

from textlayout.models import Geometry, Technology
from textlayout.schemas.dsl import LayoutSpec
from dataclasses import replace

from textlayout.simulation.adapters import FasterCapAdapter, adapter_for
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
    tolerance_pct: float | None = None,
) -> SimulationResult:
    """Prepare or (when ``execute``) run a supported open-source simulation.

    Execution is always graceful: a missing solver yields ``status="skipped"``
    (evidence stage ``solver_missing``), never an exception, and the prepared
    input files remain on disk.
    """
    selected = (
        "fastercap"
        if solver == "auto" and spec.component in {"IDC", "TestStructure"}
        else solver.lower()
    )
    if spec.component == "IDC" and selected in {"fastcap", "fastercap"}:
        return _run_adapter(spec, geometry, technology, output_dir, execute, executable, tolerance_pct)
    if spec.component == "TestStructure" and selected in {"fastcap", "fastercap"}:
        # Only the documented extraction region (the embedded IDC) is solved;
        # launches, feeds, and ground planes are explicitly out of model.
        idc_spec, idc_geometry = _test_structure_extraction_view(spec, geometry)
        return _run_adapter(idc_spec, idc_geometry, technology, output_dir, execute, executable, tolerance_pct)

    if spec.component == "CPW" and selected in {"auto", "openems"}:
        return _run_adapter(spec, geometry, technology, output_dir, execute, executable, tolerance_pct)
    if spec.component == "SpiralInductor" and selected in {"auto", "fasthenry", "fasthenry2"}:
        return _run_adapter(spec, geometry, technology, output_dir, execute, executable, tolerance_pct)
    if spec.component == "QuarterWaveResonator" and selected in {"auto", "openems"}:
        return _run_adapter(spec, geometry, technology, output_dir, execute, executable, tolerance_pct)
    if spec.component == "SQUID" and selected in {"auto", "josim"}:
        return _run_adapter(spec, geometry, technology, output_dir, execute, executable, tolerance_pct)

    return SimulationResult(
        status="planned",
        solver=selected,
        readiness_level=1,
        reason=f"Solver {selected!r} is not registered for component {spec.component!r}.",
        output_dir=Path(output_dir),
    )


def _test_structure_extraction_view(
    spec: LayoutSpec, geometry: Geometry
) -> tuple[LayoutSpec, Geometry]:
    """Slice the embedded IDC out of a TestStructure for capacitance extraction."""
    region = geometry.metadata.get("extraction_region")
    if not isinstance(region, dict) or region.get("component") != "IDC":
        raise ValueError("TestStructure geometry does not declare an IDC extraction region")
    start = int(region["polygon_start"])
    count = int(region["polygon_count"])
    idc_polygons = geometry.polygons[start : start + count]
    idc_metadata = geometry.metadata.get("idc")
    idc_geometry = Geometry(
        name="IDC",
        polygons=idc_polygons,
        metadata=dict(idc_metadata) if isinstance(idc_metadata, dict) else {},
    )
    idc_spec = LayoutSpec(
        component="IDC",
        technology=spec.technology,
        target=dict(spec.target),
        parameters=dict(region["parameters"]),
        metadata={
            "derived_from": "TestStructure",
            "extraction_note": str(region.get("excluded", "")),
        },
    )
    return idc_spec, idc_geometry


def _run_adapter(
    spec: LayoutSpec,
    geometry: Geometry,
    technology: Technology,
    output_dir: str | Path,
    execute: bool,
    executable: str | None,
    tolerance_pct: float | None = None,
) -> SimulationResult:
    """Apply the common prepare/execute lifecycle for every registered adapter."""
    adapter = adapter_for(spec)
    if tolerance_pct is not None and isinstance(adapter, FasterCapAdapter):
        adapter = replace(adapter, tolerance_pct=tolerance_pct)
    prepared = adapter.prepare(spec, geometry, technology, output_dir)
    if not execute or prepared.status != "input_files_prepared":
        return prepared
    return adapter.execute(prepared, executable=executable)
