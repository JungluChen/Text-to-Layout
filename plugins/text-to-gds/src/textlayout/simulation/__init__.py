"""Open-source simulation preparation with explicit evidence status."""

from textlayout.simulation.engine import simulate_layout
from textlayout.simulation.fastercap import prepare_idc_fastercap, run_fastercap
from textlayout.simulation.models import EVIDENCE_STAGES, READINESS_LABELS, SimulationResult
from textlayout.simulation.open_source import (
    prepare_cpw_openems,
    prepare_resonator_openems,
    prepare_spiral_fasthenry,
    prepare_squid_plan,
)
from textlayout.simulation.runners import (
    extract_resonance_from_touchstone,
    find_executable,
    parse_fasthenry_inductance,
    run_fasthenry,
    run_openems,
)

__all__ = [
    "EVIDENCE_STAGES",
    "READINESS_LABELS",
    "SimulationResult",
    "extract_resonance_from_touchstone",
    "find_executable",
    "parse_fasthenry_inductance",
    "prepare_idc_fastercap",
    "prepare_cpw_openems",
    "prepare_resonator_openems",
    "prepare_spiral_fasthenry",
    "prepare_squid_plan",
    "run_fastercap",
    "run_fasthenry",
    "run_openems",
    "simulate_layout",
]
