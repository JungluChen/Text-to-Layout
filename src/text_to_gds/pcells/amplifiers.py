from __future__ import annotations

import gdsfactory as gf

from text_to_gds.pcells.junction import dc_squid_pair
from text_to_gds.pcells.passives import cpw_straight, flux_bias_line, ground_plane, meander_inductor
from text_to_gds.process import M1, M2, M3, JJ, require_positive


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
        "inductor_segment_length": inductor_segment_length,
        "inductor_trace_width": inductor_trace_width,
        "inductor_pitch": inductor_pitch,
    }.items():
        require_positive(name, value)
    if inductor_turns < 2:
        raise ValueError(f"inductor_turns must be >= 2, got {inductor_turns}")

    c = gf.Component()

    c << ground_plane(width=active_width_um, height=active_height_um, clearance=cpw_gap)
    feedline = c << cpw_straight(
        length=cpw_length,
        trace_width=cpw_trace_width,
        gap=cpw_gap,
        ground_width=18.0,
        signal_layer=M3,
    )
    feedline.move((0.0, 0.0))

    squid = c << dc_squid_pair(
        junction_width=junction_width,
        junction_height=junction_height,
        lead_width=1.0,
        loop_width=14.0,
        loop_height=10.0,
    )
    squid.move((0.0, -28.0))

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

    c.add_port(name="rf_in", port=feedline.ports["west"])
    c.add_port(name="rf_out", port=feedline.ports["east"])
    c.add_port(name="flux_in", port=flux.ports["bias_west"])
    c.add_port(name="flux_out", port=flux.ports["bias_east"])
    c.add_port(name="squid_bottom", port=squid.ports["bottom"])
    c.add_port(name="squid_top", port=squid.ports["top"])

    single_junction_area_um2 = junction_width * junction_height
    junction_area_um2 = 2.0 * single_junction_area_um2
    squid_loop_area_um2 = (14.0 - 1.0) * (10.0 - 1.0)
    estimated_resonator_length_um = 75_000.0 / center_frequency_ghz

    c.info["device_type"] = "lumped_element_jpa_seed"
    c.info["center_frequency_ghz"] = center_frequency_ghz
    c.info["target_bandwidth_mhz"] = target_bandwidth_mhz
    c.info["target_gain_db"] = target_gain_db
    c.info["active_width_um"] = active_width_um
    c.info["active_height_um"] = active_height_um
    c.info["squid_enabled"] = True
    c.info["squid_model"] = "low_loop_inductance_dc_squid"
    c.info["squid_junction_count"] = 2
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
    c.info["inductor_turns"] = inductor_turns
    c.info["inductor_segment_length_um"] = inductor_segment_length
    c.info["inductor_trace_width_um"] = inductor_trace_width
    c.info["inductor_pitch_um"] = inductor_pitch
    c.info["estimated_quarter_wave_length_um"] = estimated_resonator_length_um
    c.info["design_notes"] = [
        "Seed layout for agent iteration; not a signoff LJPA.",
        "Use extracted sidecar parameters to build external harmonic-balance/transient models.",
        "Tune CPW, shunt capacitance, SQUID flux bias, JJ parameters, and coupling after simulation.",
    ]
    c.info["layers"] = {
        "ground": M1,
        "rf_signal": M3,
        "flux_bias": M2,
        "inductor": M2,
        "junction_bottom": M1,
        "junction_barrier": JJ,
        "junction_top": M2,
    }
    return c
