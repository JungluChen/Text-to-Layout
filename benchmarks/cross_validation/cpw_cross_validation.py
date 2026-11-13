"""Analytical CPW reference and fail-closed placeholders for solver comparisons.

No numerical solver result is available from this module. Cross-solver acceptance
requires retained solver-owned outputs and provenance from separate executions.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from scipy.special import ellipk


@dataclass(frozen=True)
class CPWBenchmarkGeometry:
    """Standard 50-ohm Coplanar Waveguide on high-resistivity silicon."""

    center_width_um: float = 10.0
    gap_um: float = 6.5
    ground_width_um: float = 100.0
    substrate_thickness_um: float = 500.0
    substrate_epsilon_r: float = 11.7
    metal_thickness_um: float = 0.2
    length_um: float = 1000.0


@dataclass(frozen=True)
class AnalyticalGhioneNaldiResult:
    """Analytical Ghione/Naldi model outputs from scikit-rf."""

    z0_ohm: float
    effective_permittivity: float
    phase_velocity_m_per_s: float
    capacitance_per_m_f: float
    capacitance_per_um_ff: float


@dataclass(frozen=True)
class FasterCapBEMResult:
    """FasterCap Boundary Element Method (BEM) quasi-static result."""

    capacitance_per_m_f: float
    capacitance_per_um_ff: float
    relative_error_vs_analytical: float
    panel_count: int
    passed_tolerance: bool


@dataclass(frozen=True)
class HighFrequencyComparisonPoint:
    """Single frequency comparison between openEMS FDTD and Palace FEM."""

    frequency_ghz: float
    openems_fdtd_z0_ohm: float
    openems_fdtd_vp_m_s: float
    palace_fem_z0_ohm: float
    palace_fem_vp_m_s: float
    z0_relative_difference: float
    vp_relative_difference: float


@dataclass(frozen=True)
class CrossSolverBenchmarkReport:
    """Complete cross-solver EM benchmark report."""

    geometry: CPWBenchmarkGeometry
    analytical: AnalyticalGhioneNaldiResult
    fastercap: FasterCapBEMResult
    high_frequency_points: list[HighFrequencyComparisonPoint]
    discretization_analysis: dict[str, str]


def compute_analytical_ghione_naldi(
    geom: CPWBenchmarkGeometry | None = None,
    frequency_ghz: float = 5.0,
) -> AnalyticalGhioneNaldiResult:
    """Compute exact analytical CPW parameters using Ghione & Naldi (1984) conformal mapping."""
    geom = geom or CPWBenchmarkGeometry()
    try:
        from skrf import Frequency
        from skrf.media import CPW

        freq = Frequency(frequency_ghz, frequency_ghz, 1, unit="GHz")
        media = CPW(
            frequency=freq,
            w=geom.center_width_um * 1e-6,
            s=geom.gap_um * 1e-6,
            h=geom.substrate_thickness_um * 1e-6,
            t=geom.metal_thickness_um * 1e-6,
            ep_r=geom.substrate_epsilon_r,
            has_metal_backside=False,
        )
        z0 = float(abs(media.z0[0]))
        ep_reff = float(media.ep_reff[0].real)
        v_p = float(media.v_p[0].real)
        c_per_m = 1.0 / (z0 * v_p)
    except ImportError:
        # Exact analytical conformal mapping (Ghione & Naldi 1984) when scikit-rf is absent
        w = geom.center_width_um * 1e-6
        s = geom.gap_um * 1e-6
        h = geom.substrate_thickness_um * 1e-6
        t = geom.metal_thickness_um * 1e-6
        c0 = 299792458.0

        if t > 0:
            delta = (1.25 * t / math.pi) * (1.0 + math.log(4.0 * math.pi * w / t))
            we = w + delta
            se = s - delta
        else:
            we, se = w, s

        k0 = we / (we + 2.0 * se)
        k0p = math.sqrt(1.0 - k0 * k0)
        K0 = float(ellipk(k0**2))
        K0p = float(ellipk(k0p**2))

        k1 = math.sinh(math.pi * we / (4.0 * h)) / math.sinh(math.pi * (we + 2.0 * se) / (4.0 * h))
        k1p = math.sqrt(1.0 - k1 * k1)
        K1 = float(ellipk(k1**2))
        K1p = float(ellipk(k1p**2))

        q = (K1 / K1p) / (K0 / K0p)
        ep_reff = 1.0 + q * (geom.substrate_epsilon_r - 1.0) / 2.0
        if t > 0:
            ep_reff -= (0.7 * (ep_reff - 1.0) * (t / s)) / ((K0 / K0p) + 0.7 * (t / s))

        z0 = (30.0 * math.pi / math.sqrt(ep_reff)) * (K0p / K0)
        v_p = c0 / math.sqrt(ep_reff)
        c_per_m = 1.0 / (z0 * v_p)

    c_per_um_ff = c_per_m * 1e15 * 1e-6

    return AnalyticalGhioneNaldiResult(
        z0_ohm=z0,
        effective_permittivity=ep_reff,
        phase_velocity_m_per_s=v_p,
        capacitance_per_m_f=c_per_m,
        capacitance_per_um_ff=c_per_um_ff,
    )


def compute_fastercap_bem_capacitance(
    geom: CPWBenchmarkGeometry | None = None,
    *,
    mesh_refinement_level: int = 3,
) -> FasterCapBEMResult:
    """Require solver-owned FasterCap output before reporting BEM capacitance."""
    raise NotImplementedError("FasterCap CPW output and convergence evidence are not connected")


def compute_high_frequency_cross_validation(
    geom: CPWBenchmarkGeometry | None = None,
    frequencies_ghz: list[float] | None = None,
) -> list[HighFrequencyComparisonPoint]:
    """Require solver-owned openEMS and Palace outputs before comparison."""
    raise NotImplementedError("openEMS and Palace CPW outputs are not connected")


def run_cpw_cross_validation_benchmark() -> CrossSolverBenchmarkReport:
    """Reject a cross-solver report until solver-owned evidence is connected."""
    raise NotImplementedError("CPW cross-solver evidence is not available")
