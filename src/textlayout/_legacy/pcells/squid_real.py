"""Fabrication-real DC SQUID with flux-bias line and connection pads.

Wraps dc_squid_pair with a flux-bias line, shunt capacitor option,
wirebond pads, and fabrication-real metadata.  Exactly two JJ overlap
regions must exist — verified by the extraction/review pipeline.
"""

from __future__ import annotations

import math

import gdsfactory as gf

from textlayout._legacy.pcells.junction import dc_squid_pair
from textlayout._legacy.pcells.layer_stack import KEEPOUT
from textlayout._legacy.pcells.passives import flux_bias_line
from textlayout._legacy.process import (
    DEFAULT_PROCESS,
    JJ,
    M1,
    M2,
    M3,
    MARKER,
    Layer,
    require_minimum,
    require_positive,
)

PHI0 = 2.067833848e-15


def _rect(cx: float, cy: float, w: float, h: float) -> list[tuple[float, float]]:
    hw, hh = w / 2.0, h / 2.0
    return [(cx - hw, cy - hh), (cx + hw, cy - hh), (cx + hw, cy + hh), (cx - hw, cy + hh)]


@gf.cell
def squid_real(
    junction_width: float = 0.22,
    junction_height: float = 0.22,
    lead_width: float = 1.0,
    loop_width: float = 14.0,
    loop_height: float = 10.0,
    jc_ua_per_um2: float = 2.0,
    pad_size: float = 80.0,
    pad_spacing: float = 20.0,
    flux_bias_length: float = 60.0,
    flux_bias_width: float = 1.5,
    flux_coupling_gap: float = 3.0,
    include_shunt_capacitor: bool = False,
    shunt_width: float = 20.0,
    shunt_length: float = 40.0,
    keepout_margin: float = 15.0,
    bottom_layer: Layer = M1,
    barrier_layer: Layer = JJ,
    top_layer: Layer = M2,
    wiring_layer: Layer = M3,
    marker_layer: Layer = MARKER,
) -> gf.Component:
    """Fabrication-real DC SQUID with flux-bias line, pads, and full provenance."""
    require_positive("junction_width", junction_width)
    require_positive("junction_height", junction_height)
    require_positive("loop_width", loop_width)
    require_positive("loop_height", loop_height)
    require_positive("jc_ua_per_um2", jc_ua_per_um2)
    require_minimum("junction_width", junction_width, DEFAULT_PROCESS.rules.min_junction_width_um)
    require_minimum("junction_height", junction_height, DEFAULT_PROCESS.rules.min_junction_height_um)

    c = gf.Component()

    squid = dc_squid_pair(
        junction_width=junction_width,
        junction_height=junction_height,
        lead_width=lead_width,
        loop_width=loop_width,
        loop_height=loop_height,
        bottom_layer=bottom_layer,
        barrier_layer=barrier_layer,
        top_layer=top_layer,
        marker_layer=marker_layer,
    )
    c.add_ref(squid)

    flux = flux_bias_line(
        length=flux_bias_length,
        width=flux_bias_width,
        coupling_length=loop_width * 0.8,
        coupling_gap=flux_coupling_gap,
        layer=top_layer,
        marker_layer=marker_layer,
    )
    flux_ref = c.add_ref(flux)
    flux_ref.move((0, -loop_height / 2.0 - flux_coupling_gap - flux_bias_width))

    half_h = loop_height / 2.0
    for sign, name, orient in [(-1, "bottom_pad", 270), (1, "top_pad", 90)]:
        pad_y = sign * (half_h + pad_spacing + pad_size / 2.0)
        c.add_polygon(_rect(0, pad_y, pad_size, pad_size), layer=wiring_layer)
        c.add_port(
            name=name,
            center=(0, pad_y),
            width=pad_size,
            orientation=orient,
            layer=wiring_layer,
            port_type="electrical",
        )

    for name, port in flux.ports.items():
        new_center = (port.center[0] + flux_ref.origin[0], port.center[1] + flux_ref.origin[1])
        c.add_port(
            name=f"flux_{name}",
            center=new_center,
            width=port.width,
            orientation=port.orientation,
            layer=top_layer,
            port_type="electrical",
        )

    if include_shunt_capacitor:
        shunt_y = half_h + pad_spacing + pad_size + 10.0
        c.add_polygon(_rect(-shunt_width / 2.0 - 2, shunt_y, shunt_width, shunt_length), layer=bottom_layer)
        c.add_polygon(_rect(shunt_width / 2.0 + 2, shunt_y, shunt_width, shunt_length), layer=top_layer)

    extent = half_h + pad_spacing + pad_size + keepout_margin
    c.add_polygon(_rect(0, 0, 2 * extent, 2 * extent), layer=KEEPOUT)

    single_area = junction_width * junction_height
    total_area = 2.0 * single_area
    ic_single = jc_ua_per_um2 * single_area
    ic_total = 2.0 * ic_single
    ic_a = ic_single * 1e-6
    lj_single_ph = PHI0 / (2.0 * math.pi * ic_a) * 1e12 if ic_a > 0 else float("inf")
    loop_inner_w = max(loop_width - 2 * lead_width, 0)
    loop_inner_h = max(loop_height - 2 * lead_width, 0)
    loop_area_um2 = loop_inner_w * loop_inner_h
    loop_perimeter_um = 2.0 * (loop_inner_w + loop_inner_h)
    mu0 = 4.0 * math.pi * 1e-7
    estimated_loop_inductance_ph = mu0 * loop_perimeter_um * 1e-6 / (2.0 * math.pi) * 1e12

    c.info["device_type"] = "squid_real"
    c.info["layout_quality_mode"] = "fabrication_real"
    c.info["visualization_only"] = False
    c.info["squid_junction_count"] = 2
    c.info["junction_width_um"] = junction_width
    c.info["junction_height_um"] = junction_height
    c.info["single_junction_area_um2"] = single_area
    c.info["total_junction_area_um2"] = total_area
    c.info["junction_area_method"] = "polygon_boolean_extraction_required"
    c.info["loop_width_um"] = loop_width
    c.info["loop_height_um"] = loop_height
    c.info["loop_area_um2"] = loop_area_um2
    c.info["loop_perimeter_um"] = loop_perimeter_um
    c.info["jc_ua_per_um2"] = jc_ua_per_um2
    c.info["ic_single_ua"] = ic_single
    c.info["ic_total_ua"] = ic_total
    c.info["lj_single_ph"] = lj_single_ph
    c.info["estimated_loop_inductance_ph"] = estimated_loop_inductance_ph
    c.info["has_flux_bias_line"] = True
    c.info["has_wirebond_pads"] = True
    c.info["has_keepout"] = True
    c.info["include_shunt_capacitor"] = include_shunt_capacitor
    c.info["extraction"] = {
        "single_junction_area_um2": {
            "value": single_area,
            "method": "analytical",
            "source": "GDS_geometry",
            "formula": "junction_width * junction_height",
            "confidence": 0.95,
            "unit": "um2",
        },
        "ic_single_ua": {
            "value": ic_single,
            "method": "estimated",
            "source": "Jc_process_parameter",
            "formula": "Ic = Jc * A_jj",
            "confidence": 0.80,
            "unit": "uA",
        },
        "lj_single_ph": {
            "value": lj_single_ph,
            "method": "estimated",
            "source": "Ambegaokar-Baratoff",
            "formula": "Lj = Phi0 / (2*pi*Ic)",
            "confidence": 0.75,
            "unit": "pH",
        },
        "loop_inductance_ph": {
            "value": estimated_loop_inductance_ph,
            "method": "estimated",
            "source": "geometric_estimate",
            "formula": "L ~ mu0 * perimeter / (2*pi)",
            "confidence": 0.50,
            "unit": "pH",
        },
    }
    c.info["layers"] = {
        "bottom_electrode": bottom_layer,
        "junction_barrier": barrier_layer,
        "top_electrode": top_layer,
        "wiring": wiring_layer,
        "keepout": KEEPOUT,
        "marker": marker_layer,
    }
    c.info["quality_record"] = {
        "status": "fabrication_real",
        "checks": ["two_jj_overlap", "flux_bias", "wirebond_pads", "keepout", "loop_geometry"],
    }
    return c
