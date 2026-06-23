"""Tests for visual credibility improvements."""
from __future__ import annotations

import json
from pathlib import Path


def test_undercut_layer_exists():
    from text_to_gds.process import DEFAULT_PROCESS

    assert "UNDERCUT" in DEFAULT_PROCESS.layers
    assert DEFAULT_PROCESS.layers["UNDERCUT"].layer == (9, 0)
    assert DEFAULT_PROCESS.layers["UNDERCUT"].purpose == "junction undercut region"


def test_klayout_renderer_produces_png(tmp_path: Path):
    import klayout.db as kdb

    from text_to_gds.rendering import render_layout_screenshot

    layout = kdb.Layout()
    layout.dbu = 0.001
    cell = layout.create_cell("TEST")
    layer = layout.layer(3, 0)
    cell.shapes(layer).insert(kdb.Box(0, 0, 10000, 5000))
    gds_path = tmp_path / "test.gds"
    layout.write(str(gds_path))

    screenshot_path = tmp_path / "test.png"
    render_layout_screenshot(gds_path, screenshot_path, image_size=500)

    assert screenshot_path.exists()
    assert screenshot_path.stat().st_size > 0


def test_manhattan_jj_has_undercut_and_bridge(tmp_path: Path):
    from text_to_gds.pcells.junction import manhattan_josephson_junction

    import klayout.db as kdb

    c = manhattan_josephson_junction(
        junction_width=0.22,
        junction_height=0.22,
        undercut_margin_um=0.3,
        bridge_overlap_um=0.15,
    )

    gds_path = tmp_path / "jj.gds"
    c.write_gds(str(gds_path))

    layout = kdb.Layout()
    layout.read(str(gds_path))
    layer_indices = list(layout.layer_indices())
    layer_infos = [layout.get_info(i) for i in layer_indices]
    layer_numbers = [(int(info.layer), int(info.datatype)) for info in layer_infos]
    assert (9, 0) in layer_numbers, f"Expected undercut layer (9,0), got: {layer_numbers}"


def test_cpw_resonator_with_launcher_has_ground_and_launcher():
    from text_to_gds.pcells.passives import cpw_resonator_with_launcher

    c = cpw_resonator_with_launcher(
        length=100.0,
        trace_width=10.0,
        gap=6.0,
        launcher_size=50.0,
    )

    info = c.info
    assert info["device_type"] == "cpw_resonator_with_launcher"
    assert "launcher" in info["layers"]
    assert "ground" in info["layers"]
    assert "via_fence" in info["layers"]


def test_extract_physical_parameters(tmp_path: Path):
    from text_to_gds.extraction import extract_physical_parameters
    from text_to_gds.pcells.junction import manhattan_josephson_junction

    c = manhattan_josephson_junction(junction_width=0.22, junction_height=0.22)
    gds_path = tmp_path / "jj.gds"
    c.write_gds(str(gds_path))

    sidecar_path = tmp_path / "jj.sidecar.json"
    sidecar = {
        "pcell": "manhattan_josephson_junction",
        "junction_area_um2": 0.0484,
        "junction_width_um": 0.22,
        "junction_height_um": 0.22,
    }
    sidecar_path.write_text(json.dumps(sidecar))

    table = extract_physical_parameters(gds_path, sidecar_path, jc_ua_per_um2=2.0)

    assert table["schema"] == "text-to-gds.extraction.v1"
    assert table["status"] == "ok"
    assert table["junction"]["area"] > 0.0
    assert table["junction"]["ic"] > 0.0
    assert table["junction"]["lj"] > 0.0
    assert table["lineage"]["junction.ic"]["formula"] == "Ic = Jc * area"


def test_jpa_target_gain_is_not_reported_as_performance():
    from text_to_gds.simulation import estimate_physical_performance

    sidecar = {
        "pcell": "lumped_element_jpa_seed",
        "info": {
            "device_type": "lumped_element_jpa_seed",
            "junction_area_um2": 0.0484,
            "junction_width_um": 0.22,
            "junction_height_um": 0.22,
            "target_gain_db": 20.0,
        },
    }
    result = estimate_physical_performance(
        sidecar,
        jc_ua_per_um2=2.0,
        shunt_capacitance_ff=100.0,
    )
    assert result == {"status": "failed", "reason": "missing extracted parameter"}


def test_solver_disagreement_injection():
    from text_to_gds.solver_agreement import cross_validate_with_disagreement

    sources = [
        {
            "source": "HFSS",
            "value": 6.03,
            "mesh_convergence": {"converged": True, "mesh_cells": 45000},
            "boundary_conditions": "radiation",
        },
        {
            "source": "openEMS",
            "value": 5.91,
            "mesh_convergence": {"converged": True, "mesh_cells": 120000},
            "boundary_conditions": "PML",
        },
    ]
    result = cross_validate_with_disagreement(sources, quantity="f0_ghz")
    assert result["passed"] is True
    assert result["max_relative_error_pct"] > 0
    assert "mesh_convergence" in result
    assert "boundary_conditions" in result
