"""First-order superconducting, microwave, magnetic, and package design models."""

from __future__ import annotations

import math
from typing import Any

import numpy as np

EPSILON_0 = 8.8541878128e-12
MU0 = 4.0e-7 * math.pi
LIGHT_SPEED = 299792458.0
FLUX_QUANTUM_WB = 2.067833848e-15


SUPERCONDUCTING_MATERIALS = {
    "Al": {"tc_k": 1.2, "penetration_depth_nm": 50.0, "gap_frequency_ghz": 88.0},
    "Nb": {"tc_k": 9.2, "penetration_depth_nm": 90.0, "gap_frequency_ghz": 670.0},
    "NbN": {"tc_k": 16.0, "penetration_depth_nm": 350.0, "gap_frequency_ghz": 1170.0},
    "NbTiN": {"tc_k": 14.0, "penetration_depth_nm": 300.0, "gap_frequency_ghz": 1020.0},
    "TiN": {"tc_k": 4.5, "penetration_depth_nm": 450.0, "gap_frequency_ghz": 330.0},
}


def superconducting_material_database() -> dict[str, dict[str, float]]:
    return {name: dict(values) for name, values in SUPERCONDUCTING_MATERIALS.items()}


def surface_impedance_model(
    *, frequency_hz: float, surface_resistance_ohm: float, kinetic_inductance_h_per_square: float
) -> dict[str, float]:
    if frequency_hz <= 0.0 or min(surface_resistance_ohm, kinetic_inductance_h_per_square) < 0.0:
        raise ValueError("Invalid surface impedance inputs")
    return {
        "resistance_ohm_per_square": surface_resistance_ohm,
        "reactance_ohm_per_square": 2.0 * math.pi * frequency_hz * kinetic_inductance_h_per_square,
    }


def superconducting_loss(
    *, frequency_hz: float, surface_resistance_ohm: float, geometric_factor_ohm: float
) -> dict[str, float]:
    if min(frequency_hz, geometric_factor_ohm) <= 0.0 or surface_resistance_ohm < 0.0:
        raise ValueError("Invalid superconducting loss inputs")
    quality_factor = math.inf if surface_resistance_ohm == 0.0 else geometric_factor_ohm / surface_resistance_ohm
    return {
        "quality_factor": quality_factor,
        "loss_tangent_equivalent": 0.0 if math.isinf(quality_factor) else 1.0 / quality_factor,
        "decay_rate_hz": 0.0 if math.isinf(quality_factor) else frequency_hz / quality_factor,
    }


def dielectric_loss_participation(regions: list[dict[str, float]]) -> dict[str, Any]:
    """Calculate electric-energy participation and dielectric-limited Q."""
    energies = np.asarray([float(region["electric_energy_j"]) for region in regions])
    if energies.size == 0 or np.any(energies < 0.0) or float(np.sum(energies)) <= 0.0:
        raise ValueError("Positive electric field energies are required")
    participation = energies / np.sum(energies)
    weighted_loss = sum(float(p) * float(region.get("loss_tangent", 0.0)) for p, region in zip(participation, regions, strict=True))
    return {
        "regions": [
            {**region, "participation": float(value)}
            for region, value in zip(regions, participation, strict=True)
        ],
        "total_loss_tangent": weighted_loss,
        "dielectric_limited_q": math.inf if weighted_loss == 0.0 else 1.0 / weighted_loss,
    }


def vortex_trapping_risk(
    *,
    field_t: float,
    trace_width_um: float,
    penetration_depth_nm: float,
    hole_pitch_um: float | None = None,
) -> dict[str, float | str]:
    if trace_width_um <= 0.0 or penetration_depth_nm <= 0.0:
        raise ValueError("Trace width and penetration depth must be positive")
    effective_area_m2 = trace_width_um**2 * 1e-12
    vortices = abs(field_t) * effective_area_m2 / FLUX_QUANTUM_WB
    screening = math.exp(-trace_width_um * 1000.0 / penetration_depth_nm)
    mitigation = 1.0 if hole_pitch_um is None else min(1.0, trace_width_um / max(hole_pitch_um, 1e-12))
    score = vortices * (1.0 - screening) / (1.0 + mitigation)
    return {
        "expected_flux_quanta_per_trace_square": vortices,
        "risk_score": score,
        "risk": "high" if score > 1.0 else "moderate" if score > 0.1 else "low",
    }


