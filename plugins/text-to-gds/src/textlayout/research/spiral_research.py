"""First-principles research for planar spiral inductors."""

from __future__ import annotations

from typing import Any

from textlayout.models import Technology
from textlayout.research.formulas import spiral_inductance_nh
from textlayout.research.models import Equation, Reference, ResearchReport

_REFERENCES = (
    Reference(
        "S. S. Mohan, M. del Mar Hershenson, S. P. Boyd, T. H. Lee, 'Simple Accurate "
        "Expressions for Planar Spiral Inductances', IEEE JSSC 34(10) (1999) 1419.",
        "Modified-Wheeler and current-sheet expressions used here.",
    ),
    Reference(
        "H. A. Wheeler, 'Simple Inductance Formulas for Radio Coils', Proc. IRE 16 (1928) 1398.",
        "",
    ),
)

_EQUATIONS = (
    Equation(
        "Modified Wheeler (square)",
        "L = K1*mu0*n^2*d_avg / (1 + K2*rho)",
        "K1=2.34, K2=2.75; d_avg=(d_out+d_in)/2.",
    ),
    Equation(
        "Fill ratio",
        "rho = (d_out - d_in) / (d_out + d_in)",
        "Density of the winding.",
    ),
)


def research_spiral(
    target: dict[str, float], parameters: dict[str, Any], tech: Technology
) -> ResearchReport:
    estimates: dict[str, Any]
    proposed: dict[str, Any] | None = None
    turns = parameters.get("turns")
    outer = parameters.get("outer_dimension_um")
    width = parameters.get("trace_width_um")
    spacing = parameters.get("spacing_um")
    if all(isinstance(value, (int, float)) for value in (turns, outer, width, spacing)):
        n = int(turns)  # type: ignore[arg-type]
        outer_um = float(outer)  # type: ignore[arg-type]
        width_um = float(width)  # type: ignore[arg-type]
        spacing_um = float(spacing)  # type: ignore[arg-type]
        inner_um = outer_um - 2.0 * n * width_um - 2.0 * (n - 1) * spacing_um
        if inner_um > 0:
            estimates = {
                "turns": n,
                "outer_dimension_um": outer_um,
                "inner_dimension_um": round(inner_um, 4),
                "estimated_inductance_nh": round(spiral_inductance_nh(n, outer_um, inner_um), 4),
            }
            proposed = dict(parameters)
        else:
            estimates = {"error": "Specified winding leaves no positive inner opening."}
    else:
        estimates = {"note": "L estimate requires turns, outer dimension, width, and spacing."}

    return ResearchReport(
        component="SpiralInductor",
        model_name="Modified-Wheeler / Mohan planar spiral inductor",
        physical_target=target,
        equations=_EQUATIONS,
        assumptions=(
            "Square planar spiral; uniform width and spacing; thin-film metal.",
            f"Substrate eps_r = {tech.substrate_epsilon_r} (technology {tech.name!r}).",
        ),
        references=_REFERENCES,
        analytical_estimates=estimates,
        design_notes=(
            "Turn count is the strongest inductance lever but raises resistance and capacitance.",
            "Trace width and spacing trade footprint, Q, and self-resonance.",
        ),
        limitations=(
            "The Mohan estimate does not establish Q or self-resonance.",
            "Skin effect, substrate loss, and parasitic capacitance require extraction.",
        ),
        simulation_recommendation={
            "inductance_and_resistance": "FastHenry/FastHenry2 first; Q3D/HFSS is optional correlation.",
        },
        proposed_parameters=proposed,
    )
