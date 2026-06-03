from __future__ import annotations

import gdsfactory as gf

from text_to_gds.process import DEFAULT_PROCESS, JJ, M1, M2, MARKER, Layer, require_minimum, require_positive

gf.gpdk.get_generic_pdk().activate()

BOTTOM_ELECTRODE: Layer = M1
BARRIER: Layer = JJ
TOP_ELECTRODE: Layer = M2
MARKER_LAYER: Layer = MARKER


def _rectangle(cx: float, cy: float, width: float, height: float) -> list[tuple[float, float]]:
    half_w = width / 2.0
    half_h = height / 2.0
    return [
        (cx - half_w, cy - half_h),
        (cx + half_w, cy - half_h),
        (cx + half_w, cy + half_h),
        (cx - half_w, cy + half_h),
    ]


@gf.cell
def manhattan_josephson_junction(
    junction_width: float = 0.22,
    junction_height: float = 0.22,
    lead_width: float = 1.0,
    lead_length: float = 6.0,
    bottom_layer: Layer = BOTTOM_ELECTRODE,
    barrier_layer: Layer = BARRIER,
    top_layer: Layer = TOP_ELECTRODE,
    marker_layer: Layer = MARKER_LAYER,
) -> gf.Component:
    """Simple Manhattan-style Josephson Junction PCell in microns."""
    for name, value in {
        "junction_width": junction_width,
        "junction_height": junction_height,
        "lead_width": lead_width,
        "lead_length": lead_length,
    }.items():
        require_positive(name, value)

    require_minimum(
        "junction_width", junction_width, DEFAULT_PROCESS.rules.min_junction_width_um
    )
    require_minimum(
        "junction_height", junction_height, DEFAULT_PROCESS.rules.min_junction_height_um
    )
    require_minimum("lead_width", lead_width, DEFAULT_PROCESS.rules.min_trace_width_um)

    c = gf.Component()

    c.add_polygon(_rectangle(0, 0, 2 * lead_length, lead_width), layer=bottom_layer)
    c.add_polygon(_rectangle(0, 0, lead_width, 2 * lead_length), layer=top_layer)
    c.add_polygon(_rectangle(0, 0, junction_width, junction_height), layer=barrier_layer)

    c.add_port(
        name="bottom_west",
        center=(-lead_length, 0),
        width=lead_width,
        orientation=180,
        layer=bottom_layer,
        port_type="electrical",
    )
    c.add_port(
        name="bottom_east",
        center=(lead_length, 0),
        width=lead_width,
        orientation=0,
        layer=bottom_layer,
        port_type="electrical",
    )
    c.add_port(
        name="top_south",
        center=(0, -lead_length),
        width=lead_width,
        orientation=270,
        layer=top_layer,
        port_type="electrical",
    )
    c.add_port(
        name="top_north",
        center=(0, lead_length),
        width=lead_width,
        orientation=90,
        layer=top_layer,
        port_type="electrical",
    )

    junction_area_um2 = junction_width * junction_height
    c.add_label(f"JJ area {junction_area_um2:.6g} um2", position=(0, 0), layer=marker_layer)

    c.info["device_type"] = "manhattan_josephson_junction"
    c.info["junction_area_um2"] = junction_area_um2
    c.info["junction_width_um"] = junction_width
    c.info["junction_height_um"] = junction_height
    c.info["lead_width_um"] = lead_width
    c.info["lead_length_um"] = lead_length
    c.info["layers"] = {
        "bottom_electrode": bottom_layer,
        "barrier": barrier_layer,
        "top_electrode": top_layer,
        "marker": marker_layer,
    }

    return c
