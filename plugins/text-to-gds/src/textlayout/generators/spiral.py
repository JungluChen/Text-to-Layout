"""Deterministic square planar-spiral generator."""

from __future__ import annotations

from pydantic import BaseModel

from textlayout.generators._path import orthogonal_path_rectangles, path_length
from textlayout.models import Geometry, Point, Port, Technology
from textlayout.ports.generator import Generator
from textlayout.research.formulas import spiral_inductance_nh
from textlayout.schemas.dsl import SpiralInductorSpec


class SpiralInductorGenerator(Generator):
    """Generate one continuous open square spiral with two electrical ports."""

    name = "SpiralInductor"
    params_model = SpiralInductorSpec

    def generate(self, params: BaseModel, tech: Technology, origin: Point) -> Geometry:
        assert isinstance(params, SpiralInductorSpec)
        x0, y0 = origin
        width = params.trace_width_um
        spacing = params.spacing_um
        pitch = width + spacing
        outer = params.outer_dimension_um
        required = 2.0 * params.turns * width + 2.0 * (params.turns - 1) * spacing
        if outer <= required:
            raise ValueError(
                f"outer_dimension_um={outer} must exceed winding width {required} for "
                f"{params.turns} turns"
            )

        half = width / 2.0
        points: list[Point] = [(x0 + half, y0 + half)]
        for level in range(params.turns):
            left = x0 + half + level * pitch
            right = x0 + outer - half - level * pitch
            bottom = y0 + half + level * pitch
            top = y0 + outer - half - level * pitch
            if points[-1] != (left, bottom):
                points.append((left, bottom))
            points.extend(((right, bottom), (right, top), (left, top)))
            if level < params.turns - 1:
                points.extend(((left, bottom + pitch), (left + pitch, bottom + pitch)))

        inner = outer - required
        estimate = spiral_inductance_nh(params.turns, outer, inner)
        polygons = orthogonal_path_rectangles(params.metal, points, width)
        ports = (
            Port("P1", points[0], width, 180.0, params.metal),
            Port("P2", points[-1], width, 180.0, params.metal),
        )
        return Geometry(
            name="SpiralInductor",
            polygons=polygons,
            ports=ports,
            metadata={
                "component": "SpiralInductor",
                "metal": params.metal,
                "turns": params.turns,
                "outer_dimension_um": outer,
                "inner_dimension_um": round(inner, 4),
                "trace_width_um": width,
                "spacing_um": spacing,
                "thickness_um": params.thickness_um,
                "centerline_points_um": [list(point) for point in points],
                "centerline_length_um": round(path_length(points), 4),
                "estimated_inductance_nh": round(estimate, 4),
                "min_ports": 2,
                "analytical_estimate": True,
                "analytical_quantity": "inductance",
            },
        )

