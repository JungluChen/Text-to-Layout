"""Reviewed design experience, with applicability and evidence boundaries.

Rules are explicit engineering knowledge, not learned model weights. Calibration
requires independently measured devices through textlayout.measurement.
"""

from __future__ import annotations

from typing import TypedDict


class DesignRule(TypedDict):
    id: str
    rationale: str
    action: str
    evidence: str


_COMMON: tuple[DesignRule, ...] = (
    {"id": "process-before-signoff",
     "rationale": "Fabrication rules and material properties depend on the process.",
     "action": "Supply a versioned PDK, metal thickness, substrate and operating temperature.",
     "evidence": "Generic technology parameters are assumptions; geometry DRC is not foundry signoff."},
    {"id": "independent-export-check",
     "rationale": "The exported mask must preserve conductor connectivity and clearances.",
     "action": "Require independent GDS readback, width checks and net-aware spacing checks.",
     "evidence": "KLayout checks the generated GDS; design_review.geometry_passed reports the verdict."},
    {"id": "measurement-learning",
     "rationale": "A process correction needs measurements paired with the exact design.",
     "action": "Use design hashes to pair simulation and measurement, preserve provenance, "
               "then assess corrections on devices held out from fitting.",
     "evidence": "textlayout measurement calibrate; generated predictions are not measured data."},
)

_DEVICE: dict[str, tuple[DesignRule, ...]] = {
    "CPW": (
        {"id": "cpw-ratio-before-scale",
         "rationale": "In the lossless thick-substrate model, impedance depends on gap/width.",
         "action": "Solve the elliptic-integral ratio, then scale width and gap together "
                   "to meet process minima and the GDS grid.",
         "evidence": "SciPy Brent solver; 16 constrained cases checked in BENCHMARK_SPEC.md."},
        {"id": "cpw-physical-corrections",
         "rationale": "Finite metal/substrate thickness and kinetic inductance can shift impedance.",
         "action": "Extract S-parameters with actual ground returns, ports and stack before release.",
         "evidence": "The analytical CPW estimate is not an openEMS or Palace result."},
    ),
    "IDC": (
        {"id": "idc-fixed-knobs",
         "rationale": "Finger count provides coarse tuning; overlap provides fine tuning.",
         "action": "Respect fixed dimensions and process minima; tune only free dimensions.",
         "evidence": "Bahl/Alley analytical sizing; optimizer records fixed knobs and convergence."},
        {"id": "idc-gap-model-limit",
         "rationale": "The current analytical estimate does not resolve arbitrary width/gap effects.",
         "action": "Use FasterCap on both conductor nets and check discretization convergence.",
         "evidence": "An analytical target match alone cannot validate physical capacitance."},
    ),
    "SpiralInductor": (
        {"id": "spiral-continuity",
         "rationale": "One continuous winding is required; disconnected corners change the circuit.",
         "action": "Check exported metal continuity and full trace width, including reversed segments.",
         "evidence": "Regression test_synthesis_constraints.py checks merged KLayout geometry."},
        {"id": "spiral-model-and-process",
         "rationale": "Modified Wheeler is an approximate geometric-inductance model.",
         "action": "Extract with FastHenry; add process-specific kinetic inductance and "
                   "check self-resonance before using a superconducting RF device.",
         "evidence": "Mohan et al. (1999), DOI 10.1109/4.792620; measured error remains in the benchmark."},
    ),
    "QuarterWaveResonator": (
        {"id": "resonator-electrical-length",
         "rationale": "A quarter-wave length is only the initial resonance estimate.",
         "action": "Model termination, coupling, bends, dielectric and metal effects in a field solver.",
         "evidence": "Paper parity requires the paper's exact geometry, stack and boundary conditions."},
    ),
    "SQUID": (
        {"id": "junction-process-required",
         "rationale": "Junction placeholders do not specify a working Josephson device.",
         "action": "Supply junction Ic, capacitance, resistance, loop inductance and bias conditions.",
         "evidence": "JoSIM circuit checks require process data; polygons alone do not establish gain."},
    ),
}


def design_rules_for(component: str) -> list[DesignRule]:
    """Return isolated review cards so an AI caller cannot mutate shared rules."""
    families = {"JPA": ("IDC", "SQUID"), "TestStructure": ("IDC", "CPW"),
                "TestChip": ("IDC", "CPW", "SpiralInductor")}.get(component, (component,))
    rules = list(_COMMON)
    for family in families:
        rules.extend(_DEVICE.get(family, ()))
    return [rule.copy() for rule in rules]
