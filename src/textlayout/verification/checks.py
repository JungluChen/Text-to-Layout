"""Built-in verification checks.

Each check is a pure function ``(VerificationContext) -> Check | None``. Returning
``None`` means the check does not apply to this component (so it is omitted from
the report — we never emit a check that did not actually run).

This is the IC-layout analogue of Text-to-CAD's geometric validation step, but
specialised for the *dangerous* part of layout: design rules (min width/gap),
layer legality, and geometry sanity.
"""

from __future__ import annotations

from collections.abc import Iterator
import math

from textlayout.models import Polygon
from textlayout.verification.context import VerificationContext
from textlayout.verification.report import Check, CheckStatus

_EPS = 1e-6


def check_component_generated(ctx: VerificationContext) -> Check:
    ok = ctx.component_built and not ctx.geometry.is_empty
    return Check(
        name="component_generated",
        status=CheckStatus.PASS if ok else CheckStatus.FAIL,
        message="" if ok else "Generator did not produce any geometry.",
    )


def check_positive_dimensions(ctx: VerificationContext) -> Check:
    bad = [
        k
        for k, v in ctx.param_dict.items()
        if isinstance(v, (int, float)) and not isinstance(v, bool) and v <= 0
    ]
    return Check(
        name="positive_dimensions",
        status=CheckStatus.PASS if not bad else CheckStatus.FAIL,
        message="" if not bad else f"Non-positive parameter(s): {', '.join(sorted(bad))}.",
    )


def check_minimum_width(ctx: VerificationContext) -> Check | None:
    widths = [
        v
        for k, v in ctx.param_dict.items()
        if "width" in k and isinstance(v, (int, float)) and not isinstance(v, bool)
    ]
    if not widths:
        return None
    value = float(min(widths))
    limit = ctx.spec.rules.get("min_width_um", ctx.technology.min_width_for(ctx.metal_layer))
    ok = value >= limit - _EPS
    return Check(
        name="minimum_width",
        status=CheckStatus.PASS if ok else CheckStatus.FAIL,
        value=value,
        limit=limit,
        message="" if ok else f"Minimum width {value}µm < limit {limit}µm on {ctx.metal_layer}.",
    )


def check_minimum_gap(ctx: VerificationContext) -> Check | None:
    gaps = [
        v
        for k, v in ctx.param_dict.items()
        if ("gap" in k or "spacing" in k)
        and isinstance(v, (int, float))
        and not isinstance(v, bool)
    ]
    if not gaps:
        return None
    value = float(min(gaps))
    limit = ctx.spec.rules.get("min_gap_um", ctx.technology.min_spacing_for(ctx.metal_layer))
    ok = value >= limit - _EPS
    return Check(
        name="minimum_gap",
        status=CheckStatus.PASS if ok else CheckStatus.FAIL,
        value=value,
        limit=limit,
        message="" if ok else f"Minimum gap {value}µm < limit {limit}µm on {ctx.metal_layer}.",
    )


def check_finger_count(ctx: VerificationContext) -> Check | None:
    count = ctx.param_dict.get("finger_pairs")
    if not isinstance(count, int):
        return None
    ok = 1 <= count <= 2000
    return Check(
        name="finger_count_sanity",
        status=CheckStatus.PASS if ok else CheckStatus.FAIL,
        value=float(count),
        unit="count",
        message="" if ok else f"finger_pairs={count} outside sane range [1, 2000].",
    )


def check_layer_exists(ctx: VerificationContext) -> Check:
    missing = [layer for layer in ctx.geometry.layers() if not ctx.technology.has_layer(layer)]
    ok = not missing
    return Check(
        name="layer_exists",
        status=CheckStatus.PASS if ok else CheckStatus.FAIL,
        message="" if ok else f"Layer(s) not in technology {ctx.technology.name!r}: {missing}.",
    )


def check_bounding_box(ctx: VerificationContext) -> Check:
    if ctx.geometry.is_empty:
        return Check("bounding_box", CheckStatus.FAIL, "Geometry has no bounding box.")
    box = ctx.geometry.bbox()
    ok = box.area > 0
    return Check(
        name="bounding_box",
        status=CheckStatus.PASS if ok else CheckStatus.FAIL,
        value=box.area,
        unit="um2",
        message="" if ok else "Bounding box has zero area.",
    )


def check_ports(ctx: VerificationContext) -> Check | None:
    min_ports = ctx.geometry.metadata.get("min_ports")
    if not isinstance(min_ports, int) or min_ports <= 0:
        return None
    have = len(ctx.geometry.ports)
    ok = have >= min_ports
    return Check(
        name="ports_exist",
        status=CheckStatus.PASS if ok else CheckStatus.FAIL,
        value=float(have),
        limit=float(min_ports),
        unit="count",
        message="" if ok else f"Component declares {min_ports} required port(s) but has {have}.",
    )


