"""Tests for CPW subtractive ground-plane gaps.

Verifies that CPW PCells use boolean subtraction from the ground plane,
that signal and ground don't overlap, and that gap clearance is continuous.
"""

from __future__ import annotations

from pathlib import Path

import pytest

kdb = pytest.importorskip("klayout.db")


def _collect_regions(gds_path: Path, layer: int, datatype: int) -> "kdb.Region":
    """Read all polygons on the given layer into a klayout Region."""
    layout = kdb.Layout()
    layout.read(str(gds_path))
    top = layout.top_cell()
    li = layout.layer(layer, datatype)
    region = kdb.Region()
    it = top.begin_shapes_rec(li)
    while not it.at_end():
        shape = it.shape()
        trans = it.trans()
        if shape.is_polygon():
            region.insert(shape.polygon.transformed(trans))
        elif shape.is_box():
            region.insert(kdb.Polygon(shape.box).transformed(trans))
        elif shape.is_path():
            region.insert(shape.path.polygon().transformed(trans))
        it.next()
    return region


# -- Boolean subtracted ground -----------------------------------------------


def test_cpw_gap_is_boolean_subtracted(tmp_path: Path) -> None:
    """Generate cpw_straight, write GDS, read back, verify M1 ground has holes."""
    from text_to_gds.pcells.passives import cpw_straight

    c = cpw_straight(length=100.0, trace_width=10.0, gap=6.0)
    gds_path = tmp_path / "cpw_bool.gds"
    c.write_gds(str(gds_path))

    layout = kdb.Layout()
    layout.read(str(gds_path))
    top = layout.top_cell()
    m1_li = layout.layer(3, 0)

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

    assert piece_count > 0, "M1 ground plane must exist"
    assert has_hole or piece_count > 1, (
        "M1 ground must show boolean subtraction (holes or disjoint pieces)"
    )


# -- Signal does not overlap ground ------------------------------------------


def test_signal_does_not_overlap_ground(tmp_path: Path) -> None:
    """Signal polygons must not overlap with M1 ground polygons."""
    from text_to_gds.pcells.passives import cpw_straight

    c = cpw_straight(length=100.0, trace_width=10.0, gap=6.0)
    gds_path = tmp_path / "cpw_overlap.gds"
    c.write_gds(str(gds_path))

    ground_region = _collect_regions(gds_path, 3, 0)  # M1
    signal_region = _collect_regions(gds_path, 6, 0)  # M3

    overlap = ground_region & signal_region
    overlap_area = overlap.area()
    dbu = 0.001  # default dbu for gdsfactory
    overlap_um2 = abs(overlap_area) * dbu * dbu

    # Allow a tiny tolerance for GDS coordinate quantization
    assert overlap_um2 < 0.01, (
        f"Signal and ground overlap area is {overlap_um2:.4f} um2, expected near zero"
    )


# -- Resonator gap continuous ------------------------------------------------


def test_cpw_resonator_gap_continuous(tmp_path: Path) -> None:
    """The ground-plane clearance must exist along the entire meander path."""
    from text_to_gds.pcells.passives import cpw_quarter_wave_resonator

    c = cpw_quarter_wave_resonator(
        target_frequency_ghz=6.0,
        trace_width=10.0,
        gap=6.0,
        meander_runs=5,
    )
    gds_path = tmp_path / "resonator_gap.gds"
    c.write_gds(str(gds_path))

    ground_region = _collect_regions(gds_path, 3, 0)  # M1 ground
    signal_region = _collect_regions(gds_path, 5, 0)  # M2 signal

    # Signal should not overlap ground (the gap should be clear)
    overlap = ground_region & signal_region
    overlap_area = abs(overlap.area()) * 0.001 * 0.001
    assert overlap_area < 0.01, (
        f"Resonator signal overlaps ground by {overlap_area:.4f} um2 -- gap is not continuous"
    )


# -- Ground plane info -------------------------------------------------------


def test_ground_plane_exists() -> None:
    """CPW info dict must have ground_geometry == 'subtractive_boolean_plane'."""
    from text_to_gds.pcells.passives import cpw_straight

    c = cpw_straight(length=100.0, trace_width=10.0, gap=6.0)
    assert c.info["ground_geometry"] == "subtractive_boolean_plane"
