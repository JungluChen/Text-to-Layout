"""Ground-plane flux-pinning perforation arrays with trace keep-out margins.

Flux vortices trapped in a wide superconducting ground plane add dissipation
and 1/f noise; a lattice of small holes pins them where the microwave current
density is low. Holes must never approach signal traces, so every keep-out
rectangle (typically the CPW trace plus a margin) suppresses any hole whose
footprint, grown by ``keep_out_margin_um``, intersects it.
"""

from __future__ import annotations

from collections.abc import Sequence

from pydantic import BaseModel

from textlayout.models import Geometry, Point, Polygon, Port, Technology, rectangle
from textlayout.ports.generator import Generator
from textlayout.schemas.dsl.perforation import KeepOutRect, PerforationSpec


def _grid_positions(extent: float, pitch: float, margin: float, hole: float) -> list[float]:
    """Hole centers along one axis, symmetric about the window center."""
    usable = extent - 2.0 * margin - hole
    if usable < 0.0:
        return []
    count = int(usable // pitch) + 1
    span = (count - 1) * pitch
    start = (extent - span) / 2.0
    return [start + i * pitch for i in range(count)]


def _blocked(cx: float, cy: float, half: float, keep_outs: Sequence[KeepOutRect]) -> bool:
    x0, y0, x1, y1 = cx - half, cy - half, cx + half, cy + half
    for region in keep_outs:
        if x0 < region.xmax and x1 > region.xmin and y0 < region.ymax and y1 > region.ymin:
            return True
    return False


def perforation_holes(spec: PerforationSpec, origin: Point = (0.0, 0.0)) -> tuple[Polygon, ...]:
    """Return the hole polygons for ``spec`` with the window's lower-left at ``origin``."""
    ox, oy = origin
    half = spec.hole_size_um / 2.0
    grown = half + spec.keep_out_margin_um
    xs = _grid_positions(
        spec.window_width_um, spec.pitch_um, spec.edge_margin_um, spec.hole_size_um
    )
    ys = _grid_positions(
        spec.window_height_um, spec.pitch_um, spec.edge_margin_um, spec.hole_size_um
    )
    holes: list[Polygon] = []
    for cy in ys:
        for cx in xs:
            if _blocked(cx, cy, grown, spec.keep_outs):
                continue
            holes.append(
                rectangle(
                    spec.hole_layer, ox + cx - half, oy + cy - half, ox + cx + half, oy + cy + half
                )
            )
    return tuple(holes)


class PerforationGenerator(Generator):
    """Generates a ground window and its flux-trap hole lattice."""

    name = "GroundPerforation"
    params_model = PerforationSpec

    def generate(self, params: BaseModel, tech: Technology, origin: Point) -> Geometry:
        assert isinstance(params, PerforationSpec)
        x0, y0 = origin
        holes = perforation_holes(params, origin)
        polygons: list[Polygon] = []
        if params.emit_ground:
            polygons.append(
                rectangle(
                    params.metal, x0, y0, x0 + params.window_width_um, y0 + params.window_height_um
                )
            )
        polygons.extend(holes)
        total_sites = len(
            _grid_positions(
                params.window_width_um, params.pitch_um, params.edge_margin_um, params.hole_size_um
            )
        ) * len(
            _grid_positions(
                params.window_height_um, params.pitch_um, params.edge_margin_um, params.hole_size_um
            )
        )
        hole_area = len(holes) * params.hole_size_um**2
        window_area = params.window_width_um * params.window_height_um
        ports = (
            Port(
                "GND_REF",
                (x0 + params.window_width_um / 2.0, y0),
                params.window_width_um,
                270.0,
                params.metal,
            ),
        )
        return Geometry(
            name="GroundPerforation",
            polygons=tuple(polygons),
            ports=ports,
            metadata={
                "component": "GroundPerforation",
                "metal": params.metal,
                "hole_layer": params.hole_layer,
                "hole_size_um": params.hole_size_um,
                "pitch_um": params.pitch_um,
                "keep_out_margin_um": params.keep_out_margin_um,
                "edge_margin_um": params.edge_margin_um,
                "keep_out_count": len(params.keep_outs),
                "grid_sites": total_sites,
                "holes_emitted": len(holes),
                "holes_suppressed_by_keep_out": total_sites - len(holes),
                "hole_fill_fraction": round(hole_area / window_area, 6) if window_area else 0.0,
                "subtractive_hole_layer": True,
                "method": "geometry",
            },
        )


__all__ = ["PerforationGenerator", "perforation_holes"]
