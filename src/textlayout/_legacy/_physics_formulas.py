from __future__ import annotations

import math
from typing import Any

PHI0_WEBER = 2.067833848e-15
PLANCK_J_S = 6.62607015e-34
BOLTZMANN_J_K = 1.380649e-23


def critical_current_ua(junction_area_um2: float, jc_ua_per_um2: float) -> float:
    """Return critical current in microamps from area and critical current density."""
    if junction_area_um2 < 0:
        raise ValueError(f"junction_area_um2 must be non-negative, got {junction_area_um2}")
    if jc_ua_per_um2 <= 0:
        raise ValueError(f"jc_ua_per_um2 must be positive, got {jc_ua_per_um2}")
    return junction_area_um2 * jc_ua_per_um2


def dc_squid_effective_critical_current_ua(
    zero_flux_critical_current_ua: float,
    *,
    flux_bias_phi0: float,
    squid_asymmetry: float = 0.0,
) -> float:
    """Return low-inductance dc-SQUID critical current versus flux.

    `zero_flux_critical_current_ua` is the total SQUID critical current at
    integer flux. `squid_asymmetry = abs(Ic1 - Ic2) / (Ic1 + Ic2)`.
    """
    if zero_flux_critical_current_ua < 0:
        raise ValueError(
            "zero_flux_critical_current_ua must be non-negative, "
            f"got {zero_flux_critical_current_ua}"
        )
    if not 0.0 <= squid_asymmetry < 1.0:
        raise ValueError(f"squid_asymmetry must satisfy 0 <= d < 1, got {squid_asymmetry}")

    phase = math.pi * flux_bias_phi0
    modulation = math.sqrt(
        math.cos(phase) ** 2 + (squid_asymmetry**2) * (math.sin(phase) ** 2)
    )
    return zero_flux_critical_current_ua * modulation


def josephson_inductance_ph(critical_current_ua: float) -> float | None:
    """Return ideal zero-phase small-signal Josephson inductance in picohenries."""
    if critical_current_ua < 0:
        raise ValueError(f"critical_current_ua must be non-negative, got {critical_current_ua}")
    if critical_current_ua == 0:
        return None
    critical_current_a = critical_current_ua * 1e-6
    return PHI0_WEBER / (2.0 * math.pi * critical_current_a) * 1e12


def _flux_period_current_ma(
    *,
    flux_period_current_ma: float | None,
    flux_mutual_inductance_ph: float | None,
) -> float | None:
    if flux_period_current_ma is not None:
        if flux_period_current_ma <= 0.0:
            raise ValueError(
                f"flux_period_current_ma must be positive, got {flux_period_current_ma}"
            )
        return flux_period_current_ma
    if flux_mutual_inductance_ph is None:
        return None
    if flux_mutual_inductance_ph <= 0.0:
        raise ValueError(
            f"flux_mutual_inductance_ph must be positive, got {flux_mutual_inductance_ph}"
        )
    return PHI0_WEBER / (flux_mutual_inductance_ph * 1e-12) * 1e3


def _resonant_capacitance_ff(center_ghz: float, lj_ph: float) -> float:
    lj_h = lj_ph * 1e-12
    resonant_cap_f = 1.0 / ((2.0 * math.pi * center_ghz * 1e9) ** 2 * lj_h)
    return resonant_cap_f * 1e15


