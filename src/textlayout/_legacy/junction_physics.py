"""Josephson-junction transport, temperature, loss, field, aging, and reliability models."""

from __future__ import annotations

import math
from typing import Any

BOLTZMANN = 1.380649e-23
E_CHARGE = 1.602176634e-19
PLANCK = 6.62607015e-34
FLUX_QUANTUM = PLANCK / (2.0 * E_CHARGE)
EPSILON_0 = 8.8541878128e-12


def bcs_gap_j(*, temperature_k: float, critical_temperature_k: float) -> float:
    if critical_temperature_k <= 0.0 or temperature_k < 0.0:
        raise ValueError("Invalid temperature")
    if temperature_k >= critical_temperature_k:
        return 0.0
    delta_0 = 1.764 * BOLTZMANN * critical_temperature_k
    return delta_0 * math.tanh(1.74 * math.sqrt(critical_temperature_k / max(temperature_k, 1e-12) - 1.0))


def ambegaokar_baratoff(*, normal_resistance_ohm: float, temperature_k: float, critical_temperature_k: float) -> dict[str, float]:
    if normal_resistance_ohm <= 0.0:
        raise ValueError("Normal resistance must be positive")
    gap = bcs_gap_j(temperature_k=temperature_k, critical_temperature_k=critical_temperature_k)
    thermal = math.tanh(gap / max(2.0 * BOLTZMANN * max(temperature_k, 1e-12), 1e-30))
    ic = math.pi * gap / (2.0 * E_CHARGE * normal_resistance_ohm) * thermal
    return {"gap_j": gap, "critical_current_a": ic, "icrn_v": ic * normal_resistance_ohm}


def temperature_dependent_ic(*, zero_temperature_ic_a: float, temperatures_k: list[float], critical_temperature_k: float) -> dict[str, Any]:
    gap0 = bcs_gap_j(temperature_k=0.0, critical_temperature_k=critical_temperature_k)
    values = []
    for temperature in temperatures_k:
        gap = bcs_gap_j(temperature_k=temperature, critical_temperature_k=critical_temperature_k)
        thermal = math.tanh(gap / max(2.0 * BOLTZMANN * max(temperature, 1e-12), 1e-30))
        values.append(zero_temperature_ic_a * gap / gap0 * thermal if gap0 else 0.0)
    return {"temperature_k": temperatures_k, "critical_current_a": values}


def junction_aging(*, initial_ic_a: float, time_days: list[float], drift_fraction_per_decade: float = -0.01, activation_energy_ev: float | None = None, storage_temperature_k: float = 300.0) -> dict[str, Any]:
    if initial_ic_a <= 0.0:
        raise ValueError("Initial Ic must be positive")
    acceleration = 1.0
    if activation_energy_ev is not None:
        acceleration = math.exp(-activation_energy_ev * E_CHARGE / (BOLTZMANN * storage_temperature_k))
    values = [initial_ic_a * (1.0 + drift_fraction_per_decade * acceleration * math.log10(1.0 + max(day, 0.0))) for day in time_days]
    return {"time_days": time_days, "critical_current_a": values, "model": "log-time aging"}


def oxide_tunneling(*, voltage_v: list[float], barrier_height_ev: float, barrier_thickness_nm: float, area_um2: float) -> dict[str, Any]:
    """Symmetric Simmons low-bias tunneling-current approximation."""
    if min(barrier_height_ev, barrier_thickness_nm, area_um2) <= 0.0:
        raise ValueError("Barrier parameters must be positive")
    thickness = barrier_thickness_nm * 1e-9
    area = area_um2 * 1e-12
    mass = 9.1093837015e-31
    phi = barrier_height_ev * E_CHARGE
    exponent = math.exp(-2.0 * thickness * math.sqrt(2.0 * mass * phi) / (PLANCK / (2.0 * math.pi)))
    conductance = area * E_CHARGE**2 / (2.0 * math.pi * PLANCK * thickness**2) * exponent / max(phi, 1e-30)
    return {"voltage_v": voltage_v, "current_a": [conductance * value for value in voltage_v], "normal_resistance_ohm": 1.0 / max(conductance, 1e-30)}


