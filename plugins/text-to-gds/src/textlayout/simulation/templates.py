"""Simulator-independent descriptions of the three supported circuit checks.

A template is *what to simulate*; each backend (JoSIM, PSCAN2, WRspice)
renders it into its own dialect. Templates never claim results — they carry
only inputs plus the analytical expectations the results are compared against.
"""

from __future__ import annotations

import math
from dataclasses import dataclass


def _require_positive(**values: float) -> None:
    for name, value in values.items():
        if not math.isfinite(value) or value <= 0:
            raise ValueError(f"{name} must be a positive finite number, got {value!r}")


@dataclass(frozen=True, slots=True)
class LCResonanceCheck:
    """Passive LC transient: layout-derived C, user/default L, pulse ringdown.

    ``capacitance_source`` states where C came from (FasterCap-extracted or
    analytical) — a circuit simulator can never upgrade that provenance.
    """

    capacitance_pf: float
    capacitance_source: str
    inductance_nh: float
    duration_ns: float = 50.0
    timestep_ps: float = 1.0
    drive_amplitude_ua: float = 1.0

    def __post_init__(self) -> None:
        _require_positive(
            capacitance_pf=self.capacitance_pf,
            inductance_nh=self.inductance_nh,
            duration_ns=self.duration_ns,
            timestep_ps=self.timestep_ps,
            drive_amplitude_ua=self.drive_amplitude_ua,
        )

    @property
    def analytical_resonance_ghz(self) -> float:
        return (
            1.0
            / (2.0 * math.pi * math.sqrt(self.inductance_nh * 1e-9 * self.capacitance_pf * 1e-12))
            / 1e9
        )


@dataclass(frozen=True, slots=True)
class JJTransientCheck:
    """JJ/SQUID-ready RCSJ transient sanity check (no gain claim, ever)."""

    critical_current_ua: float
    junction_capacitance_ff: float
    shunt_resistance_ohm: float | None = None
    loop_inductance_ph: float | None = None
    idc_capacitance_pf: float | None = None
    flux_bias_ua: float | None = None
    duration_ns: float = 50.0
    timestep_ps: float = 1.0

    def __post_init__(self) -> None:
        _require_positive(
            critical_current_ua=self.critical_current_ua,
            junction_capacitance_ff=self.junction_capacitance_ff,
            duration_ns=self.duration_ns,
            timestep_ps=self.timestep_ps,
        )


@dataclass(frozen=True, slots=True)
class PumpSignalExperiment:
    """Two-tone transient for parametric-gain extraction (arXiv:2402.12037).

    ``discard_ns`` is the initial window dropped before the FFT — it must
    cover the source ramp plus the wave-propagation time through the device.
    """

    pump_frequency_ghz: float
    pump_amplitude_ua: float
    signal_frequency_ghz: float
    signal_amplitude_ua: float
    duration_ns: float = 100.0
    timestep_ps: float = 1.0
    discard_ns: float = 20.0

    def __post_init__(self) -> None:
        _require_positive(
            pump_frequency_ghz=self.pump_frequency_ghz,
            pump_amplitude_ua=self.pump_amplitude_ua,
            signal_frequency_ghz=self.signal_frequency_ghz,
            signal_amplitude_ua=self.signal_amplitude_ua,
            duration_ns=self.duration_ns,
            timestep_ps=self.timestep_ps,
        )
        if self.discard_ns < 0 or self.discard_ns >= self.duration_ns:
            raise ValueError("discard_ns must be >= 0 and smaller than duration_ns")

    @property
    def idler_frequency_ghz(self) -> float:
        """Four-wave-mixing idler ``f_i = 2*f_p - f_s``."""
        return 2.0 * self.pump_frequency_ghz - self.signal_frequency_ghz
