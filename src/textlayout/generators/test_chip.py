"""Research test-chip tile generator: IDC + CPW + spiral + marks + title.

The tile composes the existing single-device generators — each sub-block is
byte-identical to the standalone device with the same parameters — and adds
corner alignment crosses, a geometric title label (5×7 stroke font on the TEXT
layer), and a TEXT-layer tile outline so the bounding box equals the requested
tile size exactly.

The tile is a *layout candidate for comparison structures*; nothing here claims
electrical verification of any sub-block.
"""

from __future__ import annotations

from pydantic import BaseModel

from textlayout.generators.cpw import CPWGenerator
from textlayout.generators.idc import IDCGenerator
from textlayout.generators.spiral import SpiralInductorGenerator
from textlayout.generators.text_font import text_height_um, text_polygons, text_width_um
from textlayout.models import Geometry, Point, Polygon, Port, Technology, rectangle
from textlayout.ports.generator import Generator
from textlayout.schemas.dsl.cpw import CPWSpec
from textlayout.schemas.dsl.idc import IDCSpec
from textlayout.schemas.dsl.spiral import SpiralInductorSpec
from textlayout.schemas.dsl.test_chip import TestChipSpec

_OUTLINE_WIDTH_UM = 5.0


class TestChipGenerator(Generator):
    """Generates a multi-device research comparison tile."""

    name = "TestChip"
    params_model = TestChipSpec

    def generate(self, params: BaseModel, tech: Technology, origin: Point) -> Geometry:
        assert isinstance(params, TestChipSpec)
        x0, y0 = origin
        w, h = params.tile_width_um, params.tile_height_um
        margin = params.margin_um
        metal = params.metal_layer

        polygons: list[Polygon] = []
        ports: list[Port] = []
        placements: dict[str, dict[str, object]] = {}

        # TEXT-layer tile outline: annotation only, pins the bbox to the tile.
        polygons.extend(_outline(params.text_layer, x0, y0, w, h))

        # Alignment crosses in all four corners (metal layer).
        mark_offset = margin / 2.0
        for corner_x, corner_y in (
            (x0 + mark_offset, y0 + mark_offset),
            (x0 + w - mark_offset, y0 + mark_offset),
            (x0 + mark_offset, y0 + h - mark_offset),
            (x0 + w - mark_offset, y0 + h - mark_offset),
        ):
            polygons.extend(
                _alignment_cross(
                    metal,
                    (corner_x, corner_y),
                    params.alignment_mark_size_um,
                    params.alignment_mark_width_um,
                )
            )

        # Title label (TEXT layer), top-left inside the margin.
        title_y = y0 + h - margin - text_height_um(params.title_cell_um)
        polygons.extend(
            text_polygons(
                params.title,
                layer=params.text_layer,
                origin=(x0 + margin, title_y),
                cell_um=params.title_cell_um,
            )
        )

        # IDC — lower-left quadrant.
        idc_spec = IDCSpec(
            finger_pairs=params.idc_finger_pairs,
            finger_width_um=params.idc_finger_width_um,
            gap_um=params.idc_gap_um,
            overlap_um=params.idc_overlap_um,
            bus_width_um=params.idc_bus_width_um,
            metal_layer=metal,
        )
        idc_origin = (x0 + margin, y0 + margin)
        idc = IDCGenerator().generate(idc_spec, tech, idc_origin)
        placements["IDC"] = _placement(idc, idc_origin, len(polygons))
        polygons.extend(idc.polygons)
        ports.extend(_prefixed_ports(idc.ports, "IDC"))

        # CPW — lower-right quadrant, running vertically.
        cpw_spec = CPWSpec(
            center_width_um=params.cpw_center_width_um,
            gap_um=params.cpw_gap_um,
            ground_width_um=params.cpw_ground_width_um,
            length_um=params.cpw_length_um,
            metal=metal,
        )
        cpw_origin = (x0 + 0.72 * w, y0 + margin)
        cpw = CPWGenerator().generate(cpw_spec, tech, cpw_origin)
        placements["CPW"] = _placement(cpw, cpw_origin, len(polygons))
        polygons.extend(cpw.polygons)
        ports.extend(_prefixed_ports(cpw.ports, "CPW"))

        # Spiral inductor — upper-right quadrant.
        spiral_spec = SpiralInductorSpec(
            turns=params.spiral_turns,
            outer_dimension_um=params.spiral_outer_dimension_um,
            trace_width_um=params.spiral_trace_width_um,
            spacing_um=params.spiral_spacing_um,
            metal=metal,
        )
        spiral_origin = (
            x0 + w - margin - params.spiral_outer_dimension_um,
            y0 + h - margin - params.spiral_outer_dimension_um,
        )
        spiral = SpiralInductorGenerator().generate(spiral_spec, tech, spiral_origin)
        placements["SpiralInductor"] = _placement(spiral, spiral_origin, len(polygons))
        polygons.extend(spiral.polygons)
        ports.extend(_prefixed_ports(spiral.ports, "SP"))

        return Geometry(
            name="TestChip",
            polygons=tuple(polygons),
            ports=tuple(ports),
            metadata={
                "component": "TestChip",
                "metal_layer": metal,
                "text_layer": params.text_layer,
                "tile_width_um": w,
                "tile_height_um": h,
                "title": params.title,
                "title_width_um": round(text_width_um(params.title, params.title_cell_um), 4),
                "alignment_marks": 4,
                "min_ports": 2,
                "sub_devices": placements,
                "estimated_capacitance_pf": idc.metadata["estimated_capacitance_pf"],
                "estimated_z0_ohm": cpw.metadata["estimated_z0_ohm"],
                "estimated_inductance_nh": spiral.metadata.get("estimated_inductance_nh"),
                "analytical_estimate": True,
                "analytical_quantity": "per-sub-device estimates (see sub_devices)",
                "simulation_scope": {
                    "IDC": "FasterCap-extractable standalone (geometry-identical sub-block)",
                    "CPW": "geometry-only in this tile (analytical Z0 estimate)",
                    "SpiralInductor": "geometry-only in this tile (analytical L estimate)",
                    "alignment_marks": "geometry-only",
                    "title": "geometry-only",
                },
            },
        )


def _outline(layer: str, x0: float, y0: float, w: float, h: float) -> list[Polygon]:
    t = _OUTLINE_WIDTH_UM
    return [
        rectangle(layer, x0, y0, x0 + w, y0 + t),
        rectangle(layer, x0, y0 + h - t, x0 + w, y0 + h),
        rectangle(layer, x0, y0 + t, x0 + t, y0 + h - t),
        rectangle(layer, x0 + w - t, y0 + t, x0 + w, y0 + h - t),
    ]


def _alignment_cross(
    layer: str, center: tuple[float, float], size_um: float, width_um: float
) -> list[Polygon]:
    cx, cy = center
    half = size_um / 2.0
    half_w = width_um / 2.0
    return [
        rectangle(layer, cx - half, cy - half_w, cx + half, cy + half_w),
        rectangle(layer, cx - half_w, cy - half, cx + half_w, cy + half),
    ]


def _prefixed_ports(ports: tuple[Port, ...], prefix: str) -> list[Port]:
    return [
        Port(f"{prefix}_{port.name}", port.center, port.width, port.orientation, port.layer)
        for port in ports
    ]


def _placement(sub: Geometry, origin: tuple[float, float], polygon_start: int) -> dict[str, object]:
    return {
        "origin": [origin[0], origin[1]],
        "polygon_start": polygon_start,
        "polygon_count": len(sub.polygons),
        "metadata": dict(sub.metadata),
    }