def junction_capacitance(*, area_um2: float, barrier_thickness_nm: float, relative_permittivity: float, fringe_fraction: float = 0.0) -> dict[str, float]:
    if min(area_um2, barrier_thickness_nm, relative_permittivity) <= 0.0 or fringe_fraction < 0.0:
        raise ValueError("Invalid junction capacitance inputs")
    parallel = EPSILON_0 * relative_permittivity * area_um2 * 1e-12 / (barrier_thickness_nm * 1e-9)
    return {"parallel_plate_f": parallel, "total_f": parallel * (1.0 + fringe_fraction), "specific_capacitance_ff_per_um2": parallel / area_um2 * 1e15}


def subgap_leakage(*, voltage_v: list[float], subgap_resistance_ohm: float, dynes_fraction: float = 0.0, normal_resistance_ohm: float | None = None) -> dict[str, Any]:
    if subgap_resistance_ohm <= 0.0 or dynes_fraction < 0.0:
        raise ValueError("Invalid subgap inputs")
    conductance = 1.0 / subgap_resistance_ohm + (dynes_fraction / normal_resistance_ohm if normal_resistance_ohm else 0.0)
    return {"voltage_v": voltage_v, "current_a": [conductance * value for value in voltage_v], "effective_subgap_resistance_ohm": 1.0 / conductance}


def quasiparticle_loss(*, frequency_hz: float, quasiparticle_density_per_um3: float, cooper_pair_density_per_um3: float, kinetic_participation: float) -> dict[str, float]:
    if min(frequency_hz, cooper_pair_density_per_um3) <= 0.0 or min(quasiparticle_density_per_um3, kinetic_participation) < 0.0:
        raise ValueError("Invalid quasiparticle inputs")
    loss = kinetic_participation * quasiparticle_density_per_um3 / cooper_pair_density_per_um3
    return {"inverse_q": loss, "quality_factor": math.inf if loss == 0.0 else 1.0 / loss, "decay_rate_hz": frequency_hz * loss}


def tls_loss(*, intrinsic_loss_tangent: float, electric_field_v_per_m: list[float], critical_field_v_per_m: float, temperature_k: float, frequency_hz: float) -> dict[str, Any]:
    if min(critical_field_v_per_m, temperature_k, frequency_hz) <= 0.0 or intrinsic_loss_tangent < 0.0:
        raise ValueError("Invalid TLS inputs")
    thermal = math.tanh(PLANCK * frequency_hz / (2.0 * BOLTZMANN * temperature_k))
    loss = [intrinsic_loss_tangent * thermal / math.sqrt(1.0 + (field / critical_field_v_per_m) ** 2) for field in electric_field_v_per_m]
    return {"electric_field_v_per_m": electric_field_v_per_m, "loss_tangent": loss, "quality_factor": [math.inf if value == 0.0 else 1.0 / value for value in loss]}


def magnetic_junction_degradation(*, fields_t: list[float], junction_width_um: float, effective_magnetic_thickness_nm: float, zero_field_ic_a: float) -> dict[str, Any]:
    if min(junction_width_um, effective_magnetic_thickness_nm, zero_field_ic_a) <= 0.0:
        raise ValueError("Invalid magnetic junction parameters")
    area = junction_width_um * 1e-6 * effective_magnetic_thickness_nm * 1e-9
    values = []
    for field in fields_t:
        x = math.pi * field * area / FLUX_QUANTUM
        factor = 1.0 if abs(x) < 1e-15 else abs(math.sin(x) / x)
        values.append(zero_field_ic_a * factor)
    return {"field_t": fields_t, "critical_current_a": values, "model": "Fraunhofer"}


def junction_reliability(*, stress: list[float], characteristic_stress: float, weibull_shape: float, aging_damage: float = 0.0) -> dict[str, Any]:
    if min(characteristic_stress, weibull_shape) <= 0.0 or aging_damage < 0.0:
        raise ValueError("Invalid reliability parameters")
    survival = [math.exp(-((max(value, 0.0) / characteristic_stress) ** weibull_shape + aging_damage)) for value in stress]
    return {"stress": stress, "survival_probability": survival, "failure_probability": [1.0 - value for value in survival]}
