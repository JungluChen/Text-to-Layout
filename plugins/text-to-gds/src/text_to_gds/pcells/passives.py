from __future__ import annotations

import math

import gdsfactory as gf

from text_to_gds.process import (
    DEFAULT_PROCESS,
    M1,
    M2,
    M3,
    MARKER,
    VIA12,
    VIA23,
    Layer,
    require_minimum,
    require_positive,
)


def _rotate_point(x: float, y: float, angle_deg: float) -> tuple[float, float]:
    theta = math.radians(angle_deg)
    return (
        x * math.cos(theta) - y * math.sin(theta),
        x * math.sin(theta) + y * math.cos(theta),
    )


def _rotated_rectangle(
    cx: float,
    cy: float,
    width: float,
    height: float,
    angle_deg: float,
) -> list[tuple[float, float]]:
    half_w = width / 2.0
    half_h = height / 2.0
    points = [
        (cx - half_w, cy - half_h),
        (cx + half_w, cy - half_h),
        (cx + half_w, cy + half_h),
        (cx - half_w, cy + half_h),
    ]
    return [_rotate_point(x, y, angle_deg) for x, y in points]


def _port_orientation(base_orientation: float, angle_deg: float) -> float:
    return (base_orientation + angle_deg) % 360.0


def _layer_height_nm(layer: Layer) -> float:
    for spec in DEFAULT_PROCESS.layers.values():
        if spec.layer == layer:
            return spec.thickness_nm
    return 0.0


@gf.cell
def cpw_straight(
    length: float = 100.0,
    trace_width: float = 10.0,
    gap: float = 6.0,
    ground_width: float = 25.0,
    angle_deg: float = 0.0,
    signal_layer: Layer = M3,
    ground_layer: Layer = M1,
) -> gf.Component:
    """Straight coplanar waveguide section with explicit gap and rotation."""
    for name, value in {
        "length": length,
        "trace_width": trace_width,
        "gap": gap,
        "ground_width": ground_width,
    }.items():
        require_positive(name, value)
    require_minimum("trace_width", trace_width, DEFAULT_PROCESS.rules.min_trace_width_um)
    require_minimum("gap", gap, DEFAULT_PROCESS.rules.min_cpw_gap_um)

    c = gf.Component()
    c.add_polygon(_rotated_rectangle(0, 0, length, trace_width, angle_deg), layer=signal_layer)

    ground_center_y = gap + trace_width / 2.0 + ground_width / 2.0
    c.add_polygon(
        _rotated_rectangle(0, ground_center_y, length, ground_width, angle_deg),
        layer=ground_layer,
    )
    c.add_polygon(
        _rotated_rectangle(0, -ground_center_y, length, ground_width, angle_deg),
        layer=ground_layer,
    )

    west = _rotate_point(-length / 2.0, 0.0, angle_deg)
    east = _rotate_point(length / 2.0, 0.0, angle_deg)
    c.add_port(
        name="west",
        center=west,
        width=trace_width,
        orientation=_port_orientation(180.0, angle_deg),
        layer=signal_layer,
        port_type="electrical",
    )
    c.add_port(
        name="east",
        center=east,
        width=trace_width,
        orientation=_port_orientation(0.0, angle_deg),
        layer=signal_layer,
        port_type="electrical",
    )

    c.info["device_type"] = "cpw_straight"
    c.info["length_um"] = length
    c.info["trace_width_um"] = trace_width
    c.info["gap_um"] = gap
    c.info["ground_width_um"] = ground_width
    c.info["angle_deg"] = angle_deg
    c.info["signal_layer_height_nm"] = _layer_height_nm(signal_layer)
    c.info["layers"] = {"signal": signal_layer, "ground": ground_layer}
    return c


