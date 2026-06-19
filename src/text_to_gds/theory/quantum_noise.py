from __future__ import annotations

PLANCK_J_S = 6.62607015e-34
BOLTZMANN_J_K = 1.380649e-23


def quantum_limited_noise_temperature(frequency_hz: float) -> float:
    """Phase-preserving half-photon quantum noise temperature hf/(2 kB)."""
    if frequency_hz <= 0.0:
        raise ValueError("frequency_hz must be positive")
    return PLANCK_J_S * frequency_hz / (2.0 * BOLTZMANN_J_K)


def added_noise_photons(noise_temperature_k: float, frequency_hz: float) -> float:
    if noise_temperature_k < 0.0:
        raise ValueError("noise_temperature_k must be non-negative")
    return BOLTZMANN_J_K * noise_temperature_k / (PLANCK_J_S * frequency_hz)
