"""First-principles research for a symmetric two-junction SQUID test structure."""

from __future__ import annotations

from typing import Any

from textlayout.models import Technology
from textlayout.research.models import Equation, Reference, ResearchReport

FLUX_QUANTUM_WB = 2.067_833_848e-15

_REFERENCES = (
    Reference("J. Clarke & A. I. Braginski (eds.), 'The SQUID Handbook', Vol. 1, Wiley, 2004."),
    Reference(
        "M. Tinkham, 'Introduction to Superconductivity', 2nd ed., Dover, 2004.",
        "Flux quantization and Josephson relations.",
    ),
)

_EQUATIONS = (
    Equation("Flux quantum", "Phi_0 = h / 2e = 2.07e-15 Wb"),
    Equation("Field modulation period", "dB = Phi_0 / A_loop"),
    Equation("Screening parameter", "beta_L = 2 * L_loop * Ic / Phi_0"),
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
            "Two symmetric junction placeholders in a thin-film superconducting loop.",
            f"Generic technology {tech.name!r}; no foundry junction stack is implied.",
        ),
        references=_REFERENCES,
        analytical_estimates=estimates,
        design_notes=(
            "Loop area sets the field modulation period.",
            "Matched junction critical currents are required for symmetric modulation.",
        ),
        limitations=(
            "Junction polygons are process placeholders; critical current requires Jc and overlap data.",
            "The generic JJ layer is not a qualified base/counter-electrode stack.",
        ),
        simulation_recommendation={
            "loop_inductance": "FastHenry or Elmer after a foundry stack and conductor thickness are supplied.",
            "junction_response": "Use a validated Josephson circuit solver with extracted Ic and L.",
        },
        proposed_parameters=dict(parameters) if parameters else None,
    )
