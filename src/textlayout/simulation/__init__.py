"""Open-source simulation preparation with explicit evidence status."""

from textlayout.simulation.engine import simulate_layout
from textlayout.simulation.fastercap import prepare_idc_fastercap, run_fastercap
from textlayout.simulation.models import READINESS_LABELS, SimulationResult
from textlayout.simulation.open_source import (
    prepare_cpw_openems,
    prepare_resonator_openems,
    prepare_spiral_fasthenry,
    prepare_squid_plan,
)

__all__ = [
    "READINESS_LABELS",
    "SimulationResult",
    "prepare_idc_fastercap",
    "prepare_cpw_openems",
    "prepare_resonator_openems",
    "prepare_spiral_fasthenry",
    "prepare_squid_plan",
    "run_fastercap",
    "simulate_layout",
]
