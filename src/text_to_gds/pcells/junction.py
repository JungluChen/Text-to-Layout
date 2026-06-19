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


@gf.cell
def dc_squid_pair(
    junction_width: float = 0.22,
    junction_height: float = 0.22,
    lead_width: float = 1.0,
    loop_width: float = 14.0,
    loop_height: float = 10.0,
    bottom_layer: Layer = BOTTOM_ELECTRODE,
    barrier_layer: Layer = BARRIER,
    top_layer: Layer = TOP_ELECTRODE,
    marker_layer: Layer = MARKER_LAYER,
) -> gf.Component:
    """Low-inductance two-junction dc-SQUID PCell with explicit loop metadata."""
    for name, value in {
        "junction_width": junction_width,
        "junction_height": junction_height,
        "lead_width": lead_width,
        "loop_width": loop_width,
        "loop_height": loop_height,
    }.items():
        require_positive(name, value)
    require_minimum("junction_width", junction_width, DEFAULT_PROCESS.rules.min_junction_width_um)
    require_minimum("junction_height", junction_height, DEFAULT_PROCESS.rules.min_junction_height_um)
    require_minimum("lead_width", lead_width, DEFAULT_PROCESS.rules.min_trace_width_um)
    if loop_width <= 2.0 * lead_width:
        raise ValueError("loop_width must exceed 2 * lead_width")
    if loop_height <= 2.0 * lead_width:
        raise ValueError("loop_height must exceed 2 * lead_width")

    c = gf.Component()
    half_w = loop_width / 2.0
    half_h = loop_height / 2.0
    half_trace = lead_width / 2.0
    junction_y = half_h - half_trace
    bottom_y = -half_h + half_trace

    # Superconducting loop rails and side arms. Junction barriers sit in the top rail.
    c.add_polygon(_rectangle(0, bottom_y, loop_width, lead_width), layer=bottom_layer)
    c.add_polygon(_rectangle(-half_w + half_trace, 0, lead_width, loop_height), layer=bottom_layer)
    c.add_polygon(_rectangle(half_w - half_trace, 0, lead_width, loop_height), layer=bottom_layer)
    c.add_polygon(_rectangle(0, junction_y, loop_width, lead_width), layer=top_layer)
    c.add_polygon(_rectangle(-half_w / 2.0, junction_y, junction_width, junction_height), layer=barrier_layer)
    c.add_polygon(_rectangle(half_w / 2.0, junction_y, junction_width, junction_height), layer=barrier_layer)
    c.add_polygon(_rectangle(-half_w - 3.0, bottom_y, 6.0, lead_width), layer=bottom_layer)
    c.add_polygon(_rectangle(half_w + 3.0, junction_y, 6.0, lead_width), layer=top_layer)

    c.add_port(
        name="bottom",
        center=(-half_w - 6.0, bottom_y),
        width=lead_width,
        orientation=180,
        layer=bottom_layer,
        port_type="electrical",
    )
    c.add_port(
        name="top",
        center=(half_w + 6.0, junction_y),
        width=lead_width,
        orientation=0,
        layer=top_layer,
        port_type="electrical",
    )
    c.add_port(
        name="flux_reference",
        center=(0.0, 0.0),
        width=min(loop_width, loop_height),
        orientation=90,
        layer=marker_layer,
        port_type="optical",
    )

    single_area_um2 = junction_width * junction_height
    total_area_um2 = 2.0 * single_area_um2
    loop_area_um2 = max((loop_width - lead_width) * (loop_height - lead_width), 0.0)
    c.add_label(
        f"SQUID 2x JJ area {single_area_um2:.6g} um2 loop {loop_area_um2:.6g} um2",
        position=(0, 0),
        layer=marker_layer,
    )

    c.info["device_type"] = "dc_squid_pair"
    c.info["squid_enabled"] = True
    c.info["squid_model"] = "low_loop_inductance_dc_squid"
    c.info["squid_junction_count"] = 2
    c.info["single_junction_area_um2"] = single_area_um2
    c.info["junction_area_um2"] = total_area_um2
    c.info["junction_width_um"] = junction_width
    c.info["junction_height_um"] = junction_height
    c.info["lead_width_um"] = lead_width
    c.info["squid_loop_width_um"] = loop_width
    c.info["squid_loop_height_um"] = loop_height
    c.info["squid_loop_area_um2"] = loop_area_um2
    c.info["layers"] = {
        "bottom_electrode": bottom_layer,
        "junction_barrier": barrier_layer,
        "top_electrode": top_layer,
        "marker": marker_layer,
    }
    return c
