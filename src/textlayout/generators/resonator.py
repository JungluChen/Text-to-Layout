"""Deterministic capacitively coupled quarter-wave CPW resonator."""

from __future__ import annotations

from pydantic import BaseModel

from textlayout.models import Geometry, Point, Polygon, Port, Technology, rectangle
from textlayout.ports.generator import Generator
from textlayout.research.formulas import cpw_eps_eff
from textlayout.schemas.dsl import QuarterWaveResonatorSpec


class QuarterWaveResonatorGenerator(Generator):
    """Generate a straight CPW hanger with feedline, open end, and grounded short."""

    name = "QuarterWaveResonator"
    params_model = QuarterWaveResonatorSpec

    def generate(self, params: BaseModel, tech: Technology, origin: Point) -> Geometry:
        assert isinstance(params, QuarterWaveResonatorSpec)
        x0, y0 = origin
        w = params.center_width_um
        gap = params.gap_um
        gw = params.ground_width_um
        half_w = w / 2.0
        ground_inner = half_w + gap
        y_hi = y0 + params.length_um
        feed_y0 = y_hi + params.coupling_gap_um
        feed_y1 = feed_y0 + w
        feed_x0 = x0 - params.feedline_length_um / 2.0
        feed_x1 = x0 + params.feedline_length_um / 2.0
        metal = params.metal

        polygons: tuple[Polygon, ...] = (
            rectangle(metal, x0 - half_w, y0, x0 + half_w, y_hi),
            rectangle(metal, x0 - ground_inner - gw, y0, x0 - ground_inner, y_hi),
            rectangle(metal, x0 + ground_inner, y0, x0 + ground_inner + gw, y_hi),
            rectangle(metal, x0 - ground_inner, y0, x0 + ground_inner, y0 + params.short_width_um),
            rectangle(metal, feed_x0, feed_y0, feed_x1, feed_y1),
            rectangle(metal, feed_x0, feed_y1 + gap, feed_x1, feed_y1 + gap + gw),
            rectangle(
                metal,
                feed_x0,
                feed_y0 - gap - gw,
                x0 - ground_inner,
                feed_y0 - gap,
            ),
            rectangle(
                metal,
                x0 + ground_inner,
                feed_y0 - gap - gw,
                feed_x1,
                feed_y0 - gap,
            ),
        )
        ports = (
            Port("RF_IN", (feed_x0, (feed_y0 + feed_y1) / 2.0), w, 180.0, metal),
            Port("RF_OUT", (feed_x1, (feed_y0 + feed_y1) / 2.0), w, 0.0, metal),
            Port("GND_TOP_IN", (feed_x0, feed_y1 + gap + gw / 2.0), gw, 180.0, metal),
            Port("GND_TOP_OUT", (feed_x1, feed_y1 + gap + gw / 2.0), gw, 0.0, metal),
            Port("GND_BOTTOM_IN", (feed_x0, feed_y0 - gap - gw / 2.0), gw, 180.0, metal),
            Port("GND_BOTTOM_OUT", (feed_x1, feed_y0 - gap - gw / 2.0), gw, 0.0, metal),
        )
        eps_eff = cpw_eps_eff(tech.substrate_epsilon_r)
        return Geometry(
            name="QuarterWaveResonator",
            polygons=polygons,
            ports=ports,
            metadata={
                "component": "QuarterWaveResonator",
                "metal": metal,
                "electrical_length_um": params.length_um,
                "effective_permittivity": round(eps_eff, 4),
                "coupling_gap_um": params.coupling_gap_um,
                "boundary_open": "capacitively coupled feedline end",
                "boundary_short": "ground bridge",
                "resonator_centerline_um": [[x0, y0], [x0, y_hi]],
                "physical_grounded_end_um": [x0, y0],
                "physical_open_end_um": [x0, y_hi],
                "ground_connection_bbox_um": [
                    x0 - ground_inner,
                    y0,
                    x0 + ground_inner,
                    y0 + params.short_width_um,
                ],
                "coupling_gap_bbox_um": [
                    x0 - half_w,
                    y_hi,
                    x0 + half_w,
                    feed_y0,
                ],
                "polygon_roles": [
                    "resonator_signal",
                    "resonator_ground_left",
                    "resonator_ground_right",
                    "grounded_end_bridge",
                    "feedline_signal",
                    "feedline_ground_top",
                    "feedline_ground_bottom_left",
                    "feedline_ground_bottom_right",
                ],
                "explicit_ground_reference_ports": True,
                "min_ports": 6,
                "analytical_estimate": True,
                "analytical_quantity": "resonance frequency",
            },
        )