def magnetic_field_compatibility(
    *,
    fields_t: list[float],
    zero_field_frequency_ghz: float,
    zero_field_gain_db: float,
    critical_field_t: float,
    field_alignment_factor: float = 1.0,
) -> dict[str, Any]:
    if zero_field_frequency_ghz <= 0.0 or critical_field_t <= 0.0:
        raise ValueError("Frequency and critical field must be positive")
    rows = []
    for field in fields_t:
        normalized = min(abs(field) * field_alignment_factor / critical_field_t, 1.5)
        superfluid = max(1.0 - normalized**2, 0.01)
        rows.append(
            {
                "field_t": field,
                "frequency_ghz": zero_field_frequency_ghz * math.sqrt(superfluid),
                "gain_db": max(zero_field_gain_db - 20.0 * normalized**2, 0.0),
                "relative_noise": 1.0 + 4.0 * normalized**2,
            }
        )
    return {"schema": "text-to-gds.magnetic-compatibility.v1", "sweep": rows, "model": "pair-breaking screening surrogate"}


def optimize_flux_holes(
    *, chip_width_um: float, chip_height_um: float, field_t: float, min_pitch_um: float = 10.0
) -> dict[str, Any]:
    if min(chip_width_um, chip_height_um, min_pitch_um) <= 0.0:
        raise ValueError("Dimensions and pitch must be positive")
    target_cell_area = min(FLUX_QUANTUM_WB / max(abs(field_t), 1e-12) * 1e12, min_pitch_um**2)
    pitch = max(math.sqrt(target_cell_area), min_pitch_um)
    nx, ny = max(1, int(chip_width_um // pitch)), max(1, int(chip_height_um // pitch))
    return {
        "pitch_um": pitch,
        "hole_count": nx * ny,
        "grid": [nx, ny],
        "expected_flux_quanta_per_cell": abs(field_t) * pitch**2 * 1e-12 / FLUX_QUANTUM_WB,
    }


def cpw_impedance_ohm(width_um: float, gap_um: float, epsilon_r: float) -> float:
    """Quasi-static CPW impedance using complete elliptic integrals."""
    if min(width_um, gap_um, epsilon_r) <= 0.0:
        raise ValueError("CPW dimensions and epsilon_r must be positive")
    k = width_um / (width_um + 2.0 * gap_um)
    kp = math.sqrt(1.0 - k**2)
    epsilon_eff = (epsilon_r + 1.0) / 2.0

    def elliptic_k(modulus: float) -> float:
        a, b = 1.0, math.sqrt(1.0 - modulus**2)
        for _ in range(30):
            next_a, next_b = (a + b) / 2.0, math.sqrt(a * b)
            if abs(next_a - next_b) < 1e-15:
                a = next_a
                break
            a, b = next_a, next_b
        return math.pi / (2.0 * a)

    return float(30.0 * math.pi / math.sqrt(epsilon_eff) * elliptic_k(kp) / elliptic_k(k))


def optimize_cpw_impedance(
    *, target_ohm: float = 50.0, epsilon_r: float = 11.45, min_width_um: float = 0.2
) -> dict[str, float]:
    candidates = []
    for width in np.geomspace(min_width_um, 100.0, 160):
        for ratio in np.geomspace(0.1, 5.0, 100):
            gap = width * ratio
            impedance = cpw_impedance_ohm(float(width), float(gap), epsilon_r)
            candidates.append((abs(impedance - target_ohm), width, gap, impedance))
    _, width, gap, impedance = min(candidates)
    return {"width_um": float(width), "gap_um": float(gap), "impedance_ohm": float(impedance), "error_ohm": float(impedance - target_ohm)}


def idc_capacitance_ff(
    *, finger_count: int, finger_length_um: float, finger_width_um: float, gap_um: float, epsilon_r: float
) -> float:
    if finger_count < 2 or min(finger_length_um, finger_width_um, gap_um, epsilon_r) <= 0.0:
        raise ValueError("Invalid IDC parameters")
    epsilon_eff = (epsilon_r + 1.0) / 2.0
    return (finger_count - 1) * EPSILON_0 * epsilon_eff * finger_length_um * 1e-6 * (finger_width_um / gap_um) * 1e15


def optimize_idc_capacitor(
    *, target_ff: float, epsilon_r: float = 11.45, min_feature_um: float = 0.2
) -> dict[str, float | int]:
    candidates = []
    for fingers in range(2, 101):
        for length in np.linspace(5.0, 500.0, 200):
            value = idc_capacitance_ff(finger_count=fingers, finger_length_um=float(length), finger_width_um=min_feature_um, gap_um=min_feature_um, epsilon_r=epsilon_r)
            candidates.append((abs(value - target_ff), fingers, length, value))
    _, fingers, length, value = min(candidates)
    return {"finger_count": fingers, "finger_length_um": float(length), "finger_width_um": min_feature_um, "gap_um": min_feature_um, "capacitance_ff": float(value)}


def optimize_coupling_capacitor(*, target_q_external: float, frequency_ghz: float, impedance_ohm: float = 50.0) -> dict[str, float]:
    if min(target_q_external, frequency_ghz, impedance_ohm) <= 0.0:
        raise ValueError("Coupling targets must be positive")
    omega = 2.0 * math.pi * frequency_ghz * 1e9
    capacitance = math.sqrt(math.pi / (2.0 * omega**2 * impedance_ohm**2 * target_q_external))
    return {"coupling_capacitance_ff": capacitance * 1e15, "target_q_external": target_q_external}


def tune_resonator_length(*, target_frequency_ghz: float, epsilon_eff: float, mode: str = "quarter_wave") -> dict[str, float | str]:
    if min(target_frequency_ghz, epsilon_eff) <= 0.0:
        raise ValueError("Frequency and epsilon_eff must be positive")
    divisor = 4.0 if mode == "quarter_wave" else 2.0
    length_m = LIGHT_SPEED / math.sqrt(epsilon_eff) / (target_frequency_ghz * 1e9) / divisor
    return {"mode": mode, "physical_length_um": length_m * 1e6, "guided_wavelength_um": length_m * divisor * 1e6}


def distributed_transmission_line(
    *, frequency_hz: list[float], length_m: float, inductance_h_per_m: float, capacitance_f_per_m: float, resistance_ohm_per_m: float = 0.0, conductance_s_per_m: float = 0.0
) -> dict[str, Any]:
    if min(length_m, inductance_h_per_m, capacitance_f_per_m) <= 0.0:
        raise ValueError("Line parameters must be positive")
    rows = []
    for frequency in frequency_hz:
        omega = 2.0 * math.pi * frequency
        series = complex(resistance_ohm_per_m, omega * inductance_h_per_m)
        shunt = complex(conductance_s_per_m, omega * capacitance_f_per_m)
        gamma = np.sqrt(series * shunt)
        z0 = np.sqrt(series / shunt)
        rows.append({"frequency_hz": frequency, "z0_ohm": [float(z0.real), float(z0.imag)], "gamma_per_m": [float(gamma.real), float(gamma.imag)], "electrical_length_rad": float(gamma.imag * length_m)})
    return {"schema": "text-to-gds.distributed-line.v1", "samples": rows}


def pcb_chip_codesign(
    *, chip_impedance_ohm: float, pcb_impedance_ohm: float, connector_impedance_ohm: float = 50.0
) -> dict[str, Any]:
    impedances = [chip_impedance_ohm, pcb_impedance_ohm, connector_impedance_ohm]
    if min(impedances) <= 0.0:
        raise ValueError("Impedances must be positive")
    interfaces = []
    for source, load, name in zip(impedances, impedances[1:], ("chip_to_pcb", "pcb_to_connector"), strict=True):
        gamma = (load - source) / (load + source)
        interfaces.append({"interface": name, "reflection_coefficient": gamma, "return_loss_db": -20.0 * math.log10(max(abs(gamma), 1e-15))})
    return {"interfaces": interfaces, "worst_return_loss_db": min(item["return_loss_db"] for item in interfaces)}


def connector_transition_simulation(
    *, series_inductance_nh: float, shunt_capacitance_pf: float, frequencies_ghz: list[float], impedance_ohm: float = 50.0
) -> dict[str, Any]:
    rows = []
    for frequency in frequencies_ghz:
        omega = 2.0 * math.pi * frequency * 1e9
        z_series = 1j * omega * series_inductance_nh * 1e-9
        y_shunt = 1j * omega * shunt_capacitance_pf * 1e-12
        abcd_a, abcd_b, abcd_c, abcd_d = 1.0 + z_series * y_shunt, z_series, y_shunt, 1.0
        denominator = abcd_a + abcd_b / impedance_ohm + abcd_c * impedance_ohm + abcd_d
        s21 = 2.0 / denominator
        s11 = (abcd_a + abcd_b / impedance_ohm - abcd_c * impedance_ohm - abcd_d) / denominator
        rows.append({"frequency_ghz": frequency, "s21_db": 20.0 * math.log10(max(abs(s21), 1e-15)), "s11_db": 20.0 * math.log10(max(abs(s11), 1e-15))})
    return {"schema": "text-to-gds.connector-transition.v1", "samples": rows}
