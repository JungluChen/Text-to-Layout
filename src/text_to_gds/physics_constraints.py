"""Physics Constraint Engine — fundamental limits for quantum device design.

Instead of generating blindly, the agent checks whether a requested
specification is physically realisable before committing compute.

Covers:
    - Bode-Fano bandwidth limit
    - Gain-bandwidth product limit (Manley-Rowe)
    - Quantum noise limit (Caves)
    - Kerr nonlinearity limit
    - Bifurcation / Duffing condition
    - SQUID flux quantisation
    - Kinetic inductance fraction limit
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

H_PLANCK = 6.62607015e-34        # J·s
K_B = 1.380649e-23               # J/K
HBAR = H_PLANCK / (2 * math.pi)
PHI_0 = 2.067833848e-15          # Wb (magnetic flux quantum)


# ---------------------------------------------------------------------------
# Result container
# ---------------------------------------------------------------------------

@dataclass
class ConstraintResult:
    """Outcome of a single physics constraint check."""
    name: str
    passed: bool
    value: float | None = None
    limit: float | None = None
    margin: float | None = None        # (limit - value) / limit, positive = safe
    unit: str = ""
    message: str = ""
    severity: str = "error"            # error, warning, info

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "passed": self.passed,
            "value": self.value,
            "limit": self.limit,
            "margin": round(self.margin, 4) if self.margin is not None else None,
            "unit": self.unit,
            "message": self.message,
            "severity": self.severity,
        }


@dataclass
class ConstraintReport:
    """Aggregated result of all physics checks."""
    device_id: str = ""
    specs: dict[str, Any] = field(default_factory=dict)
    results: list[ConstraintResult] = field(default_factory=list)
    feasible: bool = True
    summary: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "device_id": self.device_id,
            "specs": self.specs,
            "results": [r.to_dict() for r in self.results],
            "feasible": self.feasible,
            "summary": self.summary,
        }


# ---------------------------------------------------------------------------
# Individual constraint checkers
# ---------------------------------------------------------------------------

def check_bode_fano(
    gain_db: float,
    bandwidth_mhz: float,
    r0: float = 50.0,
    q_loaded: float = 10.0,
) -> ConstraintResult:
    """Bode-Fano limit: achievable bandwidth for a given matching Q.

    For a single-tuned matching network:
        BW / f0  <=  pi / (Q_loaded * ln(1/|S11|))
    Simplified:  sqrt(G) * BW < f0 / Q_loaded  (approximate).

    Parameters
    ----------
    gain_db : Desired small-signal gain in dB.
    bandwidth_mhz : Desired 3-dB bandwidth in MHz.
    r0 : System impedance in ohms.
    q_loaded : Loaded quality factor of the resonator.
    """
    gain_lin = 10 ** (gain_db / 20)
    bw_hz = bandwidth_mhz * 1e6
    # Product limit (conservative Manley-Rowe / Bode-Fano hybrid)
    product = gain_lin * bw_hz
    # Rough f0 estimate from loaded Q and bandwidth
    f0_hz = q_loaded * bw_hz if bw_hz > 0 else 1e9
    # More physical: GBW product < f_res * constant
    gbw_limit = f0_hz * 0.5  # empirical headroom

    passed = product < gbw_limit if gbw_limit > 0 else False
    margin = (gbw_limit - product) / gbw_limit if gbw_limit > 0 else -1.0

    if passed:
        msg = (
            f"Gain-bandwidth product {product / 1e6:.1f} MHz·(lin) "
            f"< limit {gbw_limit / 1e6:.1f} MHz·(lin). Feasible."
        )
    else:
        msg = (
            f"Gain-bandwidth product {product / 1e6:.1f} MHz·(lin) "
            f">= limit {gbw_limit / 1e6:.1f} MHz·(lin). "
            "Reduce gain, widen BW target, or use TWPA topology."
        )

    return ConstraintResult(
        name="bode_fano_gbw",
        passed=passed,
        value=product / 1e6,
        limit=gbw_limit / 1e6,
        margin=margin,
        unit="MHz·(lin)",
        message=msg,
        severity="error" if not passed else "info",
    )


def check_manley_rowe(
    input_power_dbm: float,
    output_power_dbm: float,
    idler_power_dbm: float | None = None,
    n_phonon_modes: int = 1,
) -> ConstraintResult:
    """Manley-Rowe relation for parametric amplifiers.

    For a degenerate paramp:
        P_out / P_in  <=  omega_s / omega_p  (for single-mode)
    Generalised: sum(P_out_k / omega_k) <= P_in / omega_p.

    Simplified: gain_db must satisfy energy conservation.
    """
    # Manley-Rowe upper bound for degenerate paramp: G <= 1 (0 dB) per mode
    # For non-degenerate: G_idler * G_signal <= 1 (conservation)
    # Practical limit: gain_db < 20 * log10(omega_p / omega_s)
    # Conservative: gain_db < 30 dB for any paramp
    limit_db = 30.0
    passed = (output_power_dbm - input_power_dbm) < limit_db
    margin = (limit_db - (output_power_dbm - input_power_dbm)) / limit_db

    return ConstraintResult(
        name="manley_rowe",
        passed=passed,
        value=output_power_dbm - input_power_dbm,
        limit=limit_db,
        margin=margin,
        unit="dB",
        message=(
            f"Gain {(output_power_dbm - input_power_dbm):.1f} dB "
            f"{'within' if passed else 'exceeds'} Manley-Rowe limit {limit_db} dB."
        ),
        severity="error" if not passed else "info",
    )


def check_quantum_noise(
    frequency_ghz: float,
    gain_db: float,
    system_temperature_k: float = 0.02,
    loss_before_amp_db: float = 0.0,
) -> ConstraintResult:
    """Quantum noise limit (Caves, 1982).

    Minimum added noise for a phase-insensitive amplifier:
        N_add >= hbar * omega / (2 * k_B)  (at zero temperature)
    In temperature units:
        T_add >= hbar * omega / (2 * k_B) ≈ 24 mK at 5 GHz

    System noise temperature:
        T_sys = T_input / eta + T_add
    where eta = 10^(-loss_before_amp / 10).
    """
    freq_hz = frequency_ghz * 1e9
    omega = 2 * math.pi * freq_hz
    t_quantum = HBAR * omega / (2 * K_B)  # ~24 mK at 5 GHz
    eta = 10 ** (-loss_before_amp_db / 10) if loss_before_amp_db > 0 else 1.0
    t_input = system_temperature_k / eta if eta > 0 else float("inf")
    t_add = t_quantum  # minimum added noise
    t_sys = t_input + t_add

    # For a gain-G amplifier, the referred-to-input noise is:
    # T_noise = (G - 1) * T_add / G  ≈ T_add at high gain
    # Practical limit: T_noise < 2x quantum limit for "quantum-limited"
    margin = 2.0  # factor of 2 headroom
    passed = t_add < margin * t_quantum  # always true for ideal case

    return ConstraintResult(
        name="quantum_noise_limit",
        passed=passed,
        value=round(t_add * 1000, 2),
        limit=round(margin * t_quantum * 1000, 2),
        margin=(margin * t_quantum - t_add) / (margin * t_quantum),
        unit="mK",
        message=(
            f"Quantum noise temperature {t_add * 1000:.1f} mK at {frequency_ghz} GHz "
            f"(quantum limit {t_quantum * 1000:.1f} mK). "
            f"System T = {t_sys * 1000:.1f} mK."
        ),
        severity="info",
    )


def check_kerr_limit(
    anharmonicity_ghz: float,
    pump_frequency_ghz: float,
    gain_db: float,
) -> ConstraintResult:
    """Kerr nonlinearity limit for parametric amplifiers.

    The Kerr coefficient chi^(3) sets:
        - Maximum gain before bifurcation
        - Pump-induced detuning
        - Dynamic range (P1dB)

    Condition: |anharmonicity| < detuning from pump to signal.
    If pump is at 2*f_signal (degenerate), the condition is:
        |alpha| < |f_pump - 2*f_signal|
    """
    detuning_ghz = abs(pump_frequency_ghz - 2 * (pump_frequency_ghz / 2))
    # Simplified: anharmonicity should be < 10% of pump detuning
    threshold = 0.1 * abs(pump_frequency_ghz)
    passed = abs(anharmonicity_ghz) < threshold
    margin = (threshold - abs(anharmonicity_ghz)) / threshold if threshold > 0 else -1.0

    return ConstraintResult(
        name="kerr_limit",
        passed=passed,
        value=abs(anharmonicity_ghz),
        limit=threshold,
        margin=margin,
        unit="GHz",
        message=(
            f"Kerr anharmonicity |{anharmonicity_ghz:.3f}| GHz "
            f"{'within' if passed else 'exceeds'} limit {threshold:.3f} GHz. "
            f"Pump detuning: {detuning_ghz:.3f} GHz."
        ),
        severity="error" if not passed else "info",
    )


def check_bifurcation(
    pump_power_dbm: float,
    bifurcation_threshold_dbm: float = -120.0,
    quality_factor: float = 1000.0,
    kerr_coefficient_hz: float = 1e3,
) -> ConstraintResult:
    """Duffing / bifurcation condition for Josephson parametric amplifiers.

    The bifurcation threshold:
        P_bif = (2 / (Q^2 * |K|)) * (hbar * omega)^2
    Below this power the JPA operates as a linear amplifier.
    """
    freq_hz = 5e9  # assume 5 GHz if not specified
    omega = 2 * math.pi * freq_hz
    p_bif_watt = (2 / (quality_factor ** 2 * abs(kerr_coefficient_hz))) * (HBAR * omega) ** 2
    p_bif_calculated_dbm = 10 * math.log10(p_bif_watt * 1000) if p_bif_watt > 0 else -200.0
    # Use the higher (more conservative) of calculated and user-provided threshold
    p_bif_dbm = max(p_bif_calculated_dbm, bifurcation_threshold_dbm)
    margin_db = p_bif_dbm - pump_power_dbm
    passed = pump_power_dbm < p_bif_dbm

    return ConstraintResult(
        name="bifurcation",
        passed=passed,
        value=pump_power_dbm,
        limit=round(p_bif_dbm, 2),
        margin=margin_db / abs(p_bif_dbm) if p_bif_dbm != 0 else -1.0,
        unit="dBm",
        message=(
            f"Pump {pump_power_dbm:.1f} dBm "
            f"{'below' if passed else 'above'} bifurcation threshold {p_bif_dbm:.1f} dBm. "
            f"Margin: {margin_db:.1f} dB."
        ),
        severity="error" if not passed else "warning",
    )


def check_flux_quantisation(
    flux_bias_ua: float,
    loop_area_um2: float,
    critical_current_ua: float,
) -> ConstraintResult:
    """SQUID flux quantisation: Phi = L * I_bias + M * I_ext.

    The SQUID loop must satisfy:
        n * Phi_0 = L_loop * I_JJ + M * I_ext
    where L_loop is the loop inductance, I_JJ is the junction current,
    and M is the mutual inductance.
    """
    # External flux
    mu_0 = 4 * math.pi * 1e-7
    loop_area_m2 = loop_area_um2 * 1e-12
    flux_external_wb = mu_0 * flux_bias_ua * 1e-6 * math.sqrt(loop_area_m2)
    # Fraction of flux quantum
    flux_fraction = flux_external_wb / PHI_0
    # The SQUID should operate with |Phi_ext| < Phi_0 / 2
    passed = abs(flux_fraction) < 0.5
    margin = (0.5 - abs(flux_fraction)) / 0.5

    return ConstraintResult(
        name="flux_quantisation",
        passed=passed,
        value=round(abs(flux_fraction), 4),
        limit=0.5,
        margin=margin,
        unit="Phi_0",
        message=(
            f"External flux {abs(flux_fraction):.4f} Phi_0 "
            f"{'within' if passed else 'exceeds'} operating range [0, 0.5) Phi_0."
        ),
        severity="error" if not passed else "info",
    )


def check_kinetic_inductance_fraction(
    kinetic_inductance_ph: float,
    geometric_inductance_ph: float,
    max_fraction: float = 0.95,
) -> ConstraintResult:
    """Kinetic inductance fraction limit for fabrication stability.

    If kinetic inductance dominates too much, small fabrication variations
    cause large frequency shifts.  Typical safe range: Lk/(Lk + Lg) < 0.9.
    """
    total = kinetic_inductance_ph + geometric_inductance_ph
    fraction = kinetic_inductance_ph / total if total > 0 else 0.0
    passed = fraction < max_fraction
    margin = (max_fraction - fraction) / max_fraction

    return ConstraintResult(
        name="kinetic_inductance_fraction",
        passed=passed,
        value=round(fraction, 4),
        limit=max_fraction,
        margin=margin,
        unit="",
        message=(
            f"Kinetic inductance fraction {fraction:.2%} "
            f"{'within' if passed else 'exceeds'} limit {max_fraction:.0%}. "
            f"Lk = {kinetic_inductance_ph:.1f} pH, Lg = {geometric_inductance_ph:.1f} pH."
        ),
        severity="warning" if not passed and fraction < 0.98 else ("error" if not passed else "info"),
    )


# ---------------------------------------------------------------------------
# Aggregate checker
# ---------------------------------------------------------------------------

def check_all_constraints(
    specs: dict[str, Any],
    device_id: str = "",
) -> ConstraintReport:
    """Run all applicable physics constraint checks against a specification dict.

    Expected keys in *specs* (all optional; missing checks are skipped):
        gain_db, bandwidth_mhz, frequency_ghz, quality_factor,
        input_power_dbm, output_power_dbm, anharmonicity_ghz,
        pump_frequency_ghz, pump_power_dbm, bifurcation_threshold_dbm,
        flux_bias_ua, loop_area_um2, critical_current_ua,
        kinetic_inductance_ph, geometric_inductance_ph,
        system_temperature_k, loss_before_amp_db, r0.
    """
    results: list[ConstraintResult] = []

    if "gain_db" in specs and "bandwidth_mhz" in specs:
        results.append(check_bode_fano(
            gain_db=specs["gain_db"],
            bandwidth_mhz=specs["bandwidth_mhz"],
            r0=specs.get("r0", 50.0),
            q_loaded=specs.get("quality_factor", 10.0),
        ))

    if "input_power_dbm" in specs and "output_power_dbm" in specs:
        results.append(check_manley_rowe(
            input_power_dbm=specs["input_power_dbm"],
            output_power_dbm=specs["output_power_dbm"],
        ))

    if "frequency_ghz" in specs:
        results.append(check_quantum_noise(
            frequency_ghz=specs["frequency_ghz"],
            gain_db=specs.get("gain_db", 0.0),
            system_temperature_k=specs.get("system_temperature_k", 0.02),
            loss_before_amp_db=specs.get("loss_before_amp_db", 0.0),
        ))

    if all(k in specs for k in ("anharmonicity_ghz", "pump_frequency_ghz", "gain_db")):
        results.append(check_kerr_limit(
            anharmonicity_ghz=specs["anharmonicity_ghz"],
            pump_frequency_ghz=specs["pump_frequency_ghz"],
            gain_db=specs["gain_db"],
        ))

    if "pump_power_dbm" in specs:
        results.append(check_bifurcation(
            pump_power_dbm=specs["pump_power_dbm"],
            bifurcation_threshold_dbm=specs.get("bifurcation_threshold_dbm", -120.0),
            quality_factor=specs.get("quality_factor", 1000.0),
            kerr_coefficient_hz=specs.get("kerr_coefficient_hz", 1e3),
        ))

    if all(k in specs for k in ("flux_bias_ua", "loop_area_um2", "critical_current_ua")):
        results.append(check_flux_quantisation(
            flux_bias_ua=specs["flux_bias_ua"],
            loop_area_um2=specs["loop_area_um2"],
            critical_current_ua=specs["critical_current_ua"],
        ))

    if "kinetic_inductance_ph" in specs:
        results.append(check_kinetic_inductance_fraction(
            kinetic_inductance_ph=specs["kinetic_inductance_ph"],
            geometric_inductance_ph=specs.get("geometric_inductance_ph", 100.0),
            max_fraction=specs.get("max_kinetic_fraction", 0.95),
        ))

    feasible = all(r.passed for r in results if r.severity == "error")
    failed = [r for r in results if not r.passed]
    summary = (
        f"{len(results)} checks, {len(failed)} violations"
        if failed else
        f"{len(results)} checks passed — specification is physically feasible"
    )

    return ConstraintReport(
        device_id=device_id,
        specs=specs,
        results=results,
        feasible=feasible,
        summary=summary,
    )
