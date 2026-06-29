"""Built-in verification checks.

Each check is a pure function ``(VerificationContext) -> Check | None``. Returning
``None`` means the check does not apply to this component (so it is omitted from
the report — we never emit a check that did not actually run).

This is the IC-layout analogue of Text-to-CAD's geometric validation step, but
specialised for the *dangerous* part of layout: design rules (min width/gap),
layer legality, and geometry sanity.
"""

from __future__ import annotations

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
    limit = ctx.technology.min_width_for(ctx.metal_layer)
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
        if "gap" in k and isinstance(v, (int, float)) and not isinstance(v, bool)
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
                gap = _bbox_gap(polys[i], polys[j])
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
    check_geometry_spacing,
)


def _bbox_gap(a: Polygon, b: Polygon) -> float:
    ba, bb = a.bbox, b.bbox
    dx = max(ba.xmin - bb.xmax, bb.xmin - ba.xmax, 0.0)
    dy = max(ba.ymin - bb.ymax, bb.ymin - ba.ymax, 0.0)
    if dx == 0.0 and dy == 0.0:
        return 0.0
    if dx == 0.0:
        return dy
    if dy == 0.0:
        return dx
    return math.hypot(dx, dy)
