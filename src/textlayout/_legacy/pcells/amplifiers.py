from __future__ import annotations

import gdsfactory as gf

from textlayout._legacy.pcells.junction import dc_squid_pair
from textlayout._legacy.pcells.passives import cpw_straight, flux_bias_line, meander_inductor
from textlayout._legacy.process import M1, M2, M3, JJ, require_positive


@gf.cell
def lumped_element_jpa_seed(
    center_frequency_ghz: float = 5.0,
    target_bandwidth_mhz: float = 500.0,
    target_gain_db: float = 20.0,
    active_width_um: float = 260.0,
    active_height_um: float = 180.0,
    junction_width: float = 0.22,
    junction_height: float = 0.22,
    cpw_length: float = 210.0,
    cpw_trace_width: float = 10.0,
    cpw_gap: float = 6.0,
    flux_line_length: float = 120.0,
    flux_line_width: float = 1.5,
    squid_count: int = 4,
    squid_pitch_um: float = 22.0,
    shunt_capacitor_width_um: float = 70.0,
    shunt_capacitor_gap_um: float = 3.0,
    coupling_capacitor_length_um: float = 42.0,
    coupling_capacitor_gap_um: float = 3.0,
    inductor_turns: int = 6,
    inductor_segment_length: float = 24.0,
    inductor_trace_width: float = 1.0,
    inductor_pitch: float = 3.0,
) -> gf.Component:
    """First-pass lumped-element JPA/LJPA seed layout assembled from reviewed PCells."""
    for name, value in {
        "center_frequency_ghz": center_frequency_ghz,
        "target_bandwidth_mhz": target_bandwidth_mhz,
        "target_gain_db": target_gain_db,
        "active_width_um": active_width_um,
        "active_height_um": active_height_um,
        "junction_width": junction_width,
        "junction_height": junction_height,
        "cpw_length": cpw_length,
        "cpw_trace_width": cpw_trace_width,
        "cpw_gap": cpw_gap,
        "flux_line_length": flux_line_length,
        "flux_line_width": flux_line_width,
        "squid_pitch_um": squid_pitch_um,
        "shunt_capacitor_width_um": shunt_capacitor_width_um,
        "shunt_capacitor_gap_um": shunt_capacitor_gap_um,
        "coupling_capacitor_length_um": coupling_capacitor_length_um,
        "coupling_capacitor_gap_um": coupling_capacitor_gap_um,
        "inductor_segment_length": inductor_segment_length,
        "inductor_trace_width": inductor_trace_width,
        "inductor_pitch": inductor_pitch,
    }.items():
        require_positive(name, value)
    if squid_count < 1:
        raise ValueError("squid_count must be >= 1")
    if inductor_turns < 2:
        raise ValueError(f"inductor_turns must be >= 2, got {inductor_turns}")

    c = gf.Component()

    feedline = c << cpw_straight(
        length=cpw_length,
        trace_width=cpw_trace_width,
        gap=cpw_gap,
        ground_width=8.0,
        launch_pad_length=50.0,
        launch_pad_width=cpw_trace_width,
        signal_layer=M3,
    )
    feedline.move((0.0, 0.0))

    squid_refs = []
    squid_x0 = -(squid_count - 1) * squid_pitch_um / 2.0
    for index in range(squid_count):
        squid = c << dc_squid_pair(
            junction_width=junction_width,
            junction_height=junction_height,
            lead_width=1.0,
            loop_width=14.0,
            loop_height=10.0,
        )
        squid.move((squid_x0 + index * squid_pitch_um, -28.0))
        squid_refs.append(squid)
    c.add_polygon(
        [
            (squid_x0 - 10.0, -28.5),
            (squid_x0 + (squid_count - 1) * squid_pitch_um + 10.0, -28.5),
            (squid_x0 + (squid_count - 1) * squid_pitch_um + 10.0, -27.5),
            (squid_x0 - 10.0, -27.5),
        ],
        layer=M2,
    )

    inductor = c << meander_inductor(
        num_turns=inductor_turns,
        segment_length=inductor_segment_length,
        trace_width=inductor_trace_width,
        pitch=inductor_pitch,
        layer=M2,
    )
    inductor.move((0.0, -54.0))

    flux = c << flux_bias_line(
        length=flux_line_length,
        width=flux_line_width,
        coupling_length=24.0,
        coupling_gap=3.0,
        layer=M2,
    )
    flux.move((0.0, 24.0))

    cap_y = -82.0
    idc_fingers = 8
    idc_finger_width_um = max(2.0, shunt_capacitor_gap_um)
    idc_pitch_um = idc_finger_width_um + shunt_capacitor_gap_um
    idc_span_um = (idc_fingers - 1) * idc_pitch_um + idc_finger_width_um
    bus_height_um = 4.0
    finger_length_um = shunt_capacitor_width_um
    x0 = -idc_span_um / 2.0 + idc_finger_width_um / 2.0
    top_bus_y = cap_y + finger_length_um / 2.0 + bus_height_um / 2.0
    bottom_bus_y = cap_y - finger_length_um / 2.0 - bus_height_um / 2.0
    c.add_polygon(
        [
            (-idc_span_um / 2.0, top_bus_y - bus_height_um / 2.0),
            (idc_span_um / 2.0, top_bus_y - bus_height_um / 2.0),
            (idc_span_um / 2.0, top_bus_y + bus_height_um / 2.0),
            (-idc_span_um / 2.0, top_bus_y + bus_height_um / 2.0),
        ],
        layer=M2,
    )
    c.add_polygon(
        [
            (-idc_span_um / 2.0, bottom_bus_y - bus_height_um / 2.0),
            (idc_span_um / 2.0, bottom_bus_y - bus_height_um / 2.0),
            (idc_span_um / 2.0, bottom_bus_y + bus_height_um / 2.0),
            (-idc_span_um / 2.0, bottom_bus_y + bus_height_um / 2.0),
        ],
        layer=M1,
    )
    for finger in range(idc_fingers):
        x = x0 + finger * idc_pitch_um
        layer = M2 if finger % 2 == 0 else M1
        y_anchor = top_bus_y - bus_height_um / 2.0 if layer == M2 else bottom_bus_y + bus_height_um / 2.0
        y_end = cap_y - finger_length_um / 2.0 if layer == M2 else cap_y + finger_length_um / 2.0
        c.add_polygon(
            [
                (x - idc_finger_width_um / 2.0, min(y_anchor, y_end)),
                (x + idc_finger_width_um / 2.0, min(y_anchor, y_end)),
                (x + idc_finger_width_um / 2.0, max(y_anchor, y_end)),
                (x - idc_finger_width_um / 2.0, max(y_anchor, y_end)),
            ],
            layer=layer,
        )
    for sign in (-1.0, 1.0):
        x = sign * (cpw_length / 2.0 - coupling_capacitor_length_um / 2.0)
        c.add_polygon(
            [
                (x - coupling_capacitor_length_um / 2.0, coupling_capacitor_gap_um),
                (x + coupling_capacitor_length_um / 2.0, coupling_capacitor_gap_um),
                (x + coupling_capacitor_length_um / 2.0, coupling_capacitor_gap_um + 2.0),
                (x - coupling_capacitor_length_um / 2.0, coupling_capacitor_gap_um + 2.0),
            ],
            layer=M2,
        )

    c.add_port(name="rf_in", port=feedline.ports["west"])
    c.add_port(name="rf_out", port=feedline.ports["east"])
    c.add_port(name="flux_in", port=flux.ports["bias_west"])
    c.add_port(name="flux_out", port=flux.ports["bias_east"])
    c.add_port(name="squid_bottom", port=squid_refs[0].ports["bottom"])
    c.add_port(name="squid_top", port=squid_refs[-1].ports["top"])

    single_junction_area_um2 = junction_width * junction_height
    junction_area_um2 = 2.0 * squid_count * single_junction_area_um2
    squid_loop_area_um2 = (14.0 - 1.0) * (10.0 - 1.0)
    estimated_resonator_length_um = 75_000.0 / center_frequency_ghz
    shunt_capacitance_ff = (
        8.8541878128e-12
        * 6.2
        * ((idc_fingers - 1) * finger_length_um * idc_finger_width_um * 1e-12)
        / (shunt_capacitor_gap_um * 1e-6)
        * 1e15
    )
    coupling_capacitance_ff = (
        8.8541878128e-12
        * 6.2
        * (coupling_capacitor_length_um * 2.0 * 1e-12)
        / (coupling_capacitor_gap_um * 1e-6)
        * 1e15
    )

    c.info["device_type"] = "lumped_element_jpa_seed"
    c.info["center_frequency_ghz"] = center_frequency_ghz
    c.info["target_bandwidth_mhz"] = target_bandwidth_mhz
    c.info["target_gain_db"] = target_gain_db
    c.info["jpa_gain_status"] = "SKIPPED"
    c.info["jpa_gain_skip_reason"] = "nonlinear Josephson model and pump simulation were not executed by layout generation"
    c.info["active_width_um"] = active_width_um
    c.info["active_height_um"] = active_height_um
    c.info["squid_enabled"] = True
    c.info["squid_model"] = "low_loop_inductance_dc_squid"
    c.info["squid_count"] = squid_count
    c.info["squid_pitch_um"] = squid_pitch_um
    c.info["squid_junction_count"] = 2 * squid_count
    c.info["single_junction_area_um2"] = single_junction_area_um2
    c.info["junction_area_um2"] = junction_area_um2
    c.info["junction_width_um"] = junction_width
    c.info["junction_height_um"] = junction_height
    c.info["squid_loop_area_um2"] = squid_loop_area_um2
    c.info["squid_loop_width_um"] = 14.0
    c.info["squid_loop_height_um"] = 10.0
    c.info["cpw_length_um"] = cpw_length
    c.info["cpw_trace_width_um"] = cpw_trace_width
    c.info["cpw_gap_um"] = cpw_gap
    c.info["flux_line_length_um"] = flux_line_length
    c.info["flux_line_width_um"] = flux_line_width
    c.info["shunt_capacitance_ff"] = shunt_capacitance_ff
    c.info["coupling_capacitance_ff"] = coupling_capacitance_ff
    c.info["idc_finger_count"] = idc_fingers
    c.info["idc_finger_length_um"] = finger_length_um
    c.info["idc_finger_width_um"] = idc_finger_width_um
    c.info["idc_gap_um"] = shunt_capacitor_gap_um
    c.info["shunt_capacitor_width_um"] = shunt_capacitor_width_um
    c.info["shunt_capacitor_gap_um"] = shunt_capacitor_gap_um
    c.info["coupling_capacitor_length_um"] = coupling_capacitor_length_um
    c.info["coupling_capacitor_gap_um"] = coupling_capacitor_gap_um
    c.info["inductor_turns"] = inductor_turns
    c.info["inductor_segment_length_um"] = inductor_segment_length
    c.info["inductor_trace_width_um"] = inductor_trace_width
    c.info["inductor_pitch_um"] = inductor_pitch
    c.info["estimated_quarter_wave_length_um"] = estimated_resonator_length_um
    c.info["equivalent_circuit"] = {
        "C": {"value": shunt_capacitance_ff, "unit": "fF", "role": "shunt_capacitor"},
        "Lj(phi)": {
            "unit": "H",
            "role": "SQUID_array_flux_tunable_inductance",
            "junction_count": 2 * squid_count,
        },
        "Cc": {"value": coupling_capacitance_ff, "unit": "fF", "role": "input_output_coupling"},
        "Z0": {"value": 50.0, "unit": "ohm", "role": "input_output_CPW"},
    }
    c.info["lineage"] = {
        "C": {
            "value": shunt_capacitance_ff,
            "unit": "fF",
            "method_label": "analytical",
            "source": "GDS",
            "formula": "C = eps0*eps_eff*A/gap",
            "confidence": 0.7,
        },
        "Cc": {
            "value": coupling_capacitance_ff,
            "unit": "fF",
            "method_label": "analytical",
            "source": "GDS",
            "formula": "Cc = eps0*eps_eff*A/gap",
            "confidence": 0.7,
        },
        "Z0": {
            "value": 50.0,
            "unit": "ohm",
            "method_label": "analytical",
            "source": "GDS",
            "formula": "nominal CPW port impedance; verify with EM solver for signoff",
            "confidence": 0.6,
        },
    }
    c.info["design_notes"] = [
        "Fabrication-semantic JPA seed; signoff still requires foundry DRC and executed solvers.",
        "Use extracted polygon parameters to build external harmonic-balance/transient models.",
        "Tune CPW, IDC shunt capacitance, SQUID flux bias, JJ parameters, and coupling after simulation.",
    ]
    c.info["required_jpa_features"] = {
        "squid_loop": True,
        "josephson_junction_count": 2 * squid_count,
        "idc_shunt_capacitor": True,
        "coupling_capacitor": True,
        "rf_port": True,
        "ground": True,
    }
    c.info["layers"] = {
        "ground": M1,
        "rf_signal": M3,
        "flux_bias": M2,
        "inductor": M2,
        "idc_shunt_capacitor": M2,
        "coupling_capacitor": M2,
        "junction_bottom": M1,
        "junction_barrier": JJ,
        "junction_top": M2,
    }
    return c