@gf.cell
def meander_inductor(
    num_turns: int = 6,
    segment_length: float = 20.0,
    trace_width: float = 1.0,
    pitch: float = 3.0,
    angle_deg: float = 0.0,
    layer: Layer = M2,
) -> gf.Component:
    """Manhattan meander inductor placeholder with length metadata."""
    if num_turns < 2:
        raise ValueError(f"num_turns must be >= 2, got {num_turns}")
    for name, value in {
        "segment_length": segment_length,
        "trace_width": trace_width,
        "pitch": pitch,
    }.items():
        require_positive(name, value)
    require_minimum("trace_width", trace_width, DEFAULT_PROCESS.rules.min_trace_width_um)
    require_minimum(
        "pitch",
        pitch,
        trace_width + DEFAULT_PROCESS.rules.min_trace_spacing_um,
    )

    c = gf.Component()
    y0 = -pitch * (num_turns - 1) / 2.0

    for row in range(num_turns):
        y = y0 + row * pitch
        c.add_polygon(
            _rotated_rectangle(0.0, y, segment_length, trace_width, angle_deg),
            layer=layer,
        )
        if row < num_turns - 1:
            connector_x = segment_length / 2.0 if row % 2 == 0 else -segment_length / 2.0
            c.add_polygon(
                _rotated_rectangle(connector_x, y + pitch / 2.0, trace_width, pitch, angle_deg),
                layer=layer,
            )

    start = _rotate_point(-segment_length / 2.0, y0, angle_deg)
    end_x = segment_length / 2.0 if (num_turns - 1) % 2 == 0 else -segment_length / 2.0
    end = _rotate_point(end_x, y0 + (num_turns - 1) * pitch, angle_deg)
    end_orientation = 0.0 if (num_turns - 1) % 2 == 0 else 180.0
    c.add_port(
        name="input",
        center=start,
        width=trace_width,
        orientation=_port_orientation(180.0, angle_deg),
        layer=layer,
        port_type="electrical",
    )
    c.add_port(
        name="output",
        center=end,
        width=trace_width,
        orientation=_port_orientation(end_orientation, angle_deg),
        layer=layer,
        port_type="electrical",
    )

    total_length = num_turns * segment_length + (num_turns - 1) * pitch
    squares = total_length / trace_width
    kinetic_l_ph = squares * DEFAULT_PROCESS.materials["Nb"].kinetic_inductance_ph_per_square

    c.info["device_type"] = "meander_inductor"
    c.info["num_turns"] = num_turns
    c.info["segment_length_um"] = segment_length
    c.info["trace_width_um"] = trace_width
    c.info["pitch_um"] = pitch
    c.info["angle_deg"] = angle_deg
    c.info["electrical_length_um"] = total_length
    c.info["estimated_kinetic_inductance_ph"] = kinetic_l_ph
    c.info["layer_height_nm"] = _layer_height_nm(layer)
    c.info["layers"] = {"trace": layer}
    return c


@gf.cell
def flux_bias_line(
    length: float = 60.0,
    width: float = 1.5,
    coupling_length: float = 12.0,
    coupling_gap: float = 2.0,
    angle_deg: float = 0.0,
    layer: Layer = M2,
    marker_layer: Layer = MARKER,
) -> gf.Component:
    """Straight flux-bias line with a marked coupling window near the device."""
    for name, value in {
        "length": length,
        "width": width,
        "coupling_length": coupling_length,
        "coupling_gap": coupling_gap,
    }.items():
        require_positive(name, value)
    require_minimum("width", width, DEFAULT_PROCESS.rules.min_trace_width_um)
    require_minimum("coupling_gap", coupling_gap, DEFAULT_PROCESS.rules.min_trace_spacing_um)
    if coupling_length > length:
        raise ValueError("coupling_length must be <= length")

    c = gf.Component()
    bias_y = coupling_gap + width
    c.add_polygon(_rotated_rectangle(0.0, bias_y, length, width, angle_deg), layer=layer)
    c.add_polygon(
        _rotated_rectangle(0.0, 0.0, coupling_length, width / 3.0, angle_deg),
        layer=marker_layer,
    )

    west = _rotate_point(-length / 2.0, bias_y, angle_deg)
    east = _rotate_point(length / 2.0, bias_y, angle_deg)
    c.add_port(
        name="bias_west",
        center=west,
        width=width,
        orientation=_port_orientation(180.0, angle_deg),
        layer=layer,
        port_type="electrical",
    )
    c.add_port(
        name="bias_east",
        center=east,
        width=width,
        orientation=_port_orientation(0.0, angle_deg),
        layer=layer,
        port_type="electrical",
    )

    c.info["device_type"] = "flux_bias_line"
    c.info["length_um"] = length
    c.info["width_um"] = width
    c.info["coupling_length_um"] = coupling_length
    c.info["coupling_gap_um"] = coupling_gap
    c.info["angle_deg"] = angle_deg
    c.info["layer_height_nm"] = _layer_height_nm(layer)
    c.info["layers"] = {"bias": layer, "coupling_marker": marker_layer}
    return c


