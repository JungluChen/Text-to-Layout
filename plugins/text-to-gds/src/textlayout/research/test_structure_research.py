"""First-principles research for the IDC + CPW measurement test structure."""

from __future__ import annotations

from typing import Any

from textlayout.models import Technology
from textlayout.research import formulas as F
from textlayout.research.models import Equation, Reference, ResearchReport

_REFERENCES = (
    Reference(
        "I. J. Bahl, 'Lumped Elements for RF and Microwave Circuits', Artech House, 2003, Ch. 2.",
        "Closed-form interdigital capacitance for the device under test.",
    ),
    Reference(
        "R. N. Simons, 'Coplanar Waveguide Circuits, Components, and Systems', Wiley, 2001.",
        "CPW characteristic impedance for the feed sections.",
    ),
    Reference(
        "D. F. Williams & R. B. Marks, 'Transmission line capacitance measurement', "
        "IEEE Microwave and Guided Wave Letters 1 (1991) 243.",
        "Why launch/feed parasitics must be de-embedded from a capacitance measurement.",
    ),
)

_EQUATIONS = (
    Equation(
        "Bahl IDC capacitance",
        "C = (eps_re + 1) * l * [(N - 3)*A1 + A2]",
        "Device under test only; feed and launch metal are excluded.",
    ),
    Equation(
        "CPW impedance (conformal mapping)",
        "Z0 = 30*pi/sqrt(eps_eff) * K(k')/K(k)",
        "Feed sections; k = w/(w+2g).",
    ),
)

_LIMITATIONS = (
    "The capacitance model covers the IDC region only; launch pads and feed traces add "
    "parasitic shunt capacitance that a real measurement must de-embed.",
    "The CPW feed impedance is an analytical estimate; no EM solver validates the "
    "launch-to-feed and feed-to-IDC transitions.",
    "No radiation, substrate loss, or self-resonance model is included.",
)


def research_test_structure(
    target: dict[str, float], parameters: dict[str, Any], tech: Technology
) -> ResearchReport:
    eps_r = tech.substrate_epsilon_r
    pairs = int(parameters.get("finger_pairs", 20))
    overlap = float(parameters.get("overlap_um", 250.0))
    feed_w = float(parameters.get("feed_width_um", 10.0))
    feed_g = float(parameters.get("feed_gap_um", 6.0))

    c_pf = F.idc_capacitance_pf(pairs, overlap, eps_r)
    z0, eps_eff = F.cpw_z0(feed_w, feed_g, eps_r)
    estimates: dict[str, Any] = {
        "substrate_eps_r": eps_r,
        "estimated_capacitance_pf": round(c_pf, 4),
        "feed_estimated_z0_ohm": round(z0, 4),
        "feed_effective_permittivity": round(eps_eff, 4),
    }
    target_c = target.get("capacitance_pf")
    if target_c:
        estimates["target_capacitance_pf"] = target_c
        estimates["estimate_vs_target_pct"] = round(100.0 * (c_pf - target_c) / target_c, 1)

    return ResearchReport(
        component="TestStructure",
        model_name="Bahl/Alley IDC + conformal-mapping CPW feed (composite analytical model)",
        physical_target=target,
        equations=_EQUATIONS,
        assumptions=(
            f"Substrate eps_r = {eps_r} (from technology {tech.name!r}).",
            "The device under test is the embedded IDC; feeds are treated as ideal "
            "50-ohm-class access lines.",
            "Launch pads are probe-compatible rectangles, not a calibrated GSG standard.",
        ),
        references=_REFERENCES,
        analytical_estimates=estimates,
        design_notes=(
            "Only the IDC region is exported to FasterCap; the report must state that feeds "
            "and launches are not simulated.",
            "Keep the ground clearance constant along the structure so the feed impedance "
            "estimate stays meaningful.",
        ),
        limitations=_LIMITATIONS,
        simulation_recommendation={
            "capacitance": "FasterCap/FastCap on the embedded IDC region (documented extraction region).",
            "transitions": "Full-wave EM (openEMS/HFSS/Sonnet) for launch and step transitions — not performed here.",
        },
    )
