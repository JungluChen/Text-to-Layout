"""First-principles research for planar spiral inductors (no generator yet)."""

from __future__ import annotations

from typing import Any

from textlayout.models import Technology
from textlayout.research.models import Equation, Reference, ResearchReport

_REFERENCES = (
    Reference(
        "S. S. Mohan, M. del Mar Hershenson, S. P. Boyd, T. H. Lee, 'Simple Accurate "
        "Expressions for Planar Spiral Inductances', IEEE JSSC 34(10) (1999) 1419.",
        "Modified-Wheeler and current-sheet expressions used here.",
    ),
    Reference("H. A. Wheeler, 'Simple Inductance Formulas for Radio Coils', Proc. IRE 16 (1928) 1398.", ""),
)

_EQUATIONS = (
    Equation(
        "Modified Wheeler (square)",
        "L = K1*mu0*n^2*d_avg / (1 + K2*rho)",
        "K1=2.34, K2=2.75 (square); d_avg=(d_out+d_in)/2; rho=(d_out-d_in)/(d_out+d_in).",
    ),
    Equation("Fill ratio", "rho = (d_out - d_in) / (d_out + d_in)", "Density of the winding."),
)

_DESIGN_NOTES = (
    "Inductance scales as n^2 — turn count is the strongest lever, but adds series resistance and "
    "inter-turn capacitance (lowering self-resonance).",
    "Trace width trades DC resistance (Q) against area and capacitance; spacing sets coupling and SRF.",
    "Substrate eddy currents and the dielectric loss tangent dominate Q at GHz frequencies.",
)

_LIMITATIONS = (
    "Mohan expressions are accurate to a few percent for L but say nothing about Q or SRF.",
    "A generator for this component is not yet implemented — geometry is a documented proposal only.",
)


def research_spiral(
    target: dict[str, float], parameters: dict[str, Any], tech: Technology
) -> ResearchReport:
    return ResearchReport(
        component="SpiralInductor",
        model_name="Modified-Wheeler / Mohan planar spiral inductor",
        physical_target=target,
        equations=_EQUATIONS,
        assumptions=(
            "Square planar spiral; uniform width/spacing; thin-film metal.",
            f"Substrate eps_r = {tech.substrate_epsilon_r} (technology {tech.name!r}).",
        ),
        references=_REFERENCES,
        analytical_estimates={"note": "L estimate requires d_out, d_in, n, width, spacing."},
        design_notes=_DESIGN_NOTES,
        limitations=_LIMITATIONS,
        simulation_recommendation={
            "inductance_and_Q": "Ansys Q3D / HFSS or FastHenry — extract L and Q over frequency.",
        },
        proposed_parameters=None,
    )
