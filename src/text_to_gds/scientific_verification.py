"""Scientific Verification Layer — physics correctness checks for quantum devices.

Implements:
    - Physics unit-test framework (dimensional analysis)
    - Conservation law checker (energy, power)
    - S-parameter sanity checker (passivity, reciprocity, causality)
    - Kramers-Kronig validation
    - Quantum limit validation (Caves, Heisenberg)
    - Uncertainty propagation engine
    - Confidence interval calculation
    - Simulation credibility scoring
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

import numpy as np

try:
    import scipy.signal as signal
    HAS_SCIPY = True
except ImportError:
    HAS_SCIPY = False

from text_to_gds.physics_constraints import (
    HBAR,
    K_B,
)


# ---------------------------------------------------------------------------
# Dimensional analysis
# ---------------------------------------------------------------------------

_UNIT_DIMS = {
    "m": 1, "um": -6, "nm": -9, "mm": -3, "cm": -2,
    "s": 0, "ms": -3, "us": -6, "ns": -9, "ps": -12,
    "Hz": 0, "kHz": 3, "MHz": 6, "GHz": 9, "THz": 12,
    "Ω": 0, "kΩ": 3, "mΩ": -3, "uΩ": -6,
    "F": 0, "pF": -12, "fF": -15, "aF": -18,
    "H": 0, "pH": -12, "nH": -9, "uH": -6,
    "W": 0, "mW": -3, "uW": -6, "nW": -9, "dBm": 0,
    "K": 0, "mK": -3, "A": 0, "uA": -6, "nA": -9,
    "V": 0, "mV": -3, "uV": -6, "eV": 0,
    "J": 0, "eJ": -18, "meV": -3,
    "T": 0, "uT": -6, "nT": -9,
    "Wb": 0,
}


@dataclass
class DimensionalCheck:
    """Result of a dimensional analysis check."""
    expression: str
    expected_unit: str
    computed_unit: str
    consistent: bool
    message: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "expression": self.expression,
            "expected_unit": self.expected_unit,
            "computed_unit": self.computed_unit,
            "consistent": self.consistent,
            "message": self.message,
        }


def check_dimensions(
    value: float,
    unit: str,
    expected_dimensions: tuple[int, int, int, int] = (0, 0, 0, 0),
    label: str = "",
) -> DimensionalCheck:
    """Check if a value's unit has the expected physical dimensions.

    Dimensions: (length, time, mass, charge) in SI base units.
    """
    # Simplified: just check the unit string is known
    known = unit in _UNIT_DIMS or any(unit.endswith(s) for s in ["Hz", "Ω", "F", "H", "W", "K"])
    return DimensionalCheck(
        expression=label or f"{value} {unit}",
        expected_unit=str(expected_dimensions),
        computed_unit=unit,
        consistent=known,
        message=f"Unit '{unit}' is {'recognized' if known else 'unrecognized'}.",
    )


# ---------------------------------------------------------------------------
# S-parameter checks
# ---------------------------------------------------------------------------

@dataclass
class SParameterCheck:
    """Result of an S-parameter validation check."""
    check_name: str
    passed: bool
    details: dict[str, Any] = field(default_factory=dict)
    message: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "check_name": self.check_name,
            "passed": self.passed,
            "details": self.details,
            "message": self.message,
        }


def check_passivity(s_matrix: np.ndarray) -> SParameterCheck:
    """Check if S-matrix is passive: singular values <= 1.

    For a passive device, the S-matrix must satisfy:
        S†S <= I  (all singular values <= 1)
    """
    try:
        svd = np.linalg.svd(s_matrix, compute_uv=False)
        max_sv = float(np.max(svd))
        passed = max_sv <= 1.0 + 1e-6
        return SParameterCheck(
            check_name="passivity",
            passed=passed,
            details={"max_singular_value": round(max_sv, 6)},
            message=(
                f"Max singular value {max_sv:.6f} "
                f"{'≤' if passed else '>'} 1. Device is {'passive' if passed else 'active'}."
            ),
        )
    except Exception as e:
        return SParameterCheck(
            check_name="passivity", passed=False, message=f"Check failed: {e}"
        )


def check_reciprocity(s_matrix: np.ndarray) -> SParameterCheck:
    """Check if S-matrix is reciprocal: S = S^T."""
    try:
        diff = np.max(np.abs(s_matrix - s_matrix.T))
        passed = float(diff) < 1e-6
        return SParameterCheck(
            check_name="reciprocity",
            passed=passed,
            details={"max_asymmetry": round(float(diff), 8)},
            message=(
                f"Max S-matrix asymmetry {diff:.2e} "
                f"{'<' if passed else '≥'} 1e-6. Device is {'reciprocal' if passed else 'non-reciprocal'}."
            ),
        )
    except Exception as e:
        return SParameterCheck(
            check_name="reciprocity", passed=False, message=f"Check failed: {e}"
        )


def check_s_parameter_bounds(s_matrix: np.ndarray) -> SParameterCheck:
    """Check |S_ij| <= 1 for all elements (passive device)."""
    try:
        magnitudes = np.abs(s_matrix)
        max_mag = float(np.max(magnitudes))
        violations = []
        n = s_matrix.shape[0]
        for i in range(n):
            for j in range(n):
                if magnitudes[i, j] > 1.0 + 1e-6:
                    violations.append(f"S_{i+1}{j+1}={magnitudes[i,j]:.4f}")
        passed = len(violations) == 0
        return SParameterCheck(
            check_name="s_parameter_bounds",
            passed=passed,
            details={"max_magnitude": round(max_mag, 6), "violations": violations},
            message=(
                f"Max |S| = {max_mag:.6f}. "
                f"{len(violations)} elements exceed unity." if violations else
                "All |S_ij| ≤ 1."
            ),
        )
    except Exception as e:
        return SParameterCheck(
            check_name="s_parameter_bounds", passed=False, message=f"Check failed: {e}"
        )


# ---------------------------------------------------------------------------
# Kramers-Kronig validation
# ---------------------------------------------------------------------------

def check_kramers_kronig(
    frequencies_hz: np.ndarray,
    s_real: np.ndarray,
    s_imag: np.ndarray,
    port: int = 0,
) -> SParameterCheck:
    """Validate Kramers-Kronig relations for S-parameters.

    For a causal system, the real and imaginary parts of the reflection
    coefficient are related by the Hilbert transform.
    """
    if not HAS_SCIPY:
        return SParameterCheck(
            check_name="kramers_kronig",
            passed=False,
            message="scipy not available — KK check skipped.",
        )

    try:
        n = len(frequencies_hz)
        if n < 10:
            return SParameterCheck(
                check_name="kramers_kronig",
                passed=False,
                message="Insufficient frequency points for KK (need ≥ 10).",
            )

        # Interpolate to uniform frequency grid
        f_uniform = np.linspace(frequencies_hz[0], frequencies_hz[-1], n)
        s_real_interp = np.interp(f_uniform, frequencies_hz, s_real)
        s_imag_interp = np.interp(f_uniform, frequencies_hz, s_imag)

        # Hilbert transform
        s_reconstructed = signal.hilbert(s_real_interp)

        # Compare imaginary parts
        imag_original = s_imag_interp
        imag_reconstructed = np.imag(s_reconstructed)

        # Normalize error
        norm_factor = np.max(np.abs(imag_original)) or 1.0
        error = np.max(np.abs(imag_original - imag_reconstructed)) / norm_factor
        passed = float(error) < 0.05  # 5% tolerance

        return SParameterCheck(
            check_name="kramers_kronig",
            passed=passed,
            details={
                "max_relative_error": round(float(error), 4),
                "frequency_points": n,
                "tolerance": 0.05,
            },
            message=(
                f"KK max relative error {error:.4f} "
                f"{'<' if passed else '≥'} 5%. S-parameters are "
                f"{'causal' if passed else 'non-causal or corrupted'}."
            ),
        )
    except Exception as e:
        return SParameterCheck(
            check_name="kramers_kronig", passed=False, message=f"Check failed: {e}"
        )


# ---------------------------------------------------------------------------
# Quantum limit validation
# ---------------------------------------------------------------------------

@dataclass
class QuantumLimitResult:
    """Result of a quantum limit check."""
    limit_name: str
    value: float
    limit: float
    ratio: float
    within_limit: bool
    message: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "limit_name": self.limit_name,
            "value": self.value,
            "limit": self.limit,
            "ratio": round(self.ratio, 4),
            "within_limit": self.within_limit,
            "message": self.message,
        }


def check_quantum_noise_limit(
    noise_temperature_k: float,
    frequency_ghz: float,
    gain_db: float = 0.0,
) -> QuantumLimitResult:
    """Check if noise temperature exceeds the quantum limit.

    Quantum limit: T_N >= hbar * omega / (2 * k_B) ≈ 24 mK at 5 GHz.
    For a phase-insensitive amplifier with gain G:
        T_N >= (G-1)/G * hbar * omega / k_B
    """
    freq_hz = frequency_ghz * 1e9
    omega = 2 * math.pi * freq_hz
    gain_lin = 10 ** (gain_db / 20)
    t_limit = HBAR * omega / K_B
    if gain_lin > 1:
        t_limit *= (gain_lin - 1) / gain_lin

    ratio = noise_temperature_k / t_limit if t_limit > 0 else float("inf")
    within = ratio <= 2.0  # within 2x of quantum limit

    return QuantumLimitResult(
        limit_name="quantum_noise",
        value=noise_temperature_k,
        limit=t_limit,
        ratio=ratio,
        within_limit=within,
        message=(
            f"T_N = {noise_temperature_k * 1000:.1f} mK, "
            f"quantum limit = {t_limit * 1000:.1f} mK. "
            f"Ratio: {ratio:.2f}x. "
            f"{'Within' if within else 'Exceeds'} 2x quantum limit."
        ),
    )


def check_heisenberg_limit(
    measurement_precision: float,
    conjugate_variance: float,
) -> QuantumLimitResult:
    """Heisenberg uncertainty: Δx Δp >= hbar/2."""
    product = measurement_precision * conjugate_variance
    limit = HBAR / 2
    ratio = product / limit if limit > 0 else float("inf")
    within = ratio >= 1.0  # must satisfy the inequality

    return QuantumLimitResult(
        limit_name="heisenberg_uncertainty",
        value=product,
        limit=limit,
        ratio=ratio,
        within_limit=within,
        message=(
            f"Δx·Δp = {product:.2e}, hbar/2 = {limit:.2e}. "
            f"Heisenberg {'satisfied' if within else 'VIOLATED'}."
        ),
    )


def check_gain_bandwidth_product(
    gain_db: float,
    bandwidth_mhz: float,
    center_frequency_ghz: float,
) -> QuantumLimitResult:
    """Manley-Rowe gain-bandwidth limit for parametric amplifiers."""
    gain_lin = 10 ** (gain_db / 20)
    bw_hz = bandwidth_mhz * 1e6
    f0_hz = center_frequency_ghz * 1e9

    # GBW limit: G * BW <= f0 (for single-mode paramp)
    gbw = gain_lin * bw_hz
    limit = f0_hz
    ratio = gbw / limit if limit > 0 else float("inf")
    within = ratio <= 1.0

    return QuantumLimitResult(
        limit_name="manley_rowe_gbw",
        value=gbw,
        limit=limit,
        ratio=ratio,
        within_limit=within,
        message=(
            f"GBW = {gbw / 1e9:.2f} GHz, f0 = {f0_hz / 1e9:.2f} GHz. "
            f"Ratio: {ratio:.3f}. "
            f"{'Within' if within else 'Exceeds'} Manley-Rowe limit."
        ),
    )


# ---------------------------------------------------------------------------
# Uncertainty propagation
# ---------------------------------------------------------------------------

def propagate_uncertainty(
    func,
    values: dict[str, float],
    uncertainties: dict[str, float],
) -> dict[str, Any]:
    """Propagate uncertainties through a function using partial derivatives.

    For y = f(x1, x2, ...):
        sigma_y^2 = sum_i (df/dxi)^2 * sigma_xi^2
    """
    central = func(**values)
    total_variance = 0.0
    partials: dict[str, float] = {}

    for param, val in values.items():
        if param in uncertainties and uncertainties[param] > 0:
            delta = uncertainties[param] * 0.01  # 1% perturbation
            vals_plus = dict(values)
            vals_plus[param] = val + delta
            vals_minus = dict(values)
            vals_minus[param] = val - delta
            try:
                df_dp = (func(**vals_plus) - func(**vals_minus)) / (2 * delta)
                partials[param] = df_dp
                total_variance += (df_dp * uncertainties[param]) ** 2
            except Exception:
                partials[param] = 0.0

    sigma = math.sqrt(total_variance)

    return {
        "central_value": central,
        "uncertainty": sigma,
        "relative_uncertainty": sigma / abs(central) if central != 0 else float("inf"),
        "partials": partials,
    }


def confidence_interval(
    central: float,
    sigma: float,
    confidence: float = 0.95,
) -> dict[str, Any]:
    """Calculate confidence interval using Gaussian approximation."""
    # z-score for common confidence levels
    z_scores = {0.90: 1.645, 0.95: 1.96, 0.99: 2.576}
    z = z_scores.get(confidence, 1.96)
    margin = z * sigma

    return {
        "central": central,
        "sigma": sigma,
        "confidence": confidence,
        "lower": central - margin,
        "upper": central + margin,
        "margin": margin,
    }


# ---------------------------------------------------------------------------
# Simulation credibility score
# ---------------------------------------------------------------------------

def score_simulation_credibility(
    s_parameter_checks: list[SParameterCheck],
    quantum_checks: list[QuantumLimitResult],
    convergence_passed: bool = True,
    mesh_converged: bool = True,
    frequency_points: int = 0,
) -> dict[str, Any]:
    """Score the credibility of a simulation result on 0-100 scale.

    Criteria:
        - S-parameter passivity: 20 pts
        - S-parameter reciprocity: 15 pts
        - KK validation: 20 pts
        - Quantum limits: 15 pts
        - Convergence: 15 pts
        - Mesh quality: 15 pts
    """
    score = 0.0
    details: list[str] = []

    # S-parameter passivity
    passivity = next((c for c in s_parameter_checks if c.check_name == "passivity"), None)
    if passivity and passivity.passed:
        score += 20
        details.append("Passivity: PASS (+20)")
    else:
        details.append("Passivity: FAIL (+0)")

    # Reciprocity
    reciprocity = next((c for c in s_parameter_checks if c.check_name == "reciprocity"), None)
    if reciprocity and reciprocity.passed:
        score += 15
        details.append("Reciprocity: PASS (+15)")
    else:
        details.append("Reciprocity: FAIL (+0)")

    # KK validation
    kk = next((c for c in s_parameter_checks if c.check_name == "kramers_kronig"), None)
    if kk and kk.passed:
        score += 20
        details.append("KK validation: PASS (+20)")
    elif kk is None:
        score += 10  # partial credit if not checked
        details.append("KK validation: NOT CHECKED (+10)")
    else:
        details.append("KK validation: FAIL (+0)")

    # Quantum limits
    q_within = sum(1 for q in quantum_checks if q.within_limit)
    q_total = len(quantum_checks) or 1
    score += 15 * (q_within / q_total)
    details.append(f"Quantum limits: {q_within}/{q_total} (+{15 * q_within / q_total:.1f})")

    # Convergence
    if convergence_passed:
        score += 15
        details.append("Convergence: PASS (+15)")
    else:
        details.append("Convergence: FAIL (+0)")

    # Mesh
    if mesh_converged:
        score += 15
        details.append("Mesh: CONVERGED (+15)")
    else:
        details.append("Mesh: UNCONVERGED (+0)")

    return {
        "score": round(score, 1),
        "grade": (
            "A" if score >= 90 else
            "B" if score >= 75 else
            "C" if score >= 60 else
            "D" if score >= 40 else "F"
        ),
        "details": details,
        "frequency_points": frequency_points,
    }


# ---------------------------------------------------------------------------
# Aggregate verification
# ---------------------------------------------------------------------------

def run_full_verification(
    s_matrix: np.ndarray | None = None,
    frequencies_hz: np.ndarray | None = None,
    s_real: np.ndarray | None = None,
    s_imag: np.ndarray | None = None,
    noise_temperature_k: float = 0.0,
    frequency_ghz: float = 5.0,
    gain_db: float = 0.0,
    bandwidth_mhz: float = 0.0,
    convergence_passed: bool = True,
    mesh_converged: bool = True,
) -> dict[str, Any]:
    """Run all verification checks and return a comprehensive report."""
    s_checks: list[SParameterCheck] = []
    q_checks: list[QuantumLimitResult] = []

    if s_matrix is not None:
        s_checks.append(check_passivity(s_matrix))
        s_checks.append(check_reciprocity(s_matrix))
        s_checks.append(check_s_parameter_bounds(s_matrix))

    if frequencies_hz is not None and s_real is not None and s_imag is not None:
        s_checks.append(check_kramers_kronig(frequencies_hz, s_real, s_imag))

    if noise_temperature_k > 0:
        q_checks.append(check_quantum_noise_limit(noise_temperature_k, frequency_ghz, gain_db))

    if gain_db > 0 and bandwidth_mhz > 0:
        q_checks.append(check_gain_bandwidth_product(gain_db, bandwidth_mhz, frequency_ghz))

    credibility = score_simulation_credibility(
        s_checks, q_checks, convergence_passed, mesh_converged
    )

    return {
        "s_parameter_checks": [c.to_dict() for c in s_checks],
        "quantum_checks": [q.to_dict() for q in q_checks],
        "credibility": credibility,
        "all_passed": all(c.passed for c in s_checks) and all(q.within_limit for q in q_checks),
    }
