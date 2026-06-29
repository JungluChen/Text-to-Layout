"""First-principles research for the interdigital capacitor (IDC)."""

from __future__ import annotations

from typing import Any

from textlayout.models import Technology
from textlayout.research import formulas as F
from textlayout.research.models import Equation, Reference, ResearchReport

_REFERENCES = (
    Reference(
        "I. J. Bahl, 'Lumped Elements for RF and Microwave Circuits', Artech House, 2003, Ch. 2.",
        "Closed-form interdigital capacitance used here.",
    ),
    Reference(
        "G. D. Alley, 'Interdigital Capacitors and Their Application to Lumped-Element "
        "Microwave Integrated Circuits', IEEE Trans. MTT-18 (1970) 1028.",
        "Original per-finger capacitance coefficients.",
    ),
    Reference(
        "S. S. Gevorgian et al., 'CAD models for multilayered substrate interdigital "
        "capacitors', IEEE Trans. MTT-44 (1996) 896.",
        "More accurate multilayer/finite-thickness models for EM cross-check.",
    ),
)

_EQUATIONS = (
    Equation(
        "Bahl IDC capacitance",
        "C = (eps_re + 1) * l * [(N - 3)*A1 + A2]",
        "N = 2*finger_pairs; l = overlap length [cm]; A1=0.089, A2=0.10 pF/cm.",
    ),
    Equation("Effective permittivity", "eps_re = (eps_r + 1) / 2", "Surface IDC on a thick substrate."),
    Equation(
        "Self-resonance (qualitative)",
        "f_SRF ~ 1 / (2*pi*sqrt(L_par * C))",
        "Parasitic series inductance L_par of the fingers/bus sets an upper usable frequency.",
    ),
)

_DESIGN_NOTES = (
    "Finger width sets current-handling and series resistance; too narrow raises loss and "
    "ohmic Q-degradation, too wide wastes area without adding much capacitance.",
    "Gap is the dominant capacitance lever: capacitance per unit length rises sharply as the "
    "gap shrinks, but the gap is bounded below by the process minimum-spacing rule.",
    "Overlap length l scales the capacitance linearly (see equation) — the cheapest knob for "
    "hitting a target value once gap/width are fixed by rules.",
    "Finger count N scales capacitance roughly linearly (the (N-3) term); more fingers means "
    "larger footprint and more parasitic inductance, lowering self-resonance.",
    "Parasitic series inductance of the bus and fingers creates a self-resonant frequency; "
    "above it the device no longer behaves as a capacitor.",
)

_LIMITATIONS = (
    "The Bahl model is quasi-static; accuracy depends on stack and geometry and requires EM correlation.",
    "It ignores finite metal thickness, fringing at finger ends, and substrate loss tangent.",
    "Self-resonance and Q are NOT predicted here — an EM solve is required before fabrication.",
)

_SIM = {
    "capacitance": "Ansys Q3D Extractor — quasi-static C between the two combs (see simulation/q3d_workflow.md).",
    "self_resonance_and_Q": "Ansys HFSS or Sonnet — full-wave S-parameters to find SRF and Q (simulation/hfss_workflow.md, sonnet_workflow.md).",
}


def research_idc(
    target: dict[str, float], parameters: dict[str, Any], tech: Technology
) -> ResearchReport:
    eps_r = tech.substrate_epsilon_r
    estimates: dict[str, Any] = {"substrate_eps_r": eps_r, "eps_re": (eps_r + 1) / 2}
    proposed: dict[str, Any] | None = None

    overlap = float(parameters.get("overlap_um", 250.0))
    target_c = target.get("capacitance_pf")

    if "finger_pairs" in parameters:
        pairs = int(parameters["finger_pairs"])
        c_pf = F.idc_capacitance_pf(pairs, overlap, eps_r)
        estimates["estimated_capacitance_pf"] = round(c_pf, 4)
        if target_c:
            estimates["target_capacitance_pf"] = target_c
            estimates["estimate_vs_target_pct"] = round(100.0 * (c_pf - target_c) / target_c, 1)

    if target_c:
        pairs_needed = F.idc_finger_pairs_for_target(target_c, overlap, eps_r)
        proposed = {
            "finger_pairs": pairs_needed,
            "finger_width_um": float(parameters.get("finger_width_um", 4.0)),
            "gap_um": float(parameters.get("gap_um", 2.0)),
            "overlap_um": overlap,
            "bus_width_um": float(parameters.get("bus_width_um", 25.0)),
            "metal_layer": str(parameters.get("metal_layer", "M1")),
        }
        estimates["proposed_finger_pairs_for_target"] = pairs_needed
        estimates["proposed_estimate_pf"] = round(
            F.idc_capacitance_pf(pairs_needed, overlap, eps_r), 4
        )

    return ResearchReport(
        component="IDC",
        model_name="Bahl/Alley quasi-static interdigital capacitor",
        physical_target=target,
        equations=_EQUATIONS,
        assumptions=(
            f"Substrate eps_r = {eps_r} (from technology {tech.name!r}).",
            "Coplanar fingers on a thick, lossless substrate; metal thickness neglected.",
            "Uniform fingers; end effects approximated by the two-terminal-finger term A2.",
        ),
        references=_REFERENCES,
        analytical_estimates=estimates,
        design_notes=_DESIGN_NOTES,
        limitations=_LIMITATIONS,
        simulation_recommendation=_SIM,
        proposed_parameters=proposed,
    )
