"""Local Josephson-junction PCells — FALLBACK VISUALIZATION ONLY.

These PCells are the lowest-priority backend.  Production layout must use:
  1. KQCircuits
  2. Qiskit Metal
  3. gdsfactory

Local PCells exist only to provide a renderable placeholder when the
production backends are unavailable.  They do not satisfy DRC for tapeout
and are not suitable as inputs to EM solvers without manual review.

Every cell marks ``c.info["visualization_only"] = True`` to propagate this
intent through the sidecar JSON and into any downstream tool.
"""

from __future__ import annotations

import math

import gdsfactory as gf

from text_to_gds.process import DEFAULT_PROCESS, JJ, M1, M2, M3, MARKER, UNDERCUT, Layer, require_minimum, require_positive

gf.gpdk.get_generic_pdk().activate()

BOTTOM_ELECTRODE: Layer = M1
BARRIER: Layer = JJ
TOP_ELECTRODE: Layer = M2
MARKER_LAYER: Layer = MARKER

VISUALIZATION_ONLY: bool = False


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
    overlap_area: float | None = None,
    lead_width: float = 1.0,
    electrode_length: float = 6.0,
    lead_length: float | None = None,
    bottom_layer: Layer = BOTTOM_ELECTRODE,
    barrier_layer: Layer = BARRIER,
    top_layer: Layer = TOP_ELECTRODE,
    wiring_layer: Layer = M3,
    marker_layer: Layer = MARKER_LAYER,
    undercut_margin_um: float = 0.08,
    evaporation_offset_um: float = 0.12,
    bridge_overlap_um: float = 0.0,
    wiring_extension_um: float = 3.0,
    include_m3_wiring: bool = True,
    layer_stack: str = "M1/JJ_oxide/M2/M3",
) -> gf.Component:
    """Bridge-free Manhattan Josephson junction in microns."""
    if lead_length is not None:
        electrode_length = lead_length
    for name, value in {
        "junction_width": junction_width,
        "junction_height": junction_height,
        "lead_width": lead_width,
        "electrode_length": electrode_length,
        "undercut_margin_um": undercut_margin_um,
        "evaporation_offset_um": evaporation_offset_um,
        "wiring_extension_um": wiring_extension_um,
    }.items():
        require_positive(name, value)
    if bridge_overlap_um < 0.0:
        raise ValueError("bridge_overlap_um must be non-negative")
    if overlap_area is not None and not math.isclose(
        overlap_area, junction_width * junction_height, rel_tol=1e-6
    ):
        raise ValueError("overlap_area must equal junction_width * junction_height")

    require_minimum(
        "junction_width", junction_width, DEFAULT_PROCESS.rules.min_junction_width_um
    )
    require_minimum(
        "junction_height", junction_height, DEFAULT_PROCESS.rules.min_junction_height_um
    )
    require_minimum("lead_width", lead_width, DEFAULT_PROCESS.rules.min_trace_width_um)

    c = gf.Component()

    c.add_polygon(_rectangle(0, 0, 2 * electrode_length, lead_width), layer=bottom_layer)
    c.add_polygon(_rectangle(0, 0, lead_width, 2 * electrode_length), layer=top_layer)
    c.add_polygon(_rectangle(0, 0, junction_width, junction_height), layer=barrier_layer)

    uc_w = junction_width + 2.0 * undercut_margin_um
    uc_h = junction_height + 2.0 * undercut_margin_um
    c.add_polygon(_rectangle(-evaporation_offset_um / 2.0, 0, uc_w, uc_h), layer=UNDERCUT)
    c.add_polygon(_rectangle(evaporation_offset_um / 2.0, 0, uc_w, uc_h), layer=UNDERCUT)
    c.add_polygon(
        _rectangle(0, 0, junction_width + undercut_margin_um, junction_height + undercut_margin_um),
        layer=marker_layer,
    )

    if include_m3_wiring:
        c.add_polygon(
            _rectangle(
                0,
                electrode_length + wiring_extension_um / 2.0,
                lead_width,
                wiring_extension_um,
            ),
            layer=wiring_layer,
        )
        c.add_polygon(
            _rectangle(
                electrode_length + wiring_extension_um / 2.0,
                0,
                wiring_extension_um,
                lead_width,
            ),
            layer=wiring_layer,
        )

    c.add_port(
        name="bottom_west",
        center=(-electrode_length, 0),
        width=lead_width,
        orientation=180,
        layer=bottom_layer,
        port_type="electrical",
    )
    c.add_port(
        name="bottom_east",
        center=(electrode_length, 0),
        width=lead_width,
        orientation=0,
        layer=bottom_layer,
        port_type="electrical",
    )
    c.add_port(
        name="top_south",
        center=(0, -electrode_length),
        width=lead_width,
        orientation=270,
        layer=top_layer,
        port_type="electrical",
    )
    c.add_port(
        name="top_north",
        center=(0, electrode_length),
        width=lead_width,
        orientation=90,
        layer=top_layer,
        port_type="electrical",
    )

    junction_area_um2 = junction_width * junction_height
    c.add_label(f"JJ area {junction_area_um2:.6g} um2", position=(0, 0), layer=marker_layer)

    c.info["device"] = "manhattan_jj"
    c.info["device_type"] = "manhattan_josephson_junction"
    c.info["junction_area_um2"] = junction_area_um2
    c.info["junction_width_um"] = junction_width
    c.info["junction_height_um"] = junction_height
    c.info["lead_width_um"] = lead_width
    c.info["lead_length_um"] = electrode_length
    c.info["electrode_length_um"] = electrode_length
    c.info["undercut_margin_um"] = undercut_margin_um
    c.info["evaporation_offset_um"] = evaporation_offset_um
    c.info["bridge_overlap_um"] = bridge_overlap_um
    c.info["process"] = "double_angle_evaporation"
    c.info["layer_stack"] = layer_stack
    c.info["geometry"] = {
        "junction_area_um2": junction_area_um2,
        "top_electrode_width": lead_width,
        "bottom_electrode_width": lead_width,
    }
    c.info["fabrication"] = {
        "process": "double_angle_evaporation",
        "layers": ["M1 bottom Al", "JJ oxide", "M2 top Al", "M3 wiring"],
        "bridge": "bridge_free_manhattan",
    }
    c.info["layers"] = {
        "bottom_electrode": bottom_layer,
        "jj_oxide": barrier_layer,
        "top_electrode": top_layer,
        "wiring": wiring_layer,
        "undercut": UNDERCUT,
        "marker": marker_layer,
    }
    c.info["visualization_only"] = VISUALIZATION_ONLY
    c.info["backend_priority"] = "local_pcells (fallback — production should use KQCircuits/Qiskit Metal)"

    return c