@gf.cell
def via_stack(
    via_size: float = 0.5,
    enclosure: float = 0.25,
    bottom_layer: Layer = M1,
    via_layer: Layer = VIA12,
    top_layer: Layer = M2,
) -> gf.Component:
    """Single square via with landing pads on adjacent metal layers."""
    require_positive("via_size", via_size)
    require_positive("enclosure", enclosure)
    require_minimum("via_size", via_size, DEFAULT_PROCESS.rules.via_min_size_um)
    require_minimum("enclosure", enclosure, DEFAULT_PROCESS.rules.via_enclosure_um)

    pad_size = via_size + 2.0 * enclosure
    c = gf.Component()
    c.add_polygon(_rotated_rectangle(0.0, 0.0, pad_size, pad_size, 0.0), layer=bottom_layer)
    c.add_polygon(_rotated_rectangle(0.0, 0.0, via_size, via_size, 0.0), layer=via_layer)
    c.add_polygon(_rotated_rectangle(0.0, 0.0, pad_size, pad_size, 0.0), layer=top_layer)
    c.add_port(
        name="bottom",
        center=(0.0, 0.0),
        width=pad_size,
        orientation=180.0,
        layer=bottom_layer,
        port_type="electrical",
    )
    c.add_port(
        name="top",
        center=(0.0, 0.0),
        width=pad_size,
        orientation=0.0,
        layer=top_layer,
        port_type="electrical",
    )

    c.info["device_type"] = "via_stack"
    c.info["via_size_um"] = via_size
    c.info["enclosure_um"] = enclosure
    c.info["pad_size_um"] = pad_size
    c.info["layers"] = {"bottom": bottom_layer, "via": via_layer, "top": top_layer}
    return c


@gf.cell
def ground_plane(
    width: float = 250.0,
    height: float = 250.0,
    clearance: float = 10.0,
    layer: Layer = M1,
) -> gf.Component:
    """Ground-plane tile with clearance metadata for future boolean cutouts."""
    for name, value in {"width": width, "height": height, "clearance": clearance}.items():
        require_positive(name, value)
    require_minimum("clearance", clearance, DEFAULT_PROCESS.rules.min_trace_spacing_um)

    c = gf.Component()
    c.add_polygon(_rotated_rectangle(0.0, 0.0, width, height, 0.0), layer=layer)
    c.add_label(f"GND clearance {clearance:g} um", position=(0.0, 0.0), layer=MARKER)

    c.info["device_type"] = "ground_plane"
    c.info["width_um"] = width
    c.info["height_um"] = height
    c.info["clearance_um"] = clearance
    c.info["layer_height_nm"] = _layer_height_nm(layer)
    c.info["layers"] = {"ground": layer, "marker": MARKER}
    return c