def squid_flux_modulation(
    *,
    zero_flux_critical_current_ua: float,
    flux_bias_phi0: float,
    squid_asymmetry: float,
    center_frequency_ghz: float,
    resonator_capacitance_ff: float | None = None,
    flux_sweep_span_phi0: float = 1.0,
    flux_sweep_points: int = 101,
    flux_period_current_ma: float | None = None,
    flux_mutual_inductance_ph: float | None = None,
) -> dict[str, Any]:
    """Return Aharonov-Bohm flux-periodic SQUID tuning data.

    Assumes a low-loop-inductance dc-SQUID and a fixed resonator capacitance.
    """
    if flux_sweep_points < 2:
        raise ValueError(f"flux_sweep_points must be >= 2, got {flux_sweep_points}")
    if flux_sweep_span_phi0 <= 0.0:
        raise ValueError(f"flux_sweep_span_phi0 must be positive, got {flux_sweep_span_phi0}")

    zero_flux_lj_ph = josephson_inductance_ph(zero_flux_critical_current_ua)
    if zero_flux_lj_ph is None:
        cap_ff = resonator_capacitance_ff
    else:
        cap_ff = (
            resonator_capacitance_ff
            if resonator_capacitance_ff is not None and resonator_capacitance_ff > 0.0
            else _resonant_capacitance_ff(center_frequency_ghz, zero_flux_lj_ph)
        )
    period_current_ma = _flux_period_current_ma(
        flux_period_current_ma=flux_period_current_ma,
        flux_mutual_inductance_ph=flux_mutual_inductance_ph,
    )

    def point(phi0: float) -> dict[str, float | None]:
        ic_ua = dc_squid_effective_critical_current_ua(
            zero_flux_critical_current_ua,
            flux_bias_phi0=phi0,
            squid_asymmetry=squid_asymmetry,
        )
        lj_ph = josephson_inductance_ph(ic_ua)
        if lj_ph is None or cap_ff is None:
            frequency_ghz = None
        else:
            frequency_ghz = (
                1.0 / (2.0 * math.pi * math.sqrt(lj_ph * 1e-12 * cap_ff * 1e-15)) / 1e9
            )
        return {
            "flux_phi0": phi0,
            "coil_current_ma": None if period_current_ma is None else phi0 * period_current_ma,
            "critical_current_ua": ic_ua,
            "josephson_inductance_ph": lj_ph,
            "resonant_frequency_ghz": frequency_ghz,
        }

    start = flux_bias_phi0 - flux_sweep_span_phi0 / 2.0
    step = flux_sweep_span_phi0 / float(flux_sweep_points - 1)
    sweep = [point(start + index * step) for index in range(flux_sweep_points)]
    operating_point = point(flux_bias_phi0)
    finite_frequencies = [
        float(row["resonant_frequency_ghz"])
        for row in sweep
        if row["resonant_frequency_ghz"] is not None
    ]
    return {
        "schema": "text-to-gds.squid-flux-modulation.v0",
        "model": "low_loop_inductance_dc_squid",
        "assumptions": [
            "Two-junction dc-SQUID with negligible loop inductance.",
            "Flux enters through Aharonov-Bohm phase around the SQUID loop.",
            "Resonator capacitance is fixed while Josephson inductance tunes with flux.",
        ],
        "zero_flux_critical_current_ua": zero_flux_critical_current_ua,
        "zero_flux_josephson_inductance_ph": zero_flux_lj_ph,
        "squid_asymmetry": squid_asymmetry,
        "flux_bias_phi0": flux_bias_phi0,
        "flux_period_phi0": 1.0,
        "flux_period_current_ma": period_current_ma,
        "flux_mutual_inductance_ph": flux_mutual_inductance_ph,
        "resonator_capacitance_ff": cap_ff,
        "operating_point": operating_point,
        "tuning_range_ghz": (
            [min(finite_frequencies), max(finite_frequencies)] if finite_frequencies else None
        ),
        "sweep": sweep,
    }


def simulate_ideal_junction(
    sidecar: dict[str, Any],
    *,
    jc_ua_per_um2: float,
    shunt_capacitance_ff: float,
    flux_bias_phi0: float = 0.0,
    squid_asymmetry: float = 0.0,
) -> dict[str, float | None]:
    """Compute ideal JJ quantities from Text-to-GDS sidecar metadata."""
    if shunt_capacitance_ff < 0:
        raise ValueError(f"shunt_capacitance_ff must be non-negative, got {shunt_capacitance_ff}")

    info = sidecar.get("info", {})
    area_um2 = float(info.get("junction_area_um2", 0.0))
    zero_flux_ic_ua = critical_current_ua(area_um2, jc_ua_per_um2)
    uses_squid = bool(info.get("squid_enabled")) or int(info.get("squid_junction_count", 1)) > 1
    ic_ua = (
        dc_squid_effective_critical_current_ua(
            zero_flux_ic_ua,
            flux_bias_phi0=flux_bias_phi0,
            squid_asymmetry=squid_asymmetry,
        )
        if uses_squid
        else zero_flux_ic_ua
    )
    result: dict[str, float | None] = {
        "junction_area_um2": area_um2,
        "jc_ua_per_um2": jc_ua_per_um2,
        "critical_current_ua": ic_ua,
        "josephson_inductance_ph": josephson_inductance_ph(ic_ua),
        "shunt_capacitance_ff": shunt_capacitance_ff,
    }
    if uses_squid:
        result.update(
            {
                "zero_flux_critical_current_ua": zero_flux_ic_ua,
                "flux_bias_phi0": flux_bias_phi0,
                "squid_asymmetry": squid_asymmetry,
            }
        )
    return result