def check_geometry_spacing(ctx: VerificationContext) -> Check:
    """A real (if minimal) DRC: same-layer features must respect min spacing."""
    worst: tuple[str, float, float] | None = None
    for layer in ctx.geometry.layers():
        if not ctx.technology.has_layer(layer):
            continue
        limit = ctx.technology.min_spacing_for(layer)
        polys = ctx.geometry.on_layer(layer)
        for i in range(len(polys)):
            for j in range(i + 1, len(polys)):
                gap = _polygon_gap(polys[i], polys[j])
                if 0.0 < gap < limit - _EPS and (worst is None or gap < worst[1]):
                    worst = (layer, gap, limit)
    if worst is None:
        return Check("geometry_min_spacing", CheckStatus.PASS, "")
    layer, gap, limit = worst
    return Check(
        name="geometry_min_spacing",
        status=CheckStatus.FAIL,
        value=gap,
        limit=limit,
        message=f"Geometry spacing {gap:.4g}µm on {layer} below min {limit:.4g}µm.",
    )


def check_analytical_estimate(ctx: VerificationContext) -> Check | None:
    """Warn (never fail) when a performance value is an analytical estimate.

    Mirrors Text-to-CAD's honesty: the layout is geometrically valid, but a
    quantity like capacitance is a model estimate, not a fabrication value.
    """
    if not ctx.geometry.metadata.get("analytical_estimate"):
        return None
    quantity = ctx.geometry.metadata.get("analytical_quantity", "a performance value")
    return Check(
        name="analytical_estimate",
        status=CheckStatus.WARN,
        message=(
            f"{str(quantity).capitalize()} is an analytical estimate only. "
            "EM extraction is required before fabrication."
        ),
    )


def check_rf_port_semantics(ctx: VerificationContext) -> Check | None:
    expected: set[str]
    if ctx.spec.component == "CPW":
        expected = {"RF_IN", "RF_OUT", "GND_L_IN", "GND_L_OUT", "GND_R_IN", "GND_R_OUT"}
    elif ctx.spec.component == "QuarterWaveResonator":
        expected = {
            "RF_IN",
            "RF_OUT",
            "GND_TOP_IN",
            "GND_TOP_OUT",
            "GND_BOTTOM_IN",
            "GND_BOTTOM_OUT",
        }
    else:
        return None
    names = {port.name for port in ctx.geometry.ports}
    missing = sorted(expected - names)
    return Check(
        "explicit_rf_ground_ports",
        CheckStatus.PASS if not missing else CheckStatus.FAIL,
        "" if not missing else f"Missing explicit RF/ground-reference ports: {missing}.",
    )


def check_spiral_centerline(ctx: VerificationContext) -> Check | None:
    if ctx.spec.component != "SpiralInductor":
        return None
    points = ctx.geometry.metadata.get("centerline_points_um")
    ok = isinstance(points, list) and len(points) >= 4 and len(ctx.geometry.ports) == 2
    return Check(
        "spiral_centerline_and_terminals",
        CheckStatus.PASS if ok else CheckStatus.FAIL,
        "" if ok else "Spiral requires a continuous centerline and exactly two terminals.",
    )


def check_resonator_boundaries(ctx: VerificationContext) -> Check | None:
    if ctx.spec.component != "QuarterWaveResonator":
        return None
    metadata = ctx.geometry.metadata
    ok = bool(metadata.get("boundary_open")) and bool(metadata.get("boundary_short"))
    return Check(
        "resonator_open_short_boundaries",
        CheckStatus.PASS if ok else CheckStatus.FAIL,
        "" if ok else "Quarter-wave resonator requires explicit coupled-open and grounded-short ends.",
    )


def check_squid_structure(ctx: VerificationContext) -> Check | None:
    if ctx.spec.component != "SQUID":
        return None
    jj_count = len(ctx.geometry.on_layer(str(ctx.param_dict.get("junction_layer", "JJ"))))
    target_area = ctx.spec.target.get("loop_area_um2")
    actual_area = ctx.geometry.metadata.get("loop_area_um2")
    area_ok = target_area is None or (
        isinstance(actual_area, (int, float)) and abs(float(actual_area) - target_area) <= 1e-6
    )
    ok = jj_count == 2 and area_ok and len(ctx.geometry.ports) == 2
    return Check(
        "squid_symmetry_junctions_loop_area",
        CheckStatus.PASS if ok else CheckStatus.FAIL,
        "" if ok else "SQUID requires two JJ polygons, two bias ports, and the requested loop area.",
        value=float(actual_area) if isinstance(actual_area, (int, float)) else None,
        limit=target_area,
        unit="um2",
    )


