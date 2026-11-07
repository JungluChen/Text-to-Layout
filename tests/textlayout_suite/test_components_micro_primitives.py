"""Deterministic micro-primitives: Euler bend, perforation lattice, JJ pads."""

from __future__ import annotations

import math

import pytest
from pydantic import ValidationError

from textlayout.components import (
    CPWEulerBendGenerator,
    JosephsonJunctionGenerator,
    PerforationGenerator,
    euler_centerline,
    register_components,
)
from textlayout.components.euler_bend import offset_polyline
from textlayout.generators.registry import GeneratorRegistry
from textlayout.models import LayerInfo, Technology
from textlayout.schemas.dsl import (
    CPWEulerBendSpec,
    JosephsonJunctionSpec,
    KeepOutRect,
    PerforationSpec,
)

TECH = Technology("test", {"M1": LayerInfo("M1", 1)})


def _bend(**overrides: object) -> CPWEulerBendSpec:
    base: dict[str, object] = {
        "center_width_um": 10.0,
        "gap_um": 6.0,
        "ground_width_um": 30.0,
        "min_radius_um": 100.0,
        "angle_deg": 90.0,
    }
    base.update(overrides)
    return CPWEulerBendSpec.model_validate(base)


# ------------------------------------------------------------------ Euler bend


def test_euler_centerline_turns_through_requested_angle_and_length() -> None:
    points, headings = euler_centerline(min_radius_um=100.0, angle_deg=90.0, samples=200)
    assert math.isclose(math.degrees(headings[-1] - headings[0]), 90.0, abs_tol=1e-9)
    length = sum(math.dist(a, b) for a, b in zip(points, points[1:], strict=False))
    # Pure Euler (p = 1): L = theta * (1 + p) * R_min = 2 * (pi/2) * 100.
    assert math.isclose(length, math.pi * 100.0, rel_tol=1e-6)
    # Curvature is zero at both ends: the first and last segments are nearly straight.
    assert abs(headings[1] - headings[0]) < abs(headings[101] - headings[100])


def test_euler_fraction_near_zero_recovers_a_circular_arc() -> None:
    points, _ = euler_centerline(
        min_radius_um=100.0, angle_deg=90.0, euler_fraction=1e-3, samples=4000
    )
    end_x, end_y = points[-1]
    assert math.isclose(end_x, -100.0, abs_tol=0.2)
    assert math.isclose(end_y, 100.0, abs_tol=0.2)


def test_euler_bend_keeps_continuous_ground_clearance() -> None:
    spec = _bend()
    geometry = CPWEulerBendGenerator().generate(spec, TECH, (0.0, 0.0))
    signal, ground_left, ground_right = geometry.polygons
    n = spec.points_per_bend + 1
    # band_polygon = outer offset forward, inner offset reversed.
    signal_left_edge = signal.points[:n]
    ground_left_inner = list(reversed(ground_left.points[n:]))
    for s, g in zip(signal_left_edge, ground_left_inner, strict=True):
        assert math.isclose(math.dist(s, g), spec.gap_um, abs_tol=1e-9)
    signal_right_edge = list(reversed(signal.points[n:]))
    ground_right_inner = ground_right.points[:n]
    for s, g in zip(signal_right_edge, ground_right_inner, strict=True):
        assert math.isclose(math.dist(s, g), spec.gap_um, abs_tol=1e-9)
    assert geometry.metadata["continuous_ground_clearance"] is True
    assert math.isclose(geometry.metadata["centerline_length_um"], math.pi * 100.0, rel_tol=1e-7)
    assert len(geometry.ports) == 6
    assert math.isclose(geometry.metadata["end_heading_deg"], 180.0, abs_tol=1e-9)


def test_euler_bend_is_deterministic_and_honours_origin_and_sign() -> None:
    a = CPWEulerBendGenerator().generate(_bend(), TECH, (5.0, -3.0))
    b = CPWEulerBendGenerator().generate(_bend(), TECH, (5.0, -3.0))
    assert a == b
    assert a.ports[0].center == (5.0, -3.0)
    cw = CPWEulerBendGenerator().generate(_bend(angle_deg=-90.0), TECH, (0.0, 0.0))
    assert cw.metadata["end_point_um"][0] > 0  # clockwise turn ends at +x
    assert math.isclose(cw.metadata["end_heading_deg"], 0.0, abs_tol=1e-9)


def test_euler_bend_rejects_self_intersecting_clearance() -> None:
    with pytest.raises(ValidationError, match="self-intersect"):
        _bend(min_radius_um=40.0)
    with pytest.raises(ValidationError, match="non-zero"):
        _bend(angle_deg=0.0)