@gf.cell
def via_chain_monitor(
    stage_count: int = 100,
    pitch: float = 1.0,
    row_offset: float = 5.0,
    metal_width: float = 0.4,
    via_size: float = 0.4,
    enclosure: float = 0.2,
    input_pad_size: float = 5.0,
    output_pad_size: float = 5.0,
    estimated_via_resistance_ohm: float = 0.25,
) -> gf.Component:
    """100-stage Manhattan via-chain process monitor with explicit I/O ports."""
    if stage_count < 2:
        raise ValueError(f"stage_count must be >= 2, got {stage_count}")
    for name, value in {
        "pitch": pitch,
        "row_offset": row_offset,
        "metal_width": metal_width,
        "via_size": via_size,
        "enclosure": enclosure,
        "input_pad_size": input_pad_size,
        "output_pad_size": output_pad_size,
        "estimated_via_resistance_ohm": estimated_via_resistance_ohm,
    }.items():
        require_positive(name, value)
    require_minimum("metal_width", metal_width, DEFAULT_PROCESS.rules.min_trace_width_um)
    require_minimum("via_size", via_size, DEFAULT_PROCESS.rules.via_min_size_um)
    require_minimum("enclosure", enclosure, DEFAULT_PROCESS.rules.via_enclosure_um)

    pad_size = via_size + 2.0 * enclosure
    c = gf.Component()

    layer_sequence = [M1, M2, M3, M2]
    via_layers = {
        frozenset((M1, M2)): VIA12,
        frozenset((M2, M3)): VIA23,
    }

    def point(index: int) -> tuple[float, float]:
        return index * pitch, row_offset if index % 2 == 0 else -row_offset

    def add_segment(
        start: tuple[float, float],
        end: tuple[float, float],
        layer: Layer,
    ) -> float:
        x1, y1 = start
        x2, y2 = end
        length = 0.0
        if abs(x2 - x1) > 1e-12:
            cx = (x1 + x2) / 2.0
            c.add_polygon(
                _rotated_rectangle(cx, y1, abs(x2 - x1) + metal_width, metal_width, 0.0),
                layer=layer,
            )
            length += abs(x2 - x1)
        if abs(y2 - y1) > 1e-12:
            cy = (y1 + y2) / 2.0
            c.add_polygon(
                _rotated_rectangle(x2, cy, metal_width, abs(y2 - y1) + metal_width, 0.0),
                layer=layer,
            )
            length += abs(y2 - y1)
        return length

    input_center = (-input_pad_size, 0.0)
    output_center = ((stage_count - 1) * pitch + output_pad_size, 0.0)
    c.add_polygon(
        _rotated_rectangle(input_center[0], input_center[1], input_pad_size, input_pad_size, 0.0),
        layer=M1,
    )
    c.add_polygon(
        _rotated_rectangle(output_center[0], output_center[1], output_pad_size, output_pad_size, 0.0),
        layer=layer_sequence[stage_count % len(layer_sequence)],
    )

    metal_length_um = add_segment(input_center, point(0), M1)
    current_layer = M1
    for index in range(stage_count):
        x, y = point(index)
        next_layer = layer_sequence[(index + 1) % len(layer_sequence)]
        via_layer = via_layers[frozenset((current_layer, next_layer))]
        c.add_polygon(_rotated_rectangle(x, y, pad_size, pad_size, 0.0), layer=current_layer)
        c.add_polygon(_rotated_rectangle(x, y, via_size, via_size, 0.0), layer=via_layer)
        c.add_polygon(_rotated_rectangle(x, y, pad_size, pad_size, 0.0), layer=next_layer)
        current_layer = next_layer
        if index < stage_count - 1:
            metal_length_um += add_segment(point(index), point(index + 1), current_layer)

    metal_length_um += add_segment(point(stage_count - 1), output_center, current_layer)

    c.add_port(
        name="input",
        center=input_center,
        width=input_pad_size,
        orientation=180.0,
        layer=M1,
        port_type="electrical",
    )
    c.add_port(
        name="output",
        center=output_center,
        width=output_pad_size,
        orientation=0.0,
        layer=current_layer,
        port_type="electrical",
    )
    c.add_label(f"{stage_count}-stage via-chain monitor", position=(stage_count * pitch / 2, 0.0), layer=MARKER)

    estimated_metal_resistance_ohm = metal_length_um / metal_width * 0.001
    c.info["device_type"] = "via_chain_monitor"
    c.info["stage_count"] = stage_count
    c.info["pitch_um"] = pitch
    c.info["row_offset_um"] = row_offset
    c.info["metal_width_um"] = metal_width
    c.info["via_size_um"] = via_size
    c.info["enclosure_um"] = enclosure
    c.info["pad_size_um"] = pad_size
    c.info["route_style"] = "manhattan_ladder"
    c.info["metal_length_um"] = metal_length_um
    c.info["estimated_via_resistance_ohm"] = estimated_via_resistance_ohm
    c.info["estimated_metal_resistance_ohm"] = estimated_metal_resistance_ohm
    c.info["estimated_total_resistance_ohm"] = (
        stage_count * estimated_via_resistance_ohm + estimated_metal_resistance_ohm
    )
    c.info["open_chain_detected"] = False
    c.info["layers"] = {
        "m1": M1,
        "m2": M2,
        "m3": M3,
        "via12": VIA12,
        "via23": VIA23,
        "marker": MARKER,
    }
    return c
