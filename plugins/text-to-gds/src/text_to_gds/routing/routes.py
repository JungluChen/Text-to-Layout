"""Small deterministic routing engine for superconducting microwave layouts."""

from __future__ import annotations

from dataclasses import dataclass, field
import math
from typing import Any


@dataclass(frozen=True)
class CollisionBox:
    xmin_um: float
    ymin_um: float
    xmax_um: float
    ymax_um: float

    def contains(self, point: tuple[float, float], clearance_um: float = 0.0) -> bool:
        x, y = point
        return (
            self.xmin_um - clearance_um <= x <= self.xmax_um + clearance_um
            and self.ymin_um - clearance_um <= y <= self.ymax_um + clearance_um
        )


@dataclass(frozen=True)
class RouteSpec:
    start_um: tuple[float, float]
    end_um: tuple[float, float]
    trace_width_um: float = 10.0
    gap_um: float = 6.0
    bend_radius_um: float = 50.0
    target_length_um: float | None = None
    snap_um: float = 1.0
    clearance_um: float = 10.0
    obstacles: tuple[CollisionBox, ...] = ()


@dataclass(frozen=True)
class RouteResult:
    route_type: str
    points_um: tuple[tuple[float, float], ...]
    length_um: float
    bend_count: int
    trace_width_um: float
    gap_um: float
    bend_radius_um: float
    collision_free: bool
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": "text-to-gds.route.v1",
            "route_type": self.route_type,
            "points_um": [[x, y] for x, y in self.points_um],
            "length_um": self.length_um,
            "bend_count": self.bend_count,
            "trace_width_um": self.trace_width_um,
            "gap_um": self.gap_um,
            "bend_radius_um": self.bend_radius_um,
            "collision_free": self.collision_free,
            "metadata": self.metadata,
        }


def _snap(point: tuple[float, float], grid_um: float) -> tuple[float, float]:
    return (round(point[0] / grid_um) * grid_um, round(point[1] / grid_um) * grid_um)


def _length(points: tuple[tuple[float, float], ...]) -> float:
    return sum(
        math.hypot(b[0] - a[0], b[1] - a[1])
        for a, b in zip(points, points[1:], strict=False)
    )


def _collision_free(points: tuple[tuple[float, float], ...], spec: RouteSpec) -> bool:
    if not spec.obstacles:
        return True
    for start, end in zip(points, points[1:], strict=False):
        steps = max(int(math.hypot(end[0] - start[0], end[1] - start[1]) // max(spec.snap_um, 1e-9)), 1)
        for index in range(steps + 1):
            t = index / steps
            point = (start[0] + (end[0] - start[0]) * t, start[1] + (end[1] - start[1]) * t)
            if any(box.contains(point, spec.clearance_um) for box in spec.obstacles):
                return False
    return True


class RouteCPW:
    """Manhattan CPW route with impedance-preserving bend metadata."""

    route_type = "cpw"

    def build(self, spec: RouteSpec) -> RouteResult:
        start = _snap(spec.start_um, spec.snap_um)
        end = _snap(spec.end_um, spec.snap_um)
        dogleg_y = start[1] if abs(end[0] - start[0]) >= abs(end[1] - start[1]) else end[1]
        points = (start, (end[0], dogleg_y), end)
        if points[1] == points[0] or points[1] == points[2]:
            points = (start, end)
        length_um = _length(points)
        metadata: dict[str, Any] = {
            "impedance_preserving": True,
            "bend_model": "circular fillet annotation",
        }
        if spec.target_length_um and spec.target_length_um > length_um:
            horizontal_span = abs(end[0] - start[0])
            detour_y = (spec.target_length_um - horizontal_span + start[1] + end[1]) / 2.0
            detour_y = max(detour_y, start[1], end[1]) + spec.snap_um
            points = (
                start,
                _snap((start[0], detour_y), spec.snap_um),
                _snap((end[0], detour_y), spec.snap_um),
                end,
            )
            length_um = _length(points)
            metadata["length_matched_to_um"] = spec.target_length_um
        return RouteResult(
            route_type=self.route_type,
            points_um=points,
            length_um=length_um,
            bend_count=max(len(points) - 2, 0),
            trace_width_um=spec.trace_width_um,
            gap_um=spec.gap_um,
            bend_radius_um=spec.bend_radius_um,
            collision_free=_collision_free(points, spec),
            metadata=metadata,
        )


class RouteMeander(RouteCPW):
    """Length-matched meander route."""

    route_type = "meander"


class RouteFluxLine(RouteCPW):
    """Narrow flux-bias line route."""

    route_type = "flux_line"


class RouteAirbridge(RouteCPW):
    """Airbridge placement route over CPW gaps."""

    route_type = "airbridge"

    def build(self, spec: RouteSpec) -> RouteResult:
        result = super().build(spec)
        metadata = dict(result.metadata)
        metadata.update({"requires_release_layer": True, "landing_clearance_um": spec.clearance_um})
        return RouteResult(**{**result.__dict__, "metadata": metadata})
