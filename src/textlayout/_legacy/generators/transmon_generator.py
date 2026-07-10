"""Professional Transmon generator: Pocket, Xmon, and Concentric layouts.

Implements modern IBM/Yale style transmon geometries with realistic features
recognizable by experienced quantum IC designers.
"""

from __future__ import annotations

import math
from typing import Any


def generate_transmon_layout(
    *,
    variant: str = "pocket",
    frequency_ghz: float = 5.0,
    junction_area_um2: float = 0.05,
    ej_ec_ratio: float = 50.0,
    cpw_width_um: float = 10.0,
    cpw_gap_um: float = 6.0,
    readout_frequency_ghz: float = 7.0,
    readout_coupling_capacitance_fF: float = 10.0,
    flux_line_offset_um: float = 5.0,
    chip_width_um: float = 5000.0,
    chip_height_um: float = 5000.0,
    output_path: str | None = None,
) -> dict[str, Any]:
    """Generate a professional transmon layout specification.

    Parameters
    ----------
    variant:
        "pocket", "xmon", or "concentric".
    frequency_ghz:
        Target qubit frequency.
    junction_area_um2:
        Josephson junction overlap area.
    ej_ec_ratio:
        Target Ej/Ec ratio.
    cpw_width_um:
        CPW center trace width for readout resonator.
    cpw_gap_um:
        CPW gap to ground for readout resonator.
    readout_frequency_ghz:
        Target readout resonator frequency.
    readout_coupling_capacitance_fF:
        Coupling capacitance between qubit and readout.
    flux_line_offset_um:
        Offset of flux line from SQUID center.
    chip_width_um:
        Overall chip width.
    chip_height_um:
        Overall chip height.
    output_path:
        Optional path to write the layout spec JSON.
    """
    if variant == "pocket":
        spec = _generate_pocket_transmon(
            frequency_ghz=frequency_ghz,
            junction_area_um2=junction_area_um2,
            ej_ec_ratio=ej_ec_ratio,
            cpw_width_um=cpw_width_um,
            cpw_gap_um=cpw_gap_um,
            readout_frequency_ghz=readout_frequency_ghz,
            readout_coupling_capacitance_fF=readout_coupling_capacitance_fF,
            flux_line_offset_um=flux_line_offset_um,
            chip_width_um=chip_width_um,
            chip_height_um=chip_height_um,
        )
    elif variant == "xmon":
        spec = _generate_xmon(
            frequency_ghz=frequency_ghz,
            junction_area_um2=junction_area_um2,
            ej_ec_ratio=ej_ec_ratio,
            readout_frequency_ghz=readout_frequency_ghz,
            readout_coupling_capacitance_fF=readout_coupling_capacitance_fF,
            chip_width_um=chip_width_um,
            chip_height_um=chip_height_um,
        )
    elif variant == "concentric":
        spec = _generate_concentric_transmon(
            frequency_ghz=frequency_ghz,
            junction_area_um2=junction_area_um2,
            ej_ec_ratio=ej_ec_ratio,
            readout_frequency_ghz=readout_frequency_ghz,
            readout_coupling_capacitance_fF=readout_coupling_capacitance_fF,
            chip_width_um=chip_width_um,
            chip_height_um=chip_height_um,
        )
    else:
        raise ValueError(f"Unknown transmon variant: {variant!r}. Use 'pocket', 'xmon', or 'concentric'.")

    spec["schema"] = "text-to-gds.transmon-layout-spec.v1"
    spec["variant"] = variant
    spec["target_frequency_ghz"] = frequency_ghz
    spec["target_ej_ec_ratio"] = ej_ec_ratio

    if output_path:
        import json
        from pathlib import Path

        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(spec, indent=2), encoding="utf-8")
        spec["result_path"] = str(out)

    return spec


