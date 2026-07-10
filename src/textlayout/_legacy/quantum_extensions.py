"""Quantum-circuit extraction, black-box quantization, Kerr, and lifetime models."""

from __future__ import annotations

import math
from typing import Any

import numpy as np

E_CHARGE = 1.602176634e-19
HBAR = 1.054571817e-34
PLANCK = 6.62607015e-34
PHI0 = 2.067833848e-15


def extract_hamiltonian(
    *, capacitance_f: float, critical_current_a: float, charge_offset: float = 0.0, levels: int = 8
) -> dict[str, Any]:
    """Diagonalize a charge-basis transmon Hamiltonian."""
    if min(capacitance_f, critical_current_a) <= 0.0 or levels < 3:
        raise ValueError("Positive C/Ic and at least three levels are required")
    ec = E_CHARGE**2 / (2.0 * capacitance_f)
    ej = critical_current_a * PHI0 / (2.0 * math.pi)
    cutoff = max(15, levels * 3)
    charges = np.arange(-cutoff, cutoff + 1)
    hamiltonian = np.diag(4.0 * ec * (charges - charge_offset) ** 2)
    coupling = -ej / 2.0
    hamiltonian += np.diag(np.full(2 * cutoff, coupling), 1)
    hamiltonian += np.diag(np.full(2 * cutoff, coupling), -1)
    energies = np.linalg.eigvalsh(hamiltonian)[:levels]
    energies = (energies - energies[0]) / PLANCK / 1e9
    return {
        "schema": "text-to-gds.hamiltonian.v1",
        "ej_ghz": ej / PLANCK / 1e9,
        "ec_ghz": ec / PLANCK / 1e9,
        "levels_ghz": energies.tolist(),
        "transition_01_ghz": float(energies[1]),
        "anharmonicity_mhz": float((energies[2] - 2.0 * energies[1]) * 1000.0),
        "basis": "charge",
    }


def black_box_quantization(
    modes: list[dict[str, float]], junction_participations: list[list[float]], josephson_energies_j: list[float]
) -> dict[str, Any]:
    """First-order energy-participation black-box quantization."""
    frequencies = np.asarray([mode["frequency_hz"] for mode in modes], dtype=float)
    participation = np.asarray(junction_participations, dtype=float)
    ej = np.asarray(josephson_energies_j, dtype=float)
    if participation.shape != (len(modes), len(ej)):
        raise ValueError("Participation matrix must be modes x junctions")
    zero_point_phase_sq = participation * (PLANCK * frequencies[:, None]) / np.maximum(2.0 * ej[None, :], 1e-30)
    self_kerr = -np.sum(ej[None, :] * zero_point_phase_sq**2 / (2.0 * PLANCK), axis=1)
    cross_kerr = np.zeros((len(modes), len(modes)))
    for m in range(len(modes)):
        for n in range(len(modes)):
            cross_kerr[m, n] = -np.sum(ej * zero_point_phase_sq[m] * zero_point_phase_sq[n] / PLANCK)
    return {
        "schema": "text-to-gds.black-box-quantization.v1",
        "frequencies_hz": frequencies.tolist(),
        "zero_point_phase_squared": zero_point_phase_sq.tolist(),
        "self_kerr_hz": self_kerr.tolist(),
        "cross_kerr_hz": cross_kerr.tolist(),
    }


def multimode_coupling(capacitance_matrix_f: list[list[float]], frequencies_hz: list[float]) -> dict[str, Any]:
    matrix = np.asarray(capacitance_matrix_f, dtype=float)
    frequencies = np.asarray(frequencies_hz, dtype=float)
    if matrix.shape != (len(frequencies), len(frequencies)):
        raise ValueError("Capacitance matrix shape must match mode count")
    coupling = np.zeros_like(matrix)
    for i in range(len(frequencies)):
        for j in range(i + 1, len(frequencies)):
            normalized = abs(matrix[i, j]) / math.sqrt(max(matrix[i, i] * matrix[j, j], 1e-30))
            coupling[i, j] = coupling[j, i] = normalized * math.sqrt(frequencies[i] * frequencies[j]) / 2.0
    return {"coupling_hz": coupling.tolist(), "strongest_coupling_hz": float(np.max(coupling))}


def purcell_lifetime_s(*, qubit_frequency_hz: float, resonator_frequency_hz: float, coupling_hz: float, resonator_q: float) -> float:
    if min(qubit_frequency_hz, resonator_frequency_hz, coupling_hz, resonator_q) <= 0.0:
        raise ValueError("Purcell inputs must be positive")
    detuning = abs(qubit_frequency_hz - resonator_frequency_hz)
    kappa = 2.0 * math.pi * resonator_frequency_hz / resonator_q
    gamma = (coupling_hz / max(detuning, 1e-30)) ** 2 * kappa
    return 1.0 / gamma


def radiation_lifetime_s(*, frequency_hz: float, radiated_power_w: float, stored_energy_j: float) -> float:
    if frequency_hz <= 0.0 or stored_energy_j <= 0.0 or radiated_power_w < 0.0:
        raise ValueError("Invalid radiation loss inputs")
    return math.inf if radiated_power_w == 0.0 else stored_energy_j / radiated_power_w


def qubit_lifetime_prediction(loss_channels: dict[str, float]) -> dict[str, Any]:
    """Combine independent T1 channels using reciprocal-rate addition."""
    if not loss_channels or any(value <= 0.0 for value in loss_channels.values()):
        raise ValueError("Every lifetime channel must be positive")
    rates = {name: 1.0 / value for name, value in loss_channels.items()}
    total = 1.0 / sum(rates.values())
    return {"t1_s": total, "channels_s": loss_channels, "dominant_channel": max(rates, key=rates.get), "rates_hz": rates}
