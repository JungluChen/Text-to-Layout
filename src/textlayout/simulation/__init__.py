"""Open-source simulation preparation with explicit evidence status."""

from textlayout.simulation.engine import simulate_layout
from textlayout.simulation.adapters import (
    FastHenryAdapter,
    FasterCapAdapter,
    JoSIMAdapter,
    OpenEMSAdapter,
    adapter_for,
)
from textlayout.simulation.fastercap import prepare_idc_fastercap, run_fastercap
from textlayout.simulation.models import EVIDENCE_STAGES, READINESS_LABELS, SimulationResult
from textlayout.simulation.josim import parse_josim_csv, prepare_squid_josim, run_josim
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
    "FastHenryAdapter",
    "FasterCapAdapter",
    "JoSIMAdapter",
    "OpenEMSAdapter",
    "READINESS_LABELS",
    "SimulationResult",
    "extract_resonance_from_touchstone",
    "adapter_for",
    "find_executable",
    "parse_fasthenry_inductance",
    "parse_josim_csv",
    "prepare_idc_fastercap",
    "prepare_cpw_openems",
    "prepare_resonator_openems",
    "prepare_spiral_fasthenry",
    "prepare_squid_plan",
    "prepare_squid_josim",
    "run_fastercap",
    "run_fasthenry",
    "run_openems",
    "run_josim",
    "simulate_layout",
]