def _generate_pocket_transmon(
    *,
    frequency_ghz: float,
    junction_area_um2: float,
    ej_ec_ratio: float,
    cpw_width_um: float,
    cpw_gap_um: float,
    readout_frequency_ghz: float,
    readout_coupling_capacitance_fF: float,
    flux_line_offset_um: float,
    chip_width_um: float,
    chip_height_um: float,
) -> dict[str, Any]:
    """Generate pocket transmon (IBM style)."""
    center_x = chip_width_um / 2.0
    center_y = chip_height_um / 2.0

    # Capacitor paddle dimensions (typical pocket transmon)
    paddle_width_um = 250.0
    paddle_height_um = 300.0
    paddle_gap_um = 30.0  # gap between paddles ( JJ goes here)

    # Ground pocket dimensions
    pocket_width_um = paddle_width_um * 2 + paddle_gap_um + 100.0
    pocket_height_um = paddle_height_um + 100.0

    # SQUID loop (single JJ for transmon, but can be SQUID for flux tunable)
    squid_loop_size_um = 12.0

    # Readout resonator (quarter-wave CPW)
    readout_length_um = _quarter_wave_length_um(readout_frequency_ghz, cpw_width_um, cpw_gap_um)

    return {
        "device_type": "pocket_transmon",
        "capacitor": {
            "type": "parallel_plate_paddles",
            "left_paddle": {
                "center_um": [center_x - paddle_gap_um / 2.0 - paddle_width_um / 2.0, center_y],
                "size_um": [paddle_width_um, paddle_height_um],
            },
            "right_paddle": {
                "center_um": [center_x + paddle_gap_um / 2.0 + paddle_width_um / 2.0, center_y],
                "size_um": [paddle_width_um, paddle_height_um],
            },
            "gap_um": paddle_gap_um,
            "total_capacitance_fF": _estimate_transmon_capacitance(
                paddle_width_um, paddle_height_um, paddle_gap_um
            ),
        },
        "ground_pocket": {
            "center_um": [center_x, center_y],
            "size_um": [pocket_width_um, pocket_height_um],
            "clearance_from_paddles_um": 20.0,
            "ground_via_stitching": True,
        },
        "junction": {
            "position_um": [center_x, center_y],
            "area_um2": junction_area_um2,
            "type": "single_jj" if ej_ec_ratio < 100 else "squid",
        },
        "squid": {
            "loop_size_um": squid_loop_size_um,
            "position_um": [center_x, center_y],
            "junction_separation_um": 8.0,
        },
        "flux_line": {
            "offset_um": flux_line_offset_um,
            "coupling_length_um": 20.0,
            "line_width_um": 3.0,
            "position_um": [center_x, center_y - squid_loop_size_um / 2.0 - flux_line_offset_um],
        },
        "readout_resonator": {
            "type": "quarter_wave_cpw",
            "length_um": readout_length_um,
            "center_width_um": cpw_width_um,
            "gap_um": cpw_gap_um,
            "coupling_capacitance_fF": readout_coupling_capacitance_fF,
            "coupling_type": "side_coupled",
        },
        "launch_pads": _standard_launch_pads(center_y, chip_width_um),
        "wirebond_pads": _standard_wirebond_pads(center_y, chip_width_um),
        "ground_stitching": {
            "pitch_um": 50.0,
            "via_size_um": 3.0,
        },
        "fabrication_notes": [
            "Large capacitor paddles in ground pocket (IBM style)",
            "Optimized clearance between paddles and ground pocket",
            "Flux line offset from SQUID for adjustable coupling",
            "Side-coupled readout resonator",
            "Ground via stitching around pocket",
        ],
    }


def _generate_xmon(
    *,
    frequency_ghz: float,
    junction_area_um2: float,
    ej_ec_ratio: float,
    readout_frequency_ghz: float,
    readout_coupling_capacitance_fF: float,
    chip_width_um: float,
    chip_height_um: float,
) -> dict[str, Any]:
    """Generate Xmon (Google/Yale style cross-shaped capacitor)."""
    center_x = chip_width_um / 2.0
    center_y = chip_height_um / 2.0

    arm_length_um = 200.0
    arm_width_um = 30.0

    return {
        "device_type": "xmon",
        "capacitor": {
            "type": "cross_shaped",
            "arms": [
                {"direction": "north", "center_um": [center_x, center_y + arm_length_um / 2.0],
                 "size_um": [arm_width_um, arm_length_um]},
                {"direction": "south", "center_um": [center_x, center_y - arm_length_um / 2.0],
                 "size_um": [arm_width_um, arm_length_um]},
                {"direction": "east", "center_um": [center_x + arm_length_um / 2.0, center_y],
                 "size_um": [arm_length_um, arm_width_um]},
                {"direction": "west", "center_um": [center_x - arm_length_um / 2.0, center_y],
                 "size_um": [arm_length_um, arm_width_um]},
            ],
            "arm_length_um": arm_length_um,
            "arm_width_um": arm_width_um,
        },
        "ground": {
            "type": "coplanar_ground",
            "clearance_from_arms_um": 15.0,
        },
        "junction": {
            "position_um": [center_x, center_y - arm_length_um / 2.0 - 10.0],
            "area_um2": junction_area_um2,
            "type": "single_jj",
        },
        "readout_coupling": {
            "arm": "east",
            "coupling_capacitance_fF": readout_coupling_capacitance_fF,
        },
        "launch_pads": _standard_launch_pads(center_y, chip_width_um),
        "fabrication_notes": [
            "Cross-shaped capacitor (Xmon geometry)",
            "Coplanar ground (no ground pocket)",
            "Single JJ at south arm terminus",
            "Readout coupling via east arm",
        ],
    }


