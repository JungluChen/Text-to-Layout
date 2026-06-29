"""Deterministic geometry tests for the visual benchmark generators."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from textlayout import LayoutSpec, build_default_workflow
from textlayout.simulation import simulate_layout

ROOT = Path(__file__).parents[2]
BENCHMARKS = ROOT / "examples" / "benchmarks"


def _run(folder: str):
    spec = LayoutSpec.model_validate_json(
        (BENCHMARKS / folder / "layout.json").read_text(encoding="utf-8")
    )
    workflow = build_default_workflow()
    result = workflow.run(spec, formats=("json",))
    assert result.report.passed
    return workflow, spec, result


def test_cpw_has_explicit_signal_and_ground_reference_ports() -> None:
    _, _, result = _run("02_cpw_50ohm")
    assert {port.name for port in result.geometry.ports} == {
        "RF_IN",
        "RF_OUT",
        "GND_L_IN",
        "GND_L_OUT",
        "GND_R_IN",
        "GND_R_OUT",
    }
    assert result.geometry.metadata["estimated_z0_ohm"] == pytest.approx(50.0412)


def test_spiral_is_continuous_two_port_geometry() -> None:
    _, _, result = _run("03_spiral_inductor")
    assert len(result.geometry.ports) == 2
    assert result.geometry.metadata["turns"] == 4
    assert result.geometry.metadata["estimated_inductance_nh"] == pytest.approx(1.981, rel=1e-3)
    assert len(result.geometry.metadata["centerline_points_um"]) > 8


def test_resonator_has_coupled_open_and_grounded_short() -> None:
    _, _, result = _run("04_quarter_wave_resonator")
    assert len(result.geometry.ports) == 6
    assert result.geometry.metadata["boundary_open"]
    assert result.geometry.metadata["boundary_short"] == "ground bridge"
    assert result.geometry.metadata["electrical_length_um"] == pytest.approx(4918.4652)
    signal = result.geometry.polygons[0].bbox
    lower_ground_left = result.geometry.polygons[6].bbox
    lower_ground_right = result.geometry.polygons[7].bbox
    assert signal.xmin - lower_ground_left.xmax == pytest.approx(6.0)
    assert lower_ground_right.xmin - signal.xmax == pytest.approx(6.0)


def test_squid_has_symmetric_two_junction_placeholder_geometry() -> None:
    _, _, result = _run("05_squid_loop")
    assert result.geometry.metadata["junction_count"] == 2
    assert result.geometry.metadata["loop_area_um2"] == 400.0
    assert result.geometry.metadata["foundry_stack_required"] is True
    assert len(result.geometry.on_layer("JJ")) == 2


@pytest.mark.parametrize(
    ("folder", "level", "artifact"),
    [
        ("02_cpw_50ohm", 2, "openems_model.json"),
        ("03_spiral_inductor", 2, "spiral.inp"),
        ("04_quarter_wave_resonator", 2, "openems_model.json"),
        ("05_squid_loop", 1, "simulation_manifest.json"),
    ],
)
def test_simulation_preparation_matches_readiness(
    tmp_path: Path, folder: str, level: int, artifact: str
) -> None:
    workflow, spec, generated = _run(folder)
    result = simulate_layout(
        spec,
        generated.geometry,
        workflow.technology(spec.technology),
        tmp_path,
    )
    assert result.readiness_level == level
    assert (tmp_path / artifact).is_file()
    manifest = json.loads((tmp_path / "simulation_manifest.json").read_text(encoding="utf-8"))
    assert manifest["solver_executed"] is False
