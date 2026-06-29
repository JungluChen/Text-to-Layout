"""RF launch pads and taper transitions for superconducting CPW circuits.

Provides bond pads, probe pads, and CPW taper transitions that bridge
wide bond/probe pads to narrow CPW feedlines.  Geometry follows standard
CPW launch designs from IQM/KQCircuits and Qiskit Metal references.
"""

from __future__ import annotations

import gdsfactory as gf

from text_to_gds.process import (
    DEFAULT_PROCESS,
    M1,
    M2,
    M3,
    MARKER,
    VIA12,
    Layer,
    require_minimum,
    require_positive,
)


def _rect(cx: float, cy: float, w: float, h: float) -> list[tuple[float, float]]:
    hw, hh = w / 2.0, h / 2.0
    return [(cx - hw, cy - hh), (cx + hw, cy - hh), (cx + hw, cy + hh), (cx - hw, cy + hh)]


@gf.cell
def cpw_launch_pad(
    pad_width: float = 200.0,
    pad_length: float = 200.0,
    trace_width: float = 10.0,
    gap: float = 6.0,
    taper_length: float = 100.0,
    ground_width: float = 100.0,
    signal_layer: Layer = M2,
    ground_layer: Layer = M1,
    marker_layer: Layer = MARKER,
) -> gf.Component:
    """CPW launch pad with smooth linear taper to a narrow CPW feedline.

    The pad is a wide rectangular bond/probe pad.  A trapezoidal taper
    transitions the pad width down to the CPW trace_width + gap geometry.
    Ground planes flank the entire structure with boolean-subtracted gaps.
    """
    for name, value in {
        "pad_width": pad_width,
        "pad_length": pad_length,
        "trace_width": trace_width,
        "gap": gap,
        "taper_length": taper_length,
        "ground_width": ground_width,
    }.items():
        require_positive(name, value)
    require_minimum("trace_width", trace_width, DEFAULT_PROCESS.rules.min_trace_width_um)
    require_minimum("gap", gap, DEFAULT_PROCESS.rules.min_cpw_gap_um)

    c = gf.Component()
    signal = gf.Component()
    clearance = gf.Component()

    total_length = pad_length + taper_length
    total_width = pad_width + 2.0 * gap + 2.0 * ground_width

    signal.add_polygon(_rect(-total_length / 2.0 + pad_length / 2.0, 0, pad_length, pad_width), layer=signal_layer)

    taper_x0 = -total_length / 2.0 + pad_length
    taper_x1 = taper_x0 + taper_length
    signal.add_polygon(
        [
            (taper_x0, -pad_width / 2.0),
            (taper_x1, -trace_width / 2.0),
            (taper_x1, trace_width / 2.0),
            (taper_x0, pad_width / 2.0),
        ],
        layer=signal_layer,
    )

    pad_gap = gap
    clearance.add_polygon(
        _rect(-total_length / 2.0 + pad_length / 2.0, 0, pad_length + 2.0 * pad_gap, pad_width + 2.0 * pad_gap),
        layer=ground_layer,
    )
    clearance.add_polygon(
        [
            (taper_x0 - pad_gap, -(pad_width / 2.0 + pad_gap)),
            (taper_x1, -(trace_width / 2.0 + gap)),
            (taper_x1, trace_width / 2.0 + gap),
            (taper_x0 - pad_gap, pad_width / 2.0 + pad_gap),
        ],
        layer=ground_layer,
    )

    ground = gf.components.rectangle(size=(total_length + 2.0 * gap, total_width), layer=ground_layer, centered=True)
    c.add_ref(gf.boolean(ground, clearance, operation="not", layer=ground_layer))
    c.add_ref(signal)

    c.add_port(
        name="pad",
        center=(-total_length / 2.0, 0),
        width=pad_width,
        orientation=180,
        layer=signal_layer,
        port_type="electrical",
    )
    c.add_port(
        name="cpw",
        center=(total_length / 2.0, 0),
        width=trace_width,
        orientation=0,
        layer=signal_layer,
        port_type="electrical",
    )

    c.info["device_type"] = "cpw_launch_pad"
    c.info["pad_width_um"] = pad_width
    c.info["pad_length_um"] = pad_length
    c.info["trace_width_um"] = trace_width
    c.info["gap_um"] = gap
    c.info["taper_length_um"] = taper_length
    c.info["ground_geometry"] = "subtractive_boolean_plane"
    return c


@gf.cell
def bond_pad(
    size: float = 100.0,
    metal_layer: Layer = M3,
    via_layer: Layer = VIA12,
    marker_layer: Layer = MARKER,
    via_size: float = 20.0,
    via_pitch: float = 30.0,
) -> gf.Component:
    """Simple wirebond pad with via array for multi-metal connection."""
    require_positive("size", size)
    require_positive("via_size", via_size)

    c = gf.Component()
    c.add_polygon(_rect(0, 0, size, size), layer=metal_layer)

    num_vias = max(1, int((size - 2.0 * via_size) / via_pitch))
    v0 = -(num_vias - 1) * via_pitch / 2.0
    for ix in range(num_vias):
        for iy in range(num_vias):
            vx = v0 + ix * via_pitch
            vy = v0 + iy * via_pitch
            c.add_polygon(_rect(vx, vy, via_size, via_size), layer=via_layer)

    c.add_port(name="pad", center=(0, 0), width=size, orientation=0, layer=metal_layer, port_type="electrical")

    c.info["device_type"] = "bond_pad"
    c.info["pad_size_um"] = size
    c.info["via_count"] = num_vias * num_vias
    return c


@gf.cell
def ground_strap(
    width: float = 10.0,
    span: float = 40.0,
    height: float = 4.0,
    layer: Layer = M3,
    marker_layer: Layer = MARKER,
) -> gf.Component:
    """Airbridge placeholder / ground strap across a CPW gap.

    This is an annotation-level placeholder.  Real airbridges require
    a dedicated lithographic step.  The marker layer indicates where
    an airbridge should be placed in fabrication.
    """
    require_positive("width", width)
    require_positive("span", span)

    c = gf.Component()
    c.add_polygon(_rect(0, 0, span, height), layer=layer)
    c.add_polygon(_rect(-span / 2.0, 0, width, height * 1.5), layer=layer)
    c.add_polygon(_rect(span / 2.0, 0, width, height * 1.5), layer=layer)
    c.add_polygon(_rect(0, 0, span + width, height + 2), layer=marker_layer)

    c.add_port(name="left", center=(-span / 2.0, 0), width=height, orientation=180, layer=layer)
    c.add_port(name="right", center=(span / 2.0, 0), width=height, orientation=0, layer=layer)

    c.info["device_type"] = "ground_strap"
    c.info["airbridge_placeholder"] = True
    c.info["span_um"] = span
    return c