def _sidecar_ports(sidecar: dict[str, Any]) -> list[dict[str, Any]]:
    return [port for port in sidecar.get("ports", []) if isinstance(port, dict)]


def _named_port(sidecar: dict[str, Any], names: tuple[str, ...]) -> dict[str, Any] | None:
    ports = _sidecar_ports(sidecar)
    for name in names:
        for port in ports:
            if port.get("name") == name:
                return port
    return None


def _port_pair(sidecar: dict[str, Any]) -> dict[str, Any]:
    input_port = _named_port(sidecar, ("rf_in", "input", "west", "bottom_west"))
    output_port = _named_port(sidecar, ("rf_out", "output", "east", "bottom_east"))
    return {
        "input": input_port,
        "output": output_port,
        "all_ports": _sidecar_ports(sidecar),
    }


def _safe_log10(value: float) -> float:
    return math.log10(max(value, 1e-30))


def estimate_physical_performance(
    sidecar: dict[str, Any],
    *,
    jc_ua_per_um2: float,
    shunt_capacitance_ff: float,
    target_frequency_ghz: float | None = None,
    target_gain_db: float = 20.0,
    target_bandwidth_mhz: float | None = None,
    pump_current_fraction: float = 0.017,
    coupling_capacitance_ff: float | None = None,
    resonator_capacitance_ff: float | None = None,
    flux_bias_phi0: float = 0.0,
    squid_asymmetry: float = 0.0,
    flux_sweep_span_phi0: float = 1.0,
    flux_sweep_points: int = 101,
    flux_period_current_ma: float | None = None,
    flux_mutual_inductance_ph: float | None = None,
) -> dict[str, Any]:
    """Deprecated: performance requires extraction.json plus an executed solver."""
    return {"status": "failed", "reason": "missing extracted parameter"}

    # Legacy implementation below is intentionally unreachable during the migration.
    if pump_current_fraction <= 0.0:
        raise ValueError(f"pump_current_fraction must be positive, got {pump_current_fraction}")

    info = sidecar.get("info", {})
    device_type = str(info.get("device_type", sidecar.get("pcell", "unknown")))
    area_um2 = float(info.get("junction_area_um2", 0.0))
    zero_flux_ic_ua = critical_current_ua(area_um2, jc_ua_per_um2)
    uses_squid = bool(info.get("squid_enabled")) or int(info.get("squid_junction_count", 1)) > 1
    ic_ua = (
        dc_squid_effective_critical_current_ua(
            zero_flux_ic_ua,
            flux_bias_phi0=flux_bias_phi0,
            squid_asymmetry=squid_asymmetry,
        )
        if uses_squid
        else zero_flux_ic_ua
    )
    lj_ph = josephson_inductance_ph(ic_ua)
    ports = _port_pair(sidecar)

    if device_type == "via_chain_monitor":
        stage_count = int(info.get("stage_count", 0))
        per_via_ohm = float(info.get("estimated_via_resistance_ohm", 0.0))
        metal_ohm = float(info.get("estimated_metal_resistance_ohm", 0.0))
        return {
            "analysis_type": "via_chain_resistance_estimate",
            "device_type": device_type,
            "ports": ports,
            "stage_count": stage_count,
            "estimated_total_resistance_ohm": stage_count * per_via_ohm + metal_ohm,
            "estimated_via_resistance_ohm": per_via_ohm,
            "estimated_metal_resistance_ohm": metal_ohm,
            "topology": {
                "open_chain_detected": False,
                "route_style": info.get("route_style", "manhattan_ladder"),
            },
            "model_validity": "layout-topology and resistance placeholder; not extracted RC signoff",
        }

    center_ghz = float(target_frequency_ghz or info.get("center_frequency_ghz", 5.0))
    bandwidth_mhz = float(target_bandwidth_mhz or info.get("target_bandwidth_mhz", 500.0))
    gain_db = float(info.get("target_gain_db", target_gain_db))
    quantum_noise_k = PLANCK_J_S * center_ghz * 1e9 / (2.0 * BOLTZMANN_J_K)

    if device_type == "lumped_element_jpa_seed" and lj_ph is not None:
        zero_flux_lj_ph = josephson_inductance_ph(zero_flux_ic_ua)
        capacitance_lj_ph = zero_flux_lj_ph or lj_ph
        resonator_cap_ff = (
            float(resonator_capacitance_ff)
            if resonator_capacitance_ff is not None and resonator_capacitance_ff > 0.0
            else _resonant_capacitance_ff(center_ghz, capacitance_lj_ph)
        )
        coupling_cap_ff = (
            float(coupling_capacitance_ff)
            if coupling_capacitance_ff is not None
            else max(resonator_cap_ff * 0.05, 5.0)
        )
        flux_tuning = None
        if uses_squid:
            flux_tuning = squid_flux_modulation(
                zero_flux_critical_current_ua=zero_flux_ic_ua,
                flux_bias_phi0=flux_bias_phi0,
                squid_asymmetry=squid_asymmetry,
                center_frequency_ghz=center_ghz,
                resonator_capacitance_ff=resonator_cap_ff,
                flux_sweep_span_phi0=flux_sweep_span_phi0,
                flux_sweep_points=flux_sweep_points,
                flux_period_current_ma=flux_period_current_ma,
                flux_mutual_inductance_ph=flux_mutual_inductance_ph,
            )
        q_loaded = center_ghz * 1000.0 / max(bandwidth_mhz, 1e-9)
        pump_current_ua = ic_ua * pump_current_fraction
        saturation_power_dbm = (
            -112.0
            + 10.0 * _safe_log10(ic_ua / 0.1)
            + 3.0 * _safe_log10(bandwidth_mhz / 500.0)
            - 0.25 * max(gain_db - 20.0, 0.0)
        )
        return {
            "analysis_type": "layout_derived_ljpa_estimate",
            "device_type": device_type,
            "ports": ports,
            "center_frequency_ghz": center_ghz,
            "target_gain_db": gain_db,
            "estimated_peak_gain_db": gain_db,
            "bandwidth_3db_mhz": bandwidth_mhz,
            "loaded_q": q_loaded,
            "estimated_input_1db_compression_dbm": saturation_power_dbm,
            "estimated_saturation_power_dbm": saturation_power_dbm,
            "quantum_limited_noise_temperature_k": quantum_noise_k,
            "critical_current_ua": ic_ua,
            "zero_flux_critical_current_ua": zero_flux_ic_ua,
            "josephson_inductance_ph": lj_ph,
            "pump_current_ua": pump_current_ua,
            "pump_current_fraction": pump_current_fraction,
            "resonator_capacitance_ff": resonator_cap_ff,
            "coupling_capacitance_ff": coupling_cap_ff,
            "shunt_capacitance_ff": shunt_capacitance_ff,
            "flux_tuning": flux_tuning,
            "model_validity": (
                "first-order lumped LJPA estimate; use JosephsonCircuits.jl or measured "
                "data for signoff gain, bandwidth, and compression power"
            ),
        }

    return {
        "analysis_type": "ideal_jj_small_signal",
        "device_type": device_type,
        "ports": ports,
        "critical_current_ua": ic_ua,
        "josephson_inductance_ph": lj_ph,
        "junction_area_um2": area_um2,
        "jc_ua_per_um2": jc_ua_per_um2,
        "shunt_capacitance_ff": shunt_capacitance_ff,
        "model_validity": "exact ideal zero-phase Ic and small-signal Lj from sidecar area and Jc",
    }
