"""Multi-layer Dolan-bridge and Manhattan Josephson junction pad structures.

Both styles are double-angle shadow-evaporation junctions. The geometry is
deterministic rectangles on five logical layers (base metal pads, first
electrode, second electrode, resist undercut, bandage). The overlap of the two
electrode layers is the junction area; everything else is leads and contacts.

The `I_c`, `L_J` and `E_J/h` numbers in the metadata are *geometric* estimates
from a user-supplied critical-current density; they are tagged
``analytical_estimate`` and are not fabrication evidence.
"""

from __future__ import annotations

import math

from pydantic import BaseModel

from textlayout.models import Geometry, Point, Polygon, Port, Technology, rectangle
from textlayout.ports.generator import Generator
from textlayout.research.formulas import josephson_inductance_ph
from textlayout.schemas.dsl.junction import JosephsonJunctionSpec

_PHI0_WB = 2.067_833_848e-15
_PLANCK_J_S = 6.626_070_15e-34


def junction_energy_ghz(critical_current_ua: float) -> float:
    """E_J / h in GHz for a junction with critical current ``I_c`` (µA)."""
    e_j = _PHI0_WB * critical_current_ua * 1e-6 / (2.0 * math.pi)
    return e_j / _PLANCK_J_S / 1e9


def _dolan(spec: JosephsonJunctionSpec, x0: float, y0: float) -> list[Polygon]:
    lw = spec.lead_width_um / 2.0
    jw = spec.junction_width_um / 2.0
    b = spec.bridge_um / 2.0
    ov = spec.overlap_um / 2.0
    y_b = -(spec.lead_length_um + b)  # bottom pad top edge
    y_t = spec.lead_length_um + b  # top pad bottom edge
    pw, ph = spec.pad_width_um / 2.0, spec.pad_height_um
    bs = spec.bandage_size_um / 2.0
    uc = spec.undercut_um
    return [
        rectangle(spec.metal, x0 - pw, y0 + y_b - ph, x0 + pw, y0 + y_b),
        rectangle(spec.metal, x0 - pw, y0 + y_t, x0 + pw, y0 + y_t + ph),
        # First electrode: lead up to the bridge, then a narrow finger across it.
        rectangle(spec.base_layer, x0 - lw, y0 + y_b, x0 + lw, y0 - b),
        rectangle(spec.base_layer, x0 - jw, y0 - b, x0 + jw, y0 + ov),
        # Second (shadow-shifted) electrode overlapping the finger tip.
        rectangle(spec.counter_layer, x0 - lw, y0 - ov, x0 + lw, y0 + y_t),
        # Resist undercut window around the bridge.
        rectangle(spec.undercut_layer, x0 - lw - uc, y0 - b - uc, x0 + lw + uc, y0 + b + uc),
        # Bandages at each pad/lead joint.
        rectangle(spec.bandage_layer, x0 - bs, y0 + y_b - bs, x0 + bs, y0 + y_b + bs),
        rectangle(spec.bandage_layer, x0 - bs, y0 + y_t - bs, x0 + bs, y0 + y_t + bs),
    ]


def _manhattan(spec: JosephsonJunctionSpec, x0: float, y0: float) -> list[Polygon]:
    jw = spec.junction_width_um / 2.0  # first finger half-width (along y)
    fw = spec.finger_width_um / 2.0  # second finger half-width (along x)
    ll = spec.lead_length_um
    pw, ph = spec.pad_width_um, spec.pad_height_um
    bs = spec.bandage_size_um / 2.0
    uc = spec.undercut_um
    overshoot = 2.0 * max(spec.junction_width_um, spec.finger_width_um)
    return [
        # Pads: left for the horizontal finger, bottom for the vertical finger.
        rectangle(spec.metal, x0 - ll - pw, y0 - ph / 2.0, x0 - ll, y0 + ph / 2.0),
        rectangle(spec.metal, x0 - pw / 2.0, y0 - ll - ph, x0 + pw / 2.0, y0 - ll),
        # First electrode finger along +x through the crossing.
        rectangle(spec.base_layer, x0 - ll, y0 - jw, x0 + fw + overshoot, y0 + jw),
        # Second electrode finger along +y through the crossing.
        rectangle(spec.counter_layer, x0 - fw, y0 - ll, x0 + fw, y0 + jw + overshoot),
        # Undercut square around the crossing.
        rectangle(
            spec.undercut_layer,
            x0 - max(jw, fw) - uc,
            y0 - max(jw, fw) - uc,
            x0 + max(jw, fw) + uc,
            y0 + max(jw, fw) + uc,
        ),
        rectangle(spec.bandage_layer, x0 - ll - bs, y0 - bs, x0 - ll + bs, y0 + bs),
        rectangle(spec.bandage_layer, x0 - bs, y0 - ll - bs, x0 + bs, y0 - ll + bs),
    ]


class JosephsonJunctionGenerator(Generator):
    """Generates Dolan or Manhattan junction pad structures."""

    name = "JosephsonJunction"
    params_model = JosephsonJunctionSpec

    def generate(self, params: BaseModel, tech: Technology, origin: Point) -> Geometry:
        assert isinstance(params, JosephsonJunctionSpec)
        x0, y0 = origin
        if params.style == "dolan":
            polygons = _dolan(params, x0, y0)
            y_b = -(params.lead_length_um + params.bridge_um / 2.0) - params.pad_height_um
            y_t = params.lead_length_um + params.bridge_um / 2.0 + params.pad_height_um
            ports = (
                Port("JJ_A", (x0, y0 + y_b), params.pad_width_um, 270.0, params.metal),
                Port("JJ_B", (x0, y0 + y_t), params.pad_width_um, 90.0, params.metal),
            )
        else:
            polygons = _manhattan(params, x0, y0)
            ll = params.lead_length_um
            ports = (
                Port(
                    "JJ_A",
                    (x0 - ll - params.pad_width_um, y0),
                    params.pad_height_um,
                    180.0,
                    params.metal,
                ),
                Port(
                    "JJ_B",
                    (x0, y0 - ll - params.pad_height_um),
                    params.pad_width_um,
                    270.0,
                    params.metal,
                ),
            )
        area = params.junction_area_um2
        metadata: dict[str, object] = {
            "component": "JosephsonJunction",
            "style": params.style,
            "junction_area_um2": round(area, 9),
            "layers": {
                "metal": params.metal,
                "base_electrode": params.base_layer,
                "counter_electrode": params.counter_layer,
                "undercut": params.undercut_layer,
                "bandage": params.bandage_layer,
            },
            "double_angle_evaporation": True,
            "process_placeholder_layers": True,
            "method": "geometry",
        }
        if params.critical_current_density_ua_per_um2 is not None:
            ic_ua = params.critical_current_density_ua_per_um2 * area
            metadata.update(
                {
                    "critical_current_ua": round(ic_ua, 9),
                    "josephson_inductance_ph": round(josephson_inductance_ph(ic_ua), 6),
                    "josephson_energy_ghz": round(junction_energy_ghz(ic_ua), 6),
                    "analytical_estimate": True,
                    "analytical_quantity": "junction critical current from J_c * area",
                }
            )
        return Geometry(
            name="JosephsonJunction", polygons=tuple(polygons), ports=ports, metadata=metadata
        )


__all__ = ["JosephsonJunctionGenerator", "junction_energy_ghz"]
