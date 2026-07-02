"""First-principles research for a symmetric two-junction SQUID test structure."""

from __future__ import annotations

from typing import Any, cast

from textlayout.models import Technology
from textlayout.research.formulas import josephson_inductance_ph, rectangular_loop_inductance_ph
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
    iw = parameters.get("loop_inner_width_um")
    ih = parameters.get("loop_inner_height_um")
    width = parameters.get("trace_width_um")
    if all(isinstance(value, (int, float)) for value in (iw, ih, width)):
        estimates["estimated_loop_inductance_ph"] = round(
            rectangular_loop_inductance_ph(
                float(cast(int | float, iw)),
                float(cast(int | float, ih)),
                float(cast(int | float, width)),
            ),
            4,
        )
    ic = parameters.get("critical_current_ua")
    if isinstance(ic, (int, float)):
        estimates["josephson_inductance_ph_per_junction"] = round(
            josephson_inductance_ph(float(ic)), 4
        )
        loop_l = parameters.get("loop_inductance_ph") or estimates.get(
            "estimated_loop_inductance_ph"
        )
        if isinstance(loop_l, (int, float)):
            estimates["screening_parameter_beta_l"] = round(
                2.0 * float(loop_l) * 1e-12 * float(ic) * 1e-6 / FLUX_QUANTUM_WB,
                6,
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
            "junction_response": "JoSIM RCSJ transient simulation with explicit Ic, R, C, and loop L.",
        },
        proposed_parameters=dict(parameters) if parameters else None,
    )