def check_squid_foundry_stack(ctx: VerificationContext) -> Check | None:
    if ctx.spec.component != "SQUID" or not ctx.geometry.metadata.get("foundry_stack_required"):
        return None
    return Check(
        "foundry_junction_stack",
        CheckStatus.WARN,
        "Generic JJ placeholders are not fabrication-ready without foundry layer and overlap rules.",
    )


#: Ordered default check set. Order is the report order.
DEFAULT_CHECKS = (
    check_component_generated,
    check_positive_dimensions,
    check_minimum_width,
    check_minimum_gap,
    check_finger_count,
    check_layer_exists,
    check_bounding_box,
    check_ports,
    check_rf_port_semantics,
    check_spiral_centerline,
    check_resonator_boundaries,
    check_squid_structure,
    check_squid_foundry_stack,
    check_geometry_spacing,
    check_analytical_estimate,
)


def _polygon_gap(a: Polygon, b: Polygon) -> float:
    """Return exact edge-to-edge clearance between two simple polygons."""
    edges_a = tuple(_edges(a.points))
    edges_b = tuple(_edges(b.points))
    if any(_segments_intersect(*edge_a, *edge_b) for edge_a in edges_a for edge_b in edges_b):
        return 0.0
    if _point_in_polygon(a.points[0], b.points) or _point_in_polygon(b.points[0], a.points):
        return 0.0
    return min(
        _segment_distance(*edge_a, *edge_b) for edge_a in edges_a for edge_b in edges_b
    )


def _edges(
    points: tuple[tuple[float, float], ...],
) -> Iterator[tuple[tuple[float, float], tuple[float, float]]]:
    for index, start in enumerate(points):
        yield start, points[(index + 1) % len(points)]


def _segments_intersect(
    a: tuple[float, float],
    b: tuple[float, float],
    c: tuple[float, float],
    d: tuple[float, float],
) -> bool:
    def cross(p: tuple[float, float], q: tuple[float, float], r: tuple[float, float]) -> float:
        return (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])

    def on_segment(
        p: tuple[float, float], q: tuple[float, float], r: tuple[float, float]
    ) -> bool:
        return (
            min(p[0], r[0]) - _EPS <= q[0] <= max(p[0], r[0]) + _EPS
            and min(p[1], r[1]) - _EPS <= q[1] <= max(p[1], r[1]) + _EPS
        )

    o1, o2, o3, o4 = cross(a, b, c), cross(a, b, d), cross(c, d, a), cross(c, d, b)
    if (o1 > _EPS and o2 < -_EPS or o1 < -_EPS and o2 > _EPS) and (
        o3 > _EPS and o4 < -_EPS or o3 < -_EPS and o4 > _EPS
    ):
        return True
    return (
        abs(o1) <= _EPS and on_segment(a, c, b)
        or abs(o2) <= _EPS and on_segment(a, d, b)
        or abs(o3) <= _EPS and on_segment(c, a, d)
        or abs(o4) <= _EPS and on_segment(c, b, d)
    )


def _point_in_polygon(
    point: tuple[float, float], polygon: tuple[tuple[float, float], ...]
) -> bool:
    x, y = point
    inside = False
    for (x1, y1), (x2, y2) in _edges(polygon):
        if (y1 > y) != (y2 > y):
            intersection_x = (x2 - x1) * (y - y1) / (y2 - y1) + x1
            if x < intersection_x:
                inside = not inside
    return inside


def _segment_distance(
    a: tuple[float, float],
    b: tuple[float, float],
    c: tuple[float, float],
    d: tuple[float, float],
) -> float:
    return min(
        _point_segment_distance(a, c, d),
        _point_segment_distance(b, c, d),
        _point_segment_distance(c, a, b),
        _point_segment_distance(d, a, b),
    )


def _point_segment_distance(
    point: tuple[float, float],
    start: tuple[float, float],
    end: tuple[float, float],
) -> float:
    dx, dy = end[0] - start[0], end[1] - start[1]
    length_squared = dx * dx + dy * dy
    if length_squared <= _EPS:
        return math.hypot(point[0] - start[0], point[1] - start[1])
    projection = (
        (point[0] - start[0]) * dx + (point[1] - start[1]) * dy
    ) / length_squared
    projection = max(0.0, min(1.0, projection))
    closest = (start[0] + projection * dx, start[1] + projection * dy)
    return math.hypot(point[0] - closest[0], point[1] - closest[1])