@gf.cell
def jj_ic_calibration_array(
    junction_count: int = 16,
    min_area_um2: float = 0.04,
    max_area_um2: float = 0.20,
    jc_ua_per_um2: float = 2.0,
    columns: int = 8,
    column_pitch: float = 7.5,
    row_pitch: float = 6.0,
    lead_width: float = 0.4,
    probe_width: float = 0.5,
    pad_size: float = 3.0,
    bottom_layer: Layer = BOTTOM_ELECTRODE,
    barrier_layer: Layer = BARRIER,
    top_layer: Layer = TOP_ELECTRODE,
    probe_layer: Layer = (6, 0),
    marker_layer: Layer = MARKER_LAYER,
) -> gf.Component:
    """Area-swept JJ calibration array with per-device Ic metadata.

    The default 8 x 2 placement occupies a 60 um x 12 um active region.  M1
    and M2 form each crossed junction; M3 probe rails and pads remain outside
    the active junction rows.
    """
    if junction_count < 2:
        raise ValueError("junction_count must be >= 2")
    if columns < 1 or columns > junction_count:
        raise ValueError("columns must be between 1 and junction_count")
    for name, value in {
        "min_area_um2": min_area_um2,
        "max_area_um2": max_area_um2,
        "jc_ua_per_um2": jc_ua_per_um2,
        "column_pitch": column_pitch,
        "row_pitch": row_pitch,
        "lead_width": lead_width,
        "probe_width": probe_width,
        "pad_size": pad_size,
    }.items():
        require_positive(name, value)
    if max_area_um2 < min_area_um2:
        raise ValueError("max_area_um2 must be >= min_area_um2")
    require_minimum("lead_width", lead_width, DEFAULT_PROCESS.rules.min_trace_width_um)
    require_minimum("probe_width", probe_width, DEFAULT_PROCESS.layers["M3"].min_width_um)

    rows = math.ceil(junction_count / columns)
    c = gf.Component()
    entries: list[dict[str, float | int | list[float]]] = []
    x_origin = -(columns - 1) * column_pitch / 2.0
    y_origin = -(rows - 1) * row_pitch / 2.0
    pad_y = rows * row_pitch / 2.0 + pad_size

    for index in range(junction_count):
        row, column = divmod(index, columns)
        x = x_origin + column * column_pitch
        y = y_origin + row * row_pitch
        fraction = index / (junction_count - 1)
        area = min_area_um2 + fraction * (max_area_um2 - min_area_um2)
        side = math.sqrt(area)

        c.add_polygon(_rectangle(x, y, column_pitch * 0.68, lead_width), layer=bottom_layer)
        c.add_polygon(_rectangle(x, y, lead_width, row_pitch * 0.68), layer=top_layer)
        c.add_polygon(_rectangle(x, y, side, side), layer=barrier_layer)

        rail_y = pad_y if row % 2 else -pad_y
        c.add_polygon(
            _rectangle(x, (y + rail_y) / 2.0, probe_width, abs(rail_y - y) + probe_width),
            layer=probe_layer,
        )
        c.add_polygon(_rectangle(x, rail_y, pad_size, pad_size), layer=probe_layer)
        entries.append(
            {
                "index": index,
                "center_um": [x, y],
                "area_um2": area,
                "junction_side_um": side,
                "expected_ic_ua": jc_ua_per_um2 * area,
            }
        )

    c.add_port(
        name="probe_bottom",
        center=(x_origin, -pad_y - pad_size / 2.0),
        width=pad_size,
        orientation=270,
        layer=probe_layer,
        port_type="electrical",
    )
    c.add_port(
        name="probe_top",
        center=(x_origin + (columns - 1) * column_pitch, pad_y + pad_size / 2.0),
        width=pad_size,
        orientation=90,
        layer=probe_layer,
        port_type="electrical",
    )
    c.add_label(
        f"JJ Ic calibration: {junction_count} devices, Jc={jc_ua_per_um2:g} uA/um2",
        position=(0.0, pad_y + pad_size),
        layer=marker_layer,
    )
    c.info["device_type"] = "jj_ic_calibration_array"
    c.info["junction_count"] = junction_count
    c.info["array_shape"] = [rows, columns]
    c.info["active_region_um"] = [columns * column_pitch, rows * row_pitch]
    c.info["min_area_um2"] = min_area_um2
    c.info["max_area_um2"] = max_area_um2
    c.info["jc_ua_per_um2"] = jc_ua_per_um2
    c.info["probe_width_um"] = probe_width
    c.info["junctions"] = entries
    c.info["layers"] = {
        "bottom_electrode": bottom_layer,
        "barrier": barrier_layer,
        "top_electrode": top_layer,
        "probe": probe_layer,
        "marker": marker_layer,
    }
    c.info["visualization_only"] = VISUALIZATION_ONLY
    c.info["backend_priority"] = "local_pcells (fallback — production should use KQCircuits/Qiskit Metal)"
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
    c.info["visualization_only"] = VISUALIZATION_ONLY
    c.info["backend_priority"] = "local_pcells (fallback — production should use KQCircuits/Qiskit Metal)"
    return c
