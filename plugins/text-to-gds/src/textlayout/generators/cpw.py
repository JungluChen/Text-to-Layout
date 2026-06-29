"""Coplanar Waveguide (CPW) generator.

A reference implementation of :class:`Generator`. It is intentionally small and
fully deterministic — the template every future device generator follows.
"""

from __future__ import annotations

from pydantic import BaseModel

from textlayout.models import Geometry, Point, Polygon, Port, Technology, rectangle
from textlayout.research.formulas import cpw_z0
from textlayout.ports.generator import Generator
from textlayout.schemas.dsl.cpw import CPWSpec


class CPWGenerator(Generator):
    """Generates a straight coplanar-waveguide segment.

    Layout (cross-section, x axis), centered on ``origin`` and running +y::

        ground │ gap │   signal   │ gap │ ground      (all on the metal layer)
        ◄─gw─► ◄─g─► ◄────w─────► ◄─g─► ◄─gw─►
    """

    name = "CPW"
    params_model = CPWSpec

    def generate(self, params: BaseModel, tech: Technology, origin: Point) -> Geometry:
        assert isinstance(params, CPWSpec)  # narrowed by the engine; guards misuse
        x0, y0 = origin
        w = params.center_width_um
        g = params.gap_um
        gw = params.ground_width_um
        length = params.length_um
        metal = params.metal

        y_lo, y_hi = y0, y0 + length
        half_w = w / 2.0
        ground_inner = half_w + g  # inner edge of each ground plane

        signal = rectangle(metal, x0 - half_w, y_lo, x0 + half_w, y_hi)
        ground_left = rectangle(
            metal, x0 - ground_inner - gw, y_lo, x0 - ground_inner, y_hi
        )
        ground_right = rectangle(
            metal, x0 + ground_inner, y_lo, x0 + ground_inner + gw, y_hi
        )

        polygons: tuple[Polygon, ...] = (signal, ground_left, ground_right)
        ports = (
            Port("RF_IN", (x0, y_lo), w, 270.0, metal),
            Port("RF_OUT", (x0, y_hi), w, 90.0, metal),
            Port("GND_L_IN", (x0 - ground_inner - gw / 2.0, y_lo), gw, 270.0, metal),
            Port("GND_L_OUT", (x0 - ground_inner - gw / 2.0, y_hi), gw, 90.0, metal),
            Port("GND_R_IN", (x0 + ground_inner + gw / 2.0, y_lo), gw, 270.0, metal),
            Port("GND_R_OUT", (x0 + ground_inner + gw / 2.0, y_hi), gw, 90.0, metal),
        )
        z0, eps_eff = cpw_z0(w, g, tech.substrate_epsilon_r)
        return Geometry(
            name="CPW",
            polygons=polygons,
            ports=ports,
            metadata={
                "component": "CPW",
                "metal": metal,
                "center_width_um": w,
                "gap_um": g,
                "ground_width_um": gw,
                "length_um": length,
                "min_ports": 6,
                "explicit_ground_reference_ports": True,
                "estimated_z0_ohm": round(z0, 4),
                "effective_permittivity": round(eps_eff, 4),
                "analytical_estimate": True,
                "analytical_quantity": "characteristic impedance",
            },
        )
