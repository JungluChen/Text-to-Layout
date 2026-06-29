"""First-principles research for a DC-SQUID loop test structure (no generator yet)."""

from __future__ import annotations

from typing import Any

from textlayout.models import Technology
from textlayout.research.models import Equation, Reference, ResearchReport

FLUX_QUANTUM_WB = 2.067_833_848e-15  # Phi_0 = h / 2e

_REFERENCES = (
    Reference("J. Clarke & A. I. Braginski (eds.), 'The SQUID Handbook', Vol. 1, Wiley, 2004.", ""),
    Reference("M. Tinkham, 'Introduction to Superconductivity', 2nd ed., Dover, 2004.", "Flux quantization, Josephson relations."),
)

_EQUATIONS = (
    Equation("Flux quantum", "Phi_0 = h / 2e = 2.07e-15 Wb", "Period of SQUID flux modulation."),
    Equation("Field modulation period", "dB = Phi_0 / A_loop", "Smaller loop area -> larger field period."),
    Equation("Screening parameter", "beta_L = 2 * L_loop * Ic / Phi_0", "Target beta_L ~ 1 for good modulation depth."),
)

_DESIGN_NOTES = (
    "Loop area sets flux sensitivity: V modulates with period Phi_0 in flux, i.e. dB = Phi_0/A in field.",
    "The two Josephson junctions must be symmetric (matched Ic) or the modulation depth and the "
    "optimal flux bias shift.",
    "Loop inductance L_loop and junction Ic set beta_L; beta_L near 1 maximises modulation depth.",
)

_LIMITATIONS = (
    "Junctions are layout placeholders (markers) — real Ic comes from the fabrication Jc and area.",
    "A generator for this component is not yet implemented — geometry is a documented proposal only.",
)


def research_squid(
    target: dict[str, float], parameters: dict[str, Any], tech: Technology
) -> ResearchReport:
    estimates: dict[str, Any] = {"flux_quantum_Wb": FLUX_QUANTUM_WB}
    area = target.get("loop_area_um2")
    if area:
        estimates["loop_area_um2"] = area
        estimates["field_modulation_period_uT"] = round(
            FLUX_QUANTUM_WB / (area * 1e-12) * 1e6, 4
        )
    return ResearchReport(
        component="SQUID",
        model_name="DC-SQUID loop, first-principles flux quantization",
        physical_target=target,
        equations=_EQUATIONS,
        assumptions=(
            "Two symmetric Josephson junctions; thin-film superconducting loop.",
            "Junctions represented as layout markers; Ic set later by Jc * area.",
        ),
        references=_REFERENCES,
        analytical_estimates=estimates,
        design_notes=_DESIGN_NOTES,
        limitations=_LIMITATIONS,
        simulation_recommendation={
            "inductance": "FastHenry / Q3D — loop inductance L_loop for beta_L.",
            "junction": "scqubits / JosephsonCircuits.jl — junction and SQUID electrical response.",
        },
        proposed_parameters=None,
    )
