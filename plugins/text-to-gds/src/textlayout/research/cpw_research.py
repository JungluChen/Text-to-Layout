"""First-principles research for coplanar waveguides (CPW) and λ/4 resonators."""

from __future__ import annotations

from typing import Any

from textlayout.models import Technology
from textlayout.research import formulas as F
from textlayout.research.models import Equation, Reference, ResearchReport

_REFERENCES = (
    Reference(
        "R. N. Simons, 'Coplanar Waveguide Circuits, Components, and Systems', Wiley, 2001.",
        "Conformal-mapping CPW impedance model.",
    ),
    Reference(
        "W. Hilberg, 'From approximations to exact relations for characteristic impedances', "
        "IEEE Trans. MTT-17 (1969) 259.",
        "Closed-form K(k)/K(k') used here (error < 8e-6).",
    ),
    Reference(
        "G. Ghione and C. Naldi, 'Analytical Formulas for Coplanar Lines in Hybrid and "
        "Monolithic MICs', Electronics Letters 20(4), 1984, 179-181.",
        "Finite-substrate quasi-static model implemented by optional scikit-rf CPW.",
    ),
    Reference(
        "A. Arsenovic et al., 'scikit-rf: An Open Source Python Package for Microwave "
        "Network Creation, Analysis, and Calibration', IEEE Microwave Magazine 23(1), "
        "2022, 98-105, doi:10.1109/MMM.2021.3117139.",
        "Optional BSD-3 analytical and Touchstone implementation.",
    ),
    Reference(
        "D. M. Pozar, 'Microwave Engineering', 4th ed., Wiley, 2012.",
        "Transmission-line and λ/4 theory.",
    ),
)

_EQUATIONS = (
    Equation(
        "CPW impedance",
        "Z0 = (30*pi / sqrt(eps_eff)) * K(k')/K(k)",
        "k = w/(w+2g), k'=sqrt(1-k^2).",
    ),
    Equation(
        "Effective permittivity", "eps_eff = (1 + eps_r) / 2", "Thick-substrate quasi-static CPW."
    ),
    Equation("Phase velocity", "v_p = c / sqrt(eps_eff)", ""),
    Equation("Quarter-wave length", "L = v_p / (4 f)", "Physical length of a λ/4 resonator at f."),
)

_DESIGN_NOTES = (
    "The impedance depends only on the ratio k = w/(w+2g), not absolute size — so geometry can "
    "be scaled to satisfy the minimum-gap rule while holding Z0 fixed.",
    "On high-permittivity silicon, eps_eff is large, so a given Z0 needs a relatively narrow gap "
    "compared to a low-eps substrate.",
    "Ground-plane width and any top cover shift Z0 slightly; the thick-substrate model ignores them.",
    "For a λ/4 resonator, the open/short boundary and coupling capacitor pull the resonance down "
    "from the ideal v_p/4f — EM is needed for the exact f0 and Q.",
)

_LIMITATIONS = (
    "Quasi-static, infinitely thick substrate, zero metal thickness, lossless.",
    "No dispersion, radiation, or coupling effects — Z0 accurate to a few percent, f0 needs EM.",
)

_SIM = {
    "impedance_and_S_params": "openEMS / Sonnet / HFSS — full-wave Z0 and S-parameters (simulation/hfss_workflow.md).",
    "resonance_and_Q": "HFSS / Sonnet eigenmode — exact f0 and Q for the resonator.",
}


def research_cpw(
    target: dict[str, float], parameters: dict[str, Any], tech: Technology
) -> ResearchReport:
    eps_r = tech.substrate_epsilon_r
    eps_eff = F.cpw_eps_eff(eps_r)
    estimates: dict[str, Any] = {"substrate_eps_r": eps_r, "eps_eff": round(eps_eff, 4)}
    proposed: dict[str, Any] | None = None

    w = float(parameters.get("center_width_um", 10.0))
    g = parameters.get("gap_um")

    if g is not None:
        z0, _ = F.cpw_z0(w, float(g), eps_r)
        estimates["estimated_z0_ohm"] = round(z0, 2)
        skrf_estimate = F.cpw_skrf_z0(w, float(g), eps_r)
        if skrf_estimate is not None:
            estimates["scikit_rf_z0_ohm"] = round(skrf_estimate[0], 4)
            estimates["scikit_rf_eps_eff"] = round(skrf_estimate[1], 6)
            estimates["analytical_backend"] = "scikit-rf CPW (Ghione/Naldi)"
        else:
            estimates["analytical_backend"] = (
                "built-in Simons/Hilberg (install text-to-gds[rf] for scikit-rf correlation)"
            )

    target_z0 = target.get("impedance_ohm") or target.get("z0_ohm")
    if target_z0:
        gap_needed = F.cpw_gap_for_z0(target_z0, w, eps_r)
        estimates["target_z0_ohm"] = target_z0
        estimates["proposed_gap_um_for_target"] = round(gap_needed, 3)
        feasible = gap_needed >= tech.min_spacing_for(str(parameters.get("metal", "M1")))
        estimates["proposed_gap_meets_min_spacing"] = feasible
        proposed = {
            "center_width_um": w,
            "gap_um": round(gap_needed, 3),
            "length_um": float(parameters.get("length_um", 1000.0)),
            "metal": str(parameters.get("metal", "M1")),
        }

    f_ghz = target.get("frequency_ghz")
    if f_ghz:
        length = F.cpw_quarter_wave_length_um(f_ghz, eps_eff)
        estimates["target_frequency_ghz"] = f_ghz
        estimates["quarter_wave_length_um"] = round(length, 1)
        if proposed is None:
            proposed = {
                "center_width_um": w,
                "gap_um": float(g) if g is not None else 6.0,
                "length_um": round(length, 1),
                "metal": str(parameters.get("metal", "M1")),
            }
        else:
            proposed["length_um"] = round(length, 1)

    return ResearchReport(
        component="CPW",
        model_name="Conformal-mapping CPW (Simons/Hilberg) + λ/4 transmission-line theory",
        physical_target=target,
        equations=_EQUATIONS,
        assumptions=(
            f"Substrate eps_r = {eps_r} (from technology {tech.name!r}); eps_eff = (1+eps_r)/2.",
            "Symmetric CPW, thick substrate, zero metal thickness, lossless.",
        ),
        references=_REFERENCES,
        analytical_estimates=estimates,
        design_notes=_DESIGN_NOTES,
        limitations=_LIMITATIONS,
        simulation_recommendation=_SIM,
        proposed_parameters=proposed,
    )


def research_quarter_wave_resonator(
    target: dict[str, float], parameters: dict[str, Any], tech: Technology
) -> ResearchReport:
    """Research a quarter-wave CPW hanger using the cited CPW model."""
    base = research_cpw(target, parameters, tech)
    frequency = target.get("frequency_ghz")
    estimates = dict(base.analytical_estimates)
    if frequency:
        estimates["quarter_wave_length_um"] = round(
            F.cpw_quarter_wave_length_um(frequency, F.cpw_eps_eff(tech.substrate_epsilon_r)),
            4,
        )
    return ResearchReport(
        component="QuarterWaveResonator",
        model_name="Quarter-wave CPW hanger (Simons/Pozar initial model)",
        physical_target=target,
        equations=base.equations,
        assumptions=base.assumptions,
        references=base.references,
        analytical_estimates=estimates,
        design_notes=base.design_notes,
        limitations=base.limitations,
        simulation_recommendation={
            "resonance_and_Q": "openEMS plus scikit-rf; retain Touchstone and mesh-convergence evidence.",
        },
        proposed_parameters=dict(parameters),
    )
