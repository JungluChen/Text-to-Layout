"""Smooth Euler (clothoid) bend for coplanar waveguides.

The centerline is integrated from a piecewise-linear curvature profile
(ramp-up, optional constant arc, ramp-down) with a fixed-step midpoint rule so
output is bit-for-bit reproducible. Conductor and ground outlines are built by
offsetting the centerline along its unit normal; because the clearance is a
constant lateral offset, the gap between signal and ground is the same at every
station along the bend (continuous ground clearance). Pure Python: no numpy,
no gdsfactory.
"""

from __future__ import annotations

import math
from collections.abc import Sequence

from pydantic import BaseModel

from textlayout.models import Geometry, Point, Polygon, Port, Technology
from textlayout.ports.generator import Generator
from textlayout.schemas.dsl.euler_bend import CPWEulerBendSpec


def euler_centerline(
    *,
    min_radius_um: float,
    angle_deg: float,
    euler_fraction: float = 1.0,
    samples: int = 64,
) -> tuple[list[Point], list[float]]:
    """Return centerline points and headings (radians) starting at (0, 0) heading +y.

    Curvature profile: linear ramp 0 -> kappa_max over the first ``p*theta/2``
    of turn, constant ``kappa_max`` for ``(1-p)*theta``, and linear ramp back
    to zero. Each ramp turns through ``p*theta/2`` over length ``p*theta/kappa_max``,
    so the total arc length is ``L = theta * (1 + p) / kappa_max`` (a pure Euler
    bend is twice as long as the circular arc of the same minimum radius).
    """
    theta = math.radians(abs(angle_deg))
    sign = 1.0 if angle_deg > 0 else -1.0
    kappa_max = 1.0 / min_radius_um
    p = euler_fraction
    ramp_length = p * theta / kappa_max  # each clothoid ramp
    arc_length = (1.0 - p) * theta / kappa_max
    total = 2.0 * ramp_length + arc_length

    def curvature(s: float) -> float:
        if s < ramp_length:
            return kappa_max * s / ramp_length
        if s < ramp_length + arc_length:
            return kappa_max
        remaining = total - s
        return kappa_max * max(remaining, 0.0) / ramp_length

    ds = total / samples
    x = y = 0.0
    heading = math.pi / 2.0  # +y
    points: list[Point] = [(0.0, 0.0)]
    headings: list[float] = [heading]
    for i in range(samples):
        s_mid = (i + 0.5) * ds
        heading_mid = heading + sign * curvature(s_mid) * ds / 2.0
        x += math.cos(heading_mid) * ds
        y += math.sin(heading_mid) * ds
        heading += sign * curvature(s_mid) * ds
        points.append((x, y))
        headings.append(heading)
    return points, headings


def offset_polyline(
    points: Sequence[Point], headings: Sequence[float], offset: float
) -> list[Point]:
    """Offset a centerline by ``offset`` along the left normal (+ = left of travel)."""
    out: list[Point] = []
    for (x, y), heading in zip(points, headings, strict=True):
        nx, ny = -math.sin(heading), math.cos(heading)
        out.append((x + offset * nx, y + offset * ny))
    return out


def band_polygon(
    layer: str,
    points: Sequence[Point],
    headings: Sequence[float],
    inner_offset: float,
    outer_offset: float,
) -> Polygon:
    """Polygon between two parallel offsets of the same centerline."""
    left = offset_polyline(points, headings, outer_offset)
    right = offset_polyline(points, headings, inner_offset)
    return Polygon(layer=layer, points=tuple([*left, *reversed(right)]))


def _translate(polygon: Polygon, dx: float, dy: float) -> Polygon:
    return Polygon(polygon.layer, tuple((x + dx, y + dy) for x, y in polygon.points))


class CPWEulerBendGenerator(Generator):
    """Generates a CPW Euler bend with constant signal-to-ground clearance."""

    name = "CPWEulerBend"
    params_model = CPWEulerBendSpec

    def generate(self, params: BaseModel, tech: Technology, origin: Point) -> Geometry:
        assert isinstance(params, CPWEulerBendSpec)
        x0, y0 = origin
        half_w = params.center_width_um / 2.0
        g = params.gap_um
        gw = params.ground_width_um
        metal = params.metal

        points, headings = euler_centerline(
            min_radius_um=params.min_radius_um,
            angle_deg=params.angle_deg,
            euler_fraction=params.euler_fraction,
            samples=params.points_per_bend,
        )
        signal = band_polygon(metal, points, headings, -half_w, half_w)
        ground_left = band_polygon(metal, points, headings, half_w + g, half_w + g + gw)
        ground_right = band_polygon(metal, points, headings, -(half_w + g + gw), -(half_w + g))
        polygons = tuple(_translate(poly, x0, y0) for poly in (signal, ground_left, ground_right))

        end_x, end_y = points[-1]
        end_heading_deg = round(math.degrees(headings[-1]), 9) % 360.0
        start_deg = 270.0
        ground_center = half_w + g + gw / 2.0

        def port(name: str, base: Point, heading: float, lateral: float, deg: float) -> Port:
            bx, by = base
            nx, ny = -math.sin(heading), math.cos(heading)
            width = params.center_width_um if lateral == 0.0 else gw
            return Port(name, (x0 + bx + lateral * nx, y0 + by + lateral * ny), width, deg, metal)

        start_heading = math.pi / 2.0
        ports = (
            port("RF_IN", (0.0, 0.0), start_heading, 0.0, start_deg),
            port("RF_OUT", (end_x, end_y), headings[-1], 0.0, end_heading_deg),
            port("GND_L_IN", (0.0, 0.0), start_heading, ground_center, start_deg),
            port("GND_L_OUT", (end_x, end_y), headings[-1], ground_center, end_heading_deg),
            port("GND_R_IN", (0.0, 0.0), start_heading, -ground_center, start_deg),
            port("GND_R_OUT", (end_x, end_y), headings[-1], -ground_center, end_heading_deg),
        )
        theta = math.radians(abs(params.angle_deg))
        arc_length = theta * (1.0 + params.euler_fraction) * params.min_radius_um
        return Geometry(
            name="CPWEulerBend",
            polygons=polygons,
            ports=ports,
            metadata={
                "component": "CPWEulerBend",
                "metal": metal,
                "center_width_um": params.center_width_um,
                "gap_um": g,
                "ground_width_um": gw,
                "min_radius_um": params.min_radius_um,
                "angle_deg": params.angle_deg,
                "euler_fraction": params.euler_fraction,
                "centerline_length_um": round(arc_length, 6),
                "end_point_um": (round(end_x, 6), round(end_y, 6)),
                "end_heading_deg": round(end_heading_deg, 6),
                "continuous_ground_clearance": True,
                "min_ports": 6,
                "explicit_ground_reference_ports": True,
                "curvature_profile": "clothoid ramp / arc / clothoid ramp",
                "method": "geometry",
            },
        )


__all__ = ["CPWEulerBendGenerator", "band_polygon", "euler_centerline", "offset_polyline"]