def _generate_concentric_transmon(
    *,
    frequency_ghz: float,
    junction_area_um2: float,
    ej_ec_ratio: float,
    readout_frequency_ghz: float,
    readout_coupling_capacitance_fF: float,
    chip_width_um: float,
    chip_height_um: float,
) -> dict[str, Any]:
    """Generate concentric transmon."""
    center_x = chip_width_um / 2.0
    center_y = chip_height_um / 2.0

    inner_radius_um = 50.0
    outer_radius_um = 150.0
    gap_um = 20.0

    return {
        "device_type": "concentric_transmon",
        "capacitor": {
            "type": "concentric_ring",
            "inner_disk_radius_um": inner_radius_um,
            "outer_ring_inner_radius_um": inner_radius_um + gap_um,
            "outer_ring_outer_radius_um": outer_radius_um,
            "gap_um": gap_um,
        },
        "ground": {
            "type": "coplanar_ground",
            "clearance_from_outer_ring_um": 15.0,
        },
        "junction": {
            "position_um": [center_x, center_y],
            "area_um2": junction_area_um2,
            "type": "single_jj",
            "connection": "inner_disk_to_ground",
        },
        "readout_coupling": {
            "type": "capacitive_to_outer_ring",
            "coupling_capacitance_fF": readout_coupling_capacitance_fF,
        },
        "launch_pads": _standard_launch_pads(center_y, chip_width_um),
        "fabrication_notes": [
            "Concentric disk/ring capacitor",
            "Inner disk connected to ground via JJ",
            "Outer ring coupled to readout resonator",
        ],
    }


def _standard_launch_pads(center_y: float, chip_width_um: float) -> dict[str, Any]:
    pad_width = 100.0
    pad_length = 150.0
    return {
        "configuration": "GSG",
        "left": {
            "signal": {"center_um": [pad_length / 2.0, center_y],
                        "size_um": [pad_length, pad_width]},
            "ground_top": {"center_um": [pad_length / 2.0, center_y + pad_width + 20.0],
                           "size_um": [pad_length, pad_width]},
            "ground_bottom": {"center_um": [pad_length / 2.0, center_y - pad_width - 20.0],
                              "size_um": [pad_length, pad_width]},
        },
        "right": {
            "signal": {"center_um": [chip_width_um - pad_length / 2.0, center_y],
                        "size_um": [pad_length, pad_width]},
            "ground_top": {"center_um": [chip_width_um - pad_length / 2.0, center_y + pad_width + 20.0],
                           "size_um": [pad_length, pad_width]},
            "ground_bottom": {"center_um": [chip_width_um - pad_length / 2.0, center_y - pad_width - 20.0],
                              "size_um": [pad_length, pad_width]},
        },
    }


def _standard_wirebond_pads(center_y: float, chip_width_um: float) -> dict[str, Any]:
    return {
        "pads": [
            {"name": "FLUX_BIAS", "center_um": [chip_width_um / 2.0, 100.0],
             "size_um": [120.0, 80.0]},
            {"name": "GND_LEFT", "center_um": [100.0, center_y],
             "size_um": [80.0, 120.0]},
            {"name": "GND_RIGHT", "center_um": [chip_width_um - 100.0, center_y],
             "size_um": [80.0, 120.0]},
        ],
    }


def _quarter_wave_length_um(freq_ghz: float, width_um: float, gap_um: float) -> float:
    """Estimate quarter-wave CPW length."""
    # Typical phase velocity for CPW on Si
    eps_eff = 6.2
    c = 299_792_458.0  # m/s
    vp = c / math.sqrt(eps_eff)
    wavelength_m = vp / (freq_ghz * 1e9)
    return (wavelength_m / 4.0) * 1e6  # convert to um


def _estimate_transmon_capacitance(
    paddle_width_um: float,
    paddle_height_um: float,
    gap_um: float,
) -> float:
    """Estimate transmon shunt capacitance."""
    eps0 = 8.8541878128e-12
    eps_eff = 6.2
    area_m2 = paddle_width_um * paddle_height_um * 1e-12
    c = eps0 * eps_eff * area_m2 / (gap_um * 1e-6)
    return round(c * 1e15, 2)  # fF