def test_offset_polyline_is_left_normal() -> None:
    pts = offset_polyline([(0.0, 0.0), (0.0, 1.0)], [math.pi / 2, math.pi / 2], 2.0)
    assert pts[0] == pytest.approx((-2.0, 0.0), abs=1e-12)
    assert pts[1] == pytest.approx((-2.0, 1.0), abs=1e-12)


# ----------------------------------------------------------------- perforation


def test_perforation_honours_keep_out_margin() -> None:
    spec = PerforationSpec(
        window_width_um=200.0,
        window_height_um=100.0,
        hole_size_um=5.0,
        pitch_um=20.0,
        keep_out_margin_um=10.0,
        keep_outs=(KeepOutRect(xmin=0.0, ymin=40.0, xmax=200.0, ymax=60.0),),
    )
    geometry = PerforationGenerator().generate(spec, TECH, (0.0, 0.0))
    holes = geometry.on_layer("M1_HOLE")
    assert geometry.metadata["grid_sites"] == 50
    assert len(holes) == geometry.metadata["holes_emitted"] == 20
    assert geometry.metadata["holes_suppressed_by_keep_out"] == 30
    for hole in holes:
        box = hole.bbox
        # Grown by the margin, no hole may touch the trace band y in [40, 60].
        assert (
            box.ymax + spec.keep_out_margin_um <= 40.0 or box.ymin - spec.keep_out_margin_um >= 60.0
        )
        assert box.xmin >= spec.edge_margin_um and box.xmax <= 200.0 - spec.edge_margin_um
    assert len(geometry.on_layer("M1")) == 1


def test_perforation_without_keep_out_fills_grid_and_rejects_merging_holes() -> None:
    spec = PerforationSpec(
        window_width_um=100.0, window_height_um=100.0, hole_size_um=4.0, pitch_um=10.0
    )
    geometry = PerforationGenerator().generate(spec, TECH, (10.0, 10.0))
    assert geometry.metadata["holes_emitted"] == geometry.metadata["grid_sites"] == 81
    assert geometry.bbox().xmin == 10.0
    with pytest.raises(ValidationError, match="never merge"):
        PerforationSpec(
            window_width_um=100.0, window_height_um=100.0, hole_size_um=10.0, pitch_um=10.0
        )


# -------------------------------------------------------------------- junction


@pytest.mark.parametrize("style", ["dolan", "manhattan"])
def test_junction_emits_all_process_layers_and_geometric_ic(style: str) -> None:
    spec = JosephsonJunctionSpec(
        style=style,  # type: ignore[arg-type]
        junction_width_um=0.2,
        finger_width_um=0.2,
        overlap_um=0.2,
        critical_current_density_ua_per_um2=0.5,
    )
    geometry = JosephsonJunctionGenerator().generate(spec, TECH, (0.0, 0.0))
    assert geometry.layers() == ("BANDAGE", "JJ1", "JJ2", "JJ_UNDERCUT", "M1")
    assert math.isclose(geometry.metadata["junction_area_um2"], 0.04)
    assert math.isclose(geometry.metadata["critical_current_ua"], 0.02)
    # E_J/h = Ic * Phi0 / (2 pi h): 20 nA -> 9.93 GHz
    assert math.isclose(geometry.metadata["josephson_energy_ghz"], 9.9337, rel_tol=1e-3)
    assert geometry.metadata["analytical_estimate"] is True
    assert {port.name for port in geometry.ports} == {"JJ_A", "JJ_B"}


def test_dolan_electrodes_overlap_only_over_the_junction_area() -> None:
    spec = JosephsonJunctionSpec(style="dolan", junction_width_um=0.3, overlap_um=0.25)
    geometry = JosephsonJunctionGenerator().generate(spec, TECH, (0.0, 0.0))
    base = geometry.on_layer("JJ1")
    counter = geometry.on_layer("JJ2")
    finger = max(base, key=lambda p: p.bbox.ymax)
    electrode = counter[0]
    ox = max(
        0.0, min(finger.bbox.xmax, electrode.bbox.xmax) - max(finger.bbox.xmin, electrode.bbox.xmin)
    )
    oy = max(
        0.0, min(finger.bbox.ymax, electrode.bbox.ymax) - max(finger.bbox.ymin, electrode.bbox.ymin)
    )
    assert math.isclose(ox * oy, spec.junction_area_um2, rel_tol=1e-9)


def test_junction_spec_rejects_inconsistent_widths() -> None:
    with pytest.raises(ValidationError, match="junction_width_um cannot exceed"):
        JosephsonJunctionSpec(junction_width_um=5.0, lead_width_um=1.0)


def test_components_register_without_touching_builtin_registry() -> None:
    registry = register_components(GeneratorRegistry())
    assert registry.names() == ["CPWEulerBend", "GroundPerforation", "JosephsonJunction"]
    from textlayout.generators.registry import default_registry

    assert "CPWEulerBend" not in default_registry(discover=False)
