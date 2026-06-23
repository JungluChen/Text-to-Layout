"""Physical constants and unit helpers for superconducting circuit EDA.

All constants are 2019 SI exact definitions or 2018 CODATA recommended values.
Never override these with local approximations.

source="LLM" anywhere in this module is a hard error — constants must trace to
NIST CODATA or derived exactly.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

# ─── Fundamental constants — exact (2019 SI redefinition) ─────────────────────
SPEED_OF_LIGHT: float = 2.99792458e8          # m/s
PLANCK_H: float = 6.62607015e-34              # J·s
PLANCK_HBAR: float = PLANCK_H / (2.0 * math.pi)
ELECTRON_CHARGE: float = 1.602176634e-19      # C
BOLTZMANN: float = 1.380649e-23               # J/K

# ─── Derived electromagnetic constants ────────────────────────────────────────
EPSILON_0: float = 8.8541878128e-12           # F/m  (2018 CODATA)
MU_0: float = 1.25663706212e-6                # H/m  (2018 CODATA)

# ─── Josephson / superconducting constants ─────────────────────────────────────
FLUX_QUANTUM: float = PLANCK_H / (2.0 * ELECTRON_CHARGE)    # Wb = 2.067833848e-15
REDUCED_FLUX_QUANTUM: float = FLUX_QUANTUM / (2.0 * math.pi)  # Wb/rad
JOSEPHSON_CONSTANT: float = 2.0 * ELECTRON_CHARGE / PLANCK_H  # Hz/V ≈ 483.6 THz/mV
COOPER_PAIR_CHARGE: float = 2.0 * ELECTRON_CHARGE            # C

# ─── Unit conversions ─────────────────────────────────────────────────────────

def ghz_to_hz(f: float) -> float:
    return f * 1e9

def hz_to_ghz(f: float) -> float:
    return f * 1e-9

def um_to_m(x: float) -> float:
    return x * 1e-6

def m_to_um(x: float) -> float:
    return x * 1e6

def nm_to_m(x: float) -> float:
    return x * 1e-9

def pf_to_f(c: float) -> float:
    return c * 1e-12

def f_to_pf(c: float) -> float:
    return c * 1e12

def ff_to_f(c: float) -> float:
    return c * 1e-15

def f_to_ff(c: float) -> float:
    return c * 1e15

def ph_to_h(l: float) -> float:
    return l * 1e-12

def h_to_ph(l: float) -> float:
    return l * 1e12

def nh_to_h(l: float) -> float:
    return l * 1e-9

def dbm_to_watts(p_dbm: float) -> float:
    return 1e-3 * 10.0 ** (p_dbm / 10.0)

def watts_to_dbm(p_w: float) -> float:
    if p_w <= 0:
        raise ValueError(f"Power must be positive, got {p_w}")
    return 10.0 * math.log10(p_w * 1e3)

def linear_to_db(x: float) -> float:
    if x <= 0:
        raise ValueError(f"Amplitude must be positive, got {x}")
    return 20.0 * math.log10(x)

def db_to_linear(x_db: float) -> float:
    return 10.0 ** (x_db / 20.0)

def power_db_to_linear(x_db: float) -> float:
    return 10.0 ** (x_db / 10.0)


@dataclass(frozen=True)
class Quantity:
    """A physical quantity with value, unit, and source traceability.

    Raises ValueError if source is an LLM guess or confidence is out of range.
    """
    value: float
    unit: str
    source: str
    confidence: float = 1.0
    method: str = "extracted"

    def __post_init__(self) -> None:
        if not math.isfinite(self.value):
            raise ValueError(f"Quantity value must be finite, got {self.value}")
        if not (0.0 <= self.confidence <= 1.0):
            raise ValueError(f"Confidence must be in [0, 1], got {self.confidence}")
        _FORBIDDEN_SOURCES = {"LLM", "llm", "guess", "estimated_by_llm", ""}
        if self.source in _FORBIDDEN_SOURCES:
            raise ValueError(
                f"source='{self.source}' is forbidden — LLM guesses are not physics"
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "value": self.value,
            "unit": self.unit,
            "source": self.source,
            "confidence": self.confidence,
            "method": self.method,
        }

    def __mul__(self, factor: float) -> "Quantity":
        return Quantity(
            value=self.value * factor,
            unit=self.unit,
            source=self.source,
            confidence=self.confidence,
            method=self.method,
        )
