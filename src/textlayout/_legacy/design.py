from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any

from textlayout._legacy.adapters import list_simulation_adapters
from textlayout._legacy.process import DEFAULT_PROCESS


@dataclass(frozen=True)
class DesignTarget:
    kind: str
    center_frequency_ghz: float | None
    bandwidth_mhz: float | None
    gain_db: float | None
    impedance_ohm: float
    die_size_mm: tuple[float, float]


def _first_float_before_unit(prompt: str, units: tuple[str, ...]) -> float | None:
    unit_pattern = "|".join(re.escape(unit) for unit in units)
    match = re.search(rf"(\d+(?:\.\d+)?)\s*(?:{unit_pattern})", prompt, flags=re.IGNORECASE)
    return float(match.group(1)) if match else None


def _bandwidth_from_prompt(prompt: str) -> float | None:
    explicit_mhz = _first_float_before_unit(prompt, ("mhz", "megahertz"))
    if explicit_mhz is not None:
        return explicit_mhz
    explicit_ghz = _first_float_before_unit(prompt, ("ghz bandwidth", "gigahertz bandwidth"))
    if explicit_ghz is not None:
        return explicit_ghz * 1000.0
    if re.search(r"\b(wide|broad|broadband|wilde)\b", prompt, flags=re.IGNORECASE):
        return 500.0
    return None


def plan_ljpa_design(prompt: str) -> dict[str, Any]:
    """Plan a local-first LJPA workflow from a short natural-language request."""
    center_frequency = _first_float_before_unit(prompt, ("ghz", "gigahertz"))
    bandwidth_mhz = _bandwidth_from_prompt(prompt)
    gain_db = _first_float_before_unit(prompt, ("db", "decibel"))
    if gain_db is None:
        gain_db = 20.0

    target = DesignTarget(
        kind="lumped_element_josephson_parametric_amplifier",
        center_frequency_ghz=center_frequency,
        bandwidth_mhz=bandwidth_mhz,
        gain_db=gain_db,
        impedance_ohm=50.0,
        die_size_mm=(5.0, 5.0),
    )

    clarifying_questions = [
        "Which material system, junction technology, and target Jc should be used: Nb/AlOx/Nb, Al/AlOx/Al, or a measured process file?",
        "What exact 3 dB bandwidth, gain, noise, saturation power, and dynamic-range targets should define success?",
        "Should the LJPA be flux-pumped through an on-chip bias line, current-pumped, or pump-through-input?",
        "What layer stack, metal thicknesses, min-width/spacing rules, and allowed die area should be enforced?",
        "Which simulator should be authoritative for signoff: JosephsonCircuits.jl harmonic balance, JoSIM transient, or both?",
    ]

    assumptions = {
        "process_stack": DEFAULT_PROCESS.name,
        "materials": DEFAULT_PROCESS.to_dict()["materials"],
        "layout_strategy": [
            "Start from pre-verified JJ/SQUID, CPW, shunt capacitor, flux-bias, via, and ground-plane PCells.",
            "Keep all generated GDS and reports under workspace/artifacts.",
            "Use sidecar metadata as the contract between layout, DRC, extraction, and simulation.",
        ],
        "performance_couplings": {
            "junction_area_um2": "sets Ic and Lj for the selected Jc",
            "metal_thickness_nm": "changes sheet/kinetic inductance and current density margins",
            "cpw_trace_width_um_and_gap_um": "set impedance, phase velocity, and coupling",
            "line_length_um": "sets electrical delay and resonator frequency",
            "routing_angle_deg": "affects coupling, compactness, and DRC interactions",
        },
    }

    workflow = [
        "Clarify missing process and performance targets.",
        "Synthesize first-pass JJ/SQUID, shunt capacitance, CPW feedline, flux-bias, and ground-plane parameters.",
        "Compile registered gdsfactory PCells into GDS and a semantic sidecar.",
        "Run local KLayout DRC and sidecar extraction.",
        "Build a simulator-specific netlist/model from extracted JJ, CPW, capacitance, and coupling parameters.",
        "Run JosephsonCircuits.jl for gain/noise/S-parameters and JoSIM for transient sanity checks when installed.",
        "Iterate geometry parameters until DRC and simulation targets pass.",
        "Export final GDS, layout screenshot, 2.5D stack preview, DRC report, and simulation report.",
    ]

    return {
        "schema": "text-to-gds.design-plan.v0",
        "prompt": prompt,
        "target": asdict(target),
        "clarifying_questions": clarifying_questions,
        "assumptions": assumptions,
        "recommended_pcells": [
            "manhattan_josephson_junction",
            "cpw_straight",
            "meander_inductor",
            "flux_bias_line",
            "via_stack",
            "ground_plane",
        ],
        "simulation_adapters": list_simulation_adapters(),
        "workflow": workflow,
    }
