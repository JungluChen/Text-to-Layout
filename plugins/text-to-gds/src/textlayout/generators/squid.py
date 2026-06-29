"""Generic symmetric two-junction SQUID test-structure generator."""

from __future__ import annotations

from pydantic import BaseModel

from textlayout.models import Geometry, Point, Port, Technology, rectangle
from textlayout.ports.generator import Generator
from textlayout.schemas.dsl import SQUIDSpec


class SQUIDGenerator(Generator):
    """Generate a symmetric loop while retaining an explicit process-stack warning."""

    name = "SQUID"
    params_model = SQUIDSpec

    def generate(self, params: BaseModel, tech: Technology, origin: Point) -> Geometry:
        assert isinstance(params, SQUIDSpec)
        x0, y0 = origin
        iw = params.loop_inner_width_um
        ih = params.loop_inner_height_um
        trace = params.trace_width_um
        gap = params.junction_gap_um
        jwidth = params.junction_width_um
        left0, left1 = x0 - iw / 2.0 - trace, x0 - iw / 2.0
        right0, right1 = x0 + iw / 2.0, x0 + iw / 2.0 + trace
        bottom0, bottom1 = y0 - ih / 2.0 - trace, y0 - ih / 2.0
        top0, top1 = y0 + ih / 2.0, y0 + ih / 2.0 + trace

        polygons = [
            rectangle(params.metal, left0, bottom0, right1, bottom1),
            rectangle(params.metal, left0, top0, right1, top1),
            rectangle(params.metal, left0, bottom1, left1, y0 - gap / 2.0),
            rectangle(params.metal, left0, y0 + gap / 2.0, left1, top0),
            rectangle(params.metal, right0, bottom1, right1, y0 - gap / 2.0),
            rectangle(params.metal, right0, y0 + gap / 2.0, right1, top0),
            rectangle(
                params.junction_layer,
                (left0 + left1 - jwidth) / 2.0,
                y0 - gap / 2.0,
                (left0 + left1 + jwidth) / 2.0,
                y0 + gap / 2.0,
            ),
            rectangle(
                params.junction_layer,
                (right0 + right1 - jwidth) / 2.0,
                y0 - gap / 2.0,
                (right0 + right1 + jwidth) / 2.0,
                y0 + gap / 2.0,
            ),
        ]
        stem_half = trace / 2.0
        pad_half = params.pad_width_um / 2.0
        polygons.extend(
            (
                rectangle(params.metal, x0 - stem_half, top1, x0 + stem_half, top1 + trace),
                rectangle(
                    params.metal,
                    x0 - pad_half,
                    top1 + trace,
                    x0 + pad_half,
                    top1 + trace + params.pad_height_um,
                ),
                rectangle(params.metal, x0 - stem_half, bottom0 - trace, x0 + stem_half, bottom0),
                rectangle(
                    params.metal,
                    x0 - pad_half,
                    bottom0 - trace - params.pad_height_um,
                    x0 + pad_half,
                    bottom0 - trace,
                ),
            )
        )
        ports = (
            Port("BIAS_P", (x0, top1 + trace + params.pad_height_um), params.pad_width_um, 90.0, params.metal),
            Port("BIAS_N", (x0, bottom0 - trace - params.pad_height_um), params.pad_width_um, 270.0, params.metal),
        )
        loop_area = iw * ih
        return Geometry(
            name="SQUID",
            polygons=tuple(polygons),
            ports=ports,
            metadata={
                "component": "SQUID",
                "metal": params.metal,
                "junction_layer": params.junction_layer,
                "junction_count": 2,
                "junctions_are_process_placeholders": True,
                "foundry_stack_required": True,
                "loop_area_um2": round(loop_area, 4),
                "symmetry_axis_x_um": x0,
                "min_ports": 2,
                "analytical_estimate": True,
                "analytical_quantity": "flux modulation period",
            },
        )

