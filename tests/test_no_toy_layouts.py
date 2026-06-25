"""Tests that PCells are not toy colored rectangles.

Each test verifies a specific structural expectation of the layout:
multi-layer stacks, boolean ground planes, signal traces, meanders, etc.
"""

from __future__ import annotations

from pathlib import Path

import pytest

kdb = pytest.importorskip("klayout.db")


def _layer_numbers(gds_path: Path) -> set[tuple[int, int]]:
    """Return the set of (layer, datatype) pairs that contain geometry."""
    layout = kdb.Layout()
    layout.read(str(gds_path))
    top = layout.top_cell()
    result: set[tuple[int, int]] = set()
    for li in layout.layer_indices():
        info = layout.get_info(li)
        it = top.begin_shapes_rec(li)
        if not it.at_end():
            result.add((int(info.layer), int(info.datatype)))
    return result


def _polygon_count_on_layer(gds_path: Path, layer: int, datatype: int) -> int:
    """Count polygons (including boxes) on a specific layer."""
    layout = kdb.Layout()
    layout.read(str(gds_path))
    top = layout.top_cell()
    li = layout.layer(layer, datatype)
    count = 0
    it = top.begin_shapes_rec(li)
    while not it.at_end():
        shape = it.shape()
        if shape.is_polygon() or shape.is_box() or shape.is_path():
            count += 1
        it.next()
    return count


def _total_polygon_count(gds_path: Path) -> int:
    """Count all polygons across all layers."""
    layout = kdb.Layout()
    layout.read(str(gds_path))
    top = layout.top_cell()
    count = 0
    for li in layout.layer_indices():
        it = top.begin_shapes_rec(li)
        while not it.at_end():
            shape = it.shape()
            if shape.is_polygon() or shape.is_box() or shape.is_path():
                count += 1
            it.next()
    return count


# -- CPW ground plane --------------------------------------------------------


def test_cpw_has_ground_plane(tmp_path: Path) -> None:
    """CPW straight must have M1 ground plane with boolean holes."""
    from text_to_gds.pcells.passives import cpw_straight

    c = cpw_straight(length=100.0, trace_width=10.0, gap=6.0)
    gds_path = tmp_path / "cpw.gds"
    c.write_gds(str(gds_path))

    layout = kdb.Layout()
    layout.read(str(gds_path))
    top = layout.top_cell()
    m1_li = layout.layer(3, 0)

    # Walk M1 polygons and check for holes or multiple disjoint pieces
    has_hole = False
    piece_count = 0
    it = top.begin_shapes_rec(m1_li)
    while not it.at_end():
        shape = it.shape()
        if shape.is_polygon():
            poly = shape.polygon.transformed(it.trans())
            if poly.holes() > 0:
                has_hole = True
            piece_count += 1
        elif shape.is_box():
            piece_count += 1
        it.next()

    assert piece_count > 0, "CPW must have M1 ground plane polygons"
    # Boolean subtraction produces either holes in one polygon or multiple pieces
    assert has_hole or piece_count > 1, (
        "M1 ground plane must have boolean holes or be split into pieces by gap clearance"
    )


# -- CPW signal trace ---------------------------------------------------------


def test_cpw_has_signal_trace(tmp_path: Path) -> None:
    """CPW must have signal trace on its signal layer (M3 by default)."""
    from text_to_gds.pcells.passives import cpw_straight

    c = cpw_straight(length=100.0, trace_width=10.0, gap=6.0)
    gds_path = tmp_path / "cpw_sig.gds"
    c.write_gds(str(gds_path))

    m3_count = _polygon_count_on_layer(gds_path, 6, 0)
    assert m3_count > 0, "CPW must have signal trace polygons on M3=(6,0)"


# -- JJ multi-layer ----------------------------------------------------------


def test_jj_has_multilayer(tmp_path: Path) -> None:
    """JJ must have polygons on at least M1, JJ barrier, and M2."""
    from text_to_gds.pcells.junction import manhattan_josephson_junction

    c = manhattan_josephson_junction(junction_width=0.22, junction_height=0.22)
    gds_path = tmp_path / "jj.gds"
    c.write_gds(str(gds_path))

    layers = _layer_numbers(gds_path)
    assert (3, 0) in layers, "JJ must have M1=(3,0) bottom electrode"
    assert (4, 0) in layers, "JJ must have JJ=(4,0) barrier layer"
    assert (5, 0) in layers, "JJ must have M2=(5,0) top electrode"


# -- Resonator meander -------------------------------------------------------


def test_cpw_resonator_has_meander(tmp_path: Path) -> None:
    """Quarter wave resonator must have multiple signal segments (meander)."""
    from text_to_gds.pcells.passives import cpw_quarter_wave_resonator

    c = cpw_quarter_wave_resonator(
        target_frequency_ghz=6.0,
        trace_width=10.0,
        gap=6.0,
        meander_runs=5,
    )
    gds_path = tmp_path / "resonator.gds"
    c.write_gds(str(gds_path))

    # Signal layer is M2=(5,0) by default for the resonator
    signal_count = _polygon_count_on_layer(gds_path, 5, 0)
    assert signal_count >= 5, (
        f"Resonator with 5 meander runs must have >= 5 signal polygons, got {signal_count}"
    )


# -- JJ is not a single rectangle --------------------------------------------


def test_jj_not_single_rectangle(tmp_path: Path) -> None:
    """JJ layout must have more than one polygon total."""
    from text_to_gds.pcells.junction import manhattan_josephson_junction

    c = manhattan_josephson_junction(junction_width=0.22, junction_height=0.22)
    gds_path = tmp_path / "jj_multi.gds"
    c.write_gds(str(gds_path))

    count = _total_polygon_count(gds_path)
    assert count > 1, f"JJ must have more than 1 polygon total, got {count}"
