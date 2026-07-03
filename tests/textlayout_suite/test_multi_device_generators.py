"""TestStructure and TestChip generators: geometry, metadata, extraction view."""

from __future__ import annotations

from pathlib import Path

from textlayout import build_default_workflow
from textlayout.prompt import parse_prompt
from textlayout.schemas.dsl import LayoutSpec
from textlayout.simulation import simulate_layout
from textlayout.simulation.engine import _test_structure_extraction_view


def _build(component: str, parameters: dict | None = None):
    workflow = build_default_workflow()
    spec = LayoutSpec(
        component=component,
        parameters=parameters or {},
        outputs={"gds": True, "svg": False, "png": False, "json": False},
    )
    return workflow, spec, workflow.run(spec, formats=())


def test_test_structure_generates_and_verifies() -> None:
    _, _, result = _build("TestStructure")
    assert result.report.passed
    port_names = {port.name for port in result.geometry.ports}
    assert {"P1", "P2", "GND_L", "GND_R"} <= port_names
    region = result.geometry.metadata["extraction_region"]
    assert region["component"] == "IDC"
    assert "NOT simulated" in region["excluded"]


def test_test_structure_extraction_view_is_exactly_the_idc() -> None:
    workflow, spec, result = _build("TestStructure")
    idc_spec, idc_geometry = _test_structure_extraction_view(spec, result.geometry)
    assert idc_spec.component == "IDC"
    pairs = int(idc_spec.parameters["finger_pairs"])
    assert len(idc_geometry.polygons) == 2 + 2 * pairs
    # The sliced polygons must be byte-identical to the embedded sub-geometry.
    region = result.geometry.metadata["extraction_region"]
    start, count = int(region["polygon_start"]), int(region["polygon_count"])
    assert idc_geometry.polygons == result.geometry.polygons[start : start + count]


def test_test_structure_fastercap_input_covers_only_idc(tmp_path: Path) -> None:
    workflow, spec, result = _build("TestStructure")
    prepared = simulate_layout(
        spec,
        result.geometry,
        workflow.technology(spec.technology),
        tmp_path,
        execute=False,
    )
    assert prepared.status == "input_files_prepared"
    panel_text = Path(prepared.artifacts["panel_file"]).read_text(encoding="ascii")
    pairs = int(spec.parameters.get("finger_pairs", 20))
    q_panels = [line for line in panel_text.splitlines() if line.startswith("Q ")]
    assert len(q_panels) == 2 + 2 * pairs  # IDC only: no launch/feed/ground panels


def test_test_chip_tile_geometry() -> None:
    _, _, result = _build("TestChip", {"tile_width_um": 2000.0, "tile_height_um": 2000.0})
    assert result.report.passed
    bbox = result.geometry.bbox()
    assert (round(bbox.width, 3), round(bbox.height, 3)) == (2000.0, 2000.0)
    layers = set(result.geometry.layers())
    assert {"M1", "TEXT"} <= layers
    port_names = {port.name for port in result.geometry.ports}
    assert any(name.startswith("IDC_") for name in port_names)
    assert any(name.startswith("CPW_") for name in port_names)
    assert any(name.startswith("SP_") for name in port_names)
    scope = result.geometry.metadata["simulation_scope"]
    assert "geometry-only" in scope["CPW"]


def test_prompt_parses_test_structure_and_test_chip() -> None:
    ts = parse_prompt(
        "Create a test structure with a 0.6 pF IDC connected to two 50 ohm CPW feedlines"
    )
    assert ts.component == "TestStructure"
    assert ts.target["capacitance_pf"] == 0.6

    chip = parse_prompt(
        "Create a 2 mm by 2 mm research test chip tile containing a 0.6 pF IDC, "
        "a 50 ohm CPW line, a spiral inductor, alignment marks, and a title text label."
    )
    assert chip.component == "TestChip"
    assert chip.parameters["tile_width_um"] == 2000.0
    assert chip.parameters["tile_height_um"] == 2000.0


def test_fastercap_parser_rejects_non_physical_matrix() -> None:
    import pytest

    from textlayout.simulation.fastercap import _parse_capacitance_matrix_pf

    garbage = "\n".join(
        (
            "Capacitance matrix is:",
            "Dimension 2 x 2",
            "g1_P1  -3.69159e-14 1.00257e-13",
            "g1_P2  1.00257e-13 -3.68931e-14",
        )
    )
    with pytest.raises(ValueError, match="non-physical"):
        _parse_capacitance_matrix_pf(garbage)


def test_fastercap_parser_takes_last_refinement_matrix() -> None:
    from textlayout.simulation.fastercap import _parse_capacitance_matrix_pf

    two_pass = "\n".join(
        (
            "Capacitance matrix is:",
            "Dimension 2 x 2",
            "g1_P1  1.0e-13 -0.5e-13",
            "g1_P2  -0.5e-13 1.0e-13",
            "",
            "Capacitance matrix is:",
            "Dimension 2 x 2",
            "g1_P1  6.6e-13 -6.0e-13",
            "g1_P2  -6.0e-13 6.6e-13",
        )
    )
    matrix = _parse_capacitance_matrix_pf(two_pass)
    assert abs(matrix[0][1]) == 0.6  # pF, from the LAST (converged) pass
