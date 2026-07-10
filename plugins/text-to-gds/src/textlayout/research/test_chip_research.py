"""First-principles research for the multi-device research test-chip tile."""

from __future__ import annotations

from typing import Any

from textlayout.models import Technology
from textlayout.research import formulas as F
from textlayout.research.models import Equation, Reference, ResearchReport

_REFERENCES = (
    Reference(
        "I. J. Bahl, 'Lumped Elements for RF and Microwave Circuits', Artech House, 2003.",
        "IDC and spiral-inductor lumped-element models used for the sub-block estimates.",
    ),
    Reference(
        "R. N. Simons, 'Coplanar Waveguide Circuits, Components, and Systems', Wiley, 2001.",
        "CPW impedance estimate for the transmission-line sub-block.",
    ),
    Reference(
        "S. M. Sze & K. K. Ng, 'Physics of Semiconductor Devices', Wiley, 3rd ed., 2007, "
        "lithography/alignment discussion.",
        "Role of alignment marks in multi-layer registration.",
    ),
)

_EQUATIONS = (
    Equation(
        "Bahl IDC capacitance",
        "C = (eps_re + 1) * l * [(N - 3)*A1 + A2]",
        "IDC sub-block estimate.",
    ),
    Equation(
        "CPW impedance (conformal mapping)",
        "Z0 = 30*pi/sqrt(eps_eff) * K(k')/K(k)",
        "CPW sub-block estimate.",
    ),
    Equation(
        "Modified Wheeler spiral inductance",
        "L = K1 * mu0 * n^2 * d_avg / (1 + K2 * rho)",
        "Spiral sub-block estimate.",
    ),
)

_LIMITATIONS = (
    "This tile is a geometry-level comparison candidate; no sub-block on the tile has been "
    "simulated in place, and inter-device coupling is not modeled.",
    "All electrical numbers are per-sub-device analytical estimates, valid only in isolation.",
    "Alignment marks and the title label are lithographic aids with no electrical model.",
    "The tile is not fabrication-ready: process DRC, density rules, and dicing margins are "
    "not checked.",
)


def research_test_chip(
    target: dict[str, float], parameters: dict[str, Any], tech: Technology
) -> ResearchReport:
    eps_r = tech.substrate_epsilon_r
    pairs = int(parameters.get("idc_finger_pairs", 20))
    overlap = float(parameters.get("idc_overlap_um", 250.0))
    cpw_w = float(parameters.get("cpw_center_width_um", 10.0))
    cpw_g = float(parameters.get("cpw_gap_um", 6.0))
    turns = int(parameters.get("spiral_turns", 4))
    outer = float(parameters.get("spiral_outer_dimension_um", 300.0))
    trace = float(parameters.get("spiral_trace_width_um", 4.0))
    spacing = float(parameters.get("spiral_spacing_um", 2.0))
    inner = outer - 2.0 * turns * trace - 2.0 * (turns - 1) * spacing

    z0, eps_eff = F.cpw_z0(cpw_w, cpw_g, eps_r)
    estimates: dict[str, Any] = {
        "substrate_eps_r": eps_r,
        "idc_estimated_capacitance_pf": round(F.idc_capacitance_pf(pairs, overlap, eps_r), 4),
        "cpw_estimated_z0_ohm": round(z0, 4),
        "cpw_effective_permittivity": round(eps_eff, 4),
        "spiral_estimated_inductance_nh": round(F.spiral_inductance_nh(turns, outer, inner), 4),
    }

    return ResearchReport(
        component="TestChip",
        model_name="Composite per-sub-device analytical models (Bahl IDC, conformal CPW, Wheeler spiral)",
        physical_target=target,
        equations=_EQUATIONS,
        assumptions=(
            f"Substrate eps_r = {eps_r} (from technology {tech.name!r}).",
            "Sub-devices are far enough apart that mutual coupling is neglected (not verified).",
            "Single-metal process; alignment marks assume a second lithography level exists.",
        ),
        references=_REFERENCES,
        analytical_estimates=estimates,
        design_notes=(
            "Every electrical claim on the tile must name the sub-device it belongs to and be "
            "labeled analytical unless a solver ran on that sub-device geometry.",
            "The tile outline lives on the TEXT layer so the bounding box equals the tile size "
            "without adding functional metal.",
        ),
        limitations=_LIMITATIONS,
        simulation_recommendation={
            "IDC_sub_block": "FasterCap/FastCap on the standalone IDC geometry (identical parameters).",
            "full_tile": "Full-wave EM of the assembled tile — future work, not performed here.",
        },
    )
